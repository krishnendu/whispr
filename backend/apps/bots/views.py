from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.chat.models import Conversation

from .models import Persona


def _serialize(p: Persona) -> dict:
    return {
        "slug": p.slug,
        "name": p.name,
        "avatar_url": p.avatar_url,
        "persona_card": p.persona_card,
        "spice_level": p.spice_level,
        "allowed_tags": p.allowed_tags,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_personas(request):
    qs = Persona.objects.filter(is_active=True).order_by("name")
    return Response({"personas": [_serialize(p) for p in qs]})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_persona_chat(request, slug: str):
    persona = get_object_or_404(Persona, slug=slug, is_active=True)
    if persona.spice_level != "sfw" and not request.user.age_confirmed:
        return Response({"detail": "This persona requires age confirmation."}, status=403)

    # Resume an active conversation if one exists; otherwise create.
    convo = (
        Conversation.objects.filter(
            kind="bot",
            participant_a=request.user,
            persona=persona,
            ended_at__isnull=True,
        )
        .order_by("-last_activity_at")
        .first()
    )
    if convo is None:
        convo = Conversation.objects.create(
            kind="bot",
            participant_a=request.user,
            persona=persona,
        )
    return Response({"conversation_id": convo.pk, "persona": _serialize(persona)})
