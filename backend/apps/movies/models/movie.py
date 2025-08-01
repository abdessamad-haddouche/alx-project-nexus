"""
Movie model - Core movie entity with TMDb integration.
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from core.constants import Language, MovieStatus, RecommendationType
from core.mixins.models import BaseModelMixin, MetadataMixin, TMDbContentMixin

from ..managers import MovieManager


class Movie(TMDbContentMixin, BaseModelMixin, MetadataMixin):
    """
    Movie model representing a movie from TMDb with local enhancements.

    Inherits from:
    - TMDbContentMixin: tmdb_id, popularity, vote_average, vote_count, release_date,
      sync fields
    - BaseModelMixin: created_at, updated_at, is_active, objects manager
    - MetadataMixin: metadata JSON field for flexible data storage
    """

    # Core Information
    title = models.CharField(
        _("title"), max_length=255, db_index=True, help_text=_("Movie title in English")
    )

    original_title = models.CharField(
        _("original title"),
        max_length=255,
        db_index=True,
        help_text=_("Original movie title in source language"),
    )

    tagline = models.CharField(
        _("tagline"), max_length=500, blank=True, help_text=_("Movie tagline or slogan")
    )

    overview = models.TextField(
        _("overview"), blank=True, help_text=_("Movie plot summary")
    )

    # Technical Details
    runtime = models.PositiveIntegerField(
        _("runtime"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(600)],
        help_text=_("Runtime in minutes"),
    )

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=MovieStatus.choices,
        default=MovieStatus.RELEASED,
        db_index=True,
        help_text=_("Movie release status"),
    )

    original_language = models.CharField(
        _("original language"),
        max_length=10,
        choices=Language.choices,
        default=Language.ENGLISH,
        db_index=True,
        help_text=_("Original language of the movie"),
    )

    # Financial Information
    budget = models.BigIntegerField(
        _("budget"),
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_("Production budget in USD"),
    )

    revenue = models.BigIntegerField(
        _("revenue"),
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_("Box office revenue in USD"),
    )

    # Media & External Links
    poster_path = models.CharField(
        _("poster path"),
        max_length=500,
        blank=True,
        null=True,
        help_text=_("TMDb poster image path"),
    )

    backdrop_path = models.CharField(
        _("backdrop path"),
        max_length=500,
        blank=True,
        null=True,
        help_text=_("TMDb backdrop image path"),
    )

    homepage = models.URLField(
        _("homepage"), blank=True, help_text=_("Official movie website")
    )

    tmdb_id = models.CharField(
        _("TMDb ID"),
        max_length=20,
        blank=True,
        unique=True,
        null=True,
        db_index=True,
        help_text=_("TMDb identifier"),
    )

    imdb_id = models.CharField(
        _("IMDb ID"),
        max_length=20,
        blank=True,
        unique=True,
        null=True,
        db_index=True,
        help_text=_("IMDb identifier (e.g., tt1234567)"),
    )

    # Content Classification
    adult = models.BooleanField(
        _("adult content"),
        default=False,
        db_index=True,
        help_text=_("Adult content flag"),
    )

    # Relationships
    genres = models.ManyToManyField(
        "Genre",
        through="MovieGenre",
        related_name="movies",
        blank=True,
        help_text=_("Movie genres"),
    )

    # Recommendation relationships (covers both recommendations AND similar movies)
    related_movies = models.ManyToManyField(
        # A relationship to the same Movie model
        "self",
        # Intermediate model 'MovieRecommendation' to store extra info about
        # recommendations
        through="MovieRecommendation",
        # Since recommendations have direction (Movie A recommends Movie B, not
        # necessarily vice versa)
        symmetrical=False,
        # Reverse relation name: from a recommended movie, you can find movies that
        # recommended it via 'recommended_by'
        related_name="recommended_by",
        blank=True,
        help_text=_("Movies related to this movie (recommendations, similar, etc.)"),
    )

    # Custom Manager
    objects = MovieManager()

    class Meta:
        db_table = "movies_movie"
        verbose_name = _("Movie")
        verbose_name_plural = _("Movies")
        ordering = ["-popularity", "-vote_average"]
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["original_title"]),
            models.Index(fields=["tmdb_id", "is_active"]),
            models.Index(fields=["popularity", "vote_average"]),
            models.Index(fields=["release_date", "status"]),
            models.Index(fields=["original_language", "adult"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(runtime__gte=1) | models.Q(runtime__isnull=True),
                name="valid_runtime",
            ),
            models.CheckConstraint(
                check=models.Q(budget__gte=0), name="non_negative_budget"
            ),
            models.CheckConstraint(
                check=models.Q(revenue__gte=0), name="non_negative_revenue"
            ),
        ]

    def __str__(self):
        """String representation of the movie."""
        year = f" ({self.release_year})" if self.release_year else ""
        return f"{self.title}{year}"

    def __repr__(self):
        """Developer-friendly representation."""
        return f"<Movie: {self.title} (TMDb ID: {self.tmdb_id})>"

    def get_absolute_url(self):
        """Get the absolute URL for this movie."""
        return reverse("movies:detail", kwargs={"tmdb_id": self.tmdb_id})

    # Properties
    @property
    def release_year(self):
        """Get the release year."""
        return self.release_date.year if self.release_date else None

    @property
    def is_recently_released(self):
        """Check if movie was released in the last year."""
        if not self.release_date:
            return False
        from datetime import timedelta

        from django.utils import timezone

        one_year_ago = timezone.now().date() - timedelta(days=365)
        return self.release_date >= one_year_ago

    @property
    def profit(self):
        """Calculate profit (revenue - budget)."""
        return self.revenue - self.budget if self.budget and self.revenue else 0

    @property
    def runtime_formatted(self):
        """Get formatted runtime string (e.g., '2h 30m')."""
        if not self.runtime:
            return "Unknown"
        hours, minutes = divmod(self.runtime, 60)
        if hours:
            return f"{hours}h {minutes}m" if minutes else f"{hours}h"
        return f"{minutes}m"

    @property
    def primary_genre(self):
        """Get the primary genre (first in the list)."""
        try:
            primary_mg = self.movie_genres.filter(
                is_primary=True, is_active=True
            ).first()
            return primary_mg.genre if primary_mg else None
        except:
            return None

    @property
    def genre_names(self):
        """Get list of genre names."""
        return list(self.genres.values_list("name", flat=True))

    @property
    def tmdb_url(self):
        """Get TMDb URL for this movie."""
        return f"https://www.themoviedb.org/movie/{self.tmdb_id}"

    @property
    def imdb_url(self):
        """Get IMDb URL if IMDb ID exists."""
        return f"https://www.imdb.com/title/{self.imdb_id}/" if self.imdb_id else None

    # Methods
    def get_poster_url(self, size="w500"):
        """Get full poster URL from TMDb."""
        if not self.poster_path:
            return None
        base_url = "https://image.tmdb.org/t/p/"
        return f"{base_url}{size}{self.poster_path}"

    def get_backdrop_url(self, size="w780"):
        """Get full backdrop URL from TMDb."""
        if not self.backdrop_path:
            return None
        base_url = "https://image.tmdb.org/t/p/"
        return f"{base_url}{size}{self.backdrop_path}"

    # Recommendation methods
    def get_tmdb_recommendations(self, limit=10):
        """Get TMDb-generated recommendations."""
        return self.related_movies.filter(
            movie_recommendations_from__recommendation_type=(
                RecommendationType.TMDB_RECOMMENDATION
            ),
            is_active=True,
        ).order_by(
            "-movie_recommendations_from__confidence_score",  # Nulls last
            "-movie_recommendations_from__created_at",  # Then by newest
        )[
            :limit
        ]

    # Get similar movies method
    def get_tmdb_similar(self, limit=10):
        """Get TMDb similar movies."""
        return self.related_movies.filter(
            movie_recommendations_from__recommendation_type=RecommendationType.TMDB_SIMILAR,
            is_active=True,
        ).order_by(
            "-movie_recommendations_from__confidence_score",  # Nulls last
            "-movie_recommendations_from__created_at",  # Then by newest
        )[
            :limit
        ]

    def get_all_related(self, limit=20):
        """Get all types of related movies (recommendations + similar)."""
        return self.related_movies.filter(is_active=True).order_by(
            "-movie_recommendations_from__confidence_score",
            "-movie_recommendations_from__created_at",
        )[:limit]

    def add_related(
        self,
        related_movie,
        rec_type=RecommendationType.TMDB_RECOMMENDATION,
        confidence=None,
    ):
        """Add a related movie relationship."""
        from .recommendation import MovieRecommendation

        related, created = MovieRecommendation.objects.get_or_create(
            source_movie=self,
            recommended_movie=related_movie,
            recommendation_type=rec_type,
            defaults={"confidence_score": confidence},
        )
        return related

    def add_recommendation(self, movie, confidence=None):
        """Add a TMDb recommendation."""
        return self.add_related(
            movie, RecommendationType.TMDB_RECOMMENDATION, confidence
        )

    def add_similar_movie(self, movie, confidence=None):
        """Add a TMDb similar movie."""
        return self.add_related(movie, RecommendationType.TMDB_SIMILAR, confidence)

    def save(self, *args, **kwargs):
        """Override save to handle data validation and processing."""
        # Clean and validate data
        if self.title:
            self.title = self.title.strip()
        if self.original_title:
            self.original_title = self.original_title.strip()

        # Ensure we have a title
        if not self.title and self.original_title:
            self.title = self.original_title
        elif not self.original_title and self.title:
            self.original_title = self.title

        super().save(*args, **kwargs)
