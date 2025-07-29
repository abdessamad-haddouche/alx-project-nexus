"""
Social authentication models for OAuth provider integration.

Handles OAuth authentication for Google, Facebook, and other providers
with secure token management and user account linking.
"""


from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Import constants
from core.constants import AuthProvider

# Import exceptions
from core.exceptions import TokenExpiredException, ValidationException

# Import mixins
from core.mixins import BaseModelMixin

# Import managers from this app
from ..managers import SocialAuthManager

# Import User model
from .user import User

# ================================================================
# SOCIAL AUTH MODEL
# ================================================================


class SocialAuth(BaseModelMixin):
    """
    OAuth provider integration for social authentication.

    Uses:
    - BaseModelMixin: TimeStamped + Active + BaseManager functionality

    Manages OAuth authentication data including tokens, provider information,
    and user account linking for social login functionality.
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
        help_text=_("OAuth access token (encrypted)."),
    )

    refresh_token = models.TextField(
        _("refresh token"),
        blank=True,
        null=True,
        help_text=_("OAuth refresh token (encrypted)."),
    )

    token_expires_at = models.DateTimeField(
        _("token expires at"),
        blank=True,
        null=True,
        help_text=_("Token expiration timestamp."),
    )

    last_used_at = models.DateTimeField(
        _("last used at"),
        auto_now=True,
        help_text=_("Last time this OAuth connection was used."),
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
            models.Index(fields=["is_active"]),
            models.Index(fields=["provider", "provider_user_id"]),
            models.Index(fields=["provider_email"]),
            models.Index(fields=["token_expires_at"]),
            models.Index(fields=["last_used_at"]),
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

    def clean(self):
        """Custom validation for SocialAuth."""
        super().clean()

        # Normalize provider email
        if self.provider_email:
            self.provider_email = self.provider_email.lower().strip()

    def save(self, *args, **kwargs):
        """Override save to ensure validation."""
        self.clean()
        super().save(*args, **kwargs)

    def is_token_expired(self):
        """
        Check if OAuth token is expired.

        Returns:
            bool: True if token is expired or expiration is unknown
        """
        if not self.token_expires_at:
            # If no expiration time, consider it expired for safety
            return True
        return timezone.now() >= self.token_expires_at

    def is_token_valid(self):
        """
        Check if OAuth token is valid and not expired.

        Returns:
            bool: True if token exists and is not expired
        """
        return bool(self.access_token and not self.is_token_expired())

    def refresh_access_token(self):
        """
        Refresh the OAuth access token.

        Note: This is a placeholder for actual OAuth token refresh implementation.
        Each provider will have its own token refresh logic.

        Raises:
            TokenExpiredException: If refresh token is expired
            ValidationException: If refresh fails
        """
        if not self.refresh_token:
            raise ValidationException(
                detail=_("No refresh token available"),
                extra_data={"provider": self.provider},
            )

        if self.is_token_expired():
            raise TokenExpiredException(
                detail=_("OAuth token has expired"),
                extra_data={"provider": self.provider},
            )

        # TODO: Implement actual token refresh logic based on provider

    def revoke_token(self):
        """
        Revoke OAuth tokens and deactivate this social auth.

        This should be called when user disconnects their social account
        or when tokens are compromised.
        """
        # TODO: Implement actual token revocation with provider
        # Clear tokens from our database
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        self.deactivate()  # From ActiveMixin

    @property
    def provider_display_name(self):
        """Get human-readable provider name."""
        return self.get_provider_display()

    @property
    def is_google(self):
        """Check if this is Google OAuth."""
        return self.provider == AuthProvider.GOOGLE

    @property
    def provider_profile_picture(self):
        """Get user's profile picture URL from provider data."""
        if not self.provider_data:
            return None

        # Try different picture fields based on provider
        picture_fields = ["picture", "avatar", "profile_image_url", "photo"]
        for field in picture_fields:
            if field in self.provider_data:
                return self.provider_data[field]

        return None

    def update_provider_data(self, new_data):
        """
        Update provider data with new information.

        Args:
            new_data: Dictionary of new provider data

        Raises:
            ValidationException: If new_data is not a dictionary
        """
        if not isinstance(new_data, dict):
            raise ValidationException(
                detail=_("Provider data must be a dictionary"),
                extra_data={"provided_type": type(new_data).__name__},
            )

        # Merge new data with existing data
        if not self.provider_data:
            self.provider_data = {}

        self.provider_data.update(new_data)
        self.save(update_fields=["provider_data", "updated_at"])

    def update_tokens(self, access_token, refresh_token=None, expires_at=None):
        """
        Update OAuth tokens.

        Args:
            access_token: New access token
            refresh_token: New refresh token (optional)
            expires_at: Token expiration datetime (optional)
        """
        self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token
        if expires_at:
            self.token_expires_at = expires_at

        self.last_used_at = timezone.now()

        update_fields = ["access_token", "last_used_at", "updated_at"]
        if refresh_token:
            update_fields.append("refresh_token")
        if expires_at:
            update_fields.append("token_expires_at")

        self.save(update_fields=update_fields)
