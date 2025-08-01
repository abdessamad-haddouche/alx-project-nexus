"""
Movie recommendation models - Relationships between movies for recommendations and
similar movies.
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.constants import RecommendationSource, RecommendationType
from core.mixins.models import BaseModelMixin


class MovieRecommendation(BaseModelMixin):
    """
    Recommendation relationship between movies.

    Supports multiple recommendation types:
    - TMDb recommendations
    - TMDb similar movies
    """

    source_movie = models.ForeignKey(
        "Movie",
        on_delete=models.CASCADE,
        related_name="movie_recommendations_from",
        help_text=_("Movie that generates recommendations"),
    )

    recommended_movie = models.ForeignKey(
        "Movie",
        on_delete=models.CASCADE,
        related_name="movie_recommendations_to",
        help_text=_("Recommended movie"),
    )

    recommendation_type = models.CharField(
        _("recommendation type"),
        max_length=20,
        choices=RecommendationType.choices,
        default=RecommendationType.TMDB_RECOMMENDATION,
        db_index=True,
        help_text=_("Type of recommendation algorithm"),
    )

    confidence_score = models.FloatField(
        _("confidence score"),
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        db_index=True,
        help_text=_("Recommendation confidence (0.0-1.0), null for TMDb-based"),
    )

    source = models.CharField(
        _("source"),
        max_length=20,
        choices=RecommendationSource.choices,
        default=RecommendationSource.TMDB,
        help_text=_("Source of the recommendation"),
    )

    class Meta:
        db_table = "movies_movie_recommendation"
        verbose_name = _("Movie Recommendation")
        verbose_name_plural = _("Movie Recommendations")
        unique_together = ["source_movie", "recommended_movie", "recommendation_type"]
        ordering = ["-confidence_score", "-created_at"]
        indexes = [
            models.Index(fields=["source_movie", "recommendation_type"]),
            models.Index(fields=["recommended_movie", "recommendation_type"]),
            models.Index(fields=["confidence_score", "recommendation_type"]),
            models.Index(fields=["source_movie", "confidence_score"]),
        ]
        constraints = [
            # Prevent self-recommendations
            models.CheckConstraint(
                check=~models.Q(source_movie=models.F("recommended_movie")),
                name="no_self_recommendation",
            ),
        ]

    def __str__(self):
        return (
            f"{self.source_movie.title} → "
            f"{self.recommended_movie.title} ({self.recommendation_type})"
        )

    def __repr__(self):
        return (
            f"<MovieRecommendation: {self.source_movie.tmdb_id} → "
            f"{self.recommended_movie.tmdb_id}>"
        )

    @property
    def confidence_percentage(self):
        """Get confidence as percentage."""
        if self.confidence_score is None:
            return 0.0
        return round(self.confidence_score * 100, 1)

    @property
    def is_high_confidence(self):
        """Check if this is a high-confidence recommendation."""
        if self.confidence_score is None:
            return False
        return self.confidence_score >= 0.7

    def save(self, *args, **kwargs):
        """Override save to prevent self-recommendations."""
        if self.source_movie_id == self.recommended_movie_id:
            raise ValueError("Movie cannot recommend itself")
        super().save(*args, **kwargs)
