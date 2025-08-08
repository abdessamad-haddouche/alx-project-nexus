"""
Production settings for Movie Nexus - Render.com Deployment
"""

import dj_database_url
from decouple import config

from .base import *

# ===========================
# BASIC SETTINGS
# ===========================
DEBUG = False
SECRET_KEY = config("SECRET_KEY")

ALLOWED_HOSTS = [
    "*.onrender.com",
    "localhost",
    "127.0.0.1",
]

# ===========================
# DATABASE - RENDER POSTGRESQL
# ===========================
DATABASE_URL = config("DATABASE_URL", default="")

if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    # Fallback for local testing
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="movie_nexus_prod"),
            "USER": config("DB_USER", default="postgres"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
            "CONN_MAX_AGE": 600,
        }
    }

# ===========================
# CACHE - USE DATABASE CACHE
# ===========================
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "movie_nexus_cache_table",
        "TIMEOUT": 3600,
    }
}

# ===========================
# STATIC FILES - WHITENOISE
# ===========================
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ===========================
# SECURITY - HTTPS
# ===========================
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ===========================
# CORS
# ===========================
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# ===========================
# CELERY - KEEP SIMPLE
# ===========================
CELERY_TASK_ALWAYS_EAGER = True
USE_CELERY_BACKGROUND_TASKS = False

# ===========================
# API DOCS
# ===========================
SPECTACULAR_SETTINGS.update(
    {
        "SERVE_PUBLIC": True,
        "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    }
)

print(f"Render Production: DATABASE={'✅' if DATABASE_URL else '❌'}")
