"""
Development settings for Movie Nexus

Inherits from base.py and adds development-specific configurations
"""

from decouple import config

from .base import *

# ===========================
# DEBUG SETTINGS
# ===========================
DEBUG = config("DEBUG", default=True, cast=bool)

# ===========================
# ALLOWED HOSTS
# ===========================
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1,0.0.0.0",
    cast=lambda v: [s.strip() for s in v.split(",") if s.strip()],
)

# Additional development hosts
DEV_ALLOWED_HOSTS = [
    "testserver",  # For Django test client
    "*.ngrok.io",  # For ngrok tunneling
    "*.vercel.app",  # For Vercel preview deployments
]

# Combine all hosts
ALLOWED_HOSTS.extend(DEV_ALLOWED_HOSTS)

# ===========================
# CORS SETTINGS - DEVELOPMENT
# ===========================
# Allow all origins in development for easier testing
CORS_ALLOW_ALL_ORIGINS = config("CORS_ALLOW_ALL_ORIGINS", default=True, cast=bool)

# Development frontend URLs
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Next.js default
    "http://127.0.0.1:3000",
    "http://localhost:3001",  # Alternative port
    "http://127.0.0.1:3001",
    "http://localhost:8080",  # Vue.js default
    "http://127.0.0.1:8080",
]

# CSRF trusted origins for development
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

# Allow credentials (important for JWT)
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-forwarded-for",
    "x-forwarded-proto",
    "ngrok-skip-browser-warning",
    "cache-control",
    "pragma",
]

# All HTTP methods
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
    "HEAD",
]

# ===========================
# LOGGING FOR DEBUGGING
# ===========================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "corsheaders": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}
