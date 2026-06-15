"""Vercel @vercel/python entrypoint — exposes the Django WSGI app."""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "whispr.settings")

from whispr.wsgi import application as app  # noqa: E402  (Vercel looks for `app`)
