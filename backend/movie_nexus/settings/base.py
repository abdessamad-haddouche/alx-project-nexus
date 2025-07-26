"""
Base settings for Movie Nexus project.

This file contains settings that are SHARED across all environments.
Environment-specific settings go in development.py, production.py, testing.py
"""

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
THIRD_PARTY_APPS = []

# Local apps
LOCAL_APPS = []

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
        "NAME": config("DB_NAME", default="nexus_movie_dev"),
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

# ================================================================
# DEFAULT PRIMARY KEY FIELD TYPE
# ================================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
