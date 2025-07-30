"""
Custom managers for User and UserProfile models.
Provides optimized queries and business logic methods.
"""

from django.contrib.auth.models import BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.constants import PrivacyLevel


class UserManager(BaseUserManager):
    """
    Custom user manager for email-based authentication.
    """

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user with the given email and password."""
        if not email:
            raise ValueError(_("The Email field must be set"))

        email = self.normalize_email(email)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with the given email and password."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_email_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True"))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True"))

        return self.create_user(email, password, **extra_fields)

    def get_by_email(self, email):
        """Get user by email."""
        return self.get(email=email, is_active=True)

    def verified_users(self):
        """Get only users with verified emails."""
        return self.filter(is_email_verified=True, is_active=True)


class UserProfileManager(models.Manager):
    """
    Custom manager for UserProfile.
    """

    def get_queryset(self):
        """Optimize default queryset with select_related."""
        return super().get_queryset().select_related("user")

    def public_profiles(self):
        """Get only public profiles."""
        return self.filter(
            privacy_level=PrivacyLevel.PUBLIC, is_active=True, user__is_active=True
        )
