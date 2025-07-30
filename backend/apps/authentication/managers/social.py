"""
Custom managers for SocialAuth model.
Provides optimized queries and business logic methods for OAuth authentication.
"""

from django.db import models

from core.constants import AuthProvider


class SocialAuthManager(models.Manager):
    """
    Custom manager for SocialAuth.
    """

    def get_queryset(self):
        """Optimize default queryset with select_related for user data."""
        return super().get_queryset().select_related("user").filter(is_active=True)

    def get_by_provider_user_id(self, provider, provider_user_id):
        """Get social auth by provider and external user ID."""
        return self.get(provider=provider, provider_user_id=provider_user_id)

    def find_by_provider_email(self, provider, email):
        """Find social auth by provider and email."""
        try:
            return self.get(provider=provider, provider_email=email.lower().strip())
        except self.model.DoesNotExist:
            return None

    def active_for_user(self, user):
        """Get all active social auths for a specific user."""
        return self.filter(user=user)

    def by_provider(self, provider):
        """Get all social auths for a specific provider."""
        return self.filter(provider=provider)

    def google_auths(self):
        """Get all Google OAuth authentications."""
        return self.by_provider(AuthProvider.GOOGLE)
