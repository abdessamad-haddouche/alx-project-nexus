"""
Core serializer mixins for consistent functionality across all apps.
"""

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _


class TimestampMixin(serializers.Serializer):
    """Simple timestamp fields for models with TimeStampedMixin."""

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class UserContextMixin:
    """Get current user from request context."""

    @property
    def current_user(self):
        """Get current user from request context."""
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            return request.user
        return None


class PasswordValidationMixin:
    """Essential password validation."""

    def validate_password_strength(self, password, user=None):
        """Validate password using Django's validators."""
        from django.contrib.auth.password_validation import validate_password

        try:
            validate_password(password, user)
        except Exception as e:
            raise ValidationError(str(e))
        return password

    def validate_password_confirmation(self, attrs):
        """Validate password and password confirmation match."""
        password = attrs.get("password")
        password_confirm = attrs.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            raise ValidationError(
                {"password_confirm": _("Password confirmation does not match.")}
            )

        # Remove password_confirm from validated data
        attrs.pop("password_confirm", None)
        return attrs


class LoginValidationMixin:
    """Essential login validation."""

    def validate_credentials(self, email, password):
        """Validate user credentials and return authenticated user."""
        email = email.lower().strip()
        user = authenticate(email=email, password=password)

        if not user:
            raise ValidationError(_("Invalid email or password"))

        if not user.is_active:
            raise ValidationError(_("Account is deactivated"))

        return user


class EmailValidationMixin:
    """Essential email validation."""

    def validate_email_format(self, email):
        """Basic email validation."""
        if not email:
            raise ValidationError(_("Email is required"))
        return email.lower().strip()


# ================================================================
# COMPOSITE MIXIN
# ================================================================


class BaseAuthSerializerMixin(
    TimestampMixin,
    UserContextMixin,
    PasswordValidationMixin,
    LoginValidationMixin,
    EmailValidationMixin,
):
    """
    Essential authentication serializer mixin.
    Use this for all auth serializers - contains everything you need.
    """

    def validate(self, attrs):
        """Main validation - can be extended by child serializers."""
        return super().validate(attrs) if hasattr(super(), "validate") else attrs
