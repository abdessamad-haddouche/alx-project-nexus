"""
User-related models for Movie Nexus authentication.

Contains User and UserProfile models with mixin-based architecture.
"""

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Import constants
from core.constants import Language, PrivacyLevel, ThemePreference, Timezone, UserRole
from core.defaults import get_default_notification_preferences

# Import exceptions
from core.exceptions import EmailNotVerifiedException, ValidationException

# Import mixins
from core.mixins import BaseModelMixin, TimeStampedMixin

# Import managers from this app
from ..managers import UserManager, UserProfileManager

# ================================================================
# USER MODEL
# ================================================================


class User(AbstractUser, TimeStampedMixin):
    """
    Custom user model using email as the unique identifier.

    Uses:
    - AbstractUser: Django's built-in user functionality
    - TimeStampedMixin: Automatic timestamp tracking (created_at, updated_at)
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

    def clean(self):
        """Custom validation for the User model."""
        super().clean()

        # Normalize email
        if self.email:
            self.email = self.email.lower().strip()

        # Normalize names
        if self.first_name:
            self.first_name = self.first_name.strip().title()

        if self.last_name:
            self.last_name = self.last_name.strip().title()

        # Validate date of birth
        if self.date_of_birth and self.date_of_birth >= timezone.now().date():
            raise ValidationError(
                {"date_of_birth": _("Date of birth must be in the past.")}
            )

    def save(self, *args, **kwargs):
        """Override save to ensure data validation."""
        self.clean()
        super().save(*args, **kwargs)

    def verify_email(self):
        """
        Mark user's email as verified.

        Raises:
            ValidationException: If user is already verified
        """
        if self.is_email_verified:
            raise ValidationException(
                detail=_("Email is already verified"), extra_data={"email": self.email}
            )

        self.is_email_verified = True
        self.save(update_fields=["is_email_verified"])

    def require_email_verification(self):
        """
        Check if email verification is required.

        Raises:
            EmailNotVerifiedException: If email is not verified
        """
        if not self.is_email_verified:
            raise EmailNotVerifiedException(
                detail=_("Email verification required"),
                extra_data={"email": self.email},
            )

    def has_role(self, role):
        """
        Check if user has specific role.

        Args:
            role: UserRole enum value

        Returns:
            bool: True if user has the role
        """
        return self.role == role

    def is_admin(self):
        """Check if user is admin or superadmin."""
        return self.role in [UserRole.ADMIN, UserRole.SUPERADMIN]

    def is_moderator_or_above(self):
        """Check if user is moderator, admin, or superadmin."""
        return self.role in [UserRole.MODERATOR, UserRole.ADMIN, UserRole.SUPERADMIN]

    @property
    def full_name(self):
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_name(self):
        """Return display name (full name or email)."""
        return self.full_name or self.email

    @property
    def age(self):
        """Calculate and return user's age."""
        if not self.date_of_birth:
            return None

        today = timezone.now().date()
        return (
            today.year
            - self.date_of_birth.year
            - (
                (today.month, today.day)
                < (self.date_of_birth.month, self.date_of_birth.day)
            )
        )

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

    def get_active_sessions(self):
        """Get all active sessions for this user."""
        # To be implemented with UserSession model
        return []

    def invalidate_all_sessions(self, reason="security"):
        """Invalidate all user sessions."""
        # To be implemented with UserSession model
        pass


# ================================================================
# USER PROFILE MODEL
# ================================================================


class UserProfile(BaseModelMixin):
    """
    Extended user profile information.

    Uses:
    - BaseModelMixin: TimeStamped + Active + BaseManager functionality
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

    profile_views = models.PositiveIntegerField(
        _("profile views"),
        default=0,
        help_text=_("Number of times profile has been viewed."),
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
            models.Index(fields=["preferred_language"]),
        ]

    def __str__(self):
        return f"{self.user.email} Profile"

    def clean(self):
        """Custom validation for UserProfile"""
        super().clean()

        # Validate bio length if provided
        if self.bio and len(self.bio.strip()) < 10:
            raise ValidationError(
                {"bio": _("Biography must be at least 10 characters long.")}
            )

        # Clean location
        if self.location:
            self.location = self.location.strip().title()

    def save(self, *args, **kwargs):
        """Override save to ensure validation."""
        self.clean()
        super().save(*args, **kwargs)

    def get_notification_setting(self, setting_name, default=True):
        """
        Get specific notification setting.

        Args:
            setting_name: Name of the notification setting
            default: Default value if setting not found

        Returns:
            Setting value or default
        """
        return self.notification_preferences.get(setting_name, default)

    def update_notification_setting(self, setting_name, value):
        """
        Update specific notification setting.

        Args:
            setting_name: Name of the notification setting
            value: New value for the setting
        """
        self.notification_preferences[setting_name] = value
        self.save(update_fields=["notification_preferences"])

    def increment_profile_views(self):
        """Increment profile view count."""
        self.profile_views += 1
        self.save(update_fields=["profile_views"])

    @property
    def is_public(self):
        """Check if profile is public."""
        return self.privacy_level == PrivacyLevel.PUBLIC
