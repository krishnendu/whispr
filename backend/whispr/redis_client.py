"""Lazy Redis client. Returns None if REDIS_URL is unset or unreachable.

Callers should treat Redis as optional infrastructure — Whispr falls back to
allow-by-default behavior when Redis is unavailable, so dev without an Upstash
instance keeps working.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

import redis
from django.conf import settings

log = logging.getLogger(__name__)

_client: Optional[redis.Redis] = None
_lock = threading.Lock()
_failed_once = False


def get_redis() -> Optional[redis.Redis]:
    global _client, _failed_once
    if _client is not None:
        return _client
    if _failed_once:
        return None
    with _lock:
        if _client is not None:
            return _client
        url = settings.REDIS_URL
        if not url:
            return None
        try:
            client = redis.Redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=False,
            )
            client.ping()
            _client = client
            return _client
        except Exception as exc:  # noqa: BLE001
            log.warning("Redis unavailable (%s) — rate limits will fail open", exc)
            _failed_once = True
            return None
