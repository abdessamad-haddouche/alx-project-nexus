#!/bin/bash
# ================================================================
# Railway Entrypoint for Movie Nexus
# ================================================================

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# ================================================================
# Railway Configuration
# ================================================================
export PORT=${PORT:-8000}
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-movie_nexus.settings.production}

# ================================================================
# Wait for Database (Railway PostgreSQL)
# ================================================================
wait_for_db() {
    if [ -n "$DATABASE_URL" ]; then
        log_info "Waiting for Railway PostgreSQL..."

        max_attempts=20
        attempt=0

        while [ $attempt -lt $max_attempts ]; do
            if python manage.py check --database default >/dev/null 2>&1; then
                log_success "Database is ready!"
                return 0
            fi

            attempt=$((attempt + 1))
            log_info "Database not ready, waiting... ($attempt/$max_attempts)"
            sleep 3
        done

        log_warning "Database timeout - continuing anyway"
        return 0
    else
        log_info "No DATABASE_URL found - using local settings"
        return 0
    fi
}

# ================================================================
# Essential Setup Tasks
# ================================================================
run_migrations() {
    log_info "Running database migrations..."
    python manage.py migrate --noinput
    log_success "Migrations completed!"
}

collect_static() {
    log_info "Collecting static files..."
    python manage.py collectstatic --noinput --clear
    log_success "Static files collected!"
}

create_superuser() {
    if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
        log_info "Creating superuser..."
        python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='$DJANGO_SUPERUSER_EMAIL').exists():
    User.objects.create_superuser(
        email='$DJANGO_SUPERUSER_EMAIL',
        password='$DJANGO_SUPERUSER_PASSWORD',
        first_name='${DJANGO_SUPERUSER_FIRST_NAME:-Admin}',
        last_name='${DJANGO_SUPERUSER_LAST_NAME:-User}'
    )
    print("Superuser created!")
else:
    print("Superuser already exists!")
EOF
        log_success "Superuser setup complete!"
    fi
}

# ================================================================
# Main Setup Function
# ================================================================
railway_setup() {
    log_info "Setting up Movie Nexus on Railway..."

    # Wait for database
    wait_for_db

    # Run essential tasks
    run_migrations
    collect_static
    create_superuser

    log_success "Setup completed! Starting server..."
}

# ================================================================
# Command Execution
# ================================================================
case "$1" in
    "runserver")
        # Development
        railway_setup
        log_info "Starting Django development server on port $PORT..."
        exec python manage.py runserver 0.0.0.0:$PORT
        ;;

    "shell")
        wait_for_db
        exec python manage.py shell
        ;;

    "migrate")
        wait_for_db
        run_migrations
        ;;

    "bash")
        exec /bin/bash
        ;;

    *)
        railway_setup
        log_info "Starting production server on port $PORT..."
        exec gunicorn movie_nexus.wsgi:application \
            --bind 0.0.0.0:$PORT \
            --workers 2 \
            --timeout 120 \
            --log-level info \
            --access-logfile - \
            --error-logfile -
        ;;
esac
