import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Anonymous-handle account. `username` is also the user-visible handle."""

    handle = models.CharField(max_length=32, unique=True, db_index=True)
    email_hash = models.CharField(max_length=128, blank=True, db_index=True)
    oauth_provider = models.CharField(max_length=32, blank=True)
    age_confirmed = models.BooleanField(default=False)
    pronouns = models.CharField(max_length=32, blank=True)
    locale = models.CharField(max_length=16, default="en")

    trust_score = models.IntegerField(default=50)
    is_shadow_banned = models.BooleanField(default=False)
    is_operator = models.BooleanField(default=False)

    last_seen = models.DateTimeField(null=True, blank=True)
    onboarding_complete = models.BooleanField(default=False)

    def __str__(self):
        return self.handle or self.username


class MagicLinkToken(models.Model):
    """One-time email login token. Lives for 15 minutes."""

    email = models.EmailField(db_index=True)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def issue(cls, email: str) -> "MagicLinkToken":
        return cls.objects.create(email=email.lower().strip(), token=secrets.token_urlsafe(32))

    def is_valid(self) -> bool:
        if self.consumed_at is not None:
            return False
        return timezone.now() - self.created_at < timedelta(minutes=15)

    def consume(self):
        self.consumed_at = timezone.now()
        self.save(update_fields=["consumed_at"])
