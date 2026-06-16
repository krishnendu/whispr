from django.conf import settings
from django.db import models


class Persona(models.Model):
    SPICE_CHOICES = [("sfw", "SFW"), ("flirty", "Flirty"), ("spicy", "Spicy")]

    slug = models.SlugField(max_length=48, unique=True)
    name = models.CharField(max_length=48)
    avatar_url = models.URLField(blank=True)
    persona_card = models.JSONField(default=dict)         # name, age, vibe, interests, speech tics, few-shot
    system_prompt = models.TextField()                    # cached as a single block when calling Groq
    model_id = models.CharField(max_length=64, default="llama-3.3-70b-versatile")
    spice_level = models.CharField(max_length=16, choices=SPICE_CHOICES, default="sfw")
    allowed_tags = models.JSONField(default=list)         # list of tag slugs this persona can match
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class PersonaMemory(models.Model):
    """Source-of-truth memory for a (user, persona) pair. Redis caches this."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="persona_memories")
    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name="memories")
    facts = models.JSONField(default=dict)                # {"name": "alex", "likes": ["chess"], ...}
    rolling_summary = models.TextField(blank=True)        # condensed history beyond the live window
    last_window = models.JSONField(default=list)          # last ~20 messages as [{role, content}]
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "persona")]


class BotJob(models.Model):
    """Durable queue of pending bot-reply work.

    The in-process daemon thread tries to process the job immediately;
    a standalone worker (or the cron drain) picks up anything left
    pending past the staleness threshold.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("working", "Working"),
        ("done", "Done"),
        ("failed", "Failed"),
    ]

    conversation = models.ForeignKey(
        "chat.Conversation", on_delete=models.CASCADE, related_name="bot_jobs"
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "created_at"])]
