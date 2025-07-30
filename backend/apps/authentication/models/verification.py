"""
Email verification models for secure email confirmation workflows.
"""

import secrets
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.constants import VerificationType
from core.mixins import BaseModelMixin

from ..managers import TokenVerificationManager
from .user import User


class VerificationToken(BaseModelMixin):
    """
    Verification tokens for user email verification workflows.
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

    is_used = models.BooleanField(
        _("is used"),
        default=False,
        db_index=True,
        help_text=_("Whether the token has been used."),
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
        ]

    def __str__(self):
        """String representation of TokenVerification."""
        return f"Verification for {self.email} ({self.get_verification_type_display()})"

    def save(self, *args, **kwargs):
        """Override save to ensure token generation and expiration."""
        # Generate token if not provided
        if not self.token:
            self.token = self.generate_secure_token()

        # Set default expiration if not provided
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)  # 24 hour expiration

        super().save(*args, **kwargs)

    @classmethod
    def generate_secure_token(cls):
        """Generate a cryptographically secure token."""
        return secrets.token_urlsafe(32)

    @property
    def is_expired(self):
        """Check if verification token is expired."""
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        """Check if verification token is valid (not expired, not used, active)."""
        return self.is_active and not self.is_used and not self.is_expired

    def verify(self):
        """Mark verification as completed."""
        self.is_used = True
        self.save(update_fields=["is_used", "updated_at"])
