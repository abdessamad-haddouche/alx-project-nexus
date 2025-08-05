"""
Authentication Views Module
Exports all authentication views for easy importing.
"""

from .admin_views import (
    AdminCreateView,
    AdminListView,
    AdminPromoteView,
    AdminRevokeView,
    SuperAdminCreateView,
)

# Core Authentication Views
from .auth_views import UserLoginView, UserLogoutView, UserRegistrationView

# Session Management Views
from .session_views import CurrentSessionView, SessionTerminateView, UserSessionListView

# JWT Token Management Views
from .token_views import TokenRefreshView, TokenVerifyView

# User Management Views
from .user_views import PasswordChangeView, UserProfileUpdateView, UserProfileView

# Email Verification & Password Reset Views
from .verification_views import (
    EmailVerificationView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ResendEmailVerificationView,
)

# Export all views for easy importing
__all__ = [
    # Core Authentication
    "UserRegistrationView",
    "UserLoginView",
    "UserLogoutView",
    "TokenRefreshView",
    "TokenVerifyView",
    # User Management
    "UserProfileView",
    "UserProfileUpdateView",
    "PasswordChangeView",
    "UserAccountDeleteView",
    "UserPreferencesView",
    # Email Verification & Password Reset
    "EmailVerificationView",
    "ResendEmailVerificationView",
    "PasswordResetRequestView",
    "PasswordResetConfirmView",
    "EmailChangeRequestView",
    "EmailChangeConfirmView",
    "VerificationStatusView",
    # Session Management
    "UserSessionListView",
    "SessionTerminateView",
    "CurrentSessionView",
    "SessionActivityView",
    "SessionSecurityView",
    "SessionStatsView",
    "BulkSessionActionView",
    # JWT Token Management
    "JWTTokenRefreshView",
    "JWTTokenVerifyView",
    "TokenBlacklistView",
    "TokenInfoView",
    "TokenRevokeAllView",
    "TokenStatsView",
    "AdminCreateView",
    "AdminPromoteView",
    "AdminRevokeView",
    "AdminListView",
    "SuperAdminCreateView",
]
