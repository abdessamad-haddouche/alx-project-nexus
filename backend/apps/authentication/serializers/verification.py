"""
Verification serializers for Movie Nexus.
"""

from rest_framework import serializers

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from core.constants import VerificationType
from core.mixins.serializers import BaseAuthSerializerMixin

from ..models import VerificationToken

User = get_user_model()


class EmailVerificationSerializer(BaseAuthSerializerMixin, serializers.Serializer):
    """
    Essential email verification serializer.
    """

    token = serializers.CharField()

    def validate_token(self, value):
        """Validate verification token."""
        try:
            verification = VerificationToken.objects.get_valid_token(value)
            if verification.verification_type != VerificationType.REGISTRATION:
                raise serializers.ValidationError(_("Invalid token type"))
            return verification
        except Exception:
            raise serializers.ValidationError(_("Invalid or expired token"))

    def create(self, validated_data):
        """Verify user email."""
        verification_token = validated_data["token"]
        user = verification_token.user

        # Verify the token
        verification_token.verify()

        # Update user email verification status
        user.verify_email()

        return {"user": user}

    def to_representation(self, instance):
        """Return verification success response."""
        user = instance["user"]

        return {
            "message": _("Email verified successfully"),
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "is_email_verified": user.is_email_verified,
            },
        }


class ResendVerificationSerializer(BaseAuthSerializerMixin, serializers.Serializer):
    """
    Essential resend verification serializer.
    """

    email = serializers.EmailField()

    def validate_email(self, value):
        """Validate email exists and needs verification."""
        email = self.validate_email_format(value)

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                _("No account found with this email address.")
            )

        if user.is_email_verified:
            raise serializers.ValidationError(_("Email is already verified."))

        return user

    def create(self, validated_data):
        """Create new verification token and send email."""
        user = validated_data["email"]  # Actually the user from validation

        # Deactivate existing tokens
        VerificationToken.objects.filter(
            user=user,
            verification_type=VerificationType.REGISTRATION,
            is_active=True,
            is_used=False,
        ).update(is_active=False)

        # Create new verification token
        verification = VerificationToken.objects.create(
            user=user,
            email=user.email,
            verification_type=VerificationType.REGISTRATION,
        )

        # TODO: Send verification email with Celery
        # send_verification_email_task.delay(verification.id)

        return {"verification": verification, "user": user}

    def to_representation(self, instance):
        """Return resend verification response."""
        user = instance["user"]
        verification = instance["verification"]

        return {
            "message": _("Verification email sent successfully."),
            "email": user.email,
            "expires_at": verification.expires_at,
        }
