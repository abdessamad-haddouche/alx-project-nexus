"""
User favorites and watchlist API views.
Handles favorites, watchlists, ratings, reviews, etc.
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ..base import SuccessResponse


class FavoriteMoviesView(APIView):
    """
    User favorites list endpoint.
    GET /api/v1/favorites/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return SuccessResponse.create(
            "Get favorites list endpoint - to be implemented",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )


class AddToFavoritesView(APIView):
    """
    Add movie to favorites endpoint.
    POST /api/v1/favorites/add/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        return SuccessResponse.create(
            "Add to favorites endpoint - to be implemented",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )


class RemoveFromFavoritesView(APIView):
    """
    Remove movie from favorites endpoint.
    DELETE /api/v1/favorites/remove/<movie_id>/
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request, movie_id):
        return SuccessResponse.create(
            f"Remove movie {movie_id} from favorites endpoint - to be implemented",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )


class BulkFavoritesView(APIView):
    """
    Bulk favorites operations endpoint.
    POST /api/v1/favorites/bulk/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        return SuccessResponse.create(
            "Bulk favorites operations endpoint - to be implemented",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )
