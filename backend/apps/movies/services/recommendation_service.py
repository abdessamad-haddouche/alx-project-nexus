"""
Recommendation Service - Business logic for movie recommendations.
"""


import logging
from typing import List, Optional

from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from core.constants import RecommendationSource, RecommendationType
from core.exceptions import (
    DatabaseException,
    MovieNotFoundException,
    TMDbAPIException,
    ValidationException,
)
from core.services.tmdb import tmdb_service

from ..models import Genre, Movie, MovieRecommendation

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Service class for movie recommendation operations.

    Responsibilities:
    - Generate various types of movie recommendations
    - Sync TMDb recommendation data
    - Create and manage recommendation relationships
    """

    def __init__(self):
        self.tmdb = tmdb_service
        self.cache_settings = settings.TMDB_SETTINGS.get("CACHE_SETTINGS", {})
        self._default_cache_timeout = 3600  # 1 hour for recommendations

    # =========================================================================
    # TRENDING RECOMMENDATIONS
    # =========================================================================

    def get_trending_recommendations(self, user=None, limit: int = 20) -> List[Movie]:
        """
        Get trending movie recommendations.

        Args:
            user: Optional user for personalization (not implemented yet)
            limit: Maximum number of recommendations

        Returns:
            List of trending Movie instances
        """
        if limit <= 0:
            raise ValidationException("Limit must be positive")

        logger.info(f"Getting {limit} trending recommendations")

        # Check cache first
        cache_key = f"recommendations:trending:{limit}"
        cached_recommendations = cache.get(cache_key)

        if cached_recommendations:
            # Get fresh Movie objects from cached IDs
            movie_ids = cached_recommendations
            movies = Movie.objects.filter(id__in=movie_ids, is_active=True)
            # Maintain order from cache
            ordered_movies = []
            for movie_id in movie_ids:
                movie = next((m for m in movies if m.id == movie_id), None)
                if movie:
                    ordered_movies.append(movie)

            logger.debug("Trending recommendations retrieved from cache")
            return ordered_movies[:limit]

        try:
            # Get trending movies based on popularity and recent activity
            trending_movies = Movie.objects.filter(
                is_active=True,
                release_date__isnull=False,
                vote_count__gte=100,  # Minimum votes for reliability
            ).order_by("-popularity", "-vote_average")[
                : limit * 2
            ]  # Get more to filter from

            # Apply additional filters for quality
            quality_movies = [
                movie
                for movie in trending_movies
                if movie.vote_average >= 6.0 and movie.vote_count >= 100
            ]

            # Take the requested limit
            final_recommendations = quality_movies[:limit]

            # Cache movie IDs (not objects)
            movie_ids = [movie.id for movie in final_recommendations]
            cache.set(cache_key, movie_ids, self._default_cache_timeout)

            logger.info(
                f"Generated {len(final_recommendations)} trending recommendations"
            )
            return final_recommendations

        except Exception as e:
            logger.error(f"Failed to get trending recommendations: {e}")
            raise DatabaseException(f"Failed to get trending recommendations: {e}")

    # =========================================================================
    # SIMILAR MOVIES
    # =========================================================================

    def get_similar_movies(self, movie_id: int, limit: int = 10) -> List[Movie]:
        """
        Get movies similar to the specified movie.

        Args:
            movie_id: Target movie's database ID
            limit: Maximum number of similar movies

        Returns:
            List of similar Movie instances
        """
        if limit <= 0:
            raise ValidationException("Limit must be positive")

        logger.info(f"Getting {limit} similar movies for movie ID {movie_id}")

        try:
            # Get the target movie
            try:
                target_movie = Movie.objects.get(id=movie_id, is_active=True)
            except Movie.DoesNotExist:
                raise MovieNotFoundException(f"Movie with ID {movie_id} not found")

            # Check cache first
            cache_key = f"recommendations:similar:{movie_id}:{limit}"
            cached_similar = cache.get(cache_key)

            if cached_similar:
                movie_ids = cached_similar
                movies = Movie.objects.filter(id__in=movie_ids, is_active=True)
                ordered_movies = []
                for movie_id_cached in movie_ids:
                    movie = next((m for m in movies if m.id == movie_id_cached), None)
                    if movie:
                        ordered_movies.append(movie)

                logger.debug("Similar movies retrieved from cache")
                return ordered_movies[:limit]

            # Try TMDb-based similar movies first
            tmdb_similar = target_movie.get_tmdb_similar(limit=limit)

            if len(tmdb_similar) >= limit:
                similar_movies = list(tmdb_similar)
            else:
                # Supplement with genre-based similar movies
                logger.info(
                    "Supplementing TMDb similar movies with genre-based recommendations"
                )

                # Get movies with shared genres
                target_genres = target_movie.genres.filter(is_active=True)

                if target_genres.exists():
                    genre_similar = (
                        Movie.objects.filter(
                            genres__in=target_genres,
                            is_active=True,
                            vote_average__gte=target_movie.vote_average
                            - 1.0,  # Similar quality
                        )
                        .exclude(id=target_movie.id)  # Exclude target movie
                        .distinct()
                        .order_by("-vote_average", "-popularity")[: limit * 2]
                    )

                    # Combine and deduplicate
                    all_similar = list(tmdb_similar) + list(genre_similar)
                    seen_ids = set()
                    similar_movies = []

                    for movie in all_similar:
                        if movie.id not in seen_ids and len(similar_movies) < limit:
                            similar_movies.append(movie)
                            seen_ids.add(movie.id)
                else:
                    similar_movies = list(tmdb_similar)

            # Cache movie IDs
            if similar_movies:
                movie_ids = [movie.id for movie in similar_movies]
                cache.set(cache_key, movie_ids, self._default_cache_timeout)

            logger.info(
                f"Found {len(similar_movies)} similar movies for {target_movie.title}"
            )
            return similar_movies[:limit]

        except MovieNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Failed to get similar movies: {e}")
            raise DatabaseException(f"Failed to get similar movies: {e}")

    # =========================================================================
    # GENRE-BASED RECOMMENDATIONS
    # =========================================================================

    def get_genre_based_recommendations(self, user, limit: int = 20) -> List[Movie]:
        """
        Get recommendations based on user's favorite genres.

        Args:
            user: User instance (for future implementation)
            limit: Maximum number of recommendations

        Returns:
            List of Movie instances based on popular genres
        """
        if limit <= 0:
            raise ValidationException("Limit must be positive")

        logger.info(f"Getting {limit} genre-based recommendations")

        # For now, use most popular genres since user preferences aren't implemented
        # TODO: Replace with actual user favorite genres when user system is ready

        try:
            # Get all active genres and calculate movie counts manually (no caching)
            genres = Genre.objects.filter(is_active=True)

            # Calculate movie counts for each genre
            genre_counts = []
            for genre in genres:
                movie_count = genre.movies.filter(is_active=True).count()
                if movie_count > 0:
                    genre_counts.append((genre, movie_count))

            # Sort by movie count and take top 5
            genre_counts.sort(key=lambda x: x[1], reverse=True)
            popular_genres = [genre for genre, count in genre_counts[:5]]

            if not popular_genres:
                logger.warning("No popular genres found for recommendations")
                return []

            # Get highly rated movies from these genres
            genre_movies = (
                Movie.objects.filter(
                    genres__in=popular_genres,
                    is_active=True,
                    vote_average__gte=7.0,
                    vote_count__gte=50,
                )
                .distinct()
                .order_by("-vote_average", "-popularity")[:limit]
            )

            recommendations = list(genre_movies)

            logger.info(f"Generated {len(recommendations)} genre-based recommendations")
            return recommendations

        except Exception as e:
            logger.error(f"Failed to get genre-based recommendations: {e}")
            raise DatabaseException(f"Failed to get genre-based recommendations: {e}")

    # =========================================================================
    # MOVIE-BASED RECOMMENDATION
    # =========================================================================

    def get_recommendations_for_movie(
        self, movie_id: int, limit: int = 10
    ) -> List[Movie]:
        """
        Get recommendations based on a specific movie a user watched.
        This is what you're looking for!

        Args:
            movie_id: ID of the movie the user watched
            limit: Maximum number of recommendations

        Returns:
            List of recommended movies based on the watched movie
        """
        if limit <= 0:
            raise ValidationException("Limit must be positive")

        logger.info(f"Getting recommendations based on movie ID: {movie_id}")

        try:
            # Get the source movie
            try:
                source_movie = Movie.objects.get(id=movie_id, is_active=True)
            except Movie.DoesNotExist:
                raise MovieNotFoundException(f"Movie with ID {movie_id} not found")

            # Strategy: Combine similar movies + genre-based recommendations
            similar_movies = self.get_similar_movies(movie_id, limit=limit // 2)

            # Get movies from same genres
            movie_genres = source_movie.genres.filter(is_active=True)

            if movie_genres.exists():
                genre_recommendations = (
                    Movie.objects.filter(
                        genres__in=movie_genres,
                        is_active=True,
                        vote_average__gte=source_movie.vote_average
                        - 0.5,  # Similar or better quality
                    )
                    .exclude(id=source_movie.id)  # Don't recommend the same movie
                    .distinct()
                    .order_by("-vote_average", "-popularity")[:limit]
                )
            else:
                genre_recommendations = []

            # Combine and deduplicate
            all_recommendations = list(similar_movies) + list(genre_recommendations)
            seen_ids = set()
            final_recommendations = []

            for movie in all_recommendations:
                if movie.id not in seen_ids and len(final_recommendations) < limit:
                    final_recommendations.append(movie)
                    seen_ids.add(movie.id)

            logger.info(
                f"Generated {len(final_recommendations)} recommendations based on "
                f"{source_movie.title}"
            )
            return final_recommendations

        except MovieNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Failed to get recommendations for movie {movie_id}: {e}")
            raise DatabaseException(f"Failed to get recommendations for movie: {e}")

    # =========================================================================
    # TMDB SYNCHRONIZATION
    # =========================================================================

    def sync_tmdb_recommendations(self, movie: Movie) -> List[MovieRecommendation]:
        """
        Sync TMDb recommendations for a specific movie.

        Args:
            movie: Movie instance to sync recommendations for

        Returns:
            List of MovieRecommendation instances created
        """
        if not movie:
            raise ValidationException("Movie is required")

        logger.info(f"Syncing TMDb recommendations for movie: {movie.title}")

        try:
            # Get recommendations from TMDb
            tmdb_recommendations = self.tmdb.get_movie_recommendations(
                movie_id=movie.tmdb_id, page=1
            )

            if not tmdb_recommendations or not tmdb_recommendations.get("results"):
                logger.info(f"No TMDb recommendations found for movie {movie.tmdb_id}")
                return []

            synced_recommendations = []

            with transaction.atomic():
                # Clear existing TMDb recommendations for this movie
                MovieRecommendation.objects.filter(
                    source_movie=movie,
                    recommendation_type=RecommendationType.TMDB_RECOMMENDATION,
                ).delete()

                # Create new recommendations
                for rec_data in tmdb_recommendations["results"][:20]:  # Limit to 20
                    try:
                        # Get or sync the recommended movie
                        rec_tmdb_id = rec_data.get("tmdb_id")
                        if not rec_tmdb_id:
                            continue

                        # Try to find existing movie
                        try:
                            recommended_movie = Movie.objects.get(
                                tmdb_id=rec_tmdb_id, is_active=True
                            )
                        except Movie.DoesNotExist:
                            # Movie doesn't exist locally - could sync it
                            logger.debug(
                                f"Recommended movie {rec_tmdb_id} not found locally"
                            )
                            continue

                        # Create recommendation relationship
                        recommendation = self.create_recommendation_entry(
                            source=movie,
                            target=recommended_movie,
                            rec_type=RecommendationType.TMDB_RECOMMENDATION,
                            confidence=None,  # TMDb doesn't provide confidence scores
                        )

                        synced_recommendations.append(recommendation)

                    except Exception as e:
                        logger.warning(f"Failed to sync individual recommendation: {e}")
                        continue

            logger.info(
                f"Synced {len(synced_recommendations)} TMDb recommendations for "
                f"{movie.title}"
            )
            return synced_recommendations

        except Exception as e:
            logger.error(
                f"Failed to sync TMDb recommendations for movie {movie.tmdb_id}: {e}"
            )
            raise TMDbAPIException(f"Failed to sync TMDb recommendations: {e}")

    def sync_tmdb_similar_movies(self, movie: Movie) -> List[MovieRecommendation]:
        """
        Sync TMDb similar movies for a specific movie.

        Args:
            movie: Movie instance to sync similar movies for

        Returns:
            List of MovieRecommendation instances created
        """
        if not movie:
            raise ValidationException("Movie is required")

        logger.info(f"Syncing TMDb similar movies for movie: {movie.title}")

        try:
            # Get similar movies from TMDb
            tmdb_similar = self.tmdb.get_similar_movies(movie_id=movie.tmdb_id, page=1)

            if not tmdb_similar or not tmdb_similar.get("results"):
                logger.info(f"No TMDb similar movies found for movie {movie.tmdb_id}")
                return []

            synced_similar = []

            with transaction.atomic():
                # Clear existing TMDb similar movies for this movie
                MovieRecommendation.objects.filter(
                    source_movie=movie,
                    recommendation_type=RecommendationType.TMDB_SIMILAR,
                ).delete()

                # Create new similar movie relationships
                for similar_data in tmdb_similar["results"][:20]:  # Limit to 20
                    try:
                        # Get or sync the similar movie
                        similar_tmdb_id = similar_data.get("tmdb_id")
                        if not similar_tmdb_id:
                            continue

                        # Try to find existing movie
                        try:
                            similar_movie = Movie.objects.get(
                                tmdb_id=similar_tmdb_id, is_active=True
                            )
                        except Movie.DoesNotExist:
                            # Movie doesn't exist locally
                            logger.debug(
                                f"Similar movie {similar_tmdb_id} not found locally"
                            )
                            continue

                        # Create similar movie relationship
                        recommendation = self.create_recommendation_entry(
                            source=movie,
                            target=similar_movie,
                            rec_type=RecommendationType.TMDB_SIMILAR,
                            confidence=None,
                        )

                        synced_similar.append(recommendation)

                    except Exception as e:
                        logger.warning(f"Failed to sync individual similar movie: {e}")
                        continue

            logger.info(
                f"Synced {len(synced_similar)} TMDb similar movies for {movie.title}"
            )
            return synced_similar

        except Exception as e:
            logger.error(
                f"Failed to sync TMDb similar movies for movie {movie.tmdb_id}: {e}"
            )
            raise TMDbAPIException(f"Failed to sync TMDb similar movies: {e}")

    # =========================================================================
    # RECOMMENDATION MANAGEMENT
    # =========================================================================

    def create_recommendation_entry(
        self,
        source: Movie,
        target: Movie,
        rec_type: RecommendationType,
        confidence: Optional[float] = None,
    ) -> MovieRecommendation:
        """
        Create a recommendation relationship between two movies.

        Args:
            source: Source movie that generates the recommendation
            target: Target movie being recommended
            rec_type: Type of recommendation
            confidence: Optional confidence score (0.0-1.0)

        Returns:
            MovieRecommendation instance

        Raises:
            ValidationException: If input data is invalid
            DatabaseException: If database operations fail
        """
        if not source or not target:
            raise ValidationException("Both source and target movies are required")

        if source.id == target.id:
            raise ValidationException("Movie cannot recommend itself")

        if confidence is not None and (confidence < 0.0 or confidence > 1.0):
            raise ValidationException("Confidence must be between 0.0 and 1.0")

        logger.debug(
            f"Creating recommendation: {source.title} → {target.title} ({rec_type})"
        )

        try:
            # Create or update recommendation
            recommendation, created = MovieRecommendation.objects.get_or_create(
                source_movie=source,
                recommended_movie=target,
                recommendation_type=rec_type,
                defaults={
                    "confidence_score": confidence,
                    "source": RecommendationSource.TMDB,
                    "is_active": True,
                },
            )

            if not created and recommendation.confidence_score != confidence:
                # Update confidence if it has changed
                recommendation.confidence_score = confidence
                recommendation.save(update_fields=["confidence_score"])

            logger.debug(
                f"{'Created' if created else 'Updated'} recommendation: "
                f"{recommendation}"
            )
            return recommendation

        except Exception as e:
            logger.error(f"Failed to create recommendation entry: {e}")
            raise DatabaseException(f"Failed to create recommendation: {e}")
