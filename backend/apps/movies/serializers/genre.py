"""
Genre serializers.
"""

from rest_framework import serializers

from django.utils.translation import gettext_lazy as _

from core.mixins.serializers import TimestampMixin, UserContextMixin

from ..models import Genre


class GenreListSerializer(TimestampMixin, serializers.ModelSerializer):
    """
    Genre serializer for list views and selection dropdowns.
    Now works properly with active/inactive genres.
    """

    movie_count = serializers.ReadOnlyField()

    class Meta:
        model = Genre
        fields = [
            "id",
            "tmdb_id",
            "name",
            "slug",
            "movie_count",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tmdb_id",
            "slug",
            "movie_count",
            "created_at",
            "updated_at",
        ]


class GenreDetailSerializer(GenreListSerializer):
    """
    Detailed genre serializer with movie relationships.
    Used for genre detail pages and analytics.
    """

    popular_movies = serializers.SerializerMethodField()
    recent_movies = serializers.SerializerMethodField()

    class Meta(GenreListSerializer.Meta):
        fields = GenreListSerializer.Meta.fields + [
            "popular_movies",
            "recent_movies",
        ]

    def get_popular_movies(self, obj):
        """Get popular movies in this genre."""
        limit = self.context.get("popular_movies_limit", 10)
        movies = obj.get_popular_movies(limit)

        return [
            {
                "id": movie.id,
                "tmdb_id": movie.tmdb_id,
                "title": movie.title,
                "poster_url": movie.get_poster_url("w185"),
                "vote_average": movie.vote_average,
                "popularity": movie.popularity,
                "release_year": movie.release_year,
            }
            for movie in movies
        ]

    def get_recent_movies(self, obj):
        """Get recent movies in this genre."""
        limit = self.context.get("recent_movies_limit", 10)
        movies = obj.get_recent_movies(limit)

        return [
            {
                "id": movie.id,
                "tmdb_id": movie.tmdb_id,
                "title": movie.title,
                "poster_url": movie.get_poster_url("w185"),
                "vote_average": movie.vote_average,
                "release_date": movie.release_date,
                "release_year": movie.release_year,
            }
            for movie in movies
        ]


class GenreCreateSerializer(UserContextMixin, serializers.ModelSerializer):
    """
    Genre creation serializer for TMDb sync operations.
    Updated to work with new manager setup.
    """

    class Meta:
        model = Genre
        fields = [
            "tmdb_id",
            "name",
            "slug",
            "is_active",
        ]
        extra_kwargs = {
            "is_active": {"default": True},
            "slug": {"required": False},
        }

    def validate_tmdb_id(self, value):
        """Validate TMDb ID uniqueness."""
        if self.instance is None:  # Creating new genre
            # Use objects (all records) to check for duplicates
            if Genre.objects.filter(tmdb_id=value).exists():
                raise serializers.ValidationError(
                    _("Genre with this TMDb ID already exists.")
                )
        return value

    def validate_name(self, value):
        """Validate genre name."""
        name = value.strip()

        if len(name) < 2:
            raise serializers.ValidationError(
                _("Genre name must be at least 2 characters long.")
            )

        # Check uniqueness using objects (all records) - exclude current instance
        # for updates
        queryset = Genre.objects.filter(name__iexact=name)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(_("Genre with this name already exists."))

        return name

    def validate_slug(self, value):
        """Validate slug uniqueness."""
        if not value:
            return value

        # Check uniqueness using objects (all records) - exclude current instance
        #  for updates
        queryset = Genre.objects.filter(slug=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(_("Genre with this slug already exists."))

        return value

    def create(self, validated_data):
        """Create genre with auto-generated slug if not provided."""
        # Ensure is_active is set to True if not provided
        if "is_active" not in validated_data:
            validated_data["is_active"] = True

        if not validated_data.get("slug") and validated_data.get("name"):
            from django.utils.text import slugify

            validated_data["slug"] = slugify(validated_data["name"])

        return super().create(validated_data)


class GenreUpdateSerializer(UserContextMixin, serializers.ModelSerializer):
    """
    Genre update serializer for administrative edits.
    Updated to work with new manager setup.
    """

    class Meta:
        model = Genre
        fields = [
            "name",
            "slug",
            "is_active",
        ]

    def validate_name(self, value):
        """Validate genre name for updates."""
        name = value.strip()

        if len(name) < 2:
            raise serializers.ValidationError(
                _("Genre name must be at least 2 characters long.")
            )

        # Check uniqueness excluding current instance using objects (all records)
        if (
            Genre.objects.filter(name__iexact=name)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError(_("Genre with this name already exists."))

        return name

    def validate_slug(self, value):
        """Validate slug for updates."""
        if not value:
            return value

        # Check uniqueness excluding current instance using objects (all records)
        if Genre.objects.filter(slug=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError(_("Genre with this slug already exists."))

        return value


class GenreSimpleSerializer(serializers.ModelSerializer):
    """
    Minimal genre serializer for nested relationships and quick references.
    """

    class Meta:
        model = Genre
        fields = [
            "id",
            "tmdb_id",
            "name",
            "slug",
        ]
        read_only_fields = ["id", "tmdb_id", "name", "slug"]


class GenreStatsSerializer(GenreListSerializer):
    """
    Genre serializer with statistical information.
    Used for analytics and reporting.
    """

    total_movies = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()
    total_revenue = serializers.SerializerMethodField()
    most_popular_movie = serializers.SerializerMethodField()

    class Meta(GenreListSerializer.Meta):
        fields = GenreListSerializer.Meta.fields + [
            "total_movies",
            "avg_rating",
            "total_revenue",
            "most_popular_movie",
        ]

    def get_total_movies(self, obj):
        """Get total number of active movies in genre."""
        return obj.movies.filter(is_active=True).count()

    def get_avg_rating(self, obj):
        """Get average rating of movies in genre."""
        from django.db.models import Avg

        avg_data = obj.movies.filter(
            is_active=True, vote_count__gte=10  # Only movies with sufficient votes
        ).aggregate(avg_rating=Avg("vote_average"))

        avg_rating = avg_data.get("avg_rating")
        return round(avg_rating, 2) if avg_rating else 0.0

    def get_total_revenue(self, obj):
        """Get total box office revenue for genre."""
        from django.db.models import Sum

        revenue_data = obj.movies.filter(is_active=True, revenue__gt=0).aggregate(
            total_revenue=Sum("revenue")
        )

        return revenue_data.get("total_revenue") or 0

    def get_most_popular_movie(self, obj):
        """Get the most popular movie in this genre."""
        movie = obj.movies.filter(is_active=True).order_by("-popularity").first()

        if movie:
            return {
                "id": movie.id,
                "tmdb_id": movie.tmdb_id,
                "title": movie.title,
                "popularity": movie.popularity,
                "vote_average": movie.vote_average,
                "poster_url": movie.get_poster_url("w185"),
            }
        return None
