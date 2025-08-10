"""
Core Movie CRUD Operations.
"""

import logging
from typing import Any, Dict

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

from ..models import Genre

logger = logging.getLogger(__name__)


class MovieListView(APIView):
    """
    Movie listing.
    """

    permission_classes = [AllowAny]
    movie_service = MovieService()

    # Configuration
    CACHE_TTL = 60 * 30  # 30 minutes
    MIN_MOVIES_FOR_API_FALLBACK = 100

    @extend_schema(
        summary="List movies",
        description="List movies with filtering and smart data loading",
        parameters=[
            OpenApiParameter(
                "search", OpenApiTypes.STR, description="Search in title/overview"
            ),
            OpenApiParameter(
                "genre", OpenApiTypes.INT, description="Filter by TMDb genre ID"
            ),
            OpenApiParameter(
                "min_rating", OpenApiTypes.NUMBER, description="Minimum rating (0-10)"
            ),
            OpenApiParameter("page", OpenApiTypes.INT, description="Page number"),
            OpenApiParameter(
                "page_size", OpenApiTypes.INT, description="Items per page (max 100)"
            ),
        ],
        responses={200: MovieListSerializer(many=True)},
        tags=["Movies - Public"],
    )
    def get(self, request) -> Response:
        """List movies with filtering support."""
        try:
            # Parse and validate parameters
            params = self._parse_parameters(request)
            if isinstance(params, Response):  # Validation error
                return params

            # Check cache first
            cache_key = self._build_cache_key(params)
            cached_data = cache.get(cache_key)
            if cached_data:
                return APIResponse.success("Movies from cache", cached_data)

            # Determine data source and get movies
            response_data = self._get_movies(params)

            # Cache the response
            cache.set(cache_key, response_data, self.CACHE_TTL)

            # Build success message
            source = response_data.get("data_source", "unknown")
            count = len(response_data.get("results", []))
            message = f"Retrieved {count} movies from {source}"

            return APIResponse.success(message, response_data)

        except Exception as e:
            logger.error(f"MovieListView error: {e}")
            return APIResponse.server_error("Failed to retrieve movies")

    def _parse_parameters(self, request) -> Dict[str, Any]:
        """Parse and validate request parameters."""
        try:
            search = request.query_params.get("search", "").strip()
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 100)

            # Parse genre
            genre_id = request.query_params.get("genre")
            if genre_id:
                try:
                    genre_id = int(genre_id)
                    # Validate genre exists
                    if not Genre.objects.filter(
                        tmdb_id=genre_id, is_active=True
                    ).exists():
                        return APIResponse.validation_error(
                            f"Genre with ID {genre_id} not found",
                            {"genre": [f"Genre {genre_id} does not exist"]},
                        )
                except ValueError:
                    return APIResponse.validation_error(
                        "Invalid genre ID", {"genre": ["Must be a valid integer"]}
                    )

            # Parse min_rating
            min_rating = request.query_params.get("min_rating")
            if min_rating:
                try:
                    min_rating = float(min_rating)
                    if not 0.0 <= min_rating <= 10.0:
                        return APIResponse.validation_error(
                            "Invalid rating range",
                            {"min_rating": ["Must be between 0.0 and 10.0"]},
                        )
                except ValueError:
                    return APIResponse.validation_error(
                        "Invalid rating value",
                        {"min_rating": ["Must be a valid number"]},
                    )

            # Validate page parameters
            if page < 1:
                return APIResponse.validation_error(
                    "Invalid page number", {"page": ["Must be at least 1"]}
                )

            return {
                "search": search,
                "genre_id": genre_id,
                "min_rating": min_rating,
                "page": page,
                "page_size": page_size,
                "has_filters": bool(search or genre_id or min_rating),
            }

        except ValueError:
            return APIResponse.validation_error("Invalid parameter values")

    def _get_movies(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get movies using smart data source selection."""
        # Always use database if we have filters
        if params["has_filters"]:
            return self._get_from_database(params)

        # For no filters, check if we have enough data in database
        total_movies = Movie.objects.filter(is_active=True).count()
        expected_movies = params["page"] * params["page_size"]

        if total_movies >= expected_movies:
            return self._get_from_database(params)
        else:
            return self._get_from_api_and_store(params)

    def _get_from_database(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get movies from database with proper filtering."""
        # Build optimized queryset
        queryset = (
            Movie.objects.select_related()
            .prefetch_related("movie_genres__genre")
            .filter(is_active=True)
        )

        # Apply filters
        if params["search"]:
            queryset = queryset.filter(
                Q(title__icontains=params["search"])
                | Q(original_title__icontains=params["search"])
                | Q(overview__icontains=params["search"])
            )

        if params["genre_id"]:
            queryset = queryset.filter(movie_genres__genre__tmdb_id=params["genre_id"])

        if params["min_rating"]:
            queryset = queryset.filter(vote_average__gte=params["min_rating"])

        if params["genre_id"] and not queryset.exists():
            return {
                "results": [],
                "pagination": {
                    "page": params["page"],
                    "total_pages": 0,
                    "total_results": 0,
                    "has_next": False,
                    "has_previous": False,
                },
                "data_source": "DATABASE (no movies with this genre)",
                "filters_applied": self._get_applied_filters(params),
            }

        # Order and paginate
        queryset = queryset.distinct().order_by("-popularity", "-vote_average")
        paginator = Paginator(queryset, params["page_size"])

        try:
            movies_page = paginator.page(params["page"])
        except (PageNotAnInteger, EmptyPage):
            movies_page = paginator.page(1) if paginator.num_pages > 0 else None

        if not movies_page or not movies_page.object_list:
            return {
                "results": [],
                "pagination": {},
                "data_source": "DATABASE (empty)",
                "filters_applied": self._get_applied_filters(params),
            }

        results = []
        for movie in movies_page.object_list:
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
                "adult": movie.adult,
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
                "is_local": True,
                "sync_status": movie.sync_status,
            }
            results.append(movie_data)

        return {
            "results": results,
            "pagination": {
                "page": movies_page.number,
                "total_pages": paginator.num_pages,
                "total_results": paginator.count,
                "has_next": movies_page.has_next(),
                "has_previous": movies_page.has_previous(),
                "page_size": params["page_size"],
            },
            "data_source": "DATABASE",
            "filters_applied": self._get_applied_filters(params),
        }

    def _get_from_api_and_store(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get from TMDb API and store in database."""
        try:
            api_data = self.movie_service.get_popular_movies(
                page=params["page"], store_movies=True  # This will store them
            )

            if not api_data.get("results"):
                return {
                    "results": [],
                    "pagination": {},
                    "data_source": "TMDb API (no results)",
                }

            return {
                "results": api_data["results"],
                "pagination": api_data.get("pagination", {}),
                "data_source": "TMDb API (stored in database)",
                "filters_applied": self._get_applied_filters(params),
            }

        except Exception as e:
            logger.error(f"API fallback failed: {e}")
            return self._get_from_database(params)

    def _build_cache_key(self, params: Dict[str, Any]) -> str:
        """Build cache key from parameters."""
        import hashlib

        key_parts = [
            str(params["page"]),
            str(params["page_size"]),
            params["search"] or "",
            str(params["genre_id"]) if params["genre_id"] else "",
            str(params["min_rating"]) if params["min_rating"] else "",
        ]
        key_string = "|".join(key_parts)
        hash_key = hashlib.md5(key_string.encode()).hexdigest()[:8]
        return f"movie_list:{hash_key}"

    def _get_applied_filters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get summary of applied filters."""
        return {
            "search": params["search"] or None,
            "genre_id": params["genre_id"],
            "min_rating": params["min_rating"],
            "page": params["page"],
            "page_size": params["page_size"],
        }


class MovieDetailView(APIView):
    """
    Get movie details with smart upgrade strategy:
    1. Cache complete serialized responses (VIEW level)
    2. Check database first
    3. If partial data → upgrade to complete
    4. If missing → fetch complete data and store
    """

    permission_classes = [AllowAny]
    movie_service = MovieService()

    # Cache settings
    CACHE_TTL = 60 * 60 * 24  # 24 hours for movie details

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
        """Get movie details with smart caching and upgrading."""
        try:
            # VIEW-LEVEL CACHE: Complete serialized response
            cache_key = f"movie_detail_view_{pk}"
            cached_response = cache.get(cache_key)

            if cached_response:
                logger.info(f"Complete detail response CACHED for TMDb ID {pk}")
                return APIResponse.success("Movie details from CACHE", cached_response)

            # Check database first
            try:
                movie = (
                    Movie.objects.select_related()
                    .prefetch_related("genres", "movie_genres__genre")
                    .get(tmdb_id=pk, is_active=True)
                )

                # Check if we need to upgrade from partial to complete
                if movie.sync_status == "partial":
                    logger.info(f"Upgrading partial movie {pk} to complete data")
                    movie = self._upgrade_to_complete_data(movie)
                    source = "DATABASE (upgraded from partial)"
                else:
                    source = "DATABASE (complete)"

                # Serialize and cache complete response
                serializer = MovieDetailSerializer(movie, context={"request": request})
                cache.set(cache_key, serializer.data, self.CACHE_TTL)

                return APIResponse.success(
                    f"Movie details from {source}", serializer.data
                )

            except Movie.DoesNotExist:
                # Not in database, fetch complete data
                logger.info(
                    f"Movie {pk} not in database, fetching complete data from TMDb"
                )
                movie = self._fetch_and_store_complete(pk)

                if not movie:
                    return APIResponse.not_found("Movie not found on TMDb")

                # Serialize and cache
                serializer = MovieDetailSerializer(movie, context={"request": request})
                cache.set(cache_key, serializer.data, self.CACHE_TTL)

                return APIResponse.success(
                    "Movie details from TMDb API (fetched and stored)", serializer.data
                )

        except Exception as e:
            logger.error(f"Error in movie detail view for TMDb ID {pk}: {e}")
            return APIResponse.server_error("Failed to retrieve movie details")

    def _upgrade_to_complete_data(self, movie: Movie) -> Movie:
        """Upgrade partial movie data to complete data."""
        try:
            tmdb_data = self.movie_service.tmdb.get_movie_details(int(movie.tmdb_id))

            if tmdb_data:
                # Update movie with complete data
                updated_movie = self.movie_service.update_movie_data(movie, tmdb_data)
                updated_movie.sync_status = "complete"
                updated_movie.last_synced = timezone.now()
                updated_movie.save(update_fields=["sync_status", "last_synced"])

                logger.info(f"Successfully upgraded {movie.title} to complete data")
                return updated_movie

            return movie

        except Exception as e:
            logger.error(f"Failed to upgrade movie {movie.tmdb_id}: {e}")
            return movie

    def _fetch_and_store_complete(self, tmdb_id: int) -> Movie:
        """Fetch complete movie data and store in database."""
        try:
            # SERVICE-LEVEL: Get complete movie data (with internal caching)
            movie = self.movie_service.sync_movie_from_tmdb(tmdb_id)

            if movie:
                movie.sync_status = "complete"
                movie.last_synced = timezone.now()
                movie.save(update_fields=["sync_status", "last_synced"])
                logger.info(f"Fetched and stored complete movie: {movie.title}")

            return movie

        except Exception as e:
            logger.error(f"Failed to fetch complete movie {tmdb_id}: {e}")
            return None
            return None


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
