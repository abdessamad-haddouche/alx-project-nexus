# ================================================================
# Dockerfile for Movie Nexus Django REST API
# ================================================================

FROM python:3.11-slim-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # PostgreSQL client libraries
    libpq-dev \
    # Compiler dependencies
    gcc \
    g++ \
    # Utilities
    curl \
    wget \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Copy requirements
COPY backend/requirements/ requirements/

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements/production.txt

# Copy project files
COPY backend/ .

# Create necessary directories
RUN mkdir -p staticfiles media logs

# Collect static files
RUN python manage.py collectstatic --noinput --settings=movie_nexus.settings.production || true

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE $PORT

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]

# Default command for Railway (will use gunicorn)
CMD ["gunicorn"]
