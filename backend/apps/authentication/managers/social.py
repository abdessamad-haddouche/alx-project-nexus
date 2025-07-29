"""
Custom managers for SocialAuth model.
Provides optimized queries and business logic methods for OAuth authentication.
"""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.constants import AuthProvider
from core.exceptions import UserNotFoundException, ValidationException


class SocialAuthManager(models.Manager):
    """
    Custom manager for SocialAuth with provider-specific queries and optimizations.
    """

    def get_queryset(self):
        """Optimize default queryset with select_related for user data."""
        return super().get_queryset().select_related("user").filter(is_active=True)

    def all_with_inactive(self):
        """Get all social auths including inactive ones."""
        return super().get_queryset().select_related("user")

    def get_by_provider_user_id(self, provider, provider_user_id):
        """
        Get social auth by provider and external user ID.

        Args:
            provider: OAuth provider name (AuthProvider enum value)
            provider_user_id: External user ID from the provider

        Returns:
            SocialAuth instance

        Raises:
            UserNotFoundException: If social auth not found
        """
        try:
            return self.get(provider=provider, provider_user_id=provider_user_id)
        except self.model.DoesNotExist:
            raise UserNotFoundException(
                detail=_("Social authentication not found"),
                extra_data={"provider": provider, "provider_user_id": provider_user_id},
            )

    def find_by_provider_email(self, provider, email):
        """
        Find social auth by provider and email.

        Args:
            provider: OAuth provider name
            email: Provider email address

        Returns:
            SocialAuth instance or None
        """
        try:
            return self.get(provider=provider, provider_email=email.lower().strip())
        except self.model.DoesNotExist:
            return None

    def find_user_by_provider_email(self, provider, email):
        """
        Find user by provider email for account linking.

        Args:
            provider: OAuth provider name
            email: Provider email address

        Returns:
            User instance or None
        """
        social_auth = self.find_by_provider_email(provider, email)
        return social_auth.user if social_auth else None

    def active_for_user(self, user):
        """
        Get all active social auths for a specific user.

        Args:
            user: User instance

        Returns:
            QuerySet of active SocialAuth instances
        """
        return self.filter(user=user)

    def by_provider(self, provider):
        """
        Get all social auths for a specific provider.

        Args:
            provider: OAuth provider name

        Returns:
            QuerySet of SocialAuth instances for the provider
        """
        return self.filter(provider=provider)

    def google_auths(self):
        """Get all Google OAuth authentications."""
        return self.by_provider(AuthProvider.GOOGLE)

    def with_valid_tokens(self):
        """
        Get social auths with valid (non-expired) tokens.

        Returns:
            QuerySet of SocialAuth instances with valid tokens
        """
        now = timezone.now()
        return self.filter(
            access_token__isnull=False, token_expires_at__gt=now
        ).exclude(access_token="")

    def create_from_oauth_data(self, user, provider, oauth_data):
        """
        Create a new SocialAuth from OAuth provider data.

        Args:
            user: User instance to associate with
            provider: OAuth provider name
            oauth_data: Dictionary containing OAuth data

        Returns:
            SocialAuth instance

        Raises:
            ValidationException: If required OAuth data is missing
        """
        required_fields = ["provider_user_id", "email"]
        missing_fields = [
            field
            for field in required_fields
            if field not in oauth_data or not oauth_data[field]
        ]

        if missing_fields:
            raise ValidationException(
                detail=_("Missing required OAuth data"),
                field_errors={
                    field: "This field is required" for field in missing_fields
                },
            )

        # Extract tokens if present
        access_token = oauth_data.get("access_token")
        refresh_token = oauth_data.get("refresh_token")
        expires_at = oauth_data.get("expires_at")

        # Create the social auth
        social_auth = self.create(
            user=user,
            provider=provider,
            provider_user_id=oauth_data["provider_user_id"],
            provider_email=oauth_data["email"],
            provider_data=oauth_data.get("provider_data", {}),
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=expires_at,
        )

        return social_auth

    def link_or_create(self, user, provider, oauth_data):
        """
        Link existing social auth to user or create new one.

        Args:
            user: User instance
            provider: OAuth provider name
            oauth_data: OAuth data dictionary

        Returns:
            tuple: (SocialAuth instance, created: bool)
        """
        provider_user_id = oauth_data.get("provider_user_id")

        if not provider_user_id:
            raise ValidationException(
                detail=_("Provider user ID is required"),
                field_errors={"provider_user_id": "This field is required"},
            )

        try:
            # Try to find existing social auth
            social_auth = self.get_by_provider_user_id(provider, provider_user_id)

            # Update existing social auth with new data
            social_auth.provider_email = oauth_data.get(
                "email", social_auth.provider_email
            )
            social_auth.update_provider_data(oauth_data.get("provider_data", {}))

            # Update tokens if provided
            if oauth_data.get("access_token"):
                social_auth.update_tokens(
                    access_token=oauth_data["access_token"],
                    refresh_token=oauth_data.get("refresh_token"),
                    expires_at=oauth_data.get("expires_at"),
                )

            # If social auth was linked to different user, update it
            if social_auth.user != user:
                social_auth.user = user
                social_auth.save(update_fields=["user", "updated_at"])

            return social_auth, False

        except UserNotFoundException:
            # Create new social auth
            social_auth = self.create_from_oauth_data(user, provider, oauth_data)
            return social_auth, True
