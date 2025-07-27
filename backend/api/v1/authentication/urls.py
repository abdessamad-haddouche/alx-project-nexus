"""
Authentication API endpoints.
Handles user registration, login, logout, password reset, OAuth, etc.
"""
from django.urls import path

from . import views

app_name = "authentication"

urlpatterns = [
    # ================================================================
    # Core Authentication
    # ================================================================
    # User registration and login
    path("register/", views.UserRegistrationView.as_view(), name="register"),
    path("login/", views.UserLoginView.as_view(), name="login"),
    path("logout/", views.UserLogoutView.as_view(), name="logout"),
    # JWT Token management
    path("token/refresh/", views.TokenRefreshView.as_view(), name="token-refresh"),
    path("token/verify/", views.TokenVerifyView.as_view(), name="token-verify"),
    # Password management
    path("password/reset/", views.PasswordResetView.as_view(), name="password-reset"),
    path(
        "password/reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path(
        "password/change/", views.PasswordChangeView.as_view(), name="password-change"
    ),
    # ================================================================
    # OAuth & Social Authentication
    # ================================================================
    # OAuth initiation
    path("google/", views.GoogleOAuthView.as_view(), name="google-oauth"),
    path("facebook/", views.FacebookOAuthView.as_view(), name="facebook-oauth"),
    # OAuth callbacks
    path(
        "google/callback/", views.GoogleCallbackView.as_view(), name="google-callback"
    ),
    path(
        "facebook/callback/",
        views.FacebookCallbackView.as_view(),
        name="facebook-callback",
    ),
    # ================================================================
    # 6.1.3 Email Verification & Password Recovery
    # ================================================================
    # Email verification (token in URL as per FRD)
    path(
        "verify-email/<str:token>/",
        views.EmailVerificationView.as_view(),
        name="email-verify",
    ),
    path(
        "resend-verification/",
        views.ResendEmailVerificationView.as_view(),
        name="email-resend",
    ),
]
