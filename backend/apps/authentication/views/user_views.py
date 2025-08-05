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
    ProfileOnlyUpdateSerializer,
    UserProfileSerializer,
    UserProfileUpdateSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)


class UserProfileView(APIView):
    """
    User profile management endpoint - Get and Update profile.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    @extend_schema(
        operation_id="auth_profile_get",
        summary="Get User Profile",
        description="Retrieve current user's profile information"
        " including user data and profile settings.",
        tags=["Authentication"],
        responses={
            200: {
                "description": "Profile retrieved successfully",
                "example": {
                    "success": True,
                    "message": "Profile retrieved successfully",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "data": {
                        "id": 1,
                        "email": "user@example.com",
                        "first_name": "John",
                        "last_name": "Doe",
                        "full_name": "John Doe",
                        "avatar_url": "https://ui-avatars.com/api/?name=JD",
                        "is_email_verified": True,
                        "profile": {
                            "bio": "Software developer passionate about movies",
                            "location": "San Francisco, CA",
                            "timezone": "America/Los_Angeles",
                            "preferred_language": "en",
                            "privacy_level": "public",
                            "theme_preference": "dark",
                        },
                    },
                },
            },
            401: {
                "description": "Authentication required",
                "example": {
                    "success": False,
                    "message": "Authentication credentials were not provided",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
        },
    )
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

    @extend_schema(
        operation_id="auth_profile_update",
        summary="Update User Profile",
        description="Update user profile information. Supports both "
        "user fields and profile fields in one request.",
        tags=["Authentication"],
        request=UserProfileUpdateSerializer,
        responses={
            200: {
                "description": "Profile updated successfully",
                "example": {
                    "success": True,
                    "message": "Profile updated successfully",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "data": {
                        "id": 1,
                        "email": "user@example.com",
                        "first_name": "John",
                        "last_name": "Doe",
                        "profile": {"bio": "Updated bio", "location": "New York, NY"},
                    },
                },
            },
            400: {
                "description": "Validation errors",
                "example": {
                    "success": False,
                    "message": "Profile data is invalid",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "errors": {
                        "field_errors": {
                            "bio": ["Biography must be at least 10 characters long"],
                            "phone_number": ["Invalid phone number format"],
                        }
                    },
                },
            },
        },
        examples=[
            OpenApiExample(
                "Profile Update Request",
                summary="Update profile information",
                description="Update both user and profile fields",
                value={
                    "first_name": "John",
                    "last_name": "Doe",
                    "phone_number": "+1234567890",
                    "bio": "Software developer passionate about movies",
                    "location": "San Francisco, CA",
                    "timezone": "America/Los_Angeles",
                    "privacy_level": "public",
                    "theme_preference": "dark",
                },
                request_only=True,
            )
        ],
    )
    def put(self, request):
        """Full profile update."""
        return self._update_profile(request, partial=False)

    @extend_schema(
        operation_id="auth_profile_partial_update",
        summary="Partial Update User Profile",
        description="Partially update user profile information."
        " Only provided fields will be updated.",
        tags=["Authentication"],
        request=UserProfileUpdateSerializer,
        responses={
            200: {"description": "Profile updated successfully"},
            400: {"description": "Validation errors"},
        },
    )
    def patch(self, request):
        """Partial profile update."""
        return self._update_profile(request, partial=True)

    def _update_profile(self, request, partial=False):
        """Handle profile updates (full or partial)."""
        try:
            user = request.user

            # Validate using serializer
            serializer = UserProfileUpdateSerializer(data=request.data)

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message=_("Profile data is invalid"),
                    field_errors=serializer.errors,
                )

            # Update using serializer
            updated_user, updated_profile = serializer.save(user)

            # Serialize updated data
            user_serializer = UserSerializer(updated_user)
            profile_serializer = UserProfileSerializer(updated_profile)

            response_data = {
                **user_serializer.data,
                "profile": profile_serializer.data,
            }

            logger.info(f"Profile updated for user: {user.email}")

            return APIResponse.updated(
                message=_("Profile updated successfully"), data=response_data
            )

        except Exception as e:
            logger.error(f"Profile update error for {request.user.email}: {str(e)}")
            return APIResponse.server_error(message=_("Failed to update profile"))


class UserProfileUpdateView(APIView):
    """
    Separate profile update endpoint for profile fields only.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    serializer_class = ProfileOnlyUpdateSerializer

    @extend_schema(
        operation_id="auth_profile_only_update",
        summary="Update Profile Fields Only",
        description="Update only profile-specific fields "
        "(bio, location, preferences, etc.)",
        tags=["Authentication"],
        request=ProfileOnlyUpdateSerializer,
        responses={
            200: {
                "description": "Profile updated successfully",
                "example": {
                    "success": True,
                    "message": "Profile updated successfully",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "data": {
                        "profile": {
                            "bio": "Updated bio",
                            "location": "New Location",
                            "timezone": "America/New_York",
                            "privacy_level": "private",
                        }
                    },
                },
            },
            400: {"description": "Validation errors"},
        },
    )
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
            profile_serializer = self.serializer_class(
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
            response_data = ProfileOnlyUpdateSerializer(updated_profile).data

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
