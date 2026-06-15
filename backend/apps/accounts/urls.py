from django.urls import path

from . import views

urlpatterns = [
    path("auth/google/start", views.google_start),
    path("auth/google/callback", views.google_callback),
    path("auth/magic/send", views.magic_send),
    path("auth/magic/verify", views.magic_verify),
    path("me", views.me),
]
