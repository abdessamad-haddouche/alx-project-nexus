# ================================================================
# GENRE CRUD VIEWS WITH COMPLETE DOCUMENTATION
# ================================================================

import logging

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
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

        **Data Strategy:**
        1. Check local database for genres first
        2. Auto-sync popular genres from TMDb if database is empty
        3. Apply filtering and sorting options
        4. Cache results for optimal performance

        **Features:**
        - Complete genre metadata (name, slug, TMDb ID)
        - Movie count per genre
        - Optional statistical information
        - Popularity-based sorting
        - Active/inactive filtering
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

        This is a convenience endpoint that does the same as /genres/create/
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

        **Features:**
        - Automatic slug generation from name
        - TMDb ID validation and uniqueness checking
        - Name uniqueness validation
        - Auto-activation of new genres

        **Validation Rules:**
        - Genre name must be unique (case-insensitive)
        - TMDb ID must be unique if provided
        - Slug auto-generated if not provided
        - Name must be at least 2 characters

        **Use Cases:**
        - Admin content management
        - Custom genre creation
        - TMDb sync operations
        - Content categorization setup
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

        **Features:**
        - Complete genre metadata
        - Movie count and statistics
        - Popular movies preview
        - Recent movies preview
        - Performance metrics

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

        **Soft Delete Behavior:**
        - Genre is marked as inactive (not permanently deleted)
        - Movie-genre relationships are preserved
        - Can be reactivated if needed
        - Maintains data integrity and audit trails

        **Business Impact:**
        - Movies lose this genre classification
        - Genre no longer appears in lists
        - Related caches are invalidated
        - Movie recommendations may be affected

        **Safety Measures:**
        - Prevents deletion of genres with many movies (configurable)
        - Maintains referential integrity
        - Preserves historical data
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

    # =========================================================================
    # GENRE BY SLUG VIEW
    # =========================================================================

    """
    Get genre information by slug for SEO-friendly URLs.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Get genre by slug",
        description="""
        Get genre information using SEO-friendly slug instead of ID.

        **SEO Benefits:**
        - Human-readable URLs (/genres/action/ instead of /genres/28/)
        - Better search engine indexing
        - User-friendly navigation
        - Consistent URL structure

        **Features:**
        - Same detailed information as genre detail view
        - Automatic slug-based lookup
        - Cache optimization for popular genres
        - Redirect handling for slug changes

        **URL Examples:**
        - /api/v1/movies/genres/action/
        - /api/v1/movies/genres/science-fiction/
        - /api/v1/movies/genres/romantic-comedy/
        """,
        responses={
            200: GenreDetailSerializer,
            404: None,
            500: None,
        },
        tags=["Movies - Genres"],
    )
    def get(self, request, slug):
        """Get genre by slug."""
        try:
            # Check cache first
            cache_key = f"genre_slug_{slug}"
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Genre with slug '{slug}' retrieved from cache")
                return APIResponse.success(
                    message="Genre details (cached)", data=cached_data
                )

            # Get genre by slug
            try:
                genre = Genre.objects.get(slug=slug, is_active=True)
            except Genre.DoesNotExist:
                return APIResponse.not_found(
                    message=f"Genre with slug '{slug}' not found",
                    extra_data={
                        "searched_slug": slug,
                        "suggestions": [
                            "Check the slug is correct",
                            "Use /api/v1/movies/genres/ to see available genres",
                            "Slug might have changed",
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

            # Cache for 4 hours (slug-based access is often for SEO)
            cache.set(cache_key, serializer.data, 60 * 60 * 4)

            logger.info(f"Retrieved genre by slug: {genre.name} ({slug})")

            return APIResponse.success(
                message=f"Genre: {genre.name}", data=serializer.data
            )

        except Exception as e:
            logger.error(f"Genre by slug error: {e}")
            return APIResponse.server_error(message="Failed to get genre by slug")


class GenreMoviesView(APIView):
    """
    Get all movies for a specific genre with intelligent database/TMDb fallback.
    """

    permission_classes = [AllowAny]
    genre_service = GenreService()

    @extend_schema(
        summary="Get movies by genre",
        description="""
        Get all movies associated with a specific genre with intelligent
          fallback strategy.

        **Data Strategy:**
        1. Check local database for genre and associated movies
        2. If genre not found locally, sync from TMDb API
        3. Apply smart filtering and quality controls
        4. Cache results for optimal performance
        5. Support pagination and advanced filtering

        **Discovery Features:**
        - Quality filtering (minimum rating, vote count)
        - Release year range filtering
        - Popularity-based sorting
        - Adult content filtering
        - Language preferences

        **Performance Optimizations:**
        - Smart caching (2 hours for stable genre data)
        - Efficient database queries with select_related
        - Pagination to handle large result sets
        - CDN-ready poster URLs

        **Use Cases:**
        - Genre landing pages (Browse Action movies)
        - Category-based movie discovery
        - Filtered browsing experiences
        - Content recommendation engines
        - SEO-friendly genre pages
        """,
        parameters=[
            OpenApiParameter(
                name="page",
                description="Page number (default: 1)",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("First Page", value=1),
                    OpenApiExample("Second Page", value=2),
                    OpenApiExample("Page 5", value=5),
                ],
            ),
            OpenApiParameter(
                name="page_size",
                description="Movies per page (default: 20, max: 100)",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Default", value=20),
                    OpenApiExample("More Results", value=50),
                    OpenApiExample("Maximum", value=100),
                ],
            ),
            OpenApiParameter(
                name="min_rating",
                description="Minimum vote average (default: 0.0)",
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Any Rating", value=0.0),
                    OpenApiExample("Good Movies", value=6.0),
                    OpenApiExample("Great Movies", value=7.5),
                    OpenApiExample("Masterpieces", value=8.5),
                ],
            ),
            OpenApiParameter(
                name="min_votes",
                description="Minimum vote count for reliability (default: 10)",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Any Votes", value=0),
                    OpenApiExample("Reliable", value=50),
                    OpenApiExample("Very Reliable", value=500),
                ],
            ),
            OpenApiParameter(
                name="year_from",
                description="Minimum release year",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("2000s+", value=2000),
                    OpenApiExample("2010s+", value=2010),
                    OpenApiExample("Recent", value=2020),
                ],
            ),
            OpenApiParameter(
                name="year_to",
                description="Maximum release year",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Up to 2020", value=2020),
                    OpenApiExample("Up to 2015", value=2015),
                    OpenApiExample("Classics", value=2000),
                ],
            ),
            OpenApiParameter(
                name="include_adult",
                description="Include adult content (default: false)",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Family Friendly", value=False),
                    OpenApiExample("Include Adult", value=True),
                ],
            ),
            OpenApiParameter(
                name="sort_by",
                description="Sorting method",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=["popularity", "rating", "release_date", "title"],
                default="popularity",
                required=False,
                examples=[
                    OpenApiExample("Most Popular", value="popularity"),
                    OpenApiExample("Highest Rated", value="rating"),
                    OpenApiExample("Newest First", value="release_date"),
                    OpenApiExample("Alphabetical", value="title"),
                ],
            ),
            OpenApiParameter(
                name="order",
                description="Sort order",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=["asc", "desc"],
                default="desc",
                required=False,
                examples=[
                    OpenApiExample("Descending", value="desc"),
                    OpenApiExample("Ascending", value="asc"),
                ],
            ),
            OpenApiParameter(
                name="force_sync",
                description="Force sync genre from TMDb API (default: false)",
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
            200: MovieListSerializer(many=True),
            404: None,
            400: None,
            500: None,
        },
        tags=["Movies - Genre Management"],
    )
    def get(self, request, pk):
        """Get movies by genre with intelligent database/TMDb fallback."""
        try:
            # Parse and validate parameters
            page = max(int(request.query_params.get("page", 1)), 1)
            page_size = min(max(int(request.query_params.get("page_size", 20)), 1), 100)
            min_rating = max(float(request.query_params.get("min_rating", 0.0)), 0.0)
            min_votes = max(int(request.query_params.get("min_votes", 10)), 0)
            year_from = request.query_params.get("year_from")
            year_to = request.query_params.get("year_to")
            include_adult = (
                request.query_params.get("include_adult", "false").lower() == "true"
            )
            sort_by = request.query_params.get("sort_by", "popularity")
            order = request.query_params.get("order", "desc")
            force_sync = (
                request.query_params.get("force_sync", "false").lower() == "true"
            )

            # Validate parameters
            if min_rating > 10.0:
                return APIResponse.validation_error(
                    message="Invalid minimum rating",
                    field_errors={"min_rating": ["Must be between 0.0 and 10.0"]},
                )

            if year_from and (int(year_from) < 1888 or int(year_from) > 2030):
                return APIResponse.validation_error(
                    message="Invalid year_from",
                    field_errors={"year_from": ["Must be between 1888 and 2030"]},
                )

            if year_to and (int(year_to) < 1888 or int(year_to) > 2030):
                return APIResponse.validation_error(
                    message="Invalid year_to",
                    field_errors={"year_to": ["Must be between 1888 and 2030"]},
                )

            if sort_by not in ["popularity", "rating", "release_date", "title"]:
                return APIResponse.validation_error(
                    message="Invalid sort_by value",
                    field_errors={
                        "sort_by": [
                            "Must be one of: popularity, rating, release_date, title"
                        ]
                    },
                )

            if order not in ["asc", "desc"]:
                return APIResponse.validation_error(
                    message="Invalid order value",
                    field_errors={"order": ["Must be 'asc' or 'desc'"]},
                )

            # Check cache first (unless force sync)
            cache_key = (
                f"genre_movies_{pk}_{page}_{page_size}_{min_rating}_"
                f"{min_votes}_{year_from}_{year_to}_{include_adult}_"
                f"{sort_by}_{order}"
            )
            if not force_sync:
                cached_data = cache.get(cache_key)
                if cached_data:
                    logger.info(f"Genre movies for ID {pk} retrieved from cache")
                    return APIResponse.success(
                        message="Genre movies (cached)", data=cached_data
                    )

            # Step 1: Try to get genre from local database
            try:
                genre = Genre.objects.get(pk=pk, is_active=True)
                logger.info(f"Genre found in database: {genre.name}")
            except Genre.DoesNotExist:
                # Step 2: Try by tmdb_id
                try:
                    genre = Genre.objects.get(tmdb_id=pk, is_active=True)
                    logger.info(f"Genre found by TMDb ID: {genre.name}")
                except Genre.DoesNotExist:
                    # Step 3: Try to sync genre from TMDb
                    logger.info(f"Genre with ID {pk} not found locally")
                    return APIResponse.not_found(
                        message=f"Genre with ID {pk} not found",
                        extra_data={
                            "searched_id": pk,
                            "suggestions": [
                                "Verify the genre ID is correct",
                                "Check available genres with /api/v1/movies/genres/",
                                "Genre might not be synced from TMDb yet",
                            ],
                        },
                    )

            # Step 4: Get movies for this genre with filtering
            try:
                # Build the base queryset
                movies_queryset = Movie.objects.filter(
                    genres=genre, is_active=True
                ).distinct()

                # Apply filters
                filters = {}

                # Rating filter
                if min_rating > 0:
                    filters["vote_average__gte"] = min_rating

                # Vote count filter
                if min_votes > 0:
                    filters["vote_count__gte"] = min_votes

                # Adult content filter
                if not include_adult:
                    filters["adult"] = False

                # Year filters
                if year_from:
                    filters["release_date__year__gte"] = int(year_from)

                if year_to:
                    filters["release_date__year__lte"] = int(year_to)

                # Apply filters
                if filters:
                    movies_queryset = movies_queryset.filter(**filters)

                # Apply sorting
                sort_fields = {
                    "popularity": "popularity",
                    "rating": "vote_average",
                    "release_date": "release_date",
                    "title": "title",
                }

                sort_field = sort_fields[sort_by]
                if order == "desc":
                    sort_field = f"-{sort_field}"

                movies_queryset = movies_queryset.order_by(sort_field, "-popularity")

                # Get total count before pagination
                total_count = movies_queryset.count()

                # Apply pagination
                start_index = (page - 1) * page_size
                end_index = start_index + page_size
                page_movies = movies_queryset[start_index:end_index]

                # Serialize movies
                serializer = MovieListSerializer(
                    page_movies, many=True, context={"request": request}
                )

                # Build response data
                response_data = {
                    "genre": {
                        "id": genre.id,
                        "tmdb_id": genre.tmdb_id,
                        "name": genre.name,
                        "slug": genre.slug,
                    },
                    "movies": serializer.data,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_pages": (total_count + page_size - 1) // page_size,
                        "total_results": total_count,
                        "has_next": end_index < total_count,
                        "has_previous": page > 1,
                        "next_page": page + 1 if end_index < total_count else None,
                        "previous_page": page - 1 if page > 1 else None,
                    },
                    "filters_applied": {
                        "min_rating": min_rating,
                        "min_votes": min_votes,
                        "year_from": year_from,
                        "year_to": year_to,
                        "include_adult": include_adult,
                        "sort_by": sort_by,
                        "order": order,
                    },
                    "data_source": "Local Database",
                    "fetched_at": timezone.now().isoformat(),
                }

                # Cache for 2 hours (genre movie lists change moderately)
                cache.set(cache_key, response_data, 60 * 60 * 2)

                logger.info(
                    f"Retrieved {len(serializer.data)} movies for genre {genre.name}"
                )

                return APIResponse.success(
                    message=f"Found {total_count} {genre.name} movies "
                    f"(showing {len(serializer.data)})",
                    data=response_data,
                )

            except Exception as e:
                logger.error(f"Failed to get movies for genre {genre.name}: {e}")
                return APIResponse.server_error(
                    message="Genre movies temporarily unavailable",
                    extra_data={"genre_name": genre.name},
                )

        except ValueError as e:
            return APIResponse.validation_error(
                message="Invalid parameter value", field_errors={"parameter": [str(e)]}
            )
        except Exception as e:
            logger.error(f"Genre movies error: {e}")
            return APIResponse.server_error(message="Failed to get genre movies")
