"""
Discovert Views
"""

import logging
from typing import Dict, List

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from django.core.cache import cache
from django.utils import timezone

from apps.movies.models import Movie
from apps.movies.serializers import MovieListSerializer, MovieSearchSerializer
from apps.movies.services import MovieService
from core.constants import TMDBTimeWindow
from core.responses import APIResponse

logger = logging.getLogger(__name__)

# =========================================================================
# MOVIE SEARCH VIEW
# =========================================================================


class MovieSearchView(APIView):
    """
    Search movies and optionally store popular results in database.
    """

    permission_classes = [AllowAny]
    movie_service = MovieService()

    @extend_schema(
        summary="Search movies",
        description="""
        Search for movies across title, original title, and overview using TMDb API.

        **Features:**
        - Full-text search across multiple fields
        - Smart caching (2 hours) to reduce API costs
        - Optional storage of quality results in database
        - Quality filter: rating ≥ 6.0, votes ≥ 50
        - Force fresh results with force_sync parameter

        **Search Strategy:**
        1. Check cache first (unless force_sync=true)
        2. Search TMDb API (fresh results)
        3. Store quality results in database for future use
        4. Cache results to optimize costs
        """,
        parameters=[
            OpenApiParameter(
                name="q",
                description="Search query (required, minimum 2 characters)",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=True,
                examples=[
                    OpenApiExample(
                        "Movie Title",
                        value="inception",
                        description='Search for "Inception"',
                    ),
                    OpenApiExample(
                        "Actor Name",
                        value="leonardo dicaprio",
                        description="Search movies with Leonardo DiCaprio",
                    ),
                    OpenApiExample(
                        "Multiple Words",
                        value="dark knight batman",
                        description="Search with multiple keywords",
                    ),
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
                name="store_results",
                description="Store quality results in database (default: true)",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("Store Results", value=True),
                    OpenApiExample("No Storage", value=False),
                ],
            ),
            OpenApiParameter(
                name="force_sync",
                description="Force fresh data from TMDb API, bypassing"
                " cache (default: false)",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample(
                        "Use Cache", value=False, description="Use cached data (faster)"
                    ),
                    OpenApiExample(
                        "Force Fresh Data",
                        value=True,
                        description="Get fresh data from TMDb API (slower)",
                    ),
                ],
            ),
        ],
        responses={
            200: MovieSearchSerializer(many=True),
            400: None,
            500: None,
        },
        tags=["Movies - Discovery"],
    )
    def get(self, request):
        """Search movies and store quality results."""
        try:
            # Validate query
            query = request.query_params.get("q", "").strip()
            if len(query) < 2:
                return APIResponse.validation_error(
                    message="Search query must be at least 2 characters",
                    field_errors={"q": ["Minimum 2 characters required"]},
                )

            page = int(request.query_params.get("page", 1))
            store_results = (
                request.query_params.get("store_results", "true").lower() == "true"
            )
            force_sync = (
                request.query_params.get("force_sync", "false").lower() == "true"
            )

            # Check cache first (unless force_sync is enabled)
            cache_key = f"search_{query}_{page}".replace(" ", "_")

            if not force_sync:
                cached_results = cache.get(cache_key)
                if cached_results:
                    logger.info(f"Search results retrieved from cache for: '{query}'")
                    return APIResponse.success(
                        message=f"Found {len(cached_results['results'])} movies (cached)",
                        data=cached_results,
                    )
            else:
                logger.info(
                    f"Force sync enabled - bypassing cache for search: '{query}'"
                )

            # Search TMDb API
            try:
                search_results = self.movie_service.search_movies(query, page=page)
                api_results = search_results.get("results", [])

                # Store quality results in database (in background)
                if store_results and api_results:
                    stored_count = self._store_quality_search_results(
                        query, api_results
                    )
                    search_results["stored_in_db"] = stored_count

                # Cache results for 2 hours (even with force_sync to benefit next requests)
                cache.set(cache_key, search_results, 60 * 60 * 2)

                result_count = len(api_results)
                sync_message = " (force synced)" if force_sync else ""

                logger.info(
                    f"Search completed for '{query}': {result_count} results{sync_message}"
                )

                return APIResponse.success(
                    message=f"Found {result_count} movies matching '{query}'{sync_message}",
                    data=search_results,
                )

            except Exception as e:
                logger.error(f"Search failed for '{query}': {e}")
                return APIResponse.server_error(
                    message="Search temporarily unavailable"
                )

        except ValueError:
            return APIResponse.validation_error(
                message="Invalid page number",
                field_errors={"page": ["Must be a valid integer"]},
            )
        except Exception as e:
            logger.error(f"Search error: {e}")
            return APIResponse.server_error(message="Search failed")

    # _store_quality_search_results method remains the same as before
    def _store_quality_search_results(self, query: str, api_results: List[Dict]) -> int:
        """Store quality search results in database (runs synchronously for now)."""
        try:
            stored_count = 0

            # Only store top 5 results that meet quality criteria
            for result in api_results[:5]:
                tmdb_id = result.get("tmdb_id")
                vote_average = result.get("vote_average", 0)
                vote_count = result.get("vote_count", 0)

                # Quality filter: decent rating and some votes
                if tmdb_id and vote_average >= 6.0 and vote_count >= 50:
                    try:
                        # Check if already exists
                        if not Movie.objects.filter(tmdb_id=tmdb_id).exists():
                            # Store in database
                            movie = self.movie_service.sync_movie_from_tmdb(tmdb_id)
                            if movie:
                                stored_count += 1
                                logger.info(
                                    f"Stored quality search result: {movie.title}"
                                )
                    except Exception as e:
                        logger.warning(f"Failed to store movie {tmdb_id}: {e}")
                        continue

            if stored_count > 0:
                logger.info(
                    f"Stored {stored_count} quality movies from search '{query}'"
                )

            return stored_count

        except Exception as e:
            logger.warning(f"Error storing search results for '{query}': {e}")
            return 0


# =========================================================================
# TRENDING MOVIES VIEW
# =========================================================================


class TrendingMoviesView(APIView):
    """Get trending movies from TMDb API with smart caching."""

    permission_classes = [AllowAny]
    movie_service = MovieService()

    @extend_schema(
        summary="Get trending movies",
        description="""
        Get currently trending movies from TMDb API.

        **Data Source:** TMDb API (fresh data when force_sync=true)
        **Caching Strategy:** 1 hour (daily) / 6 hours (weekly)
        **Cost Optimization:** Aggressive caching reduces API calls

        **Time Windows:**
        - 'day': Movies trending in the last 24 hours
        - 'week': Movies trending in the last 7 days

        Returns up to 20 movies per request with pagination info.
        """,
        parameters=[
            OpenApiParameter(
                name="time_window",
                description="Trending time window",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=["day", "week"],
                default="day",
                required=False,
                examples=[
                    OpenApiExample(
                        "Daily Trending",
                        value="day",
                        description="Movies trending in the last 24 hours",
                    ),
                    OpenApiExample(
                        "Weekly Trending",
                        value="week",
                        description="Movies trending in the last 7 days",
                    ),
                ],
            ),
            OpenApiParameter(
                name="force_sync",
                description="Force fresh data from TMDb API, bypassing cache (default: false)",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample(
                        "Use Cache", value=False, description="Use cached data (faster)"
                    ),
                    OpenApiExample(
                        "Force Fresh Data",
                        value=True,
                        description="Get fresh data from TMDb API (slower)",
                    ),
                ],
            ),
        ],
        responses={
            200: MovieListSerializer(many=True),
            400: None,
            500: None,
        },
        tags=["Movies - Discovery"],
    )
    def get(self, request):
        """Get trending movies with optional force sync."""
        try:
            time_window = request.query_params.get("time_window", "day").lower()
            force_sync = (
                request.query_params.get("force_sync", "false").lower() == "true"
            )

            if time_window not in ["day", "week"]:
                return APIResponse.validation_error(
                    message="Invalid time window",
                    field_errors={"time_window": ["Must be 'day' or 'week'"]},
                )

            # Check cache first (unless force_sync is enabled)
            cache_key = f"trending_{time_window}"

            if not force_sync:
                cached_data = cache.get(cache_key)
                if cached_data:
                    logger.info(f"Trending movies ({time_window}) retrieved from cache")
                    return APIResponse.success(
                        message=f"Trending movies ({time_window}) - cached",
                        data=cached_data,
                    )
            else:
                logger.info(
                    f"Force sync enabled - bypassing cache for trending ({time_window})"
                )

            # Get from TMDb API
            try:
                time_window_enum = (
                    TMDBTimeWindow.DAY if time_window == "day" else TMDBTimeWindow.WEEK
                )
                trending_data = self.movie_service.get_trending_movies(
                    time_window=time_window_enum
                )

                # Add metadata
                trending_data["time_window"] = time_window
                trending_data["data_source"] = "TMDb API"
                trending_data["fetched_at"] = timezone.now().isoformat()
                trending_data["force_sync"] = force_sync

                # Cache for 1 hour (day) or 6 hours (week) - even with force_sync
                cache_timeout = 60 * 60 if time_window == "day" else 60 * 60 * 6
                cache.set(cache_key, trending_data, cache_timeout)

                result_count = len(trending_data.get("results", []))
                sync_message = " (force synced)" if force_sync else ""

                logger.info(
                    f"Trending movies ({time_window}): {result_count} results{sync_message}"
                )

                return APIResponse.success(
                    message=f"Retrieved {result_count} trending movies ({time_window}){sync_message}",
                    data=trending_data,
                )

            except Exception as e:
                logger.error(f"TMDb trending API failed: {e}")
                return APIResponse.server_error(
                    message="Trending movies temporarily unavailable",
                    extra_data={
                        "suggestions": [
                            "Try again in a few minutes",
                            "Check TMDb API status",
                            "Try the popular movies endpoint instead",
                        ]
                    },
                )

        except Exception as e:
            logger.error(f"Trending movies error: {e}")
            return APIResponse.server_error(message="Failed to get trending movies")


# =========================================================================
# POPULAR MOVIES VIEW
# =========================================================================


class PopularMoviesView(APIView):
    """Get popular movies from TMDb API with smart caching."""

    permission_classes = [AllowAny]
    movie_service = MovieService()

    @extend_schema(
        summary="Get popular movies",
        description="""
        Get currently popular movies from TMDb API.

        **Data Source:** TMDb API
        **Caching Strategy:** 6 hours (popularity changes slowly)
        **Pagination:** 20 movies per page
        """,
        parameters=[
            OpenApiParameter(
                name="page",
                description="Page number (default: 1, max: 500)",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("First Page", value=1),
                    OpenApiExample("Second Page", value=2),
                    OpenApiExample("Page 10", value=10),
                ],
            ),
            OpenApiParameter(
                name="force_sync",
                description="Force fresh data from TMDb API, bypassing cache (default: false)",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample(
                        "Use Cache", value=False, description="Use cached data (faster)"
                    ),
                    OpenApiExample(
                        "Force Fresh Data",
                        value=True,
                        description="Get fresh data from TMDb API (slower)",
                    ),
                ],
            ),
        ],
        responses={
            200: MovieListSerializer(many=True),
            400: None,
            500: None,
        },
        tags=["Movies - Discovery"],
    )
    def get(self, request):
        """Get popular movies with optional force sync."""
        try:
            page = int(request.query_params.get("page", 1))
            force_sync = (
                request.query_params.get("force_sync", "false").lower() == "true"
            )

            # Validate page number
            if page < 1 or page > 500:
                return APIResponse.validation_error(
                    message="Invalid page number",
                    field_errors={"page": ["Page must be between 1 and 500"]},
                )

            cache_key = f"popular_movies_{page}"

            # Check cache first (unless force_sync is enabled)
            if not force_sync:
                cached_data = cache.get(cache_key)
                if cached_data:
                    logger.info(f"Popular movies page {page} retrieved from cache")
                    return APIResponse.success(
                        message="Popular movies (cached)", data=cached_data
                    )
            else:
                logger.info(
                    f"Force sync enabled - bypassing cache for popular movies page {page}"
                )

            # Get fresh data from TMDb API
            try:
                popular_data = self.movie_service.get_popular_movies(page=page)

                # Add metadata
                popular_data["data_source"] = "TMDb API"
                popular_data["fetched_at"] = timezone.now().isoformat()
                popular_data["force_sync"] = force_sync

                # Cache for 6 hours (always cache, even with force_sync)
                cache.set(cache_key, popular_data, 60 * 60 * 6)

                result_count = len(popular_data.get("results", []))
                sync_message = " (force synced)" if force_sync else ""

                logger.info(
                    f"Popular movies page {page}: {result_count} results{sync_message}"
                )

                return APIResponse.success(
                    message=f"Retrieved {result_count} popular movies{sync_message}",
                    data=popular_data,
                )

            except Exception as e:
                logger.error(f"TMDb popular API failed: {e}")
                return APIResponse.server_error(
                    message="Popular movies temporarily unavailable"
                )

        except ValueError:
            return APIResponse.validation_error(
                message="Invalid page number",
                field_errors={"page": ["Must be a valid integer"]},
            )
        except Exception as e:
            logger.error(f"Popular movies error: {e}")
            return APIResponse.server_error(message="Failed to get popular movies")


# =========================================================================
# TOP RATED MOVIES VIEW
# =========================================================================


class TopRatedMoviesView(APIView):
    """Get top-rated movies from TMDb API with smart caching."""

    permission_classes = [AllowAny]
    movie_service = MovieService()

    @extend_schema(
        summary="Get top-rated movies",
        description="""
        Get highest-rated movies from TMDb API.

        **Data Source:** TMDb API (fresh data when force_sync=true)
        **Caching Strategy:** 12 hours (top-rated changes very slowly)
        **Pagination:** 20 movies per page

        **Features:**
        - Force fresh data with force_sync parameter
        - Automatic caching for performance
        - Validated page numbers (1-500)

        Top-rated movies are determined by:
        - User vote average (minimum 8.0+ typically)
        - Minimum vote count threshold
        - Quality and reliability of ratings

        Perfect for discovering critically acclaimed films and classics.
        """,
        parameters=[
            OpenApiParameter(
                name="page",
                description="Page number (default: 1, max: 500)",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample("First Page", value=1),
                    OpenApiExample("Second Page", value=2),
                    OpenApiExample("Top 100 (Page 5)", value=5),
                ],
            ),
            OpenApiParameter(
                name="force_sync",
                description="Force fresh data from TMDb API, bypassing cache (default: false)",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                examples=[
                    OpenApiExample(
                        "Use Cache", value=False, description="Use cached data (faster)"
                    ),
                    OpenApiExample(
                        "Force Fresh Data",
                        value=True,
                        description="Get fresh data from TMDb API (slower)",
                    ),
                ],
            ),
        ],
        responses={
            200: MovieListSerializer(many=True),
            400: None,
            500: None,
        },
        tags=["Movies - Discovery"],
    )
    def get(self, request):
        """Get top-rated movies with optional force sync."""
        try:
            page = int(request.query_params.get("page", 1))
            force_sync = (
                request.query_params.get("force_sync", "false").lower() == "true"
            )

            # Validate page number
            if page < 1 or page > 500:
                return APIResponse.validation_error(
                    message="Invalid page number",
                    field_errors={"page": ["Page must be between 1 and 500"]},
                )

            # Check cache first (unless force_sync is enabled)
            cache_key = f"top_rated_movies_{page}"

            if not force_sync:
                cached_data = cache.get(cache_key)
                if cached_data:
                    logger.info(f"Top-rated movies page {page} retrieved from cache")
                    return APIResponse.success(
                        message="Top-rated movies (cached)", data=cached_data
                    )
            else:
                logger.info(
                    f"Force sync enabled - bypassing cache for top-rated page {page}"
                )

            # Get from TMDb API
            try:
                top_rated_data = self.movie_service.get_top_rated_movies(page=page)

                # Add metadata
                top_rated_data["data_source"] = "TMDb API"
                top_rated_data["fetched_at"] = timezone.now().isoformat()
                top_rated_data["force_sync"] = force_sync

                # Cache for 12 hours (top-rated changes slowly) - even with force_sync
                cache.set(cache_key, top_rated_data, 60 * 60 * 12)

                result_count = len(top_rated_data.get("results", []))
                sync_message = " (force synced)" if force_sync else ""

                logger.info(
                    f"Top-rated movies page {page}: {result_count} results{sync_message}"
                )

                return APIResponse.success(
                    message=f"Retrieved {result_count} top-rated movies{sync_message}",
                    data=top_rated_data,
                )

            except Exception as e:
                logger.error(f"TMDb top-rated API failed: {e}")
                return APIResponse.server_error(
                    message="Top-rated movies temporarily unavailable"
                )

        except ValueError:
            return APIResponse.validation_error(
                message="Invalid page number",
                field_errors={"page": ["Must be a valid integer"]},
            )
        except Exception as e:
            logger.error(f"Top-rated movies error: {e}")
            return APIResponse.server_error(message="Failed to get top-rated movies")
