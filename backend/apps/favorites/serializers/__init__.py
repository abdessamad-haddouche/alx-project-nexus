"""
Favorites app serializers package.
"""

from .favorite import (
    FavoriteCreateSerializer,
    FavoriteListSerializer,
    FavoriteSerializer,
    FavoriteToggleSerializer,
    FavoriteUpdateSerializer,
    MoviePopularityStatsSerializer,
    UserFavoriteStatsSerializer,
    WatchlistSerializer,
)

__all__ = [
    "FavoriteSerializer",
    "FavoriteCreateSerializer",
    "FavoriteUpdateSerializer",
    "FavoriteListSerializer",
    "WatchlistSerializer",
    "UserFavoriteStatsSerializer",
    "MoviePopularityStatsSerializer",
    "FavoriteToggleSerializer",
]
