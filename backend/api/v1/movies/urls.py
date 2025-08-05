"""
Movies API endpoints.
Handles movie catalog, genres, search, discovery, and TMDb integration.
"""

from django.urls import path

from apps.movies.views import (
    MovieCreateView,
    MovieDeleteView,
    MovieDetailView,
    MovieUpdateView,
)

app_name = "movies"


urlpatterns = [
    # ================================================================
    # CORE MOVIE OPERATIONS
    # ================================================================
    # Movie CRUD operations
    path("create/", MovieCreateView.as_view(), name="create"),
    path("<int:pk>/", MovieDetailView.as_view(), name="detail"),
    path("<int:pk>/update/", MovieUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", MovieDeleteView.as_view(), name="delete"),
]
