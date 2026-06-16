"""Outbound moderation judge.

Cheap, defensive: a single Groq call asks "is this message a hard violation".
On block, the message body is redacted before it ever reaches the recipient.

Hard violations only — we don't want to over-block bot personality (a flirty
persona being flirty is fine). The system prompt lists the specific lines that
trigger a block.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Protocol

import requests
from django.conf import settings

log = logging.getLogger(__name__)


@dataclass
class Verdict:
    """Three-way moderation outcome.

    - ok:    deliver as-is.
    - soft:  deliver but blur client-side until the recipient taps to reveal.
    - block: redact entirely.
    """

    level: str = "ok"  # "ok" | "soft" | "block"
    reason: str = ""

    @property
    def block(self) -> bool:
        return self.level == "block"

    @property
    def soft(self) -> bool:
        return self.level == "soft"


JUDGE_PROMPT = (
    "You are a content moderator for a chat app. Classify this assistant message:\n"
    "\n"
    "BLOCK if it does any of these:\n"
    "  1. Sexualizes minors in any way.\n"
    "  2. Gives detailed instructions for self-harm or suicide methods.\n"
    "  3. Makes a credible, specific threat of violence against a real person.\n"
    "  4. Describes explicit non-consensual sexual scenarios.\n"
    "  5. Doxxes — shares real names, addresses, phone numbers, or identifying info.\n"
    "\n"
    "SOFT-FLAG (deliver but blur until tapped) if it is:\n"
    "  - Sexually explicit beyond mild flirting.\n"
    "  - Graphically violent or gory.\n"
    "  - Heavy emotional content (suicidal ideation discussed, intense distress) — "
    "    NOT methods, which are BLOCK.\n"
    "  - Uses slurs.\n"
    "\n"
    "Otherwise OK. Flirty, mature, dark, or emotional language is fine. Profanity is fine.\n"
    "Be conservative on BLOCK; be willing to use SOFT for genuinely intense content.\n"
    "\n"
    "Reply with ONE JSON object on a single line, nothing else:\n"
    '  {"verdict": "ok"|"soft"|"block", "reason": "<short>"}\n'
)


class Judge(Protocol):
    def check(self, text: str) -> Verdict: ...


class MockJudge:
    def check(self, text: str) -> Verdict:
        return Verdict(level="ok")


class GroqJudge:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def check(self, text: str) -> Verdict:
        try:
            r = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": JUDGE_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 60,
                },
                timeout=10,
            )
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # noqa: BLE001
            log.warning("moderation judge failed: %s — fail-open", exc)
            return Verdict(level="ok")

        # The model is told to emit pure JSON, but be defensive.
        match = re.search(r"\{.*?\}", raw, re.DOTALL)
        if not match:
            return Verdict(level="ok")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return Verdict(level="ok")
        # Accept either {"verdict": ...} or the older {"block": bool} shape.
        if "verdict" in data:
            level = str(data.get("verdict", "ok")).lower()
            if level not in ("ok", "soft", "block"):
                level = "ok"
        else:
            level = "block" if bool(data.get("block", False)) else "ok"
        return Verdict(level=level, reason=str(data.get("reason", "")))


def get_judge() -> Judge:
    if settings.GROQ_API_KEY:
        return GroqJudge(settings.GROQ_API_KEY, settings.GROQ_BASE_URL, settings.GROQ_DEFAULT_MODEL)
    return MockJudge()
