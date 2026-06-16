"""Match queue: pair waiting users by tag overlap, fall back to a persona after T seconds."""

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.bots.models import Persona
from apps.chat.models import Conversation
from apps.moderation.models import Block

from .models import MatchQueueEntry


def _user_tag_slugs(user) -> list[str]:
    return list(user.user_tags.values_list("tag__slug", flat=True))


def _try_pair(entry: MatchQueueEntry) -> Conversation | None:
    """Try to pair `entry` with another waiting user. Returns the created Conversation, or None."""
    my_tags = set(entry.tag_slugs)
    # Filter out: self, shadow-banned, anyone I've blocked, anyone who's blocked me.
    blocked_out = set(Block.objects.filter(user_a=entry.user).values_list("user_b_id", flat=True))
    blocked_in = set(Block.objects.filter(user_b=entry.user).values_list("user_a_id", flat=True))
    excluded = {entry.user_id} | blocked_out | blocked_in
    candidates = (
        MatchQueueEntry.objects.select_for_update()
        .exclude(user_id__in=excluded)
        .exclude(user__is_shadow_banned=True)
        .filter(matched_conversation__isnull=True)
        .order_by("joined_at")
    )
    best = None
    best_overlap = 0
    # candidates is ordered by joined_at ASC, so the *first* candidate at any overlap level wins
    for c in candidates:
        overlap = len(my_tags & set(c.tag_slugs))
        if overlap > best_overlap:
            best_overlap = overlap
            best = c

    if best is None:
        return None

    conversation = Conversation.objects.create(
        kind="human",
        participant_a=entry.user,
        participant_b=best.user,
    )
    # mark both entries as matched but don't delete yet — the other side reads it via /match/status
    MatchQueueEntry.objects.filter(pk__in=[entry.pk, best.pk]).update(
        matched_conversation=conversation
    )
    return conversation


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def match_start(request):
    user = request.user
    if not user.onboarding_complete:
        return Response({"detail": "Finish onboarding first."}, status=400)
    if user.is_shadow_banned:
        # Silent failure — user thinks they're queued but never gets matched.
        return Response({"status": "waiting"})

    tag_slugs = _user_tag_slugs(user)
    if not tag_slugs:
        return Response({"detail": "Pick at least one tag."}, status=400)

    with transaction.atomic():
        entry, _ = MatchQueueEntry.objects.select_for_update().get_or_create(
            user=user, defaults={"tag_slugs": tag_slugs}
        )
        # refresh tag set in case they edited their vibe since last queue
        entry.tag_slugs = tag_slugs
        entry.matched_conversation = None
        entry.save(update_fields=["tag_slugs", "matched_conversation"])

        convo = _try_pair(entry)

    if convo is not None:
        return Response({"status": "matched", "conversation_id": convo.pk})
    return Response({"status": "waiting"})


def _pick_persona_for(user_tags: set[str], user) -> Persona | None:
    """Return the active persona whose allowed_tags overlap most with the user's tags."""
    best = None
    best_overlap = -1
    for p in Persona.objects.filter(is_active=True):
        if p.spice_level != "sfw" and not user.age_confirmed:
            continue
        overlap = len(user_tags & set(p.allowed_tags or []))
        if overlap > best_overlap:
            best_overlap = overlap
            best = p
    return best


def _fallback_to_persona(entry: MatchQueueEntry) -> Conversation | None:
    user_tags = set(entry.tag_slugs)
    persona = _pick_persona_for(user_tags, entry.user)
    if persona is None:
        return None
    convo = Conversation.objects.create(
        kind="bot", participant_a=entry.user, persona=persona
    )
    entry.matched_conversation = convo
    entry.save(update_fields=["matched_conversation"])
    return convo


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def match_status(request):
    entry = MatchQueueEntry.objects.filter(user=request.user).first()
    if entry is None:
        return Response({"status": "idle"})
    if entry.matched_conversation_id:
        # consume — once polled, remove the queue entry
        convo_id = entry.matched_conversation_id
        entry.delete()
        return Response({"status": "matched", "conversation_id": convo_id})

    # Fallback: if no human appeared after T seconds, route to a persona.
    waited = (timezone.now() - entry.joined_at).total_seconds()
    if waited >= settings.WHISPR_BOT_FALLBACK_AFTER_S:
        with transaction.atomic():
            entry.refresh_from_db()
            if not entry.matched_conversation_id:
                convo = _fallback_to_persona(entry)
                if convo is not None:
                    entry.delete()
                    return Response({"status": "matched", "conversation_id": convo.pk})

    return Response({"status": "waiting"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def match_cancel(request):
    MatchQueueEntry.objects.filter(user=request.user, matched_conversation__isnull=True).delete()
    return Response({"status": "cancelled"})
