"""
MovieGenre through model - Movie-Genre relationship with metadata.
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.mixins.models import BaseModelMixin

from ..managers import MovieGenreManager


class MovieGenre(BaseModelMixin):
    """
    Through model for Movie-Genre many-to-many relationship.
    """

    movie = models.ForeignKey(
        "Movie", on_delete=models.CASCADE, related_name="movie_genres"
    )

    genre = models.ForeignKey(
        "Genre", on_delete=models.CASCADE, related_name="movie_genres"
    )

    is_primary = models.BooleanField(
        _("is primary"),
        default=False,
        db_index=True,
        help_text=_("Primary genre for this movie"),
    )

    weight = models.FloatField(
        _("weight"),
        null=True,
        blank=True,
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text=_("Genre relevance weight (0.0-1.0)"),
    )

    # Custom Manager
    objects = MovieGenreManager()

    class Meta:
        db_table = "movies_movie_genre"
        verbose_name = _("Movie Genre")
        verbose_name_plural = _("Movie Genres")
        unique_together = ["movie", "genre"]
        ordering = ["-is_primary", "-weight", "genre__name"]
        indexes = [
            models.Index(fields=["movie", "is_primary"]),
            models.Index(fields=["genre", "weight"]),
            models.Index(fields=["is_primary", "weight"]),
        ]

    def __str__(self):
        primary = " (Primary)" if self.is_primary else ""
        return f"{self.movie.title} - {self.genre.name}{primary}"

    def __repr__(self):
        return f"<MovieGenre: {self.movie.tmdb_id} → {self.genre.name}>"

    # def save(self, *args, **kwargs):
    #     """Override save to ensure only one primary genre per movie."""
    #     if self.is_primary:
    #         # Remove primary flag from other genres for this movie
    #         MovieGenre.objects.filter(movie=self.movie, is_primary=True).exclude(
    #             id=self.id
    #         ).update(is_primary=False)
    #     super().save(*args, **kwargs)
