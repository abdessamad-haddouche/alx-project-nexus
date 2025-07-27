"""
Authentication API endpoints.
Handles user registration, login, logout, password reset, etc.
"""
from django.urls import path

from . import views

app_name = "authentication"

urlpatterns = [
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
    # Email verification
    path("email/verify/", views.EmailVerificationView.as_view(), name="email-verify"),
    path(
        "email/resend/",
        views.ResendEmailVerificationView.as_view(),
        name="email-resend",
    ),
]
