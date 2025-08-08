"""
Simplified Discovery Views using centralized logic
"""

import logging

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.response import Response

from apps.movies.serializers import MovieListSerializer, MovieSearchSerializer
from apps.movies.views.base_discovery import BaseDiscoveryView
from core.responses import APIResponse

logger = logging.getLogger(__name__)


class MovieSearchView(BaseDiscoveryView):
    """Search movies with centralized storage logic"""

    @extend_schema(
        summary="Search movies",
        description="Search movies with automatic partial data storage",
        parameters=[
            OpenApiParameter(
                "q", OpenApiTypes.STR, required=True, description="Search query"
            ),
            OpenApiParameter("page", OpenApiTypes.INT, description="Page number"),
            OpenApiParameter(
                "store_results", OpenApiTypes.BOOL, description="Store results"
            ),
            OpenApiParameter(
                "force_sync", OpenApiTypes.BOOL, description="Force fresh data"
            ),
        ],
        responses={200: MovieSearchSerializer(many=True)},
        tags=["Movies - Discovery"],
    )
    def get(self, request) -> Response:
        # Validate query
        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return APIResponse.validation_error(
                "Search query must be at least 2 characters",
                {"q": ["Minimum 2 characters required"]},
            )

        # Parse params
        page = int(request.query_params.get("page", 1))
        store_results = (
            request.query_params.get("store_results", "true").lower() == "true"
        )
        force_sync = request.query_params.get("force_sync", "false").lower() == "true"

        # Validate page
        if not 1 <= page <= 500:
            return APIResponse.validation_error(
                "Invalid page number", {"page": ["Page must be between 1 and 500"]}
            )

        return self.handle_discovery_request(
            get_data_func=lambda: self.movie_service.search_movies(
                query, page=page, sync_results=store_results
            )
        )


class TrendingMoviesView(BaseDiscoveryView):
    @extend_schema(
        summary="Get trending movies",
        description="Get trending movies with automatic storage",
        parameters=[
            OpenApiParameter(
                "time_window", OpenApiTypes.STR, description="'day' or 'week'"
            ),
            OpenApiParameter(
                "store_results", OpenApiTypes.BOOL, description="Store results"
            ),
        ],
        responses={200: MovieListSerializer(many=True)},
        tags=["Movies - Discovery"],
    )
    def get(self, request) -> Response:
        # Parse params
        time_window = request.query_params.get("time_window", "day").lower()
        store_results = (
            request.query_params.get("store_results", "true").lower() == "true"
        )

        if time_window not in ["day", "week"]:
            return APIResponse.validation_error(
                "Invalid time window", {"time_window": ["Must be 'day' or 'week'"]}
            )

        return self.handle_discovery_request(
            get_data_func=lambda: self.movie_service.get_trending_movies(
                time_window=time_window, store_movies=store_results
            )
        )


class PopularMoviesView(BaseDiscoveryView):
    @extend_schema(
        summary="Get popular movies",
        description="Get popular movies with automatic storage",
        parameters=[
            OpenApiParameter("page", OpenApiTypes.INT, description="Page number"),
            OpenApiParameter(
                "store_results", OpenApiTypes.BOOL, description="Store results"
            ),
        ],
        responses={200: MovieListSerializer(many=True)},
        tags=["Movies - Discovery"],
    )
    def get(self, request) -> Response:
        # Parse params
        page = int(request.query_params.get("page", 1))
        store_results = (
            request.query_params.get("store_results", "true").lower() == "true"
        )

        if not 1 <= page <= 500:
            return APIResponse.validation_error(
                "Invalid page number", {"page": ["Page must be between 1 and 500"]}
            )

        return self.handle_discovery_request(
            get_data_func=lambda: self.movie_service.get_popular_movies(
                page=page, store_movies=store_results
            )
        )


class TopRatedMoviesView(BaseDiscoveryView):
    @extend_schema(
        summary="Get top-rated movies",
        description="Get top-rated movies with automatic storage",
        parameters=[
            OpenApiParameter("page", OpenApiTypes.INT, description="Page number"),
            OpenApiParameter(
                "store_results", OpenApiTypes.BOOL, description="Store results"
            ),
        ],
        responses={200: MovieListSerializer(many=True)},
        tags=["Movies - Discovery"],
    )
    def get(self, request) -> Response:
        # Parse params
        page = int(request.query_params.get("page", 1))
        store_results = (
            request.query_params.get("store_results", "true").lower() == "true"
        )

        if not 1 <= page <= 500:
            return APIResponse.validation_error(
                "Invalid page number", {"page": ["Page must be between 1 and 500"]}
            )

        return self.handle_discovery_request(
            get_data_func=lambda: self.movie_service.get_top_rated_movies(
                page=page, store_movies=store_results
            )
        )
