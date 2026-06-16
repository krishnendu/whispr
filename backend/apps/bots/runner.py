"""Spawn a daemon thread per user message in a bot conversation.

The thread:
 1. Pulls persona + memory + recent window from the DB.
 2. Calls the BotEngine for a reply.
 3. Splits via humanize() into bubbles with delays.
 4. Writes each bubble as a Message with `sent_at` staggered into the future,
    so the polling endpoint reveals them at the right time.

For prod this gets replaced by a real worker (Fly/Railway) reading the same
queue/stream. The shape stays identical.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from apps.chat.models import Conversation, Message
from apps.moderation.judge import get_judge

from .engine import ChatTurn, get_engine, humanize
from .models import BotJob, PersonaMemory

log = logging.getLogger(__name__)

WINDOW_SIZE = 20


def schedule_bot_reply(conversation_id: int) -> None:
    """Persist a BotJob and try to process it now via an in-process thread.

    The job is the durable artifact — the thread is just an optimistic fast path.
    If the thread dies (e.g. serverless function instance recycled), the cron
    drain or a standalone worker will pick the job up later.
    """
    job = BotJob.objects.create(conversation=Conversation.objects.get(pk=conversation_id))
    t = threading.Thread(
        target=_run_job,
        args=(job.pk,),
        name=f"bot-reply-{conversation_id}",
        daemon=True,
    )
    t.start()


def _run_job(job_id: int) -> None:
    try:
        _claim_and_run(job_id)
    except Exception:  # noqa: BLE001 - top-level thread boundary
        log.exception("bot reply thread crashed")
    finally:
        close_old_connections()


def _claim_and_run(job_id: int) -> bool:
    """Atomically transition a pending job to working, run it, mark done/failed.

    Returns True if this caller did the work, False if someone else already had it.
    """
    claimed = BotJob.objects.filter(pk=job_id, status="pending").update(
        status="working", claimed_at=timezone.now()
    )
    if not claimed:
        return False
    job = BotJob.objects.get(pk=job_id)
    try:
        _do_run(job.conversation_id)
        job.status = "done"
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "completed_at"])
    except Exception as exc:  # noqa: BLE001
        log.exception("bot job %s failed", job_id)
        job.status = "failed"
        job.error = str(exc)[:1000]
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error", "completed_at"])
    return True


def drain_orphans(max_jobs: int = 25, stale_after_s: int = 30) -> dict:
    """Claim and run any pending jobs older than `stale_after_s`.

    Called by /api/cron/process-bot-jobs and by the standalone worker loop.
    """
    cutoff = timezone.now() - timedelta(seconds=stale_after_s)
    candidates = list(
        BotJob.objects.filter(status="pending", created_at__lte=cutoff)
        .order_by("created_at")
        .values_list("pk", flat=True)[:max_jobs]
    )
    done = 0
    skipped = 0
    for jid in candidates:
        if _claim_and_run(jid):
            done += 1
        else:
            skipped += 1
    return {"considered": len(candidates), "done": done, "skipped": skipped}


def _do_run(conversation_id: int) -> None:
    convo = Conversation.objects.select_related("persona", "participant_a").filter(
        pk=conversation_id, kind="bot"
    ).first()
    if convo is None or convo.persona is None or convo.ended_at is not None:
        return

    user = convo.participant_a
    persona = convo.persona

    # Recent window from PG (already sorted desc / oldest-first slicing).
    window_qs = convo.messages.order_by("-sent_at")[:WINDOW_SIZE]
    window = list(reversed(list(window_qs)))
    history: list[ChatTurn] = [
        ChatTurn(role="user" if m.sender_id is not None else "assistant", content=m.body)
        for m in window
    ]
    if not history:
        return

    memory, _ = PersonaMemory.objects.get_or_create(user=user, persona=persona)
    system_prompt = _compose_system_prompt(persona.system_prompt, memory)

    engine = get_engine()
    try:
        text = engine.reply(system_prompt, history)
    except Exception as exc:  # noqa: BLE001
        log.warning("engine.reply failed: %s", exc)
        text = "give me a sec, brain's lagging…"

    bubbles = humanize(text)
    if not bubbles:
        return

    judge = get_judge()
    now = timezone.now()
    cumulative = 0.0
    for delay, body in bubbles:
        cumulative += delay
        send_at = now + timedelta(seconds=cumulative)
        verdict = judge.check(body)
        mod_flags = {}
        if verdict.block:
            log.info("moderation blocked bubble: %s", verdict.reason)
            body = "[redacted]"
            mod_flags = {"blocked": True, "reason": verdict.reason}
        with transaction.atomic():
            Message.objects.create(
                conversation=convo,
                sender=None,  # null sender = persona
                body=body,
                sent_at=send_at,
                mod_flags=mod_flags,
                is_redacted=verdict.block,
            )
            convo.last_activity_at = send_at
            convo.save(update_fields=["last_activity_at"])

            # Rotation: keep only the last N persisted per conversation.
            keep = settings.WHISPR_MSG_WARM_KEEP
            ids_to_keep = list(
                convo.messages.order_by("-sent_at").values_list("pk", flat=True)[:keep]
            )
            convo.messages.exclude(pk__in=ids_to_keep).delete()

    # Update the persona memory's window snapshot.
    _update_memory(memory, window, bubbles)


def _compose_system_prompt(base: str, memory: PersonaMemory) -> str:
    facts = memory.facts or {}
    if not facts and not memory.rolling_summary:
        return base
    addenda: list[str] = []
    if facts:
        addenda.append("Things you've learned about this user: " + ", ".join(f"{k}={v}" for k, v in facts.items()))
    if memory.rolling_summary:
        addenda.append("Earlier in your conversation: " + memory.rolling_summary)
    return base + "\n\n" + "\n".join(addenda)


def _update_memory(
    memory: PersonaMemory,
    window: list[Message],
    new_bubbles: list[tuple[float, str]],
) -> None:
    window_payload = [
        {"role": "user" if m.sender_id is not None else "assistant", "content": m.body}
        for m in window
    ] + [{"role": "assistant", "content": body} for _, body in new_bubbles]
    memory.last_window = window_payload[-WINDOW_SIZE:]
    memory.save(update_fields=["last_window", "updated_at"])
