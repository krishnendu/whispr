from django.urls import path

from . import views

urlpatterns = [
    path("conversations/<int:convo_id>", views.get_conversation),
    path("conversations/<int:convo_id>/poll", views.poll_conversation),
    path("conversations/<int:convo_id>/stream", views.stream_conversation),
    path("conversations/<int:convo_id>/messages", views.post_message),
    path("conversations/<int:convo_id>/end", views.end_conversation),
]
