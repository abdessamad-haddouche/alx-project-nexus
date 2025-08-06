"""
User's Profile models for Movie Nexus authentication.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.constants import Language, PrivacyLevel, ThemePreference, Timezone
from core.defaults import get_default_notification_preferences
from core.mixins import BaseModelMixin

from ..managers import ProfileManager


class Profile(BaseModelMixin):
    """
    Extended user profile information.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
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
    objects = ProfileManager()

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
