"""
Social authentication models for OAuth provider integration.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.constants import AuthProvider
from core.mixins import BaseModelMixin

from ..managers import SocialAuthManager
from .user import User


class SocialAuth(BaseModelMixin):
    """
    OAuth provider integration for social authentication.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="social_auths",
        verbose_name=_("user"),
        help_text=_("Reference to User model."),
    )

    provider = models.CharField(
        _("provider"),
        max_length=20,
        choices=AuthProvider.choices,
        db_index=True,
        help_text=_("OAuth provider name."),
    )

    provider_user_id = models.CharField(
        _("provider user ID"),
        max_length=100,
        help_text=_("External user ID from provider."),
    )

    provider_email = models.EmailField(
        _("provider email"), max_length=254, help_text=_("Email from OAuth provider.")
    )

    provider_data = models.JSONField(
        _("provider data"),
        default=dict,
        blank=True,
        help_text=_("Additional provider data (name, profile picture, etc.)."),
    )

    access_token = models.TextField(
        _("access token"),
        blank=True,
        null=True,
        help_text=_("OAuth access token."),
    )

    # Custom manager
    objects = SocialAuthManager()

    class Meta:
        verbose_name = _("Social Authentication")
        verbose_name_plural = _("Social Authentications")
        db_table = "auth_social_auth"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["provider"]),
            models.Index(fields=["provider", "provider_user_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_user_id"],
                condition=models.Q(is_active=True),
                name="unique_active_provider_user",
            ),
        ]

    def __str__(self):
        """String representation of SocialAuth."""
        return f"{self.user.email} - {self.get_provider_display()}"

    @property
    def is_google(self):
        """Check if this is Google OAuth."""
        return self.provider == AuthProvider.GOOGLE
