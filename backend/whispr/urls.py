from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"ok": True, "service": "whispr-api"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", health),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.tags.urls")),
    path("api/", include("apps.chat.urls")),
    path("api/", include("apps.matching.urls")),
    path("api/", include("apps.bots.urls")),
    path("api/", include("apps.moderation.urls")),
]
