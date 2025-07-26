"""
Settings package for Movie Nexus

This package contains environment-specific settings:
- base.py: Common settings shared across all environments
- development.py: Development-specific settings
- production.py: Production-specific settings
- testing.py: Test-specific settings

Usage:
    Set DJANGO_SETTINGS_MODULE environment variable:
    - Development: movie_nexus.settings.development
    - Production: movie_nexus.settings.production
    - Testing: movie_nexus.settings.testing
"""

import os
import sys

# Auto-detect environment if DJANGO_SETTINGS_MODULE is not set
if 'DJANGO_SETTINGS_MODULE' not in os.environ:
    # Check for common test indicators
    if 'test' in sys.argv or 'pytest' in sys.modules:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movie_nexus.settings.testing')
    # Check for production indicators
    elif os.environ.get('ENVIRONMENT') == 'production':
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movie_nexus.settings.production')
    # Default to development
    else:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movie_nexus.settings.development')