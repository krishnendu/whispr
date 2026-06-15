from django.urls import path

from . import views

urlpatterns = [
    path("personas", views.list_personas),
    path("personas/<slug:slug>/start", views.start_persona_chat),
]
