.PHONY: help install dev-install test clean lint format migrate run shell setup-frontend

help:
	@echo "ALX Project Nexus - Movie Recommendation Platform"
	@echo "Available commands:"
	@echo "  install        Install production dependencies"
	@echo "  dev-install    Install development dependencies"
	@echo "  test           Run backend tests"
	@echo "  lint           Run linting"
	@echo "  format         Format code"
	@echo "  migrate        Run database migrations"
	@echo "  run            Run development server"
	@echo "  shell          Open Django shell"
	@echo "  setup-frontend Setup React frontend (optional)"
	@echo "  clean          Clean cache and temporary files"

install:
	pip install -r backend/requirements/production.txt

dev-install:
	pip install -r backend/requirements/development.txt
	cd backend && pre-commit install

test:
	cd backend && python manage.py test
	cd backend && pytest --cov=apps --cov-report=html

lint:
	cd backend && flake8 .
	cd backend && black --check .
	cd backend && isort --check-only .

format:
	cd backend && black .
	cd backend && isort .

migrate:
	cd backend && python manage.py makemigrations
	cd backend && python manage.py migrate

run:
	cd backend && python manage.py runserver

shell:
	cd backend && python manage.py shell

setup-frontend:
	npx create-react-app frontend --template typescript
	@echo "Frontend React app created in frontend/ directory"

clean:
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
