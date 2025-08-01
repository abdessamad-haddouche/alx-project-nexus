"""
Custom managers for Movie models.
"""

from .genre import GenreManager
from .movie import MovieManager
from .moviegenre import MovieGenreManager

__all__ = [
    "GenreManager",
    "MovieManager",
    "MovieGenreManager",
]
