"""
Custom managers for the Movie model.
"""

from datetime import timedelta

from django.db import models
from django.utils import timezone

from core.constants import MovieStatus
from core.mixins.managers import BaseManager


class MovieManager(BaseManager):
    """
    Custom manager for Movie model with specialized query methods.
    """

    def get_queryset(self):
        """Override to include select_related for common queries."""
        return super().get_queryset().select_related().prefetch_related("genres")

    def popular(self, limit=20):
        """Get popular movies ordered by popularity."""
        return self.filter(is_active=True, popularity__gte=10.0).order_by(
            "-popularity", "-vote_average"
        )[:limit]

    def highly_rated(self, min_votes=100, limit=20):
        """Get highly rated movies with minimum vote threshold."""
        return self.filter(
            is_active=True, vote_average__gte=7.0, vote_count__gte=min_votes
        ).order_by("-vote_average", "-vote_count")[:limit]

    def recent_releases(self, limit=20):
        """Get recently released movies."""
        return self.filter(
            is_active=True, release_date__isnull=False, status=MovieStatus.RELEASED
        ).order_by("-release_date")[:limit]

    def by_genre(self, genre_ids, limit=20):
        """Get movies by genre IDs."""
        if not isinstance(genre_ids, (list, tuple)):
            genre_ids = [genre_ids]

        return (
            self.filter(is_active=True, genres__tmdb_id__in=genre_ids)
            .distinct()
            .order_by("-popularity")[:limit]
        )

    def search_by_title(self, query):
        """Search movies by title (case-insensitive)."""
        return self.filter(is_active=True, title__icontains=query).order_by(
            "-popularity", "-vote_average"
        )

    def needs_sync(self, hours=24):
        """
        Get movies that need TMDb synchronization.

        Logic:
        - Never synced movies: Always need sync
        - Failed sync movies: Always need sync
        - Released movies: Only sync if very old (7+ days) or critical data missing
        - Unreleased movies: Sync regularly (every 24h) as they get updates
        """
        cutoff = timezone.now() - timedelta(hours=hours)

        return self.filter(
            (
                models.Q(last_synced__isnull=True)
                | models.Q(sync_status="failed")
                | (
                    ~models.Q(status=MovieStatus.RELEASED)
                    & models.Q(last_synced__lt=cutoff)
                )
                | (
                    models.Q(status=MovieStatus.RELEASED)
                    & (
                        models.Q(runtime__isnull=True)
                        | models.Q(overview="")
                        | models.Q(poster_path="")
                    )
                )
            )
        )

    def by_tmdb_id(self, tmdb_id):
        """Get movie by TMDb ID with error handling."""
        try:
            return self.get(tmdb_id=tmdb_id)
        except self.model.DoesNotExist:
            return None

    def with_runtime_range(self, min_runtime=0, max_runtime=300):
        """Filter movies by runtime range."""
        return self.filter(
            is_active=True, runtime__gte=min_runtime, runtime__lte=max_runtime
        )
