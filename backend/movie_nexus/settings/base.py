"""
Base settings for Movie Nexus project.

This file contains settings that are SHARED across all environments.
Environment-specific settings go in development.py, production.py, testing.py
"""

from datetime import timedelta
from pathlib import Path

from decouple import config

# ================================================================
# PATHS & DIRECTORIES
# ================================================================
BASE_DIR = Path(__file__).resolve().parent.parent

# ================================================================
# SECURITY SETTINGS
# ================================================================
SECRET_KEY = config(
    "SECRET_KEY", default="5+d_&-9y-s9d-_rv3i%1go84wxkyl^xzjudk^kdu7$@#2_)%+v"
)

DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="",
    cast=lambda v: [s.strip() for s in v.split(",") if s.strip()],
)

# ================================================================
# CUSTOM USER MODEL
# ================================================================
AUTH_USER_MODEL = "authentication.User"

# ================================================================
# APPLICATION DEFINITION
# ================================================================
# Django core apps
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

# Third-party apps
THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
]

# Local apps
LOCAL_APPS = [
    "core",
    "apps.authentication",
    "apps.movies",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ================================================================
# MIDDLEWARE CONFIGURATION
# ================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ================================================================
# REST FRAMEWORK CONFIGURATION
# ================================================================
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": (
        "rest_framework_simplejwt.authentication.default_user_authentication_rule"
    ),
}

# Make sure REST_FRAMEWORK is also configured
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

# ================================================================
# JWT CONFIGURATION
# ================================================================
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": (
        "rest_framework_simplejwt.authentication.default_user_authentication_rule"
    ),
}

# ================================================================
# URL CONFIGURATION
# ================================================================
ROOT_URLCONF = "movie_nexus.urls"

# ================================================================
# TEMPLATE CONFIGURATION
# ================================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ================================================================
# WSGI CONFIGURATION
# ================================================================
WSGI_APPLICATION = "movie_nexus.wsgi.application"

# ================================================================
# DATABASE CONFIGURATION
# ================================================================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="movie_nexus_dev"),
        "USER": config("DB_USER", default="movie_nexus_user"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
        "CONN_MAX_AGE": 600,
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}


# ================================================================
# CACHE CONFIGURATION (Redis)
# ================================================================

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://127.0.0.1:6379/1"),
        "TIMEOUT": 3600,  # 1 hour default timeout
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 50,
                "retry_on_timeout": True,
            },
            "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
        },
        "KEY_PREFIX": "movie_nexus",  # Prefix for all cache keys
        "VERSION": 1,
    },
    # Separate cache for sessions
    "sessions": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://127.0.0.1:6379/2"),
        "TIMEOUT": 86400,  # 24 hours for sessions
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 20,
            },
        },
        "KEY_PREFIX": "movie_nexus_session",
    },
}

# Use Redis for session storage
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "sessions"
SESSION_COOKIE_AGE = 86400  # 24 hours

# Cache settings for different environments
CACHE_TTL = {
    "DEFAULT": 3600,  # 1 hour
    "SHORT": 300,  # 5 minutes
    "MEDIUM": 1800,  # 30 minutes
    "LONG": 86400,  # 24 hours
    "WEEK": 604800,  # 1 week
}


# ================================================================
# PASSWORD VALIDATION
# ================================================================
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": ("django.contrib.auth.password_validation." "MinimumLengthValidator"),
    },
    {
        "NAME": ("django.contrib.auth.password_validation." "CommonPasswordValidator"),
    },
    {
        "NAME": ("django.contrib.auth.password_validation." "NumericPasswordValidator"),
    },
]


# ================================================================
# INTERNATIONALIZATION
# ================================================================
LANGUAGE_CODE = config("LANGUAGE_CODE", default="en-us")
TIME_ZONE = config("TIME_ZONE", default="UTC")
USE_I18N = config("USE_I18N", default=True, cast=bool)
USE_TZ = config("USE_TZ", default=True, cast=bool)

# ================================================================
# STATIC FILES CONFIGURATION
# ================================================================
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# ================================================================
# MEDIA FILES CONFIGURATION
# ================================================================
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ================================================================
# DEFAULT PRIMARY KEY FIELD TYPE
# ================================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ================================================================
# EMAIL CONFIGURATION - ADD THIS FOR EMAIL SERVICES
# ================================================================
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"  # Development
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@movienexus.com")
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")


# ================================================================
# TMDB API CONFIGURATION
# ================================================================
TMDB_API_KEY = config("TMDB_API_KEY", default="")
TMDB_READ_ACCESS_TOKEN = config("TMDB_READ_ACCESS_TOKEN", default="")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/"

# TMDb API Settings
TMDB_SETTINGS = {
    "API_KEY": TMDB_API_KEY,
    "READ_ACCESS_TOKEN": TMDB_READ_ACCESS_TOKEN,
    "BASE_URL": TMDB_BASE_URL,
    "IMAGE_BASE_URL": TMDB_IMAGE_BASE_URL,
    "RATE_LIMIT": {
        "REQUESTS_PER_SECOND": 4,  # 40 requests per 10 seconds = 4/sec
        "BURST_SIZE": 10,  # Allow burst of 10 requests
        "RETRY_ATTEMPTS": 3,
        "RETRY_DELAY": 1,  # seconds
        "BACKOFF_FACTOR": 2,  # exponential backoff
    },
    "CACHE_SETTINGS": {
        "MOVIE_DETAILS_TTL": CACHE_TTL["LONG"],  # 24 hours
        "SEARCH_RESULTS_TTL": CACHE_TTL["MEDIUM"],  # 30 minutes
        "POPULAR_MOVIES_TTL": CACHE_TTL["MEDIUM"],  # 30 minutes
        "TRENDING_MOVIES_TTL": CACHE_TTL["SHORT"],  # 5 minutes
        "GENRE_LIST_TTL": CACHE_TTL["WEEK"],  # 1 week
    },
    "IMAGE_SIZES": {
        "POSTER": ["w92", "w154", "w185", "w342", "w500", "w780", "original"],
        "BACKDROP": ["w300", "w780", "w1280", "original"],
        "PROFILE": ["w45", "w185", "h632", "original"],
    },
    "IMAGE_CONFIGS": {
        "LIST_VIEW": {
            "poster_size": "w342",
            "backdrop_size": "w780",
            "profile_size": "w185",
        },
        "DETAIL_VIEW": {
            "poster_size": "w500",
            "backdrop_size": "w1280",
            "profile_size": "w185",
        },
        "MOBILE_VIEW": {
            "poster_size": "w185",
            "backdrop_size": "w780",
            "profile_size": "w185",
        },
        "THUMBNAIL_VIEW": {
            "poster_size": "w154",
            "backdrop_size": "w300",
            "profile_size": "w45",
        },
    },
    "DEFAULT_LANGUAGE": "en-US",
    "DEFAULT_REGION": "US",
    "TIMEOUT": 10,  # Request timeout in seconds
}

# Validate TMDb configuration
if not TMDB_API_KEY and not TMDB_READ_ACCESS_TOKEN:
    import warnings

    warnings.warn(
        "TMDb API credentials not configured. Movie features will be limited.",
        UserWarning,
    )


# ================================================================
# SITE CONFIGURATION - ADD THIS FOR EMAIL TEMPLATES
# ================================================================
SITE_NAME = config("SITE_NAME", default="Movie Nexus")
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:3000")
