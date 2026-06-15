from django.urls import path

from . import views

urlpatterns = [
    path("tags", views.list_tags),
    path("tags/create", views.create_tag),
]
