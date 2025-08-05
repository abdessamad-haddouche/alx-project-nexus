"""
Core Movie CRUD Operations with Essential OpenAPI Documentation.
"""

import logging

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.core.cache import cache
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.utils import timezone

from apps.movies.models import Movie
from apps.movies.serializers import (
    MovieCreateSerializer,
    MovieDetailSerializer,
    MovieListSerializer,
    MovieUpdateSerializer,
)
from apps.movies.services import MovieService
from core.permissions import IsAdminUser
from core.responses import APIResponse

logger = logging.getLogger(__name__)


class MovieListView(APIView):
    """List movies from database with API fallback."""

    permission_classes = [AllowAny]
    movie_service = MovieService()

    @extend_schema(
        summary="List movies",
        description="List movies with filtering. Uses database"
        " when available, TMDb API as fallback.",
        parameters=[
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Search across title, original title, and overview",
                examples=[
                    OpenApiExample("Movie Title", value="batman"),
                    OpenApiExample("Actor Name", value="leonardo dicaprio"),
                    OpenApiExample("Keywords", value="superhero action"),
                ],
            ),
            OpenApiParameter(
                name="genre",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by genre (TMDb genre ID)",
                examples=[
                    OpenApiExample("Action", value=28),
                    OpenApiExample("Comedy", value=35),
                    OpenApiExample("Drama", value=18),
                    OpenApiExample("Horror", value=27),
                    OpenApiExample("Sci-Fi", value=878),
                ],
            ),
            OpenApiParameter(
                name="min_rating",
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Minimum TMDb rating (0.0-10.0)",
                examples=[
                    OpenApiExample("Good Movies", value=7.0),
                    OpenApiExample("Great Movies", value=8.0),
                    OpenApiExample("Masterpieces", value=9.0),
                ],
            ),
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Page number (default: 1)",
                examples=[
                    OpenApiExample("First Page", value=1),
                    OpenApiExample("Second Page", value=2),
                ],
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Items per page (default: 20, max: 100)",
                examples=[
                    OpenApiExample("Small Page", value=10),
                    OpenApiExample("Default Page", value=20),
                    OpenApiExample("Large Page", value=50),
                ],
            ),
        ],
        responses={
            200: MovieListSerializer(many=True),
            400: None,
            500: None,
        },
        tags=["Movies - Public"],
    )
    @extend_schema(
        summary="List movies",
        description="List movies with filtering. Uses database"
        " when available, TMDb API as fallback.",
        parameters=[
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Search across title, original title, and overview",
                examples=[
                    OpenApiExample("Movie Title", value="batman"),
                    OpenApiExample("Actor Name", value="leonardo dicaprio"),
                    OpenApiExample("Keywords", value="superhero action"),
                ],
            ),
            OpenApiParameter(
                name="genre",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by genre (TMDb genre ID)",
                examples=[
                    OpenApiExample("Action", value=28),
                    OpenApiExample("Comedy", value=35),
                    OpenApiExample("Drama", value=18),
                ],
            ),
            OpenApiParameter(
                name="min_rating",
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Minimum TMDb rating (0.0-10.0)",
                examples=[
                    OpenApiExample("Good Movies", value=7.0),
                    OpenApiExample("Great Movies", value=8.0),
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
                description="Items per page (default: 20, max: 100)",
            ),
        ],
        responses={
            200: MovieListSerializer(many=True),
            400: None,
            500: None,
        },
        tags=["Movies - Public"],
    )
    def get(self, request) -> Response:
        """List movies - hybrid database + API approach."""
        try:
            # Get filters
            search = request.query_params.get("search", "").strip()
            genre_id = request.query_params.get("genre")
            min_rating = request.query_params.get("min_rating")
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 100)

            # Check if we have enough movies in database
            total_movies = Movie.objects.filter(is_active=True).count()

            if total_movies >= 50:  # Database has enough content
                logger.info(
                    f"Using database for movie list ({total_movies} movies available)"
                )
                return self._get_from_database(
                    request, search, genre_id, min_rating, page, page_size
                )
            else:
                logger.info(f"Database has only {total_movies} movies, using TMDb API")
                return self._get_from_api(request, page)

        except Exception as e:
            logger.error(f"Error in movie list: {e}")
            return APIResponse.server_error(message="Failed to retrieve movies")

    def _get_from_database(
        self, request, search, genre_id, min_rating, page, page_size
    ):
        """Get movies from local database with filtering."""
        # Build queryset
        queryset = (
            Movie.objects.select_related()
            .prefetch_related("genres")
            .filter(is_active=True)
        )

        # Apply filters
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(original_title__icontains=search)
                | Q(overview__icontains=search)
            )

        if genre_id:
            try:
                queryset = queryset.filter(genres__tmdb_id=int(genre_id))
            except ValueError:
                pass

        if min_rating:
            try:
                queryset = queryset.filter(vote_average__gte=float(min_rating))
            except ValueError:
                pass

        # Order by popularity
        queryset = queryset.order_by("-popularity", "-vote_average")

        # Paginate
        paginator = Paginator(queryset, page_size)

        try:
            movies_page = paginator.page(page)
        except PageNotAnInteger:
            movies_page = paginator.page(1)  # Invalid page format -> page 1
        except EmptyPage:
            # Page out of range -> return empty results
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
                        "max_page": paginator.num_pages,
                    },
                    "data_source": "Database",
                    "database_movie_count": Movie.objects.filter(
                        is_active=True
                    ).count(),
                },
            )

        # Serialize
        serializer = MovieListSerializer(
            movies_page, many=True, context={"request": request}
        )

        response_data = {
            "results": serializer.data,
            "pagination": {
                "page": movies_page.number,
                "page_size": page_size,
                "total_pages": paginator.num_pages,
                "total_results": paginator.count,
                "has_next": movies_page.has_next(),
                "has_previous": movies_page.has_previous(),
            },
            "data_source": "Database",
            "database_movie_count": Movie.objects.filter(is_active=True).count(),
        }

        return APIResponse.success(
            message=f"Retrieved {len(serializer.data)} movies from database",
            data=response_data,
        )

    def _get_from_api(self, request, page):
        """Get movies from TMDb API when database is sparse."""
        try:
            popular_data = self.movie_service.get_popular_movies(page=page)

            popular_data["data_source"] = "TMDb API (Database Building...)"
            popular_data["database_movie_count"] = Movie.objects.filter(
                is_active=True
            ).count()
            popular_data["note"] = (
                "Database is being built. More movies will be available"
                " locally over time."
            )

            return APIResponse.success(
                message=f"Retrieved {len(popular_data.get('results', []))} movies "
                "from TMDb API",
                data=popular_data,
            )
        except Exception as e:
            logger.error(f"TMDb API failed: {e}")
            return APIResponse.server_error(message="Failed to retrieve movies")


class MovieDetailView(APIView):
    """Get movie details with smart database storage."""

    permission_classes = [AllowAny]
    movie_service = MovieService()

    @extend_schema(
        summary="Get movie details",
        description="Get movie details by TMDb ID. Fetches from "
        "TMDb and stores in database if not found locally.",
        responses={
            200: MovieDetailSerializer,
            404: None,
            500: None,
        },
        tags=["Movies - Public"],
    )
    def get(self, request, pk: int) -> Response:
        """Get movie details - stores in database if not exists."""
        try:
            # Step 1: Check cache first
            cache_key = f"movie_detail_{pk}"
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Movie detail retrieved from cache: TMDb ID {pk}")
                return APIResponse.success(
                    message="Movie details retrieved (cached)", data=cached_data
                )

            # Step 2: Check database by TMDb ID
            try:
                movie = (
                    Movie.objects.select_related()
                    .prefetch_related(
                        "genres",
                        "movie_genres__genre",
                    )
                    .get(tmdb_id=pk, is_active=True)
                )

                logger.info(f"Movie found in database: {movie.title}")

                # Found in database - serialize and cache
                serializer = MovieDetailSerializer(movie, context={"request": request})
                cache.set(cache_key, serializer.data, 60 * 60 * 24)  # Cache 24 hours

                return APIResponse.success(
                    message="Movie details retrieved from database",
                    data=serializer.data,
                )

            except Movie.DoesNotExist:
                # Step 3: Not in database - fetch from TMDb and store
                logger.info(
                    f"Movie TMDb ID {pk} not in database, fetching from TMDb..."
                )

                try:
                    # Sync from TMDb (this will store in database)
                    movie = self.movie_service.sync_movie_from_tmdb(pk)

                    if movie:
                        logger.info(
                            f"Movie successfully synced and stored: {movie.title}"
                        )

                        # Serialize the newly stored movie
                        serializer = MovieDetailSerializer(
                            movie, context={"request": request}
                        )
                        cache.set(cache_key, serializer.data, 60 * 60 * 24)

                        return APIResponse.success(
                            message="Movie details retrieved from TMDb and "
                            "stored in database",
                            data=serializer.data,
                        )
                    else:
                        return APIResponse.not_found(
                            message="Movie not found on TMDb",
                            extra_data={"tmdb_id": pk},
                        )

                except Exception as e:
                    logger.error(f"Failed to sync movie {pk} from TMDb: {e}")
                    return APIResponse.server_error(
                        message="Failed to fetch movie details",
                        extra_data={"tmdb_id": pk},
                    )

        except Exception as e:
            logger.error(f"Error in movie detail view for TMDb ID {pk}: {e}")
            return APIResponse.server_error(message="Failed to retrieve movie")


class MovieCreateView(APIView):
    """Create new movie entry (Admin only)."""

    permission_classes = [IsAuthenticated, IsAdminUser]
    movie_service = MovieService()

    @extend_schema(
        summary="Create movie (Admin)",
        description="Create a new movie entry. Admin access required.",
        request=MovieCreateSerializer,
        responses={
            201: MovieDetailSerializer,
            400: None,
            401: None,
            403: None,
            409: None,
            500: None,
        },
        tags=["Movies - Admin"],
    )
    def post(self, request) -> Response:
        """Create a new movie with smart soft delete restoration."""
        try:
            # Step 1: Check for existing movie (including soft-deleted)
            tmdb_id = request.data.get("tmdb_id")
            existing_movie = None

            if tmdb_id:
                existing_movie = Movie.objects.filter(tmdb_id=tmdb_id).first()

                if existing_movie and existing_movie.is_active:
                    return APIResponse.error(
                        message=f"Movie with TMDb ID {tmdb_id} already"
                        "exists and is active",
                        status_code=status.HTTP_409_CONFLICT,
                    )

            # Step 2: Handle soft-deleted movie restoration
            if existing_movie and not existing_movie.is_active:
                logger.info(f"Found soft-deleted movie {tmdb_id}, restoring...")

                # Create a copy of request data without tmdb_id for validation
                restore_data = request.data.copy()
                restore_data.pop(
                    "tmdb_id", None
                )  # Remove tmdb_id to avoid constraint issues

                # Use update serializer for validation only
                serializer = MovieUpdateSerializer(
                    existing_movie,
                    data=restore_data,
                    partial=True,
                    context={"request": request},
                )

                if not serializer.is_valid():
                    logger.warning(
                        f"Movie restoration validation failed: {serializer.errors}"
                    )
                    return APIResponse.validation_error(
                        message="Movie restoration failed",
                        field_errors=serializer.errors,
                    )

                # Apply validated data to the existing movie
                for field, value in serializer.validated_data.items():
                    setattr(existing_movie, field, value)

                # Restore the movie
                existing_movie.is_active = True
                existing_movie.sync_status = "success"
                existing_movie.last_synced = timezone.now()
                existing_movie.save()

                movie = existing_movie
                action_message = f"Movie '{movie.title}' restored from soft delete"
                logger.info(
                    f"Successfully restored movie: {movie.title} (ID: {movie.id})"
                )

            else:
                # Step 3: Create genuinely new movie
                serializer = MovieCreateSerializer(
                    data=request.data, context={"request": request}
                )

                if not serializer.is_valid():
                    logger.warning(
                        f"Movie creation validation failed: {serializer.errors}"
                    )
                    return APIResponse.validation_error(
                        message="Movie creation failed", field_errors=serializer.errors
                    )

                movie = serializer.save()
                action_message = f"Movie '{movie.title}' created successfully"
                logger.info(
                    f"Successfully created movie: {movie.title} (ID: {movie.id})"
                )

            # Clear any cached data
            cache.delete(f"movie_detail_{tmdb_id}")
            cache.delete(f"movie_detail_{movie.id}")

            # Step 4: Return response
            detail_serializer = MovieDetailSerializer(
                movie, context={"request": request}
            )

            return APIResponse.created(
                message=action_message, data=detail_serializer.data
            )

        except Exception as e:
            logger.error(f"Error creating/restoring movie: {str(e)}")
            return APIResponse.server_error(message="Failed to create movie")


class MovieUpdateView(APIView):
    """Update existing movie (Admin only)."""

    permission_classes = [IsAuthenticated, IsAdminUser]
    movie_service = MovieService()

    @extend_schema(
        summary="Update movie (Complete)",
        description="Fully update an existing movie. Admin access required.",
        request=MovieUpdateSerializer,
        responses={
            200: MovieDetailSerializer,
            400: None,
            401: None,
            403: None,
            404: None,
            500: None,
        },
        tags=["Movies - Admin"],
    )
    def put(self, request, pk: int) -> Response:
        """Fully update a movie."""
        return self._update_movie(request, pk, partial=False)

    @extend_schema(
        summary="Update movie (Partial)",
        description="Partially update an existing movie. Admin access required.",
        request=MovieUpdateSerializer,
        responses={
            200: MovieDetailSerializer,
            400: None,
            401: None,
            403: None,
            404: None,
            500: None,
        },
        tags=["Movies - Admin"],
    )
    def patch(self, request, pk: int) -> Response:
        """Partially update a movie."""
        return self._update_movie(request, pk, partial=True)

    def _update_movie(self, request, pk: int, partial: bool = False) -> Response:
        """Common update logic for PUT and PATCH."""
        try:
            # Get existing movie by database ID
            try:
                movie = Movie.objects.get(pk=pk, is_active=True)
            except Movie.DoesNotExist:
                logger.warning(f"Movie with ID {pk} not found for update")
                return APIResponse.not_found(message="Movie not found")

            # Validate update data
            serializer = MovieUpdateSerializer(
                movie, data=request.data, partial=partial, context={"request": request}
            )

            if not serializer.is_valid():
                logger.warning(f"Movie update validation failed: {serializer.errors}")
                return APIResponse.validation_error(
                    message="Movie update failed", field_errors=serializer.errors
                )

            # Update movie
            updated_movie = serializer.save()

            # Clear related caches
            cache.delete(f"movie_detail_{pk}")
            cache.delete(f"movie_detail_{updated_movie.tmdb_id}")

            # Return updated movie data
            detail_serializer = MovieDetailSerializer(
                updated_movie, context={"request": request}
            )

            update_type = "partially" if partial else "fully"
            logger.info(
                f"Movie {update_type} updated: {updated_movie.title} (ID: {pk})"
            )

            return APIResponse.updated(
                message=f"Movie {update_type} updated successfully",
                data=detail_serializer.data,
            )

        except Exception as e:
            logger.error(f"Error updating movie {pk}: {str(e)}")
            return APIResponse.server_error(message="Failed to update movie")


class MovieDeleteView(APIView):
    """Delete movie (Admin only)."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary="Delete movie (Admin)",
        description="Delete a movie. Soft delete by default, "
        "hard delete with parameter. Admin access required.",
        parameters=[
            OpenApiParameter(
                name="hard_delete",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Permanent deletion (default: false)",
                examples=[
                    OpenApiExample("Soft Delete", value=False),
                    OpenApiExample("Hard Delete", value=True),
                ],
            ),
        ],
        responses={
            204: None,
            400: None,
            401: None,
            403: None,
            404: None,
            500: None,
        },
        tags=["Movies - Admin"],
    )
    def delete(self, request, pk: int) -> Response:
        """Delete a movie."""
        try:
            # Get movie by database ID
            try:
                movie = Movie.objects.get(pk=pk)
            except Movie.DoesNotExist:
                logger.warning(f"Movie with ID {pk} not found for deletion")
                return APIResponse.not_found(message="Movie not found")

            # Check if already deleted
            if not movie.is_active:
                return APIResponse.error(
                    message="Movie is already deleted",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Determine deletion type
            hard_delete = (
                request.query_params.get("hard_delete", "false").lower() == "true"
            )

            movie_title = movie.title
            movie_id = movie.id
            tmdb_id = movie.tmdb_id

            if hard_delete:
                # Permanent deletion
                movie.delete()
                logger.warning(
                    f"Movie permanently deleted: {movie_title} (ID: {movie_id})"
                )
                deletion_message = (
                    f"Movie '{movie_title}' permanently deleted successfully"
                )
            else:
                # Soft deletion
                movie.is_active = False
                movie.save(update_fields=["is_active"])
                logger.info(f"Movie soft deleted: {movie_title} (ID: {movie_id})")
                deletion_message = f"Movie '{movie_title}' deleted successfully"

            # Clear related caches
            cache.delete(f"movie_detail_{pk}")
            cache.delete(f"movie_detail_{tmdb_id}")
            cache.delete("movie_list")

            return APIResponse.deleted(message=deletion_message)

        except Exception as e:
            logger.error(f"Error deleting movie {pk}: {str(e)}")
            return APIResponse.server_error(message="Failed to delete movie")
