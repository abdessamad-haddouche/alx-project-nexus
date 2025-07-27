"""
Movie catalog API endpoints.
Handles movie listing, details, search, filtering, etc.
"""
from django.urls import path

from . import views

app_name = "movies"

urlpatterns = [
    # Movie listing and details
    path("", views.MovieListView.as_view(), name="movie-list"),
    path("<int:pk>/", views.MovieDetailView.as_view(), name="movie-detail"),
    # Movie discovery
    path("trending/", views.TrendingMoviesView.as_view(), name="trending-movies"),
    path("popular/", views.PopularMoviesView.as_view(), name="popular-movies"),
    path("latest/", views.LatestMoviesView.as_view(), name="latest-movies"),
    # Movie relationships
    path("<int:pk>/similar/", views.SimilarMoviesView.as_view(), name="similar-movies"),
    path("<int:pk>/cast/", views.MovieCastView.as_view(), name="movie-cast"),
    path("<int:pk>/crew/", views.MovieCrewView.as_view(), name="movie-crew"),
]
