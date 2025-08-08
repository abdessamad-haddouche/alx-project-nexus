# ================================================================
# MOVIE RELATIONSHIP VIEWS
# ================================================================

import logging
from typing import Dict, List

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from django.core.cache import cache
from django.utils import timezone

from apps.movies.models import Movie
from apps.movies.serializers import GenreSimpleSerializer, MovieSimpleSerializer
from apps.movies.services import MovieService, RecommendationService
from core.responses import APIResponse

logger = logging.getLogger(__name__)


class BaseMovieRelationshipView(APIView):
    """Base class for movie relationship views with shared functionality."""

    permission_classes = [AllowAny]

    def __init__(self):
        super().__init__()
        self.movie_service = MovieService()

    def _parse_parameters(self, request, default_limit=10, default_rating=6.0) -> Dict:
        """Parse and validate request parameters."""
        try:
            limit = min(int(request.query_params.get("limit", default_limit)), 50)
            min_rating = float(request.query_params.get("min_rating", default_rating))
            force_sync = (
                request.query_params.get("force_sync", "false").lower() == "true"
            )

            # Validate
            if limit < 1:
                return APIResponse.validation_error(
                    "Invalid limit", {"limit": ["Must be at least 1"]}
                )

            if min_rating < 0 or min_rating > 10:
                return APIResponse.validation_error(
                    "Invalid min_rating", {"min_rating": ["Must be between 0 and 10"]}
                )

            return {
                "limit": limit,
                "min_rating": min_rating,
                "force_sync": force_sync,
            }

        except ValueError:
            return APIResponse.validation_error("Invalid parameter values")

    def _get_or_sync_movie(self, pk) -> Movie:
        """Get movie by ID or sync from TMDb if not found."""
        # Try database ID first
        try:
            movie = Movie.objects.get(pk=pk, is_active=True)
            logger.info(f"Movie found by DB ID: {movie.title}")
            return movie
        except (Movie.DoesNotExist, ValueError):
            pass

        # Try TMDb ID
        try:
            movie = Movie.objects.get(tmdb_id=pk, is_active=True)
            logger.info(f"Movie found by TMDb ID: {movie.title}")
            return movie
        except (Movie.DoesNotExist, ValueError):
            pass

        # Try to sync from TMDb
        try:
            movie = self.movie_service.sync_movie_from_tmdb(pk)
            if movie:
                logger.info(f"Movie synced from TMDb: {movie.title}")
                return movie
        except Exception as e:
            logger.error(f"Failed to sync movie {pk}: {e}")

        return APIResponse.not_found(
            f"Movie with ID {pk} not found",
            {"searched_id": pk, "suggestion": "Verify the movie ID is correct"},
        )

    def _get_or_store_movie(self, tmdb_id: int, tmdb_data: Dict = None) -> Movie:
        """Get existing movie or store from TMDb data/API."""
        # Check if movie exists
        movie = self.movie_service.get_movie_by_tmdb_id(tmdb_id)
        if movie:
            return movie

        if tmdb_data:
            try:
                stored_movie = self.movie_service._store_basic_movie(tmdb_data)
                if stored_movie:
                    logger.info(f"Stored movie from data: {stored_movie.title}")
                    return stored_movie
            except Exception as e:
                logger.warning(f"Failed to store movie from data: {e}")

        try:
            synced_movie = self.movie_service.sync_movie_from_tmdb(tmdb_id)
            if synced_movie:
                logger.info(f"Synced movie from TMDb: {synced_movie.title}")
                return synced_movie
        except Exception as e:
            logger.warning(f"Failed to sync movie {tmdb_id}: {e}")

        return None

    def _passes_filters(self, movie: Movie, params: Dict) -> bool:
        """Check if movie passes quality filters."""
        return (
            movie.vote_average >= params["min_rating"]
            and movie.vote_count >= 10  # Minimum votes for reliability
        )

    def _format_movie_basic(self, movie: Movie) -> Dict:
        """Format basic movie info."""
        return {
            "id": movie.id,
            "tmdb_id": movie.tmdb_id,
            "title": movie.title,
            "release_year": movie.release_year,
            "vote_average": movie.vote_average,
            "poster_url": movie.get_poster_url("w185") if movie.poster_path else None,
        }

    def _build_cache_key(self, endpoint: str, pk: int, params: Dict) -> str:
        """Build cache key from parameters."""
        import hashlib

        key_parts = [
            endpoint,
            str(pk),
            str(params["limit"]),
            str(params["min_rating"]),
        ]
        key_string = "|".join(key_parts)
        hash_key = hashlib.md5(key_string.encode()).hexdigest()[:8]
        return f"movie_{endpoint}:{hash_key}"


# =========================================================================
# MOVIE RECOMMENDATIONS VIEW
# =========================================================================


class MovieRecommendationsView(BaseMovieRelationshipView):
    """Get movie recommendations with automatic storage."""

    permission_classes = [AllowAny]
    movie_service = MovieService()
    recommendation_service = RecommendationService()

    @extend_schema(
        summary="Get movie recommendations",
        description="Get personalized movie recommendations based on a specific movie",
        parameters=[
            OpenApiParameter(
                "limit",
                OpenApiTypes.INT,
                description="Max recommendations (default: 10, max: 50)",
            ),
            OpenApiParameter(
                "min_rating",
                OpenApiTypes.NUMBER,
                description="Minimum rating 0-10 (default: 6.0)",
            ),
            OpenApiParameter(
                "force_sync",
                OpenApiTypes.BOOL,
                description="Skip cache and get fresh data",
            ),
        ],
        responses={200: MovieSimpleSerializer(many=True)},
        tags=["Movies - Relationships"],
    )
    def get(self, request, pk) -> Response:
        """Get movie recommendations with smart storage."""
        try:
            # Parse and validate parameters
            params = self._parse_parameters(request)
            if isinstance(params, Response):
                return params

            # Check cache unless force_sync
            if not params["force_sync"]:
                cache_key = self._build_cache_key("recommendations", pk, params)
                cached_data = cache.get(cache_key)
                if cached_data:
                    return APIResponse.success("Recommendations (cached)", cached_data)

            # Get or sync movie
            movie = self._get_or_sync_movie(pk)
            if isinstance(movie, Response):
                return movie

            # Get recommendations with storage
            recommendations = self._get_recommendations_with_storage(movie, params)

            # Build response
            response_data = {
                "source_movie": self._format_movie_basic(movie),
                "recommendations": MovieSimpleSerializer(
                    recommendations, many=True
                ).data,
                "total_count": len(recommendations),
                "filters_applied": {
                    "min_rating": params["min_rating"],
                    "limit": params["limit"],
                },
                "data_source": "TMDb API + Local Storage",
                "fetched_at": timezone.now().isoformat(),
            }

            # Cache for 2 hours
            if not params["force_sync"]:
                cache_key = self._build_cache_key("recommendations", pk, params)
                cache.set(cache_key, response_data, 60 * 60 * 2)

            message = (
                f"Found {len(recommendations)} recommendations for '{movie.title}'"
            )
            return APIResponse.success(message, response_data)

        except Exception as e:
            logger.error(f"Movie recommendations error: {e}")
            return APIResponse.server_error("Failed to get recommendations")

    def _get_recommendations_with_storage(
        self, movie: Movie, params: Dict
    ) -> List[Movie]:
        """Get recommendations from TMDb and store missing movies."""
        try:
            # Get TMDb recommendations
            tmdb_data = self.movie_service.tmdb.movies.get_recommendations(
                movie_id=movie.tmdb_id, page=1
            )

            recommendations = []

            if tmdb_data and tmdb_data.get("results"):
                for rec_data in tmdb_data["results"][: params["limit"] * 2]:
                    rec_tmdb_id = rec_data.get("tmdb_id") or rec_data.get("id")

                    if rec_tmdb_id:
                        # Get existing or store new movie
                        rec_movie = self._get_or_store_movie(rec_tmdb_id, rec_data)

                        if rec_movie and self._passes_filters(rec_movie, params):
                            recommendations.append(rec_movie)

                            if len(recommendations) >= params["limit"]:
                                break

            return recommendations

        except Exception as e:
            logger.error(f"Failed to get recommendations with storage: {e}")
            return []


# =========================================================================
# SIMILAR MOVIES VIEW
# =========================================================================


class SimilarMoviesView(BaseMovieRelationshipView):
    """Get similar movies with automatic storage."""

    permission_classes = [AllowAny]
    movie_service = MovieService()
    recommendation_service = RecommendationService()

    @extend_schema(
        summary="Get similar movies",
        description="Get movies similar to a specific movie based on TMDb algorithm",
        parameters=[
            OpenApiParameter(
                "limit",
                OpenApiTypes.INT,
                description="Max similar movies (default: 12, max: 50)",
            ),
            OpenApiParameter(
                "min_rating",
                OpenApiTypes.NUMBER,
                description="Minimum rating 0-10 (default: 5.0)",
            ),
            OpenApiParameter(
                "force_sync",
                OpenApiTypes.BOOL,
                description="Skip cache and get fresh data",
            ),
        ],
        responses={200: MovieSimpleSerializer(many=True)},
        tags=["Movies - Relationships"],
    )
    def get(self, request, pk) -> Response:
        """Get similar movies with smart storage."""
        try:
            # Parse and validate parameters
            params = self._parse_parameters(
                request, default_limit=12, default_rating=5.0
            )
            if isinstance(params, Response):
                return params

            # Check cache unless force_sync
            if not params["force_sync"]:
                cache_key = self._build_cache_key("similar", pk, params)
                cached_data = cache.get(cache_key)
                if cached_data:
                    return APIResponse.success("Similar movies (cached)", cached_data)

            # Get or sync movie
            movie = self._get_or_sync_movie(pk)
            if isinstance(movie, Response):
                return movie

            # Get similar movies with storage
            similar_movies = self._get_similar_with_storage(movie, params)

            # Build response
            response_data = {
                "source_movie": self._format_movie_basic(movie),
                "similar_movies": MovieSimpleSerializer(similar_movies, many=True).data,
                "total_count": len(similar_movies),
                "filters_applied": {
                    "min_rating": params["min_rating"],
                    "limit": params["limit"],
                },
                "data_source": "TMDb API + Local Storage",
                "fetched_at": timezone.now().isoformat(),
            }

            # Cache for 4 hours
            if not params["force_sync"]:
                cache_key = self._build_cache_key("similar", pk, params)
                cache.set(cache_key, response_data, 60 * 60 * 4)

            message = f"Found {len(similar_movies)} movies similar to '{movie.title}'"
            return APIResponse.success(message, response_data)

        except Exception as e:
            logger.error(f"Similar movies error: {e}")
            return APIResponse.server_error("Failed to get similar movies")

    def _get_similar_with_storage(self, movie: Movie, params: Dict) -> List[Movie]:
        """Get similar movies from TMDb and store missing movies."""
        try:
            # Get TMDb similar movies
            tmdb_data = self.movie_service.tmdb.movies.get_similar(
                movie_id=movie.tmdb_id, page=1
            )

            similar_movies = []

            if tmdb_data and tmdb_data.get("results"):
                for similar_data in tmdb_data["results"][: params["limit"] * 2]:
                    similar_tmdb_id = similar_data.get("tmdb_id") or similar_data.get(
                        "id"
                    )

                    if similar_tmdb_id:
                        # Get existing or store new movie
                        similar_movie = self._get_or_store_movie(
                            similar_tmdb_id, similar_data
                        )

                        if similar_movie and self._passes_filters(
                            similar_movie, params
                        ):
                            similar_movies.append(similar_movie)

                            if len(similar_movies) >= params["limit"]:
                                break

            return similar_movies

        except Exception as e:
            logger.error(f"Failed to get similar movies with storage: {e}")
            return []


# =========================================================================
# MOVIE GENRES VIEW
# =========================================================================


class MovieGenresView(APIView):
    """
    Get genres associated with a specific movie with intelligent fallback.
    """

    permission_classes = [AllowAny]
    movie_service = MovieService()

    @extend_schema(
        summary="Get movie genres",
        description="""
        Get all genres associated with a specific movie, including relationship details.

        **Data Strategy:**
        1. Check local database for movie and genres first
        2. If movie not found locally, sync from TMDb API
        3. Store quality movie with genres in database
        4. Apply caching for performance
        """,
        parameters=[
            OpenApiParameter(
                name="include_stats",
                description="Include statistical information for each genre (default: false)",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Basic Info", value=False),
                    OpenApiExample("With Statistics", value=True),
                ],
            ),
            OpenApiParameter(
                name="include_related",
                description="Include related movies count per genre (default: true)",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("With Related Count", value=True),
                    OpenApiExample("No Related Info", value=False),
                ],
            ),
        ],
        responses={
            200: GenreSimpleSerializer(many=True),
            404: None,
            400: None,
            500: None,
        },
        tags=["Movies - Relationships"],
    )
    def get(self, request, pk):
        """Get movie genres with intelligent database/TMDb fallback."""
        try:
            # Parse parameters
            include_stats = (
                request.query_params.get("include_stats", "false").lower() == "true"
            )
            include_related = (
                request.query_params.get("include_related", "true").lower() == "true"
            )

            # Check cache first
            cache_key = f"movie_genres_{pk}_{include_stats}_{include_related}"
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Movie genres for ID {pk} retrieved from cache")
                return APIResponse.success(
                    message="Movie genres (cached)", data=cached_data
                )

            # Step 1: Try to get movie from local database or sync from TMDb
            try:
                movie = Movie.objects.get(pk=pk, is_active=True)
                logger.info(f"Movie found in database: {movie.title}")
            except Movie.DoesNotExist:
                # Try by tmdb_id
                try:
                    movie = Movie.objects.get(tmdb_id=pk, is_active=True)
                    logger.info(f"Movie found by TMDb ID: {movie.title}")
                except Movie.DoesNotExist:
                    # Try to sync from TMDb
                    logger.info(f"Attempting to sync movie from TMDb with ID: {pk}")
                    try:
                        movie = self.movie_service.sync_movie_from_tmdb(pk)
                        if not movie:
                            return APIResponse.not_found(
                                message=f"Movie with ID {pk} not found in TMDb database",
                                extra_data={
                                    "searched_id": pk,
                                    "suggestions": [
                                        "Verify the movie ID is correct",
                                        "Check if the movie exists on TMDb",
                                        "Try searching for the movie first",
                                    ],
                                },
                            )
                        logger.info(
                            f"Successfully synced movie from TMDb: {movie.title}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to sync movie from TMDb with ID {pk}: {e}"
                        )
                        return APIResponse.server_error(
                            message="Failed to find or sync movie",
                            extra_data={"searched_id": pk, "error_type": "sync_failed"},
                        )

            # Step 2: Get movie genres
            try:
                # Get movie-genre relationships
                movie_genres = (
                    movie.movie_genres.select_related("genre")
                    .filter(is_active=True, genre__is_active=True)
                    .order_by("-is_primary", "-weight", "genre__name")
                )

                # Check if we have no genres
                if not movie_genres.exists():
                    logger.warning(f"Movie {movie.title} has no active genres")
                    # Return empty but valid response
                    response_data = {
                        "movie": {
                            "id": movie.id,
                            "tmdb_id": movie.tmdb_id,
                            "title": movie.title,
                            "release_year": movie.release_year,
                            "poster_url": movie.get_poster_url("w185"),
                        },
                        "genres": [],
                        "primary_genre": None,
                        "total_genres": 0,
                        "genre_names": [],
                        "data_source": "Local Database",
                        "metadata": {
                            "include_stats": include_stats,
                            "include_related": include_related,
                            "fetched_at": timezone.now().isoformat(),
                            "note": "Movie found but has no genres assigned",
                        },
                    }

                    return APIResponse.success(
                        message=f"Movie '{movie.title}' found but has no genres assigned",
                        data=response_data,
                    )

                # Format genre data
                genres_data = []
                for mg in movie_genres:
                    genre_info = {
                        "id": mg.genre.id,
                        "tmdb_id": mg.genre.tmdb_id,
                        "name": mg.genre.name,
                        "slug": mg.genre.slug,
                        "is_primary": mg.is_primary,
                        "weight": mg.weight,
                    }

                    # Add related movies count if requested
                    if include_related:
                        genre_info["related_movies_count"] = mg.genre.movies.filter(
                            is_active=True
                        ).count()

                    # Add statistics if requested
                    if include_stats:
                        genre_info["statistics"] = self._get_genre_statistics(mg.genre)

                    genres_data.append(genre_info)

                # Identify primary genre
                primary_genre = next((g for g in genres_data if g["is_primary"]), None)

                # Format response data
                response_data = {
                    "movie": {
                        "id": movie.id,
                        "tmdb_id": movie.tmdb_id,
                        "title": movie.title,
                        "release_year": movie.release_year,
                        "poster_url": movie.get_poster_url("w185"),
                    },
                    "genres": genres_data,
                    "primary_genre": primary_genre,
                    "total_genres": len(genres_data),
                    "genre_names": [g["name"] for g in genres_data],
                    "data_source": "Local Database",
                    "metadata": {
                        "include_stats": include_stats,
                        "include_related": include_related,
                        "fetched_at": timezone.now().isoformat(),
                    },
                }

                # Cache for 6 hours (genre relationships change rarely)
                cache.set(cache_key, response_data, 60 * 60 * 6)

                logger.info(f"Retrieved {len(genres_data)} genres for {movie.title}")

                return APIResponse.success(
                    message=f"Found {len(genres_data)} genres for '{movie.title}'",
                    data=response_data,
                )

            except Exception as e:
                logger.error(f"Failed to get genres for movie {movie.title}: {e}")
                return APIResponse.server_error(
                    message="Movie genres temporarily unavailable",
                    extra_data={"movie_title": movie.title},
                )

        except Exception as e:
            logger.error(f"Movie genres error: {e}")
            return APIResponse.server_error(message="Failed to get movie genres")

    def _get_genre_statistics(self, genre) -> Dict:
        """Get statistical information for a genre."""
        try:
            from django.db.models import Avg, Count, Sum

            stats = genre.movies.filter(is_active=True).aggregate(
                total_movies=Count("id"),
                avg_rating=Avg("vote_average"),
                total_revenue=Sum("revenue"),
                avg_popularity=Avg("popularity"),
            )

            return {
                "total_movies": stats["total_movies"] or 0,
                "average_rating": round(stats["avg_rating"] or 0, 2),
                "total_revenue": stats["total_revenue"] or 0,
                "average_popularity": round(stats["avg_popularity"] or 0, 2),
            }

        except Exception as e:
            logger.warning(f"Failed to get genre statistics: {e}")
            return {
                "total_movies": 0,
                "average_rating": 0.0,
                "total_revenue": 0,
                "average_popularity": 0.0,
            }
