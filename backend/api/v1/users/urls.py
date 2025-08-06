"""
User Management API endpoints.
Handles user profile management, account settings, and user data operations.
"""

from django.urls import path

from apps.users.views import PasswordChangeView, ProfileOnlyUpdateView, UserProfileView

app_name = "users"

urlpatterns = [
    # ================================================================
    # PROFILE MANAGEMENT
    # ================================================================
    # Main profile endpoint - GET/PUT/PATCH (user + profile data)
    path("profile/", UserProfileView.as_view(), name="profile"),
    # Profile-only endpoint - PUT/PATCH (profile fields only)
    path("profile/update/", ProfileOnlyUpdateView.as_view(), name="profile-update"),
    # ================================================================
    # ACCOUNT MANAGEMENT
    # ================================================================
    # Password change (authenticated users)
    path(
        "account/password/change/", PasswordChangeView.as_view(), name="password-change"
    ),
]
