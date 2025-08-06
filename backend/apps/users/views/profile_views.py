"""
User profile management views for Movie Nexus.
Handles user profile retrieval and profile-specific updates.
"""

import logging

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from django.utils.translation import gettext_lazy as _

from apps.authentication.serializers import UserSerializer
from core.responses import APIResponse

from ..serializers import (
    ProfileOnlyUpdateSerializer,
    UserProfileSerializer,
    UserProfileUpdateSerializer,
)

logger = logging.getLogger(__name__)


class UserProfileView(APIView):
    """
    User profile management endpoint - Get and Update profile.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    @extend_schema(
        operation_id="user_profile_get",
        summary="Get User Profile",
        description="Retrieve current user's profile information"
        " including user data and profile settings.",
        tags=["User Management"],
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
                from ..models import Profile

                profile = Profile.objects.create(user=user)
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
        operation_id="user_profile_update",
        summary="Update User Profile",
        description="Update user profile information. Supports both "
        "user fields and profile fields in one request.",
        tags=["User Management"],
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
        operation_id="user_profile_partial_update",
        summary="Partial Update User Profile",
        description="Partially update user profile information."
        " Only provided fields will be updated.",
        tags=["User Management"],
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


class ProfileOnlyUpdateView(APIView):
    """
    Profile-only update endpoint for profile fields only.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    serializer_class = ProfileOnlyUpdateSerializer

    @extend_schema(
        operation_id="user_profile_only_update",
        summary="Update Profile Fields Only",
        description="Update only profile-specific fields "
        "(bio, location, preferences, etc.)",
        tags=["User Management"],
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

    @extend_schema(
        operation_id="user_profile_only_partial_update",
        summary="Partial Update Profile Fields Only",
        description="Partially update only profile-specific fields "
        "(bio, location, preferences, etc.). Only provided fields will be updated.",
        tags=["User Management"],
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
            400: {
                "description": "Validation errors",
                "example": {
                    "success": False,
                    "message": "Profile data is invalid",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "errors": {
                        "field_errors": {
                            "bio": ["Biography must be at least 10 characters long"],
                            "timezone": ["Invalid timezone format"],
                        }
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
        examples=[
            OpenApiExample(
                "Partial Profile Update",
                summary="Update specific profile fields",
                description="Update only the fields you want to change",
                value={
                    "bio": "Updated biography text",
                    "location": "New York, NY",
                    "privacy_level": "private",
                },
                request_only=True,
            ),
        ],
    )
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
                from ..models import Profile

                profile = Profile.objects.create(user=user)
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
