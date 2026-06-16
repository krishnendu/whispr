"""Daily housekeeping. Triggered by Vercel Cron via /api/cron/cleanup.

Protected by a shared secret in the `Authorization: Bearer …` header.
Set CRON_SECRET in env on Vercel and inside the cron job config.
"""

from datetime import timedelta

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.accounts.models import MagicLinkToken
from apps.bots.runner import drain_orphans
from apps.chat.models import Conversation, Message
from apps.matching.models import MatchQueueEntry


def _require_cron_secret(request):
    expected = settings.CRON_SECRET
    provided = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not expected or provided != expected:
        return JsonResponse({"detail": "unauthorized"}, status=401)
    return None


@csrf_exempt
@require_http_methods(["GET", "POST"])
def cleanup(request):
    if (denied := _require_cron_secret(request)) is not None:
        return denied

    now = timezone.now()
    idle_cutoff = now - timedelta(days=settings.WHISPR_CONVO_IDLE_DAYS)
    magic_cutoff = now - timedelta(hours=1)
    queue_cutoff = now - timedelta(minutes=10)

    # Close idle conversations.
    idle_closed = Conversation.objects.filter(
        ended_at__isnull=True, last_activity_at__lt=idle_cutoff
    ).update(ended_at=now)

    # Drop raw text from ended/idle conversations (keep aggregates).
    drained = 0
    for convo in Conversation.objects.filter(
        ended_at__isnull=False, summary_text=""
    ).only("id"):
        # Per the plan: summarize, then drop raw text. Summary is currently empty —
        # a real summarizer can be wired later; for now we just drop the raw text.
        drained += Message.objects.filter(conversation_id=convo.id).delete()[0]
        Conversation.objects.filter(pk=convo.id).update(summary_text="(drained)")

    # Tokens older than 1h have no business sticking around.
    stale_tokens, _ = MagicLinkToken.objects.filter(created_at__lt=magic_cutoff).delete()

    # Abandoned match queue entries (client crashed, never cancelled).
    stale_queue, _ = MatchQueueEntry.objects.filter(joined_at__lt=queue_cutoff).delete()

    return JsonResponse(
        {
            "ok": True,
            "idle_closed": idle_closed,
            "messages_drained": drained,
            "stale_tokens": stale_tokens,
            "stale_queue": stale_queue,
        }
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def process_bot_jobs(request):
    """Drain any BotJobs the in-process thread didn't finish.

    Runs every minute on Vercel Cron. A standalone worker can hit the same
    function via apps.bots.runner.drain_orphans() directly.
    """
    if (denied := _require_cron_secret(request)) is not None:
        return denied
    result = drain_orphans()
    return JsonResponse({"ok": True, **result})
