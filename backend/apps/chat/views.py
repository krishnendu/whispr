"""Conversation + message endpoints. Polling + SSE."""

import json
import time

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


def _other_handle(convo: Conversation, viewer_id: int) -> str:
    if convo.kind == "bot":
        return convo.persona.name if convo.persona else "persona"
    other = convo.participant_b if convo.participant_a_id == viewer_id else convo.participant_a
    return other.handle if other else "—"


def _convo_payload(convo: Conversation, viewer_id: int, messages_qs) -> dict:
    return {
        "id": convo.id,
        "kind": convo.kind,
        "other_handle": _other_handle(convo, viewer_id),
        "started_at": convo.started_at.isoformat(),
        "ended_at": convo.ended_at.isoformat() if convo.ended_at else None,
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

    convo = get_object_or_404(Conversation, pk=convo_id)
    if not _ensure_participant(convo, request.user.id):
        return Response({"detail": "Not your conversation."}, status=403)
    if convo.ended_at:
        return Response({"detail": "Conversation ended."}, status=400)

    with transaction.atomic():
        msg = Message.objects.create(conversation=convo, sender=request.user, body=body)
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
    return Response({"ended": True})


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

    def gen():
        try:
            cursor = after_id
            start = time.time()
            last_ping = time.time()
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

                convo.refresh_from_db(fields=["ended_at"])
                if convo.ended_at is not None:
                    yield "event: end\ndata: {}\n\n"
                    break

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
