"""
Favorites API Views with Essential OpenAPI Documentation.
Handles user favorites, watchlist, ratings, and analytics.
"""

import logging

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.core.cache import cache
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

from apps.favorites.models import Favorite
from apps.favorites.serializers import (
    FavoriteCreateByTMDbSerializer,
    FavoriteCreateSerializer,
    FavoriteListSerializer,
    FavoriteSerializer,
    FavoriteToggleSerializer,
    FavoriteUpdateSerializer,
    UserFavoriteStatsSerializer,
    WatchlistSerializer,
)
from apps.favorites.services import FavoriteService
from core.exceptions import (
    MovieNotFoundException,
    NotFoundException,
    ValidationException,
)
from core.responses import APIResponse

logger = logging.getLogger(__name__)


class FavoriteListView(APIView):
    """List user's favorites with filtering and search."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List user favorites",
        description="Get current user's favorite movies with optional filtering and search.",
        parameters=[
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Search within user's favorites by movie title or notes",
                examples=[
                    OpenApiExample("Movie Title", value="batman"),
                    OpenApiExample("Notes Search", value="rewatch"),
                ],
            ),
            OpenApiParameter(
                name="rating_min",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Minimum user rating (1-10)",
                examples=[
                    OpenApiExample("Highly Rated", value=8),
                    OpenApiExample("Good Movies", value=7),
                ],
            ),
            OpenApiParameter(
                name="is_watchlist",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by watchlist status",
                examples=[
                    OpenApiExample("Watchlist Only", value=True),
                    OpenApiExample("Non-Watchlist", value=False),
                ],
            ),
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Page number (default: 1)",
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Items per page (default: 20, max: 50)",
            ),
        ],
        responses={
            200: FavoriteListSerializer(many=True),
            401: None,
            500: None,
        },
        tags=["Favorites - User"],
    )
    def get(self, request) -> Response:
        """List user's favorites with filtering."""
        try:
            user = request.user

            # Get query parameters
            search = request.query_params.get("search", "").strip()
            rating_min = request.query_params.get("rating_min")
            is_watchlist = request.query_params.get("is_watchlist")
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 50)

            # Build base queryset
            queryset = Favorite.objects.for_user(user)

            # Apply search
            if search:
                if len(search) < 2:
                    return APIResponse.validation_error(
                        message="Search query must be at least 2 characters long"
                    )
                try:
                    result = FavoriteService.search_user_favorites(user, search)
                    return APIResponse.success(
                        message=f"Found {result['count']} favorites matching '{search}'",
                        data=result,
                    )
                except ValidationException as e:
                    return APIResponse.validation_error(
                        message=str(e.detail), field_errors=e.field_errors
                    )

            # Apply filters
            if rating_min:
                try:
                    rating_min = int(rating_min)
                    if 1 <= rating_min <= 10:
                        queryset = queryset.filter(user_rating__gte=rating_min)
                except ValueError:
                    pass

            if is_watchlist is not None:
                is_watchlist_bool = is_watchlist.lower() == "true"
                queryset = queryset.filter(is_watchlist=is_watchlist_bool)

            # Order by last interaction
            queryset = queryset.order_by("-last_interaction", "-first_favorited")

            # Paginate
            paginator = Paginator(queryset, page_size)

            try:
                favorites_page = paginator.page(page)
            except PageNotAnInteger:
                favorites_page = paginator.page(1)
            except EmptyPage:
                return APIResponse.success(
                    message=f"Page {page} is out of range",
                    data={
                        "results": [],
                        "pagination": {
                            "page": page,
                            "page_size": page_size,
                            "total_pages": paginator.num_pages,
                            "total_results": paginator.count,
                            "has_next": False,
                            "has_previous": page > 1,
                        },
                    },
                )

            # Serialize
            serializer = FavoriteListSerializer(
                favorites_page, many=True, context={"request": request}
            )

            response_data = {
                "results": serializer.data,
                "pagination": {
                    "page": favorites_page.number,
                    "page_size": page_size,
                    "total_pages": paginator.num_pages,
                    "total_results": paginator.count,
                    "has_next": favorites_page.has_next(),
                    "has_previous": favorites_page.has_previous(),
                },
            }

            return APIResponse.success(
                message=f"Retrieved {len(serializer.data)} favorites",
                data=response_data,
            )

        except Exception as e:
            logger.error(f"Error in favorites list for user {request.user.id}: {e}")
            return APIResponse.server_error(message="Failed to retrieve favorites")


class FavoriteDetailView(APIView):
    """Get specific favorite details."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get favorite details",
        description="Get detailed information about a specific favorite.",
        responses={
            200: FavoriteSerializer,
            401: None,
            403: None,
            404: None,
            500: None,
        },
        tags=["Favorites - User"],
    )
    def get(self, request, pk: int) -> Response:
        """Get favorite details."""
        try:
            try:
                favorite = Favorite.objects.get(
                    pk=pk, user=request.user, is_active=True
                )
            except Favorite.DoesNotExist:
                return APIResponse.not_found(message="Favorite not found")

            serializer = FavoriteSerializer(favorite, context={"request": request})

            return APIResponse.success(
                message="Favorite details retrieved successfully", data=serializer.data
            )

        except Exception as e:
            logger.error(f"Error retrieving favorite {pk}: {e}")
            return APIResponse.server_error(message="Failed to retrieve favorite")


class FavoriteCreateView(APIView):
    """Add movie to favorites."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Add movie to favorites",
        description="Add a movie to user's favorites with optional rating and notes.",
        request=FavoriteCreateSerializer,
        responses={
            201: FavoriteSerializer,
            400: None,
            401: None,
            404: None,
            409: None,
            500: None,
        },
        tags=["Favorites - User"],
    )
    def post(self, request) -> Response:
        """Add movie to favorites."""
        try:
            movie_id = request.data.get("movie")

            if not movie_id:
                return APIResponse.validation_error(
                    message="Movie ID is required",
                    field_errors={"movie": ["This field is required."]},
                )

            # Extract additional data
            user_rating = request.data.get("user_rating")
            notes = request.data.get("notes", "")
            is_watchlist = request.data.get("is_watchlist", False)
            recommendation_source = request.data.get("recommendation_source")

            try:
                result = FavoriteService.add_favorite(
                    user=request.user,
                    movie_id=movie_id,
                    user_rating=user_rating,
                    notes=notes,
                    is_watchlist=is_watchlist,
                    recommendation_source=recommendation_source,
                )

                return APIResponse.created(
                    message=result["message"], data=result["favorite"]
                )

            except ValidationException as e:
                return APIResponse.validation_error(
                    message=str(e.detail), field_errors=e.field_errors
                )
            except Exception as e:
                logger.error(f"Service error adding favorite: {e}")
                return APIResponse.server_error(message="Failed to add favorite")

        except Exception as e:
            logger.error(f"Error in favorite create view: {e}")
            return APIResponse.server_error(message="Failed to add favorite")


class FavoriteCreateByTMDbView(APIView):
    """Add movie to favorites using TMDb ID."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Add movie to favorites by TMDb ID",
        description="Add a movie to user's favorites using TMDb ID. Creates movie in database if it doesn't exist.",
        request=FavoriteCreateByTMDbSerializer,
        responses={
            201: FavoriteSerializer,
            400: None,
            401: None,
            404: None,
            409: None,
            500: None,
        },
        examples=[
            OpenApiExample(
                "Add Batman Begins",
                value={
                    "tmdb_id": "1892",
                    "user_rating": 8,
                    "notes": "Great origin story!",
                    "is_watchlist": False,
                },
            ),
            OpenApiExample(
                "Add to Watchlist", value={"tmdb_id": "550", "is_watchlist": True}
            ),
            OpenApiExample("Simple Add", value={"tmdb_id": "27205"}),
        ],
        tags=["Favorites - User"],
    )
    def post(self, request) -> Response:
        """Add movie to favorites by TMDb ID."""
        try:
            serializer = FavoriteCreateByTMDbSerializer(
                data=request.data, context={"request": request}
            )

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message="Invalid data provided", field_errors=serializer.errors
                )

            # Extract validated data
            tmdb_id = serializer.validated_data["tmdb_id"]
            user_rating = serializer.validated_data.get("user_rating")
            notes = serializer.validated_data.get("notes", "")
            is_watchlist = serializer.validated_data.get("is_watchlist", False)
            recommendation_source = serializer.validated_data.get(
                "recommendation_source"
            )

            try:
                result = FavoriteService.add_favorite_by_tmdb_id(
                    user=request.user,
                    tmdb_id=tmdb_id,
                    user_rating=user_rating,
                    notes=notes,
                    is_watchlist=is_watchlist,
                    recommendation_source=recommendation_source,
                )

                return APIResponse.created(
                    message=result["message"], data=result["favorite"]
                )

            except ValidationException as e:
                return APIResponse.validation_error(
                    message=str(e.detail), field_errors=e.field_errors
                )
            except MovieNotFoundException as e:
                return APIResponse.not_found(message=str(e.detail))

        except Exception as e:
            logger.error(f"Error in favorite create by TMDb view: {e}")
            return APIResponse.server_error(message="Failed to add favorite")


class FavoriteUpdateView(APIView):
    """Update existing favorite."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Update favorite",
        description="Update rating, notes, or watchlist status of existing favorite.",
        request=FavoriteUpdateSerializer,
        responses={
            200: FavoriteSerializer,
            400: None,
            401: None,
            403: None,
            404: None,
            500: None,
        },
        tags=["Favorites - User"],
    )
    def patch(self, request, pk: int) -> Response:
        """Update favorite."""
        try:
            try:
                favorite = Favorite.objects.get(
                    pk=pk, user=request.user, is_active=True
                )
            except Favorite.DoesNotExist:
                return APIResponse.not_found(message="Favorite not found")

            movie_id = favorite.movie.id

            try:
                result = FavoriteService.update_favorite(
                    user=request.user, movie_id=movie_id, **request.data
                )

                return APIResponse.updated(
                    message=result["message"], data=result["favorite"]
                )

            except ValidationException as e:
                return APIResponse.validation_error(
                    message=str(e.detail), field_errors=e.field_errors
                )
            except NotFoundException as e:
                return APIResponse.not_found(message=str(e.detail))

        except Exception as e:
            logger.error(f"Error updating favorite {pk}: {e}")
            return APIResponse.server_error(message="Failed to update favorite")


class FavoriteDeleteView(APIView):
    """Remove movie from favorites."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Remove from favorites",
        description="Remove a movie from user's favorites.",
        responses={
            204: None,
            401: None,
            403: None,
            404: None,
            500: None,
        },
        tags=["Favorites - User"],
    )
    def delete(self, request, pk: int) -> Response:
        """Remove from favorites."""
        try:
            try:
                favorite = Favorite.objects.get(
                    pk=pk, user=request.user, is_active=True
                )
            except Favorite.DoesNotExist:
                return APIResponse.not_found(message="Favorite not found")

            movie_id = favorite.movie.id
            movie_title = favorite.movie.title

            try:
                result = FavoriteService.remove_favorite(
                    user=request.user, movie_id=movie_id
                )

                return APIResponse.success(message=result["message"])

            except NotFoundException as e:
                return APIResponse.not_found(message=str(e.detail))

        except Exception as e:
            logger.error(f"Error deleting favorite {pk}: {e}")
            return APIResponse.server_error(message="Failed to remove favorite")


class FavoriteToggleView(APIView):
    """Toggle favorite status (add/remove)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Toggle favorite status",
        description="Add movie to favorites if not favorited, remove if already favorited.",
        request=FavoriteToggleSerializer,
        responses={
            200: FavoriteToggleSerializer,
            400: None,
            401: None,
            404: None,
            500: None,
        },
        tags=["Favorites - User"],
    )
    def post(self, request) -> Response:
        """Toggle favorite status."""
        try:
            serializer = FavoriteToggleSerializer(
                data=request.data, context={"request": request}
            )

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message="Invalid data provided", field_errors=serializer.errors
                )

            movie_id = serializer.validated_data["movie_id"]

            try:
                result = FavoriteService.toggle_favorite(
                    user=request.user, movie_id=movie_id
                )

                return APIResponse.success(
                    message=result["message"],
                    data={
                        "movie_id": movie_id,
                        "is_favorited": result["is_favorited"],
                        "message": result["message"],
                    },
                )

            except ValidationException as e:
                return APIResponse.validation_error(
                    message=str(e.detail), field_errors=e.field_errors
                )
            except Exception as e:
                logger.error(f"Service error toggling favorite: {e}")
                return APIResponse.server_error(message="Failed to toggle favorite")

        except Exception as e:
            logger.error(f"Error in toggle favorite view: {e}")
            return APIResponse.server_error(message="Failed to toggle favorite")


class UserWatchlistView(APIView):
    """Get user's watchlist."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get user watchlist",
        description="Get current user's watchlist (movies they want to watch).",
        parameters=[
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Page number (default: 1)",
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Items per page (default: 20, max: 50)",
            ),
        ],
        responses={
            200: WatchlistSerializer(many=True),
            401: None,
            500: None,
        },
        tags=["Favorites - Watchlist"],
    )
    def get(self, request) -> Response:
        """Get user's watchlist."""
        try:
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 50)

            try:
                result = FavoriteService.get_user_watchlist(
                    user=request.user, limit=page_size * page  # Simple limit for now
                )

                # Simple pagination (you might want to implement proper pagination)
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                paginated_watchlist = result["watchlist"][start_idx:end_idx]

                response_data = {
                    "results": paginated_watchlist,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_results": result["count"],
                        "has_next": end_idx < result["count"],
                        "has_previous": page > 1,
                    },
                }

                return APIResponse.success(
                    message=f"Retrieved {len(paginated_watchlist)} watchlist items",
                    data=response_data,
                )

            except Exception as e:
                logger.error(f"Service error getting watchlist: {e}")
                return APIResponse.server_error(message="Failed to get watchlist")

        except Exception as e:
            logger.error(f"Error in watchlist view: {e}")
            return APIResponse.server_error(message="Failed to retrieve watchlist")


class WatchlistAddView(APIView):
    """Add movie to watchlist."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Add to watchlist",
        description="Add a movie to user's watchlist.",
        request={"movie_id": OpenApiTypes.INT},
        responses={
            201: WatchlistSerializer,
            400: None,
            401: None,
            404: None,
            409: None,
            500: None,
        },
        tags=["Favorites - Watchlist"],
    )
    def post(self, request) -> Response:
        """Add movie to watchlist."""
        try:
            movie_id = request.data.get("movie_id")

            if not movie_id:
                return APIResponse.validation_error(
                    message="Movie ID is required",
                    field_errors={"movie_id": ["This field is required."]},
                )

            try:
                result = FavoriteService.add_to_watchlist(
                    user=request.user, movie_id=movie_id
                )

                return APIResponse.created(
                    message=result["message"], data=result["favorite"]
                )

            except ValidationException as e:
                return APIResponse.validation_error(
                    message=str(e.detail), field_errors=e.field_errors
                )
            except Exception as e:
                logger.error(f"Service error adding to watchlist: {e}")
                return APIResponse.server_error(message="Failed to add to watchlist")

        except Exception as e:
            logger.error(f"Error in watchlist add view: {e}")
            return APIResponse.server_error(message="Failed to add to watchlist")


class WatchlistRemoveView(APIView):
    """Remove movie from watchlist."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Remove from watchlist",
        description="Remove a movie from user's watchlist.",
        request={"movie_id": OpenApiTypes.INT},
        responses={
            200: None,
            400: None,
            401: None,
            404: None,
            500: None,
        },
        tags=["Favorites - Watchlist"],
    )
    def post(self, request) -> Response:
        """Remove movie from watchlist."""
        try:
            movie_id = request.data.get("movie_id")

            if not movie_id:
                return APIResponse.validation_error(
                    message="Movie ID is required",
                    field_errors={"movie_id": ["This field is required."]},
                )

            try:
                result = FavoriteService.remove_from_watchlist(
                    user=request.user, movie_id=movie_id
                )

                return APIResponse.success(message=result["message"])

            except NotFoundException as e:
                return APIResponse.not_found(message=str(e.detail))
            except Exception as e:
                logger.error(f"Service error removing from watchlist: {e}")
                return APIResponse.server_error(
                    message="Failed to remove from watchlist"
                )

        except Exception as e:
            logger.error(f"Error in watchlist remove view: {e}")
            return APIResponse.server_error(message="Failed to remove from watchlist")


class UserFavoriteStatsView(APIView):
    """Get user's favorite statistics."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get user favorite statistics",
        description="Get comprehensive statistics about user's favorite activity.",
        parameters=[
            OpenApiParameter(
                name="no_cache",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Bypass cache and get fresh data (default: true)",
                examples=[
                    OpenApiExample("Bypass Cache (Default)", value=True),
                    OpenApiExample("Use Cache", value=False),
                ],
            ),
        ],
        responses={
            200: UserFavoriteStatsSerializer,
            401: None,
            500: None,
        },
        tags=["Favorites - Analytics"],
    )
    def get(self, request) -> Response:
        """Get user's favorite statistics."""
        try:
            # Check if user wants to use cache (default is to bypass cache)
            no_cache = request.query_params.get("no_cache", "true").lower() == "true"

            if not no_cache:
                # Check cache first
                cache_key = f"user_favorite_stats_{request.user.id}"
                cached_stats = cache.get(cache_key)

                if cached_stats:
                    return APIResponse.success(
                        message="User statistics retrieved (cached)", data=cached_stats
                    )

            try:
                stats = FavoriteService.get_user_stats(user=request.user)

                # Cache for 1 hour (only if not bypassing cache)
                if not no_cache:
                    cache_key = f"user_favorite_stats_{request.user.id}"
                    cache.set(cache_key, stats, 60 * 60)

                return APIResponse.success(
                    message="User statistics retrieved successfully", data=stats
                )

            except Exception as e:
                logger.error(f"Service error getting user stats: {e}")
                return APIResponse.server_error(message="Failed to get user statistics")

        except Exception as e:
            logger.error(f"Error in user stats view: {e}")
            return APIResponse.server_error(message="Failed to retrieve statistics")
