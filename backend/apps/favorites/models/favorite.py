"""
Favorite model - User's favorite movies.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.constants import RecommendationType
from core.mixins.models import BaseModelMixin, MetadataMixin

from ..managers import FavoriteManager


class Favorite(BaseModelMixin, MetadataMixin):
    """
    User's favorite movies with additional metadata.

    Tracks when users favorite movies and provides data for
    personalized recommendations based on their preferences.

    Inherits from:
    - BaseModelMixin: created_at, updated_at, is_active, objects manager
    - MetadataMixin: metadata JSON field for flexible data storage
    """

    # Core Relationship
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
        verbose_name=_("user"),
        db_index=True,
        help_text=_("User who favorited this movie"),
    )

    movie = models.ForeignKey(
        "movies.Movie",
        on_delete=models.CASCADE,
        related_name="favorited_by",
        verbose_name=_("movie"),
        db_index=True,
        help_text=_("Movie that was favorited"),
    )

    # Optional User Rating & Notes
    user_rating = models.PositiveSmallIntegerField(
        _("user rating"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        db_index=True,
        help_text=_("User's personal rating (1-10 scale)"),
    )

    notes = models.TextField(
        _("notes"),
        blank=True,
        max_length=1000,
        help_text=_("User's personal notes about this movie"),
    )

    # Recommendation Data
    recommendation_source = models.CharField(
        _("recommendation source"),
        max_length=30,
        choices=RecommendationType.choices,
        null=True,
        blank=True,
        help_text=_("How user discovered this movie (for analytics)"),
    )

    # Timestamps for analytics
    first_favorited = models.DateTimeField(
        _("first favorited"),
        auto_now_add=True,
        db_index=True,
        help_text=_("When user first favorited this movie"),
    )

    last_interaction = models.DateTimeField(
        _("last interaction"),
        auto_now=True,
        db_index=True,
        help_text=_("Last time user interacted with this favorite"),
    )

    # Watchlist functionality
    is_watchlist = models.BooleanField(
        _("is watchlist"),
        default=False,
        db_index=True,
        help_text=_("Movie is in user's watchlist (want to watch)"),
    )

    # Custom Manager
    objects = FavoriteManager()

    class Meta:
        db_table = "favorites_favorite"
        verbose_name = _("Favorite")
        verbose_name_plural = _("Favorites")
        ordering = ["-last_interaction", "-first_favorited"]

        indexes = [
            models.Index(fields=["user", "movie"]),
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["user", "user_rating"]),
            models.Index(fields=["user", "is_watchlist"]),
            models.Index(fields=["movie", "user_rating"]),
            models.Index(fields=["first_favorited"]),
            models.Index(fields=["last_interaction"]),
        ]

        constraints = [
            # Prevent duplicate favorites
            models.UniqueConstraint(
                fields=["user", "movie"],
                condition=models.Q(is_active=True),
                name="unique_active_user_movie_favorite",
            ),
            # Ensure valid rating range
            models.CheckConstraint(
                check=models.Q(user_rating__gte=1, user_rating__lte=10)
                | models.Q(user_rating__isnull=True),
                name="valid_user_rating_range",
            ),
        ]

    def __str__(self):
        """String representation of the favorite."""
        rating_str = f" ({self.user_rating}/10)" if self.user_rating else ""
        return f"{self.user.email} → {self.movie.title}{rating_str}"

    def __repr__(self):
        """Developer-friendly representation."""
        return f"<Favorite: {self.user.email} → {self.movie.title}>"

    @property
    def is_recent(self):
        """Check if favorited in the last 30 days."""
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        return self.first_favorited >= thirty_days_ago

    @property
    def rating_stars(self):
        """Convert 1-10 rating to 1-5 stars."""
        if not self.user_rating:
            return None
        return round(self.user_rating / 2, 1)

    @property
    def is_highly_rated_by_user(self):
        """Check if user rated this movie highly (8+)."""
        return self.user_rating and self.user_rating >= 8

    # Essential Methods
    def update_interaction(self):
        """Update last interaction timestamp."""
        self.last_interaction = timezone.now()
        self.save(update_fields=["last_interaction"])

    def set_rating(self, rating):
        """Set user rating with validation."""
        if rating is not None and not (1 <= rating <= 10):
            raise ValueError("Rating must be between 1 and 10")

        self.user_rating = rating
        self.last_interaction = timezone.now()
        self.save(update_fields=["user_rating", "last_interaction"])

    def toggle_watchlist(self):
        """Toggle watchlist status."""
        self.is_watchlist = not self.is_watchlist
        self.last_interaction = timezone.now()
        self.save(update_fields=["is_watchlist", "last_interaction"])

    def save(self, *args, **kwargs):
        """Override save for data validation and cleanup."""
        # Clean notes
        if self.notes:
            self.notes = self.notes.strip()[:1000]

        # Update interaction timestamp on any save
        if self.pk:  # Existing record
            self.last_interaction = timezone.now()

        super().save(*args, **kwargs)
