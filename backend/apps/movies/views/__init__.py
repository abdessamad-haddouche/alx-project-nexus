from .discovery_views import (
    MovieSearchView,
    PopularMoviesView,
    TopRatedMoviesView,
    TrendingMoviesView,
)
from .genre_views import (
    GenreCreateView,
    GenreDeleteView,
    GenreDetailView,
    GenreListView,
    GenreMoviesView,
    GenreUpdateView,
)
from .movie_genre_views import (
    MovieGenreCreateView,
    MovieGenreDeleteView,
    MovieGenreDetailView,
    MovieGenreListView,
    MovieGenreUpdateView,
)
from .movie_views import (
    MovieCreateView,
    MovieDeleteView,
    MovieDetailView,
    MovieListView,
    MovieUpdateView,
)
from .recommendation_views import (
    MovieGenresView,
    MovieRecommendationsView,
    SimilarMoviesView,
)

__all__ = [
    # Movie CRUD Views
    "MovieListView",
    "MovieDetailView",
    "MovieCreateView",
    "MovieUpdateView",
    "MovieDeleteView",
    #
    "MovieSearchView",
    "PopularMoviesView",
    "TrendingMoviesView",
    "TopRatedMoviesView",
    # Movie Recommendation Views
    "MovieRecommendationsView",
    "SimilarMoviesView",
    "MovieGenresView",
    # Genre Views
    "GenreListView",
    "GenreCreateView",
    "GenreDetailView",
    "GenreUpdateView",
    "GenreDeleteView",
    "GenreBySlugView",
    "GenreMoviesView",
    # Movie Genre Views
    "MovieGenreListView",
    "MovieGenreCreateView",
    "MovieGenreDetailView",
    "MovieGenreUpdateView",
    "MovieGenreDeleteView",
    "MovieGenreBulkCreateView",
]
