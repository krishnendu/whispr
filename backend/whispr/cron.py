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

import logging

from apps.accounts.models import MagicLinkToken
from apps.bots.engine import ChatTurn, get_engine
from apps.bots.runner import drain_orphans
from apps.chat.models import Conversation, Message
from apps.matching.models import MatchQueueEntry

log = logging.getLogger(__name__)


SUMMARY_PROMPT = (
    "You are summarizing a brief chat for our records. Write 1–2 short sentences "
    "describing the vibe and topic of the conversation. No names. No greetings. "
    "Output ONLY the summary, no preamble."
)


def _summarize(messages: list[Message]) -> str:
    if not messages:
        return ""
    history = [
        ChatTurn(
            role="user" if m.sender_id is not None else "assistant",
            content=m.body[:500],
        )
        for m in messages
    ]
    try:
        text = get_engine().reply(SUMMARY_PROMPT, history)
        return text.strip()[:500]
    except Exception as exc:  # noqa: BLE001
        log.warning("summarizer failed: %s", exc)
        return ""


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

    # Summarize then drop raw text from ended/idle conversations.
    drained = 0
    summarized = 0
    for convo in Conversation.objects.filter(
        ended_at__isnull=False, summary_text=""
    ):
        msgs = list(
            Message.objects.filter(conversation_id=convo.id).order_by("sent_at")
        )
        summary = _summarize(msgs) or "(drained)"
        drained += Message.objects.filter(conversation_id=convo.id).delete()[0]
        Conversation.objects.filter(pk=convo.id).update(summary_text=summary)
        if summary != "(drained)":
            summarized += 1

    # Tokens older than 1h have no business sticking around.
    stale_tokens, _ = MagicLinkToken.objects.filter(created_at__lt=magic_cutoff).delete()

    # Abandoned match queue entries (client crashed, never cancelled).
    stale_queue, _ = MatchQueueEntry.objects.filter(joined_at__lt=queue_cutoff).delete()

    return JsonResponse(
        {
            "ok": True,
            "idle_closed": idle_closed,
            "messages_drained": drained,
            "summarized": summarized,
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
