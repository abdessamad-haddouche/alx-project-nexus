"""
Authentication API endpoints.
Handles user registration, login, logout, password reset, OAuth, etc.
"""


from django.urls import path

# Import views from authentication app
from apps.authentication.views import (
    AdminCreateView,
    AdminListView,
    AdminPromoteView,
    AdminRevokeView,
    CurrentSessionView,
    EmailVerificationView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ResendEmailVerificationView,
    SessionTerminateView,
    SuperAdminCreateView,
    TokenBlacklistView,
    TokenInfoView,
    TokenRefreshView,
    TokenVerifyView,
    UserLoginView,
    UserLogoutView,
    UserProfileUpdateView,
    UserProfileView,
    UserRegistrationView,
    UserSessionListView,
)

app_name = "authentication"

urlpatterns = [
    # ================================================================
    # CORE AUTHENTICATION
    # ================================================================
    # User registration and login
    path("register/", UserRegistrationView.as_view(), name="register"),
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    # ================================================================
    # JWT TOKEN MANAGEMENT
    # ================================================================
    # Token operations
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token-verify"),
    path("token/blacklist/", TokenBlacklistView.as_view(), name="token-blacklist"),
    path("token/info/", TokenInfoView.as_view(), name="token-info"),
    # ================================================================
    # USER PROFILE MANAGEMENT
    # ================================================================
    # Profile operations
    path("profile/", UserProfileView.as_view(), name="profile"),
    path("profile/update/", UserProfileUpdateView.as_view(), name="profile-update"),
    # ================================================================
    # PASSWORD MANAGEMENT
    # ================================================================
    # Password operations
    path("password/change/", PasswordChangeView.as_view(), name="password-change"),
    path("password/reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path(
        "password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    # ================================================================
    # EMAIL VERIFICATION
    # ================================================================
    # Email verification
    path("verify-email/", EmailVerificationView.as_view(), name="verify-email"),
    path(
        "resend-verification/",
        ResendEmailVerificationView.as_view(),
        name="resend-verification",
    ),
    # ================================================================
    # SESSION MANAGEMENT
    # ================================================================
    # Session operations
    path("sessions/", UserSessionListView.as_view(), name="sessions"),
    path("sessions/current/", CurrentSessionView.as_view(), name="current-session"),
    path(
        "sessions/terminate/", SessionTerminateView.as_view(), name="session-terminate"
    ),
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
