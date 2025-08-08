.PHONY: help install dev-install test clean lint format migrate run shell setup-frontend
.PHONY: docker-build docker-run docker-stop docker-test prod-test railway-test
.PHONY: deploy-prep railway-logs db-start db-stop db-access redis-start redis-stop

help:
	@echo "ALX Project Nexus - Movie Recommendation Platform"
	@echo ""
	@echo " Development Commands:"
	@echo "  dev-install    Install development dependencies"
	@echo "  run            Run development server"
	@echo "  test           Run backend tests"
	@echo "  shell          Open Django shell"
	@echo "  migrate        Run database migrations"
	@echo "  lint           Run linting"
	@echo "  format         Format code"
	@echo "  clean          Clean cache and temporary files"
	@echo ""
	@echo " Production Commands:"
	@echo "  install        Install production dependencies"
	@echo "  prod-test      Test production settings locally"
	@echo "  docker-build   Build Docker image"
	@echo "  docker-run     Run Docker container locally"
	@echo "  docker-test    Test Docker setup"
	@echo "  deploy-prep    Prepare for Railway deployment"
	@echo ""
	@echo " Database Commands:"
	@echo "  db-start       Start PostgreSQL service"
	@echo "  db-stop        Stop PostgreSQL service"
	@echo "  db-access      Access PostgreSQL database"
	@echo ""
	@echo "⚡ Redis Commands:"
	@echo "  redis-start    Start Redis service"
	@echo "  redis-stop     Stop Redis service"
	@echo "  redis-status   Check Redis service status"
	@echo "  redis-clear    Wipe Redis database"
	@echo ""
	@echo " Utilities:"
	@echo "  tree-clean     Show directory structure"

# ================================================================
# Development Commands
# ================================================================
dev-install:
	pip install -r backend/requirements/development.txt
	cd backend && pre-commit install

run:
	cd backend && python manage.py runserver

test:
	cd backend && python manage.py test
	cd backend && pytest --cov=apps --cov-report=html

shell:
	cd backend && python manage.py shell

migrate:
	cd backend && python manage.py makemigrations
	cd backend && python manage.py migrate

lint:
	cd backend && flake8 .
	cd backend && black --check .
	cd backend && isort --check-only .

format:
	cd backend && black .
	cd backend && isort .

clean:
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

# ================================================================
# Production & Railway Commands
# ================================================================
install:
	pip install -r backend/requirements/production.txt

prod-test:
	@echo "Testing production settings locally..."
	cd backend && DJANGO_SETTINGS_MODULE=movie_nexus.settings.production python manage.py check
	cd backend && DJANGO_SETTINGS_MODULE=movie_nexus.settings.production python manage.py migrate --dry-run
	cd backend && DJANGO_SETTINGS_MODULE=movie_nexus.settings.production python manage.py collectstatic --noinput --dry-run
	@echo "✅ Production test completed!"

docker-build:
	@echo "Building Docker image..."
	docker build -t movie-nexus:latest .
	@echo "✅ Docker image built successfully!"

docker-run:
	@echo "Running Docker container..."
	docker run -p 8000:8000 --env-file .env movie-nexus:latest

docker-test:
	@echo "Testing Docker setup..."
	docker build -t movie-nexus-test .
	docker run --rm movie-nexus-test python manage.py check
	@echo "✅ Docker test completed!"

deploy-prep:
	@echo "Preparing for Railway deployment..."
	@echo "Checking required files..."
	@test -f Dockerfile || (echo "❌ Dockerfile missing!" && exit 1)
	@test -f entrypoint.sh || (echo "❌ entrypoint.sh missing!" && exit 1)
	@test -f .dockerignore || (echo "❌ .dockerignore missing!" && exit 1)
	@test -f backend/requirements/production.txt || (echo "❌ production.txt missing!" && exit 1)
	@echo "✅ All required files present!"
	@echo "Running production test..."
	$(MAKE) prod-test
	@echo ""
	@echo "✅ Ready for Railway deployment!"

railway-test:
	@echo "Testing Railway configuration..."
	@echo "Checking environment variables..."
	@test -n "$$SECRET_KEY" || (echo "❌ SECRET_KEY not set!" && exit 1)
	@test -n "$$TMDB_API_KEY" || (echo "❌ TMDB_API_KEY not set!" && exit 1)
	@echo "✅ Environment variables check passed!"

# ================================================================
# Database Commands
# ================================================================
db-start:
	sudo service postgresql start

db-stop:
	sudo service postgresql stop

db-access:
	psql -h localhost -p 5432 -U movie_nexus_user -d movie_nexus_dev

# ================================================================
# Redis Commands
# ================================================================
redis-start:
	sudo service redis-server start

redis-stop:
	sudo service redis-server stop

redis-status:
	sudo service redis-server status

redis-clear:
	redis-cli FLUSHALL

# ================================================================
# Utilities
# ================================================================
tree-clean:
	tree -I '*[0-9]*|__pycache__|.venv|planning'
