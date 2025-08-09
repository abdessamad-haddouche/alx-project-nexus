# Movie Nexus - Development Setup Guide

> **Quick setup guide for local development**
> Get the Movie Nexus backend running in under 10 minutes

## 🚀 Quick Start

### **Prerequisites**
- **Python 3.11+**
- **PostgreSQL 15+**
- **Redis 7.0+**
- **Git**

### **1. Clone & Setup**
```bash
# Clone repository
git clone https://github.com/abdessamad-haddouche/alx-project-nexus.git
cd alx-project-nexus

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
make dev-install
```

### **2. Environment Configuration**
```bash
# Copy environment template
cp .env.example .env

# Edit with your settings
nano .env
```

**Required Environment Variables:**
```bash
# Database
DB_NAME=movie_nexus_dev
DB_USER=movie_nexus_user
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432

# TMDb API (Required)
TMDB_API_KEY=your_tmdb_api_key_here
TMDB_READ_ACCESS_TOKEN=your_tmdb_read_access_token

# Redis
REDIS_URL=redis://localhost:6379/1

# Security
SECRET_KEY=your-super-secure-secret-key-here
DEBUG=True
```

### **3. Requirements Overview**

The project uses **layered requirements** for different environments:

```bash
# Project requirements structure
backend/requirements/
├── base.txt           # Core dependencies (shared)
├── development.txt    # Development tools & debugging
├── production.txt     # Production-optimized packages
└── testing.txt        # Testing frameworks & tools
```

**Quick Install:**
```bash
# Install all development dependencies
make dev-install

# Or manually:
pip install -r backend/requirements/development.txt
```

### **4. Database Setup**
```bash
# Start PostgreSQL
make db-start

# Create database and user
sudo -u postgres createdb movie_nexus_dev
sudo -u postgres createuser movie_nexus_user
sudo -u postgres psql -c "ALTER USER movie_nexus_user PASSWORD 'your_secure_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE movie_nexus_dev TO movie_nexus_user;"

# Run migrations
make migrate
```

### **5. Redis Setup**
```bash
# Start Redis
make redis-start

# Verify Redis is running
make redis-status
```

### **6. Run Development Server**
```bash
# Start the development server
make run

# Server available at: http://localhost:8000
# API Documentation: http://localhost:8000/api/docs/
```

---

## 🔧 Development Commands

### **Database Operations**
```bash
# Database management
make db-start          # Start PostgreSQL service
make db-stop           # Stop PostgreSQL service
make db-access         # Access database shell
make migrate           # Run migrations

```

### **Redis Operations**
```bash
make redis-start       # Start Redis service
make redis-stop        # Stop Redis service
make redis-status      # Check Redis status
make redis-clear       # Clear Redis database
```

### **Code Quality**
```bash
make lint             # Run linting (flake8, black, isort)
make format           # Format code (black, isort)
make test             # Run tests
make clean            # Clean cache files
```

### **Django Management**
```bash
make shell            # Open Django shell
cd backend && python manage.py collectstatic  # Collect static files
cd backend && python manage.py createsuperuser  # Create admin user
```

---

## 🔑 Getting TMDb API Keys

### **1. Create TMDb Account**
- Visit: [https://www.themoviedb.org/](https://www.themoviedb.org/)
- Sign up for a free account

### **2. Get API Key**
- Go to: Settings → API
- Request API key (select "Developer")
- Fill out the form (use localhost for development)
- Copy your **API Key (v3 auth)**

### **3. Get Read Access Token**
- In the same API settings page
- Copy your **API Read Access Token (v4 auth)**

### **4. Add to Environment**
```bash
# Add to your .env file
TMDB_API_KEY=your_api_key_here
TMDB_READ_ACCESS_TOKEN=your_read_access_token_here
```

---

## 📖 Development Resources

### **API Documentation**
- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc**: http://localhost:8000/api/redoc/
- **OpenAPI Schema**: http://localhost:8000/api/schema/

### **Admin Interface**
- **Django Admin**: http://localhost:8000/admin/
- Use superuser credentials to access

### **Database Management**
```bash
# PostgreSQL shell
make db-access

# Django shell
make shell

# Check database status
cd backend && python manage.py dbshell
```

---

## 🚀 Production Testing

### **Test Production Settings Locally**
```bash
# Test production configuration
make prod-test

# Test static file collection
cd backend && DJANGO_SETTINGS_MODULE=movie_nexus.settings.production python manage.py collectstatic --noinput
```

---
