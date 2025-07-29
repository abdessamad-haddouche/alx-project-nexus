"""
Project-wide constants and enums for consistent usage across the application.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

# ================================================================
# AUTHENTICATION CONSTANTS
# ================================================================


class AuthProvider(models.TextChoices):
    """OAuth authentication providers."""

    GOOGLE = "google", _("Google OAuth")
    FACEBOOK = "facebook", _("Facebook OAuth")
    APPLE = "apple", _("Apple Sign-In")
    TWITTER = "twitter", _("Twitter OAuth")


class UserRole(models.TextChoices):
    """User roles for access control."""

    USER = "user", _("Regular User")
    MODERATOR = "moderator", _("Moderator")
    ADMIN = "admin", _("Administrator")
    SUPERADMIN = "superadmin", _("Super Administrator")


class VerificationType(models.TextChoices):
    """Types of email verification."""

    REGISTRATION = "registration", _("Account Registration")
    EMAIL_CHANGE = "email_change", _("Email Address Change")
    PASSWORD_RESET = "password_reset", _("Password Reset")


# ================================================================
# USER PROFILE CONSTANTS
# ================================================================


class PrivacyLevel(models.TextChoices):
    """Privacy levels for user profiles."""

    PUBLIC = "public", _("Public")
    FRIENDS = "friends", _("Friends Only")
    PRIVATE = "private", _("Private")


class ThemePreference(models.TextChoices):
    """UI theme preferences."""

    LIGHT = "light", _("Light Theme")
    DARK = "dark", _("Dark Theme")
    AUTO = "auto", _("Auto (System)")


class Language(models.TextChoices):
    """Supported languages (ISO 639-1)."""

    ENGLISH = "en", _("English")
    FRENCH = "fr", _("Français")
    ARABIC = "ar", _("العربية")


class Timezone(models.TextChoices):
    """Common timezones."""

    UTC = "UTC", _("UTC")
    # Africa
    AFRICA_CASABLANCA = "Africa/Casablanca", _("Casablanca")
    AFRICA_JOHANNESBURG = "Africa/Johannesburg", _("South Africa")
    # North America
    US_EASTERN = "America/New_York", _("US Eastern")
    US_CENTRAL = "America/Chicago", _("US Central")
    US_MOUNTAIN = "America/Denver", _("US Mountain")
    US_PACIFIC = "America/Los_Angeles", _("US Pacific")
    # Europe
    EUROPE_LONDON = "Europe/London", _("London")
    EUROPE_PARIS = "Europe/Paris", _("Paris")
    EUROPE_BERLIN = "Europe/Berlin", _("Berlin")
    # Asia
    ASIA_TOKYO = "Asia/Tokyo", _("Tokyo")
    ASIA_SHANGHAI = "Asia/Shanghai", _("Shanghai")
    # Oceania
    AUSTRALIA_SYDNEY = "Australia/Sydney", _("Sydney")


# ================================================================
# MOVIE CATALOG & CONTENT
# ================================================================


class MovieStatus(models.TextChoices):
    """Movie release status from TMDb."""

    RUMORED = "rumored", _("Rumored")
    PLANNED = "planned", _("Planned")
    IN_PRODUCTION = "in_production", _("In Production")
    POST_PRODUCTION = "post_production", _("Post Production")
    RELEASED = "released", _("Released")
    CANCELED = "canceled", _("Canceled")


class ContentRating(models.TextChoices):
    """Movie content rating (MPAA system)."""

    G = "G", _("General Audiences")
    PG = "PG", _("Parental Guidance Suggested")
    PG13 = "PG-13", _("Parents Strongly Cautioned")
    R = "R", _("Restricted")
    NC17 = "NC-17", _("Adults Only")
    NR = "NR", _("Not Rated")
    UR = "UR", _("Unrated")


# ================================================================
# USER ACTIVITY & ANALYTICS
# ================================================================


class VideoType(models.TextChoices):
    """Video/trailer type choices."""

    TRAILER = "trailer", _("Trailer")
    TEASER = "teaser", _("Teaser")
    CLIP = "clip", _("Clip")
    BEHIND_THE_SCENES = "behind_the_scenes", _("Behind the Scenes")
    BLOOPERS = "bloopers", _("Bloopers")
    FEATURETTE = "featurette", _("Featurette")
    OPENING_CREDITS = "opening_credits", _("Opening Credits")


class ActivityType(models.TextChoices):
    """Types of user activities for tracking."""

    # Authentication activities
    LOGIN = "login", _("User Login")
    LOGOUT = "logout", _("User Logout")
    REGISTRATION = "registration", _("User Registration")

    # Profile activities
    PROFILE_UPDATE = "profile_update", _("Profile Update")
    PASSWORD_CHANGE = "password_change", _("Password Change")
    EMAIL_VERIFICATION = "email_verification", _("Email Verification")

    # Movie interactions
    MOVIE_VIEW = "movie_view", _("Movie Viewed")
    MOVIE_SEARCH = "movie_search", _("Movie Search")
    MOVIE_RATE = "movie_rate", _("Movie Rated")

    # Collection management
    FAVORITE_ADD = "favorite_add", _("Added to Favorites")
    FAVORITE_REMOVE = "favorite_remove", _("Removed from Favorites")
    WATCHLIST_ADD = "watchlist_add", _("Added to Watchlist")
    WATCHLIST_REMOVE = "watchlist_remove", _("Removed from Watchlist")

    # Social activities
    SHARE = "share", _("Shared")
    COMMENT = "comment", _("Commented")
    RECOMMEND = "recommend", _("Recommended to Others")


# ================================================================
# RECOMMENDATIONS & ALGORITHMS
# ================================================================


class RecommendationContext(models.TextChoices):
    """Context where recommendations are shown."""

    HOME_FEED = "home_feed", _("Home Feed")
    MOVIE_DETAIL = "movie_detail", _("Movie Detail Page")
    SEARCH_RESULTS = "search_results", _("Search Results")
    GENRE_BROWSE = "genre_browse", _("Genre Browse")
    USER_PROFILE = "user_profile", _("User Profile")
    EMAIL_DIGEST = "email_digest", _("Email Digest")


class RecommendationAlgorithm(models.TextChoices):
    """Types of recommendation algorithms."""

    COLLABORATIVE = "collaborative", _("Collaborative Filtering")
    CONTENT_BASED = "content_based", _("Content-Based")
    HYBRID = "hybrid", _("Hybrid Algorithm")
    POPULARITY = "popularity", _("Popularity-Based")
    TRENDING = "trending", _("Trending Content")


# ================================================================
# NOTIFICATIONS & COMMUNICATIONS
# ================================================================


class NotificationChannel(models.TextChoices):
    """Notification delivery channels."""

    EMAIL = "email", _("Email Notification")
    PUSH = "push", _("Push Notification")
    IN_APP = "in_app", _("In-App Notification")
    SMS = "sms", _("SMS Notification")


class NotificationCategory(models.TextChoices):
    """Categories of notifications for better organization."""

    # System notifications
    WELCOME = "welcome", _("Welcome")
    EMAIL_VERIFICATION = "email_verification", _("Email Verification")
    PASSWORD_RESET = "password_reset", _("Password Reset")
    SECURITY = "security", _("Security Alert")
    SYSTEM = "system", _("System Notification")

    # Content notifications
    NEW_RECOMMENDATION = "new_recommendation", _("New Recommendations")
    MOVIE_RELEASE = "movie_release", _("Movie Released")
    WEEKLY_DIGEST = "weekly_digest", _("Weekly Digest")
    MONTHLY_SUMMARY = "monthly_summary", _("Monthly Summary")

    # Social notifications
    FRIEND_ACTIVITY = "friend_activity", _("Friend Activity")
    SHARED_CONTENT = "shared_content", _("Shared Content")


# ================================================================
# API & TECHNICAL CONSTANTS
# ================================================================


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


# ================================================================
# VALIDATION PATTERNS
# ================================================================


class RegexPatterns:
    """Common regex patterns for validation."""

    EMAIL = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    USERNAME = r"^[a-zA-Z0-9_-]{3,30}$"
    SLUG = r"^[a-zA-Z0-9-]+$"
    UUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    PHONE = r"^\+?1?\d{9,15}$"


# ================================================================
# DATE & TIME FORMATS
# ================================================================


class DateTimeFormats:
    """Standard date and time formats."""

    DATE_FORMAT = "%Y-%m-%d"
    TIME_FORMAT = "%H:%M:%S"
    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
    HUMAN_DATE = "%B %d, %Y"
    HUMAN_DATETIME = "%B %d, %Y at %I:%M %p"


# ================================================================
# DEFAULT CONFIGURATIONS
# ================================================================

# Default notification preferences for new users
DEFAULT_NOTIFICATION_PREFERENCES = {
    # Email notifications
    "email_recommendations": True,  # Weekly movie recommendations
    "email_favorites": False,  # Updates about favorite movies
    "email_security": True,  # Security alerts (login, password change)
    "email_watchlist": False,  # Watchlist reminders
    "email_new_releases": True,  # New releases in preferred genres
    "email_weekly_digest": True,  # Weekly summary of activity
    "email_monthly_summary": False,  # Monthly platform updates
}

# Default movie preferences for new users
DEFAULT_MOVIE_PREFERENCES = {
    "min_rating": 6.0,  # Minimum TMDb rating
    "preferred_genres": [],  # Empty - user will set
    "content_rating_max": ContentRating.R,  # Maximum content rating
    "preferred_languages": [Language.ENGLISH],  # Preferred movie languages
    "min_year": 1980,  # Minimum release year
    "max_year": None,  # Maximum release year (None = current)
    "discovery_factor": 0.3,  # 0.0 = safe, 1.0 = adventurous
}

# Verification token expiration times (in hours)

DEFAULT_VERIFICATION_EXPIRATION_HOURS = 24

VERIFICATION_EXPIRATION_HOURS = {
    VerificationType.REGISTRATION: 24,  # 24 hours for registration
    VerificationType.EMAIL_CHANGE: 2,  # 2 hours for email change (more sensitive)
    VerificationType.PASSWORD_RESET: 1,  # 1 hour for password reset (most sensitive)
}
