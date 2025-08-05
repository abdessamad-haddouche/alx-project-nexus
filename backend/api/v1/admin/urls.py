"""
Admin management API endpoints.
"""


from django.urls import path

from apps.authentication.views import (
    AdminCreateView,
    AdminListView,
    AdminPromoteView,
    AdminRevokeView,
    SuperAdminCreateView,
)

app_name = "admin_management"

urlpatterns = [
    # ================================================================
    # ADMIN MANAGEMENT (SUPERUSER ONLY)
    # ================================================================
    path("admin/create/", AdminCreateView.as_view(), name="admin-create"),
    path("admin/promote/", AdminPromoteView.as_view(), name="admin-promote"),
    path("admin/revoke/<int:user_id>/", AdminRevokeView.as_view(), name="admin-revoke"),
    path("admin/list/", AdminListView.as_view(), name="admin-list"),
    path(
        "superadmin/create/", SuperAdminCreateView.as_view(), name="superadmin-create"
    ),
]
