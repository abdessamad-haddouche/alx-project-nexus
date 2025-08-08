"""
Favorites API endpoints.
Handles user favorites, watchlist, ratings, and recommendation analytics.
"""

from django.urls import path

from apps.favorites.views import (
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

app_name = "favorites"

urlpatterns = [
    # ================================================================
    # CORE FAVORITE OPERATIONS
    # ================================================================
    # Favorite CRUD operations
    path("", FavoriteListView.as_view(), name="list"),
    path("create/", FavoriteCreateView.as_view(), name="create"),
    path("tmdb/create/", FavoriteCreateByTMDbView.as_view(), name="create-by-tmdb"),
    path("<int:pk>/", FavoriteDetailView.as_view(), name="detail"),
    path("<int:pk>/update/", FavoriteUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", FavoriteDeleteView.as_view(), name="delete"),
    # ================================================================
    # QUICK ACTIONS
    # ================================================================
    # Toggle favorite status (add/remove)
    path("toggle/", FavoriteToggleView.as_view(), name="toggle"),
    # ================================================================
    # WATCHLIST OPERATIONS
    # ================================================================
    # User's watchlist management
    path("watchlist/", UserWatchlistView.as_view(), name="watchlist"),
    path("watchlist/add/", WatchlistAddView.as_view(), name="watchlist-add"),
    path("watchlist/remove/", WatchlistRemoveView.as_view(), name="watchlist-remove"),
    # ================================================================
    # USER ANALYTICS & STATS
    # ================================================================
    # User's favorite statistics and preferences
    path("stats/", UserFavoriteStatsView.as_view(), name="user-stats"),
]
