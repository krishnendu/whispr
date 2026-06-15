from django.urls import path

from . import views

urlpatterns = [
    path("match/start", views.match_start),
    path("match/status", views.match_status),
    path("match/cancel", views.match_cancel),
]
