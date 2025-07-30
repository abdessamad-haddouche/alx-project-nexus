"""
User-related models for Movie Nexus authentication.
"""

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.constants import Language, PrivacyLevel, ThemePreference, Timezone, UserRole
from core.defaults import get_default_notification_preferences
from core.mixins import BaseModelMixin, TimeStampedMixin

from ..managers import UserManager, UserProfileManager


class User(AbstractUser, TimeStampedMixin):
    """
    Custom user model using email as the unique identifier.
    """

    # Remove username field from AbstractUser
    username = None

    # Primary authentication credential
    email = models.EmailField(
        _("email address"),
        max_length=254,
        unique=True,
        db_index=True,
        help_text=_("Required. User email address for authentication."),
    )

    first_name = models.CharField(
        _("first name"),
        max_length=50,
        blank=False,
        null=False,
        help_text=_("User first name."),
    )

    last_name = models.CharField(
        _("last name"),
        max_length=50,
        blank=False,
        null=False,
        help_text=_("User last name."),
    )

    is_email_verified = models.BooleanField(
        _("email verified"),
        default=False,
        db_index=True,
        help_text=_("Email verification status."),
    )

    phone_number = models.CharField(
        _("phone number"),
        max_length=15,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r"^\+?1?\d{9,15}$",
                message=_(
                    'Phone number must be entered in format: "+999999999". '
                    "Up to 15 digits allowed."
                ),
            )
        ],
        help_text=_("Optional phone number."),
    )

    date_of_birth = models.DateField(
        _("date of birth"), blank=True, null=True, help_text=_("User birth date.")
    )

    avatar = models.URLField(
        _("avatar"),
        max_length=500,
        blank=True,
        null=True,
        help_text=_("Profile picture URL."),
    )

    role = models.CharField(
        _("role"),
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.USER,
        db_index=True,
        help_text=_("User role for access control."),
    )

    # Use email as username field
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    # Custom manager
    objects = UserManager()

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        db_table = "auth_user"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["is_active", "is_email_verified"]),
            models.Index(fields=["role"]),
            models.Index(fields=["date_joined"]),
        ]

    def __str__(self):
        return self.email

    def verify_email(self):
        """Mark user's email as verified."""
        self.is_email_verified = True
        self.save(update_fields=["is_email_verified"])

    @property
    def full_name(self):
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_name(self):
        """Return display name (full name or email)."""
        return self.full_name or self.email

    @property
    def avatar_url(self):
        """Return avatar URL with fallback to generated avatar."""
        if self.avatar:
            return self.avatar

        # Generate initials-based avatar
        initials = (
            f"{self.first_name[0]}{self.last_name[0]}"
            if self.first_name and self.last_name
            else "U"
        )
        return (
            f"https://ui-avatars.com/api/?name={initials}"
            f"&background=6366f1&color=fff&size=200"
        )


class UserProfile(BaseModelMixin):
    """
    Extended user profile information.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name=_("user"),
        help_text=_("Reference to User model."),
    )

    bio = models.TextField(
        _("biography"),
        max_length=1000,
        blank=True,
        help_text=_("User biography/description."),
    )

    location = models.CharField(
        _("location"),
        max_length=100,
        blank=True,
        help_text=_("User geographic location."),
    )

    timezone = models.CharField(
        _("timezone"),
        max_length=50,
        choices=Timezone.choices,
        default=Timezone.UTC,
        help_text=_("User timezone."),
    )

    preferred_language = models.CharField(
        _("preferred language"),
        max_length=10,
        choices=Language.choices,
        default=Language.ENGLISH,
        help_text=_("Language preference (ISO 639-1)."),
    )

    privacy_level = models.CharField(
        _("privacy level"),
        max_length=20,
        choices=PrivacyLevel.choices,
        default=PrivacyLevel.PUBLIC,
        db_index=True,
        help_text=_("Privacy setting."),
    )

    notification_preferences = models.JSONField(
        _("notification preferences"),
        default=get_default_notification_preferences,
        help_text=_("Notification settings."),
    )

    theme_preference = models.CharField(
        _("theme preference"),
        max_length=20,
        choices=ThemePreference.choices,
        default=ThemePreference.LIGHT,
        help_text=_("UI theme preference."),
    )

    # Custom manager
    objects = UserProfileManager()

    class Meta:
        verbose_name = _("User Profile")
        verbose_name_plural = _("User Profiles")
        db_table = "auth_user_profile"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["privacy_level"]),
        ]

    def __str__(self):
        return f"{self.user.email} Profile"
