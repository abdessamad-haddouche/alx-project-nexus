"""
Email verification models for secure email confirmation workflows.
"""

import secrets
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Import constants
from core.constants import VerificationType

# Import exceptions
from core.exceptions import TokenExpiredException, ValidationException

# Import mixins - using BaseModelMixin for complete functionality
from core.mixins import BaseModelMixin

# Import managers from this app
from ..managers import TokenVerificationManager

# Import User model
from .user import User


class VerificationToken(BaseModelMixin):
    """
    Multi-purpose verification tokens for secure user workflows.

    Handles verification tokens for:
        - User registration email verification
        - Email address change verification
        - Password reset verification
        - Account activation

    Uses:
    - BaseModelMixin: TimeStamped + Active + BaseManager functionality

    Manages verification tokens for user registration, email changes, and password
    resets with automatic expiration, security features, and usage tracking.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="email_verifications",
        verbose_name=_("user"),
        help_text=_("User associated with this verification."),
    )

    token = models.CharField(
        _("verification token"),
        max_length=255,
        unique=True,
        db_index=True,
        help_text=_("Unique verification token."),
    )

    email = models.EmailField(
        _("email address"),
        max_length=254,
        help_text=_("Email address being verified."),
    )

    verification_type = models.CharField(
        _("verification type"),
        max_length=20,
        choices=VerificationType.choices,
        default=VerificationType.REGISTRATION,
        db_index=True,
        help_text=_("Type of email verification."),
    )

    expires_at = models.DateTimeField(
        _("expires at"),
        db_index=True,
        help_text=_("Token expiration timestamp."),
    )

    verified_at = models.DateTimeField(
        _("verified at"),
        null=True,
        blank=True,
        help_text=_("When the verification was completed."),
    )

    attempts = models.PositiveIntegerField(
        _("verification attempts"),
        default=0,
        help_text=_("Number of verification attempts."),
    )

    max_attempts = models.PositiveIntegerField(
        _("maximum attempts"),
        default=3,
        help_text=_("Maximum allowed verification attempts."),
    )

    is_used = models.BooleanField(
        _("is used"),
        default=False,
        db_index=True,
        help_text=_("Whether the token has been used."),
    )

    ip_address = models.GenericIPAddressField(
        _("IP address"),
        null=True,
        blank=True,
        help_text=_("IP address when verification was requested."),
    )

    user_agent = models.TextField(
        _("user agent"),
        blank=True,
        help_text=_("User agent when verification was requested."),
    )

    # Custom manager
    objects = TokenVerificationManager()

    class Meta:
        verbose_name = _("Token Verification")
        verbose_name_plural = _("Token Verifications")
        db_table = "auth_email_verification"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["token"]),
            models.Index(fields=["email"]),
            models.Index(fields=["verification_type"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["is_used", "is_active"]),
            models.Index(fields=["verified_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "verification_type"],
                condition=models.Q(is_active=True, is_used=False),
                name="unique_active_verification_per_user_type",
            ),
        ]

    def __str__(self):
        """String representation of TokenVerification."""
        return f"Verification for {self.email} ({self.get_verification_type_display()})"

    def clean(self):
        """Custom validation for TokenVerification."""
        super().clean()

        # Normalize email
        if self.email:
            self.email = self.email.lower().strip()

        # Validate max attempts
        if self.max_attempts <= 0:
            raise ValidationException(
                detail=_("Maximum attempts must be greater than 0"),
                field_errors={"max_attempts": "Must be greater than 0"},
            )

        # Validate expiration date
        if self.expires_at and self.expires_at <= timezone.now():
            raise ValidationException(
                detail=_("Expiration date must be in the future"),
                field_errors={"expires_at": "Must be in the future"},
            )

    def save(self, *args, **kwargs):
        """Override save to ensure validation and token generation."""
        # Generate token if not provided
        if not self.token:
            self.token = self.generate_secure_token()

        # Set default expiration if not provided
        if not self.expires_at:
            self.expires_at = self.get_default_expiration()

        self.clean()
        super().save(*args, **kwargs)

    @classmethod
    def generate_secure_token(cls):
        """
        Generate a cryptographically secure token.

        Returns:
            str: Secure random token
        """
        return secrets.token_urlsafe(32)

    def get_default_expiration(self):
        """
        Get default expiration time based on verification type.

        Returns:
            datetime: Default expiration timestamp
        """
        from core.constants import (
            DEFAULT_VERIFICATION_EXPIRATION_HOURS,
            VERIFICATION_EXPIRATION_HOURS,
        )

        hours = VERIFICATION_EXPIRATION_HOURS.get(
            self.verification_type, DEFAULT_VERIFICATION_EXPIRATION_HOURS
        )
        return timezone.now() + timedelta(hours=hours)

    @property
    def is_expired(self):
        """
        Check if verification token is expired.

        Returns:
            bool: True if token is expired
        """
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        """
        Check if verification token is valid (not expired, not used, active).

        Returns:
            bool: True if token is valid
        """
        return (
            self.is_active
            and not self.is_used
            and not self.is_expired
            and self.attempts < self.max_attempts
        )

    @property
    def time_until_expiry(self):
        """
        Get time remaining until expiration.

        Returns:
            timedelta: Time remaining, or None if expired
        """
        if self.is_expired:
            return None
        return self.expires_at - timezone.now()

    @property
    def attempts_remaining(self):
        """
        Get number of attempts remaining.

        Returns:
            int: Number of attempts remaining
        """
        return max(0, self.max_attempts - self.attempts)

    def verify(self, user=None):
        """
        Mark verification as completed.

        Args:
            user: User performing the verification (optional)

        Raises:
            TokenExpiredException: If token is expired
            ValidationException: If token is invalid
        """
        if not self.is_valid:
            if self.is_expired:
                raise TokenExpiredException(
                    detail=_("Verification token has expired"),
                    extra_data={"token": self.token, "expired_at": self.expires_at},
                )
            elif self.is_used:
                raise ValidationException(
                    detail=_("Verification token has already been used"),
                    extra_data={"token": self.token, "used_at": self.verified_at},
                )
            elif self.attempts >= self.max_attempts:
                raise ValidationException(
                    detail=_("Maximum verification attempts exceeded"),
                    extra_data={"token": self.token, "attempts": self.attempts},
                )
            else:
                raise ValidationException(
                    detail=_("Verification token is invalid"),
                    extra_data={"token": self.token},
                )

        self.is_used = True
        self.verified_at = timezone.now()
        self.save(update_fields=["is_used", "verified_at", "updated_at"])

    def increment_attempts(self):
        """
        Increment verification attempts counter.

        Returns:
            int: Updated attempts count
        """
        self.attempts += 1
        self.save(update_fields=["attempts", "updated_at"])

        # Deactivate if max attempts reached
        if self.attempts >= self.max_attempts:
            self.deactivate()  # From ActiveMixin

        return self.attempts

    def invalidate(self, reason="manual"):
        """
        Invalidate the verification token.

        Args:
            reason: Reason for invalidation
        """
        self.is_used = True
        self.deactivate()  # From ActiveMixin
        self.save(update_fields=["is_used", "is_active", "updated_at"])

    @classmethod
    def cleanup_expired(cls):
        """
        Cleanup expired verification tokens.

        Returns:
            int: Number of tokens cleaned up
        """
        expired_tokens = cls.objects.filter(
            expires_at__lt=timezone.now(), is_active=True
        )
        count = expired_tokens.count()
        expired_tokens.update(is_active=False)
        return count
