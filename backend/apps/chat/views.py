"""Conversation + message endpoints. Polling + SSE."""

import json
import time
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections, models, transaction
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.bots.runner import schedule_bot_reply
from whispr.ratelimit import check_rate

from .models import Conversation, Message


def _serialize_message(m: Message, viewer_id: int) -> dict:
    return {
        "id": m.id,
        "body": m.body,
        "sent_at": m.sent_at.isoformat(),
        "is_me": m.sender_id == viewer_id,
        "is_persona": m.sender_id is None,
    }


def _ensure_participant(convo: Conversation, user_id: int) -> bool:
    return user_id in (convo.participant_a_id, convo.participant_b_id)


def _other(convo: Conversation, viewer_id: int):
    if convo.kind == "bot":
        return None
    return convo.participant_b if convo.participant_a_id == viewer_id else convo.participant_a


def _other_handle(convo: Conversation, viewer_id: int) -> str:
    if convo.kind == "bot":
        return convo.persona.name if convo.persona else "persona"
    other = _other(convo, viewer_id)
    return other.handle if other else "—"


def _convo_payload(convo: Conversation, viewer_id: int, messages_qs) -> dict:
    user_is_a = convo.participant_a_id == viewer_id
    other = _other(convo, viewer_id)
    return {
        "id": convo.id,
        "kind": convo.kind,
        "other_handle": _other_handle(convo, viewer_id),
        "other_verified": bool(other.oauth_provider) if other else False,
        "started_at": convo.started_at.isoformat(),
        "ended_at": convo.ended_at.isoformat() if convo.ended_at else None,
        "is_vaulted": convo.is_vaulted_by_a if user_is_a else convo.is_vaulted_by_b,
        "messages": [_serialize_message(m, viewer_id) for m in messages_qs],
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_conversation(request, convo_id: int):
    convo = get_object_or_404(
        Conversation.objects.select_related("participant_a", "participant_b", "persona"),
        pk=convo_id,
    )
    if not _ensure_participant(convo, request.user.id):
        return Response({"detail": "Not your conversation."}, status=403)

    messages = (
        convo.messages.filter(sent_at__lte=timezone.now())
        .order_by("sent_at")[: settings.WHISPR_MSG_HOT_BUFFER]
    )
    return Response(_convo_payload(convo, request.user.id, messages))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def poll_conversation(request, convo_id: int):
    """Return messages newer than `?after=<id>`. Used by clients polling for the other side's replies."""
    convo = get_object_or_404(Conversation, pk=convo_id)
    if not _ensure_participant(convo, request.user.id):
        return Response({"detail": "Not your conversation."}, status=403)
    try:
        after_id = int(request.query_params.get("after", "0"))
    except ValueError:
        after_id = 0

    new_msgs = (
        convo.messages.filter(pk__gt=after_id, sent_at__lte=timezone.now())
        .order_by("sent_at")
    )
    return Response(
        {
            "messages": [_serialize_message(m, request.user.id) for m in new_msgs],
            "ended": convo.ended_at is not None,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def post_message(request, convo_id: int):
    body = (request.data.get("body") or "").strip()
    if not body:
        return Response({"detail": "Empty message."}, status=400)
    if len(body) > 2000:
        return Response({"detail": "Message too long."}, status=400)

    if not check_rate(f"msg:{request.user.id}", limit=30, window_s=60):
        return Response({"detail": "Slow down."}, status=429)

    signals_raw = request.data.get("signals") or {}
    behavior_signals: dict = {}
    if isinstance(signals_raw, dict):
        for key in ("typing_ms", "paste_count", "length"):
            v = signals_raw.get(key)
            if isinstance(v, (int, float)):
                behavior_signals[key] = int(v)

    convo = get_object_or_404(Conversation, pk=convo_id)
    if not _ensure_participant(convo, request.user.id):
        return Response({"detail": "Not your conversation."}, status=403)
    if convo.ended_at:
        return Response({"detail": "Conversation ended."}, status=400)

    with transaction.atomic():
        msg = Message.objects.create(
            conversation=convo,
            sender=request.user,
            body=body,
            behavior_signals=behavior_signals,
        )
        convo.last_activity_at = timezone.now()
        convo.save(update_fields=["last_activity_at"])

        # Rotation: keep only the last N persisted messages per conversation
        keep = settings.WHISPR_MSG_WARM_KEEP
        ids_to_keep = list(
            convo.messages.order_by("-sent_at").values_list("pk", flat=True)[:keep]
        )
        convo.messages.exclude(pk__in=ids_to_keep).delete()

    if convo.kind == "bot":
        schedule_bot_reply(convo.pk)

    return Response(_serialize_message(msg, request.user.id))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def end_conversation(request, convo_id: int):
    convo = get_object_or_404(Conversation, pk=convo_id)
    if not _ensure_participant(convo, request.user.id):
        return Response({"detail": "Not your conversation."}, status=403)
    if convo.ended_at is None:
        convo.ended_at = timezone.now()
        convo.save(update_fields=["ended_at"])
        _maybe_award_trust(convo)
    return Response({"ended": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reroll_conversation(request, convo_id: int):
    """End the current conversation and immediately re-enter the match queue.

    One round-trip replaces the end-then-match dance the client used to do —
    avoids a race where the matcher could pair the user before the end commits.
    """
    from apps.matching.views import enqueue_and_match

    convo = get_object_or_404(Conversation, pk=convo_id)
    if not _ensure_participant(convo, request.user.id):
        return Response({"detail": "Not your conversation."}, status=403)
    if convo.kind != "human":
        return Response({"detail": "Reroll is for human chats only."}, status=400)
    if convo.ended_at is None:
        convo.ended_at = timezone.now()
        convo.save(update_fields=["ended_at"])
        _maybe_award_trust(convo)
    return enqueue_and_match(request.user)


def _maybe_award_trust(convo: Conversation) -> None:
    """If the conversation went the distance, bump both participants' trust."""
    if convo.kind != "human" or convo.participant_b_id is None:
        return
    msg_count = convo.messages.count()
    if msg_count < 10:
        return
    for u in (convo.participant_a, convo.participant_b):
        if u is None:
            continue
        u.trust_score = min(100, u.trust_score + 1)
        u.save(update_fields=["trust_score"])


# ---------- Typing indicator ----------

TYPING_TTL_S = 5


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def signal_typing(request, convo_id: int):
    convo = get_object_or_404(Conversation, pk=convo_id)
    if not _ensure_participant(convo, request.user.id):
        return Response({"detail": "Not your conversation."}, status=403)
    if convo.ended_at:
        return Response({"detail": "Conversation ended."}, status=400)
    until = timezone.now() + timedelta(seconds=TYPING_TTL_S)
    if convo.participant_a_id == request.user.id:
        convo.typing_a_until = until
        convo.save(update_fields=["typing_a_until"])
    else:
        convo.typing_other_until = until
        convo.save(update_fields=["typing_other_until"])
    return Response({"ok": True})


# ---------- Vault ----------

VAULT_MAX = 10


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def vault_conversation(request, convo_id: int):
    convo = get_object_or_404(Conversation, pk=convo_id)
    if not _ensure_participant(convo, request.user.id):
        return Response({"detail": "Not your conversation."}, status=403)
    user_is_a = convo.participant_a_id == request.user.id

    # Cap the user's vault — drop the oldest if at the limit.
    if user_is_a and not convo.is_vaulted_by_a:
        _evict_oldest_vault(request.user.id, "a")
        convo.is_vaulted_by_a = True
        convo.save(update_fields=["is_vaulted_by_a"])
    elif not user_is_a and not convo.is_vaulted_by_b:
        _evict_oldest_vault(request.user.id, "b")
        convo.is_vaulted_by_b = True
        convo.save(update_fields=["is_vaulted_by_b"])
    return Response({"vaulted": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unvault_conversation(request, convo_id: int):
    convo = get_object_or_404(Conversation, pk=convo_id)
    if not _ensure_participant(convo, request.user.id):
        return Response({"detail": "Not your conversation."}, status=403)
    if convo.participant_a_id == request.user.id:
        convo.is_vaulted_by_a = False
        convo.save(update_fields=["is_vaulted_by_a"])
    else:
        convo.is_vaulted_by_b = False
        convo.save(update_fields=["is_vaulted_by_b"])
    return Response({"vaulted": False})


def _evict_oldest_vault(user_id: int, side: str) -> None:
    field = "is_vaulted_by_a" if side == "a" else "is_vaulted_by_b"
    qs = Conversation.objects.filter(**{field: True})
    if side == "a":
        qs = qs.filter(participant_a_id=user_id)
    else:
        qs = qs.filter(participant_b_id=user_id)
    if qs.count() < VAULT_MAX:
        return
    oldest = qs.order_by("started_at").first()
    if oldest is not None:
        setattr(oldest, field, False)
        oldest.save(update_fields=[field])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_vault(request):
    a = Conversation.objects.filter(
        participant_a=request.user, is_vaulted_by_a=True
    ).select_related("persona", "participant_b")
    b = Conversation.objects.filter(
        participant_b=request.user, is_vaulted_by_b=True
    ).select_related("persona", "participant_a")
    items = []
    for c in list(a) + list(b):
        items.append(
            {
                "id": c.id,
                "kind": c.kind,
                "other_handle": _other_handle(c, request.user.id),
                "summary_text": c.summary_text or "",
                "started_at": c.started_at.isoformat(),
                "ended_at": c.ended_at.isoformat() if c.ended_at else None,
            }
        )
    items.sort(key=lambda x: x["started_at"], reverse=True)
    return Response({"items": items})


# ---------- Server-Sent Events ----------
#
# EventSource doesn't let JS set headers, so auth is via `?token=`. The frontend
# already has the DRF token in memory (handed down server-side from
# requireUser()), so this isn't a real downgrade.
#
# We exit the loop ~270s in so we stay under Vercel's 300s function timeout.
# The browser auto-reconnects EventSource and sends Last-Event-ID so we
# resume from the last message id without losing anything.

SSE_MAX_LIFETIME_S = 270
SSE_TICK_S = 0.25
SSE_KEEPALIVE_S = 15


@require_GET
def stream_conversation(request, convo_id: int):
    token_key = request.GET.get("token")
    if not token_key:
        return HttpResponse(status=401)
    try:
        token = Token.objects.select_related("user").get(key=token_key)
    except Token.DoesNotExist:
        return HttpResponse(status=401)
    user = token.user

    convo = Conversation.objects.filter(pk=convo_id).first()
    if convo is None or not _ensure_participant(convo, user.id):
        return HttpResponse(status=404)

    # Resume cursor: prefer Last-Event-ID (browser auto-reconnect), fall back to ?after=
    last_event_id = request.META.get("HTTP_LAST_EVENT_ID") or request.GET.get("after", "0")
    try:
        after_id = int(last_event_id)
    except (TypeError, ValueError):
        after_id = 0

    user_is_a = convo.participant_a_id == user.id

    def gen():
        try:
            cursor = after_id
            start = time.time()
            last_ping = time.time()
            last_typing_emitted = False
            # Flush a comment immediately so the browser opens the stream.
            yield ":ok\n\n"

            while True:
                if time.time() - start > SSE_MAX_LIFETIME_S:
                    break

                new_msgs = list(
                    convo.messages.filter(pk__gt=cursor, sent_at__lte=timezone.now())
                    .order_by("sent_at")
                )
                for m in new_msgs:
                    payload = _serialize_message(m, user.id)
                    yield (
                        f"id: {m.id}\n"
                        f"event: message\n"
                        f"data: {json.dumps(payload)}\n\n"
                    )
                    cursor = m.id

                convo.refresh_from_db(
                    fields=["ended_at", "typing_a_until", "typing_other_until"]
                )
                if convo.ended_at is not None:
                    yield "event: end\ndata: {}\n\n"
                    break

                # Typing — emit a state change for the OTHER side.
                other_until = convo.typing_other_until if user_is_a else convo.typing_a_until
                typing_now = other_until is not None and other_until > timezone.now()
                if typing_now != last_typing_emitted:
                    yield (
                        f"event: typing\ndata: {json.dumps({'typing': typing_now})}\n\n"
                    )
                    last_typing_emitted = typing_now

                now = time.time()
                if now - last_ping > SSE_KEEPALIVE_S:
                    yield ":keepalive\n\n"
                    last_ping = now

                time.sleep(SSE_TICK_S)
        finally:
            # Daemon-thread DB connection hygiene.
            close_old_connections()

    response = StreamingHttpResponse(gen(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # disable any upstream buffering
    return response
