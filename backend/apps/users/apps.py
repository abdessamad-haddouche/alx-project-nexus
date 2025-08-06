"""
Users app configuration.
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class UsersConfig(AppConfig):
    """
    Configuration for the Users app.

    Handles user's Profile management
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    verbose_name = _("Users")

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
