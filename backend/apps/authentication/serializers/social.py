"""
Social authentication serializers for Movie Nexus.
"""

from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from core.constants import AuthProvider
from core.mixins.serializers import BaseAuthSerializerMixin

from ..models import SocialAuth, UserProfile

User = get_user_model()


class SocialAuthSerializer(BaseAuthSerializerMixin, serializers.ModelSerializer):
    """
    Social auth serializer for viewing linked accounts.
    """

    user_email = serializers.EmailField(source="user.email", read_only=True)
    provider_display = serializers.CharField(
        source="get_provider_display", read_only=True
    )

    class Meta:
        model = SocialAuth
        fields = [
            "id",
            "user",
            "user_email",
            "provider",
            "provider_display",
            "provider_email",
            "is_active",
            "created_at",
        ]
        extra_kwargs = {
            "user": {"read_only": True},
            "provider_user_id": {"write_only": True},
            "access_token": {"write_only": True},
        }


class GoogleOAuthSerializer(BaseAuthSerializerMixin, serializers.Serializer):
    """
    Google OAuth login/registration serializer.
    """

    access_token = serializers.CharField(write_only=True)

    def validate_access_token(self, value):
        """Basic token validation."""
        if not value or len(value.strip()) < 20:
            raise serializers.ValidationError(_("Invalid access token"))
        return value.strip()

    def validate_google_token(self, access_token):
        """
        Validate Google access token and get user info.
        Simplified version - in production you'd verify with Google API.
        """
        # TODO: verify token with Google API

        google_user_data = {
            "id": "123456789",
            "email": "user@gmail.com",
            "name": "John Doe",
            "picture": "https://example.com/picture.jpg",
        }

        return google_user_data

    def validate(self, attrs):
        """Validate Google OAuth data."""
        access_token = attrs.get("access_token")

        # Validate token and get user data from Google
        try:
            google_data = self.validate_google_token(access_token)
            attrs["google_data"] = google_data
        except Exception:
            raise serializers.ValidationError(_("Invalid Google token"))

        return attrs

    def create(self, validated_data):
        """Login or register user with Google OAuth."""
        google_data = validated_data["google_data"]

        google_id = str(google_data["id"])
        google_email = google_data["email"].lower().strip()

        # Try to find existing social auth
        try:
            social_auth = SocialAuth.objects.get(
                provider=AuthProvider.GOOGLE, provider_user_id=google_id, is_active=True
            )
            user = social_auth.user
            created = False

        except SocialAuth.DoesNotExist:
            # Try to find user by email
            try:
                user = User.objects.get(email=google_email)
                created = False
            except User.DoesNotExist:
                # Create new user
                user = self.create_user_from_google(google_data)
                created = True

            # Create social auth record
            social_auth = SocialAuth.objects.create(
                user=user,
                provider=AuthProvider.GOOGLE,
                provider_user_id=google_id,
                provider_email=google_email,
                access_token=validated_data["access_token"],
                provider_data=google_data,
            )

        # Create session
        request = self.context.get("request")
        from ..models import UserSession

        session = UserSession.objects.create_session(
            user=user,
            ip_address=request.META.get("REMOTE_ADDR", "") if request else "",
            user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
            login_method="google",
        )

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        access_token["session_id"] = str(session.id)
        access_token["email_verified"] = user.is_email_verified

        return {
            "user": user,
            "social_auth": social_auth,
            "session": session,
            "created": created,
            "tokens": {
                "refresh": str(refresh),
                "access": str(access_token),
            },
        }

    def create_user_from_google(self, google_data):
        """Create user from Google OAuth data."""
        email = google_data["email"].lower().strip()
        name = google_data.get("name", "").strip()

        # Parse name
        name_parts = name.split(" ", 1) if name else ["", ""]
        first_name = name_parts[0] or "User"
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Create user
        user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_email_verified=True,  # Google emails are pre-verified
            avatar=google_data.get("picture", ""),
        )

        # Create profile
        UserProfile.objects.create(user=user)

        return user

    def to_representation(self, instance):
        """Return OAuth login response."""
        user = instance["user"]
        tokens = instance["tokens"]
        created = instance["created"]

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "avatar_url": user.avatar_url,
                "is_email_verified": user.is_email_verified,
            },
            "tokens": tokens,
            "created": created,
            "message": _("Google login successful"),
        }


class SocialAuthLinkSerializer(BaseAuthSerializerMixin, serializers.Serializer):
    """
    Serializer for linking social accounts to existing user.
    """

    provider = serializers.ChoiceField(choices=AuthProvider.choices)
    access_token = serializers.CharField(write_only=True)

    def validate(self, attrs):
        """Validate social auth linking."""
        provider = attrs.get("provider")
        access_token = attrs.get("access_token")

        if not self.current_user:
            raise serializers.ValidationError(
                _("User must be authenticated to link accounts")
            )

        # Validate token based on provider
        if provider == AuthProvider.GOOGLE:
            google_serializer = GoogleOAuthSerializer()
            provider_data = google_serializer.validate_google_token(access_token)
        else:
            raise serializers.ValidationError(_("Unsupported provider"))

        attrs["provider_data"] = provider_data
        return attrs

    def create(self, validated_data):
        """Link social account to current user."""
        provider = validated_data["provider"]
        provider_data = validated_data["provider_data"]
        access_token = validated_data["access_token"]
        user = self.current_user

        provider_user_id = str(provider_data.get("id") or provider_data.get("sub"))
        provider_email = provider_data.get("email", "").lower().strip()

        # Check if this social account is already linked to another user
        existing_social = SocialAuth.objects.filter(
            provider=provider, provider_user_id=provider_user_id, is_active=True
        ).first()

        if existing_social and existing_social.user != user:
            raise serializers.ValidationError(
                _("This social account is already linked to another user")
            )

        # Create or update social auth
        social_auth, created = SocialAuth.objects.update_or_create(
            user=user,
            provider=provider,
            provider_user_id=provider_user_id,
            defaults={
                "provider_email": provider_email,
                "access_token": access_token,
                "provider_data": provider_data,
                "is_active": True,
            },
        )

        return {
            "social_auth": social_auth,
            "created": created,
        }

    def to_representation(self, instance):
        """Return link response."""
        social_auth = instance["social_auth"]
        created = instance["created"]

        return {
            "social_auth": {
                "id": social_auth.id,
                "provider": social_auth.provider,
                "provider_display": social_auth.get_provider_display(),
                "provider_email": social_auth.provider_email,
            },
            "created": created,
            "message": _("Social account linked successfully")
            if created
            else _("Social account updated successfully"),
        }
