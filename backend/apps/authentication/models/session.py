"""
User session models for tracking and managing user authentication sessions.
"""

import secrets
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.constants import DeviceType, LoginMethod
from core.mixins import BaseModelMixin

from ..managers import UserSessionManager
from .user import User


class UserSession(BaseModelMixin):
    """
    User authentication session tracking.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sessions",
        verbose_name=_("user"),
        help_text=_("User associated with this session."),
    )

    session_key = models.CharField(
        _("session key"),
        max_length=255,
        unique=True,
        db_index=True,
        help_text=_("Unique session identifier."),
    )

    login_method = models.CharField(
        _("login method"),
        max_length=20,
        choices=LoginMethod.choices,
        default=LoginMethod.PASSWORD,
        help_text=_("Authentication method used for login."),
    )

    ip_address = models.GenericIPAddressField(
        _("IP address"),
        help_text=_("Client IP address."),
    )

    user_agent = models.TextField(
        _("user agent"),
        help_text=_("Browser/device user agent string."),
    )

    device_type = models.CharField(
        _("device type"),
        max_length=15,
        choices=DeviceType.choices,
        default=DeviceType.UNKNOWN,
        help_text=_("Detected device category."),
    )

    login_at = models.DateTimeField(
        _("login time"),
        auto_now_add=True,
        help_text=_("When the session was created."),
    )

    last_activity = models.DateTimeField(
        _("last activity"),
        auto_now=True,
        help_text=_("Last time session was used."),
    )

    expires_at = models.DateTimeField(
        _("expires at"),
        help_text=_("Session expiration timestamp."),
    )

    # Custom manager
    objects = UserSessionManager()

    class Meta:
        verbose_name = _("User Session")
        verbose_name_plural = _("User Sessions")
        db_table = "auth_user_session"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["session_key"]),
            models.Index(fields=["expires_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["session_key"],
                name="unique_session_key",
            ),
        ]

    def __str__(self):
        """String representation of UserSession."""
        return f"{self.user.email} - {self.get_device_type_display()}"

    def save(self, *args, **kwargs):
        """Override save to ensure key generation and expiration."""
        # Generate session key if not provided
        if not self.session_key:
            self.session_key = self.generate_session_key()

        # Set default expiration if not provided (7 days)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)

        super().save(*args, **kwargs)

    @classmethod
    def generate_session_key(cls):
        """Generate a cryptographically secure session key."""
        return secrets.token_urlsafe(32)

    @property
    def is_expired(self):
        """Check if session is expired."""
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        """Check if session is valid (active, not expired)."""
        return self.is_active and not self.is_expired

    def terminate(self, reason="user_logout"):
        """Terminate the session."""
        self.deactivate()  # From ActiveMixin
        self.save(update_fields=["is_active", "updated_at"])
