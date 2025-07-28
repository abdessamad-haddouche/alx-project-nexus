"""
Default value functions for Django model fields.

This module contains functions that return default values for model fields.
These functions are needed because Django migrations cannot serialize lambda functions.
"""

from .constants import DEFAULT_NOTIFICATION_PREFERENCES


def get_default_notification_preferences():
    """
    Return a fresh copy of default notification preferences for new users.

    Returns:
        dict: Fresh copy of notification preferences with all default values
    """
    return DEFAULT_NOTIFICATION_PREFERENCES.copy()
