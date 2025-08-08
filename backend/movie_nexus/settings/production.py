"""
Production settings for Movie Nexus - Railway Deployment
"""

import os

import dj_database_url
from decouple import config

from .base import *

# ===========================
# DEBUG & SECURITY
# ===========================
DEBUG = config("DEBUG", default=False, cast=bool)
SECRET_KEY = config("SECRET_KEY")

# ===========================
# ALLOWED HOSTS - RAILWAY
# ===========================
ALLOWED_HOSTS = [
    "*.up.railway.app",
    "localhost",
    "127.0.0.1",
]

# Add custom domains
custom_hosts = config("ALLOWED_HOSTS", default="", cast=str)
if custom_hosts:
    ALLOWED_HOSTS.extend(
        [host.strip() for host in custom_hosts.split(",") if host.strip()]
    )

# ===========================
# DATABASE - RAILWAY POSTGRESQL
# ===========================
DATABASE_URL = config("DATABASE_URL", default="")

if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME"),
            "USER": config("DB_USER"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
            "CONN_MAX_AGE": 600,
        }
    }

# ===========================
# CACHE - RAILWAY REDIS
# ===========================
REDIS_URL = config("REDIS_URL", default="")

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": 3600,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
            "KEY_PREFIX": "movie_nexus",
        },
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "cache_table",
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.db"

# ===========================
# STATIC FILES - WHITENOISE
# ===========================
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ===========================
# CORS
# ===========================
CORS_ALLOW_ALL_ORIGINS = config("CORS_ALLOW_ALL_ORIGINS", default=True, cast=bool)
CORS_ALLOW_CREDENTIALS = True

if not CORS_ALLOW_ALL_ORIGINS:
    CORS_ALLOWED_ORIGINS = config(
        "CORS_ALLOWED_ORIGINS",
        default="",
        cast=lambda v: [s.strip() for s in v.split(",") if s.strip()],
    )

# ===========================
# HTTPS - RAILWAY PROVIDES SSL
# ===========================
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ===========================
# EMAIL - SIMPLE CONSOLE FOR DEMO
# ===========================
EMAIL_BACKEND = config(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@movienexus.com")

# ===========================
# CELERY
# ===========================
if REDIS_URL:
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL

# For school project, keep tasks synchronous
CELERY_TASK_ALWAYS_EAGER = config("CELERY_TASK_ALWAYS_EAGER", default=True, cast=bool)
USE_CELERY_BACKGROUND_TASKS = config(
    "USE_CELERY_BACKGROUND_TASKS", default=False, cast=bool
)

# ===========================
# LOGGING
# ===========================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ===========================
# API DOCS
# ===========================
SPECTACULAR_SETTINGS.update(
    {
        "SERVE_PUBLIC": True,
        "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    }
)

# ===========================
# SIMPLE TMDB SETTINGS
# ===========================
TMDB_SETTINGS["RATE_LIMIT"].update(
    {
        "REQUESTS_PER_SECOND": 2,
        "BURST_SIZE": 5,
        "RETRY_ATTEMPTS": 3,
    }
)

print(
    f"Railway Production Mode: DEBUG={DEBUG}, DATABASE={'Railway' if DATABASE_URL else 'Manual'}, CACHE={'Redis' if REDIS_URL else 'Database'}"
)
