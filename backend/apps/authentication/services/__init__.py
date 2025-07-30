"""
Authentication Services Base Module
"""

# Authentication Service
from .auth_service import (
    AuthenticationService,
    authenticate_user,
    generate_tokens,
    logout_user,
    refresh_token,
)

# Email Service
from .email_service import EmailService

# OAuth Service
from .oauth_service import (
    OAuthService,
    google_oauth_login,
    link_social_account,
    validate_oauth_token,
)

# Session Service
from .session_service import (
    SessionService,
    create_user_session,
    get_active_sessions,
    terminate_all_sessions,
    terminate_user_session,
)

# Token Service
from .token_service import (
    TokenService,
    cleanup_expired_tokens,
    create_password_reset_token,
    create_verification_token,
    validate_verification_token,
)

# User Management Service
from .user_service import (
    UserService,
    change_user_password,
    create_user_account,
    update_user_profile,
    verify_user_email,
)

__all__ = [
    # Email Service
    "EmailService",
    # Authentication Services
    "AuthenticationService",
    "UserService",
    "OAuthService",
    "TokenService",
    "SessionService",
    # User Management Services
    "authenticate_user",
    "generate_tokens",
    "refresh_token",
    "logout_user",
    "create_user_account",
    "verify_user_email",
    "update_user_profile",
    "change_user_password",
    "google_oauth_login",
    "link_social_account",
    "validate_oauth_token",
    "create_verification_token",
    "validate_verification_token",
    "create_password_reset_token",
    "cleanup_expired_tokens",
    "create_user_session",
    "terminate_user_session",
    "terminate_all_sessions",
    "get_active_sessions",
]


from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


# ================================================================
# SERVICE RESULT CLASS
# ================================================================


class ServiceResult:
    """
    Standard service result for consistent return values.
    Demonstrates professional API design patterns.
    """

    def __init__(self, success: bool = True, data: Any = None, message: str = ""):
        self.success = success
        self.data = data
        self.message = message
        self.timestamp = timezone.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def success(cls, data: Any = None, message: str = "Operation successful"):
        """Create successful result."""
        return cls(success=True, data=data, message=message)

    @classmethod
    def error(cls, message: str = "Operation failed", data: Any = None):
        """Create error result."""
        return cls(success=False, data=data, message=message)
