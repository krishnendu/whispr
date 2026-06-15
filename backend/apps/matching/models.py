from django.conf import settings
from django.db import models


class MatchQueueEntry(models.Model):
    """A user waiting to be paired. One row per active wait — `unique` on user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="match_wait"
    )
    tag_slugs = models.JSONField(default=list)
    joined_at = models.DateTimeField(auto_now_add=True)

    # Set once a match is found; the polling client reads this to redirect into the chat.
    matched_conversation = models.ForeignKey(
        "chat.Conversation", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        indexes = [models.Index(fields=["joined_at"])]
