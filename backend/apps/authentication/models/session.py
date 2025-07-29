"""
User session models for tracking and managing user authentication sessions.

"""

import secrets
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Import constants
from core.constants import DeviceType, LoginMethod, SessionStatus

# Import exceptions
from core.exceptions import ValidationException

# Import mixins
from core.mixins import BaseModelMixin

# Import managers from this app
from ..managers import UserSessionManager

# Import User model
from .user import User


class UserSession(BaseModelMixin):
    """
    User authentication session tracking and management.

    Uses:
    - BaseModelMixin: TimeStamped + Active + BaseManager functionality
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

    # Authentication details
    login_method = models.CharField(
        _("login method"),
        max_length=20,
        choices=LoginMethod.choices,
        default=LoginMethod.PASSWORD,
        help_text=_("Authentication method used for login."),
    )

    # Device and location information
    ip_address = models.GenericIPAddressField(
        _("IP address"),
        help_text=_("Client IP address."),
    )

    user_agent = models.TextField(
        _("user agent"),
        help_text=_("Browser/device user agent string."),
    )

    device_info = models.JSONField(
        _("device information"),
        default=dict,
        blank=True,
        help_text=_("Parsed device details (browser, OS, device type)."),
    )

    device_type = models.CharField(
        _("device type"),
        max_length=15,
        choices=DeviceType.choices,
        default=DeviceType.UNKNOWN,
        help_text=_("Detected device category."),
    )

    location_data = models.JSONField(
        _("location data"),
        default=dict,
        blank=True,
        help_text=_("Geographic location information."),
    )

    # Session lifecycle
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

    logout_at = models.DateTimeField(
        _("logout time"),
        null=True,
        blank=True,
        help_text=_("When the session was terminated."),
    )

    expires_at = models.DateTimeField(
        _("expires at"),
        help_text=_("Session expiration timestamp."),
    )

    # Session status and security
    status = models.CharField(
        _("session status"),
        max_length=20,
        choices=SessionStatus.choices,
        default=SessionStatus.ACTIVE,
        db_index=True,
        help_text=_("Current session status."),
    )

    is_remembered = models.BooleanField(
        _("remember me"),
        default=False,
        help_text=_("Extended session lifetime (remember me)."),
    )

    # Security tracking
    login_attempts = models.PositiveIntegerField(
        _("login attempts"),
        default=1,
        help_text=_("Number of login attempts before success."),
    )

    # Session metadata
    session_data = models.JSONField(
        _("session data"),
        default=dict,
        blank=True,
        help_text=_("Additional session-specific data."),
    )

    logout_reason = models.CharField(
        _("logout reason"),
        max_length=50,
        blank=True,
        help_text=_("Reason for session termination."),
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
            models.Index(fields=["ip_address"]),
            models.Index(fields=["status"]),
            models.Index(fields=["login_at"]),
            models.Index(fields=["last_activity"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["device_type"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["session_key"],
                name="unique_session_key",
            ),
        ]

    def __str__(self):
        """String representation of UserSession."""
        device_info = self.get_device_display()
        return f"{self.user.email} - {device_info} ({self.get_status_display()})"

    def clean(self):
        """Custom validation for UserSession."""
        super().clean()

        # Validate expiration date
        if self.expires_at and self.expires_at <= timezone.now():
            raise ValidationException(
                detail=_("Session expiration must be in the future"),
                field_errors={"expires_at": "Must be in the future"},
            )

        # Validate login attempts
        if self.login_attempts < 1:
            raise ValidationException(
                detail=_("Login attempts must be at least 1"),
                field_errors={"login_attempts": "Must be at least 1"},
            )

    def save(self, *args, **kwargs):
        """Override save to ensure validation and key generation."""
        # Generate session key if not provided
        if not self.session_key:
            self.session_key = self.generate_session_key()

        # Set default expiration if not provided
        if not self.expires_at:
            self.expires_at = self.get_default_expiration()

        self.clean()
        super().save(*args, **kwargs)

    @classmethod
    def generate_session_key(cls):
        """
        Generate a cryptographically secure session key.

        Returns:
            str: Secure random session key
        """
        return secrets.token_urlsafe(32)

    def get_default_expiration(self):
        """
        Get default session expiration based on remember me setting.

        Returns:
            datetime: Default expiration timestamp
        """
        from core.constants import DEFAULT_SESSION_EXPIRATION_HOURS

        # Standard session
        hours = DEFAULT_SESSION_EXPIRATION_HOURS
        return timezone.now() + timedelta(hours=hours)

    @property
    def is_expired(self):
        """
        Check if session is expired.

        Returns:
            bool: True if session is expired
        """
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        """
        Check if session is valid (active, not expired).

        Returns:
            bool: True if session is valid
        """
        return (
            self.is_active
            and self.status == SessionStatus.ACTIVE
            and not self.is_expired
        )

    @property
    def session_duration(self):
        """
        Get total session duration.

        Returns:
            timedelta: Session duration
        """
        end_time = self.logout_at or timezone.now()
        return end_time - self.login_at

    @property
    def time_until_expiry(self):
        """
        Get time remaining until expiration.

        Returns:
            timedelta: Time remaining, or None if expired
        """
        if self.is_expired:
            return None
        return self.expires_at - timezone.now()

    def terminate(self, reason="user_logout"):
        """
        Terminate the session.

        Args:
            reason: Reason for termination
        """
        self.status = SessionStatus.TERMINATED
        self.logout_at = timezone.now()
        self.logout_reason = reason
        self.deactivate()  # From ActiveMixin

        self.save(
            update_fields=[
                "status",
                "logout_at",
                "logout_reason",
                "is_active",
                "updated_at",
            ]
        )

    def extend_session(self, hours=None, days=None):
        """
        Extend session expiration.

        Args:
            hours: Hours to extend (optional)
            days: Days to extend (optional)
        """
        if hours:
            self.expires_at = timezone.now() + timedelta(hours=hours)
        elif days:
            self.expires_at = timezone.now() + timedelta(days=days)
        else:
            # Use default extension
            self.expires_at = self.get_default_expiration()

        self.save(update_fields=["expires_at", "updated_at"])
