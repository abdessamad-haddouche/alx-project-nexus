"""
User profile management views for Movie Nexus.
Handles user profile retrieval, updates, and password changes.
"""

import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from django.utils.translation import gettext_lazy as _

from core.exceptions import AuthenticationException, ValidationException
from core.responses import APIResponse

from ..serializers import UserProfileSerializer, UserSerializer
from ..services import change_user_password, update_user_profile

logger = logging.getLogger(__name__)


class UserProfileView(APIView):
    """
    User profile management endpoint - Get and Update profile.

    GET /api/v1/auth/profile/
    - Returns current user profile data

    PUT /api/v1/auth/profile/
    {
        "first_name": "John",
        "last_name": "Doe",
        "phone_number": "+1234567890",
        "avatar": "https://example.com/avatar.jpg",
        "bio": "Software developer passionate about movies",
        "location": "San Francisco, CA",
        "timezone": "America/Los_Angeles",
        "preferred_language": "en",
        "privacy_level": "public",
        "theme_preference": "dark"
    }

    PATCH /api/v1/auth/profile/
    - Partial updates allowed
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        """Get current user profile."""
        try:
            user = request.user

            # Serialize user data
            user_serializer = UserSerializer(user)
            user_data = user_serializer.data

            # Get profile data
            try:
                profile = user.profile
                profile_serializer = UserProfileSerializer(profile)
                profile_data = profile_serializer.data
            except AttributeError:
                # Profile doesn't exist, create it
                from ..models import UserProfile

                profile = UserProfile.objects.create(user=user)
                profile_serializer = UserProfileSerializer(profile)
                profile_data = profile_serializer.data
                logger.info(f"Profile created for user: {user.email}")

            # Combine user and profile data
            response_data = {**user_data, "profile": profile_data}

            return APIResponse.success(
                message=_("Profile retrieved successfully"), data=response_data
            )

        except Exception as e:
            logger.error(f"Error retrieving profile for {request.user.email}: {str(e)}")
            return APIResponse.server_error(message=_("Failed to retrieve profile"))

    def put(self, request):
        """Full profile update."""
        return self._update_profile(request, partial=False)

    def patch(self, request):
        """Partial profile update."""
        return self._update_profile(request, partial=True)

    def _update_profile(self, request, partial=False):
        """Handle profile updates (full or partial)."""
        try:
            user = request.user

            # Update profile using service
            try:
                result = update_user_profile(user, **request.data)

                # Serialize updated data
                user_serializer = UserSerializer(result["user"])
                profile_serializer = UserProfileSerializer(result["profile"])

                response_data = {
                    **user_serializer.data,
                    "profile": profile_serializer.data,
                }

                logger.info(f"Profile updated for user: {user.email}")

                return APIResponse.updated(
                    message=_("Profile updated successfully"), data=response_data
                )

            except ValidationException as e:
                return APIResponse.validation_error(
                    message=str(e.detail),
                    field_errors=getattr(e, "extra_data", {}).get("field_errors"),
                )

        except Exception as e:
            logger.error(f"Profile update error for {request.user.email}: {str(e)}")
            return APIResponse.server_error(message=_("Failed to update profile"))


class UserProfileUpdateView(APIView):
    """
    Separate profile update endpoint for specific profile fields only.
    Useful when you want to update only profile-specific data.

    PUT/PATCH /api/v1/auth/profile/update/
    {
        "bio": "New bio",
        "location": "New Location",
        "timezone": "America/New_York",
        "preferred_language": "es",
        "privacy_level": "private",
        "theme_preference": "light",
        "notification_preferences": {
            "email_notifications": true,
            "push_notifications": false
        }
    }
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def put(self, request):
        """Full profile update (profile fields only)."""
        return self._update_profile_only(request, partial=False)

    def patch(self, request):
        """Partial profile update (profile fields only)."""
        return self._update_profile_only(request, partial=True)

    def _update_profile_only(self, request, partial=False):
        """Update only profile-specific fields."""
        try:
            user = request.user

            # Get or create profile
            try:
                profile = user.profile
            except AttributeError:
                from ..models import UserProfile

                profile = UserProfile.objects.create(user=user)
                logger.info(f"Profile created for user: {user.email}")

            # Validate profile data
            profile_serializer = UserProfileSerializer(
                profile, data=request.data, partial=partial
            )

            if not profile_serializer.is_valid():
                return APIResponse.validation_error(
                    message=_("Profile data is invalid"),
                    field_errors=profile_serializer.errors,
                )

            # Save profile
            updated_profile = profile_serializer.save()

            # Return updated profile data
            response_data = UserProfileSerializer(updated_profile).data

            logger.info(f"Profile-only update completed for user: {user.email}")

            return APIResponse.updated(
                message=_("Profile updated successfully"),
                data={"profile": response_data},
            )

        except Exception as e:
            logger.error(
                f"Profile-only update error for {request.user.email}: {str(e)}"
            )
            return APIResponse.server_error(message=_("Failed to update profile"))


class PasswordChangeView(APIView):
    """
    Password change endpoint for authenticated users.

    POST /api/v1/auth/password/change/
    {
        "current_password": "current_password_here",
        "new_password": "new_secure_password",
        "new_password_confirm": "new_secure_password"
    }
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request):
        """Handle password change."""
        try:
            user = request.user

            # Validate required fields
            current_password = request.data.get("current_password")
            new_password = request.data.get("new_password")
            new_password_confirm = request.data.get("new_password_confirm")

            if not all([current_password, new_password, new_password_confirm]):
                return APIResponse.validation_error(
                    message=_("All password fields are required"),
                    field_errors={
                        "current_password": _("Current password is required")
                        if not current_password
                        else None,
                        "new_password": _("New password is required")
                        if not new_password
                        else None,
                        "new_password_confirm": _("Password confirmation is required")
                        if not new_password_confirm
                        else None,
                    },
                )

            # Validate password confirmation
            if new_password != new_password_confirm:
                return APIResponse.validation_error(
                    message=_("Password confirmation does not match"),
                    field_errors={
                        "new_password_confirm": _(
                            "Password confirmation does not match"
                        )
                    },
                )

            # Change password using service
            try:
                result = change_user_password(
                    user=user,
                    current_password=current_password,
                    new_password=new_password,
                )

                logger.info(f"Password changed successfully for user: {user.email}")
                logger.info(f"Print result: {result}")

                return APIResponse.success(message=_("Password changed successfully"))

            except AuthenticationException as e:
                logger.warning(
                    f"Invalid current password attempt for user: {user.email}"
                )
                return APIResponse.unauthorized(message=str(e.detail))

            except ValidationException as e:
                return APIResponse.validation_error(
                    message=str(e.detail),
                    field_errors=getattr(e, "extra_data", {}).get("field_errors"),
                )

        except Exception as e:
            logger.error(f"Password change error for {request.user.email}: {str(e)}")
            return APIResponse.server_error(message=_("Failed to change password"))
