"""Standalone bot-reply worker. Runs forever, drains BotJobs.

Deploy this on Fly.io / Railway / a tiny VM if you need guaranteed bot reply
delivery — the in-process thread on the Django side is best-effort, and on
Vercel serverless threads can be killed when the function instance recycles.

Usage:
    DATABASE_URL=postgres://... GROQ_API_KEY=... \\
        python worker/run.py

The worker shares Django's settings and ORM, so it needs the same env vars
the backend does.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "whispr.settings")

import django  # noqa: E402

django.setup()

from apps.bots.runner import drain_orphans  # noqa: E402
from django.db import close_old_connections  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("whispr.worker")


POLL_INTERVAL_S = 2
STALE_AFTER_S = 5  # be aggressive — the worker is the primary path in prod


def main() -> int:
    log.info("whispr worker starting (poll=%ss, stale=%ss)", POLL_INTERVAL_S, STALE_AFTER_S)
    while True:
        try:
            result = drain_orphans(max_jobs=10, stale_after_s=STALE_AFTER_S)
            if result["done"]:
                log.info("drained: %s", result)
        except Exception:
            log.exception("drain loop crashed")
        finally:
            close_old_connections()
        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    sys.exit(main())
