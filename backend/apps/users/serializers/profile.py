"""
User's Profile serializers.
"""

from rest_framework import serializers

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core.constants import Language, PrivacyLevel, ThemePreference, Timezone
from core.mixins.serializers import BaseAuthSerializerMixin

from ..models import Profile

User = get_user_model()


class UserProfileSerializer(BaseAuthSerializerMixin, serializers.ModelSerializer):
    """
    User profile serializer.
    """

    # User info (read-only)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = Profile
        fields = [
            "id",
            "user",
            "user_email",
            "user_full_name",
            "bio",
            "location",
            "timezone",
            "preferred_language",
            "privacy_level",
            "notification_preferences",
            "theme_preference",
            "is_active",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "user": {"read_only": True},
        }

    def validate_bio(self, value):
        """Basic bio validation."""
        if value and len(value.strip()) < 10:
            raise serializers.ValidationError(
                _("Biography must be at least 10 characters long.")
            )
        return value


class UserProfileUpdateSerializer(BaseAuthSerializerMixin, serializers.Serializer):
    """
    Combined user and profile update serializer.
    Handles both user fields and profile fields in one request.
    """

    # User fields (optional)
    first_name = serializers.CharField(
        max_length=50, required=False, help_text="User's first name"
    )
    last_name = serializers.CharField(
        max_length=50, required=False, help_text="User's last name"
    )
    phone_number = serializers.CharField(
        max_length=15,
        required=False,
        allow_blank=True,
        help_text="Phone number in international format",
    )
    avatar = serializers.URLField(
        required=False, allow_blank=True, help_text="Profile picture URL"
    )

    # Profile fields (optional)
    bio = serializers.CharField(
        max_length=1000, required=False, allow_blank=True, help_text="User biography"
    )
    location = serializers.CharField(
        max_length=100, required=False, allow_blank=True, help_text="User location"
    )
    timezone = serializers.ChoiceField(
        choices=Timezone.choices, required=False, help_text="User timezone"
    )
    preferred_language = serializers.ChoiceField(
        choices=Language.choices, required=False, help_text="Preferred language"
    )
    privacy_level = serializers.ChoiceField(
        choices=PrivacyLevel.choices, required=False, help_text="Privacy level setting"
    )
    theme_preference = serializers.ChoiceField(
        choices=ThemePreference.choices, required=False, help_text="UI theme preference"
    )
    notification_preferences = serializers.JSONField(
        required=False, help_text="Notification preferences object"
    )

    def validate_bio(self, value):
        """Validate bio length."""
        if value and len(value.strip()) < 10:
            raise serializers.ValidationError(
                _("Biography must be at least 10 characters long")
            )
        return value

    def validate_phone_number(self, value):
        """Validate phone number format."""
        if value and value.strip():
            # Basic phone validation
            import re

            pattern = r"^\+?1?\d{9,15}$"
            if not re.match(pattern, value.strip()):
                raise serializers.ValidationError(_("Invalid phone number format"))
        return value

    def save(self, user):
        """Update user and profile with validated data."""
        validated_data = self.validated_data

        # Separate user fields from profile fields
        user_fields = ["first_name", "last_name", "phone_number", "avatar"]
        profile_fields = [
            "bio",
            "location",
            "timezone",
            "preferred_language",
            "privacy_level",
            "theme_preference",
            "notification_preferences",
        ]

        user_data = {k: v for k, v in validated_data.items() if k in user_fields}
        profile_data = {k: v for k, v in validated_data.items() if k in profile_fields}

        # Update user fields
        for field, value in user_data.items():
            setattr(user, field, value)
        if user_data:
            user.save(update_fields=list(user_data.keys()) + ["updated_at"])

        # Update profile fields
        if profile_data:
            profile, created = Profile.objects.get_or_create(user=user)
            for field, value in profile_data.items():
                setattr(profile, field, value)
            profile.save(update_fields=list(profile_data.keys()) + ["updated_at"])
        else:
            # Ensure profile exists
            profile, created = Profile.objects.get_or_create(user=user)

        return user, profile


class ProfileOnlyUpdateSerializer(BaseAuthSerializerMixin, serializers.ModelSerializer):
    """
    Profile-only update serializer.
    For updating only profile-specific fields.
    """

    class Meta:
        model = Profile
        fields = [
            "bio",
            "location",
            "timezone",
            "preferred_language",
            "privacy_level",
            "theme_preference",
            "notification_preferences",
        ]
        extra_kwargs = {
            "bio": {"required": False},
            "location": {"required": False},
            "timezone": {"required": False},
            "preferred_language": {"required": False},
            "privacy_level": {"required": False},
            "theme_preference": {"required": False},
            "notification_preferences": {"required": False},
        }

    def validate_bio(self, value):
        """Validate bio length."""
        if value and len(value.strip()) < 10:
            raise serializers.ValidationError(
                _("Biography must be at least 10 characters long")
            )
        return value


class PasswordChangeSerializer(BaseAuthSerializerMixin, serializers.Serializer):
    """
    Password change serializer for authenticated users.
    """

    current_password = serializers.CharField(
        write_only=True, help_text="User's current password for verification"
    )
    new_password = serializers.CharField(
        write_only=True, min_length=8, help_text="New password (minimum 8 characters)"
    )
    new_password_confirm = serializers.CharField(
        write_only=True, help_text="Confirmation of new password"
    )

    def validate_current_password(self, value):
        """Validate current password is provided."""
        if not value:
            raise serializers.ValidationError(_("Current password is required"))
        return value

    def validate_new_password(self, value):
        """Validate new password strength."""
        if not value:
            raise serializers.ValidationError(_("New password is required"))

        # Use Django's password validation
        try:
            validate_password(value, self.context.get("user"))
        except ValidationError as e:
            raise serializers.ValidationError(str(e))

        return value

    def validate(self, attrs):
        """Validate password change data."""
        attrs = super().validate(attrs)

        current_password = attrs.get("current_password")
        new_password = attrs.get("new_password")
        new_password_confirm = attrs.get("new_password_confirm")

        # Check password confirmation
        if new_password != new_password_confirm:
            raise serializers.ValidationError(
                {"new_password_confirm": _("Password confirmation does not match")}
            )

        # Check current password is correct
        user = self.context.get("user")
        if user and not user.check_password(current_password):
            raise serializers.ValidationError(
                {"current_password": _("Current password is incorrect")}
            )

        # Check new password is different from current
        if current_password == new_password:
            raise serializers.ValidationError(
                {
                    "new_password": _(
                        "New password must be different from current password"
                    )
                }
            )

        # Remove password_confirm from validated data
        attrs.pop("new_password_confirm", None)
        return attrs

    def save(self):
        """Change user password."""
        user = self.context["user"]
        new_password = self.validated_data["new_password"]

        # Change password using service
        from apps.users.services import change_user_password

        result = change_user_password(
            user=user,
            current_password=self.validated_data["current_password"],
            new_password=new_password,
        )

        return result
