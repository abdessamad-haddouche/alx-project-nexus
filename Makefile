.PHONY: help install dev-install test clean lint format migrate run shell
.PHONY: prod-test render-build render-test db-start db-stop db-access redis-start redis-stop

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
	@echo "  render-build   Test Render build process"
	@echo "  render-test    Test Render deployment readiness"
	@echo ""
	@echo " Database Commands:"
	@echo "  db-start       Start PostgreSQL service"
	@echo "  db-stop        Stop PostgreSQL service"
	@echo "  db-access      Access PostgreSQL database"
	@echo ""
	@echo " Redis Commands:"
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

run:
	cd backend && python manage.py runserver

test:
	cd backend && python manage.py test

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
# Production Commands
# ================================================================
install:
	pip install -r backend/requirements/production.txt

prod-test:
	@echo "Testing production settings locally..."
	cd backend && DJANGO_SETTINGS_MODULE=movie_nexus.settings.production python manage.py check
	cd backend && DJANGO_SETTINGS_MODULE=movie_nexus.settings.production python manage.py migrate --dry-run
	cd backend && DJANGO_SETTINGS_MODULE=movie_nexus.settings.production python manage.py collectstatic --noinput --dry-run
	@echo "✅ Production test completed!"

# ================================================================
# Render Commands
# ================================================================
render-build:
	@echo "Testing Render build process..."
	chmod +x build.sh
	./build.sh
	@echo "✅ Render build test completed!"

render-test:
	@echo "Testing Render deployment readiness..."
	@test -f build.sh || (echo "❌ build.sh missing!" && exit 1)
	@test -f backend/requirements/production.txt || (echo "❌ production.txt missing!" && exit 1)
	@echo "✅ All required files present!"
	$(MAKE) prod-test
	@echo "✅ Ready for Render deployment!"

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
