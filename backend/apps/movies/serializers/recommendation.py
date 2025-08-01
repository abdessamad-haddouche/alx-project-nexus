"""
Movie recommendation serializers.
"""

from rest_framework import serializers

from django.utils.translation import gettext_lazy as _

from core.constants import RecommendationSource, RecommendationType
from core.mixins.serializers import TimestampMixin, UserContextMixin

from ..models import Movie, MovieRecommendation


class MovieRecommendationListSerializer(TimestampMixin, serializers.ModelSerializer):
    """
    MovieRecommendation serializer for list views and relationship display.
    """

    source_movie = serializers.SerializerMethodField()
    recommended_movie = serializers.SerializerMethodField()
    confidence_percentage = serializers.ReadOnlyField()
    is_high_confidence = serializers.ReadOnlyField()

    class Meta:
        model = MovieRecommendation
        fields = [
            "id",
            "source_movie",
            "recommended_movie",
            "recommendation_type",
            "confidence_score",
            "confidence_percentage",
            "is_high_confidence",
            "source",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "confidence_percentage",
            "is_high_confidence",
            "created_at",
            "updated_at",
        ]

    def get_source_movie(self, obj):
        """Get minimal source movie data."""
        return {
            "id": obj.source_movie.id,
            "tmdb_id": obj.source_movie.tmdb_id,
            "title": obj.source_movie.title,
            "release_year": obj.source_movie.release_year,
            "vote_average": obj.source_movie.vote_average,
            "poster_url": obj.source_movie.get_poster_url("w185"),
        }

    def get_recommended_movie(self, obj):
        """Get minimal recommended movie data."""
        return {
            "id": obj.recommended_movie.id,
            "tmdb_id": obj.recommended_movie.tmdb_id,
            "title": obj.recommended_movie.title,
            "release_year": obj.recommended_movie.release_year,
            "vote_average": obj.recommended_movie.vote_average,
            "poster_url": obj.recommended_movie.get_poster_url("w185"),
        }


class MovieRecommendationDetailSerializer(MovieRecommendationListSerializer):
    """
    Detailed MovieRecommendation serializer with extended information.
    """

    # Additional computed fields
    source_movie_title = serializers.CharField(
        source="source_movie.title", read_only=True
    )
    recommended_movie_title = serializers.CharField(
        source="recommended_movie.title", read_only=True
    )
    source_movie_rating = serializers.FloatField(
        source="source_movie.vote_average", read_only=True
    )
    recommended_movie_rating = serializers.FloatField(
        source="recommended_movie.vote_average", read_only=True
    )
    recommendation_type_display = serializers.CharField(
        source="get_recommendation_type_display", read_only=True
    )
    source_display = serializers.CharField(source="get_source_display", read_only=True)

    class Meta(MovieRecommendationListSerializer.Meta):
        fields = MovieRecommendationListSerializer.Meta.fields + [
            "source_movie_title",
            "recommended_movie_title",
            "source_movie_rating",
            "recommended_movie_rating",
            "recommendation_type_display",
            "source_display",
        ]


class MovieRecommendationCreateSerializer(
    UserContextMixin, serializers.ModelSerializer
):
    """
    MovieRecommendation creation serializer for establishing recommendation
    relationships.
    """

    class Meta:
        model = MovieRecommendation
        fields = [
            "source_movie",
            "recommended_movie",
            "recommendation_type",
            "confidence_score",
            "source",
        ]

    def validate_source_movie(self, value):
        """Validate source movie exists and is active."""
        if not value.is_active:
            raise serializers.ValidationError(
                _("Cannot create recommendations from inactive movies.")
            )
        return value

    def validate_recommended_movie(self, value):
        """Validate recommended movie exists and is active."""
        if not value.is_active:
            raise serializers.ValidationError(_("Cannot recommend inactive movies."))
        return value

    def validate_confidence_score(self, value):
        """Validate confidence score range."""
        if value is not None and (value < 0.0 or value > 1.0):
            raise serializers.ValidationError(
                _("Confidence score must be between 0.0 and 1.0.")
            )
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        attrs = super().validate(attrs)

        source_movie = attrs.get("source_movie")
        recommended_movie = attrs.get("recommended_movie")
        recommendation_type = attrs.get("recommendation_type")

        # Prevent self-recommendations
        if source_movie.id == recommended_movie.id:
            raise serializers.ValidationError(_("A movie cannot recommend itself."))

        # Check for duplicate relationships
        if MovieRecommendation.objects.filter(
            source_movie=source_movie,
            recommended_movie=recommended_movie,
            recommendation_type=recommendation_type,
        ).exists():
            raise serializers.ValidationError(
                _("This recommendation relationship already exists.")
            )

        # Validate confidence score based on source
        source = attrs.get("source", RecommendationSource.TMDB)
        confidence_score = attrs.get("confidence_score")

        if source == RecommendationSource.TMDB and confidence_score is not None:
            # TMDb doesn't provide confidence scores, should be null
            attrs["confidence_score"] = None
        elif source == RecommendationSource.INTERNAL and confidence_score is None:
            # Internal algorithms should provide confidence scores
            raise serializers.ValidationError(
                _("Internal recommendations must include a confidence score.")
            )

        return attrs


class MovieRecommendationUpdateSerializer(
    UserContextMixin, serializers.ModelSerializer
):
    """
    MovieRecommendation update serializer for modifying recommendation relationships.
    """

    class Meta:
        model = MovieRecommendation
        fields = [
            "recommendation_type",
            "confidence_score",
            "source",
            "is_active",
        ]

    def validate_confidence_score(self, value):
        """Validate confidence score range."""
        if value is not None and (value < 0.0 or value > 1.0):
            raise serializers.ValidationError(
                _("Confidence score must be between 0.0 and 1.0.")
            )
        return value

    def validate(self, attrs):
        """Cross-field validation for updates."""
        attrs = super().validate(attrs)

        # Validate confidence score consistency with source
        source = attrs.get("source", self.instance.source if self.instance else None)
        confidence_score = attrs.get("confidence_score")

        if source == RecommendationSource.TMDB and confidence_score is not None:
            attrs["confidence_score"] = None
        elif source == RecommendationSource.INTERNAL and confidence_score is None:
            raise serializers.ValidationError(
                _("Internal recommendations must include a confidence score.")
            )

        return attrs


class MovieRecommendationBulkCreateSerializer(UserContextMixin, serializers.Serializer):
    """
    Bulk creation serializer for multiple movie recommendations.
    Used for TMDb sync operations and batch recommendation imports.
    """

    source_movie_id = serializers.IntegerField()
    recommendations = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=50,  # Reasonable limit for recommendations per movie
    )
    recommendation_type = serializers.ChoiceField(
        choices=RecommendationType.choices,
        default=RecommendationType.TMDB_RECOMMENDATION,
    )
    source = serializers.ChoiceField(
        choices=RecommendationSource.choices, default=RecommendationSource.TMDB
    )

    def validate_source_movie_id(self, value):
        """Validate source movie exists."""
        try:
            movie = Movie.objects.get(pk=value, is_active=True)
            return movie
        except Movie.DoesNotExist:
            raise serializers.ValidationError(_("Source movie not found or inactive."))

    def validate_recommendations(self, value):
        """Validate recommendation data."""
        validated_recommendations = []
        movie_ids = []

        for rec_data in value:
            # Validate required fields
            if "movie_id" not in rec_data:
                raise serializers.ValidationError(
                    _("Each recommendation must include 'movie_id'.")
                )

            movie_id = rec_data["movie_id"]

            # Check for duplicates
            if movie_id in movie_ids:
                raise serializers.ValidationError(
                    _("Duplicate movie recommendations are not allowed.")
                )
            movie_ids.append(movie_id)

            # Validate movie exists
            try:
                movie = Movie.objects.get(pk=movie_id, is_active=True)
            except Movie.DoesNotExist:
                raise serializers.ValidationError(
                    _("Recommended movie with ID {} not found or inactive.").format(
                        movie_id
                    )
                )

            # Validate optional confidence score
            confidence_score = rec_data.get("confidence_score")
            if confidence_score is not None and (
                confidence_score < 0.0 or confidence_score > 1.0
            ):
                raise serializers.ValidationError(
                    _("Confidence score must be between 0.0 and 1.0.")
                )

            validated_recommendations.append(
                {
                    "movie": movie,
                    "confidence_score": confidence_score,
                }
            )

        return validated_recommendations

    def validate(self, attrs):
        """Cross-field validation."""
        attrs = super().validate(attrs)

        source_movie = attrs["source_movie_id"]  # Already converted to Movie instance
        recommendations = attrs["recommendations"]
        source = attrs["source"]

        # Prevent self-recommendations
        for rec in recommendations:
            if source_movie.id == rec["movie"].id:
                raise serializers.ValidationError(_("A movie cannot recommend itself."))

        # Validate confidence scores based on source
        if source == RecommendationSource.TMDB:
            # TMDb doesn't provide confidence scores
            for rec in recommendations:
                rec["confidence_score"] = None
        elif source == RecommendationSource.INTERNAL:
            # Internal algorithms should provide confidence scores
            for rec in recommendations:
                if rec["confidence_score"] is None:
                    raise serializers.ValidationError(
                        _("Internal recommendations must include confidence scores.")
                    )

        return attrs

    def create(self, validated_data):
        """Create multiple MovieRecommendation relationships."""
        source_movie = validated_data["source_movie_id"]
        recommendations = validated_data["recommendations"]
        recommendation_type = validated_data["recommendation_type"]
        source = validated_data["source"]

        created_recommendations = []

        for rec_data in recommendations:
            # Create or update recommendation
            recommendation, created = MovieRecommendation.objects.get_or_create(
                source_movie=source_movie,
                recommended_movie=rec_data["movie"],
                recommendation_type=recommendation_type,
                defaults={
                    "confidence_score": rec_data["confidence_score"],
                    "source": source,
                },
            )

            if not created:
                # Update existing recommendation
                recommendation.confidence_score = rec_data["confidence_score"]
                recommendation.source = source
                recommendation.is_active = True  # Reactivate if was inactive
                recommendation.save(
                    update_fields=["confidence_score", "source", "is_active"]
                )

            created_recommendations.append(recommendation)

        return created_recommendations

    def to_representation(self, instance):
        """Return created recommendations."""
        return [
            {
                "id": rec.id,
                "source_movie_id": rec.source_movie.id,
                "recommended_movie_id": rec.recommended_movie.id,
                "recommended_movie_title": rec.recommended_movie.title,
                "recommendation_type": rec.recommendation_type,
                "confidence_score": rec.confidence_score,
                "confidence_percentage": rec.confidence_percentage,
                "source": rec.source,
            }
            for rec in instance
        ]


class MovieRecommendationSimpleSerializer(serializers.ModelSerializer):
    """
    Minimal recommendation serializer for nested relationships and quick references.
    """

    recommended_movie_title = serializers.CharField(
        source="recommended_movie.title", read_only=True
    )
    recommended_movie_poster = serializers.SerializerMethodField()
    confidence_percentage = serializers.ReadOnlyField()

    class Meta:
        model = MovieRecommendation
        fields = [
            "id",
            "recommended_movie",
            "recommended_movie_title",
            "recommended_movie_poster",
            "recommendation_type",
            "confidence_score",
            "confidence_percentage",
        ]
        read_only_fields = ["id", "recommended_movie_title", "confidence_percentage"]

    def get_recommended_movie_poster(self, obj):
        """Get poster URL for recommended movie."""
        return obj.recommended_movie.get_poster_url("w185")


class MovieWithRecommendationsSerializer(serializers.ModelSerializer):
    """
    Movie serializer that includes its recommendations.
    Used for recommendation feeds and discovery pages.
    """

    # Basic movie fields
    release_year = serializers.ReadOnlyField()
    poster_url = serializers.SerializerMethodField()

    # Recommendation fields
    tmdb_recommendations = serializers.SerializerMethodField()
    similar_movies = serializers.SerializerMethodField()
    all_recommendations_count = serializers.SerializerMethodField()

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
            "tmdb_recommendations",
            "similar_movies",
            "all_recommendations_count",
        ]
        read_only_fields = [
            "id",
            "tmdb_id",
            "title",
            "release_date",
            "vote_average",
            "poster_path",
        ]

    def get_poster_url(self, obj):
        """Get small poster URL."""
        return obj.get_poster_url("w185")

    def get_tmdb_recommendations(self, obj):
        """Get TMDb recommendations."""
        limit = self.context.get("recommendations_limit", 5)
        recommendations = obj.movie_recommendations_from.filter(
            recommendation_type=RecommendationType.TMDB_RECOMMENDATION, is_active=True
        ).select_related("recommended_movie")[:limit]

        return MovieRecommendationSimpleSerializer(recommendations, many=True).data

    def get_similar_movies(self, obj):
        """Get similar movies."""
        limit = self.context.get("similar_limit", 5)
        similar = obj.movie_recommendations_from.filter(
            recommendation_type=RecommendationType.TMDB_SIMILAR, is_active=True
        ).select_related("recommended_movie")[:limit]

        return MovieRecommendationSimpleSerializer(similar, many=True).data

    def get_all_recommendations_count(self, obj):
        """Get total count of all recommendations."""
        return obj.movie_recommendations_from.filter(is_active=True).count()
