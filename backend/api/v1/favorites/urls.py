"""
User favorites and watchlist API endpoints.
Handles favorites, watchlists, ratings, reviews, etc.
"""
from django.urls import path

app_name = "favorites"

urlpatterns = [
    # # # Favorites management
    # path("", views.FavoriteMoviesView.as_view(), name="favorite-list"),
    # path("add/", views.AddToFavoritesView.as_view(), name="add-favorite"),
    # path(
    #     "remove/<int:movie_id>/",
    #     views.RemoveFromFavoritesView.as_view(),
    #     name="remove-favorite",
    # ),
    # path("bulk/", views.BulkFavoritesView.as_view(), name="bulk-favorites"),
]
