from django.conf import settings
from django.db import models


class Tag(models.Model):
    CATEGORY_CHOICES = [
        ("mood", "Mood"),
        ("topic", "Topic"),
        ("spice", "Spice Level"),
        ("language", "Language"),
        ("region", "Region"),
        ("time", "Time of Day"),
        ("custom", "Custom"),
    ]

    slug = models.SlugField(max_length=48, unique=True)
    label = models.CharField(max_length=48)
    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES, default="topic")
    is_user_created = models.BooleanField(default=False)
    is_honeypot = models.BooleanField(default=False)  # surfaced in /api/tags; client filters out
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    usage_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["category", "usage_count"])]

    def __str__(self):
        return f"#{self.slug}"


class UserTag(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="user_tags")
    weight = models.FloatField(default=1.0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "tag")]
