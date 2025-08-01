"""
Movie serializers package.
"""

# Genre serializers
from .genre import (
    GenreCreateSerializer,
    GenreDetailSerializer,
    GenreListSerializer,
    GenreSimpleSerializer,
    GenreStatsSerializer,
    GenreUpdateSerializer,
)

# Movie serializers
from .movie import (
    MovieCreateSerializer,
    MovieDetailSerializer,
    MovieListSerializer,
    MovieSearchSerializer,
    MovieSimpleSerializer,
    MovieUpdateSerializer,
)

# MovieGenre serializers
from .moviegenre import (
    MovieGenreBulkCreateSerializer,
    MovieGenreCreateSerializer,
    MovieGenreDetailSerializer,
    MovieGenreListSerializer,
    MovieGenreUpdateSerializer,
)

# Recommendation serializers
from .recommendation import (
    MovieRecommendationBulkCreateSerializer,
    MovieRecommendationCreateSerializer,
    MovieRecommendationDetailSerializer,
    MovieRecommendationListSerializer,
    MovieRecommendationSimpleSerializer,
    MovieRecommendationUpdateSerializer,
    MovieWithRecommendationsSerializer,
)

__all__ = [
    # Movie serializers
    "MovieListSerializer",
    "MovieDetailSerializer",
    "MovieCreateSerializer",
    "MovieUpdateSerializer",
    "MovieSearchSerializer",
    "MovieSimpleSerializer",
    # Genre serializers
    "GenreListSerializer",
    "GenreDetailSerializer",
    "GenreCreateSerializer",
    "GenreUpdateSerializer",
    "GenreSimpleSerializer",
    "GenreStatsSerializer",
    # MovieGenre serializers
    "MovieGenreListSerializer",
    "MovieGenreDetailSerializer",
    "MovieGenreCreateSerializer",
    "MovieGenreUpdateSerializer",
    "MovieGenreBulkCreateSerializer",
    # Recommendation serializers
    "MovieRecommendationListSerializer",
    "MovieRecommendationDetailSerializer",
    "MovieRecommendationCreateSerializer",
    "MovieRecommendationUpdateSerializer",
    "MovieRecommendationBulkCreateSerializer",
    "MovieRecommendationSimpleSerializer",
    "MovieWithRecommendationsSerializer",
]
