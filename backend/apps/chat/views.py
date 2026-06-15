"""Conversation + message endpoints. Polling-based for now; Ably comes next."""

from django.conf import settings
from django.db import models, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.bots.runner import schedule_bot_reply

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
