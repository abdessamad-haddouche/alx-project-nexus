"""
Essential user management services for Movie Nexus.
"""

import logging
from typing import Dict, Optional

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

# Fixed imports
from apps.authentication.models import User, VerificationToken
from core.constants import VerificationType
from core.exceptions import AuthenticationException, ValidationException

from ..models import Profile

logger = logging.getLogger(__name__)


class UserService:
    """
    Essential user management service.
    Handles user registration, email verification, profile updates, and password
    changes.
    """

    @staticmethod
    @transaction.atomic
    def create_user_account(
        email: str, password: str, first_name: str, last_name: str, **extra_fields
    ) -> Dict:
        """
        Complete user registration flow.
        Creates user, profile, and verification token.

        Args:
            email: User email address
            password: User password
            first_name: User first name
            last_name: User last name
            **extra_fields: Additional user fields (phone_number, date_of_birth, etc.)

        Returns:
            Dict containing user, profile, verification_token, and status

        Raises:
            ValidationException: If data validation fails
        """
        try:
            # Normalize and validate email
            email = email.lower().strip()
            first_name = first_name.strip()
            last_name = last_name.strip()

            # Basic validation
            if not email or not password or not first_name or not last_name:
                raise ValidationException(
                    detail=_("Email, password, first name, and last name are required")
                )

            # Check if user already exists
            if User.objects.filter(email=email).exists():
                raise ValidationException(
                    detail=_("User with this email already exists"),
                    field_errors={"email": "This email is already registered"},
                )

            # Validate password strength
            try:
                validate_password(password)
            except ValidationError as e:
                raise ValidationException(
                    detail=_("Password does not meet requirements"),
                    field_errors={"password": str(e)},
                )

            # Create user
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                **extra_fields,
            )

            # Create user profile - FIXED: Use Profile instead of UserProfile
            profile = Profile.objects.create(user=user)

            # Create email verification token
            verification_token = VerificationToken.objects.create(
                user=user,
                email=user.email,
                verification_type=VerificationType.REGISTRATION,
            )

            logger.info(f"User account created successfully: {email}")

            return {
                "user": user,
                "profile": profile,
                "verification_token": verification_token,
                "created": True,
                "message": _(
                    "Account created successfully. Please check your email for "
                    "verification."
                ),
            }

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Failed to create user account for {email}: {str(e)}")
            raise ValidationException(detail=_("Failed to create user account"))

    @staticmethod
    @transaction.atomic
    def verify_user_email(token: str) -> Dict:
        """
        Email verification processing.
        Validates token and marks user email as verified.

        Args:
            token: Email verification token

        Returns:
            Dict containing user and verification status

        Raises:
            ValidationException: If token is invalid or expired
        """
        try:
            # Get and validate verification token
            try:
                verification = VerificationToken.objects.get(
                    token=token,
                    verification_type=VerificationType.REGISTRATION,
                    is_active=True,
                    is_used=False,
                )
            except VerificationToken.DoesNotExist:
                raise ValidationException(detail=_("Invalid verification token"))

            # Check if token is expired
            if verification.is_expired:
                raise ValidationException(detail=_("Verification token has expired"))

            # Get user
            user = verification.user

            # Check if already verified
            if user.is_email_verified:
                logger.warning(
                    f"Attempted to verify already verified user: {user.email}"
                )
                return {
                    "user": user,
                    "verified": True,
                    "already_verified": True,
                    "message": _("Email is already verified"),
                }

            # Mark verification as used
            verification.verify()

            # Mark user email as verified
            user.verify_email()

            logger.info(f"Email verified successfully for user: {user.email}")

            return {
                "user": user,
                "verified": True,
                "already_verified": False,
                "message": _("Email verified successfully"),
            }

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Email verification failed for token {token}: {str(e)}")
            raise ValidationException(detail=_("Email verification failed"))

    @staticmethod
    def update_user_profile(user: "User", **profile_data) -> Dict:
        """
        Profile management - update user and profile data.

        Args:
            user: User instance
            **profile_data: Profile fields to update

        Returns:
            Dict containing updated user and profile

        Raises:
            ValidationException: If validation fails
        """
        try:
            updated_fields = []

            # User fields that can be updated
            user_fields = [
                "first_name",
                "last_name",
                "phone_number",
                "date_of_birth",
                "avatar",
            ]

            # Profile fields that can be updated
            profile_fields = [
                "bio",
                "location",
                "timezone",
                "preferred_language",
                "privacy_level",
                "theme_preference",
            ]

            # Update user fields
            for field, value in profile_data.items():
                if field in user_fields and hasattr(user, field):
                    if field in ["first_name", "last_name"] and value:
                        value = value.strip()
                    setattr(user, field, value)
                    updated_fields.append(field)

            # Save user if any user fields were updated
            if any(field in user_fields for field in updated_fields):
                user.save(update_fields=updated_fields + ["updated_at"])

            # Update profile fields
            profile = user.profile
            profile_updated_fields = []

            for field, value in profile_data.items():
                if field in profile_fields and hasattr(profile, field):
                    setattr(profile, field, value)
                    profile_updated_fields.append(field)

            # Save profile if any profile fields were updated
            if profile_updated_fields:
                profile.save(update_fields=profile_updated_fields + ["updated_at"])

            logger.info(f"Profile updated for user: {user.email}")

            return {
                "user": user,
                "profile": profile,
                "updated_fields": updated_fields + profile_updated_fields,
                "message": _("Profile updated successfully"),
            }

        except Exception as e:
            logger.error(f"Failed to update profile for {user.email}: {str(e)}")
            raise ValidationException(detail=_("Failed to update profile"))

    @staticmethod
    @transaction.atomic
    def change_user_password(
        user: "User", current_password: str, new_password: str
    ) -> Dict:
        """
        Secure password updates with validation.

        Args:
            user: User instance
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            Dict containing password change status

        Raises:
            AuthenticationException: If current password is wrong
            ValidationException: If new password is invalid
        """
        try:
            # Verify current password
            if not user.check_password(current_password):
                raise AuthenticationException(_("Current password is incorrect"))

            # Validate new password strength
            try:
                validate_password(new_password, user)
            except ValidationError as e:
                raise ValidationException(
                    detail=_("New password does not meet requirements"),
                    field_errors={"new_password": str(e)},
                )

            # Check if new password is different from current
            if user.check_password(new_password):
                raise ValidationException(
                    detail=_("New password must be different from current password")
                )

            # Set new password
            user.set_password(new_password)
            user.save(update_fields=["password", "updated_at"])

            logger.info(f"Password changed successfully for user: {user.email}")

            return {
                "user": user,
                "password_changed": True,
                "message": _("Password changed successfully"),
            }

        except (AuthenticationException, ValidationException):
            raise
        except Exception as e:
            logger.error(f"Password change failed for {user.email}: {str(e)}")
            raise ValidationException(detail=_("Password change failed"))

    # ================================================================
    # HELPER METHODS
    # ================================================================

    @staticmethod
    def get_user_by_email(email: str) -> Optional["User"]:
        """
        Get user by email address.

        Args:
            email: User email

        Returns:
            User instance or None
        """
        try:
            return User.objects.get(email=email.lower().strip(), is_active=True)
        except User.DoesNotExist:
            return None

    @staticmethod
    def get_user_by_id(user_id: int) -> Optional["User"]:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User instance or None
        """
        try:
            return User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return None

    @staticmethod
    def resend_email_verification(user: "User") -> Dict:
        """
        Resend email verification token.

        Args:
            user: User instance

        Returns:
            Dict containing new verification token

        Raises:
            ValidationException: If user is already verified or rate limited
        """
        try:
            # Check if already verified
            if user.is_email_verified:
                raise ValidationException(detail=_("Email is already verified"))

            # Properly deactivate existing tokens
            existing_tokens = VerificationToken.objects.filter(
                user=user,
                verification_type=VerificationType.REGISTRATION,
                is_active=True,
                is_used=False,
            )

            # Deactivate all existing tokens one by one to ensure proper cleanup
            for token in existing_tokens:
                token.is_active = False
                token.save(update_fields=["is_active", "updated_at"])

            # Create new verification token
            verification_token = VerificationToken.objects.create(
                user=user,
                email=user.email,
                verification_type=VerificationType.REGISTRATION,
            )

            logger.info(f"Email verification resent for user: {user.email}")

            return {
                "user": user,
                "verification_token": verification_token,
                "message": _("Verification email sent"),
            }

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Failed to resend verification for {user.email}: {str(e)}")
            raise ValidationException(detail=_("Failed to resend verification email"))


# ================================================================
# CONVENIENCE FUNCTIONS
# ================================================================


def create_user_account(
    email: str, password: str, first_name: str, last_name: str, **extra_fields
) -> Dict:
    """Convenience function for user registration."""
    return UserService.create_user_account(
        email, password, first_name, last_name, **extra_fields
    )


def verify_user_email(token: str) -> Dict:
    """Convenience function for email verification."""
    return UserService.verify_user_email(token)


def update_user_profile(user: "User", **profile_data) -> Dict:
    """Convenience function for profile updates."""
    return UserService.update_user_profile(user, **profile_data)


def change_user_password(
    user: "User", current_password: str, new_password: str
) -> Dict:
    """Convenience function for password changes."""
    return UserService.change_user_password(user, current_password, new_password)
