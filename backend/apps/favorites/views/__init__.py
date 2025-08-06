"""
Favorite Views Package
"""

from .favorite_views import (
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
    "FavoriteUpdateView",
    "FavoriteDeleteView",
    "FavoriteToggleView",
    "UserWatchlistView",
    "WatchlistAddView",
    "WatchlistRemoveView",
    "UserFavoriteStatsView",
]
