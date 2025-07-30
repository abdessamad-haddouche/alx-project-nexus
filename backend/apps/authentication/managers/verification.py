"""
Custom managers for TokenVerification model.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.constants import VerificationType


class TokenVerificationManager(models.Manager):
    """
    Custom manager for TokenVerification.
    """

    def get_queryset(self):
        """Optimize default queryset with select_related for user data."""
        return super().get_queryset().select_related("user").filter(is_active=True)

    def get_by_token(self, token):
        """Get verification by token."""
        return self.get(token=token)

    def get_valid_token(self, token):
        """Get valid (non-expired, unused) verification by token."""
        verification = self.get_by_token(token)
        if not verification.is_valid:
            raise ValueError(_("Invalid or expired token"))
        return verification

    def active_for_user(self, user):
        """Get all active verifications for a specific user."""
        return self.filter(user=user)

    def by_verification_type(self, verification_type):
        """Get verifications by type."""
        return self.filter(verification_type=verification_type)

    def create_verification(self, user, email, verification_type, **extra_fields):
        """Create a new email verification for a user."""
        # Deactivate any existing pending verifications of the same type
        self.filter(
            user=user,
            verification_type=verification_type,
            is_used=False,
            is_active=True,
        ).update(is_active=False)

        verification = self.create(
            user=user,
            email=email.lower().strip(),
            verification_type=verification_type,
            **extra_fields,
        )

        return verification

    def create_registration_verification(self, user, email=None, **extra_fields):
        """Create registration verification for a user."""
        if not email:
            email = user.email

        return self.create_verification(
            user=user,
            email=email,
            verification_type=VerificationType.REGISTRATION,
            **extra_fields,
        )

    def verify_token(self, token):
        """Verify a token and mark it as used."""
        verification = self.get_valid_token(token)
        verification.verify()
        return verification
