"""
Favorite Views Package
"""

from .favorite_views import (
    FavoriteCreateByTMDbView,
    FavoriteCreateView,
    FavoriteDeleteView,
    FavoriteDetailView,
    FavoriteListView,
    FavoriteToggleView,
    FavoriteUpdateView,
    UserFavoriteStatsView,
    UserWatchlistView,
    WatchlistAddView,
    WatchlistRemoveView,
)

__all__ = [
    "FavoriteListView",
    "FavoriteDetailView",
    "FavoriteCreateView",
    "FavoriteCreateByTMDbView",
    "FavoriteUpdateView",
    "FavoriteDeleteView",
    "FavoriteToggleView",
    "UserWatchlistView",
    "WatchlistAddView",
    "WatchlistRemoveView",
    "UserFavoriteStatsView",
]
