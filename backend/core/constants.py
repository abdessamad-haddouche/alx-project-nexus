"""
Project-wide constants and enums for consistent usage across the application.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

# =============================================================================
# User-related constants
# =============================================================================


class UserRole(models.TextChoices):
    """User role choices for role-based access control."""

    USER = "USER", _("User")
    MODERATOR = "MODERATOR", _("Moderator")
    ADMIN = "ADMIN", _("Administrator")
    SUPERADMIN = "SUPERADMIN", _("Super Administrator")


class UserStatus(models.TextChoices):
    """User account status choices."""

    PENDING = "PENDING", _("Pending Verification")
    ACTIVE = "ACTIVE", _("Active")
    SUSPENDED = "SUSPENDED", _("Suspended")
    DEACTIVATED = "DEACTIVATED", _("Deactivated")
    BANNED = "BANNED", _("Banned")


class AuthProvider(models.TextChoices):
    """Authentication provider choices."""

    EMAIL = "EMAIL", _("Email")
    GOOGLE = "GOOGLE", _("Google")
    FACEBOOK = "FACEBOOK", _("Facebook")
    APPLE = "APPLE", _("Apple")


# Movie-related constants
class MovieStatus(models.TextChoices):
    """Movie release status from TMDb."""

    RUMORED = "RUMORED", _("Rumored")
    PLANNED = "PLANNED", _("Planned")
    IN_PRODUCTION = "IN_PRODUCTION", _("In Production")
    POST_PRODUCTION = "POST_PRODUCTION", _("Post Production")
    RELEASED = "RELEASED", _("Released")
    CANCELED = "CANCELED", _("Canceled")


class ContentRating(models.TextChoices):
    """Movie content rating (MPAA)."""

    G = "G", _("General Audiences")
    PG = "PG", _("Parental Guidance Suggested")
    PG13 = "PG-13", _("Parents Strongly Cautioned")
    R = "R", _("Restricted")
    NC17 = "NC-17", _("Adults Only")
    NR = "NR", _("Not Rated")


class VideoType(models.TextChoices):
    """Video/trailer type choices."""

    TRAILER = "TRAILER", _("Trailer")
    TEASER = "TEASER", _("Teaser")
    CLIP = "CLIP", _("Clip")
    BEHIND_THE_SCENES = "BTS", _("Behind the Scenes")
    BLOOPERS = "BLOOPERS", _("Bloopers")
    FEATURETTE = "FEATURETTE", _("Featurette")
    OPENING_CREDITS = "OPENING", _("Opening Credits")


class RecommendationContext(models.TextChoices):
    """Context where recommendations are shown."""

    HOME_FEED = "HOME", _("Home Feed")
    MOVIE_DETAIL = "DETAIL", _("Movie Detail Page")
    SEARCH_RESULTS = "SEARCH", _("Search Results")
    GENRE_BROWSE = "GENRE", _("Genre Browse")
    USER_PROFILE = "PROFILE", _("User Profile")
    EMAIL = "EMAIL", _("Email Digest")


# =============================================================================
# Activity and interaction constants
# =============================================================================


class ActivityType(models.TextChoices):
    """Types of user activities for tracking."""

    VIEW = "VIEW", _("Viewed")
    SEARCH = "SEARCH", _("Searched")
    RATE = "RATE", _("Rated")
    FAVORITE = "FAVORITE", _("Added to Favorites")
    UNFAVORITE = "UNFAVORITE", _("Removed from Favorites")
    WATCHLIST_ADD = "WATCHLIST_ADD", _("Added to Watchlist")
    WATCHLIST_REMOVE = "WATCHLIST_REMOVE", _("Removed from Watchlist")
    SHARE = "SHARE", _("Shared")
    COMMENT = "COMMENT", _("Commented")
    RECOMMEND = "RECOMMEND", _("Recommended to Others")


class NotificationType(models.TextChoices):
    """Types of notifications."""

    WELCOME = "WELCOME", _("Welcome")
    EMAIL_VERIFICATION = "EMAIL_VERIFY", _("Email Verification")
    PASSWORD_RESET = "PASSWORD_RESET", _("Password Reset")
    NEW_RECOMMENDATION = "NEW_REC", _("New Recommendations")
    MOVIE_RELEASE = "RELEASE", _("Movie Released")
    WEEKLY_DIGEST = "WEEKLY", _("Weekly Digest")
    SECURITY = "SECURITY", _("Security Alert")
    SYSTEM = "SYSTEM", _("System Notification")


# =============================================================================
# API-related constants
# =============================================================================


class APIVersion:
    """API version constants."""

    V1 = "v1"
    V2 = "v2"
    DEFAULT = V1


class HTTPMethod:
    """HTTP method constants."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


# =============================================================================
# Regular expressions
# =============================================================================


class RegexPatterns:
    """Common regex patterns for validation."""

    EMAIL = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    USERNAME = r"^[a-zA-Z0-9_-]{3,30}$"
    SLUG = r"^[a-zA-Z0-9-]+$"
    UUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    PHONE = r"^\+?1?\d{9,15}$"


# =============================================================================
# Date and time formats
# =============================================================================


class DateTimeFormats:
    """Standard date and time formats."""

    DATE_FORMAT = "%Y-%m-%d"
    TIME_FORMAT = "%H:%M:%S"
    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
    HUMAN_DATE = "%B %d, %Y"
    HUMAN_DATETIME = "%B %d, %Y at %I:%M %p"
