"""
Custom managers for User and UserProfile models.
Provides optimized queries and business logic methods.
"""

from django.contrib.auth.models import BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.constants import PrivacyLevel
from core.exceptions import (
    InvalidCredentialsException,
    UserNotFoundException,
    ValidationException,
)

# ================================================================
# USER MANAGER
# ================================================================


class UserManager(BaseUserManager):
    """
    Custom user manager for email-based authentication.
    Handles user creation, authentication, and common queries.
    """

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a regular user with the given email and password.

        Args:
            email: User email address
            password: User password (optional for OAuth users)
            **extra_fields: Additional user fields

        Returns:
            User instance

        Raises:
            ValidationException: If email is missing or creation fails
        """
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

        # Set sensible defaults
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)

        try:
            user.save(using=self._db)
        except Exception as e:
            raise ValidationException(
                detail=_("Failed to create user"), extra_data={"error": str(e)}
            )

        return user

    def create_oauth_user(self, email, provider_data=None, **extra_fields):
        """
        Create user for OAuth authentication (no password required).

        Args:
            email: User email from OAuth provider
            provider_data: Additional data from OAuth provider
            **extra_fields: Additional user fields

        Returns:
            User instance
        """
        # OAuth users have verified emails by default
        extra_fields.setdefault("is_email_verified", True)

        # Extract name from provider data if available
        if provider_data:
            if not extra_fields.get("first_name") and "given_name" in provider_data:
                extra_fields["first_name"] = provider_data["given_name"]
            if not extra_fields.get("last_name") and "family_name" in provider_data:
                extra_fields["last_name"] = provider_data["family_name"]
            if not extra_fields.get("avatar") and "picture" in provider_data:
                extra_fields["avatar"] = provider_data["picture"]

        return self.create_user(
            email=email, password=None, is_oauth_user=True, **extra_fields
        )

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a superuser with the given email and password.

        Args:
            email: Superuser email
            password: Superuser password
            **extra_fields: Additional user fields

        Returns:
            User instance

        Raises:
            ValidationException: If superuser requirements not met
        """
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

        if not password:
            raise ValidationException(
                detail=_("Superuser must have a password"),
                field_errors={"password": "Password is required for superuser"},
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
            InvalidCredentialsException: If credentials are invalid
        """
        try:
            user = self.get_by_email(email)
        except UserNotFoundException:
            # Don't reveal whether email exists for security
            raise InvalidCredentialsException()

        if not user.check_password(password):
            raise InvalidCredentialsException()

        return user

    def verified_users(self):
        """Get only users with verified emails."""
        return self.filter(is_email_verified=True, is_active=True)

    def unverified_users(self):
        """Get users with unverified emails."""
        return self.filter(is_email_verified=False, is_active=True)

    def admins(self):
        """Get all admin users."""
        from core.constants import UserRole

        return self.filter(
            role__in=[UserRole.ADMIN, UserRole.SUPERADMIN], is_active=True
        )

    def moderators_and_above(self):
        """Get moderators, admins, and superadmins."""
        from core.constants import UserRole

        return self.filter(
            role__in=[UserRole.MODERATOR, UserRole.ADMIN, UserRole.SUPERADMIN],
            is_active=True,
        )

    def with_profiles(self):
        """Optimize query to include user profiles."""
        return self.select_related("profile")


# ================================================================
# USER PROFILE MANAGER
# ================================================================


class UserProfileManager(models.Manager):
    """
    Custom manager for UserProfile with optimizations and business logic.
    """

    def get_queryset(self):
        """Optimize default queryset with select_related."""
        return super().get_queryset().select_related("user")

    def get_by_user_id(self, user_id):
        """
        Get profile by user ID with proper error handling.

        Args:
            user_id: User ID

        Returns:
            UserProfile instance

        Raises:
            UserNotFoundException: If profile doesn't exist
        """
        try:
            return self.get(user_id=user_id)
        except self.model.DoesNotExist:
            raise UserNotFoundException(
                detail=_("User profile not found"), extra_data={"user_id": user_id}
            )

    def get_by_user_email(self, email):
        """
        Get profile by user email.

        Args:
            email: User email address

        Returns:
            UserProfile instance

        Raises:
            UserNotFoundException: If profile doesn't exist
        """
        try:
            return self.get(user__email=email, user__is_active=True)
        except self.model.DoesNotExist:
            raise UserNotFoundException(
                detail=_("User profile not found"), extra_data={"email": email}
            )

    def public_profiles(self):
        """Get only public profiles."""
        return self.filter(
            privacy_level=PrivacyLevel.PUBLIC, is_active=True, user__is_active=True
        )

    def private_profiles(self):
        """Get only private profiles."""
        return self.filter(
            privacy_level=PrivacyLevel.PRIVATE, is_active=True, user__is_active=True
        )
