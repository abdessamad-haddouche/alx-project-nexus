"""
Custom managers for the Genre model.
"""

from django.db import models

from core.mixins.managers import BaseManager


class GenreManager(BaseManager):
    """
    Custom manager for Genre model.
    """

    def popular_genres(self, limit=10):
        """Get genres with most movies."""
        return (
            self.filter(is_active=True)
            .annotate(
                annotated_movie_count=models.Count(
                    "movies", filter=models.Q(movies__is_active=True)
                )
            )
            .order_by("-annotated_movie_count")[:limit]
        )

    def by_tmdb_id(self, tmdb_id):
        """Get genre by TMDb ID with error handling."""
        try:
            return self.get(tmdb_id=tmdb_id)
        except self.model.DoesNotExist:
            return None
