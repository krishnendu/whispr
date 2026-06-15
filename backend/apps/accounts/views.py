"""Auth + profile endpoints."""

import urllib.parse

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.tags.models import Tag, UserTag

from .models import MagicLinkToken
from .serializers import UpdateProfileSerializer, UserSerializer
from .utils import get_or_create_user_by_email, issue_token


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


# ---------- Google OAuth ----------

@api_view(["GET"])
@permission_classes([AllowAny])
def google_start(request):
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        return Response({"detail": "Google OAuth not configured."}, status=503)
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
    }
    return Response({"url": f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"})


@api_view(["POST"])
@permission_classes([AllowAny])
def google_callback(request):
    code = request.data.get("code")
    if not code:
        return Response({"detail": "Missing code."}, status=400)

    token_resp = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    if token_resp.status_code != 200:
        return Response({"detail": "Token exchange failed.", "google": token_resp.text}, status=400)

    access_token = token_resp.json().get("access_token")
    info_resp = requests.get(
        GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10
    )
    if info_resp.status_code != 200:
        return Response({"detail": "Userinfo failed."}, status=400)
    email = info_resp.json().get("email")
    if not email:
        return Response({"detail": "Google did not return an email."}, status=400)

    user, _ = get_or_create_user_by_email(email, oauth_provider="google")
    return Response({"token": issue_token(user), "user": UserSerializer(user).data})


# ---------- Magic link ----------

@api_view(["POST"])
@permission_classes([AllowAny])
def magic_send(request):
    email = (request.data.get("email") or "").strip().lower()
    if "@" not in email:
        return Response({"detail": "Valid email required."}, status=400)

    mlt = MagicLinkToken.issue(email)
    frontend_base = request.data.get("frontend_base") or "http://localhost:3000"
    link = f"{frontend_base.rstrip('/')}/auth/magic?token={mlt.token}"

    if settings.EMAIL_HOST_USER:
        send_mail(
            subject="Your Whispr sign-in link",
            message=f"Tap to sign in:\n\n{link}\n\nLink expires in 15 minutes. If you didn't ask for this, ignore.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        return Response({"sent": True})

    # Dev fallback — return the link so we can sign in without SMTP configured.
    return Response({"sent": True, "dev_link": link})


@api_view(["POST"])
@permission_classes([AllowAny])
def magic_verify(request):
    token = request.data.get("token")
    if not token:
        return Response({"detail": "Missing token."}, status=400)
    mlt = MagicLinkToken.objects.filter(token=token).first()
    if not mlt or not mlt.is_valid():
        return Response({"detail": "Invalid or expired token."}, status=400)

    with transaction.atomic():
        mlt.consume()
        user, _ = get_or_create_user_by_email(mlt.email, oauth_provider="magic")

    return Response({"token": issue_token(user), "user": UserSerializer(user).data})


# ---------- Profile ----------

@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user
    if request.method == "GET":
        return Response(UserSerializer(user).data)

    ser = UpdateProfileSerializer(user, data=request.data, partial=True)
    ser.is_valid(raise_exception=True)
    tag_slugs = ser.validated_data.pop("tag_slugs", None)

    with transaction.atomic():
        for field, val in ser.validated_data.items():
            setattr(user, field, val)
        # If they set a handle, mirror it into username too (the auth column)
        if "handle" in ser.validated_data:
            user.username = ser.validated_data["handle"]
        if tag_slugs is not None:
            _replace_tags(user, tag_slugs)
        # Mark onboarding complete once they've picked a handle + age + ≥3 tags
        if user.handle and user.age_confirmed and user.user_tags.count() >= 3:
            user.onboarding_complete = True
        user.save()

    return Response(UserSerializer(user).data)


def _replace_tags(user, slugs):
    slugs = list({s.strip().lower() for s in slugs if s and s.strip()})[:8]
    tags = list(Tag.objects.filter(slug__in=slugs))
    user.user_tags.all().delete()
    UserTag.objects.bulk_create([UserTag(user=user, tag=t) for t in tags])
    Tag.objects.filter(slug__in=[t.slug for t in tags]).update(usage_count=models.F("usage_count") + 1)


# avoid circular import-time pull
from django.db import models  # noqa: E402
