# 🎬 Nexus — Movie Recommendation App  
*ALX ProDev Backend Engineering Capstone Project*

> A robust backend for movie recommendations, seamlessly integrated with a React frontend.  
> Part of the ALX ProDev Backend Engineering Program.

---

### 🚀 API Endpoint  
[https://abdessamad.tech/api/v1/](https://abdessamad.tech/api/v1/)

### 🌐 Live Demo  
[https://alx-project-nexus-h9z9.vercel.app/](https://alx-project-nexus-h9z9.vercel.app/)


## 👨‍💻 About the Developer

**Abdessamad Haddouche**  
Backend Engineer | ALX Software Engineering Graduate  

🔗 **GitHub:** [github.com/abdessamad-haddouche](https://github.com/abdessamad-haddouche)  
💼 **LinkedIn:** [linkedin.com/in/abdessamad-haddouche](https://linkedin.com/in/abdessamad-haddouche)


### 🤝 Frontend Collaboration

This project highlights successful **backend-frontend collaboration** between ALX ProDev programs.

- **Frontend Developer:** [Soumia Bellali](https://github.com/besomi22) *(ALX ProDev Frontend Program)*  
- **Frontend Repository:** [github.com/besomi22](https://github.com/besomi22)  
- **Live Frontend Demo:** [https://alx-project-nexus-h9z9.vercel.app/](https://alx-project-nexus-h9z9.vercel.app/)

> Soumia leveraged this backend API to build a modern Next.js frontend, demonstrating seamless API integration and effective cross-program collaboration.


---

## 🎓 ALX ProDev Backend Engineering Program

### Program Overview

The **ALX ProDev Backend Engineering Program** is an intensive, industry-focused curriculum designed to develop skilled and proficient backend engineers. This comprehensive program covers backend development from foundational concepts to advanced scalable system design.

### 🏆 Major Learnings & Technologies Covered

**Key Technologies Mastered:**
- **Python** - Advanced concepts (Generators, Decorators, Context Managers, Async Programming)
- **Django & Django REST Framework** - Full-stack web development with DRF
- **REST APIs** - RESTful architecture design and implementation
- **GraphQL** - Modern API query language integration
- **Docker** - Containerization and multi-service orchestration
- **CI/CD** - Automated deployment pipelines with GitHub Actions

**Important Backend Development Concepts:**
- **Database Design** - PostgreSQL optimization, relationships, and indexing strategies
- **Asynchronous Programming** - High-performance concurrent operations
- **Caching Strategies** - Multi-level caching with Redis for optimal performance
- **Authentication & Security** - JWT, RBAC, and comprehensive security practices
- **API Documentation** - Swagger/OpenAPI implementation
- **Background Tasks** - Celery integration for scalable task processing

### 🚧 Challenges Faced & Solutions Implemented

**1. TMDb API Integration & Rate Limiting**
- **Challenge:** Managing external API calls while maintaining performance
- **Solution:** Implemented intelligent Redis caching strategy and background sync jobs

**2. Complex Database Relationships**
- **Challenge:** Designing efficient schema for movies, genres, users, and favorites
- **Solution:** Custom Django managers, strategic indexing, and optimized ORM queries

**3. Authentication & Authorization Architecture**
- **Challenge:** Building secure, scalable JWT authentication system
- **Solution:** Custom permission classes, email verification, JWT blacklisting and session management

**4. Multi-Level Caching Strategy**
- **Challenge:** Implementing caching without data inconsistency
- **Solution:** Hierarchical cache keys, cache warming, and smart invalidation

**5. Production Deployment & DevOps**
- **Challenge:** Deploying multi-service application to production
- **Solution:** Docker containerization, Digital Ocean cloud deployment, Nginx load balancer configuration, and automated CI/CD pipelines

### 🏆 Best Practices & Personal Takeaways

**Code Quality & Standards:**
- Service Layer Pattern for business logic separation
- Custom exception handling for consistent error responses
- Comprehensive API documentation with Swagger
- Strategic use of Django ORM optimization techniques
- Pre-commit hooks implementation for automated code quality checks (Black, isort, flake8, trailing whitespace, YAML/JSON validation)

**Performance & Security:**
- Multi-layer caching implementation (view, service, database levels)
- JWT best practices with secure token management
- Database query optimization and strategic indexing
- Input validation and comprehensive security measures

**Development Workflow:**
- Git best practices with meaningful commits and proper branching
- Documentation-driven development approach
- Professional project structure and code organization
- Production deployment on Digital Ocean with Nginx load balancing

---

## 🎬 Project Overview: Movie Nexus

Movie Nexus represents the culmination of my ALX ProDev Backend Engineering journey, implementing every major concept learned throughout the program. This project mirrors real-world backend development scenarios where performance, security, and user-centric design are crucial.

### ✨ Key Features
- **🔐 Advanced Authentication** - JWT-based auth with email verification
- **🎬 Movie Discovery** - TMDb API integration with intelligent caching
- **⭐ Smart Recommendations** - Genre-based and similarity recommendations
- **❤️ User Favorites** - Personal watchlist and rating system
- **🚀 High Performance** - Multi-level Redis caching and optimized queries
- **🐳 Production Ready** - Docker containerization, Digital Ocean hosting, and Nginx load balancer

### 🛠️ Technology Stack
- **Backend:** Django 5.0+ & Django REST Framework
- **Database:** PostgreSQL 15+ (Primary), Redis 7.0+ (Cache/Sessions)
- **Authentication:** JWT with custom permissions and email verification
- **External APIs:** TMDb API v3 integration
- **Frontend:** React 18 + Redux Toolkit + TailwindCSS
- **DevOps:** Docker, GitHub Actions CI/CD, Digital Ocean hosting, Nginx load balancer

---

## 🚀 Quick Start

```bash
# Clone repository
git clone https://github.com/abdessamad-haddouche/alx-project-nexus.git
cd alx-project-nexus

# Docker setup (recommended)
docker-compose up --build

# OR Local development
python -m venv .venv && source .venv/bin/activate
make dev-install && make migrate && make run

# Access API: http://localhost:8000/api/docs/
```

---

## 📚 Complete Documentation

### 📖 Core Documentation

| Documentation | Description | Link |
|---------------|-------------|------|
| 🔧 **Development Setup** | Complete local environment setup guide | **[docs/development/setup.md](docs/development/setup.md)** |
| 🔌 **API Reference** | Comprehensive endpoint documentation with examples | **[docs/api/README.md](docs/api/README.md)** |
| 🏗️ **System Architecture** | Technical design, database schema, and patterns | **[docs/architecture/overview.md](docs/architecture/overview.md)** |
| 🐳 **Deployment Guide** | Docker and production deployment instructions | **[docs/deployment/docker.md](docs/deployment/docker.md)** |

### 🌐 Live Resources

| Resource | Description | URL |
|----------|-------------|-----|
| 🌍 **Live API** | Production backend endpoint | [abdessamad.tech/api/v1](https://abdessamad.tech/api/v1/) |
| 📋 **Interactive API Docs** | Swagger documentation interface | [abdessamad.tech/api/docs](https://abdessamad.tech/api/docs/) |
| 📱 **Frontend Demo** | React frontend consuming the API | [alx-project-nexus-h9z9.vercel.app](https://alx-project-nexus-h9z9.vercel.app/) |
| 📄 **OpenAPI Schema** | API specification download | [abdessamad.tech/api/schema](https://abdessamad.tech/api/schema/) |

---

## 📁 Project Structure

```plaintext
alx-project-nexus/
├── 📄 README.md                    # Project documentation
├── 🐳 Dockerfile                   # Container configuration
├── 🔧 Makefile                     # Development automation
├── 📄 .pre-commit-config.yaml      # Code quality hooks
├── 📁 backend/                     # Django REST API
│   ├── 📁 apps/                   # Django applications
│   │   ├── 📁 authentication/     # JWT auth & user management
│   │   │   ├── 📁 models/         # User, Session, VerificationToken
│   │   │   ├── 📁 services/       # AuthService, EmailService, TokenService
│   │   │   ├── 📁 serializers/    # Request/response validation
│   │   │   └── 📁 views/          # Authentication endpoints
│   │   ├── 📁 movies/             # Movie catalog & discovery
│   │   │   ├── 📁 models/         # Movie, Genre, MovieGenre, Recommendation
│   │   │   ├── 📁 services/       # MovieService, RecommendationService
│   │   │   ├── 📁 managers/       # Custom ORM managers
│   │   │   └── 📁 views/          # Movie CRUD & discovery endpoints
│   │   ├── 📁 favorites/          # User favorites & watchlist
│   │   │   ├── 📁 models/         # Favorite model
│   │   │   ├── 📁 services/       # FavoriteService
│   │   │   └── 📁 views/          # Favorites management
│   │   └── 📁 users/              # User profiles & preferences
│   │       ├── 📁 models/         # UserProfile
│   │       ├── 📁 services/       # UserService
│   │       └── 📁 views/          # Profile management
│   ├── 📁 core/                   # Shared utilities & services
│   │   ├── 📁 mixins/             # Reusable model/manager behaviors
│   │   ├── 📁 services/tmdb/      # TMDb API integration
│   │   ├── 📄 permissions.py      # Custom permission classes
│   │   ├── 📄 exceptions.py       # Custom exception handling
│   │   └── 📄 responses.py        # Standardized API responses
│   ├── 📁 movie_nexus/            # Django project settings
│   │   ├── 📁 settings/           # Environment-specific configs
│   │   ├── 📄 urls.py             # URL routing
│   │   └── 📄 celery.py           # Background task configuration
│   ├── 📁 requirements/           # Layered dependencies
│   │   ├── 📄 base.txt            # Core dependencies
│   │   ├── 📄 development.txt     # Development tools
│   │   ├── 📄 production.txt      # Production packages
│   │   └── 📄 testing.txt         # Testing frameworks
│   └── 📄 manage.py               # Django management script
├── 📁 frontend/                   # React frontend (optional)
├── 📁 docs/                       # 📖 Complete Documentation
│   ├── 📄 api/README.md           # 🔌 API Documentation
│   ├── 📄 architecture/overview.md # 🏗️ System Architecture
│   ├── 📄 development/setup.md    # 🔧 Setup Guide
│   └── 📄 deployment/docker.md    # 🐳 Deployment Instructions
└── 📁 scripts/                    # Deployment & utility scripts
    ├── 📄 build.sh                # Production build script
    └── 📄 entrypoint.sh           # Container entrypoint
```

---

## 🎯 ALX ProDev Project Requirements Fulfilled

```plaintext
✅ **API Creation** - Comprehensive endpoints for movie recommendations and user management
✅ **User Management** - JWT authentication with favorite movies functionality
✅ **Performance Optimization** - Redis caching implementation for enhanced performance
✅ **TMDb Integration** - Robust third-party API integration with error handling
✅ **Documentation** - Swagger API documentation hosted at `/api/docs/`
✅ **Code Quality** - Modular, maintainable code following Django best practices
✅ **Deployment** - Production-ready hosting with CI/CD implementation
```

---

## 🙏 Acknowledgments

**Special Thanks to ALX Africa Staff:**  
- The dedicated ALX ProDev Backend Engineering instructors and mentors  
- The supportive ALX community and fellow learners  
- The comprehensive curriculum that enabled this project  

**Frontend Collaboration:**  
- **[Soumia Bellali](https://github.com/besomi22)** from ALX ProDev Frontend Program for seamless API integration  

**Technologies & Communities:**  
- Django and Django REST Framework communities  
- The Movie Database (TMDb) for providing an excellent movie data API  
- Open source contributors whose work made this project possible  

---
