"""
TMDb Service Package
"""

from .base import BaseTMDbService
from .client import TMDbClient
from .movies import MovieService

# Default service instances
tmdb_client = TMDbClient()
movie_service = MovieService(tmdb_client)


class TMDbService:
    """
    Main TMDb service that provides access to all sub-services.

    This is the primary interface for TMDb operations.
    Use this class for most TMDb interactions.
    """

    def __init__(self):
        self.client = tmdb_client
        self.movies = movie_service
        # Future services will be added here:
        # self.people = person_service
        # self.tv = tv_service
        # self.collections = collection_service

    # ================================================================
    # CONVENIENCE METHODS - Delegate to sub-services
    # ================================================================

    def get_movie_details(self, tmdb_id: int, **kwargs):
        """Get detailed movie information"""
        return self.movies.get_details(tmdb_id, **kwargs)

    def search_movies(self, query: str, **kwargs):
        """Search for movies"""
        return self.movies.search(query, **kwargs)

    def get_popular_movies(self, **kwargs):
        """Get popular movies"""
        return self.movies.get_popular(**kwargs)

    def get_trending_movies(self, **kwargs):
        """Get trending movies"""
        return self.movies.get_trending(**kwargs)

    def get_movie_recommendations(self, movie_id: int, **kwargs):
        """Get movie recommendations"""
        return self.movies.get_recommendations(movie_id, **kwargs)

    def get_similar_movies(self, movie_id: int, **kwargs):
        """Get similar movies"""
        return self.movies.get_similar(movie_id, **kwargs)

    def get_genres_list(self, **kwargs):
        """Get movie genres list"""
        return self.movies.get_genres_list(**kwargs)

    def test_connection(self):
        """Test TMDb API connection"""
        return self.client.test_connection()

    def get_service_health(self):
        """Get overall service health status"""
        from django.utils import timezone

        return {
            "client_status": self.client.test_connection(),
            "movie_service_status": self.movies.test_service(),
            "overall_status": "healthy",
            "timestamp": timezone.now().isoformat(),
        }


# Default service instance
tmdb_service = TMDbService()

# ================================================================
# CONVENIENCE FUNCTIONS - For direct import and quick usage
# ================================================================


def get_movie_details(tmdb_id: int, **kwargs):
    """Convenience function to get movie details"""
    return tmdb_service.get_movie_details(tmdb_id, **kwargs)


def search_movies(query: str, **kwargs):
    """Convenience function to search movies"""
    return tmdb_service.search_movies(query, **kwargs)


def get_popular_movies(**kwargs):
    """Convenience function to get popular movies"""
    return tmdb_service.get_popular_movies(**kwargs)


def get_trending_movies(**kwargs):
    """Convenience function to get trending movies"""
    return tmdb_service.get_trending_movies(**kwargs)


def get_genres(**kwargs):
    """Convenience function to get genres list"""
    return tmdb_service.get_genres_list(**kwargs)


__all__ = [
    # Main classes
    "TMDbService",
    "TMDbClient",
    "BaseTMDbService",
    "MovieService",
    # Default instance
    "tmdb_service",
    # Convenience functions
    "get_movie_details",
    "search_movies",
    "get_popular_movies",
    "get_trending_movies",
    "get_genres",
    "test_tmdb_connection",
]
