"""Bot engine: Groq via OpenAI-compatible API, plus a Mock fallback for dev without a key.

The engine is intentionally tiny — it takes the persona system prompt, recent message
window, and the new user message, and returns a single string. The humanizer splits
that string into bubbles + delays so it feels paced.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from typing import Iterable, Protocol

import requests
from django.conf import settings


@dataclass
class ChatTurn:
    role: str  # "user" | "assistant"
    content: str


class BotEngine(Protocol):
    def reply(self, system_prompt: str, history: Iterable[ChatTurn]) -> str: ...


class MockEngine:
    """Returns a deterministic response so you can dev without a Groq key."""

    def reply(self, system_prompt: str, history: Iterable[ChatTurn]) -> str:
        last_user = ""
        for turn in history:
            if turn.role == "user":
                last_user = turn.content
        bits = [
            f"Heh, you said: \"{last_user}\".",
            "I'm running in mock mode so I can't really think yet.",
            "Plug a GROQ_API_KEY in and try again ✨",
        ]
        return " ".join(bits)


class GroqEngine:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def reply(self, system_prompt: str, history: Iterable[ChatTurn]) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        for turn in history:
            messages.append({"role": turn.role, "content": turn.content})

        r = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": 0.85,
                "max_tokens": 240,
                "top_p": 0.95,
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()


def get_engine() -> BotEngine:
    if settings.GROQ_API_KEY:
        return GroqEngine(settings.GROQ_API_KEY, settings.GROQ_BASE_URL, settings.GROQ_DEFAULT_MODEL)
    return MockEngine()


# ---------- Humanizer ----------

_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\s*\n+\s*")


def humanize(text: str, max_bubbles: int = 3) -> list[tuple[float, str]]:
    """Split a single LLM reply into 1–N "bubbles" with realistic per-bubble delays.

    Returns list of (delay_seconds_before_sending, body).
    """
    raw = [b.strip() for b in _SPLIT_RE.split(text) if b.strip()]
    if not raw:
        return []

    # Coalesce very short sentences with the next one so we don't end up with 6 1-word bubbles.
    merged: list[str] = []
    for piece in raw:
        if merged and (len(piece) < 18 or len(merged[-1]) < 18):
            merged[-1] = f"{merged[-1]} {piece}"
        else:
            merged.append(piece)

    # Cap at max_bubbles by gluing the tail back together.
    if len(merged) > max_bubbles:
        merged = merged[: max_bubbles - 1] + [" ".join(merged[max_bubbles - 1 :])]

    out: list[tuple[float, str]] = []
    for body in merged:
        # Rough typing speed: ~25 chars/sec, plus a "thinking" beat per bubble.
        delay = min(0.5 + len(body) / 25.0 + random.uniform(0.2, 0.9), 6.0)
        out.append((delay, body))
    return out
