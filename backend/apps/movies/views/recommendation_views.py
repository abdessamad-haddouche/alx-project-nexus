# ================================================================
# MOVIE RELATIONSHIP VIEWS
# ================================================================

import logging
from typing import Dict, List

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from django.core.cache import cache
from django.utils import timezone

from apps.movies.models import Movie
from apps.movies.serializers import GenreSimpleSerializer, MovieSimpleSerializer
from apps.movies.services import MovieService, RecommendationService
from core.responses import APIResponse

logger = logging.getLogger(__name__)

# =========================================================================
# MOVIE RECOMMENDATIONS VIEW
# =========================================================================


class MovieRecommendationsView(APIView):
    """
    Get movie recommendations based on a specific movie.
    """

    permission_classes = [AllowAny]
    movie_service = MovieService()
    recommendation_service = RecommendationService()

    @extend_schema(
        summary="Get movie recommendations",
        description="""
        Get personalized movie recommendations based on a specific movie.

        **Data Strategy:**
        1. Check local database for stored recommendations first
        2. Fall back to TMDb API for fresh recommendations
        3. Store quality recommendations in database
        4. Apply smart filtering and ranking

        **Filters:**
        - Minimum rating: 6.0+
        - Minimum votes: 50+
        - Active movies only
        - No adult content (unless requested)
        """,
        parameters=[
            OpenApiParameter(
                name="limit",
                description="Maximum number of recommendations (default: 10, max: 50)",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Default Limit", value=10),
                    OpenApiExample("More Results", value=20),
                    OpenApiExample("Maximum", value=50),
                ],
            ),
            OpenApiParameter(
                name="include_adult",
                description="Include adult content in recommendations (default: false)",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("No Adult Content", value=False),
                    OpenApiExample("Include Adult", value=True),
                ],
            ),
            OpenApiParameter(
                name="min_rating",
                description="Minimum vote average for recommendations (default: 6.0)",
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Default Quality", value=6.0),
                    OpenApiExample("High Quality", value=7.5),
                    OpenApiExample("Premium Quality", value=8.0),
                ],
            ),
            OpenApiParameter(
                name="force_sync",
                description="Force fresh data from TMDb API and store in database (default: false)",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Use Cache/DB", value=False),
                    OpenApiExample("Force TMDb API", value=True),
                ],
            ),
        ],
        responses={
            200: MovieSimpleSerializer(many=True),
            404: None,
            400: None,
            500: None,
        },
        tags=["Movies - Relationships"],
    )
    def get(self, request, pk):
        """Get movie recommendations with intelligent fallback strategy."""
        try:
            # Parse parameters first
            limit = min(int(request.query_params.get("limit", 10)), 50)
            include_adult = (
                request.query_params.get("include_adult", "false").lower() == "true"
            )
            min_rating = float(request.query_params.get("min_rating", 6.0))
            force_sync = (
                request.query_params.get("force_sync", "false").lower() == "true"
            )

            # Validate parameters
            if limit < 1:
                return APIResponse.validation_error(
                    message="Invalid limit",
                    field_errors={"limit": ["Must be at least 1"]},
                )

            if min_rating < 0 or min_rating > 10:
                return APIResponse.validation_error(
                    message="Invalid minimum rating",
                    field_errors={"min_rating": ["Must be between 0 and 10"]},
                )

            # Check cache first (unless force sync)
            cache_key = (
                f"movie_recommendations_{pk}_{limit}_{include_adult}_{min_rating}"
            )
            if not force_sync:
                cached_data = cache.get(cache_key)
                if cached_data:
                    logger.info(
                        f"Movie recommendations for ID {pk} retrieved from cache"
                    )
                    return APIResponse.success(
                        message=f"Found {len(cached_data['recommendations'])} recommendations (cached)",
                        data=cached_data,
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
                                message=f"Movie with ID {pk} not found",
                                extra_data={"searched_id": pk},
                            )
                        logger.info(f"Successfully synced movie: {movie.title}")
                    except Exception as e:
                        logger.error(f"Failed to sync movie {pk}: {e}")
                        return APIResponse.server_error(
                            message="Failed to find or sync movie",
                            extra_data={"searched_id": pk},
                        )

            # Step 2: Get recommendations
            try:
                if force_sync:
                    # Force sync: Get fresh data from TMDb API
                    logger.info(
                        f"Force sync enabled - getting fresh recommendations from TMDb for {movie.title}"
                    )
                    tmdb_recommendations = (
                        self.movie_service.tmdb.movies.get_recommendations(
                            movie_id=movie.tmdb_id, page=1
                        )
                    )

                    recommendations = []
                    if tmdb_recommendations and tmdb_recommendations.get("results"):
                        # Process TMDb results and sync movies to database
                        for rec_data in tmdb_recommendations.get("results", [])[
                            : limit * 2
                        ]:
                            rec_tmdb_id = rec_data.get("tmdb_id")
                            if rec_tmdb_id:
                                try:
                                    # Try to get existing movie or sync from TMDb
                                    rec_movie = self.movie_service.get_movie_by_tmdb_id(
                                        rec_tmdb_id
                                    )
                                    if not rec_movie:
                                        rec_movie = (
                                            self.movie_service.sync_movie_from_tmdb(
                                                rec_tmdb_id
                                            )
                                        )
                                    if rec_movie:
                                        recommendations.append(rec_movie)
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to sync recommended movie {rec_tmdb_id}: {e}"
                                    )

                    data_source = "TMDb API (Force Sync)"
                else:
                    # Normal flow: Try local DB first, fallback to TMDb if needed
                    recommendations = (
                        self.recommendation_service.get_recommendations_for_movie(
                            movie_id=movie.id, limit=limit * 2
                        )
                    )

                    if not recommendations:
                        logger.info(
                            f"No local recommendations found, fetching from TMDb for {movie.title}"
                        )
                        tmdb_recommendations = (
                            self.movie_service.tmdb.movies.get_recommendations(
                                movie_id=movie.tmdb_id, page=1
                            )
                        )

                        recommendations = []
                        if tmdb_recommendations and tmdb_recommendations.get("results"):
                            for rec_data in tmdb_recommendations.get("results", [])[
                                : limit * 2
                            ]:
                                rec_tmdb_id = rec_data.get("tmdb_id")
                                if rec_tmdb_id:
                                    try:
                                        rec_movie = (
                                            self.movie_service.get_movie_by_tmdb_id(
                                                rec_tmdb_id
                                            )
                                        )
                                        if not rec_movie:
                                            rec_movie = (
                                                self.movie_service.sync_movie_from_tmdb(
                                                    rec_tmdb_id
                                                )
                                            )
                                        if rec_movie:
                                            recommendations.append(rec_movie)
                                    except Exception as e:
                                        logger.warning(
                                            f"Failed to sync recommended movie {rec_tmdb_id}: {e}"
                                        )

                        data_source = "TMDb API (Fallback)"
                    else:
                        data_source = "Local Database"

                # Apply filters
                filtered_recommendations = self._apply_recommendation_filters(
                    recommendations, min_rating=min_rating, include_adult=include_adult
                )[:limit]

                # Format response data
                response_data = {
                    "source_movie": {
                        "id": movie.id,
                        "tmdb_id": movie.tmdb_id,
                        "title": movie.title,
                        "release_year": movie.release_year,
                        "vote_average": movie.vote_average,
                        "poster_url": movie.get_poster_url("w185"),
                    },
                    "recommendations": MovieSimpleSerializer(
                        filtered_recommendations, many=True
                    ).data,
                    "total_count": len(filtered_recommendations),
                    "filters_applied": {
                        "min_rating": min_rating,
                        "include_adult": include_adult,
                        "limit": limit,
                    },
                    "data_source": data_source,
                    "fetched_at": timezone.now().isoformat(),
                    "force_sync": force_sync,
                }

                # Cache for 2 hours
                cache.set(cache_key, response_data, 60 * 60 * 2)

                logger.info(
                    f"Generated {len(filtered_recommendations)} recommendations for {movie.title}"
                )

                return APIResponse.success(
                    message=f"Found {len(filtered_recommendations)} recommendations for '{movie.title}'",
                    data=response_data,
                )

            except Exception as e:
                logger.error(f"Failed to get recommendations for movie {pk}: {e}")
                return APIResponse.server_error(
                    message="Recommendations temporarily unavailable",
                    extra_data={"movie_title": movie.title},
                )

        except ValueError as e:
            return APIResponse.validation_error(
                message="Invalid parameter value", field_errors={"parameter": [str(e)]}
            )
        except Exception as e:
            logger.error(f"Movie recommendations error: {e}")
            return APIResponse.server_error(message="Failed to get recommendations")

    def _apply_recommendation_filters(
        self, movies: List[Movie], min_rating: float, include_adult: bool
    ) -> List[Movie]:
        """Apply quality and content filters to recommendations."""
        filtered = []

        for movie in movies:
            # Skip adult content
            if not include_adult and movie.adult:
                continue

            # Apply rating filter
            if movie.vote_average < min_rating:
                continue

            # Ensure minimum vote count for reliability
            if movie.vote_count < 20:
                continue

            filtered.append(movie)

        return filtered


# =========================================================================
# SIMILAR MOVIES VIEW
# =========================================================================


class SimilarMoviesView(APIView):
    """
    Get movies similar to a specific movie.
    """

    permission_classes = [AllowAny]
    movie_service = MovieService()
    recommendation_service = RecommendationService()

    @extend_schema(
        summary="Get similar movies",
        description="""
        Get movies similar to a specific movie based on multiple similarity factors.

        **Data Strategy:**
        1. Check local database for TMDb similar movies
        2. Supplement with genre-based similar movies
        3. Fall back to TMDb API if needed
        4. Store quality similar movies in database
        """,
        parameters=[
            OpenApiParameter(
                name="limit",
                description="Maximum number of similar movies (default: 12, max: 50)",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Default Grid", value=12),
                    OpenApiExample("Extended List", value=24),
                    OpenApiExample("Maximum", value=50),
                ],
            ),
            OpenApiParameter(
                name="similarity_threshold",
                description="Minimum similarity score (0.0-1.0, default: 0.3)",
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Loose Similarity", value=0.2),
                    OpenApiExample("Default", value=0.3),
                    OpenApiExample("High Similarity", value=0.6),
                ],
            ),
            OpenApiParameter(
                name="include_older",
                description="Include movies older than 10 years (default: true)",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Include Classics", value=True),
                    OpenApiExample("Recent Only", value=False),
                ],
            ),
            OpenApiParameter(
                name="force_sync",
                description="Force fresh data from TMDb API (default: false)",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Use Cache/DB", value=False),
                    OpenApiExample("Force TMDb API", value=True),
                ],
            ),
        ],
        responses={
            200: MovieSimpleSerializer(many=True),
            404: None,
            400: None,
            500: None,
        },
        tags=["Movies - Relationships"],
    )
    def get(self, request, pk):
        """Get similar movies with multi-algorithm approach."""
        try:
            # Parse parameters first
            limit = min(int(request.query_params.get("limit", 12)), 50)
            similarity_threshold = float(
                request.query_params.get("similarity_threshold", 0.3)
            )
            include_older = (
                request.query_params.get("include_older", "true").lower() == "true"
            )
            force_sync = (
                request.query_params.get("force_sync", "false").lower() == "true"
            )

            # Validate parameters
            if limit < 1:
                return APIResponse.validation_error(
                    message="Invalid limit",
                    field_errors={"limit": ["Must be at least 1"]},
                )

            if similarity_threshold < 0 or similarity_threshold > 1:
                return APIResponse.validation_error(
                    message="Invalid similarity threshold",
                    field_errors={
                        "similarity_threshold": ["Must be between 0.0 and 1.0"]
                    },
                )

            # Check cache first (unless force sync)
            cache_key = (
                f"similar_movies_{pk}_{limit}_{similarity_threshold}_{include_older}"
            )
            if not force_sync:
                cached_data = cache.get(cache_key)
                if cached_data:
                    logger.info(f"Similar movies for ID {pk} retrieved from cache")
                    return APIResponse.success(
                        message=f"Found {len(cached_data['similar_movies'])} similar movies (cached)",
                        data=cached_data,
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
                                message=f"Movie with ID {pk} not found",
                                extra_data={"searched_id": pk},
                            )
                        logger.info(f"Successfully synced movie: {movie.title}")
                    except Exception as e:
                        logger.error(f"Failed to sync movie {pk}: {e}")
                        return APIResponse.server_error(
                            message="Failed to find or sync movie",
                            extra_data={"searched_id": pk},
                        )

            # Step 2: Get similar movies
            try:
                if force_sync:
                    # Get fresh data from TMDb API
                    logger.info(
                        f"Force sync enabled - getting fresh similar movies from TMDb for {movie.title}"
                    )
                    tmdb_similar = self.movie_service.tmdb.movies.get_similar(
                        movie_id=movie.tmdb_id, page=1
                    )

                    similar_movies = []
                    if tmdb_similar and tmdb_similar.get("results"):
                        # Process TMDb results and sync movies to database
                        for similar_data in tmdb_similar.get("results", [])[
                            : limit * 2
                        ]:
                            similar_tmdb_id = similar_data.get("tmdb_id")
                            if similar_tmdb_id:
                                try:
                                    # Try to get existing movie or sync from TMDb
                                    similar_movie = (
                                        self.movie_service.get_movie_by_tmdb_id(
                                            similar_tmdb_id
                                        )
                                    )
                                    if not similar_movie:
                                        similar_movie = (
                                            self.movie_service.sync_movie_from_tmdb(
                                                similar_tmdb_id
                                            )
                                        )
                                    if similar_movie:
                                        similar_movies.append(similar_movie)
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to sync similar movie {similar_tmdb_id}: {e}"
                                    )

                    data_source = "TMDb API (Force Sync)"
                else:
                    # Normal flow: Try local DB first, fallback to TMDb if needed
                    similar_movies = self.recommendation_service.get_similar_movies(
                        movie_id=movie.id, limit=limit * 2
                    )

                    if not similar_movies:
                        logger.info(
                            f"No local similar movies found, fetching from TMDb for {movie.title}"
                        )
                        tmdb_similar = self.movie_service.tmdb.movies.get_similar(
                            movie_id=movie.tmdb_id, page=1
                        )

                        similar_movies = []
                        if tmdb_similar and tmdb_similar.get("results"):
                            for similar_data in tmdb_similar.get("results", [])[
                                : limit * 2
                            ]:
                                similar_tmdb_id = similar_data.get("tmdb_id")
                                if similar_tmdb_id:
                                    try:
                                        similar_movie = (
                                            self.movie_service.get_movie_by_tmdb_id(
                                                similar_tmdb_id
                                            )
                                        )
                                        if not similar_movie:
                                            similar_movie = (
                                                self.movie_service.sync_movie_from_tmdb(
                                                    similar_tmdb_id
                                                )
                                            )
                                        if similar_movie:
                                            similar_movies.append(similar_movie)
                                    except Exception as e:
                                        logger.warning(
                                            f"Failed to sync similar movie {similar_tmdb_id}: {e}"
                                        )

                        data_source = "TMDb API (Fallback)"
                    else:
                        data_source = "Local Database"

                # Apply filters and ranking
                filtered_similar = self._apply_similarity_filters(
                    similar_movies,
                    target_movie=movie,
                    threshold=similarity_threshold,
                    include_older=include_older,
                )[:limit]

                # Format response data
                response_data = {
                    "source_movie": {
                        "id": movie.id,
                        "tmdb_id": movie.tmdb_id,
                        "title": movie.title,
                        "release_year": movie.release_year,
                        "vote_average": movie.vote_average,
                        "genres": [
                            genre.name for genre in movie.genres.filter(is_active=True)
                        ],
                        "poster_url": movie.get_poster_url("w185"),
                    },
                    "similar_movies": MovieSimpleSerializer(
                        filtered_similar, many=True
                    ).data,
                    "total_count": len(filtered_similar),
                    "similarity_factors": [
                        "TMDb similarity algorithm",
                        "Shared genres",
                        "Similar ratings",
                        "Release period proximity",
                    ],
                    "filters_applied": {
                        "similarity_threshold": similarity_threshold,
                        "include_older": include_older,
                        "limit": limit,
                    },
                    "data_source": data_source,
                    "fetched_at": timezone.now().isoformat(),
                    "force_sync": force_sync,
                }

                # Cache for 4 hours (similar movies change less frequently)
                cache.set(cache_key, response_data, 60 * 60 * 4)

                logger.info(
                    f"Found {len(filtered_similar)} similar movies for {movie.title}"
                )

                return APIResponse.success(
                    message=f"Found {len(filtered_similar)} movies similar to '{movie.title}'",
                    data=response_data,
                )

            except Exception as e:
                logger.error(f"Failed to get similar movies for {pk}: {e}")
                return APIResponse.server_error(
                    message="Similar movies temporarily unavailable",
                    extra_data={"movie_title": movie.title},
                )

        except ValueError as e:
            return APIResponse.validation_error(
                message="Invalid parameter value", field_errors={"parameter": [str(e)]}
            )
        except Exception as e:
            logger.error(f"Similar movies error: {e}")
            return APIResponse.server_error(message="Failed to get similar movies")

    def _apply_similarity_filters(
        self,
        movies: List[Movie],
        target_movie: Movie,
        threshold: float,
        include_older: bool,
    ) -> List[Movie]:
        """Apply similarity filters and ranking."""
        from datetime import date

        filtered = []
        current_year = date.today().year

        for movie in movies:
            # Calculate basic similarity score (simplified)
            similarity_score = self._calculate_similarity_score(movie, target_movie)

            if similarity_score < threshold:
                continue

            # Age filter
            if not include_older and movie.release_date:
                if movie.release_date.year < (current_year - 10):
                    continue

            # Quality filter
            if movie.vote_average < 5.0 or movie.vote_count < 10:
                continue

            filtered.append(movie)

        # Sort by similarity score (simplified - would be more complex in production)
        return sorted(
            filtered,
            key=lambda m: (
                self._calculate_similarity_score(m, target_movie),
                m.vote_average,
                m.popularity,
            ),
            reverse=True,
        )

    def _calculate_similarity_score(self, movie1: Movie, movie2: Movie) -> float:
        """Calculate basic similarity score between two movies."""
        score = 0.0

        # Genre overlap
        movie1_genres = set(movie1.genres.values_list("tmdb_id", flat=True))
        movie2_genres = set(movie2.genres.values_list("tmdb_id", flat=True))

        if movie1_genres and movie2_genres:
            genre_overlap = len(movie1_genres & movie2_genres) / len(
                movie1_genres | movie2_genres
            )
            score += genre_overlap * 0.4

        # Rating similarity
        if movie1.vote_average > 0 and movie2.vote_average > 0:
            rating_diff = abs(movie1.vote_average - movie2.vote_average)
            rating_similarity = max(0, 1 - (rating_diff / 10))
            score += rating_similarity * 0.3

        # Popularity similarity
        if movie1.popularity > 0 and movie2.popularity > 0:
            pop_ratio = min(movie1.popularity, movie2.popularity) / max(
                movie1.popularity, movie2.popularity
            )
            score += pop_ratio * 0.3

        return min(score, 1.0)


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
