"""
Custom manager for Favorite models.
"""

from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone

from core.mixins.managers import BaseManager


class FavoriteManager(BaseManager):
    """
    Custom manager for Favorite model with business logic methods.
    """

    def get_queryset(self):
        """Override to include select_related for common queries."""
        return (
            super()
            .get_queryset()
            .select_related("user", "movie")
            .prefetch_related("movie__genres")
        )

    # ================================================================
    # USER-SPECIFIC QUERIES
    # ================================================================

    def for_user(self, user):
        """Get all active favorites for a specific user."""
        return self.filter(user=user, is_active=True)

    def user_has_favorited(self, user, movie):
        """Check if user has favorited a specific movie."""
        return self.filter(user=user, movie=movie, is_active=True).exists()

    def user_favorites_count(self, user):
        """Get count of user's active favorites."""
        return self.for_user(user).count()

    def user_watchlist(self, user):
        """Get user's watchlist (movies they want to watch)."""
        return (
            self.for_user(user).filter(is_watchlist=True).order_by("-first_favorited")
        )

    def user_rated_movies(self, user, min_rating=None):
        """Get user's rated favorites, optionally filtered by minimum rating."""
        queryset = self.for_user(user).filter(user_rating__isnull=False)
        if min_rating:
            queryset = queryset.filter(user_rating__gte=min_rating)
        return queryset.order_by("-user_rating", "-last_interaction")

    def user_recent_favorites(self, user, days=30):
        """Get user's recent favorites."""
        cutoff = timezone.now() - timedelta(days=days)
        return (
            self.for_user(user)
            .filter(first_favorited__gte=cutoff)
            .order_by("-first_favorited")
        )

    def user_genre_preferences(self, user):
        """
        Get user's genre preferences based on their favorites.
        Returns genres ordered by how often user favorites movies in that genre.
        """
        from apps.movies.models import Genre

        return (
            Genre.objects.filter(
                movies__favorited_by__user=user,
                movies__favorited_by__is_active=True,
                is_active=True,
            )
            .annotate(favorite_count=Count("movies__favorited_by"))
            .order_by("-favorite_count", "name")
        )

    # ================================================================
    # MOVIE-SPECIFIC QUERIES (ESSENTIAL)
    # ================================================================

    def for_movie(self, movie):
        """Get all active favorites for a specific movie."""
        return self.filter(movie=movie, is_active=True)

    def movie_popularity_stats(self, movie):
        """Get popularity metrics for a movie based on favorites."""
        favorites = self.for_movie(movie)
        return {
            "total_favorites": favorites.count(),
            "average_user_rating": favorites.aggregate(avg_rating=Avg("user_rating"))[
                "avg_rating"
            ],
            "recent_favorites_count": favorites.filter(
                first_favorited__gte=timezone.now() - timedelta(days=30)
            ).count(),
        }

    def most_favorited_movies(self, limit=20, days=None):
        """Get most favorited movies, optionally within a time period."""
        queryset = self.filter(is_active=True)

        if days:
            cutoff = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(first_favorited__gte=cutoff)

        return (
            queryset.values("movie")
            .annotate(favorite_count=Count("id"), avg_rating=Avg("user_rating"))
            .order_by("-favorite_count")[:limit]
        )

    # ================================================================
    # ANALYTICS (FOR DASHBOARD)
    # ================================================================

    def user_activity_stats(self, user):
        """Get comprehensive stats for a user's favorite activity."""
        favorites = self.for_user(user)

        return {
            "total_favorites": favorites.count(),
            "watchlist_count": favorites.filter(is_watchlist=True).count(),
            "rated_count": favorites.filter(user_rating__isnull=False).count(),
            "average_rating": favorites.aggregate(avg=Avg("user_rating"))["avg"],
            "recent_count": favorites.filter(
                first_favorited__gte=timezone.now() - timedelta(days=30)
            ).count(),
            "top_genres": list(
                self.user_genre_preferences(user)[:5].values_list("name", flat=True)
            ),
        }

    # ================================================================
    # SEARCH & FILTERING
    # ================================================================

    def search_user_favorites(self, user, query):
        """Search within user's favorites by movie title."""
        return (
            self.for_user(user)
            .filter(
                Q(movie__title__icontains=query)
                | Q(movie__original_title__icontains=query)
                | Q(notes__icontains=query)
            )
            .order_by("-last_interaction")
        )

    def filter_by_genres(self, user, genre_ids):
        """Filter user's favorites by genre IDs."""
        if not isinstance(genre_ids, (list, tuple)):
            genre_ids = [genre_ids]

        return (
            self.for_user(user)
            .filter(movie__genres__tmdb_id__in=genre_ids)
            .distinct()
            .order_by("-last_interaction")
        )
