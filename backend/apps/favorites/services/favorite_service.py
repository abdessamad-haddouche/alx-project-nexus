"""
Business logic service for Favorite operations.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from apps.movies.models import Movie
from core.exceptions import (
    MovieNotFoundException,
    NotFoundException,
    ValidationException,
)

from ..models import Favorite
from ..serializers import (
    FavoriteCreateSerializer,
    FavoriteListSerializer,
    FavoriteSerializer,
    FavoriteUpdateSerializer,
    UserFavoriteStatsSerializer,
    WatchlistSerializer,
)

# Type hints only
if TYPE_CHECKING:
    from apps.authentication.models import User
else:
    # Runtime imports
    from django.contrib.auth import get_user_model

    from apps.authentication.models import User

    User = get_user_model()


class FavoriteService:
    """
    Service class handling essential favorite operations.
    """

    # ================================================================
    # CORE OPERATIONS
    # ================================================================

    @staticmethod
    def add_favorite(user: User, movie_id: int, **kwargs) -> Dict[str, Any]:
        """Add a movie to user's favorites."""
        try:
            movie = Movie.objects.get(id=movie_id, is_active=True)
        except Movie.DoesNotExist:
            raise MovieNotFoundException(
                detail=_("Movie not found."), extra_data={"movie_id": movie_id}
            )

        if Favorite.objects.user_has_favorited(user, movie):
            raise ValidationException(
                detail=_("You have already favorited this movie."),
                field_errors={"movie": _("Already in favorites.")},
            )

        # Create favorite
        favorite_data = {"movie": movie.id, **kwargs}
        mock_request = type("MockRequest", (), {"user": user})()
        context = {"request": mock_request}
        serializer = FavoriteCreateSerializer(data=favorite_data, context=context)

        if not serializer.is_valid():
            raise ValidationException(
                detail=_("Invalid favorite data."), field_errors=serializer.errors
            )

        favorite = serializer.save()

        return {
            "success": True,
            "favorite": FavoriteSerializer(favorite).data,
            "message": _("Movie added to favorites successfully."),
        }

    @staticmethod
    def remove_favorite(user: User, movie_id: int) -> Dict[str, Any]:
        """Remove a movie from user's favorites."""
        try:
            favorite = Favorite.objects.get(
                user=user, movie_id=movie_id, is_active=True
            )
        except Favorite.DoesNotExist:
            raise NotFoundException(
                detail=_("This movie is not in your favorites."),
            )

        favorite.delete()  # Soft delete

        return {
            "success": True,
            "message": _("Movie removed from favorites."),
        }

    @staticmethod
    def toggle_favorite(user: User, movie_id: int) -> Dict[str, Any]:
        """Toggle favorite status (add/remove)."""
        try:
            movie = Movie.objects.get(id=movie_id, is_active=True)
        except Movie.DoesNotExist:
            raise MovieNotFoundException(detail=_("Movie not found."))

        if Favorite.objects.user_has_favorited(user, movie):
            FavoriteService.remove_favorite(user, movie_id)
            return {
                "is_favorited": False,
                "message": _("Movie removed from favorites."),
            }
        else:
            result = FavoriteService.add_favorite(user, movie_id)
            return {
                "is_favorited": True,
                "message": result["message"],
                "favorite": result["favorite"],
            }

    @staticmethod
    def update_favorite(user: User, movie_id: int, **updates) -> Dict[str, Any]:
        """Update an existing favorite."""
        try:
            favorite = Favorite.objects.get(
                user=user, movie_id=movie_id, is_active=True
            )
        except Favorite.DoesNotExist:
            raise NotFoundException(detail=_("This movie is not in your favorites."))

        serializer = FavoriteUpdateSerializer(
            instance=favorite, data=updates, partial=True
        )

        if not serializer.is_valid():
            raise ValidationException(
                detail=_("Invalid update data."), field_errors=serializer.errors
            )

        updated_favorite = serializer.save()

        return {
            "success": True,
            "favorite": FavoriteSerializer(updated_favorite).data,
            "message": _("Favorite updated successfully."),
        }

    @staticmethod
    def add_favorite_by_tmdb_id(user: User, tmdb_id: str, **kwargs) -> Dict[str, Any]:
        """Add a movie to user's favorites by TMDb ID (creates movie if needed)."""
        # Validate TMDb ID format
        try:
            tmdb_id_int = int(tmdb_id)
            if tmdb_id_int <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValidationException(
                detail=_("Invalid TMDb ID format."),
                field_errors={"tmdb_id": _("TMDb ID must be a positive integer.")},
            )

        tmdb_id = str(tmdb_id_int)

        try:
            movie = Movie.objects.get(tmdb_id=tmdb_id, is_active=True)
        except Movie.DoesNotExist:
            try:
                movie = FavoriteService._get_or_create_movie_from_tmdb(tmdb_id)
            except Exception as e:
                raise MovieNotFoundException(
                    detail=_("Could not fetch movie from TMDb."),
                    extra_data={"tmdb_id": tmdb_id, "error": str(e)},
                )

        return FavoriteService.add_favorite(user, movie.id, **kwargs)

    @staticmethod
    def _get_or_create_movie_from_tmdb(tmdb_id: str) -> Movie:
        """Fetch movie from TMDb API and create in database."""
        from apps.movies.serializers import MovieCreateSerializer
        from core.services.tmdb import tmdb_service

        movie_data = tmdb_service.get_movie_details(int(tmdb_id))

        if not movie_data:
            raise MovieNotFoundException(
                detail=_("Movie not found on TMDb."),
                extra_data={"tmdb_id": tmdb_id},
            )

        movie_create_data = {
            "tmdb_id": str(movie_data["tmdb_id"]),
            "title": movie_data.get("title", ""),
            "original_title": movie_data.get("original_title", ""),
            "tagline": movie_data.get("tagline", ""),
            "overview": movie_data.get("overview", ""),
            "runtime": movie_data.get("runtime"),
            "status": movie_data.get("status", "Released"),
            "original_language": movie_data.get("original_language", "en"),
            "release_date": movie_data.get("release_date"),
            "budget": movie_data.get("budget", 0),
            "revenue": movie_data.get("revenue", 0),
            "poster_path": movie_data.get("poster_path"),
            "backdrop_path": movie_data.get("backdrop_path"),
            "homepage": movie_data.get("homepage", ""),
            "imdb_id": movie_data.get("imdb_id"),
            "adult": movie_data.get("adult", False),
            "popularity": movie_data.get("popularity", 0.0),
            "vote_average": movie_data.get("vote_average", 0.0),
            "vote_count": movie_data.get("vote_count", 0),
            "main_trailer_key": movie_data.get("main_trailer_key"),
            "main_trailer_site": movie_data.get("main_trailer_site", "YouTube"),
            "is_active": True,
        }

        serializer = MovieCreateSerializer(data=movie_create_data)
        if not serializer.is_valid():
            raise ValidationException(
                detail=_("Invalid movie data from TMDb."),
                field_errors=serializer.errors,
            )

        return serializer.save()

    # ================================================================
    # WATCHLIST OPERATIONS
    # ================================================================

    @staticmethod
    def add_to_watchlist(user: User, movie_id: int) -> Dict[str, Any]:
        """Add movie to watchlist."""
        try:
            movie = Movie.objects.get(id=movie_id, is_active=True)
        except Movie.DoesNotExist:
            raise MovieNotFoundException(detail=_("Movie not found."))

        favorite, created = Favorite.objects.get_or_create(
            user=user, movie=movie, defaults={"is_watchlist": True}
        )

        if not created and favorite.is_watchlist:
            raise ValidationException(detail=_("Movie is already in your watchlist."))

        if not created:
            favorite.is_watchlist = True
            favorite.save(update_fields=["is_watchlist"])

        return {
            "success": True,
            "favorite": FavoriteSerializer(favorite).data,
            "message": _("Movie added to watchlist."),
        }

    @staticmethod
    def remove_from_watchlist(user: User, movie_id: int) -> Dict[str, Any]:
        """Remove movie from watchlist."""
        try:
            favorite = Favorite.objects.get(
                user=user, movie_id=movie_id, is_active=True, is_watchlist=True
            )
        except Favorite.DoesNotExist:
            raise NotFoundException(detail=_("This movie is not in your watchlist."))

        if not favorite.user_rating and not favorite.notes:
            favorite.delete()
            message = _("Movie removed from watchlist.")
        else:
            favorite.is_watchlist = False
            favorite.save(update_fields=["is_watchlist"])
            message = _("Movie removed from watchlist but kept in favorites.")

        return {
            "success": True,
            "message": message,
        }

    # ================================================================
    # RATING OPERATIONS
    # ================================================================

    @staticmethod
    def rate_movie(
        user: User, movie_id: int, rating: int, notes: str = ""
    ) -> Dict[str, Any]:
        """Rate a movie (creates favorite if doesn't exist)."""
        if not (1 <= rating <= 10):
            raise ValidationException(
                detail=_("Rating must be between 1 and 10."),
                field_errors={"rating": _("Invalid rating value.")},
            )

        try:
            movie = Movie.objects.get(id=movie_id, is_active=True)
        except Movie.DoesNotExist:
            raise MovieNotFoundException(detail=_("Movie not found."))

        favorite, created = Favorite.objects.get_or_create(
            user=user,
            movie=movie,
            defaults={"user_rating": rating, "notes": notes.strip()[:1000]},
        )

        if not created:
            favorite.user_rating = rating
            if notes:
                favorite.notes = notes.strip()[:1000]
            favorite.save(update_fields=["user_rating", "notes"])

        return {
            "success": True,
            "favorite": FavoriteSerializer(favorite).data,
            "message": _("Movie rated successfully."),
        }

    # ================================================================
    # USER DATA & ANALYTICS
    # ================================================================

    @staticmethod
    def get_user_favorites(user: User, limit: int = 20) -> Dict[str, Any]:
        """Get user's favorites list."""
        if limit > 50:
            limit = 50

        favorites = Favorite.objects.for_user(user)[:limit]

        return {
            "favorites": FavoriteListSerializer(favorites, many=True).data,
            "count": len(favorites),
        }

    @staticmethod
    def get_user_watchlist(user: User, limit: int = 20) -> Dict[str, Any]:
        """Get user's watchlist."""
        if limit > 50:
            limit = 50

        watchlist = Favorite.objects.user_watchlist(user)[:limit]

        return {
            "watchlist": WatchlistSerializer(watchlist, many=True).data,
            "count": len(watchlist),
        }

    @staticmethod
    def get_user_stats(user: User) -> Dict[str, Any]:
        """Get user's favorite statistics."""
        stats_data = Favorite.objects.user_activity_stats(user)
        return UserFavoriteStatsSerializer(stats_data).data

    @staticmethod
    def search_user_favorites(user: User, query: str) -> Dict[str, Any]:
        """Search within user's favorites."""
        if not query or len(query.strip()) < 2:
            raise ValidationException(
                detail=_("Search query must be at least 2 characters long."),
            )

        results = Favorite.objects.search_user_favorites(user, query.strip())[:20]

        return {
            "results": FavoriteListSerializer(results, many=True).data,
            "query": query.strip(),
            "count": len(results),
        }

    # ================================================================
    # MOVIE INSIGHTS
    # ================================================================

    @staticmethod
    def get_movie_popularity_stats(movie_id: int) -> Dict[str, Any]:
        """Get movie popularity stats based on favorites."""
        try:
            movie = Movie.objects.get(id=movie_id, is_active=True)
        except Movie.DoesNotExist:
            raise MovieNotFoundException(detail=_("Movie not found."))

        return Favorite.objects.movie_popularity_stats(movie)

    @staticmethod
    def get_trending_favorites(days: int = 7, limit: int = 10) -> List[Dict]:
        """Get trending favorited movies."""
        if days < 1 or days > 30:
            days = 7
        if limit > 20:
            limit = 20

        trending = Favorite.objects.most_favorited_movies(limit=limit, days=days)

        # Get movie details
        movie_ids = [item["movie"] for item in trending]
        movies = Movie.objects.filter(id__in=movie_ids, is_active=True)
        movie_map = {movie.id: movie for movie in movies}

        result = []
        for item in trending:
            movie = movie_map.get(item["movie"])
            if movie:
                result.append(
                    {
                        "movie_id": movie.id,
                        "movie_title": movie.title,
                        "movie_poster": movie.get_poster_url(),
                        "favorite_count": item["favorite_count"],
                        "avg_user_rating": item["avg_rating"],
                    }
                )

        return result

    # ================================================================
    # UTILITY METHODS
    # ================================================================

    @staticmethod
    def is_movie_favorited(user: User, movie_id: int) -> bool:
        """Check if user has favorited a movie."""
        try:
            movie = Movie.objects.get(id=movie_id, is_active=True)
            return Favorite.objects.user_has_favorited(user, movie)
        except Movie.DoesNotExist:
            return False

    @staticmethod
    def get_favorite_by_movie(user: User, movie_id: int) -> Optional[Dict]:
        """Get user's favorite for a specific movie."""
        try:
            favorite = Favorite.objects.get(
                user=user, movie_id=movie_id, is_active=True
            )
            return FavoriteSerializer(favorite).data
        except Favorite.DoesNotExist:
            return None

    @staticmethod
    def get_user_genre_preferences(user: User, limit: int = 5) -> List[Dict]:
        """Get user's top genre preferences."""
        if limit > 10:
            limit = 10

        genres = Favorite.objects.user_genre_preferences(user)[:limit]
        total_favorites = Favorite.objects.user_favorites_count(user)

        return [
            {
                "genre_name": genre.name,
                "favorite_count": getattr(genre, "favorite_count", 0),
                "percentage": round(
                    (getattr(genre, "favorite_count", 0) / max(1, total_favorites))
                    * 100,
                    1,
                ),
            }
            for genre in genres
        ]
