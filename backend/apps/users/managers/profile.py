"""
Custom managers for user's Profile models.
Provides optimized queries and business logic methods.
"""

from django.db import models

from core.constants import PrivacyLevel


class ProfileManager(models.Manager):
    """
    Custom manager for Profile.
    """

    def get_queryset(self):
        """Optimize default queryset with select_related."""
        return super().get_queryset().select_related("user")

    def public_profiles(self):
        """Get only public profiles."""
        return self.filter(
            privacy_level=PrivacyLevel.PUBLIC, is_active=True, user__is_active=True
        )

    def for_user(self, user):
        """Get profile for specific user with optimizations."""
        return self.select_related("user").get(user=user)

    def active_profiles(self):
        """Get all active profiles."""
        return self.filter(is_active=True, user__is_active=True)
