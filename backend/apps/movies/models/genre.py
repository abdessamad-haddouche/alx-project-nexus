"""
Genre model - Movie genre classification.
"""

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from core.mixins.models import ActiveMixin, TimeStampedMixin

from ..managers import GenreManager


class Genre(TimeStampedMixin, ActiveMixin):
    """
    Movie genre model with TMDb integration.
    """

    tmdb_id = models.PositiveIntegerField(
        _("TMDb ID"),
        unique=True,
        db_index=True,
        help_text=_("The Movie Database genre identifier"),
    )

    name = models.CharField(
        _("name"), max_length=50, unique=True, db_index=True, help_text=_("Genre name")
    )

    slug = models.SlugField(
        _("slug"), max_length=50, unique=True, help_text=_("URL-friendly genre name")
    )

    # Dual manager setup
    objects = models.Manager()
    active_objects = GenreManager()

    class Meta:
        db_table = "movies_genre"
        verbose_name = _("Genre")
        verbose_name_plural = _("Genres")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["tmdb_id"]),
            models.Index(fields=["name"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<Genre: {self.name} (TMDb ID: {self.tmdb_id})>"

    def get_absolute_url(self):
        """Get the absolute URL for this genre."""
        return reverse("movies:genre-detail", kwargs={"slug": self.slug})

    @property
    def movie_count(self):
        """Get count of active movies in this genre."""
        return self.movies.filter(is_active=True).count()

    def get_popular_movies(self, limit=20):
        """Get popular movies in this genre."""
        return self.movies.filter(is_active=True).order_by(
            "-popularity", "-vote_average"
        )[:limit]

    def get_recent_movies(self, limit=20):
        """Get recently released movies in this genre."""
        return self.movies.filter(is_active=True, release_date__isnull=False).order_by(
            "-release_date"
        )[:limit]

    def save(self, *args, **kwargs):
        """Override save to auto-generate slug and ensure proper defaults."""
        # Ensure new genres are active by default
        if self._state.adding and self.is_active is None:
            self.is_active = True

        # Auto-generate slug if not provided
        if not self.slug and self.name:
            from django.utils.text import slugify

            self.slug = slugify(self.name)

        super().save(*args, **kwargs)
