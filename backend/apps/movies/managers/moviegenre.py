"""
MovieGenre through model - Movie-Genre relationship with metadata.
"""

from core.mixins.managers import BaseManager


class MovieGenreManager(BaseManager):
    """
    Custom manager for MovieGenre.
    """

    def get_queryset(self):
        """Override to include select_related for performance."""
        return super().get_queryset().select_related("movie", "genre")

    def primary_genres(self):
        """Get all primary genre relationships."""
        return self.filter(is_primary=True)

    def by_movie(self, movie):
        """Get all genre relationships for a specific movie."""
        return self.filter(movie=movie).order_by(
            "-is_primary", "-weight", "genre__name"
        )

    def by_genre(self, genre):
        """Get all movie relationships for a specific genre."""
        return self.filter(genre=genre).order_by("-weight", "-movie__popularity")

    def set_primary_genre(self, movie, genre):
        """Set a genre as primary for a movie."""
        # Remove primary flag from all genres for this movie
        self.filter(movie=movie).update(is_primary=False)

        # Set the specified genre as primary
        movie_genre, created = self.get_or_create(
            movie=movie, genre=genre, defaults={"is_primary": True, "weight": 1.0}
        )
        if not created:
            movie_genre.is_primary = True
            movie_genre.save(update_fields=["is_primary"])

        return movie_genre

    def get_movie_primary_genre(self, movie):
        """Get the primary genre for a movie."""
        try:
            return self.get(movie=movie, is_primary=True).genre
        except self.model.DoesNotExist:
            # Return first genre if no primary set
            first_genre_rel = self.filter(movie=movie).first()
            return first_genre_rel.genre if first_genre_rel else None
        
    def filter_active_primary(self, movie):
        """Get active primary genres for a movie."""
        return self.filter(movie=movie, is_primary=True, is_active=True)
