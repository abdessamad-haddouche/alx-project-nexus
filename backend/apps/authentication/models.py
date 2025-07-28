"""
Authentication models for Movie Nexus.

This module contains all authentication-related models including User, UserProfile,
OAuth integration, email verification, JWT token management, and session tracking.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.constants import (
    AuthProvider,
    Language,
    PrivacyLevel,
    ThemePreference,
    Timezone,
    UserRole,
)
from core.defaults import get_default_notification_preferences
from core.exceptions import (
    EmailNotVerifiedException,
    InvalidCredentialsException,
    TokenExpiredException,
    UserNotFoundException,
    ValidationException,
)
from core.models import BaseModel, TimeStampedModel

# ================================================================
# USER MANAGER
# ================================================================


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication"""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user with the given email and password"""
        if not email:
            raise ValidationException(
                detail=_("The Email field must be set"),
                field_errors={"email": "Email is required"},
            )

        # For regular users, password is required unless explicitly creating OAuth user
        is_oauth_user = extra_fields.pop("is_oauth_user", False)
        if not password and not is_oauth_user:
            raise ValidationException(
                detail=_("Password is required for regular users"),
                field_errors={"password": "Password is required"},
            )

        email = self.normalize_email(email)
        # Account enabled by default - can log in immediately
        extra_fields.setdefault("is_active", True)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)

        try:
            user.save(using=self._db)
        except Exception as e:
            raise ValidationException(
                detail=_("Failed to create user"), extra_data={"error": str(e)}
            )

        return user

    def create_oauth_user(self, email, provider_data=None, **extra_fields):
        """Create user for OAuth authentication (no password required)."""
        extra_fields["is_oauth_user"] = True
        extra_fields["is_email_verified"] = True  # OAuth emails are pre-verified

        return self.create_user(email=email, password=None, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with the given email and password."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_email_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValidationException(
                detail=_("Superuser must have is_staff=True"),
                field_errors={"is_staff": "Superuser must be staff"},
            )
        if extra_fields.get("is_superuser") is not True:
            raise ValidationException(
                detail=_("Superuser must have is_superuser=True"),
                field_errors={"is_superuser": "Superuser flag required"},
            )

        return self.create_user(email, password, **extra_fields)

    def get_by_email(self, email):
        """
        Get user by email with proper exception handling.

        Args:
            email: User email address

        Returns:
            User instance

        Raises:
            UserNotFoundException: If user with email doesn't exist
        """
        try:
            return self.get(email=email, is_active=True)
        except self.model.DoesNotExist:
            raise UserNotFoundException(
                detail=_("User with this email does not exist"),
                extra_data={"email": email},
            )

    def authenticate_user(self, email, password):
        """
        Authenticate user with email and password.

        Args:
            email: User email
            password: User password

        Returns:
            User instance if authentication successful

        Raises:
            InvalidCredentialsException: If credentials are invalid (security)
        """
        try:
            user = self.get_by_email(email)
        except UserNotFoundException:
            raise InvalidCredentialsException()

        if not user.check_password(password):
            raise InvalidCredentialsException()

        return user


# ================================================================
# USER PROFILE MANAGER
# ================================================================


class UserProfileManager(models.Manager):
    """Custom manager for UserProfile with basic optimizations."""

    def get_queryset(self):
        """Optimize default queryset with select_related."""
        # Use select_related to fetch related User in a single query
        # and avoid N+1 DB hits when accessing profile.user
        return super().get_queryset().select_related("user")

    def get_by_user_id(self, user_id):
        """
        Get profile by user ID with proper error handling.

        Args:
            user_id: User ID

        Returns:
            UserProfile instance

        Raises:
            NotFoundException: If profile doesn't exist
        """
        try:
            return self.get(user_id=user_id)
        except self.model.DoesNotExist:
            raise UserNotFoundException(
                detail=_("User profile not found"), extra_data={"user_id": user_id}
            )

    def public_profiles(self):
        """Get only public profiles."""
        return self.filter(privacy_level=PrivacyLevel.PUBLIC)


# ================================================================
# USER SOCIAL AUTH MANAGER
# ================================================================


class SocialAuthManager(models.Manager):
    """Custom manager for SocialAuth with provider-specific queries."""

    def get_queryset(self):
        """Optimize default queryset with select_related."""
        return super().get_queryset().select_related("user")

    def get_by_provider_user_id(self, provider, provider_user_id):
        """
        Get social auth by provider and external user ID.

        Args:
            provider: OAuth provider name
            provider_user_id: External user ID

        Returns:
            SocialAuth instance

        Raises:
            NotFoundException: If social auth not found
        """
        try:
            return self.get(
                provider=provider, provider_user_id=provider_user_id, is_active=True
            )
        except self.model.DoesNotExist:
            raise UserNotFoundException(
                detail=_("Social authentication not found"),
                extra_data={"provider": provider, "provider_user_id": provider_user_id},
            )

    def find_user_by_provider_email(self, provider, email):
        """
        Find user by provider email for account linking.

        Args:
            provider: OAuth provider name
            email: Provider email address

        Returns:
            User instance or None
        """
        try:
            social_auth = self.get(
                provider=provider, provider_email=email, is_active=True
            )
            return social_auth.user
        except self.model.DoesNotExist:
            return None

    def active_for_user(self, user):
        """Get all active social auths for a user."""
        return self.filter(user=user, is_active=True)


# ================================================================
# USER MODEL (extends AbstractUser)
# ================================================================


class User(AbstractUser, TimeStampedModel):
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

    # Optional phone number
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

    # User's birth date
    date_of_birth = models.DateField(
        _("date of birth"), blank=True, null=True, help_text=_("User birth date.")
    )

    # Profile picture URL
    avatar = models.URLField(
        _("avatar"),
        max_length=500,
        blank=True,
        null=True,
        help_text=_("Profile picture URL."),
    )

    # User role for access control
    role = models.CharField(
        _("role"),
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.USER,
        db_index=True,
        help_text=_("User role for access control."),
    )

    # Use email as username field (email and password are required by default)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    # Custom manager
    objects = UserManager()

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        db_table = "nexus_user"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["date_joined"]),
            models.Index(fields=["is_email_verified"]),
            models.Index(fields=["is_active", "is_email_verified"]),
            models.Index(fields=["role"]),
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

    def save(self, *args, **kwargs):
        """Override save to ensure data validation."""
        self.clean()
        super().save(*args, **kwargs)

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
        # To be implemented
        pass

    def invalidate_all_sessions(self, reason="security"):
        """Invalidate all user sessions."""
        # To be implemented
        pass


# ================================================================
# USER PROFILE MODEL
# ================================================================


class UserProfile(BaseModel):
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
        # Return a fresh copy for each instance to avoid shared mutable defaults
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

    @property
    def is_public(self):
        """Check if profile is public."""
        return self.privacy_level == PrivacyLevel.PUBLIC

    @property
    def display_location(self):
        """Get formatted location for display."""
        return self.location if self.location else _("Location not specified")


# ================================================================
# SOCIAL AUTH MODEL
# ================================================================


class SocialAuth(BaseModel):
    """
    OAuth provider integration for social authentication
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

    # Custom manager
    objects = SocialAuthManager()

    class Meta:
        verbose_name = _("Social Authentication")
        verbose_name_plural = _("Social Authentications")
        db_table = "auth_social_auth"
        unique_together = [["provider", "provider_user_id"]]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["provider"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["provider", "provider_user_id"]),
            models.Index(fields=["provider_email"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_user_id"],
                condition=models.Q(is_active=True),
                name="unique_active_provider_user",
            ),
        ]

    def __str__(self):
        # Django by default creates get_field_display() for any field with choices
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
        """Check if OAuth token is expired."""
        if not self.token_expires_at:
            return False
        return timezone.now() >= self.token_expires_at

    def refresh_access_token(self):
        """
        Refresh the OAuth access token.

        Raises:
            TokenExpiredException: If refresh token is expired
            ValidationException: If refresh fails
        """
        if self.is_token_expired():
            raise TokenExpiredException(
                detail=_("OAuth token has expired"),
                extra_data={"provider": self.provider},
            )
        # TODO: Implement actual token refresh logic based on provider

    @property
    def provider_display_name(self):
        """Get human-readable provider name."""
        return self.get_provider_display()

    @property
    def is_google(self):
        """Check if this is Google OAuth."""
        return self.provider == AuthProvider.GOOGLE

    @property
    def is_facebook(self):
        """Check if this is Facebook OAuth."""
        return self.provider == AuthProvider.FACEBOOK

    def update_provider_data(self, new_data):
        """
        Update provider data with new information.

        Args:
            new_data: Dictionary of new provider data
        """
        if not isinstance(new_data, dict):
            raise ValidationException(
                detail=_("Provider data must be a dictionary"),
                extra_data={"provided_type": type(new_data).__name__},
            )

        self.provider_data.update(new_data)
        self.save(update_fields=["provider_data", "updated_at"])
