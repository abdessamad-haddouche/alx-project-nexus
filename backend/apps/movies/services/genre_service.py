"""
Genre Service - Business logic for genre operations.
"""

import logging
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import QuerySet
from django.utils.text import slugify

from core.exceptions import DatabaseException, TMDbAPIException, ValidationException
from core.services.tmdb import tmdb_service

from ..models import Genre, Movie, MovieGenre

logger = logging.getLogger(__name__)


class GenreService:
    """
    Service class for genre-related operations.

    Responsibilities:
    - Genre synchronization from TMDb
    - Movie-genre relationship management
    - Genre-based movie queries
    """

    def __init__(self):
        self.tmdb = tmdb_service
        self.cache_settings = settings.TMDB_SETTINGS.get("CACHE_SETTINGS", {})
        self._default_cache_timeout = self.cache_settings.get(
            "GENRE_LIST_TTL", 604800
        )  # 1 week

    # =========================================================================
    # GENRE SYNCHRONIZATION OPERATIONS
    # =========================================================================

    def sync_genres_from_tmdb(self) -> List[Genre]:
        """
        Synchronize all movie genres from TMDb.

        Returns:
            List of Genre instances that were synced

        Raises:
            TMDbAPIException: If TMDb API fails
            DatabaseException: If database operations fail
        """
        logger.info("Starting genre synchronization from TMDb...")

        try:
            # Get genres from TMDb API
            tmdb_genres = self.tmdb.get_genres_list()
            if not tmdb_genres:
                logger.warning("No genres returned from TMDb API")
                return []

            synced_genres = []
            created_count = 0
            updated_count = 0

            with transaction.atomic():
                for genre_data in tmdb_genres:
                    try:
                        genre, created = self._sync_single_genre(genre_data)
                        synced_genres.append(genre)

                        if created:
                            created_count += 1
                        else:
                            updated_count += 1

                    except Exception as e:
                        logger.error(f"Failed to sync genre {genre_data}: {e}")
                        continue

            # Clear genre cache after sync
            self._invalidate_genre_cache()

            logger.info(
                f"Genre sync completed: {created_count} created, "
                f"{updated_count} updated, {len(synced_genres)} total"
            )

            return synced_genres

        except Exception as e:
            logger.error(f"Genre synchronization failed: {e}")
            raise TMDbAPIException(f"Failed to sync genres from TMDb: {e}")

    def get_or_create_genre(self, tmdb_id: int, name: str) -> Genre:
        """
        Get existing genre or create new one.

        Args:
            tmdb_id: TMDb genre identifier
            name: Genre name

        Returns:
            Genre instance

        Raises:
            ValidationException: If input data is invalid
            DatabaseException: If database operations fail
        """
        if not tmdb_id or not name:
            raise ValidationException("TMDb ID and name are required")

        logger.debug(f"Getting or creating genre: {name} (TMDb ID: {tmdb_id})")

        try:
            # Try to get existing genre first
            genre = Genre.objects.filter(tmdb_id=tmdb_id).first()

            if genre:
                # Update name if it has changed
                if genre.name != name:
                    genre.name = name
                    genre.slug = self._generate_slug(name)
                    genre.save(update_fields=["name", "slug"])
                    logger.info(f"Updated genre name: {genre.name}")

                return genre

            # Create new genre
            genre = Genre.objects.create(
                tmdb_id=tmdb_id,
                name=name,
                slug=self._generate_slug(name),
                is_active=True,
            )

            logger.info(f"Created new genre: {genre.name}")
            return genre

        except Exception as e:
            logger.error(f"Failed to get or create genre {name}: {e}")
            raise DatabaseException(f"Genre operation failed: {e}")

    # =========================================================================
    # GENRE QUERY OPERATIONS
    # =========================================================================

    def get_popular_genres(self, limit: int = 10) -> List["Genre"]:
        """
        Get genres ordered by movie count (popularity).

        Args:
            limit: Maximum number of genres to return

        Returns:
            List of Genre instances ordered by popularity
        """
        if limit <= 0:
            raise ValidationException("Limit must be positive")

        logger.debug(f"Getting {limit} popular genres")

        # DON'T cache model objects - just get fresh data each time
        # This is fast enough for genres since there are only ~20 of them

        try:
            # Get all active genres and calculate movie count manually
            genres = Genre.objects.filter(is_active=True)

            # Calculate movie counts and sort
            genre_counts = []
            for genre in genres:
                movie_count = genre.movies.filter(is_active=True).count()
                if movie_count > 0:  # Only include genres with movies
                    genre_counts.append((genre, movie_count))

            # Sort by movie count (descending) and take the limit
            genre_counts.sort(key=lambda x: x[1], reverse=True)

            # Extract just the genres (no caching of model objects)
            popular_genres_list = [genre for genre, count in genre_counts[:limit]]

            logger.info(f"Retrieved {len(popular_genres_list)} popular genres")
            return popular_genres_list

        except Exception as e:
            logger.error(f"Failed to get popular genres: {e}")
            raise DatabaseException(f"Failed to retrieve popular genres: {e}")

    def get_all_genres(self, include_inactive: bool = False) -> List["Genre"]:
        """
        Get all genres without caching.

        Args:
            include_inactive: Whether to include inactive genres

        Returns:
            List of Genre instances
        """
        logger.debug(f"Getting all genres (include_inactive: {include_inactive})")

        # No caching - just return fresh data
        # Genres don't change often and there are only ~20 of them

        try:
            if include_inactive:
                genres = Genre.objects.all().order_by("name")
            else:
                genres = Genre.objects.filter(is_active=True).order_by("name")

            # Convert to list and return
            genres_list = list(genres)

            logger.info(f"Retrieved {len(genres_list)} genres")
            return genres_list

        except Exception as e:
            logger.error(f"Failed to get all genres: {e}")
            raise DatabaseException(f"Failed to retrieve genres: {e}")

    # =========================================================================
    # MOVIE-GENRE RELATIONSHIP OPERATIONS
    # =========================================================================

    def assign_genres_to_movie(
        self, movie: Movie, genre_data: List[Dict]
    ) -> List[MovieGenre]:
        """
        Assign genres to a movie, handling creation and updates.

        Args:
            movie: Movie instance
            genre_data: List of genre dictionaries with 'tmdb_id', 'name', etc.

        Returns:
            List of MovieGenre instances created/updated

        Raises:
            ValidationException: If input data is invalid
            DatabaseException: If database operations fail
        """
        if not movie:
            raise ValidationException("Movie is required")

        if not genre_data or not isinstance(genre_data, list):
            logger.warning(f"No genre data provided for movie {movie.tmdb_id}")
            return []

        logger.info(f"Assigning {len(genre_data)} genres to movie: {movie.title}")

        try:
            with transaction.atomic():
                # Get or create all genres first
                genres = []
                for genre_info in genre_data:
                    if isinstance(genre_info, dict):
                        tmdb_id = genre_info.get("tmdb_id") or genre_info.get("id")
                        name = genre_info.get("name", "")
                    else:
                        # Handle simple ID list
                        tmdb_id = genre_info
                        name = f"Genre {tmdb_id}"  # Fallback name

                    if tmdb_id:
                        try:
                            genre = self.get_or_create_genre(tmdb_id, name)
                            genres.append(genre)
                        except Exception as e:
                            logger.warning(f"Failed to get/create genre {tmdb_id}: {e}")
                            continue

                if not genres:
                    logger.warning(f"No valid genres found for movie {movie.tmdb_id}")
                    return []

                # Clear existing genre relationships
                MovieGenre.objects.filter(movie=movie).delete()

                # Create new relationships
                movie_genres = []
                for i, genre in enumerate(genres):
                    movie_genre = MovieGenre.objects.create(
                        movie=movie,
                        genre=genre,
                        is_primary=(i == 0),  # First genre is primary
                        weight=1.0 - (i * 0.1),  # Decreasing weight
                    )
                    movie_genres.append(movie_genre)

                logger.info(
                    f"Assigned {len(movie_genres)} genres to movie {movie.title}"
                )
                return movie_genres

        except Exception as e:
            logger.error(f"Failed to assign genres to movie {movie.tmdb_id}: {e}")
            raise DatabaseException(f"Genre assignment failed: {e}")

    def set_primary_genre(self, movie: Movie, genre: Genre) -> MovieGenre:
        """
        Set a specific genre as primary for a movie.

        Args:
            movie: Movie instance
            genre: Genre instance to set as primary

        Returns:
            MovieGenre instance that was set as primary

        Raises:
            ValidationException: If movie or genre is invalid
            DatabaseException: If database operations fail
        """
        if not movie or not genre:
            raise ValidationException("Both movie and genre are required")

        logger.info(f"Setting primary genre '{genre.name}' for movie '{movie.title}'")

        try:
            with transaction.atomic():
                # Remove primary flag from all existing genres for this movie
                MovieGenre.objects.filter(movie=movie, is_primary=True).update(
                    is_primary=False
                )

                # Get or create the movie-genre relationship
                movie_genre, created = MovieGenre.objects.get_or_create(
                    movie=movie,
                    genre=genre,
                    defaults={"is_primary": True, "weight": 1.0, "is_active": True},
                )

                # If it already existed, update it to be primary
                if not created and not movie_genre.is_primary:
                    movie_genre.is_primary = True
                    movie_genre.weight = 1.0
                    movie_genre.save(update_fields=["is_primary", "weight"])

                logger.info(f"Set '{genre.name}' as primary genre for '{movie.title}'")
                return movie_genre

        except Exception as e:
            logger.error(f"Failed to set primary genre: {e}")
            raise DatabaseException(f"Failed to set primary genre: {e}")

    def get_movies_by_genre(
        self, genre: Genre, filters: Optional[Dict] = None, limit: Optional[int] = None
    ) -> QuerySet[Movie]:
        """
        Get movies by genre with optional filters.

        Args:
            genre: Genre instance
            filters: Optional filters dict (e.g., {'min_rating': 7.0, 'min_year': 2000})
            limit: Optional limit on number of results

        Returns:
            QuerySet of Movie instances

        Raises:
            ValidationException: If genre is invalid
        """
        if not genre:
            raise ValidationException("Genre is required")

        logger.debug(f"Getting movies for genre: {genre.name}")

        try:
            # Start with basic query
            movies = Movie.objects.filter(genres=genre, is_active=True).distinct()

            # Apply filters if provided
            if filters:
                movies = self._apply_movie_filters(movies, filters)

            # Order by popularity and rating
            movies = movies.order_by("-popularity", "-vote_average")

            # Apply limit if specified
            if limit and limit > 0:
                movies = movies[:limit]

            logger.debug(
                f"Found {movies.count() if hasattr(movies, 'count') else len(movies)} "
                f"movies for genre {genre.name}"
            )
            return movies

        except Exception as e:
            logger.error(f"Failed to get movies for genre {genre.name}: {e}")
            raise DatabaseException(f"Failed to get movies by genre: {e}")

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    def _sync_single_genre(self, genre_data: Dict[str, Any]) -> tuple[Genre, bool]:
        """Synchronize a single genre from TMDb data."""
        tmdb_id = genre_data.get("tmdb_id")
        name = genre_data.get("name", "")

        if not tmdb_id or not name:
            raise ValidationException("Genre data missing required fields")

        # Get or create genre
        genre, created = Genre.objects.get_or_create(
            tmdb_id=tmdb_id,
            defaults={
                "name": name,
                "slug": self._generate_slug(name),
                "is_active": True,
            },
        )

        # Update existing genre if needed
        if not created:
            updated_fields = []

            if genre.name != name:
                genre.name = name
                updated_fields.append("name")

            new_slug = self._generate_slug(name)
            if genre.slug != new_slug:
                genre.slug = new_slug
                updated_fields.append("slug")

            if not genre.is_active:
                genre.is_active = True
                updated_fields.append("is_active")

            if updated_fields:
                genre.save(update_fields=updated_fields)

        return genre, created

    def _generate_slug(self, name: str) -> str:
        """Generate URL-friendly slug from genre name."""
        return slugify(name.lower().replace("&", "and"))

    def _apply_movie_filters(
        self, queryset: QuerySet[Movie], filters: Dict
    ) -> QuerySet[Movie]:
        """Apply filters to movie queryset."""
        if not filters:
            return queryset

        # Rating filter
        min_rating = filters.get("min_rating")
        if min_rating:
            queryset = queryset.filter(vote_average__gte=min_rating)

        max_rating = filters.get("max_rating")
        if max_rating:
            queryset = queryset.filter(vote_average__lte=max_rating)

        # Year filters
        min_year = filters.get("min_year")
        if min_year:
            queryset = queryset.filter(release_date__year__gte=min_year)

        max_year = filters.get("max_year")
        if max_year:
            queryset = queryset.filter(release_date__year__lte=max_year)

        # Popularity filter
        min_popularity = filters.get("min_popularity")
        if min_popularity:
            queryset = queryset.filter(popularity__gte=min_popularity)

        # Vote count filter (for reliability)
        min_votes = filters.get("min_votes")
        if min_votes:
            queryset = queryset.filter(vote_count__gte=min_votes)

        # Language filter
        language = filters.get("language")
        if language:
            queryset = queryset.filter(original_language=language)

        # Adult content filter
        include_adult = filters.get("include_adult", False)
        if not include_adult:
            queryset = queryset.filter(adult=False)

        return queryset

    def _invalidate_genre_cache(self) -> None:
        """
        Simplified cache invalidation since we're not caching model objects.
        """
        # Since we removed model object caching, this is much simpler
        try:
            # Only clear any data caches (not model caches)
            cache_keys_to_clear = [
                "genres:statistics",  # If you add this back later
            ]

            for key in cache_keys_to_clear:
                cache.delete(key)

            logger.debug("Genre cache invalidated")

        except Exception as e:
            logger.warning(f"Failed to invalidate genre cache: {e}")

    def _get_cache_key(self, prefix: str, identifier: Any) -> str:
        """Generate cache key with consistent format."""
        return f"genres:{prefix}:{identifier}"
