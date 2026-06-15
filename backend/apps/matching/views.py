"""Match queue: pair waiting users by tag overlap."""

from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.chat.models import Conversation

from .models import MatchQueueEntry


def _user_tag_slugs(user) -> list[str]:
    return list(user.user_tags.values_list("tag__slug", flat=True))


def _try_pair(entry: MatchQueueEntry) -> Conversation | None:
    """Try to pair `entry` with another waiting user. Returns the created Conversation, or None."""
    my_tags = set(entry.tag_slugs)
    candidates = (
        MatchQueueEntry.objects.select_for_update()
        .exclude(user_id=entry.user_id)
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
    return Response({"status": "waiting"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def match_cancel(request):
    MatchQueueEntry.objects.filter(user=request.user, matched_conversation__isnull=True).delete()
    return Response({"status": "cancelled"})
