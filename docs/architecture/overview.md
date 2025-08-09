# Movie Nexus Architecture Overview

> **System Design and Technical Architecture**
> Django REST Framework | PostgreSQL | Redis | TMDb Integration

## 📋 Table of Contents

- [System Overview](#system-overview)
- [Architecture Patterns](#architecture-patterns)
- [Application Layer Structure](#application-layer-structure)
- [Database Design](#database-design)
- [Service Layer](#service-layer)
- [Caching Strategy](#caching-strategy)
- [External Integrations](#external-integrations)
- [Security Architecture](#security-architecture)
- [Performance Considerations](#performance-considerations)

---

## 🎯 System Overview

Movie Nexus follows a **service-oriented architecture** with clear separation of concerns, implementing Django best practices for scalability and maintainability.

### High-Level Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Load Balancer │    │   Django API    │
│   (Next.js)     │◄──►│   (Nginx)       │◄──►│   (DRF)         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                       ┌─────────────────┐            │
                       │   Redis Cache   │◄───────────┤
                       │   (Sessions)    │            │
                       └─────────────────┘            │
                                                       │
                       ┌─────────────────┐            │
                       │   PostgreSQL    │◄───────────┤
                       │   (Primary DB)  │            │
                       └─────────────────┘            │
                                                       │
                       ┌─────────────────┐            │
                       │   TMDb API      │◄───────────┘
                       │   (External)    │
                       └─────────────────┘
```

### Technology Stack
- **Backend Framework**: Django 5.0+ with Django REST Framework
- **Database**: PostgreSQL 15+ (primary), Redis 7.0+ (cache/sessions)
- **Authentication**: JWT tokens with refresh mechanism
- **External APIs**: The Movie Database (TMDb) API v3
- **Containerization**: Docker with multi-stage builds
- **Web Server**: Nginx (reverse proxy + static files)
- **Background Tasks**: Celery with RabbitMQ (planned)

---

## 🏗️ Architecture Patterns

### 1. Service Layer Pattern
Separates business logic from views and models, promoting code reusability and testability.

```python
# Service Structure
apps/movies/services/
├── movie_service.py          # Movie business logic
├── recommendation_service.py # Recommendation algorithms
└── genre_service.py          # Genre management

core/services/tmdb/           # Shared TMDb integration
├── base.py                   # Base TMDb client
├── client.py                 # Main TMDb API client
└── movies.py                 # Movie-specific TMDb operations
```

### 2. Repository Pattern (via Django ORM)
Custom managers and querysets provide abstraction over data access.

```python
# Custom Manager Example
class MovieManager(models.Manager):
    def get_by_tmdb_id(self, tmdb_id):
        return self.get(tmdb_id=tmdb_id, is_active=True)

    def popular_movies(self, limit=20):
        return self.filter(is_active=True).order_by('-popularity')[:limit]
```

### 3. Mixin Pattern
Reusable model behaviors through mixins for consistent functionality.

```python
# Core Mixins
core/mixins/models.py:
├── BaseModelMixin       # created_at, updated_at, is_active
├── MetadataMixin       # JSON metadata field
└── TMDbContentMixin    # TMDb-specific fields
```

---

## 📱 Application Layer Structure

### Django Apps Organization
```
backend/apps/
├── authentication/     # User auth, JWT, sessions
│   ├── models/        # User, Session, VerificationToken
│   ├── services/      # AuthService, TokenService, EmailService
│   ├── serializers/   # Request/response validation
│   └── views/         # API endpoints
├── users/             # User profiles and preferences
│   ├── models/        # Profile
│   └── services/      # UserService
├── movies/            # Movie catalog and discovery
│   ├── models/        # Movie, Genre, MovieGenre, MovieRecommendation
│   ├── services/      # MovieService, GenreService, RecommendationService
│   └── views/         # Movie CRUD, discovery, relationships
└── favorites/         # User favorites and watchlist
    ├── models/        # Favorite
    ├── services/      # FavoriteService
    └── views/         # Favorites management, analytics
```

### Core Utilities
```
backend/core/
├── mixins/            # Reusable model and manager behaviors
├── services/          # Shared business logic
├── permissions.py     # Custom permission classes
├── responses.py       # Standardized API responses
├── exceptions.py      # Custom exception classes
└── constants.py       # Application constants
```

---

## 🗄️ Database Design

### Core Entities and Relationships

```sql
-- User Management
auth_user (Django's User model extended)
auth_user_profile (One-to-One with User)
auth_user_session (User authentication sessions)

-- Movie Catalog
movies_movie (Core movie entity)
movies_genre (Movie genres from TMDb)
movies_movie_genre (Many-to-Many through table)
movies_movie_recommendation (Movie relationships)

-- User Interactions
favorites_favorite (User's favorite movies)
```

### Key Relationships
```python
# User ↔ Favorites (One-to-Many)
User.favorites → Favorite.user

# Movie ↔ Genres (Many-to-Many through MovieGenre)
Movie.genres ↔ Genre.movies (through MovieGenre)

# Movie ↔ Recommendations (Many-to-Many through MovieRecommendation)
Movie.related_movies ↔ Movie.recommended_by (through MovieRecommendation)

# User ↔ Movies (Many-to-Many through Favorite)
User.favorited_movies ↔ Movie.favorited_by (through Favorite)
```

### Database Optimization
- **Strategic Indexing**: High-query fields (tmdb_id, popularity, vote_average)
- **Relationship Optimization**: `select_related` and `prefetch_related` usage
- **Constraints**: Database-level data integrity validation
- **Soft Deletes**: `is_active` field for data preservation

---

## ⚙️ Service Layer

### Service Responsibilities

#### MovieService
```python
class MovieService:
    def get_popular_movies(page=1, store_movies=True)
    def search_movies(query, page=1, sync_results=True)
    def sync_movie_from_tmdb(tmdb_id)
    def update_movie_data(movie, tmdb_data)
```

#### FavoriteService
```python
class FavoriteService:
    def add_favorite(user, movie_id, user_rating=None, notes="")
    def remove_favorite(user, movie_id)
    def get_user_stats(user)
    def search_user_favorites(user, query)
```

#### AuthService
```python
class AuthService:
    def authenticate_user(email, password, request)
    def create_user_account(**user_data)
    def verify_user_email(verification_token)
```

### Service Layer Benefits
- **Business Logic Separation**: Views focus on HTTP handling
- **Reusability**: Services used across multiple views
- **Testing**: Easier unit testing of business logic
- **Consistency**: Standardized data operations

---

## 🚀 Caching Strategy

### Multi-Level Caching Architecture

#### 1. View-Level Caching
```python
# Complete API response caching
cache_key = f"movie_detail_view_{pk}"
cached_response = cache.get(cache_key)
if cached_response:
    return APIResponse.success("Movie details from CACHE", cached_response)
```

#### 2. Service-Level Caching
```python
# TMDb API response caching
def get_popular_movies(self, page=1):
    cache_key = f"tmdb_popular_movies_{page}"
    cached_data = cache.get(cache_key)
    if not cached_data:
        cached_data = self.tmdb_client.get_popular_movies(page)
        cache.set(cache_key, cached_data, timeout=3600)
    return cached_data
```

#### 3. Database Query Caching
```python
# Expensive query results caching
def get_user_stats(self, user):
    cache_key = f"user_favorite_stats_{user.id}"
    stats = cache.get(cache_key)
    if not stats:
        stats = self._calculate_user_stats(user)
        cache.set(cache_key, stats, timeout=3600)
    return stats
```

### Cache Configuration
- **Redis TTL Strategy**: Variable expiration based on data volatility
- **Cache Invalidation**: Smart cleanup on data modifications
- **Cache Keys**: Hierarchical naming for easy management
- **Fallback Strategy**: Graceful degradation when cache unavailable

---

## 🔗 External Integrations

### TMDb API Integration

#### Client Architecture
```python
core/services/tmdb/
├── base.py          # Base TMDb client with auth
├── client.py        # Main TMDb API client
└── movies.py        # Movie-specific operations

class TMDbMoviesClient:
    def get_movie_details(movie_id)
    def get_popular_movies(page=1)
    def get_recommendations(movie_id, page=1)
    def search_movies(query, page=1)
```

#### Data Synchronization Strategy
1. **On-Demand Fetching**: Missing movies fetched when requested
2. **Intelligent Storage**: Partial vs. complete data tracking
3. **Background Sync**: Periodic updates for popular content
4. **Error Handling**: Graceful fallbacks for API failures

## 🛡️ Security Architecture

### Data Protection
- **Input Validation**: Comprehensive serializer validation
- **SQL Injection Prevention**: Django ORM exclusive usage
- **Rate Limiting**: API abuse prevention
- **CORS Configuration**: Cross-origin request security
- **Environment Variables**: Sensitive data protection

---

## 📊 Performance Considerations

### Database Performance
```python
# Query Optimization Examples
# Avoid N+1 queries
movies = Movie.objects.select_related().prefetch_related(
    'movie_genres__genre'
).filter(is_active=True)

# Strategic indexing
class Movie(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['tmdb_id', 'is_active']),
            models.Index(fields=['popularity', 'vote_average']),
            models.Index(fields=['release_date', 'status']),
        ]
```

### API Performance Optimization
- **Pagination**: Efficient large dataset handling
- **Field Selection**: Minimal data transfer
- **Response Compression**: Gzip compression enabled
- **Connection Pooling**: Database connection optimization

### Monitoring & Metrics
- **Response Times**: Sub-100ms for cached responses
- **Cache Hit Rates**: 85%+ for frequently accessed data
- **Database Queries**: Optimized for minimal query count
- **Memory Usage**: Efficient Django ORM usage

---

## 🔄 Data Flow Examples

### User Registration Flow
```
1. User submits registration data
2. UserRegistrationSerializer validates input
3. AuthService.create_user_account() processes
4. VerificationToken created and stored
5. EmailService sends verification email
6. User profile automatically created
7. Success response with user data
```

### Movie Discovery Flow
```
1. User requests popular movies
2. MovieService checks cache first
3. If cache miss → TMDb API call
4. Store basic movie data in database
5. Cache response for future requests
6. Return paginated movie list
```

### Favorite Management Flow
```
1. User adds movie to favorites
2. FavoriteService validates movie exists
3. If movie missing → sync from TMDb
4. Create Favorite record with metadata
5. Update user statistics cache
6. Return success with favorite data
```

---

## 🔧 Development Patterns

### Code Organization Principles
- **Single Responsibility**: Each class/function has one purpose
- **DRY (Don't Repeat Yourself)**: Shared logic in mixins/services
- **Separation of Concerns**: Views, services, models have distinct roles
- **Dependency Injection**: Services injected into views

### Error Handling Strategy
```python
# Consistent error responses
try:
    result = some_operation()
    return APIResponse.success("Operation successful", result)
except ValidationException as e:
    return APIResponse.validation_error(str(e.detail), e.field_errors)
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return APIResponse.server_error("Operation failed")
```

---
