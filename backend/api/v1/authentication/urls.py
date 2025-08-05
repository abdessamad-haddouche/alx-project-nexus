"""
Authentication API endpoints.
Handles user registration, login, logout, password reset, OAuth, etc.
"""


from django.urls import path

from apps.authentication.views import (
    EmailVerificationView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ResendEmailVerificationView,
    TokenRefreshView,
    TokenVerifyView,
    UserLoginView,
    UserLogoutView,
    UserProfileUpdateView,
    UserProfileView,
    UserRegistrationView,
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
]
