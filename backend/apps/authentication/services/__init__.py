"""
Authentication Services Base Module
"""

from .admin_service import (
    AdminService,
    create_admin_user,
    create_superadmin_user,
    promote_user_to_admin,
    revoke_admin_privileges,
)

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

# Token Service
from .token_service import (
    TokenService,
    cleanup_expired_tokens,
    create_password_reset_token,
    create_verification_token,
    validate_verification_token,
)

__all__ = [
    # Email Service
    "EmailService",
    # Authentication Services
    "AuthenticationService",
    "OAuthService",
    "TokenService",
    # Admin Services
    "AdminService",
    # User Management Services
    "authenticate_user",
    "generate_tokens",
    "refresh_token",
    "logout_user",
    "google_oauth_login",
    "link_social_account",
    "validate_oauth_token",
    "create_verification_token",
    "validate_verification_token",
    "create_password_reset_token",
    "cleanup_expired_tokens",
    "create_admin_user",
    "create_superadmin_user",
    "promote_user_to_admin",
    "revoke_admin_privileges",
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
