"""
Development settings for Movie Nexus

Inherits from base.py and adds development-specific configurations
"""

from .base import *
from decouple import config

# ===========================
# DEBUG SETTINGS
# ===========================
DEBUG = config('DEBUG', default=True, cast=bool)

# ===========================
# ALLOWED HOSTS
# ===========================
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='',
    cast=lambda v: [s.strip() for s in v.split(',') if s.strip()]
)

DEV_ALLOWED_HOSTS = []

# Combine all hosts
ALLOWED_HOSTS = ALLOWED_HOSTS + DEV_ALLOWED_HOSTS

# ===========================
# DEVELOPMENT APPS - Conditional Loading
# ===========================
DEVELOPMENT_APPS = []
