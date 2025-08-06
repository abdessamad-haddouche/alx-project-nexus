"""
Serializers for Favorite model.
"""

from rest_framework import serializers

from django.utils.translation import gettext_lazy as _

from core.mixins.serializers import TimestampMixin, UserContextMixin

from ..models import Favorite


class FavoriteSerializer(TimestampMixin, UserContextMixin, serializers.ModelSerializer):
    """
    Full serializer for Favorite model with all fields.
    """

    # Related fields
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_full_name = serializers.CharField(source="user.get_full_name", read_only=True)

    # Movie details
    movie_title = serializers.CharField(source="movie.title", read_only=True)
    movie_poster = serializers.SerializerMethodField()
    movie_release_year = serializers.IntegerField(
        source="movie.release_year", read_only=True
    )
    movie_tmdb_id = serializers.CharField(source="movie.tmdb_id", read_only=True)
    movie_vote_average = serializers.FloatField(
        source="movie.vote_average", read_only=True
    )
    movie_genres = serializers.SerializerMethodField()

    # Computed fields
    rating_stars = serializers.ReadOnlyField()
    is_recent = serializers.ReadOnlyField()
    is_highly_rated_by_user = serializers.ReadOnlyField()
    days_favorited = serializers.SerializerMethodField()

    class Meta:
        model = Favorite
        fields = [
            # IDs and relationships
            "id",
            "user",
            "user_email",
            "user_full_name",
            "movie",
            "movie_tmdb_id",
            # Movie info
            "movie_title",
            "movie_poster",
            "movie_release_year",
            "movie_vote_average",
            "movie_genres",
            # User data
            "user_rating",
            "rating_stars",
            "notes",
            "is_watchlist",
            # Analytics
            "recommendation_source",
            "first_favorited",
            "last_interaction",
            # Computed properties
            "is_recent",
            "is_highly_rated_by_user",
            "days_favorited",
            # Base model fields
            "created_at",
            "updated_at",
            "is_active",
            "metadata",
        ]
        read_only_fields = [
            "id",
            "user",
            "first_favorited",
            "last_interaction",
            "created_at",
            "updated_at",
            "is_active",
            # All movie fields are read-only
            "user_email",
            "user_full_name",
            "movie_title",
            "movie_poster",
            "movie_release_year",
            "movie_tmdb_id",
            "movie_vote_average",
            "movie_genres",
            # Computed fields
            "rating_stars",
            "is_recent",
            "is_highly_rated_by_user",
            "days_favorited",
        ]

    def get_movie_poster(self, obj):
        """Get movie poster URL."""
        return obj.movie.get_poster_url() if obj.movie.poster_path else None

    def get_movie_genres(self, obj):
        """Get movie genre names."""
        return obj.movie.genre_names

    def get_days_favorited(self, obj):
        """Get days since favorited."""
        from django.utils import timezone

        return (timezone.now() - obj.first_favorited).days

    def validate_user_rating(self, value):
        """Validate user rating is in correct range."""
        if value is not None and not (1 <= value <= 10):
            raise serializers.ValidationError(_("Rating must be between 1 and 10."))
        return value

    def validate_notes(self, value):
        """Validate and clean notes."""
        if value:
            value = value.strip()
            if len(value) > 1000:
                raise serializers.ValidationError(
                    _("Notes cannot exceed 1000 characters.")
                )
        return value


class FavoriteCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new favorites.
    """

    class Meta:
        model = Favorite
        fields = [
            "movie",
            "user_rating",
            "notes",
            "is_watchlist",
            "recommendation_source",
        ]

    def validate_user_rating(self, value):
        """Validate user rating is in correct range."""
        if value is not None and not (1 <= value <= 10):
            raise serializers.ValidationError(_("Rating must be between 1 and 10."))
        return value

    def validate_notes(self, value):
        """Validate and clean notes."""
        if value:
            value = value.strip()
            if len(value) > 1000:
                raise serializers.ValidationError(
                    _("Notes cannot exceed 1000 characters.")
                )
        return value

    def create(self, validated_data):
        """Create favorite with current user."""
        user = self.context["request"].user
        movie = validated_data["movie"]

        # Check if user already favorited this movie
        if Favorite.objects.user_has_favorited(user, movie):
            raise serializers.ValidationError(
                {"movie": _("You have already favorited this movie.")}
            )

        validated_data["user"] = user
        return super().create(validated_data)


class FavoriteUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating existing favorites.
    """

    class Meta:
        model = Favorite
        fields = ["user_rating", "notes", "is_watchlist"]

    def validate_user_rating(self, value):
        """Validate user rating is in correct range."""
        if value is not None and not (1 <= value <= 10):
            raise serializers.ValidationError(_("Rating must be between 1 and 10."))
        return value

    def validate_notes(self, value):
        """Validate and clean notes."""
        if value:
            value = value.strip()
            if len(value) > 1000:
                raise serializers.ValidationError(
                    _("Notes cannot exceed 1000 characters.")
                )
        return value

    def update(self, instance, validated_data):
        """Update with automatic interaction timestamp update."""
        instance = super().update(instance, validated_data)
        instance.update_interaction()  # Update last_interaction
        return instance


class FavoriteListSerializer(TimestampMixin, serializers.ModelSerializer):
    """
    Lightweight serializer for listing favorites.
    """

    movie_title = serializers.CharField(source="movie.title", read_only=True)
    movie_poster = serializers.SerializerMethodField()
    movie_release_year = serializers.IntegerField(
        source="movie.release_year", read_only=True
    )
    movie_tmdb_id = serializers.CharField(source="movie.tmdb_id", read_only=True)
    movie_vote_average = serializers.FloatField(
        source="movie.vote_average", read_only=True
    )
    rating_stars = serializers.ReadOnlyField()

    class Meta:
        model = Favorite
        fields = [
            "id",
            "movie",
            "movie_tmdb_id",
            "movie_title",
            "movie_poster",
            "movie_release_year",
            "movie_vote_average",
            "user_rating",
            "rating_stars",
            "is_watchlist",
            "first_favorited",
            "is_recent",
        ]

    def get_movie_poster(self, obj):
        """Get movie poster URL."""
        return obj.movie.get_poster_url() if obj.movie.poster_path else None


class WatchlistSerializer(TimestampMixin, serializers.ModelSerializer):
    """
    Specialized serializer for watchlist items.
    """

    movie_title = serializers.CharField(source="movie.title", read_only=True)
    movie_poster = serializers.SerializerMethodField()
    movie_release_year = serializers.IntegerField(
        source="movie.release_year", read_only=True
    )
    movie_tmdb_id = serializers.CharField(source="movie.tmdb_id", read_only=True)
    movie_overview = serializers.CharField(source="movie.overview", read_only=True)
    movie_genres = serializers.SerializerMethodField()

    class Meta:
        model = Favorite
        fields = [
            "id",
            "movie",
            "movie_tmdb_id",
            "movie_title",
            "movie_poster",
            "movie_release_year",
            "movie_overview",
            "movie_genres",
            "first_favorited",
            "notes",
        ]

    def get_movie_poster(self, obj):
        """Get movie poster URL."""
        return obj.movie.get_poster_url() if obj.movie.poster_path else None

    def get_movie_genres(self, obj):
        """Get movie genre names."""
        return obj.movie.genre_names


class UserFavoriteStatsSerializer(UserContextMixin, serializers.Serializer):
    """
    Serializer for user's favorite activity statistics.
    """

    total_favorites = serializers.IntegerField(read_only=True)
    watchlist_count = serializers.IntegerField(read_only=True)
    rated_count = serializers.IntegerField(read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    recent_count = serializers.IntegerField(read_only=True)
    top_genres = serializers.ListField(child=serializers.CharField(), read_only=True)


class MoviePopularityStatsSerializer(serializers.Serializer):
    """
    Serializer for movie popularity statistics based on favorites.
    """

    total_favorites = serializers.IntegerField(read_only=True)
    average_user_rating = serializers.FloatField(read_only=True)
    recent_favorites_count = serializers.IntegerField(read_only=True)


class FavoriteToggleSerializer(UserContextMixin, serializers.Serializer):
    """
    Serializer for toggling favorite status.
    """

    movie_id = serializers.IntegerField()
    is_favorited = serializers.BooleanField(read_only=True)
    message = serializers.CharField(read_only=True)

    def validate_movie_id(self, value):
        """Validate movie exists."""
        from apps.movies.models import Movie

        try:
            Movie.objects.get(id=value, is_active=True)
        except Movie.DoesNotExist:
            raise serializers.ValidationError(_("Movie not found."))

        return value
