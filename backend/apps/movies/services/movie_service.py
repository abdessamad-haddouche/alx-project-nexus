"""
Movie Service - Core business logic for movie operations.
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction

from core.constants import MovieStatus, RecommendationType, TMDBTimeWindow
from core.exceptions import (
    DatabaseException,
    MovieNotFoundException,
    TMDbAPIException,
    ValidationException,
)
from core.services.tmdb import tmdb_service

from ..models import Genre, Movie, MovieGenre, MovieRecommendation

logger = logging.getLogger(__name__)


class MovieService:
    """
    Service class for movie-related operations.

    Responsibilities:
    - Movie CRUD operations with TMDb integration
    - Data synchronization and caching
    - Business logic for movie operations
    """

    def __init__(self):
        self.tmdb = tmdb_service
        self.cache_settings = settings.TMDB_SETTINGS.get("CACHE_SETTINGS", {})
        self._default_cache_timeout = self.cache_settings.get("MOVIE_DETAILS_TTL", 3600)

    # =========================================================================
    # CORE MOVIE RETRIEVAL OPERATIONS
    # =========================================================================

    def get_movie_by_tmdb_id(self, tmdb_id: int) -> Optional[Movie]:
        """
        Get movie by TMDb ID - NO caching of model objects.
        """
        try:
            movie = Movie.objects.get(tmdb_id=tmdb_id, is_active=True)
            logger.debug(f"Movie {tmdb_id} retrieved from database")
            return movie
        except Movie.DoesNotExist:
            logger.info(f"Movie with TMDb ID {tmdb_id} not found in database")
            return None

    def get_movie_details(
        self, tmdb_id: int, force_sync: bool = False
    ) -> Dict[str, Any]:
        """
        Get complete movie details with caching of formatted data.
        """
        cache_key = f"movies:details:{tmdb_id}"
        if not force_sync:
            cached_details = cache.get(cache_key)
            if cached_details:
                logger.debug(f"Movie details {tmdb_id} retrieved from cache")
                return cached_details

        logger.info(f"Getting movie details for TMDb ID: {tmdb_id}")

        # Try to get existing movie
        movie = self.get_movie_by_tmdb_id(tmdb_id)

        # Determine if sync is needed
        needs_sync = not movie or force_sync or (movie and movie.needs_sync())

        if needs_sync:
            logger.info(f"Syncing movie {tmdb_id} from TMDb")
            movie = self.sync_movie_from_tmdb(tmdb_id)

        if not movie:
            raise MovieNotFoundException(
                f"Movie with TMDb ID {tmdb_id} not found",
                extra_data={"tmdb_id": tmdb_id},
            )

        # Format and cache the details
        formatted_details = self._format_movie_details(movie)
        cache.set(cache_key, formatted_details, self._default_cache_timeout)

        return formatted_details

    def search_movies(
        self, query: str, page: int = 1, sync_results: bool = True
    ) -> Dict[str, Any]:
        """
        Search movies with optional local sync of results.

        Args:
            query: Search query string
            page: Page number for pagination
            sync_results: Whether to sync found movies to local database

        Returns:
            Dictionary with search results and pagination info
        """
        if not query or not query.strip():
            raise ValidationException("Search query cannot be empty")

        logger.info(f"Searching movies for query: '{query}', page: {page}")

        # Check cache first
        cache_key = self._get_search_cache_key(query, page)
        cached_results = cache.get(cache_key)

        if cached_results:
            logger.debug(f"Search results retrieved from cache for query: '{query}'")
            return cached_results

        try:
            # Search via TMDb
            tmdb_results = self.tmdb.search_movies(query, page=page)

            # Process and format results
            formatted_results = self._format_search_results(tmdb_results, sync_results)

            # Cache results
            cache_timeout = self.cache_settings.get("SEARCH_RESULTS_TTL", 1800)
            cache.set(cache_key, formatted_results, cache_timeout)

            logger.info(
                f"Search completed for '{query}': "
                f"{len(formatted_results['results'])} results"
            )

            return formatted_results

        except Exception as e:
            logger.error(f"Search failed for query '{query}': {str(e)}")
            raise TMDbAPIException(f"Search failed: {str(e)}")

    # =========================================================================
    # TMDB SYNCHRONIZATION OPERATIONS
    # =========================================================================

    def sync_movie_from_tmdb(self, tmdb_id: int) -> Optional[Movie]:
        """
        Synchronize a single movie from TMDb.

        Args:
            tmdb_id: TMDb movie identifier

        Returns:
            Synchronized Movie instance or None if sync failed
        """
        logger.info(f"Starting sync for movie TMDb ID: {tmdb_id}")

        try:
            # Fetch movie data from TMDb
            tmdb_data = self.tmdb.get_movie_details(tmdb_id)

            if not tmdb_data:
                logger.warning(f"No data found for movie TMDb ID: {tmdb_id}")
                return None

            # Sync the movie
            with transaction.atomic():
                movie = self._sync_movie_data(tmdb_data)

                if movie:
                    # Clear cache for this movie
                    self._invalidate_movie_cache(tmdb_id)
                    logger.info(f"Successfully synced movie: {movie.title} ({tmdb_id})")

                return movie

        except Exception as e:
            logger.error(f"Failed to sync movie {tmdb_id}: {str(e)}")
            # Mark sync as failed if movie exists
            try:
                movie = Movie.objects.get(tmdb_id=tmdb_id)
                movie.mark_sync_failed()
            except Movie.DoesNotExist:
                pass
            return None

    def sync_genres_from_tmdb(self) -> List[Genre]:
        """
        Sync all movie genres from TMDb.
        Run this before syncing movies!
        """
        logger.info("Syncing genres from TMDb...")

        try:
            # Get genres from TMDb
            tmdb_genres = self.tmdb.get_genres_list()

            synced_genres = []
            for genre_data in tmdb_genres:
                genre, created = Genre.objects.get_or_create(
                    tmdb_id=genre_data["tmdb_id"],
                    defaults={
                        "name": genre_data["name"],
                        "slug": genre_data["slug"],
                        "is_active": True,
                    },
                )
                synced_genres.append(genre)

                if created:
                    logger.info(f"Created genre: {genre.name}")
                else:
                    logger.debug(f"Genre already exists: {genre.name}")

            logger.info(f"Synced {len(synced_genres)} genres")
            return synced_genres

        except Exception as e:
            logger.error(f"Failed to sync genres: {e}")
            return []

    def bulk_sync_movies(self, tmdb_ids: List[int]) -> List[Movie]:
        """
        Synchronize multiple movies from TMDb efficiently.

        Args:
            tmdb_ids: List of TMDb movie identifiers

        Returns:
            List of successfully synchronized Movie instances
        """
        if not tmdb_ids:
            return []

        logger.info(f"Starting bulk sync for {len(tmdb_ids)} movies")

        synced_movies = []
        failed_syncs = []

        for tmdb_id in tmdb_ids:
            try:
                movie = self.sync_movie_from_tmdb(tmdb_id)
                if movie:
                    synced_movies.append(movie)
                else:
                    failed_syncs.append(tmdb_id)

            except Exception as e:
                logger.error(
                    f"Failed to sync movie {tmdb_id} in bulk operation: {str(e)}"
                )
                failed_syncs.append(tmdb_id)

        logger.info(
            f"Bulk sync completed: {len(synced_movies)} successful, "
            f"{len(failed_syncs)} failed"
        )

        return synced_movies

    def update_movie_data(self, movie: Movie, tmdb_data: Dict[str, Any]) -> Movie:
        """
        Update an existing movie with fresh TMDb data.

        Args:
            movie: Existing Movie instance
            tmdb_data: Fresh data from TMDb

        Returns:
            Updated Movie instance
        """
        logger.info(f"Updating movie data for: {movie.title} ({movie.tmdb_id})")

        try:
            with transaction.atomic():
                # Update basic movie fields
                self._update_movie_fields(movie, tmdb_data)

                # Update genres
                self._sync_movie_genres(movie, tmdb_data.get("genre_ids", []))

                # Update recommendations if present
                if tmdb_data.get("recommendation_ids"):
                    self._sync_movie_recommendations(
                        movie, tmdb_data["recommendation_ids"]
                    )

                # Update similar movies if present
                if tmdb_data.get("similar_movie_ids"):
                    self._sync_movie_similar(movie, tmdb_data["similar_movie_ids"])

                # Mark sync as successful
                movie.mark_sync_success()

                # Clear cache
                self._invalidate_movie_cache(movie.tmdb_id)

                logger.info(f"Successfully updated movie: {movie.title}")
                return movie

        except Exception as e:
            logger.error(f"Failed to update movie {movie.tmdb_id}: {str(e)}")
            movie.mark_sync_failed()
            raise DatabaseException(f"Failed to update movie: {str(e)}")

    # =========================================================================
    # MOVIE DISCOVERY OPERATIONS
    # =========================================================================

    def get_popular_movies(
        self, page: int = 1, store_movies: bool = True
    ) -> Dict[str, Any]:
        """Get popular movies with SEARCH-STYLE storage"""
        logger.info(
            f"Getting popular movies, page: {page}, store_movies: {store_movies}"
        )

        cache_key = f"popular_movies:page:{page}:store:{store_movies}"
        cached_results = cache.get(cache_key)

        if cached_results:
            logger.debug("Popular movies retrieved from cache")
            return cached_results

        try:
            # Get data from TMDb
            tmdb_results = self.tmdb.movies.get_popular(page=page)

            formatted_results = self._format_search_results(
                tmdb_results, sync_results=store_movies
            )

            cache_timeout = self.cache_settings.get("POPULAR_MOVIES_TTL", 1800)
            cache.set(cache_key, formatted_results, cache_timeout)

            return formatted_results

        except Exception as e:
            logger.error(f"Failed to get popular movies: {str(e)}")
            raise TMDbAPIException(f"Failed to get popular movies: {str(e)}")

    def get_trending_movies(
        self, time_window: str = "day", store_movies: bool = True
    ) -> Dict[str, Any]:
        """Get trending movies with SEARCH-STYLE storage"""
        if time_window not in ["day", "week"]:
            raise ValidationException("time_window must be 'day' or 'week'")

        logger.info(
            f"Getting trending movies for time window: {time_window}, store_movies: {store_movies}"
        )

        cache_key = f"trending_movies:{time_window}:store:{store_movies}"
        cached_results = cache.get(cache_key)

        if cached_results:
            logger.debug(f"Trending movies ({time_window}) retrieved from cache")
            return cached_results

        try:
            # Convert string to enum
            time_window_enum = (
                TMDBTimeWindow.DAY if time_window == "day" else TMDBTimeWindow.WEEK
            )

            # Get data from TMDb
            tmdb_results = self.tmdb.movies.get_trending(time_window=time_window_enum)

            formatted_results = self._format_search_results(
                tmdb_results, sync_results=store_movies
            )

            cache_timeout = self.cache_settings.get("TRENDING_MOVIES_TTL", 900)
            cache.set(cache_key, formatted_results, cache_timeout)

            return formatted_results

        except Exception as e:
            logger.error(f"Failed to get trending movies: {str(e)}")
            raise TMDbAPIException(f"Failed to get trending movies: {str(e)}")

    def get_top_rated_movies(
        self, page: int = 1, store_movies: bool = True
    ) -> Dict[str, Any]:
        """Get top-rated movies with SEARCH-STYLE storage"""
        logger.info(
            f"Getting top-rated movies, page: {page}, store_movies: {store_movies}"
        )

        cache_key = f"top_rated_movies_page_{page}_store_{store_movies}"
        cached_results = cache.get(cache_key)

        if cached_results:
            logger.debug("Top-rated movies retrieved from cache")
            return cached_results

        try:
            # Get data from TMDb
            tmdb_results = self.tmdb.movies.get_top_rated(page=page)

            formatted_results = self._format_search_results(
                tmdb_results, sync_results=store_movies
            )

            cache_timeout = self.cache_settings.get("TOP_RATED_MOVIES_TTL", 43200)
            cache.set(cache_key, formatted_results, cache_timeout)

            movie_count = len(formatted_results.get("results", []))
            logger.info(f"Retrieved {movie_count} top-rated movies")

            return formatted_results

        except Exception as e:
            logger.error(f"Failed to get top-rated movies: {str(e)}")
            raise TMDbAPIException(f"Failed to get top-rated movies: {str(e)}")

    def get_movies_by_genre(
        self, genre_id: int, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Get movies by genre from local database with proper pagination.
        """
        logger.info(f"Getting movies for genre {genre_id}, page: {page}")

        try:
            # Verify genre exists
            genre = Genre.objects.get(tmdb_id=genre_id, is_active=True)

            # Get all movies for this genre (don't limit in manager)
            movies_queryset = Movie.objects.by_genre([genre_id])

            # Apply pagination using Django's Paginator
            paginator = Paginator(movies_queryset, page_size)

            try:
                movies_page = paginator.page(page)
            except PageNotAnInteger:
                # If page is not an integer, deliver first page
                movies_page = paginator.page(1)
            except EmptyPage:
                # If page is out of range, deliver last page
                movies_page = paginator.page(paginator.num_pages)

            # Format results
            results = {
                "results": [self._format_movie_basic(movie) for movie in movies_page],
                "pagination": {
                    "page": movies_page.number,
                    "page_size": page_size,
                    "total_pages": paginator.num_pages,
                    "total_results": paginator.count,
                    "has_next": movies_page.has_next(),
                    "has_previous": movies_page.has_previous(),
                    "next_page": movies_page.next_page_number()
                    if movies_page.has_next()
                    else None,
                    "previous_page": movies_page.previous_page_number()
                    if movies_page.has_previous()
                    else None,
                },
                "genre": {
                    "id": genre.tmdb_id,
                    "name": genre.name,
                    "slug": genre.slug,
                },
            }

            return results

        except Genre.DoesNotExist:
            raise ValidationException(f"Genre with ID {genre_id} not found")

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    def _sync_movie_data(self, tmdb_data: Dict[str, Any]) -> Optional[Movie]:
        """Synchronize movie data from TMDb response."""
        tmdb_id = tmdb_data.get("tmdb_id")

        if not tmdb_id:
            logger.error("TMDb data missing tmdb_id field")
            return None

        try:
            # Get or create movie
            movie, created = Movie.objects.get_or_create(
                tmdb_id=tmdb_id, defaults=self._prepare_movie_defaults(tmdb_data)
            )

            if not created:
                # Update existing movie
                self._update_movie_fields(movie, tmdb_data)

            # Sync genres
            genre_ids = tmdb_data.get("genre_ids", [])
            if genre_ids:
                self._sync_movie_genres(movie, genre_ids)

            logger.info(f"{'Created' if created else 'Updated'} movie: {movie.title}")
            return movie

        except Exception as e:
            logger.error(f"Failed to sync movie data for TMDb ID {tmdb_id}: {str(e)}")
            raise

    def _prepare_movie_defaults(self, tmdb_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare default values for movie creation."""
        runtime = tmdb_data.get("runtime")
        if runtime is None or runtime == 0:
            runtime = None

        imdb_id = tmdb_data.get("imdb_id")
        if imdb_id == "" or imdb_id is None:
            imdb_id = None

        return {
            "title": tmdb_data.get("title", ""),
            "original_title": tmdb_data.get("original_title", ""),
            "overview": tmdb_data.get("overview", ""),
            "release_date": self._parse_date(tmdb_data.get("release_date")),
            "runtime": runtime,
            "status": tmdb_data.get("status", MovieStatus.RELEASED),
            "original_language": tmdb_data.get("original_language", "en"),
            "adult": tmdb_data.get("adult", False),
            "popularity": tmdb_data.get("popularity", 0.0),
            "vote_average": tmdb_data.get("vote_average", 0.0),
            "vote_count": tmdb_data.get("vote_count", 0),
            "poster_path": tmdb_data.get("poster_path") or "",
            "backdrop_path": tmdb_data.get("backdrop_path") or "",
            "budget": tmdb_data.get("budget", 0),
            "revenue": tmdb_data.get("revenue", 0),
            "homepage": tmdb_data.get("homepage") or "",
            "imdb_id": imdb_id,
            "tagline": tmdb_data.get("tagline") or "",
            "main_trailer_key": tmdb_data.get("main_trailer_key"),
            "main_trailer_site": tmdb_data.get("main_trailer_site", "YouTube"),
        }

    def _update_movie_fields(self, movie: Movie, tmdb_data: Dict[str, Any]) -> None:
        """Update movie fields from TMDb data."""
        fields_to_update = []

        field_mapping = {
            "title": "title",
            "original_title": "original_title",
            "overview": "overview",
            "release_date": "release_date",
            "runtime": "runtime",
            "status": "status",
            "original_language": "original_language",
            "adult": "adult",
            "popularity": "popularity",
            "vote_average": "vote_average",
            "vote_count": "vote_count",
            "poster_path": "poster_path",
            "backdrop_path": "backdrop_path",
            "budget": "budget",
            "revenue": "revenue",
            "homepage": "homepage",
            "imdb_id": "imdb_id",
            "tagline": "tagline",
            "main_trailer_key": "main_trailer_key",
            "main_trailer_site": "main_trailer_site",
        }

        for tmdb_field, model_field in field_mapping.items():
            if tmdb_field in tmdb_data:
                value = tmdb_data[tmdb_field]

                if tmdb_field == "release_date":
                    value = self._parse_date(value)

                elif tmdb_field == "imdb_id":
                    if value == "" or value is None:
                        value = None

                if getattr(movie, model_field) != value:
                    setattr(movie, model_field, value)
                    fields_to_update.append(model_field)

        if fields_to_update:
            movie.save(update_fields=fields_to_update)

    def _sync_movie_genres(self, movie: Movie, genre_ids: List[int]) -> None:
        """Sync movie genres from TMDb genre IDs."""
        if not genre_ids:
            return

        # Get existing genres
        existing_genres = set(movie.genres.values_list("tmdb_id", flat=True))

        # Find genres to add/remove
        new_genre_ids = set(genre_ids)
        genres_to_add = new_genre_ids - existing_genres
        genres_to_remove = existing_genres - new_genre_ids

        # Remove old genres
        if genres_to_remove:
            MovieGenre.objects.filter(
                movie=movie, genre__tmdb_id__in=genres_to_remove
            ).delete()

        # Add new genres
        for genre_id in genres_to_add:
            try:
                genre = Genre.objects.get(tmdb_id=genre_id, is_active=True)
                MovieGenre.objects.get_or_create(
                    movie=movie, genre=genre, defaults={"weight": 1.0}
                )
            except Genre.DoesNotExist:
                logger.warning(f"Genre {genre_id} not found for movie {movie.tmdb_id}")

    def _sync_movie_recommendations(
        self, movie: Movie, recommendation_ids: List[int]
    ) -> None:
        """Sync TMDb recommendations for a movie."""
        self._sync_movie_relationships(
            movie, recommendation_ids, RecommendationType.TMDB_RECOMMENDATION
        )

    def _sync_movie_similar(self, movie: Movie, similar_ids: List[int]) -> None:
        """Sync TMDb similar movies for a movie."""
        self._sync_movie_relationships(
            movie, similar_ids, RecommendationType.TMDB_SIMILAR
        )

    def _sync_movie_relationships(
        self,
        movie: Movie,
        related_ids: List[int],
        relationship_type: RecommendationType,
    ) -> None:
        """Generic method to sync movie relationships."""
        if not related_ids:
            return

        # Clear existing relationships of this type
        MovieRecommendation.objects.filter(
            source_movie=movie, recommendation_type=relationship_type
        ).delete()

        # Create new relationships
        relationships_to_create = []

        for related_id in related_ids:
            try:
                related_movie = Movie.objects.get(tmdb_id=related_id, is_active=True)
                relationships_to_create.append(
                    MovieRecommendation(
                        source_movie=movie,
                        recommended_movie=related_movie,
                        recommendation_type=relationship_type,
                    )
                )
            except Movie.DoesNotExist:
                # Related movie doesn't exist locally - could trigger sync
                logger.debug(f"Related movie {related_id} not found locally")

        if relationships_to_create:
            MovieRecommendation.objects.bulk_create(
                relationships_to_create, ignore_conflicts=True
            )

    def _format_movie_details(self, movie: Movie) -> Dict[str, Any]:
        """Format movie for detailed view."""
        return {
            "id": movie.id,
            "tmdb_id": movie.tmdb_id,
            "title": movie.title,
            "original_title": movie.original_title,
            "overview": movie.overview,
            "tagline": movie.tagline,
            "release_date": movie.release_date.isoformat()
            if movie.release_date
            else None,
            "release_year": movie.release_year,
            "runtime": movie.runtime,
            "runtime_formatted": movie.runtime_formatted,
            "status": movie.status,
            "original_language": movie.original_language,
            "adult": movie.adult,
            "budget": movie.budget,
            "revenue": movie.revenue,
            "profit": movie.profit,
            "homepage": movie.homepage,
            "imdb_id": movie.imdb_id,
            "popularity": movie.popularity,
            "vote_average": movie.vote_average,
            "vote_count": movie.vote_count,
            "rating_stars": movie.rating_stars,
            "poster_path": movie.poster_path,
            "poster_url": movie.get_poster_url(),
            "backdrop_path": movie.backdrop_path,
            "backdrop_url": movie.get_backdrop_url(),
            "tmdb_url": movie.tmdb_url,
            "imdb_url": movie.imdb_url,
            "main_trailer_key": movie.main_trailer_key,
            "main_trailer_url": movie.main_trailer_url,
            "main_trailer_embed_url": movie.main_trailer_embed_url,
            "genres": [
                {
                    "id": genre.tmdb_id,
                    "name": genre.name,
                    "slug": genre.slug,
                }
                for genre in movie.genres.filter(is_active=True)
            ],
            "primary_genre": {
                "id": movie.primary_genre.tmdb_id,
                "name": movie.primary_genre.name,
            }
            if movie.primary_genre
            else None,
            "is_recently_released": movie.is_recently_released,
            "created_at": movie.created_at.isoformat(),
            "updated_at": movie.updated_at.isoformat(),
        }

    def _format_movie_basic(self, movie: Movie) -> Dict[str, Any]:
        """Format movie for list views."""
        return {
            "id": movie.id,
            "tmdb_id": movie.tmdb_id,
            "title": movie.title,
            "original_title": movie.original_title,
            "overview": movie.overview[:200] + "..."
            if len(movie.overview) > 200
            else movie.overview,
            "release_date": movie.release_date.isoformat()
            if movie.release_date
            else None,
            "release_year": movie.release_year,
            "popularity": movie.popularity,
            "vote_average": movie.vote_average,
            "vote_count": movie.vote_count,
            "rating_stars": movie.rating_stars,
            "poster_url": movie.get_poster_url(),
            "backdrop_url": movie.get_backdrop_url(),
            "genres": movie.genre_names,
            "primary_genre": movie.primary_genre.name if movie.primary_genre else None,
            "main_trailer_url": movie.main_trailer_url,
            "main_trailer_embed_url": movie.main_trailer_embed_url,
        }

    def _format_search_results(
        self, tmdb_results: Dict, sync_results: bool = False
    ) -> Dict[str, Any]:
        """Format search results from TMDb."""
        results = []

        for tmdb_movie in tmdb_results.get("results", []):
            # Check if movie exists locally
            local_movie = None
            if tmdb_movie.get("tmdb_id"):
                local_movie = self.get_movie_by_tmdb_id(tmdb_movie["tmdb_id"])

            if local_movie:
                # Use local movie data
                results.append(self._format_movie_basic(local_movie))
            else:
                # Use TMDb data directly
                results.append(self._format_tmdb_movie_basic(tmdb_movie))

                # Optionally sync to local database
                if sync_results and tmdb_movie.get("tmdb_id"):
                    try:
                        self.sync_movie_from_tmdb(tmdb_movie["tmdb_id"])
                    except Exception as e:
                        logger.warning(
                            f"Failed to sync movie {tmdb_movie['tmdb_id']} "
                            f"during search: {e}"
                        )

        return {
            "results": results,
            "pagination": tmdb_results.get("pagination", {}),
            "query": tmdb_results.get("query", ""),
        }

    def _store_basic_movie(self, tmdb_movie_data: Dict[str, Any]) -> Optional[Movie]:
        """Store basic movie data from TMDb list/search results in database."""
        from django.utils import timezone

        tmdb_id = tmdb_movie_data.get("tmdb_id") or tmdb_movie_data.get("id")

        if not tmdb_id:
            logger.warning("TMDb movie data missing tmdb_id")
            return None

        try:
            with transaction.atomic():
                # Check if already exists
                existing_movie = Movie.objects.filter(tmdb_id=tmdb_id).first()
                if existing_movie:
                    return existing_movie

                # Prepare basic movie data for storage
                movie_data = {
                    "tmdb_id": str(tmdb_id),
                    "title": tmdb_movie_data.get("title", ""),
                    "original_title": tmdb_movie_data.get("original_title", ""),
                    "overview": tmdb_movie_data.get("overview", ""),
                    "release_date": self._parse_date(
                        tmdb_movie_data.get("release_date")
                    ),
                    "adult": tmdb_movie_data.get("adult", False),
                    "popularity": tmdb_movie_data.get("popularity", 0.0),
                    "vote_average": tmdb_movie_data.get("vote_average", 0.0),
                    "vote_count": tmdb_movie_data.get("vote_count", 0),
                    "original_language": tmdb_movie_data.get("original_language", "en"),
                    "poster_path": tmdb_movie_data.get("poster_path") or "",
                    "backdrop_path": tmdb_movie_data.get("backdrop_path") or "",
                    "runtime": None,
                    "budget": 0,
                    "revenue": 0,
                    "homepage": "",
                    "imdb_id": tmdb_movie_data.get("imdb_id") or None,
                    "tagline": "",
                    "main_trailer_key": None,
                    "main_trailer_site": "YouTube",
                    "status": MovieStatus.RELEASED,
                    "sync_status": "partial",
                    "last_synced": timezone.now(),
                    "is_active": True,
                }

                # Create movie
                movie = Movie.objects.create(**movie_data)

                # Store genres if available
                genre_ids = tmdb_movie_data.get("genre_ids", [])
                if genre_ids:
                    self._sync_movie_genres(movie, genre_ids)

                logger.info(f"Stored basic movie: {movie.title} (ID: {movie.id})")
                return movie

        except Exception as e:
            logger.error(f"Failed to store basic movie {tmdb_id}: {str(e)}")
            return None

    def _format_tmdb_movie_basic(self, tmdb_movie: Dict) -> Dict[str, Any]:
        """Format TMDb movie data for basic display."""
        return {
            "tmdb_id": tmdb_movie.get("tmdb_id"),
            "title": tmdb_movie.get("title", ""),
            "original_title": tmdb_movie.get("original_title", ""),
            "overview": tmdb_movie.get("overview", "")[:200] + "..."
            if len(tmdb_movie.get("overview", "")) > 200
            else tmdb_movie.get("overview", ""),
            "release_date": tmdb_movie.get("release_date"),
            "release_year": tmdb_movie.get("release_date", "")[:4]
            if tmdb_movie.get("release_date")
            else None,
            "popularity": tmdb_movie.get("popularity", 0.0),
            "vote_average": tmdb_movie.get("vote_average", 0.0),
            "vote_count": tmdb_movie.get("vote_count", 0),
            "rating_stars": round(tmdb_movie.get("vote_average", 0.0) / 2, 1),
            "poster_url": tmdb_movie.get("poster_url"),
            "backdrop_url": tmdb_movie.get("backdrop_url"),
            "genres": [],
            "is_local": False,
        }

    def _parse_date(self, date_string: str) -> Optional[date]:
        """Parse date string to proper date object."""
        if not date_string:
            return None
        try:
            from datetime import datetime

            parsed_date = datetime.strptime(date_string, "%Y-%m-%d")
            return parsed_date.date()
        except (ValueError, TypeError):
            return None

    def _get_cache_key(self, prefix: str, identifier: Any) -> str:
        """Generate cache key with consistent format."""
        return f"movies:{prefix}:{identifier}"

    def _get_search_cache_key(self, query: str, page: int) -> str:
        """Generate cache key for search results."""
        import hashlib

        query_hash = hashlib.md5(query.lower().encode()).hexdigest()[:8]
        return f"movies:search:{query_hash}:page:{page}"

    def _invalidate_movie_cache(self, tmdb_id: int) -> None:
        """Invalidate all cache entries for a specific movie."""
        cache_keys = [
            self._get_cache_key("movie", tmdb_id),
            self._get_cache_key("details", tmdb_id),
        ]

        for key in cache_keys:
            cache.delete(key)
