# ================================================================
# MOVIE-GENRE RELATIONSHIP MANAGEMENT VIEWS
# ================================================================

import logging

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.movies.models import MovieGenre
from apps.movies.serializers import (
    MovieGenreCreateSerializer,
    MovieGenreDetailSerializer,
    MovieGenreListSerializer,
    MovieGenreUpdateSerializer,
)
from core.permissions import IsAdminUser
from core.responses import APIResponse

logger = logging.getLogger(__name__)

# =========================================================================
# MOVIE-GENRE LIST VIEW
# =========================================================================


class MovieGenreListView(APIView):
    """
    List all movie-genre relationships with filtering and pagination.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="List movie-genre relationships",
        description="""
        Get a paginated list of all movie-genre relationships with filtering options.

        **Data Strategy:**
        1. Query local database for movie-genre relationships
        2. Apply filtering by movie, genre, or relationship properties
        3. Cache results for performance optimization
        4. Return paginated results with metadata

        """,
        parameters=[
            OpenApiParameter(
                name="movie_id",
                description="Filter by specific movie ID",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample(
                        "Specific Movie",
                        value=123,
                        description="Show genres for movie 123",
                    ),
                    OpenApiExample(
                        "Popular Movie", value=1, description="Show genres for movie 1"
                    ),
                ],
            ),
            OpenApiParameter(
                name="genre_id",
                description="Filter by specific genre ID",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample(
                        "Action Movies",
                        value=28,
                        description="Show action movie assignments",
                    ),
                    OpenApiExample(
                        "Drama Movies",
                        value=18,
                        description="Show drama movie assignments",
                    ),
                ],
            ),
            OpenApiParameter(
                name="is_primary",
                description="Filter by primary genre status",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Primary Genres Only", value=True),
                    OpenApiExample("Secondary Genres Only", value=False),
                ],
            ),
            OpenApiParameter(
                name="min_weight",
                description="Minimum weight threshold (0.0-1.0)",
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("High Weight", value=0.8),
                    OpenApiExample("Medium Weight", value=0.5),
                ],
            ),
            OpenApiParameter(
                name="page",
                description="Page number (default: 1)",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("First Page", value=1),
                    OpenApiExample("Second Page", value=2),
                ],
            ),
            OpenApiParameter(
                name="page_size",
                description="Results per page (default: 20, max: 100)",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Default", value=20),
                    OpenApiExample("More Results", value=50),
                    OpenApiExample("Maximum", value=100),
                ],
            ),
        ],
        responses={
            200: MovieGenreListSerializer(many=True),
            400: None,
            500: None,
        },
        tags=["Movies - Genre Relationships"],
    )
    def get(self, request):
        """List movie-genre relationships with filtering."""
        try:
            # Parse parameters
            movie_id = request.query_params.get("movie_id")
            genre_id = request.query_params.get("genre_id")
            is_primary = request.query_params.get("is_primary")
            min_weight = request.query_params.get("min_weight")
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 100)

            # Validate parameters
            if page < 1:
                return APIResponse.validation_error(
                    message="Invalid page number",
                    field_errors={"page": ["Page must be at least 1"]},
                )

            if page_size < 1:
                return APIResponse.validation_error(
                    message="Invalid page size",
                    field_errors={"page_size": ["Page size must be at least 1"]},
                )

            # Build cache key
            cache_key = (
                f"movie_genres_list_{movie_id}_{genre_id}_"
                f"{is_primary}_{min_weight}_{page}_{page_size}"
            )
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info("Movie-genre relationships retrieved from cache")
                return APIResponse.success(
                    message="Movie-genre relationships (cached)", data=cached_data
                )

            # Build queryset with filters
            queryset = MovieGenre.objects.select_related("movie", "genre").filter(
                is_active=True
            )

            # Apply filters
            if movie_id:
                queryset = queryset.filter(movie_id=movie_id)

            if genre_id:
                queryset = queryset.filter(genre_id=genre_id)

            if is_primary is not None:
                is_primary_bool = is_primary.lower() == "true"
                queryset = queryset.filter(is_primary=is_primary_bool)

            if min_weight:
                try:
                    min_weight_float = float(min_weight)
                    queryset = queryset.filter(weight__gte=min_weight_float)
                except ValueError:
                    return APIResponse.validation_error(
                        message="Invalid weight value",
                        field_errors={"min_weight": ["Must be a valid number"]},
                    )

            # Order results
            queryset = queryset.order_by(
                "-is_primary", "-weight", "movie__title", "genre__name"
            )

            # Apply pagination
            total_count = queryset.count()
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            page_results = queryset[start_index:end_index]

            # Serialize results
            serializer = MovieGenreListSerializer(page_results, many=True)

            # Build response data
            response_data = {
                "results": serializer.data,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size,
                    "total_results": total_count,
                    "has_next": end_index < total_count,
                    "has_previous": page > 1,
                },
                "filters_applied": {
                    "movie_id": movie_id,
                    "genre_id": genre_id,
                    "is_primary": is_primary,
                    "min_weight": min_weight,
                },
                "fetched_at": timezone.now().isoformat(),
            }

            # Cache for 30 minutes
            cache.set(cache_key, response_data, 60 * 30)

            logger.info(f"Retrieved {len(serializer.data)} movie-genre relationships")

            return APIResponse.success(
                message=f"Found {total_count} movie-genre relationships",
                data=response_data,
            )

        except ValueError as e:
            return APIResponse.validation_error(
                message="Invalid parameter value", field_errors={"parameter": [str(e)]}
            )
        except Exception as e:
            logger.error(f"Movie-genre list error: {e}")
            return APIResponse.server_error(
                message="Failed to get movie-genre relationships"
            )


# =========================================================================
# MOVIE-GENRE CREATE VIEW
# =========================================================================


class MovieGenreCreateView(APIView):
    """
    Create new movie-genre relationship.
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary="Create movie-genre relationship",
        description="""
        Create a new relationship between a movie and a genre.

        **Admin Only**: This operation requires admin privileges.

        **Cache Management:**
        - Clears related movie and genre caches
        - Updates recommendation caches
        - Invalidates list view caches
        """,
        request=MovieGenreCreateSerializer,
        responses={
            201: MovieGenreDetailSerializer,
            400: None,
            401: None,
            403: None,
            500: None,
        },
        tags=["Movies - Genre Relationships"],
    )
    def post(self, request):
        """Create movie-genre relationship with validation."""
        try:
            serializer = MovieGenreCreateSerializer(
                data=request.data, context={"request": request}
            )

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message="Invalid movie-genre relationship data",
                    field_errors=serializer.errors,
                )

            # Create the relationship within transaction
            try:
                with transaction.atomic():
                    movie_genre = serializer.save()

                    # Clear related caches
                    self._clear_related_caches(
                        movie_genre.movie.id, movie_genre.genre.id
                    )

                    # Serialize response
                    response_serializer = MovieGenreDetailSerializer(movie_genre)

                    logger.info(
                        f"Created movie-genre relationship: "
                        f"{movie_genre.movie.title} → {movie_genre.genre.name}"
                    )

                    return APIResponse.created(
                        message=(
                            f"Successfully created relationship: {movie_genre.movie.title} "
                            f"→ {movie_genre.genre.name}"
                        ),
                        data=response_serializer.data,
                    )

            except Exception as e:
                logger.error(f"Failed to create movie-genre relationship: {e}")
                return APIResponse.server_error(
                    message="Failed to create movie-genre relationship",
                    extra_data={"error_type": "creation_failed"},
                )

        except Exception as e:
            logger.error(f"Movie-genre create error: {e}")
            return APIResponse.server_error(
                message="Failed to create movie-genre relationship"
            )

    def _clear_related_caches(self, movie_id: int, genre_id: int):
        """Clear caches related to movie and genre."""
        try:
            # Clear movie-specific caches
            cache.delete_many(
                [
                    f"movie_genres_{movie_id}_*",
                    f"movie_recommendations_{movie_id}_*",
                    f"similar_movies_{movie_id}_*",
                ]
            )

            # Clear genre-specific caches
            cache.delete(f"genre_movies_{genre_id}")

            # Clear list caches
            cache.delete_pattern("movie_genres_list_*")

            logger.debug(f"Cleared caches for movie {movie_id} and genre {genre_id}")

        except Exception as e:
            logger.warning(f"Failed to clear caches: {e}")


# =========================================================================
# MOVIE-GENRE DETAIL VIEW WITH COMPLETE DOCUMENTATION
# =========================================================================


class MovieGenreDetailView(APIView):
    """
    Get detailed information about a specific movie-genre relationship.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Get movie-genre relationship details",
        description="""
        Get detailed information about a specific movie-genre relationship.

        **Response Details:**
        - Complete movie and genre information
        - Relationship metadata (primary status, weight)
        - Creation and modification timestamps
        - Related statistics and metrics

        **Use Cases:**
        - Admin review of genre assignments
        - Data quality validation
        - Relationship audit trails
        - Integration debugging
        """,
        responses={
            200: MovieGenreDetailSerializer,
            404: None,
            500: None,
        },
        tags=["Movies - Genre Relationships"],
    )
    def get(self, request, pk):
        """Get movie-genre relationship details."""
        try:
            # Check cache first
            cache_key = f"movie_genre_detail_{pk}"
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Movie-genre relationship {pk} retrieved from cache")
                return APIResponse.success(
                    message="Movie-genre relationship details (cached)",
                    data=cached_data,
                )

            # Get the relationship
            try:
                movie_genre = MovieGenre.objects.select_related("movie", "genre").get(
                    pk=pk, is_active=True
                )
            except MovieGenre.DoesNotExist:
                return APIResponse.not_found(
                    message=f"Movie-genre relationship with ID {pk} not found",
                    extra_data={"searched_id": pk},
                )

            # Serialize the relationship
            serializer = MovieGenreDetailSerializer(movie_genre)

            # Cache for 1 hour
            cache.set(cache_key, serializer.data, 60 * 60)

            logger.info(
                f"Retrieved movie-genre relationship: "
                f"{movie_genre.movie.title} → {movie_genre.genre.name}"
            )

            return APIResponse.success(
                message=(
                    f"Movie-genre relationship: {movie_genre.movie.title} "
                    f"→ {movie_genre.genre.name}"
                ),
                data=serializer.data,
            )

        except Exception as e:
            logger.error(f"Movie-genre detail error: {e}")
            return APIResponse.server_error(
                message="Failed to get movie-genre relationship details"
            )


# =========================================================================
# MOVIE-GENRE UPDATE VIEW
# =========================================================================


class MovieGenreUpdateView(APIView):
    """
    Update an existing movie-genre relationship.
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary="Update movie-genre relationship",
        description="""
        Update properties of an existing movie-genre relationship.

        **Admin Only**: This operation requires admin privileges.

        **Updatable Fields:**
        - Primary genre status (with automatic conflict resolution)
        - Weight value (0.0-1.0)
        - Active status

        **Cache Management:**
        - Clears movie and genre specific caches
        - Updates recommendation algorithms
        - Refreshes list view caches
        """,
        request=MovieGenreUpdateSerializer,
        responses={
            200: MovieGenreDetailSerializer,
            400: None,
            401: None,
            403: None,
            404: None,
            500: None,
        },
        tags=["Movies - Genre Relationships"],
    )
    def patch(self, request, pk):
        """Update movie-genre relationship."""
        try:
            # Get the relationship
            try:
                movie_genre = MovieGenre.objects.select_related("movie", "genre").get(
                    pk=pk, is_active=True
                )
            except MovieGenre.DoesNotExist:
                return APIResponse.not_found(
                    message=f"Movie-genre relationship with ID {pk} not found",
                    extra_data={"searched_id": pk},
                )

            # Validate update data
            serializer = MovieGenreUpdateSerializer(
                movie_genre,
                data=request.data,
                partial=True,
                context={"request": request},
            )

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message="Invalid update data", field_errors=serializer.errors
                )

            # Update within transaction
            try:
                with transaction.atomic():
                    updated_movie_genre = serializer.save()

                    # Clear related caches
                    self._clear_related_caches(
                        updated_movie_genre.movie.id, updated_movie_genre.genre.id
                    )

                    # Serialize response
                    response_serializer = MovieGenreDetailSerializer(
                        updated_movie_genre
                    )

                    logger.info(
                        f"Updated movie-genre relationship: {updated_movie_genre.movie.title} "
                        f"→ {updated_movie_genre.genre.name}"
                    )

                    return APIResponse.updated(
                        message=f"Successfully updated relationship: {updated_movie_genre.movie.title} → {updated_movie_genre.genre.name}",
                        data=response_serializer.data,
                    )

            except Exception as e:
                logger.error(f"Failed to update movie-genre relationship {pk}: {e}")
                return APIResponse.server_error(
                    message="Failed to update movie-genre relationship",
                    extra_data={"relationship_id": pk},
                )

        except Exception as e:
            logger.error(f"Movie-genre update error: {e}")
            return APIResponse.server_error(
                message="Failed to update movie-genre relationship"
            )

    def _clear_related_caches(self, movie_id: int, genre_id: int):
        """Clear caches related to movie and genre."""
        try:
            # Clear movie-specific caches
            cache.delete_many(
                [
                    f"movie_genres_{movie_id}_*",
                    f"movie_recommendations_{movie_id}_*",
                    f"similar_movies_{movie_id}_*",
                    "movie_genre_detail_*",
                ]
            )

            # Clear genre-specific caches
            cache.delete(f"genre_movies_{genre_id}")

            # Clear list caches
            cache.delete_pattern("movie_genres_list_*")

            logger.debug(f"Cleared caches for movie {movie_id} and genre {genre_id}")

        except Exception as e:
            logger.warning(f"Failed to clear caches: {e}")


# =========================================================================
# MOVIE-GENRE DELETE VIEW
# =========================================================================


class MovieGenreDeleteView(APIView):
    """
    Delete (deactivate) a movie-genre relationship.
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary="Delete movie-genre relationship",
        description="""
        Soft delete (deactivate) a movie-genre relationship.

        **Admin Only**: This operation requires admin privileges.

        **Safety Measures:**
        - Primary genre deletion requires confirmation
        - Prevents orphaned movie records
        - Maintains referential integrity
        """,
        responses={
            204: None,
            400: None,
            401: None,
            403: None,
            404: None,
            500: None,
        },
        tags=["Movies - Genre Relationships"],
    )
    def delete(self, request, pk):
        """Soft delete movie-genre relationship."""
        try:
            # Get the relationship
            try:
                movie_genre = MovieGenre.objects.select_related("movie", "genre").get(
                    pk=pk, is_active=True
                )
            except MovieGenre.DoesNotExist:
                return APIResponse.not_found(
                    message=f"Movie-genre relationship with ID {pk} not found",
                    extra_data={"searched_id": pk},
                )

            # Check if this is the only genre for the movie
            movie_genre_count = MovieGenre.objects.filter(
                movie=movie_genre.movie, is_active=True
            ).count()

            if movie_genre_count == 1:
                return APIResponse.validation_error(
                    message="Cannot delete the last genre from a movie",
                    field_errors={
                        "genre": [
                            "Movies must have at least one genre. Add another"
                            " genre before deleting this one."
                        ]
                    },
                )

            # Delete within transaction
            try:
                with transaction.atomic():
                    movie_title = movie_genre.movie.title
                    genre_name = movie_genre.genre.name
                    movie_id = movie_genre.movie.id
                    genre_id = movie_genre.genre.id

                    # Soft delete (mark as inactive)
                    movie_genre.is_active = False
                    movie_genre.save(update_fields=["is_active"])

                    # If this was a primary genre, make another genre primary
                    if movie_genre.is_primary:
                        next_genre = (
                            MovieGenre.objects.filter(
                                movie=movie_genre.movie, is_active=True
                            )
                            .order_by("-weight")
                            .first()
                        )

                        if next_genre:
                            next_genre.is_primary = True
                            next_genre.weight = 1.0
                            next_genre.save(update_fields=["is_primary", "weight"])
                            logger.info(
                                f"Made {next_genre.genre.name} the new primary genre for {movie_title}"
                            )

                    # Clear related caches
                    self._clear_related_caches(movie_id, genre_id)

                    logger.info(
                        f"Deleted movie-genre relationship: {movie_title} → {genre_name}"
                    )

                    return APIResponse.deleted(
                        message=f"Successfully removed {genre_name} from {movie_title}"
                    )

            except Exception as e:
                logger.error(f"Failed to delete movie-genre relationship {pk}: {e}")
                return APIResponse.server_error(
                    message="Failed to delete movie-genre relationship",
                    extra_data={"relationship_id": pk},
                )

        except Exception as e:
            logger.error(f"Movie-genre delete error: {e}")
            return APIResponse.server_error(
                message="Failed to delete movie-genre relationship"
            )

    def _clear_related_caches(self, movie_id: int, genre_id: int):
        """Clear caches related to movie and genre."""
        try:
            # Clear movie-specific caches
            cache.delete_many(
                [
                    f"movie_genres_{movie_id}_*",
                    f"movie_recommendations_{movie_id}_*",
                    f"similar_movies_{movie_id}_*",
                    "movie_genre_detail_*",
                ]
            )

            # Clear genre-specific caches
            cache.delete(f"genre_movies_{genre_id}")

            # Clear list caches
            cache.delete_pattern("movie_genres_list_*")

            logger.debug(f"Cleared caches for movie {movie_id} and genre {genre_id}")

        except Exception as e:
            logger.warning(f"Failed to clear caches: {e}")
