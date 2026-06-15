from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Tag


def _serialize(tag: Tag) -> dict:
    return {
        "slug": tag.slug,
        "label": tag.label,
        "category": tag.category,
        "is_user_created": tag.is_user_created,
        "usage_count": tag.usage_count,
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def list_tags(request):
    query = (request.query_params.get("q") or "").strip().lower()
    qs = Tag.objects.all().order_by("category", "-usage_count", "slug")
    if query:
        qs = qs.filter(slug__icontains=query) | qs.filter(label__icontains=query)
    by_category: dict[str, list] = {}
    for tag in qs[:200]:
        by_category.setdefault(tag.category, []).append(_serialize(tag))
    return Response({"categories": by_category})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_tag(request):
    label = (request.data.get("label") or "").strip()
    if not label or len(label) > 32:
        return Response({"detail": "Label must be 1–32 characters."}, status=400)
    slug = slugify(label)[:48]
    if not slug:
        return Response({"detail": "Invalid label."}, status=400)
    tag, created = Tag.objects.get_or_create(
        slug=slug,
        defaults={"label": label, "category": "custom", "is_user_created": True, "created_by": request.user},
    )
    return Response(_serialize(tag), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
