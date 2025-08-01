"""
MovieGenre through model serializers.
"""

from rest_framework import serializers

from django.utils.translation import gettext_lazy as _

from core.mixins.serializers import TimestampMixin, UserContextMixin

from ..models import Genre, Movie, MovieGenre


class MovieGenreListSerializer(TimestampMixin, serializers.ModelSerializer):
    """
    MovieGenre serializer for list views and relationship display.
    """

    # Use simple nested serializers to avoid circular imports
    movie = serializers.SerializerMethodField()
    genre = serializers.SerializerMethodField()

    class Meta:
        model = MovieGenre
        fields = [
            "id",
            "movie",
            "genre",
            "is_primary",
            "weight",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def get_movie(self, obj):
        """Get minimal movie data."""
        return {
            "id": obj.movie.id,
            "tmdb_id": obj.movie.tmdb_id,
            "title": obj.movie.title,
            "release_year": obj.movie.release_year,
            "vote_average": obj.movie.vote_average,
            "poster_url": obj.movie.get_poster_url("w185"),
        }

    def get_genre(self, obj):
        """Get minimal genre data."""
        return {
            "id": obj.genre.id,
            "tmdb_id": obj.genre.tmdb_id,
            "name": obj.genre.name,
            "slug": obj.genre.slug,
        }


class MovieGenreDetailSerializer(MovieGenreListSerializer):
    """
    Detailed MovieGenre serializer with extended information.
    """

    # Add movie and genre details for comprehensive view
    movie_title = serializers.CharField(source="movie.title", read_only=True)
    genre_name = serializers.CharField(source="genre.name", read_only=True)
    movie_popularity = serializers.FloatField(source="movie.popularity", read_only=True)
    movie_vote_average = serializers.FloatField(
        source="movie.vote_average", read_only=True
    )

    class Meta(MovieGenreListSerializer.Meta):
        fields = MovieGenreListSerializer.Meta.fields + [
            "movie_title",
            "genre_name",
            "movie_popularity",
            "movie_vote_average",
        ]


class MovieGenreCreateSerializer(UserContextMixin, serializers.ModelSerializer):
    """
    MovieGenre creation serializer for establishing movie-genre relationships.
    """

    class Meta:
        model = MovieGenre
        fields = [
            "movie",
            "genre",
            "is_primary",
            "weight",
        ]

    def validate_movie(self, value):
        """Validate movie exists and is active."""
        if not value.is_active:
            raise serializers.ValidationError(
                _("Cannot assign genres to inactive movies.")
            )
        return value

    def validate_genre(self, value):
        """Validate genre exists and is active."""
        if not value.is_active:
            raise serializers.ValidationError(
                _("Cannot assign inactive genres to movies.")
            )
        return value

    def validate_weight(self, value):
        """Validate weight is within acceptable range."""
        if value is not None and (value < 0.0 or value > 1.0):
            raise serializers.ValidationError(_("Weight must be between 0.0 and 1.0."))
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        attrs = super().validate(attrs)

        movie = attrs.get("movie")
        genre = attrs.get("genre")

        # Check for duplicate relationship
        if MovieGenre.objects.filter(movie=movie, genre=genre).exists():
            raise serializers.ValidationError(
                _("This movie-genre relationship already exists.")
            )

        # Validate primary genre logic
        is_primary = attrs.get("is_primary", False)
        if is_primary:
            # Check if movie already has a primary genre
            existing_primary = MovieGenre.objects.filter(
                movie=movie, is_primary=True, is_active=True
            ).exists()

            if existing_primary:
                raise serializers.ValidationError(
                    _(
                        "Movie already has a primary genre. Set is_primary=False or "
                        "update the existing primary genre."
                    )
                )

        return attrs

    def create(self, validated_data):
        """Create MovieGenre with automatic weight assignment."""
        movie = validated_data["movie"]
        is_primary = validated_data.get("is_primary", False)
        weight = validated_data.get("weight")

        # Auto-assign weight if not provided
        if weight is None:
            if is_primary:
                weight = 1.0
            else:
                # Count existing genres for this movie and assign decreasing weight
                existing_count = MovieGenre.objects.filter(
                    movie=movie, is_active=True
                ).count()
                weight = max(0.1, 1.0 - (existing_count * 0.1))

        validated_data["weight"] = weight
        return super().create(validated_data)


class MovieGenreUpdateSerializer(UserContextMixin, serializers.ModelSerializer):
    """
    MovieGenre update serializer for modifying relationships.
    """

    class Meta:
        model = MovieGenre
        fields = [
            "is_primary",
            "weight",
            "is_active",
        ]

    def validate_weight(self, value):
        """Validate weight is within acceptable range."""
        if value is not None and (value < 0.0 or value > 1.0):
            raise serializers.ValidationError(_("Weight must be between 0.0 and 1.0."))
        return value

    def validate_is_primary(self, value):
        """Validate primary genre logic for updates."""
        # If setting to False, always allow
        if not value:
            return value

        # If setting to True, handle the switching in the update() method
        # Don't validate here, just return the value
        return value

    def update(self, instance, validated_data):
        """Custom update logic for primary genre management."""
        is_primary = validated_data.get("is_primary")

        if is_primary is True:
            MovieGenre.objects.filter(movie=instance.movie, is_primary=True).exclude(
                pk=instance.pk
            ).update(is_primary=False)

            # Set higher weight for primary genre if not specified
            if "weight" not in validated_data:
                validated_data["weight"] = 1.0

        return super().update(instance, validated_data)


class MovieGenreBulkCreateSerializer(UserContextMixin, serializers.Serializer):
    """
    Bulk creation serializer for multiple movie-genre relationships.
    Used for TMDb sync operations and batch assignments.
    """

    movie_id = serializers.IntegerField()
    genre_assignments = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=10,  # Reasonable limit for genres per movie
    )

    def validate_movie_id(self, value):
        """Validate movie exists."""
        try:
            movie = Movie.objects.get(pk=value, is_active=True)
            return movie
        except Movie.DoesNotExist:
            raise serializers.ValidationError(_("Movie not found or inactive."))

    def validate_genre_assignments(self, value):
        """Validate genre assignment data."""
        validated_assignments = []
        genre_ids = []
        primary_count = 0

        for assignment in value:
            # Validate required fields
            if "genre_id" not in assignment:
                raise serializers.ValidationError(
                    _("Each assignment must include 'genre_id'.")
                )

            genre_id = assignment["genre_id"]

            # Check for duplicates
            if genre_id in genre_ids:
                raise serializers.ValidationError(
                    _("Duplicate genre assignments are not allowed.")
                )
            genre_ids.append(genre_id)

            # Validate genre exists
            try:
                genre = Genre.objects.get(pk=genre_id, is_active=True)
            except Genre.DoesNotExist:
                raise serializers.ValidationError(
                    _("Genre with ID {} not found or inactive.").format(genre_id)
                )

            # Validate optional fields
            is_primary = assignment.get("is_primary", False)
            weight = assignment.get("weight")

            if is_primary:
                primary_count += 1

            if weight is not None and (weight < 0.0 or weight > 1.0):
                raise serializers.ValidationError(
                    _("Weight must be between 0.0 and 1.0.")
                )

            validated_assignments.append(
                {
                    "genre": genre,
                    "is_primary": is_primary,
                    "weight": weight,
                }
            )

        # Ensure only one primary genre
        if primary_count > 1:
            raise serializers.ValidationError(
                _("Only one genre can be marked as primary.")
            )

        return validated_assignments

    def create(self, validated_data):
        """Create multiple MovieGenre relationships."""
        movie = validated_data[
            "movie_id"
        ]  # Already validated and converted to Movie instance
        assignments = validated_data["genre_assignments"]

        created_relationships = []

        for i, assignment in enumerate(assignments):
            # Auto-assign weight if not provided
            weight = assignment["weight"]
            if weight is None:
                if assignment["is_primary"]:
                    weight = 1.0
                else:
                    existing_count = MovieGenre.objects.filter(
                        movie=movie, is_active=True
                    ).count()
                    weight = max(0.1, 1.0 - ((existing_count + i) * 0.1))

            # Create or update relationship
            movie_genre, created = MovieGenre.objects.get_or_create(
                movie=movie,
                genre=assignment["genre"],
                defaults={
                    "is_primary": assignment["is_primary"],
                    "weight": weight,
                },
            )

            if not created:
                # Update existing relationship
                movie_genre.is_primary = assignment["is_primary"]
                movie_genre.weight = weight
                movie_genre.save(update_fields=["is_primary", "weight"])

            created_relationships.append(movie_genre)

        return created_relationships

    def to_representation(self, instance):
        """Return created relationships."""
        return [
            {
                "id": mg.id,
                "movie_id": mg.movie.id,
                "genre_id": mg.genre.id,
                "genre_name": mg.genre.name,
                "is_primary": mg.is_primary,
                "weight": mg.weight,
            }
            for mg in instance
        ]
