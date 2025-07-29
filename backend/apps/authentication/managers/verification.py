"""
Custom managers for TokenVerification model.
"""

from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.constants import VerificationType
from core.exceptions import (
    TokenExpiredException,
    UserNotFoundException,
    ValidationException,
)


class TokenVerificationManager(models.Manager):
    """
    Custom manager for TokenVerification with verification-specific queries and
    optimizations.
    """

    def get_queryset(self):
        """Optimize default queryset with select_related for user data."""
        return super().get_queryset().select_related("user").filter(is_active=True)

    def all_with_inactive(self):
        """Get all token verifications including inactive ones."""
        return super().get_queryset().select_related("user")

    def get_by_token(self, token):
        """
        Get verification by token with proper exception handling.

        Args:
            token: Verification token string

        Returns:
            TokenVerification instance

        Raises:
            UserNotFoundException: If verification not found
        """
        try:
            return self.get(token=token)
        except self.model.DoesNotExist:
            raise UserNotFoundException(
                detail=_("Verification token not found"),
                extra_data={"token": token},
            )

    def get_valid_token(self, token):
        """
        Get valid (non-expired, unused) verification by token.

        Args:
            token: Verification token string

        Returns:
            TokenVerification instance

        Raises:
            UserNotFoundException: If verification not found
            TokenExpiredException: If token is expired or invalid
        """
        verification = self.get_by_token(token)

        if not verification.is_valid:
            if verification.is_expired:
                raise TokenExpiredException(
                    detail=_("Verification token has expired"),
                    extra_data={"token": token, "expired_at": verification.expires_at},
                )
            elif verification.is_used:
                raise ValidationException(
                    detail=_("Verification token has already been used"),
                    extra_data={"token": token, "used_at": verification.verified_at},
                )
            else:
                raise ValidationException(
                    detail=_("Verification token is invalid"),
                    extra_data={"token": token},
                )

        return verification

    def active_for_user(self, user):
        """
        Get all active verifications for a specific user.

        Args:
            user: User instance

        Returns:
            QuerySet of active TokenVerification instances
        """
        return self.filter(user=user)

    def by_verification_type(self, verification_type):
        """
        Get verifications by type.

        Args:
            verification_type: VerificationType enum value

        Returns:
            QuerySet of TokenVerification instances
        """
        return self.filter(verification_type=verification_type)

    def registration_verifications(self):
        """Get all registration verifications."""
        return self.by_verification_type(VerificationType.REGISTRATION)

    def email_change_verifications(self):
        """Get all email change verifications."""
        return self.by_verification_type(VerificationType.EMAIL_CHANGE)

    def password_reset_verifications(self):
        """Get all password reset verifications."""
        return self.by_verification_type(VerificationType.PASSWORD_RESET)

    def valid_tokens(self):
        """
        Get all valid (non-expired, unused, active) verifications.

        Returns:
            QuerySet of valid TokenVerification instances
        """
        now = timezone.now()
        return self.filter(
            is_used=False, expires_at__gt=now, attempts__lt=models.F("max_attempts")
        )

    def expired_tokens(self):
        """
        Get all expired verifications.

        Returns:
            QuerySet of expired TokenVerification instances
        """
        now = timezone.now()
        return self.filter(expires_at__lte=now)

    def used_tokens(self):
        """
        Get all used verifications.

        Returns:
            QuerySet of used TokenVerification instances
        """
        return self.filter(is_used=True)

    def pending_for_user(self, user, verification_type=None):
        """
        Get pending verifications for a user.

        Args:
            user: User instance
            verification_type: Optional verification type filter

        Returns:
            QuerySet of pending TokenVerification instances
        """
        queryset = self.filter(user=user, is_used=False, expires_at__gt=timezone.now())

        if verification_type:
            queryset = queryset.filter(verification_type=verification_type)

        return queryset

    def create_verification(self, user, email, verification_type, **extra_fields):
        """
        Create a new email verification for a user.

        Args:
            user: User instance
            email: Email address to verify
            verification_type: Type of verification
            **extra_fields: Additional fields

        Returns:
            TokenVerification instance
        """
        # Deactivate any existing pending verifications of the same type
        self.pending_for_user(user, verification_type).update(is_active=False)

        verification = self.create(
            user=user,
            email=email.lower().strip(),
            verification_type=verification_type,
            **extra_fields,
        )

        return verification

    def create_registration_verification(self, user, email=None, **extra_fields):
        """
        Create registration verification for a user.

        Args:
            user: User instance
            email: Email to verify (defaults to user.email)
            **extra_fields: Additional fields

        Returns:
            TokenVerification instance
        """
        if not email:
            email = user.email

        return self.create_verification(
            user=user,
            email=email,
            verification_type=VerificationType.REGISTRATION,
            **extra_fields,
        )

    def create_email_change_verification(self, user, new_email, **extra_fields):
        """
        Create email change verification for a user.

        Args:
            user: User instance
            new_email: New email address to verify
            **extra_fields: Additional fields

        Returns:
            TokenVerification instance
        """
        return self.create_verification(
            user=user,
            email=new_email,
            verification_type=VerificationType.EMAIL_CHANGE,
            **extra_fields,
        )

    def create_password_reset_verification(self, user, email=None, **extra_fields):
        """
        Create password reset verification for a user.

        Args:
            user: User instance
            email: Email to send reset to (defaults to user.email)
            **extra_fields: Additional fields

        Returns:
            TokenVerification instance
        """
        if not email:
            email = user.email

        return self.create_verification(
            user=user,
            email=email,
            verification_type=VerificationType.PASSWORD_RESET,
            **extra_fields,
        )

    def verify_token(self, token):
        """
        Verify a token and mark it as used.

        Args:
            token: Verification token string

        Returns:
            TokenVerification instance

        Raises:
            Various exceptions for invalid tokens
        """
        verification = self.get_valid_token(token)
        verification.verify()
        return verification

    def cleanup_expired(self, days_old=30):
        """
        Clean up old expired verifications.

        Args:
            days_old: Remove verifications expired longer than this many days

        Returns:
            int: Number of verifications cleaned up
        """
        cutoff_date = timezone.now() - timedelta(days=days_old)
        expired_verifications = self.all_with_inactive().filter(
            expires_at__lt=cutoff_date
        )
        count = expired_verifications.count()
        expired_verifications.delete()
        return count

    def cleanup_old_used(self, days_old=7):
        """
        Clean up old used verifications.

        Args:
            days_old: Remove used verifications older than this many days

        Returns:
            int: Number of verifications cleaned up
        """
        cutoff_date = timezone.now() - timedelta(days=days_old)
        old_used = self.all_with_inactive().filter(
            is_used=True, verified_at__lt=cutoff_date
        )
        count = old_used.count()
        old_used.delete()
        return count
