"""
User authentication serializers.
"""

from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from core.constants import VerificationType
from core.mixins.serializers import BaseAuthSerializerMixin

from ..models import UserProfile, VerificationToken

User = get_user_model()


class UserSerializer(BaseAuthSerializerMixin, serializers.ModelSerializer):
    """
    User serializer for profile management.
    """

    # Read-only computed fields
    full_name = serializers.ReadOnlyField()
    display_name = serializers.ReadOnlyField()
    avatar_url = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "display_name",
            "phone_number",
            "date_of_birth",
            "avatar",
            "avatar_url",
            "is_active",
            "is_email_verified",
            "date_joined",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "email": {"required": True},
            "first_name": {"required": True},
            "last_name": {"required": True},
            "date_joined": {"read_only": True},
        }

    def validate_email(self, value):
        """Validate email uniqueness."""
        email = self.validate_email_format(value)

        # Check uniqueness (exclude current user for updates)
        queryset = User.objects.filter(email=email)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(_("User with this email already exists."))

        return email

    def update(self, instance, validated_data):
        """Update user fields."""
        return super().update(instance, validated_data)


class UserProfileSerializer(BaseAuthSerializerMixin, serializers.ModelSerializer):
    """
    User profile serializer.
    """

    # User info (read-only)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = UserProfile
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


class UserRegistrationSerializer(BaseAuthSerializerMixin, serializers.ModelSerializer):
    """
    User registration serializer.
    """

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
            "phone_number",
            "date_of_birth",
        ]
        extra_kwargs = {
            "email": {"required": True},
            "first_name": {"required": True},
            "last_name": {"required": True},
        }

    def validate_email(self, value):
        """Validate email availability."""
        email = self.validate_email_format(value)

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(_("User with this email already exists"))

        return email

    def validate(self, attrs):
        """Validate registration data."""
        attrs = super().validate(attrs)
        return self.validate_password_confirmation(attrs)

    def create(self, validated_data):
        """Create user and profile."""
        # Remove password_confirm
        validated_data.pop("password_confirm", None)

        # Create user
        user = User.objects.create_user(**validated_data)

        # Create profile
        UserProfile.objects.create(user=user)

        # Create verification token
        verification = VerificationToken.objects.create(
            user=user,
            email=user.email,
            verification_type=VerificationType.REGISTRATION,
        )

        return {
            "user": user,
            "verification_token": verification,
        }

    def to_representation(self, instance):
        """Return registration success response."""
        user = instance["user"]

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "is_email_verified": user.is_email_verified,
            },
            "message": _("Registration successful. Please check your email."),
        }


class UserLoginSerializer(BaseAuthSerializerMixin, serializers.Serializer):
    """
    User login serializer.
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        """Validate email format."""
        return self.validate_email_format(value)

    def validate(self, attrs):
        """Validate login credentials."""
        email = attrs.get("email")
        password = attrs.get("password")

        # Validate credentials
        user = self.validate_credentials(email, password)

        # Check email verification
        if not user.is_email_verified:
            raise serializers.ValidationError(
                _("Please verify your email address before logging in.")
            )

        attrs["user"] = user
        return attrs

    def create(self, validated_data):
        """Create login session and return tokens."""
        user = validated_data["user"]
        request = self.context.get("request")

        # Create user session (simple version)
        from ..models import UserSession

        session = UserSession.objects.create_session(
            user=user,
            ip_address=request.META.get("REMOTE_ADDR", "") if request else "",
            user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
        )

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token

        # Add custom claims
        access_token["session_id"] = str(session.id)
        access_token["email_verified"] = user.is_email_verified

        return {
            "user": user,
            "session": session,
            "tokens": {
                "refresh": str(refresh),
                "access": str(access_token),
            },
        }

    def to_representation(self, instance):
        """Return login response data."""
        user = instance["user"]
        tokens = instance["tokens"]

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "avatar_url": user.avatar_url,
                "is_email_verified": user.is_email_verified,
            },
            "tokens": tokens,
            "message": _("Login successful"),
        }


class PasswordResetRequestSerializer(BaseAuthSerializerMixin, serializers.Serializer):
    """
    Password reset request serializer.
    """

    email = serializers.EmailField()

    def validate_email(self, value):
        """Validate email format."""
        return self.validate_email_format(value)

    def create(self, validated_data):
        """Create password reset token if user exists."""
        email = validated_data["email"]

        try:
            user = User.objects.get(email=email, is_active=True)

            # Deactivate existing tokens
            VerificationToken.objects.filter(
                user=user,
                verification_type=VerificationType.PASSWORD_RESET,
                is_active=True,
                is_used=False,
            ).update(is_active=False)

            # Create new token
            reset_token = VerificationToken.objects.create(
                user=user,
                email=user.email,
                verification_type=VerificationType.PASSWORD_RESET,
            )

            return reset_token

        except User.DoesNotExist:
            # For security, don't reveal if email exists
            pass

        return None

    def to_representation(self, instance):
        """Return password reset response."""
        return {
            "message": _(
                "If an account exists with this email, "
                "password reset instructions have been sent."
            ),
        }


class PasswordResetConfirmSerializer(BaseAuthSerializerMixin, serializers.Serializer):
    """
    Password reset confirmation serializer.
    """

    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    def validate_token(self, value):
        """Validate password reset token."""
        try:
            verification = VerificationToken.objects.get_valid_token(value)
            if verification.verification_type != VerificationType.PASSWORD_RESET:
                raise serializers.ValidationError(_("Invalid token type"))
            return verification
        except Exception:
            raise serializers.ValidationError(_("Invalid or expired token"))

    def validate(self, attrs):
        """Validate password reset confirmation."""
        attrs = super().validate(attrs)
        return self.validate_password_confirmation(attrs)

    def create(self, validated_data):
        """Reset user password."""
        verification_token = validated_data["token"]
        new_password = validated_data["password"]

        user = verification_token.user

        # Verify the token
        verification_token.verify()

        # Update user password
        user.set_password(new_password)
        user.save(update_fields=["password"])

        return {"user": user}

    def to_representation(self, instance):
        """Return password reset success response."""
        user = instance["user"]

        return {
            "message": _("Password reset successful"),
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
            },
        }
