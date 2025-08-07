"""
Core Movie CRUD Operations.
"""

import hashlib
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
from django.db import transaction
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
    """
    List movies with progressive data loading strategy:
    1. Cache complete API responses (VIEW level)
    2. Store partial data from TMDb popular endpoint
    3. Use database when sufficient movies available
    """

    permission_classes = [AllowAny]
    movie_service = MovieService()

    # Cache settings
    CACHE_TTL = 60 * 30  # 30 minutes for complete responses
    MIN_MOVIES_FOR_DB = 100

    @extend_schema(
        summary="List movies",
        description="""
        List movies with progressive data loading strategy.

        **Data Strategy:**
        - Check database first for this specific page
        - If not enough data → fetch from TMDb API and store as partial data
        - Store movies with sync_status='partial' for fast browsing
        - Use database when sufficient movies available
        """,
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
        """EXACT LOGIC: Page by page storage and retrieval."""
        try:
            search = request.query_params.get("search", "").strip()
            genre_id = request.query_params.get("genre")
            min_rating = request.query_params.get("min_rating")
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 100)

            # Check if we have enough movies in database for THIS PAGE
            total_movies = Movie.objects.filter(is_active=True).count()
            expected_movies_for_this_page = page * page_size

            # Check if we have enough data for this specific page
            if total_movies >= expected_movies_for_this_page and not any(
                [search, genre_id, min_rating]
            ):
                # Enough data AND no filters -> use database
                logger.info(
                    f"Using DATABASE for page {page} - have {total_movies} movies"
                )
                response_data = self._get_from_database(
                    request, search, genre_id, min_rating, page, page_size
                )
                return APIResponse.success(
                    f"Movies retrieved from DATABASE (page {page})", response_data
                )
            else:
                # Need to get from API and store
                if any([search, genre_id, min_rating]):
                    logger.info(f"Using DATABASE for page {page} with filters")
                    response_data = self._get_from_database(
                        request, search, genre_id, min_rating, page, page_size
                    )
                    return APIResponse.success(
                        f"Movies retrieved from DATABASE with filters (page {page})",
                        response_data,
                    )
                else:
                    logger.info(
                        f"Getting from TMDb API for page {page} - need {expected_movies_for_this_page}, have {total_movies}"
                    )
                    response_data = self._get_from_api_and_store(page)
                    return APIResponse.success(
                        f"Movies retrieved from TMDb API and STORED (page {page})",
                        response_data,
                    )

        except ValueError:
            return APIResponse.validation_error("Invalid page parameters")
        except Exception as e:
            logger.error(f"MovieListView error: {e}")
            return APIResponse.server_error("Failed to retrieve movies")

    def _get_cache_key(
        self, search: str, genre_id: str, min_rating: str, page: int, page_size: int
    ) -> str:
        """Generate cache key for complete API response."""
        key_data = f"movies_list_{page}_{page_size}_{search}_{genre_id}_{min_rating}"
        return f"view_cache_{hashlib.md5(key_data.encode()).hexdigest()[:8]}"

    def _get_from_database(
        self,
        request,
        search: str,
        genre_id: str,
        min_rating: str,
        page: int,
        page_size: int,
    ) -> Dict[str, Any]:
        """Get filtered movies from database."""
        # Build queryset with optimizations
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

        # Order and paginate
        queryset = queryset.order_by("-popularity", "-vote_average")
        paginator = Paginator(queryset, page_size)

        try:
            movies_page = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            movies_page = paginator.page(1) if paginator.num_pages > 0 else None

        if not movies_page or not movies_page.object_list:
            return {"results": [], "pagination": {}, "data_source": "DATABASE (empty)"}

        # Serialize
        serializer = MovieListSerializer(
            movies_page, many=True, context={"request": request}
        )

        return {
            "results": serializer.data,
            "pagination": {
                "page": movies_page.number,
                "total_pages": paginator.num_pages,
                "total_results": paginator.count,
                "has_next": movies_page.has_next(),
                "has_previous": movies_page.has_previous(),
            },
            "data_source": "DATABASE",
            "page": movies_page.number,
            "total_movies_in_db": paginator.count,
        }

    def _get_from_api_and_store(self, page: int) -> Dict[str, Any]:
        """Get from TMDb API and ACTUALLY STORE the fucking data."""
        try:
            # Get raw data from TMDb API
            api_data = self.movie_service.get_popular_movies(
                page=page, store_movies=False
            )

            if not api_data.get("results"):
                return {
                    "results": [],
                    "pagination": {},
                    "data_source": "TMDb API (no results)",
                    "stored_movies": 0,
                }

            stored_count = self._store_partial_movies(api_data["results"])
            logger.info(f"STORED {stored_count} movies from TMDb API page {page}")

            return {
                "results": api_data["results"],
                "pagination": api_data.get("pagination", {}),
                "data_source": "TMDb API + STORED",
                "stored_movies": stored_count,
                "page": page,
                "total_movies_in_db": Movie.objects.filter(is_active=True).count(),
            }

        except Exception as e:
            logger.error(f"TMDb API failed for page {page}: {e}")
            raise

    def _store_partial_movies(self, movies_data: list) -> int:
        """Store movies with sync_status='partial'."""
        stored = 0

        try:
            with transaction.atomic():
                for movie in movies_data:
                    tmdb_id = movie.get("tmdb_id") or movie.get("id")

                    if not tmdb_id or Movie.objects.filter(tmdb_id=tmdb_id).exists():
                        continue

                    # Create with partial data - INCLUDE ALL REQUIRED FIELDS
                    Movie.objects.create(
                        tmdb_id=str(tmdb_id),
                        title=movie.get("title", ""),
                        original_title=movie.get("original_title", "")
                        or movie.get("title", ""),
                        overview=movie.get("overview", ""),
                        release_date=self._parse_date(movie.get("release_date")),
                        adult=movie.get("adult", False),
                        popularity=movie.get("popularity", 0.0),
                        vote_average=movie.get("vote_average", 0.0),
                        vote_count=movie.get("vote_count", 0),
                        original_language=movie.get("original_language", "en"),
                        poster_path=movie.get("poster_path") or "",
                        backdrop_path=movie.get("backdrop_path") or "",
                        # PARTIAL DATA STATUS
                        sync_status="partial",
                        last_synced=timezone.now(),
                        is_active=True,
                        # Defaults for missing fields
                        runtime=None,
                        budget=0,
                        revenue=0,
                        homepage="",
                        tagline="",
                        main_trailer_key=None,
                        main_trailer_site="YouTube",
                        status="Released",
                    )
                    stored += 1
                    logger.info(
                        f"STORED movie: {movie.get('title')} (TMDb ID: {tmdb_id})"
                    )

        except Exception as e:
            logger.error(f"Error storing partial movies: {e}")

        logger.info(f"Stored {stored} partial movies")
        return stored

    def _parse_date(self, date_string: str):
        """Parse date string to date object."""
        if not date_string:
            return None
        try:
            from datetime import datetime

            return datetime.strptime(date_string, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None


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
                    return APIResponse.not_found(
                        "Movie not found on TMDb", {"tmdb_id": pk}
                    )

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
