"""
User management API views.
Handles user profiles, preferences, and settings.
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ..base import SuccessResponse


class CurrentUserProfileView(APIView):
    """
    Current user profile endpoint.
    GET /api/v1/users/me/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return SuccessResponse.create(
            "Current user profile endpoint - to be implemented",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )


class UserProfileUpdateView(APIView):
    """
    User profile update endpoint.
    PATCH /api/v1/users/me/profile/
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request):
        return SuccessResponse.create(
            "Profile update endpoint - to be implemented",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )
