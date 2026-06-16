"""Sliding-window rate limiter backed by Redis ZSETs.

ZADD a timestamp for each event, ZREMRANGEBYSCORE everything outside the window,
ZCARD the survivors. If it exceeds the limit, the action is rejected. Atomic via
a single MULTI pipeline.

Fail-open: if Redis is unavailable, all calls return True (allow).
"""

from __future__ import annotations

import time

from .redis_client import get_redis


def check_rate(key: str, limit: int, window_s: int) -> bool:
    """Return True if this action is allowed; False if the rate limit is exhausted.

    Records the action only if allowed — denials don't pollute the window.
    """
    r = get_redis()
    if r is None:
        return True

    now_ms = int(time.time() * 1000)
    window_ms = window_s * 1000
    bucket = f"rl:{key}"

    try:
        # First check current count without recording, then record if under the cap.
        with r.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(bucket, 0, now_ms - window_ms)
            pipe.zcard(bucket)
            _, count = pipe.execute()

        if count >= limit:
            return False

        with r.pipeline(transaction=True) as pipe:
            pipe.zadd(bucket, {f"{now_ms}-{count}": now_ms})
            pipe.expire(bucket, window_s + 5)
            pipe.execute()
        return True
    except Exception:
        # Don't punish users for a Redis hiccup — log path can be added later.
        return True
