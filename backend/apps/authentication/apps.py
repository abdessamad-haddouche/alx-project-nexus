"""
Authentication app configuration for Movie Nexus.
"""

from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    """Configuration for the authentication app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.authentication"
    label = "authentication"
    verbose_name = "Authentication"

    def ready(self):
        """
        Import signals when the app is ready.
        This ensures signal handlers are connected.
        """
        try:
            # Import signals to connect them
            # from . import signals  # Uncomment when you add signals
            pass
        except ImportError:
            pass
