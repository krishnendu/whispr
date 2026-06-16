from django.conf import settings
from django.db import models


class Conversation(models.Model):
    KIND_CHOICES = [("human", "Human ↔ Human"), ("bot", "Human ↔ Bot")]

    kind = models.CharField(max_length=8, choices=KIND_CHOICES)
    participant_a = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="convos_as_a"
    )
    participant_b = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="convos_as_b"
    )
    persona = models.ForeignKey(
        "bots.Persona", on_delete=models.SET_NULL, null=True, blank=True, related_name="conversations"
    )

    started_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    summary_text = models.TextField(blank=True, default="")

    is_vaulted_by_a = models.BooleanField(default=False)
    is_vaulted_by_b = models.BooleanField(default=False)

    # Ephemeral "is typing" hints. The SSE stream reveals one to the other side.
    typing_a_until = models.DateTimeField(null=True, blank=True)
    typing_other_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["kind", "last_activity_at"]),
            models.Index(fields=["participant_a", "last_activity_at"]),
        ]

    def __str__(self):
        return f"Conv#{self.pk} ({self.kind})"


class Message(models.Model):
    """Rotating store. App-level prune keeps last N per conversation in PG; Redis holds the hot buffer."""

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="messages"
    )
    # null sender + bot-kind conversation = persona message
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    mod_flags = models.JSONField(default=dict)        # {"toxicity": 0.1, "blocked": false, ...}
    is_redacted = models.BooleanField(default=False)
    # Behavioral signals from the client. Data-only for now; nothing enforces.
    # Shape: {"typing_ms": int, "paste_count": int, "length": int}
    behavior_signals = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["conversation", "sent_at"])]
