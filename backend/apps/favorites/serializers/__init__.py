"""
Favorites app serializers package.
"""

from .favorite import (
    FavoriteCreateByTMDbSerializer,
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
    "FavoriteCreateByTMDbSerializer",
    "FavoriteUpdateSerializer",
    "FavoriteListSerializer",
    "WatchlistSerializer",
    "UserFavoriteStatsSerializer",
    "MoviePopularityStatsSerializer",
    "FavoriteToggleSerializer",
]
