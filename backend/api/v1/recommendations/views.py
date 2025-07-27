"""
Recommendation engine API views.
Handles personalized recommendations, similar movies, trending suggestions, etc.
"""
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from ..base import SuccessResponse


class PersonalizedRecommendationsView(APIView):
    """
    Personalized recommendations endpoint.
    GET /api/v1/recommendations/
    """

    permission_classes = [IsAuthenticated]  # Requires user login for personalization

    def get(self, request):
        return SuccessResponse.create(
            "Personalized recommendations endpoint - to be implemented",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )


class TrendingRecommendationsView(APIView):
    """
    Trending recommendations endpoint.
    GET /api/v1/recommendations/trending/
    """

    permission_classes = [AllowAny]  # Can be public

    def get(self, request):
        return SuccessResponse.create(
            "Trending recommendations endpoint - to be implemented",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )


class DiscoveryRecommendationsView(APIView):
    """
    Discovery recommendations endpoint.
    GET /api/v1/recommendations/discover/
    """

    permission_classes = [IsAuthenticated]  # Better with user context

    def get(self, request):
        return SuccessResponse.create(
            "Discovery recommendations endpoint - to be implemented",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )
