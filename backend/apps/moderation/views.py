"""Report, block, admin queue."""

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.chat.models import Conversation
from whispr.ratelimit import check_rate

from .models import AuditLog, Ban, Block, Report

User = get_user_model()


# ---------- Report ----------

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def file_report(request):
    convo_id = request.data.get("conversation_id")
    reason = request.data.get("reason", "other")
    note = (request.data.get("note") or "")[:1000]

    if reason not in {c[0] for c in Report.REASON_CHOICES}:
        return Response({"detail": "Invalid reason."}, status=400)

    if not check_rate(f"report:{request.user.id}", limit=10, window_s=86400):
        return Response({"detail": "Too many reports today."}, status=429)

    target_user = None
    convo = None
    if convo_id:
        convo = Conversation.objects.filter(pk=convo_id).first()
        if convo is None or request.user.id not in (convo.participant_a_id, convo.participant_b_id):
            return Response({"detail": "Not your conversation."}, status=403)
        if convo.kind == "human":
            target_user = (
                convo.participant_b if convo.participant_a_id == request.user.id else convo.participant_a
            )

    Report.objects.create(
        reporter=request.user,
        target_user=target_user,
        conversation=convo,
        reason=reason,
        note=note,
    )
    # Soft trust-score decay on the target. Auto-shadow-ban deliberately not wired —
    # operator still gates the harsh action.
    if target_user is not None:
        target_user.trust_score = max(0, target_user.trust_score - 5)
        target_user.save(update_fields=["trust_score"])
    return Response({"filed": True})


# ---------- Block ----------

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def block_in_conversation(request, convo_id: int):
    convo = get_object_or_404(Conversation, pk=convo_id)
    if request.user.id not in (convo.participant_a_id, convo.participant_b_id):
        return Response({"detail": "Not your conversation."}, status=403)
    if convo.kind != "human":
        return Response({"detail": "Cannot block a persona."}, status=400)
    target = (
        convo.participant_b if convo.participant_a_id == request.user.id else convo.participant_a
    )
    if target is None:
        return Response({"detail": "No other party."}, status=400)
    Block.objects.get_or_create(user_a=request.user, user_b=target)
    if convo.ended_at is None:
        convo.ended_at = timezone.now()
        convo.save(update_fields=["ended_at"])
    return Response({"blocked": True})


# ---------- Admin queue ----------

def _require_operator(request):
    if not request.user.is_authenticated or not request.user.is_operator:
        return Response({"detail": "Operator only."}, status=403)
    return None


def _serialize_report(r: Report) -> dict:
    return {
        "id": r.id,
        "reporter": r.reporter.handle if r.reporter else None,
        "target": r.target_user.handle if r.target_user else None,
        "target_id": r.target_user.id if r.target_user else None,
        "conversation_id": r.conversation_id,
        "reason": r.reason,
        "note": r.note,
        "status": r.status,
        "created_at": r.created_at.isoformat(),
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_reports(request):
    blocked = _require_operator(request)
    if blocked:
        return blocked
    qs = Report.objects.select_related("reporter", "target_user").order_by("-created_at")[:200]
    return Response({"reports": [_serialize_report(r) for r in qs]})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_dismiss_report(request, report_id: int):
    blocked = _require_operator(request)
    if blocked:
        return blocked
    r = get_object_or_404(Report, pk=report_id)
    r.status = "dismissed"
    r.save(update_fields=["status"])
    AuditLog.objects.create(
        actor=request.user,
        action="report_dismissed",
        target_type="report",
        target_id=str(r.pk),
        payload={"reason": r.reason},
    )
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_action_report(request, report_id: int):
    """Shadow-ban the target and mark the report actioned."""
    blocked = _require_operator(request)
    if blocked:
        return blocked
    r = get_object_or_404(Report, pk=report_id)
    if r.target_user_id:
        target = r.target_user
        target.is_shadow_banned = True
        target.save(update_fields=["is_shadow_banned"])
        Ban.objects.create(user=target, kind="shadow", reason=f"report#{r.id}: {r.reason}")
    r.status = "actioned"
    r.save(update_fields=["status"])
    AuditLog.objects.create(
        actor=request.user,
        action="report_actioned",
        target_type="report",
        target_id=str(r.pk),
        payload={"reason": r.reason, "target_user_id": r.target_user_id},
    )
    return Response({"ok": True})


# ---------- Admin user list ----------


def _serialize_user(u) -> dict:
    return {
        "id": u.id,
        "handle": u.handle,
        "trust_score": u.trust_score,
        "is_shadow_banned": u.is_shadow_banned,
        "is_verified": bool(u.oauth_provider),
        "age_confirmed": u.age_confirmed,
        "created_at": u.date_joined.isoformat() if u.date_joined else None,
        "last_seen": u.last_seen.isoformat() if u.last_seen else None,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_users(request):
    blocked = _require_operator(request)
    if blocked:
        return blocked
    UserModel = get_user_model()
    q = (request.query_params.get("q") or "").strip().lower()
    qs = UserModel.objects.all()
    if q:
        qs = qs.filter(handle__icontains=q)
    qs = qs.order_by("-date_joined")[:100]
    return Response({"users": [_serialize_user(u) for u in qs]})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_toggle_shadow_ban(request, user_id: int):
    blocked = _require_operator(request)
    if blocked:
        return blocked
    UserModel = get_user_model()
    target = get_object_or_404(UserModel, pk=user_id)
    if target.id == request.user.id:
        return Response({"detail": "Can't ban yourself."}, status=400)
    target.is_shadow_banned = not target.is_shadow_banned
    target.save(update_fields=["is_shadow_banned"])
    if target.is_shadow_banned:
        Ban.objects.create(user=target, kind="shadow", reason="manual admin action")
    AuditLog.objects.create(
        actor=request.user,
        action="shadow_ban_toggled",
        target_type="user",
        target_id=str(target.pk),
        payload={"is_shadow_banned": target.is_shadow_banned, "handle": target.handle},
    )
    return Response({"is_shadow_banned": target.is_shadow_banned})


# ---------- Admin audit log ----------


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_audit_log(request):
    blocked = _require_operator(request)
    if blocked:
        return blocked
    action = (request.query_params.get("action") or "").strip()
    qs = AuditLog.objects.select_related("actor").order_by("-created_at")
    if action:
        qs = qs.filter(action=action)
    qs = qs[:200]
    return Response(
        {
            "entries": [
                {
                    "id": e.id,
                    "actor": e.actor.handle if e.actor else None,
                    "action": e.action,
                    "target_type": e.target_type,
                    "target_id": e.target_id,
                    "payload": e.payload,
                    "created_at": e.created_at.isoformat(),
                }
                for e in qs
            ]
        }
    )
