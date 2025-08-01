"""
Movies app configuration for Movie Nexus.
"""

from django.apps import AppConfig


class MoviesConfig(AppConfig):
    """Configuration for the movies app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.movies"
    label = "movies"
    verbose_name = "Movies"

    def ready(self):
        """
        Import signals when the app is ready.
        Ensures signal handlers are connected.
        """
        try:
            # Import signals to connect them

            # Examples for future implementation:
            # - Cache invalidation when movies are updated
            # - TMDb sync triggers
            # - Search index updates
            # - Recommendation refresh signals
            pass
        except ImportError:
            pass
