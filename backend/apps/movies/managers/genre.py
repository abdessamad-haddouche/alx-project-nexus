"""
Custom managers for the Genre model.
"""

from django.db import models

from core.mixins.managers import BaseManager


class GenreManager(BaseManager):
    """
    Custom manager for Genre model that filters to active records only.
    This is now used as the secondary manager (active_objects).
    """

    def get_queryset(self):
        """Return only active genres."""
        return super().get_queryset().filter(is_active=True)

    def popular_genres(self, limit=10):
        """Get genres with most movies."""
        return (
            self.get_queryset()  # Already filtered to active
            .annotate(
                annotated_movie_count=models.Count(
                    "movies", filter=models.Q(movies__is_active=True)
                )
            )
            .order_by("-annotated_movie_count")[:limit]
        )

    def by_tmdb_id(self, tmdb_id):
        """Get genre by TMDb ID with error handling (active only)."""
        try:
            return self.get_queryset().get(tmdb_id=tmdb_id)
        except self.model.DoesNotExist:
            return None


class AllGenreManager(models.Manager):
    """
    Manager that sees all genres (active + inactive).
    Useful for admin operations and data migrations.
    """

    def active(self):
        """Get only active genres."""
        return self.filter(is_active=True)

    def inactive(self):
        """Get only inactive genres."""
        return self.filter(is_active=False)

    def activate_all(self):
        """Activate all genres."""
        return self.update(is_active=True)

    def by_tmdb_id(self, tmdb_id, include_inactive=True):
        """Get genre by TMDb ID including inactive if specified."""
        try:
            qs = self.all() if include_inactive else self.active()
            return qs.get(tmdb_id=tmdb_id)
        except self.model.DoesNotExist:
            return None
