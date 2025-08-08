# ================================================================
# GENRE CRUD VIEWS
# ================================================================

import logging
from typing import Any, Dict

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.movies.models import Genre, Movie
from apps.movies.serializers import (
    GenreCreateSerializer,
    GenreDetailSerializer,
    GenreListSerializer,
    GenreStatsSerializer,
    GenreUpdateSerializer,
    MovieListSerializer,
)
from apps.movies.services import GenreService
from core.permissions import IsAdminUser
from core.responses import APIResponse

logger = logging.getLogger(__name__)

# =========================================================================
# GENRE LIST VIEW
# =========================================================================


class GenreListView(APIView):
    """
    List all movie genres with filtering and statistics.
    Also handles genre creation for convenience.
    """

    permission_classes = [AllowAny]
    genre_service = GenreService()

    @extend_schema(
        summary="List all movie genres",
        description="""
        Get a list of all movie genres with optional filtering and statistics.
        """,
        parameters=[
            OpenApiParameter(
                name="include_stats",
                description="Include statistical information (default: false)",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Basic Info", value=False),
                    OpenApiExample("With Statistics", value=True),
                ],
            ),
            OpenApiParameter(
                name="include_inactive",
                description="Include inactive genres (default: false)",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Active Only", value=False),
                    OpenApiExample("Include All", value=True),
                ],
            ),
            OpenApiParameter(
                name="min_movies",
                description="Minimum number of movies per genre (default: 0)",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Any Count", value=0),
                    OpenApiExample("Popular Genres", value=10),
                    OpenApiExample("Major Genres", value=50),
                ],
            ),
            OpenApiParameter(
                name="sort_by",
                description="Sorting method",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=["name", "popularity", "movie_count"],
                default="popularity",
                required=False,
                examples=[
                    OpenApiExample("Alphabetical", value="name"),
                    OpenApiExample("Most Popular", value="popularity"),
                    OpenApiExample("Most Movies", value="movie_count"),
                ],
            ),
            OpenApiParameter(
                name="force_sync",
                description="Force sync genres from TMDb API (default: false)",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Use Cache", value=False),
                    OpenApiExample("Force Refresh", value=True),
                ],
            ),
        ],
        responses={
            200: GenreListSerializer(many=True),
            500: None,
        },
        tags=["Movies - Genres"],
    )
    def get(self, request):
        """List all genres with filtering and optional statistics."""
        try:
            # Parse parameters
            include_stats = (
                request.query_params.get("include_stats", "false").lower() == "true"
            )
            include_inactive = (
                request.query_params.get("include_inactive", "false").lower() == "true"
            )
            min_movies = max(int(request.query_params.get("min_movies", 0)), 0)
            sort_by = request.query_params.get("sort_by", "popularity")
            force_sync = (
                request.query_params.get("force_sync", "false").lower() == "true"
            )

            # Validate sort_by
            if sort_by not in ["name", "popularity", "movie_count"]:
                return APIResponse.validation_error(
                    message="Invalid sort_by value",
                    field_errors={
                        "sort_by": ["Must be one of: name, popularity, movie_count"]
                    },
                )

            # Check cache first (unless force sync)
            cache_key = (
                f"genres_list_{include_stats}_{include_inactive}_{min_movies}_{sort_by}"
            )
            if not force_sync:
                cached_data = cache.get(cache_key)
                if cached_data:
                    logger.info("Genres list retrieved from cache")
                    return APIResponse.success(
                        message="Genres list (cached)", data=cached_data
                    )

            # Get genres from service
            try:
                genres = self.genre_service.get_all_genres(
                    include_inactive=include_inactive
                )

                # Auto-sync if no genres found
                if not genres and not include_inactive:
                    logger.info("No genres found, attempting auto-sync from TMDb")
                    try:
                        synced_genres = self.genre_service.sync_genres_from_tmdb()
                        if synced_genres:
                            genres = synced_genres
                            logger.info(
                                f"Auto-synced {len(synced_genres)} genres from TMDb"
                            )
                    except Exception as e:
                        logger.warning(f"Auto-sync failed: {e}")
                        # Continue with empty list

                if not genres:
                    return APIResponse.success(
                        message="No genres found",
                        data={
                            "genres": [],
                            "total_count": 0,
                            "metadata": {
                                "include_stats": include_stats,
                                "include_inactive": include_inactive,
                                "min_movies": min_movies,
                                "sort_by": sort_by,
                                "auto_sync_attempted": True,
                                "fetched_at": timezone.now().isoformat(),
                            },
                        },
                    )

                # Apply movie count filter and calculate stats
                filtered_genres = []
                for genre in genres:
                    # Calculate movie count
                    movie_count = genre.movies.filter(is_active=True).count()

                    # Apply min_movies filter
                    if movie_count >= min_movies:
                        # Store movie_count as temporary attribute (not model field)
                        setattr(genre, "_movie_count", movie_count)
                        filtered_genres.append(genre)

                # Apply sorting
                if sort_by == "name":
                    filtered_genres.sort(key=lambda g: g.name.lower())
                elif sort_by == "movie_count":
                    filtered_genres.sort(
                        key=lambda g: getattr(g, "_movie_count", 0), reverse=True
                    )
                else:  # popularity - sort by movie count as proxy
                    filtered_genres.sort(
                        key=lambda g: getattr(g, "_movie_count", 0), reverse=True
                    )

                # Serialize genres
                if include_stats:
                    serializer = GenreStatsSerializer(filtered_genres, many=True)
                else:
                    serializer = GenreListSerializer(filtered_genres, many=True)

                # Build response data
                response_data = {
                    "genres": serializer.data,
                    "total_count": len(filtered_genres),
                    "metadata": {
                        "include_stats": include_stats,
                        "include_inactive": include_inactive,
                        "min_movies": min_movies,
                        "sort_by": sort_by,
                        "filters_applied": min_movies > 0,
                        "fetched_at": timezone.now().isoformat(),
                    },
                }

                # Cache for 1 hour (genres don't change often)
                cache.set(cache_key, response_data, 60 * 60)

                logger.info(f"Retrieved {len(filtered_genres)} genres")

                return APIResponse.success(
                    message=f"Found {len(filtered_genres)} genres", data=response_data
                )

            except Exception as e:
                logger.error(f"Failed to get genres: {e}")
                return APIResponse.server_error(
                    message="Failed to retrieve genres",
                    extra_data={"error_type": "retrieval_failed"},
                )

        except ValueError as e:
            return APIResponse.validation_error(
                message="Invalid parameter value", field_errors={"parameter": [str(e)]}
            )
        except Exception as e:
            logger.error(f"Genres list error: {e}")
            return APIResponse.server_error(message="Failed to get genres list")

    @extend_schema(
        summary="Create new movie genre",
        description="""
        Create a new movie genre for content categorization.

        **Admin Only**: This operation requires admin privileges.
        """,
        request=GenreCreateSerializer,
        responses={
            201: GenreDetailSerializer,
            400: None,
            401: None,
            403: None,
            500: None,
        },
        tags=["Movies - Genres"],
    )
    def post(self, request):
        """Create new genre - convenience method."""
        # Check if user is admin for POST operations
        if not request.user.is_authenticated:
            return APIResponse.unauthorized(
                message="Authentication required for genre creation"
            )

        if not (request.user.is_staff or request.user.is_superuser):
            return APIResponse.forbidden(
                message="Admin access required for genre creation"
            )

        try:
            serializer = GenreCreateSerializer(
                data=request.data, context={"request": request}
            )

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message="Invalid genre data", field_errors=serializer.errors
                )

            # Create genre within transaction
            try:
                with transaction.atomic():
                    genre = serializer.save()

                    # Clear genre caches
                    self._clear_genre_caches()

                    # Serialize response
                    response_serializer = GenreDetailSerializer(genre)

                    logger.info(f"Created new genre: {genre.name}")

                    return APIResponse.created(
                        message=f"Successfully created genre: {genre.name}",
                        data=response_serializer.data,
                    )

            except Exception as e:
                logger.error(f"Failed to create genre: {e}")
                return APIResponse.server_error(
                    message="Failed to create genre",
                    extra_data={"error_type": "creation_failed"},
                )

        except Exception as e:
            logger.error(f"Genre create error: {e}")
            return APIResponse.server_error(message="Failed to create genre")

    def _clear_genre_caches(self):
        """Clear all genre-related caches."""
        try:
            cache.delete_pattern("genres_list_*")
            cache.delete_pattern("genre_detail_*")
            cache.delete_pattern("genre_movies_*")
            logger.debug("Cleared genre caches")
        except Exception as e:
            logger.warning(f"Failed to clear genre caches: {e}")


# =========================================================================
# GENRE CREATE VIEW
# =========================================================================


class GenreCreateView(APIView):
    """
    Create a new movie genre.
    """

    permission_classes = [IsAuthenticated, IsAdminUser]
    genre_service = GenreService()

    @extend_schema(
        summary="Create new movie genre",
        description="""
        Create a new movie genre for content categorization.

        **Admin Only**: This operation requires admin privileges.
        """,
        request=GenreCreateSerializer,
        responses={
            201: GenreDetailSerializer,
            400: None,
            401: None,
            403: None,
            500: None,
        },
        tags=["Movies - Genres"],
    )
    def post(self, request):
        """Create new genre with validation."""
        try:
            serializer = GenreCreateSerializer(
                data=request.data, context={"request": request}
            )

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message="Invalid genre data", field_errors=serializer.errors
                )

            # Create genre within transaction
            try:
                with transaction.atomic():
                    genre = serializer.save()

                    # Clear genre caches
                    self._clear_genre_caches()

                    # Serialize response
                    response_serializer = GenreDetailSerializer(genre)

                    logger.info(f"Created new genre: {genre.name}")

                    return APIResponse.created(
                        message=f"Successfully created genre: {genre.name}",
                        data=response_serializer.data,
                    )

            except Exception as e:
                logger.error(f"Failed to create genre: {e}")
                return APIResponse.server_error(
                    message="Failed to create genre",
                    extra_data={"error_type": "creation_failed"},
                )

        except Exception as e:
            logger.error(f"Genre create error: {e}")
            return APIResponse.server_error(message="Failed to create genre")

    def _clear_genre_caches(self):
        """Clear all genre-related caches."""
        try:
            cache.delete_pattern("genres_list_*")
            cache.delete_pattern("genre_detail_*")
            cache.delete_pattern("genre_movies_*")
            logger.debug("Cleared genre caches")
        except Exception as e:
            logger.warning(f"Failed to clear genre caches: {e}")


# =========================================================================
# GENRE DETAIL VIEW
# =========================================================================


class GenreDetailView(APIView):
    """
    Get detailed information about a specific genre.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Get genre details",
        description="""
        Get detailed information about a specific genre including statistics.

        **Response Details:**
        - Genre information (name, slug, TMDb ID)
        - Movie counts and averages
        - Sample of popular movies
        - Sample of recent movies
        - Creation and update timestamps
        """,
        responses={
            200: GenreDetailSerializer,
            404: None,
            500: None,
        },
        tags=["Movies - Genres"],
    )
    def get(self, request, pk):
        """Get genre details with statistics."""
        try:
            # Check cache first
            cache_key = f"genre_detail_{pk}"
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Genre details for ID {pk} retrieved from cache")
                return APIResponse.success(
                    message="Genre details (cached)", data=cached_data
                )

            # Get genre - try both database ID and TMDb ID
            genre = None
            try:
                genre = Genre.objects.get(pk=pk, is_active=True)
                logger.info(f"Genre found by database ID: {genre.name}")
            except Genre.DoesNotExist:
                try:
                    genre = Genre.objects.get(tmdb_id=pk, is_active=True)
                    logger.info(f"Genre found by TMDb ID: {genre.name}")
                except Genre.DoesNotExist:
                    return APIResponse.not_found(
                        message=f"Genre with ID {pk} not found",
                        extra_data={
                            "searched_id": pk,
                            "suggestions": [
                                "Check the genre ID is correct",
                                "Use /api/v1/movies/genres/ to see available genres",
                                "Genre might be inactive",
                            ],
                        },
                    )

            # Serialize genre with detailed information
            serializer = GenreDetailSerializer(
                genre,
                context={
                    "request": request,
                    "popular_movies_limit": 10,
                    "recent_movies_limit": 10,
                },
            )

            # Cache for 2 hours (genre details change infrequently)
            cache.set(cache_key, serializer.data, 60 * 60 * 2)

            logger.info(f"Retrieved details for genre: {genre.name}")

            return APIResponse.success(
                message=f"Genre details: {genre.name}", data=serializer.data
            )

        except Exception as e:
            logger.error(f"Genre detail error: {e}")
            return APIResponse.server_error(message="Failed to get genre details")


# =========================================================================
# GENRE UPDATE VIEW
# =========================================================================


class GenreUpdateView(APIView):
    """
    Update an existing movie genre.
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary="Update movie genre",
        description="""
        Update properties of an existing movie genre.

        **Admin Only**: This operation requires admin privileges.

        **Updatable Fields:**
        - Genre name (with uniqueness validation)
        - Slug (with uniqueness validation)
        - Active status

        **Validation:**
        - Name uniqueness (excluding current genre)
        - Slug uniqueness (excluding current genre)
        - Name length validation (minimum 2 characters)
        """,
        request=GenreUpdateSerializer,
        responses={
            200: GenreDetailSerializer,
            400: None,
            401: None,
            403: None,
            404: None,
            500: None,
        },
        tags=["Movies - Genres"],
    )
    def patch(self, request, pk):
        """Update genre with validation."""
        try:
            # Get genre - try both database ID and TMDb ID
            genre = None
            try:
                genre = Genre.objects.get(pk=pk, is_active=True)
            except Genre.DoesNotExist:
                try:
                    genre = Genre.objects.get(tmdb_id=pk, is_active=True)
                except Genre.DoesNotExist:
                    return APIResponse.not_found(
                        message=f"Genre with ID {pk} not found",
                        extra_data={"searched_id": pk},
                    )

            # Validate update data
            serializer = GenreUpdateSerializer(
                genre, data=request.data, partial=True, context={"request": request}
            )

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message="Invalid update data", field_errors=serializer.errors
                )

            # Update within transaction
            try:
                with transaction.atomic():
                    updated_genre = serializer.save()

                    # Clear related caches
                    self._clear_genre_caches(updated_genre.id)

                    # Serialize response
                    response_serializer = GenreDetailSerializer(updated_genre)

                    logger.info(f"Updated genre: {updated_genre.name}")

                    return APIResponse.updated(
                        message=f"Successfully updated genre: {updated_genre.name}",
                        data=response_serializer.data,
                    )

            except Exception as e:
                logger.error(f"Failed to update genre {pk}: {e}")
                return APIResponse.server_error(
                    message="Failed to update genre", extra_data={"genre_id": pk}
                )

        except Exception as e:
            logger.error(f"Genre update error: {e}")
            return APIResponse.server_error(message="Failed to update genre")

    def _clear_genre_caches(self, genre_id: int):
        """Clear caches related to genre."""
        try:
            cache.delete_many(
                [
                    f"genre_detail_{genre_id}",
                    f"genre_movies_{genre_id}",
                ]
            )
            cache.delete_pattern("genres_list_*")
            logger.debug(f"Cleared caches for genre {genre_id}")
        except Exception as e:
            logger.warning(f"Failed to clear genre caches: {e}")


# =========================================================================
# GENRE DELETE VIEW
# =========================================================================


class GenreDeleteView(APIView):
    """
    Delete (deactivate) a movie genre.
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary="Delete movie genre",
        description="""
        Soft delete (deactivate) a movie genre.

        **Admin Only**: This operation requires admin privileges.
        """,
        responses={
            204: None,
            400: None,
            401: None,
            403: None,
            404: None,
            500: None,
        },
        tags=["Movies - Genres"],
    )
    def delete(self, request, pk):
        """Soft delete genre with safety checks."""
        try:
            # Get genre - try both database ID and TMDb ID
            genre = None
            try:
                genre = Genre.objects.get(pk=pk, is_active=True)
            except Genre.DoesNotExist:
                try:
                    genre = Genre.objects.get(tmdb_id=pk, is_active=True)
                except Genre.DoesNotExist:
                    return APIResponse.not_found(
                        message=f"Genre with ID {pk} not found",
                        extra_data={"searched_id": pk},
                    )

            # Safety check - prevent deletion of popular genres
            movie_count = genre.movies.filter(is_active=True).count()
            if movie_count > 100:  # Configurable threshold
                return APIResponse.validation_error(
                    message="Cannot delete genre with many movies",
                    field_errors={
                        "movies": [
                            f"This genre has {movie_count} movies. "
                            "Consider reassigning movies before deletion."
                        ]
                    },
                )

            # Delete within transaction
            try:
                with transaction.atomic():
                    genre_name = genre.name
                    genre_id = genre.id

                    # Soft delete (mark as inactive)
                    genre.is_active = False
                    genre.save(update_fields=["is_active"])

                    # Clear related caches
                    self._clear_genre_caches(genre_id)

                    logger.info(f"Deleted genre: {genre_name}")

                    return APIResponse.deleted(
                        message=f"Successfully deleted genre: {genre_name}"
                    )

            except Exception as e:
                logger.error(f"Failed to delete genre {pk}: {e}")
                return APIResponse.server_error(
                    message="Failed to delete genre", extra_data={"genre_id": pk}
                )

        except Exception as e:
            logger.error(f"Genre delete error: {e}")
            return APIResponse.server_error(message="Failed to delete genre")

    def _clear_genre_caches(self, genre_id: int):
        """Clear caches related to genre."""
        try:
            cache.delete_many(
                [
                    f"genre_detail_{genre_id}",
                    f"genre_movies_{genre_id}",
                ]
            )
            cache.delete_pattern("genres_list_*")
            logger.debug(f"Cleared caches for genre {genre_id}")
        except Exception as e:
            logger.warning(f"Failed to clear genre caches: {e}")


class GenreMoviesView(APIView):
    """Get movies by genre with clean filtering."""

    permission_classes = [AllowAny]
    genre_service = GenreService()

    @extend_schema(
        summary="Get movies by genre",
        description="Get all movies for a specific genre with filtering and pagination",
        parameters=[
            OpenApiParameter(
                "page", OpenApiTypes.INT, description="Page number (default: 1)"
            ),
            OpenApiParameter(
                "page_size",
                OpenApiTypes.INT,
                description="Items per page (default: 20, max: 100)",
            ),
            OpenApiParameter(
                "min_rating",
                OpenApiTypes.NUMBER,
                description="Minimum rating 0-10 (default: 0)",
            ),
            OpenApiParameter(
                "min_votes",
                OpenApiTypes.INT,
                description="Minimum vote count (default: 0)",
            ),
            OpenApiParameter(
                "year_from", OpenApiTypes.INT, description="Minimum release year"
            ),
            OpenApiParameter(
                "year_to", OpenApiTypes.INT, description="Maximum release year"
            ),
            OpenApiParameter(
                "sort_by",
                OpenApiTypes.STR,
                description="Sort by: popularity, rating, release_date, title",
            ),
            OpenApiParameter("order", OpenApiTypes.STR, description="Order: asc, desc"),
            OpenApiParameter(
                "force_sync",
                OpenApiTypes.BOOL,
                description="Skip cache (default: false)",
            ),
        ],
        responses={200: MovieListSerializer(many=True)},
        tags=["Movies - Genres"],
    )
    def get(self, request, pk):
        """Get movies by genre with filtering."""
        try:
            # Parse and validate parameters
            params = self._parse_parameters(request)
            if isinstance(params, Response):  # Validation error
                return params

            # Check cache first (unless force_sync)
            if not params["force_sync"]:
                cache_key = self._build_cache_key(pk, params)
                cached_data = cache.get(cache_key)
                if cached_data:
                    return APIResponse.success("Genre movies (cached)", cached_data)

            # Get genre
            genre = self._get_genre(pk)
            if isinstance(genre, Response):
                return genre

            # Get filtered movies
            response_data = self._get_filtered_movies(genre, params)

            # Cache the response (2 hours)
            if not params["force_sync"]:
                cache_key = self._build_cache_key(pk, params)
                cache.set(cache_key, response_data, 60 * 60 * 2)

            # Build success message
            total = response_data["pagination"]["total_results"]
            showing = len(response_data["movies"])
            message = f"Found {total} {genre.name} movies (showing {showing})"

            return APIResponse.success(message, response_data)

        except Exception as e:
            logger.error(f"Genre movies error: {e}")
            return APIResponse.server_error("Failed to get genre movies")

    def _parse_parameters(self, request) -> Dict[str, Any]:
        """Parse and validate all parameters."""
        try:
            # Basic pagination
            page = max(int(request.query_params.get("page", 1)), 1)
            page_size = min(max(int(request.query_params.get("page_size", 20)), 1), 100)

            # Rating filters
            min_rating = float(request.query_params.get("min_rating", 0.0))
            if min_rating < 0.0 or min_rating > 10.0:
                return APIResponse.validation_error(
                    "Invalid min_rating",
                    {"min_rating": ["Must be between 0.0 and 10.0"]},
                )

            min_votes = max(int(request.query_params.get("min_votes", 0)), 0)

            # Year filters
            year_from = request.query_params.get("year_from")
            year_to = request.query_params.get("year_to")

            if year_from:
                year_from = int(year_from)
                if year_from < 1888 or year_from > 2030:
                    return APIResponse.validation_error(
                        "Invalid year_from",
                        {"year_from": ["Must be between 1888 and 2030"]},
                    )

            if year_to:
                year_to = int(year_to)
                if year_to < 1888 or year_to > 2030:
                    return APIResponse.validation_error(
                        "Invalid year_to",
                        {"year_to": ["Must be between 1888 and 2030"]},
                    )

            if year_from and year_to and year_from > year_to:
                return APIResponse.validation_error(
                    "Invalid year range", {"year_to": ["Must be >= year_from"]}
                )

            # Sorting
            sort_by = request.query_params.get("sort_by", "popularity")
            if sort_by not in ["popularity", "rating", "release_date", "title"]:
                return APIResponse.validation_error(
                    "Invalid sort_by",
                    {"sort_by": ["Must be: popularity, rating, release_date, title"]},
                )

            order = request.query_params.get("order", "desc")
            if order not in ["asc", "desc"]:
                return APIResponse.validation_error(
                    "Invalid order", {"order": ["Must be 'asc' or 'desc'"]}
                )

            force_sync = (
                request.query_params.get("force_sync", "false").lower() == "true"
            )

            return {
                "page": page,
                "page_size": page_size,
                "min_rating": min_rating,
                "min_votes": min_votes,
                "year_from": year_from,
                "year_to": year_to,
                "sort_by": sort_by,
                "order": order,
                "force_sync": force_sync,
            }

        except ValueError as e:
            return APIResponse.validation_error(
                "Invalid parameter", {"error": [str(e)]}
            )

    def _get_genre(self, pk) -> Genre:
        """Get genre by ID or TMDb ID."""
        # Try database ID first
        try:
            genre = Genre.objects.get(pk=pk, is_active=True)
            logger.info(f"Genre found by DB ID: {genre.name}")
            return genre
        except (Genre.DoesNotExist, ValueError):
            pass

        # Try TMDb ID
        try:
            genre = Genre.objects.get(tmdb_id=pk, is_active=True)
            logger.info(f"Genre found by TMDb ID: {genre.name}")
            return genre
        except (Genre.DoesNotExist, ValueError):
            pass

        return APIResponse.not_found(
            f"Genre with ID {pk} not found",
            {
                "searched_id": pk,
                "suggestion": "Use /api/v1/movies/genres/ to see available genres",
            },
        )

    def _get_filtered_movies(
        self, genre: Genre, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get movies with all filters applied."""
        # Start with base queryset
        queryset = (
            Movie.objects.filter(
                movie_genres__genre=genre,  # 🔥 FIX: Use correct relationship
                is_active=True,
            )
            .select_related()
            .prefetch_related("movie_genres__genre")
            .distinct()
        )

        # Apply rating filter
        if params["min_rating"] > 0:
            queryset = queryset.filter(vote_average__gte=params["min_rating"])

        # Apply vote count filter
        if params["min_votes"] > 0:
            queryset = queryset.filter(vote_count__gte=params["min_votes"])

        # Apply year filters
        if params["year_from"]:
            queryset = queryset.filter(release_date__year__gte=params["year_from"])

        if params["year_to"]:
            queryset = queryset.filter(release_date__year__lte=params["year_to"])

        # Apply sorting
        sort_field = {
            "popularity": "popularity",
            "rating": "vote_average",
            "release_date": "release_date",
            "title": "title",
        }[params["sort_by"]]

        if params["order"] == "desc":
            sort_field = f"-{sort_field}"

        queryset = queryset.order_by(sort_field, "-popularity")

        # Get total count
        total_count = queryset.count()

        # Apply pagination
        start = (params["page"] - 1) * params["page_size"]
        end = start + params["page_size"]
        page_movies = queryset[start:end]

        # Serialize movies
        movies_data = []
        for movie in page_movies:
            movie_data = {
                "id": movie.id,
                "tmdb_id": movie.tmdb_id,
                "title": movie.title,
                "original_title": movie.original_title,
                "overview": movie.overview[:200] + "..."
                if len(movie.overview) > 200
                else movie.overview,
                "release_date": movie.release_date.isoformat()
                if movie.release_date
                else None,
                "release_year": movie.release_year,
                "popularity": movie.popularity,
                "vote_average": movie.vote_average,
                "vote_count": movie.vote_count,
                "rating_stars": movie.rating_stars,
                "original_language": movie.original_language,
                "poster_path": movie.poster_path,
                "poster_url": movie.get_poster_url() if movie.poster_path else None,
                "backdrop_path": movie.backdrop_path,
                "backdrop_url": movie.get_backdrop_url()
                if movie.backdrop_path
                else None,
                "tmdb_url": movie.tmdb_url,
                "imdb_url": movie.imdb_url,
                "genres": movie.genre_names,
                "primary_genre": movie.primary_genre.name
                if movie.primary_genre
                else None,
                "main_trailer_url": movie.main_trailer_url,
                "sync_status": movie.sync_status,
                "is_local": True,
            }
            movies_data.append(movie_data)

        # Build response
        return {
            "genre": {
                "id": genre.id,
                "tmdb_id": genre.tmdb_id,
                "name": genre.name,
                "slug": genre.slug,
            },
            "movies": movies_data,
            "pagination": {
                "page": params["page"],
                "page_size": params["page_size"],
                "total_pages": (total_count + params["page_size"] - 1)
                // params["page_size"],
                "total_results": total_count,
                "has_next": end < total_count,
                "has_previous": params["page"] > 1,
                "next_page": params["page"] + 1 if end < total_count else None,
                "previous_page": params["page"] - 1 if params["page"] > 1 else None,
            },
            "filters_applied": {
                "min_rating": params["min_rating"],
                "min_votes": params["min_votes"],
                "year_from": params["year_from"],
                "year_to": params["year_to"],
                "sort_by": params["sort_by"],
                "order": params["order"],
            },
            "data_source": "Local Database",
            "fetched_at": timezone.now().isoformat(),
        }

    def _build_cache_key(self, pk: int, params: Dict[str, Any]) -> str:
        """Build cache key from parameters."""
        import hashlib

        key_parts = [
            str(pk),
            str(params["page"]),
            str(params["page_size"]),
            str(params["min_rating"]),
            str(params["min_votes"]),
            str(params["year_from"]) if params["year_from"] else "",
            str(params["year_to"]) if params["year_to"] else "",
            params["sort_by"],
            params["order"],
        ]
        key_string = "|".join(key_parts)
        hash_key = hashlib.md5(key_string.encode()).hexdigest()[:8]
        return f"genre_movies:{hash_key}"
