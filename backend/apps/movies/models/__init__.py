"""
Movies models package.
"""

from .genre import Genre
from .movie import Movie
from .moviegenre import MovieGenre
from .recommendation import MovieRecommendation

__all__ = [
    "Movie",
    "Genre",
    "MovieGenre",
    "MovieRecommendation",
]
