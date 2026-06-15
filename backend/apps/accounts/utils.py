"""Helpers for handle generation, email hashing, token issuing."""

import hashlib
import secrets
from typing import Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

User = get_user_model()


ADJECTIVES = [
    "silent", "violet", "amber", "soft", "wild", "lone", "neon", "muted",
    "midnight", "drifting", "still", "wired", "quiet", "warm", "lucky",
]
NOUNS = [
    "fox", "moth", "comet", "river", "ember", "echo", "harbor", "lyric",
    "drift", "whisper", "pulse", "static", "marrow", "fable", "halo",
]


def random_handle() -> str:
    return f"{secrets.choice(ADJECTIVES)}-{secrets.choice(NOUNS)}-{secrets.randbelow(900) + 100}"


def unique_handle() -> str:
    for _ in range(8):
        h = random_handle()
        if not User.objects.filter(handle=h).exists():
            return h
    return f"{random_handle()}-{secrets.token_hex(2)}"


def email_hash(email: str) -> str:
    return hashlib.sha256(email.lower().strip().encode()).hexdigest()


def get_or_create_user_by_email(email: str, oauth_provider: str = "") -> Tuple[User, bool]:
    eh = email_hash(email)
    existing = User.objects.filter(email_hash=eh).first()
    if existing:
        return existing, False
    user = User.objects.create(
        username=unique_handle(),
        handle=unique_handle(),
        email=email,
        email_hash=eh,
        oauth_provider=oauth_provider,
    )
    return user, True


def issue_token(user: User) -> str:
    token, _ = Token.objects.get_or_create(user=user)
    return token.key
