"""Persona memory fact extractor.

Run periodically (every Nth bot reply) to update PersonaMemory.facts with
small atomic facts a persona "learned" about the user — favorite music,
job, location vibe, mood, etc.

The extractor is intentionally narrow:
 - Outputs a JSON object with short keys → short values
 - Merges into existing facts (new keys win, blank values clear)
 - Drops anything that smells like a phone number / address / email
"""

from __future__ import annotations

import json
import logging
import re
from typing import Iterable

from django.conf import settings

from .engine import ChatTurn, get_engine
from .models import PersonaMemory

log = logging.getLogger(__name__)


EXTRACT_PROMPT = (
    "Read this chat. Extract up to 5 short, lasting facts about the USER "
    "(the human, not you). Each fact is a tiny key→value pair such as:\n"
    "  - name → alex\n"
    "  - likes → bedroom pop, chess\n"
    "  - mood → vent\n"
    "  - location_vibe → west coast\n"
    "Skip greetings, pleasantries, and anything that would only matter once.\n"
    "NEVER record: phone numbers, addresses, full names, email addresses, "
    "credit card numbers, government IDs.\n"
    "If nothing's worth recording, return {}.\n"
    'Output a single JSON object on one line, e.g. {"likes": "chess", "mood": "chill"}.\n'
    "Output ONLY the JSON, no preamble."
)


_PII_RE = re.compile(
    r"(?ix)"
    r"(?:\+?\d[\d\s().-]{7,}\d)"       # phone-ish
    r"|(?:[\w.+-]+@[\w.-]+\.[a-z]{2,})"  # email-ish
    r"|(?:\d{1,5}\s+[A-Za-z][\w\s]{3,}\s+(?:st|ave|rd|blvd|ln|dr|street|avenue|road))"
)


def _sanitize(value: str) -> str | None:
    value = value.strip()[:80]
    if not value or _PII_RE.search(value):
        return None
    return value


def extract_facts(messages: Iterable[dict]) -> dict[str, str]:
    """messages: iterable of {role, content}."""
    if not settings.GROQ_API_KEY:
        return {}
    history = [ChatTurn(role=m["role"], content=m["content"][:500]) for m in messages]
    try:
        raw = get_engine().reply(EXTRACT_PROMPT, history)
    except Exception as exc:  # noqa: BLE001
        log.warning("fact extractor failed: %s", exc)
        return {}

    match = re.search(r"\{.*?\}", raw, re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}

    out: dict[str, str] = {}
    for key, value in list(data.items())[:5]:
        if not isinstance(key, str) or not isinstance(value, (str, int, float)):
            continue
        clean_key = re.sub(r"[^a-z0-9_]+", "_", str(key).strip().lower())[:32]
        clean_value = _sanitize(str(value))
        if clean_key and clean_value:
            out[clean_key] = clean_value
    return out


def maybe_extract(memory: PersonaMemory, every_n_bubbles: int = 6) -> None:
    """Decide whether to extract this round, do it if so."""
    window = memory.last_window or []
    if len(window) < every_n_bubbles:
        return
    # Skip if we've already extracted recently — rough heuristic on facts size.
    if len(memory.facts or {}) >= 8:
        # Already rich, save the tokens.
        return

    new_facts = extract_facts(window)
    if not new_facts:
        return

    facts = dict(memory.facts or {})
    facts.update(new_facts)
    # Cap total facts so the system prompt stays small.
    if len(facts) > 10:
        facts = dict(list(facts.items())[-10:])
    memory.facts = facts
    memory.save(update_fields=["facts", "updated_at"])
