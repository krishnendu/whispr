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
    block: bool
    reason: str = ""


JUDGE_PROMPT = (
    "You are a content moderator for a chat app. Decide if this assistant message "
    "violates any of these HARD rules:\n"
    "  1. Sexualizing minors in any way.\n"
    "  2. Detailed instructions for self-harm or suicide methods.\n"
    "  3. Credible, specific threats of violence against a real person.\n"
    "  4. Explicit non-consensual sexual scenarios.\n"
    "  5. Doxxing — sharing real names, addresses, phone numbers, or identifying info.\n"
    "\n"
    "Be CONSERVATIVE — only block clear-cut violations. Flirty, mature, dark, "
    "or emotional language is fine. Profanity is fine.\n"
    "\n"
    "Reply with ONE JSON object on a single line, nothing else:\n"
    '  {"block": true|false, "reason": "<short>"}\n'
)


class Judge(Protocol):
    def check(self, text: str) -> Verdict: ...


class MockJudge:
    def check(self, text: str) -> Verdict:
        return Verdict(block=False)


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
            return Verdict(block=False)

        # The model is told to emit pure JSON, but be defensive.
        match = re.search(r"\{.*?\}", raw, re.DOTALL)
        if not match:
            return Verdict(block=False)
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return Verdict(block=False)
        return Verdict(block=bool(data.get("block", False)), reason=str(data.get("reason", "")))


def get_judge() -> Judge:
    if settings.GROQ_API_KEY:
        return GroqJudge(settings.GROQ_API_KEY, settings.GROQ_BASE_URL, settings.GROQ_DEFAULT_MODEL)
    return MockJudge()
