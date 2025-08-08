#!/usr/bin/env bash
set -o errexit

echo "Building Movie Nexus..."

# Install dependencies
cd backend
pip install --upgrade pip
pip install -r requirements/production.txt

# Setup database
python manage.py migrate --noinput
python manage.py createcachetable movie_nexus_cache_table || echo "Cache table exists"

# Collect static files
python manage.py collectstatic --noinput --clear

# Create superuser if provided
if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py shell << EOF
from django.contrib.auth import get_user_model
import os
User = get_user_model()
email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
if email and password and not User.objects.filter(email=email).exists():
    User.objects.create_superuser(email=email, password=password)
    print("✅ Superuser created!")
EOF
fi

echo "✅ Build completed!"
