"""
Movie serializers.
"""

from rest_framework import serializers

from django.utils.translation import gettext_lazy as _

from core.constants import Language, MovieStatus, TMDBImageSize
from core.mixins.serializers import TimestampMixin, UserContextMixin

from ..models import Movie


class MovieListSerializer(TimestampMixin, serializers.ModelSerializer):
    """
    Lightweight movie serializer for list views and search results.
    Optimized for performance with minimal database queries.
    """

    # Computed fields
    release_year = serializers.ReadOnlyField()
    runtime_formatted = serializers.ReadOnlyField()
    rating_stars = serializers.ReadOnlyField()
    profit = serializers.ReadOnlyField()

    # URLs
    poster_url = serializers.SerializerMethodField()
    backdrop_url = serializers.SerializerMethodField()
    tmdb_url = serializers.ReadOnlyField()
    imdb_url = serializers.ReadOnlyField()

    # Genres (optimized)
    genre_names = serializers.ReadOnlyField()
    primary_genre = serializers.SerializerMethodField()

    class Meta:
        model = Movie
        fields = [
            "id",
            "tmdb_id",
            "title",
            "original_title",
            "tagline",
            "overview",
            "release_date",
            "release_year",
            "runtime",
            "runtime_formatted",
            "status",
            "original_language",
            "adult",
            "popularity",
            "vote_average",
            "vote_count",
            "rating_stars",
            "budget",
            "revenue",
            "profit",
            "poster_path",
            "poster_url",
            "backdrop_path",
            "backdrop_url",
            "homepage",
            "imdb_id",
            "tmdb_url",
            "imdb_url",
            "genre_names",
            "primary_genre",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tmdb_id",
            "popularity",
            "vote_average",
            "vote_count",
            "created_at",
            "updated_at",
        ]

    def get_poster_url(self, obj):
        """Get poster URL with configurable size."""
        size = self.context.get("poster_size", TMDBImageSize.W342)
        return obj.get_poster_url(size)

    def get_backdrop_url(self, obj):
        """Get backdrop URL with configurable size."""
        size = self.context.get("backdrop_size", TMDBImageSize.W780)
        return obj.get_backdrop_url(size)

    def get_primary_genre(self, obj):
        """Get primary genre info."""
        genre = obj.primary_genre
        if genre:
            return {"id": genre.id, "name": genre.name, "slug": genre.slug}
        return None


class MovieDetailSerializer(MovieListSerializer):
    """
    Detailed movie serializer with full information and relationships.
    Used for movie detail views and comprehensive data display.
    """

    # Extended relationships
    genres = serializers.SerializerMethodField()
    recommendations = serializers.SerializerMethodField()
    similar_movies = serializers.SerializerMethodField()

    # Additional computed fields
    is_recently_released = serializers.ReadOnlyField()
    is_popular = serializers.ReadOnlyField()
    is_highly_rated = serializers.ReadOnlyField()
    sync_age_hours = serializers.ReadOnlyField()

    class Meta(MovieListSerializer.Meta):
        fields = MovieListSerializer.Meta.fields + [
            "genres",
            "recommendations",
            "similar_movies",
            "is_recently_released",
            "is_popular",
            "is_highly_rated",
            "last_synced",
            "sync_status",
            "sync_age_hours",
            "metadata",
        ]

    def get_genres(self, obj):
        """Get full genre information with weights."""
        movie_genres = obj.movie_genres.select_related("genre").all()
        return [
            {
                "id": mg.genre.id,
                "tmdb_id": mg.genre.tmdb_id,
                "name": mg.genre.name,
                "slug": mg.genre.slug,
                "is_primary": mg.is_primary,
                "weight": mg.weight,
            }
            for mg in movie_genres
        ]

    def get_recommendations(self, obj):
        """Get TMDb recommendations (limited for performance)."""
        limit = self.context.get("recommendations_limit", 5)
        recommendations = obj.get_tmdb_recommendations(limit)

        return [
            {
                "id": movie.id,
                "tmdb_id": movie.tmdb_id,
                "title": movie.title,
                "poster_url": movie.get_poster_url("w185"),
                "vote_average": movie.vote_average,
                "release_year": movie.release_year,
            }
            for movie in recommendations
        ]

    def get_similar_movies(self, obj):
        """Get similar movies (limited for performance)."""
        limit = self.context.get("similar_limit", 5)
        similar = obj.get_tmdb_similar(limit)

        return [
            {
                "id": movie.id,
                "tmdb_id": movie.tmdb_id,
                "title": movie.title,
                "poster_url": movie.get_poster_url("w185"),
                "vote_average": movie.vote_average,
                "release_year": movie.release_year,
            }
            for movie in similar
        ]


class MovieCreateSerializer(UserContextMixin, serializers.ModelSerializer):
    """
    Movie creation serializer for TMDb data import.
    Used by sync commands and admin operations.
    """

    class Meta:
        model = Movie
        fields = [
            # Core Information
            "tmdb_id",
            "title",
            "original_title",
            "tagline",
            "overview",
            # Technical Details
            "runtime",
            "status",
            "original_language",
            "release_date",
            # Financial Information
            "budget",
            "revenue",
            # Media & External Links
            "poster_path",
            "backdrop_path",
            "homepage",
            "imdb_id",
            # Content Classification
            "adult",
            # TMDb Data (from TMDbContentMixin)
            "popularity",
            "vote_average",
            "vote_count",
            "last_synced",
            "sync_status",
            "sync_retries",
            # Flexible Data Storage
            "metadata",
            # Control Fields
            "is_active",
        ]
        extra_kwargs = {
            # Required fields for TMDb sync
            "tmdb_id": {"required": True},
            "title": {"required": False},  # Can be auto-filled from original_title
            "original_title": {"required": False},  # Can be auto-filled from title
            # Optional fields with reasonable defaults
            "status": {"default": MovieStatus.RELEASED},
            "original_language": {"default": Language.ENGLISH},
            "adult": {"default": False},
            "budget": {"default": 0},
            "revenue": {"default": 0},
            "popularity": {"default": 0.0},
            "vote_average": {"default": 0.0},
            "vote_count": {"default": 0},
            "is_active": {"default": True},
        }

    def validate_tmdb_id(self, value):
        """Validate TMDb ID uniqueness and format."""
        if not value:
            raise serializers.ValidationError(
                _("TMDb ID is required for movie creation.")
            )

        # Check if it's a valid number (TMDb IDs are integers)
        try:
            tmdb_id_int = int(value)
            if tmdb_id_int <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise serializers.ValidationError(_("TMDb ID must be a positive integer."))

        # Check uniqueness for new movies
        if self.instance is None:
            if Movie.objects.filter(tmdb_id=value).exists():
                raise serializers.ValidationError(
                    _("Movie with this TMDb ID already exists.")
                )

        return str(tmdb_id_int)  # Ensure consistent string format

    def validate_title(self, value):
        """Validate and clean title."""
        if value:
            value = value.strip()
            if len(value) < 1:
                raise serializers.ValidationError(_("Title cannot be empty."))
            if len(value) > 255:
                raise serializers.ValidationError(
                    _("Title cannot exceed 255 characters.")
                )
        return value

    def validate_original_title(self, value):
        """Validate and clean original title."""
        if value:
            value = value.strip()
            if len(value) < 1:
                raise serializers.ValidationError(_("Original title cannot be empty."))
            if len(value) > 255:
                raise serializers.ValidationError(
                    _("Original title cannot exceed 255 characters.")
                )
        return value

    def validate_runtime(self, value):
        """Validate runtime range."""
        if value is not None:
            if value < 1 or value > 600:
                raise serializers.ValidationError(
                    _("Runtime must be between 1 and 600 minutes.")
                )
        return value

    def validate_budget(self, value):
        """Validate budget is non-negative."""
        if value is not None and value < 0:
            raise serializers.ValidationError(_("Budget cannot be negative."))
        return value or 0

    def validate_revenue(self, value):
        """Validate revenue is non-negative."""
        if value is not None and value < 0:
            raise serializers.ValidationError(_("Revenue cannot be negative."))
        return value or 0

    def validate_vote_average(self, value):
        """Validate vote average range."""
        if value is not None and (value < 0.0 or value > 10.0):
            raise serializers.ValidationError(
                _("Vote average must be between 0.0 and 10.0.")
            )
        return value or 0.0

    def validate_vote_count(self, value):
        """Validate vote count is non-negative."""
        if value is not None and value < 0:
            raise serializers.ValidationError(_("Vote count cannot be negative."))
        return value or 0

    def validate_popularity(self, value):
        """Validate popularity is non-negative."""
        if value is not None and value < 0.0:
            raise serializers.ValidationError(_("Popularity cannot be negative."))
        return value or 0.0

    def validate_imdb_id(self, value):
        """Validate IMDb ID format."""
        if value:
            value = value.strip()
            if not value.startswith("tt") or len(value) < 9:
                raise serializers.ValidationError(
                    _("IMDb ID must start with 'tt' and be at least 9 characters long.")
                )
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        attrs = super().validate(attrs)

        # Ensure we have at least title or original_title
        title = attrs.get("title", "").strip() if attrs.get("title") else ""
        original_title = (
            attrs.get("original_title", "").strip()
            if attrs.get("original_title")
            else ""
        )

        if not title and not original_title:
            raise serializers.ValidationError(
                _("Either title or original_title is required.")
            )

        # Auto-fill missing title fields
        if not title and original_title:
            attrs["title"] = original_title
        elif not original_title and title:
            attrs["original_title"] = title

        # Validate homepage URL if provided
        homepage = attrs.get("homepage")
        if homepage and not (
            homepage.startswith("http://") or homepage.startswith("https://")
        ):
            raise serializers.ValidationError(
                {
                    "homepage": _(
                        "Homepage must be a valid URL starting with http:// or https://"
                    )
                }
            )

        # Validate release date is not in the far future
        release_date = attrs.get("release_date")
        if release_date:
            from datetime import timedelta

            from django.utils import timezone

            # Allow up to 5 years in the future for announced movies
            max_future_date = timezone.now().date() + timedelta(days=365 * 5)
            if release_date > max_future_date:
                raise serializers.ValidationError(
                    {
                        "release_date": _(
                            "Release date cannot be more than 5 years in the future."
                        )
                    }
                )

        return attrs

    def create(self, validated_data):
        """Create movie with proper sync status."""
        # Add missing import
        from django.utils import timezone

        validated_data["sync_status"] = "success"
        validated_data["last_synced"] = timezone.now()

        return super().create(validated_data)


class MovieUpdateSerializer(UserContextMixin, serializers.ModelSerializer):
    """
    Movie update serializer for manual edits and sync updates.
    More permissive than create serializer for editing existing movies.
    """

    class Meta:
        model = Movie
        fields = [
            # Core Information (editable)
            "title",
            "original_title",
            "tagline",
            "overview",
            # Technical Details (editable)
            "runtime",
            "status",
            "original_language",
            "release_date",
            # Financial Information (editable)
            "budget",
            "revenue",
            # Media & External Links (editable)
            "poster_path",
            "backdrop_path",
            "homepage",
            "imdb_id",
            # Content Classification (editable)
            "adult",
            # TMDb Data (usually from sync, but allow manual override)
            "popularity",
            "vote_average",
            "vote_count",
            # Sync fields (admin only)
            "last_synced",
            "sync_status",
            "sync_retries",
            # Flexible Data Storage
            "metadata",
            # Control Fields
            "is_active",
        ]
        # Note: tmdb_id is intentionally excluded from updates to prevent conflicts

    def validate_title(self, value):
        """Validate and clean title."""
        if value is not None:  # Allow None for partial updates
            value = value.strip()
            if value and len(value) > 255:
                raise serializers.ValidationError(
                    _("Title cannot exceed 255 characters.")
                )
        return value

    def validate_original_title(self, value):
        """Validate and clean original title."""
        if value is not None:
            value = value.strip()
            if value and len(value) > 255:
                raise serializers.ValidationError(
                    _("Original title cannot exceed 255 characters.")
                )
        return value

    def validate_tagline(self, value):
        """Validate tagline length."""
        if value and len(value) > 500:
            raise serializers.ValidationError(
                _("Tagline cannot exceed 500 characters.")
            )
        return value

    def validate_runtime(self, value):
        """Validate runtime range."""
        if value is not None and value > 0 and (value < 1 or value > 600):
            raise serializers.ValidationError(
                _("Runtime must be between 1 and 600 minutes.")
            )
        return value

    def validate_budget(self, value):
        """Validate budget is non-negative."""
        if value is not None and value < 0:
            raise serializers.ValidationError(_("Budget cannot be negative."))
        return value

    def validate_revenue(self, value):
        """Validate revenue is non-negative."""
        if value is not None and value < 0:
            raise serializers.ValidationError(_("Revenue cannot be negative."))
        return value

    def validate_vote_average(self, value):
        """Validate vote average range."""
        if value is not None and (value < 0.0 or value > 10.0):
            raise serializers.ValidationError(
                _("Vote average must be between 0.0 and 10.0.")
            )
        return value

    def validate_vote_count(self, value):
        """Validate vote count is non-negative."""
        if value is not None and value < 0:
            raise serializers.ValidationError(_("Vote count cannot be negative."))
        return value

    def validate_popularity(self, value):
        """Validate popularity is non-negative."""
        if value is not None and value < 0.0:
            raise serializers.ValidationError(_("Popularity cannot be negative."))
        return value

    def validate_imdb_id(self, value):
        """Validate IMDb ID format and uniqueness."""
        if value:
            value = value.strip()
            if not value.startswith("tt") or len(value) < 9:
                raise serializers.ValidationError(
                    _("IMDb ID must start with 'tt' and be at least 9 characters long.")
                )

            # Check uniqueness excluding current instance
            if (
                Movie.objects.filter(imdb_id=value)
                .exclude(pk=self.instance.pk)
                .exists()
            ):
                raise serializers.ValidationError(
                    _("Movie with this IMDb ID already exists.")
                )
        return value

    def validate_homepage(self, value):
        """Validate homepage URL format."""
        if value and not (value.startswith("http://") or value.startswith("https://")):
            raise serializers.ValidationError(
                _("Homepage must be a valid URL starting with http:// or https://")
            )
        return value

    def validate_sync_retries(self, value):
        """Validate sync retries is non-negative."""
        if value is not None and value < 0:
            raise serializers.ValidationError(_("Sync retries cannot be negative."))
        return value

    def validate(self, attrs):
        """Cross-field validation for updates."""
        attrs = super().validate(attrs)

        # If updating titles, ensure at least one is not empty
        title = attrs.get("title")
        original_title = attrs.get("original_title")

        # Only validate if both are being updated and both would be empty
        if (
            title is not None
            and original_title is not None
            and not title.strip()
            and not original_title.strip()
        ):
            raise serializers.ValidationError(
                _("At least one of title or original_title must be provided.")
            )

        # Auto-fill missing title if updating one but not the other
        if title is not None and title.strip() and original_title is None:
            # If updating title but not original_title, and instance has empty
            # original_title
            if not self.instance.original_title:
                attrs["original_title"] = title.strip()
        elif original_title is not None and original_title.strip() and title is None:
            # If updating original_title but not title, and instance has empty title
            if not self.instance.title:
                attrs["title"] = original_title.strip()

        # Validate release date is reasonable
        release_date = attrs.get("release_date")
        if release_date:
            from datetime import date, timedelta

            from django.utils import timezone

            # Don't allow dates before 1888 (first film) or too far in the future
            min_date = date(1888, 1, 1)
            max_future_date = timezone.now().date() + timedelta(days=365 * 5)

            if release_date < min_date:
                raise serializers.ValidationError(
                    {"release_date": _("Release date cannot be before 1888.")}
                )

            if release_date > max_future_date:
                raise serializers.ValidationError(
                    {
                        "release_date": _(
                            "Release date cannot be more than 5 years in the future."
                        )
                    }
                )

        return attrs

    def update(self, instance, validated_data):
        """Custom update logic with metadata merging and genre handling."""
        from django.utils import timezone

        # Handle genre_ids
        genre_ids = validated_data.pop("genre_ids", None)

        # Handle metadata updates specially - merge instead of replace
        if "metadata" in validated_data:
            metadata = validated_data.pop("metadata")
            if isinstance(metadata, dict) and isinstance(instance.metadata, dict):
                # Deep merge metadata
                merged_metadata = instance.metadata.copy()
                merged_metadata.update(metadata)
                validated_data["metadata"] = merged_metadata
            else:
                validated_data["metadata"] = metadata

        # Track sync status changes
        sync_status = validated_data.get("sync_status")
        if sync_status and sync_status != instance.sync_status:
            if sync_status == "success":
                validated_data["sync_retries"] = 0
                if "last_synced" not in validated_data:
                    validated_data["last_synced"] = timezone.now()

        # Update last_synced if sync fields are being updated
        sync_fields = {
            "popularity",
            "vote_average",
            "vote_count",
            "poster_path",
            "backdrop_path",
        }
        if any(field in validated_data for field in sync_fields):
            if "last_synced" not in validated_data:
                validated_data["last_synced"] = timezone.now()
            if "sync_status" not in validated_data:
                validated_data["sync_status"] = "success"

        # Update the instance
        instance = super().update(instance, validated_data)

        # Handle genre associations if provided
        if genre_ids is not None:
            # Clear existing genres and create new ones
            from ..models import MovieGenre

            MovieGenre.objects.filter(movie=instance).delete()

            for i, genre_id in enumerate(genre_ids):
                MovieGenre.objects.create(
                    movie=instance,
                    genre_id=genre_id,
                    is_primary=(i == 0),  # First genre is primary
                    weight=max(0.1, 1.0 - (i * 0.1)),  # Decreasing weight
                )

        return instance


class MovieSimpleSerializer(serializers.ModelSerializer):
    """
    Minimal movie serializer for relationships and references.
    """

    release_year = serializers.ReadOnlyField()
    poster_url = serializers.SerializerMethodField()

    class Meta:
        model = Movie
        fields = [
            "id",
            "tmdb_id",
            "title",
            "release_date",
            "release_year",
            "vote_average",
            "poster_path",
            "poster_url",
        ]

    def get_poster_url(self, obj):
        """Get small poster for search results."""
        return obj.get_poster_url("w185")

    def get_primary_genre_name(self, obj):
        """Get primary genre name."""
        genre = obj.primary_genre
        return genre.name if genre else None


class MovieSearchSerializer(serializers.ModelSerializer):
    """
    Minimal movie serializer for search results.
    Extremely lightweight for fast search responses.
    """

    release_year = serializers.ReadOnlyField()
    poster_url = serializers.SerializerMethodField()
    primary_genre_name = serializers.SerializerMethodField()

    class Meta:
        model = Movie
        fields = [
            "id",
            "tmdb_id",
            "title",
            "original_title",
            "release_date",
            "release_year",
            "vote_average",
            "popularity",
            "poster_path",
            "poster_url",
            "primary_genre_name",
            "adult",
        ]

    def get_poster_url(self, obj):
        """Get small poster for search results."""
        return obj.get_poster_url("w185")

    def get_primary_genre_name(self, obj):
        """Get primary genre name."""
        genre = obj.primary_genre
        return genre.name if genre else None
