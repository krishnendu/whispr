from django.urls import path

from . import views

urlpatterns = [
    path("report", views.file_report),
    path("conversations/<int:convo_id>/block", views.block_in_conversation),
    path("admin/reports", views.admin_reports),
    path("admin/reports/<int:report_id>/dismiss", views.admin_dismiss_report),
    path("admin/reports/<int:report_id>/action", views.admin_action_report),
    path("admin/users", views.admin_users),
    path("admin/users/<int:user_id>/toggle-ban", views.admin_toggle_shadow_ban),
]
