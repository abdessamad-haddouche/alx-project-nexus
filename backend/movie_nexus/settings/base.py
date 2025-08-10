"""
Base settings for Movie Nexus project.

This file contains settings that are SHARED across all environments.
Environment-specific settings go in development.py, production.py, testing.py
"""

from datetime import timedelta
from pathlib import Path

import dj_database_url
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
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_extensions",
    "drf_spectacular",
]

# Local apps
LOCAL_APPS = [
    "core",
    "apps.authentication",
    "apps.movies",
    "apps.favorites",
    "apps.users",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ================================================================
# CORS SETTINGS (Cross-Origin Resource Sharing)
# ================================================================
CORS_ALLOW_CREDENTIALS = config("CORS_ALLOW_CREDENTIALS", default=True, cast=bool)

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-forwarded-for",
    "x-forwarded-proto",
]

# ================================================================
# MIDDLEWARE CONFIGURATION
# ================================================================

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
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
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # "rest_framework_simplejwt.authentication.JWTAuthentication",
        "core.authentication.BlacklistJWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# ================================================================
# JWT CONFIGURATION
# ================================================================
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
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
ENVIRONMENT = config("ENVIRONMENT", default="development")

if ENVIRONMENT == "production":
    # Production: Use DATABASE_URL
    DATABASE_URL = config("DATABASE_URL")
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Development: Use local database settings
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="movie_nexus_dev"),
            "USER": config("DB_USER", default="movie_nexus_user"),
            "PASSWORD": config("DB_PASSWORD", default="9wa4459AwAdp"),
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

REDIS_URL = config("REDIS_URL", default="")

USE_REDIS_CACHE = (
    REDIS_URL and REDIS_URL.strip() and REDIS_URL.startswith(("redis://", "rediss://"))
)

if USE_REDIS_CACHE:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": 3600,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "CONNECTION_POOL_KWARGS": {
                    "max_connections": 50,
                    "retry_on_timeout": True,
                },
                "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
                "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            },
            "KEY_PREFIX": "movie_nexus",
            "VERSION": 1,
        },
        "sessions": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": 86400,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "CONNECTION_POOL_KWARGS": {
                    "max_connections": 20,
                },
            },
            "KEY_PREFIX": "movie_nexus_session",
        },
    }

    # Redis session storage
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "sessions"
    SESSION_COOKIE_AGE = 86400

else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "movie_nexus_cache_table",
            "TIMEOUT": 3600,
            "OPTIONS": {
                "MAX_ENTRIES": 1000,
                "CULL_FREQUENCY": 3,
            },
        }
    }

    # Database session storage
    SESSION_ENGINE = "django.contrib.sessions.backends.db"
    SESSION_COOKIE_AGE = 86400

# Cache timeout configurations
CACHE_TTL = {
    "DEFAULT": 3600,
    "SHORT": 300,
    "MEDIUM": 1800,
    "LONG": 86400,
    "WEEK": 604800,
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
# API DOCUMENTATION CONFIGURATION (DRF-Spectacular)
# ================================================================
SPECTACULAR_SETTINGS = {
    "TITLE": "Movie Nexus API",
    "DESCRIPTION": """
    A comprehensive movie recommendation platform API built with Django REST Framework.

    Features:
    - Movie catalog management with TMDb integration
    - Advanced search and filtering with intelligent caching
    - TMDb-powered movie recommendations and similar movie discovery
    - Secure user authentication with JWT tokens & token blacklisting
    - Genre-based movie discovery and categorization
    - Comprehensive admin operations for content management

    """,
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "CONTACT": {
        "name": "Abdessamad Haddouche",
        "email": "abdessamad.hadd@gmail.com",
    },
    "LICENSE": {
        "name": "MIT License",
    },
    # API Configuration
    "COMPONENT_SPLIT_REQUEST": True,
    "COMPONENT_NO_READ_ONLY_REQUIRED": True,
    # Authentication
    "SERVE_AUTHENTICATION": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    # Schema customization
    "SCHEMA_PATH_PREFIX": "/api/v1/",
    "SCHEMA_PATH_PREFIX_TRIM": True,
    "OPERATION_ID_GENERATOR": None,
    "ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE": False,
    "DISABLE_AUTO_TAGS": True,
    "APPEND_COMPONENTS": {},  # prevents warnings
    "TAGS": [
        {
            "name": "Authentication",
            "description": "User authentication and authorization",
        },
        {"name": "Admin Management", "description": "Admin user management"},
        {"name": "Movies - Public", "description": "Public movie browsing and search"},
        {"name": "Movies - Admin", "description": "Administrative movie management"},
        {"name": "Movies - Genres", "description": "CRUD operations for movie genres"},
        {
            "name": "Movies - Genre Relationships",
            "description": "CRUD operations for movie-genre associations and mappings",
        },
        {
            "name": "Movies - Discovery",
            "description": "Discovering popular, trending, and highly-rated movies",
        },
        {
            "name": "Movies - Relationships",
            "description": "Movie-to-movie relationships including recommendations, "
            "similar movies, and genre associations",
        },
        {
            "name": "Favorites - User",
            "description": "Includes CRUD operations for favorites, watchlist"
            " management, user statistics, and discovery features.",
        },
    ],
    # UI Customization
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": False,
        "displayRequestDuration": True,
        "filter": True,
        "tryItOutEnabled": True,
    },
    "REDOC_UI_SETTINGS": {
        "hideDownloadButton": False,
        "theme": {"colors": {"primary": {"main": "#1976d2"}}},
    },
    # Security
    "SERVE_PUBLIC": True,
    "DISABLE_ERRORS_AND_WARNINGS": False,
}

# ================================================================
# SITE CONFIGURATION
# ================================================================
SITE_NAME = config("SITE_NAME", default="Movie Nexus")
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:3000")

# ================================================================
# CELERY CONFIGURATION
# ================================================================

# Celery Broker (using Redis)
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/3")
CELERY_RESULT_BACKEND = config(
    "CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/4"
)

# Celery Configuration
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Task routing and queue configuration
CELERY_TASK_ROUTES = {
    "apps.movies.tasks.sync_movie_details": {"queue": "movies"},
    "apps.movies.tasks.seed_popular_movies": {"queue": "seeding"},
    "apps.movies.tasks.sync_search_results": {"queue": "movies"},
    "apps.movies.tasks.refresh_stale_movies": {"queue": "maintenance"},
}

# Default queue configuration
CELERY_TASK_DEFAULT_QUEUE = "default"

# Task execution configuration
CELERY_TASK_ALWAYS_EAGER = config(
    "CELERY_TASK_ALWAYS_EAGER", default=True, cast=bool
)  # TRUE = No background tasks
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_STORE_EAGER_RESULT = True

# Rate limiting (for when i enable Celery)
CELERY_TASK_ANNOTATIONS = {
    "apps.movies.tasks.sync_movie_details": {"rate_limit": "10/m"},
    "apps.movies.tasks.sync_search_results": {"rate_limit": "5/m"},
}

# Worker configuration (for when i enable Celery)
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Beat scheduler configuration (for periodic tasks)
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Monitoring
CELERY_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True

# ================================================================
# CELERY TOGGLE SETTINGS
# ================================================================

# This determines if background tasks run immediately (True) or in background (False)
USE_CELERY_BACKGROUND_TASKS = config(
    "USE_CELERY_BACKGROUND_TASKS", default=False, cast=bool
)
