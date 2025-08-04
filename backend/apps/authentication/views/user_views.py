"""
User profile management views for Movie Nexus.
Handles user profile retrieval, updates, and password changes.
"""

import logging

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from django.utils.translation import gettext_lazy as _

from core.exceptions import AuthenticationException, ValidationException
from core.responses import APIResponse

from ..serializers import (
    PasswordChangeSerializer,
    UserProfileSerializer,
    UserSerializer,
)
from ..services import update_user_profile

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
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    serializer_class = PasswordChangeSerializer

    @extend_schema(
        operation_id="auth_password_change",
        summary="Change Password",
        description=(
            "Change the authenticated user's password. "
            "Requires current password verification.",
        ),
        tags=["Authentication"],
        request=PasswordChangeSerializer,
        responses={
            200: {
                "description": "Password changed successfully",
                "example": {
                    "success": True,
                    "message": "Password changed successfully",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
            400: {
                "description": "Validation errors",
                "example": {
                    "success": False,
                    "message": "Password change data is invalid",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "errors": {
                        "field_errors": {
                            "current_password": ["Current password is incorrect"],
                            "new_password": ["Password too weak"],
                            "new_password_confirm": [
                                "Password confirmation does not match"
                            ],
                        }
                    },
                },
            },
            401: {
                "description": "Authentication required or current password incorrect",
                "example": {
                    "success": False,
                    "message": "Current password is incorrect",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
            429: {"description": "Rate limit exceeded"},
        },
        examples=[
            OpenApiExample(
                "Password Change Request",
                summary="Change user password",
                description=(
                    "Standard password change with current password verification",
                ),
                value={
                    "current_password": "oldPassword123!",
                    "new_password": "newSecurePassword456!",
                    "new_password_confirm": "newSecurePassword456!",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        """Handle password change with serializer validation."""
        try:
            # Initialize serializer with user context
            serializer = self.serializer_class(
                data=request.data, context={"user": request.user, "request": request}
            )

            # Validate input data
            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message=_("Password change data is invalid"),
                    field_errors=serializer.errors,
                )

            # Change password using serializer
            try:
                serializer.save()

                logger.info(
                    f"Password changed successfully for user: {request.user.email}"
                )

                return APIResponse.success(message=_("Password changed successfully"))

            except AuthenticationException as e:
                logger.warning(
                    f"Invalid current password attempt for user: {request.user.email}"
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
