"""
Essential token services for Movie Nexus.
"""


import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Dict, List

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.constants import VerificationType
from core.exceptions import TokenInvalidException, ValidationException

# Type hints only
if TYPE_CHECKING:
    from ..models import User, VerificationToken
else:
    # Runtime imports
    from django.contrib.auth import get_user_model

    from ..models import VerificationToken

    User = get_user_model()

logger = logging.getLogger(__name__)


logger = logging.getLogger(__name__)


class TokenService:
    """
    Essential token service for Movie Nexus.
    Handles email verification and password reset tokens.
    """

    @staticmethod
    @transaction.atomic
    def create_verification_token(
        user: "User",
        email: str = None,
        verification_type: str = VerificationType.REGISTRATION,
    ) -> "VerificationToken":
        """
        Create email verification token for user.

        Args:
            user: User instance
            email: Email address (defaults to user.email)
            verification_type: Type of verification token

        Returns:
            VerificationToken instance

        Raises:
            ValidationException: If token creation fails
        """
        try:
            if not email:
                email = user.email

            email = email.lower().strip()

            # Deactivate existing active tokens of same type
            VerificationToken.objects.filter(
                user=user,
                verification_type=verification_type,
                is_active=True,
                is_used=False,
            ).update(is_active=False)

            # Create new token
            token = VerificationToken.objects.create(
                user=user, email=email, verification_type=verification_type
            )

            logger.info(
                f"Verification token created: {user.email} - {verification_type}"
            )
            return token

        except Exception as e:
            logger.error(
                f"Failed to create verification token for {user.email}: {str(e)}"
            )
            raise ValidationException(_("Failed to create verification token"))

    @staticmethod
    def validate_verification_token(token_string: str) -> Dict:
        """
        Validate verification token and return details.

        Args:
            token_string: Token string to validate

        Returns:
            Dict containing token info and validation status

        Raises:
            TokenInvalidException: If token is invalid or expired
        """
        try:
            # Get token
            try:
                token = VerificationToken.objects.get(
                    token=token_string, is_active=True
                )
            except VerificationToken.DoesNotExist:
                raise TokenInvalidException(_("Invalid verification token"))

            # Check if token is valid
            if not token.is_valid:
                if token.is_expired:
                    raise TokenInvalidException(_("Verification token has expired"))
                elif token.is_used:
                    raise TokenInvalidException(
                        _("Verification token has already been used")
                    )
                else:
                    raise TokenInvalidException(_("Invalid verification token"))

            return {
                "token": token,
                "user": token.user,
                "email": token.email,
                "verification_type": token.verification_type,
                "expires_at": token.expires_at,
                "valid": True,
                "message": _("Token is valid"),
            }

        except TokenInvalidException:
            raise
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            raise TokenInvalidException(_("Token validation failed"))

    @staticmethod
    @transaction.atomic
    def create_password_reset_token(user: "User") -> "VerificationToken":
        """
        Create password reset token for user.

        Args:
            user: User instance

        Returns:
            VerificationToken instance for password reset

        Raises:
            ValidationException: If token creation fails
        """
        try:
            # Deactivate existing password reset tokens
            VerificationToken.objects.filter(
                user=user,
                verification_type=VerificationType.PASSWORD_RESET,
                is_active=True,
                is_used=False,
            ).update(is_active=False)

            # Create new reset token (shorter expiration for security)
            token = VerificationToken.objects.create(
                user=user,
                email=user.email,
                verification_type=VerificationType.PASSWORD_RESET,
                expires_at=timezone.now() + timedelta(hours=1),  # 1 hour expiration
            )

            logger.info(f"Password reset token created for: {user.email}")
            return token

        except Exception as e:
            logger.error(
                f"Failed to create password reset token for {user.email}: {str(e)}"
            )
            raise ValidationException(_("Failed to create password reset token"))

    @staticmethod
    def cleanup_expired_tokens() -> Dict:
        """
        Clean up expired and used verification tokens.

        Returns:
            Dict containing cleanup statistics
        """
        try:
            # Get expired tokens
            expired_tokens = VerificationToken.objects.filter(
                expires_at__lt=timezone.now(), is_active=True
            )

            # Get old used tokens (older than 7 days)
            old_used_tokens = VerificationToken.objects.filter(
                is_used=True, updated_at__lt=timezone.now() - timedelta(days=7)
            )

            # Count before deletion
            expired_count = expired_tokens.count()
            old_used_count = old_used_tokens.count()

            # Deactivate expired tokens (don't delete for audit trail)
            expired_tokens.update(is_active=False)

            # Delete old used tokens to save space
            old_used_tokens.delete()

            total_cleaned = expired_count + old_used_count

            logger.info(
                f"Token cleanup completed: {expired_count} expired, "
                f"{old_used_count} old used tokens"
            )

            return {
                "expired_deactivated": expired_count,
                "old_used_deleted": old_used_count,
                "total_cleaned": total_cleaned,
                "message": _("Token cleanup completed successfully"),
            }

        except Exception as e:
            logger.error(f"Token cleanup failed: {str(e)}")
            return {
                "expired_deactivated": 0,
                "old_used_deleted": 0,
                "total_cleaned": 0,
                "error": _("Token cleanup failed"),
            }

    # ================================================================
    # HELPER METHODS
    # ================================================================

    @staticmethod
    def get_user_active_tokens(
        user: "User", verification_type: str = None
    ) -> List["VerificationToken"]:
        """
        Get active verification tokens for user.

        Args:
            user: User instance
            verification_type: Filter by verification type (optional)

        Returns:
            List of active VerificationToken instances
        """
        try:
            queryset = VerificationToken.objects.filter(
                user=user, is_active=True, is_used=False
            )

            if verification_type:
                queryset = queryset.filter(verification_type=verification_type)

            return list(queryset.order_by("-created_at"))

        except Exception as e:
            logger.error(f"Failed to get active tokens for {user.email}: {str(e)}")
            return []

    @staticmethod
    def revoke_user_tokens(user: "User", verification_type: str = None) -> int:
        """
        Revoke (deactivate) all active tokens for user.

        Args:
            user: User instance
            verification_type: Revoke only specific type (optional)

        Returns:
            Number of tokens revoked
        """
        try:
            queryset = VerificationToken.objects.filter(
                user=user, is_active=True, is_used=False
            )

            if verification_type:
                queryset = queryset.filter(verification_type=verification_type)

            count = queryset.count()
            queryset.update(is_active=False)

            logger.info(f"Revoked {count} tokens for user: {user.email}")
            return count

        except Exception as e:
            logger.error(f"Failed to revoke tokens for {user.email}: {str(e)}")
            return 0

    @staticmethod
    def verify_and_use_token(token_string: str) -> Dict:
        """
        Verify token and mark it as used in one operation.

        Args:
            token_string: Token string to verify and use

        Returns:
            Dict containing verification result

        Raises:
            TokenInvalidException: If token is invalid
        """
        try:
            # Validate token first
            token_data = TokenService.validate_verification_token(token_string)
            token = token_data["token"]

            # Mark token as used
            token.verify()

            logger.info(
                f"Token verified and used: {token.user.email} - "
                f"{token.verification_type}"
            )

            return {
                "token": token,
                "user": token.user,
                "email": token.email,
                "verification_type": token.verification_type,
                "verified": True,
                "used": True,
                "message": _("Token verified and processed successfully"),
            }

        except TokenInvalidException:
            raise
        except Exception as e:
            logger.error(f"Token verification and usage failed: {str(e)}")
            raise TokenInvalidException(_("Failed to process verification token"))

    @staticmethod
    def get_token_statistics() -> Dict:
        """
        Get token usage statistics for monitoring.

        Returns:
            Dict containing token statistics
        """
        try:
            now = timezone.now()

            # Count by type and status
            stats = {
                "total_tokens": VerificationToken.objects.count(),
                "active_tokens": VerificationToken.objects.filter(
                    is_active=True, is_used=False
                ).count(),
                "used_tokens": VerificationToken.objects.filter(is_used=True).count(),
                "expired_tokens": VerificationToken.objects.filter(
                    expires_at__lt=now
                ).count(),
                "registration_tokens": VerificationToken.objects.filter(
                    verification_type=VerificationType.REGISTRATION
                ).count(),
                "password_reset_tokens": VerificationToken.objects.filter(
                    verification_type=VerificationType.PASSWORD_RESET
                ).count(),
            }

            return stats

        except Exception as e:
            logger.error(f"Failed to get token statistics: {str(e)}")
            return {}


# ================================================================
# CONVENIENCE FUNCTIONS
# ================================================================


def create_verification_token(
    user: "User",
    email: str = None,
    verification_type: str = VerificationType.REGISTRATION,
) -> "VerificationToken":
    """Convenience function for creating verification tokens."""
    return TokenService.create_verification_token(user, email, verification_type)


def validate_verification_token(token_string: str) -> Dict:
    """Convenience function for token validation."""
    return TokenService.validate_verification_token(token_string)


def create_password_reset_token(user: "User") -> "VerificationToken":
    """Convenience function for creating password reset tokens."""
    return TokenService.create_password_reset_token(user)


def cleanup_expired_tokens() -> Dict:
    """Convenience function for token cleanup."""
    return TokenService.cleanup_expired_tokens()
