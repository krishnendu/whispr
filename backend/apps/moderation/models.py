from django.conf import settings
from django.db import models


class Report(models.Model):
    REASON_CHOICES = [
        ("spam", "Spam"),
        ("harassment", "Harassment"),
        ("nsfw", "NSFW outside spice"),
        ("minor", "Suspected minor"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [("open", "Open"), ("dismissed", "Dismissed"), ("actioned", "Actioned")]

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="reports_filed")
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports_against")
    conversation = models.ForeignKey("chat.Conversation", on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.CharField(max_length=16, choices=REASON_CHOICES)
    note = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)


class Ban(models.Model):
    KIND_CHOICES = [("shadow", "Shadow"), ("full", "Full")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bans")
    kind = models.CharField(max_length=8, choices=KIND_CHOICES)
    reason = models.TextField()
    issued_at = models.DateTimeField(auto_now_add=True)
    lifted_at = models.DateTimeField(null=True, blank=True)


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="audit_actions")
    action = models.CharField(max_length=64)
    target_type = models.CharField(max_length=32, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["action", "created_at"])]
