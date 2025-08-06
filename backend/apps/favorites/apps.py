"""
Favorites app configuration.
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class FavoritesConfig(AppConfig):
    """
    Configuration for the Favorites app.

    Handles user's favorite movies, watchlist management
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.favorites"
    verbose_name = _("Favorites")

    def ready(self):
        """
        Initialize app when Django starts.
        Import signals and perform any necessary setup.
        """
        # Import signals to ensure they're registered
        try:
            from . import signals  # noqa
        except ImportError:
            pass
