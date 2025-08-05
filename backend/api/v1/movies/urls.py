"""
Movies API endpoints.
Handles movie catalog, genres, search, discovery, and TMDb integration.
"""

from django.urls import path

from apps.movies.views import (
    GenreCreateView,
    GenreDeleteView,
    GenreDetailView,
    GenreListView,
    GenreMoviesView,
    GenreUpdateView,
    MovieCreateView,
    MovieDeleteView,
    MovieDetailView,
    MovieListView,
    MovieSearchView,
    MovieUpdateView,
    PopularMoviesView,
    TopRatedMoviesView,
    TrendingMoviesView,
)

app_name = "movies"


urlpatterns = [
    # ================================================================
    # CORE MOVIE OPERATIONS
    # ================================================================
    # Movie CRUD operations
    path("", MovieListView.as_view(), name="list"),
    path("create/", MovieCreateView.as_view(), name="create"),
    path("<int:pk>/", MovieDetailView.as_view(), name="detail"),
    path("<int:pk>/update/", MovieUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", MovieDeleteView.as_view(), name="delete"),
    # # ================================================================
    # # MOVIE SEARCH & DISCOVERY
    # # ================================================================
    # # Search operations
    path("search/", MovieSearchView.as_view(), name="search"),
    # Discovery operations
    path("popular/", PopularMoviesView.as_view(), name="popular"),
    path("trending/", TrendingMoviesView.as_view(), name="trending"),
    path("top-rated/", TopRatedMoviesView.as_view(), name="top-rated"),
    # # ================================================================
    # # GENRE OPERATIONS
    # # ================================================================
    # Genre CRUD operations
    path("genres/", GenreListView.as_view(), name="genre-list"),
    path("genres/create/", GenreCreateView.as_view(), name="genre-create"),
    path("genres/<int:pk>/", GenreDetailView.as_view(), name="genre-detail"),
    path("genres/<int:pk>/update/", GenreUpdateView.as_view(), name="genre-update"),
    path("genres/<int:pk>/delete/", GenreDeleteView.as_view(), name="genre-delete"),
    # # Genre relationships
    path("genres/<int:pk>/movies/", GenreMoviesView.as_view(), name="genre-movies"),
]
