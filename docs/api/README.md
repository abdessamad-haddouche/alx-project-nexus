# 🎬 Movie Nexus API Reference

> **API reference for the Movie Nexus Backend**  
> 📄 **Full Documentation:** [View API Docs](https://abdessamad.tech/api/docs/)

---

## 🔗 Base Information

- **Base URL:** [`https://abdessamad.tech/api/v1/`](https://abdessamad.tech/api/v1/)
- **Authentication:** JWT Bearer Token
- **Response Format:** JSON

---

## 🔐 Authentication

### Authorization Header
```bash
Authorization: Bearer <access_token>
```


### Token Management
```bash
curl -X POST https://abdessamad.tech/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'

# Refresh expired token
curl -X POST https://abdessamad.tech/api/v1/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "your_refresh_token"}'
```

### Permission Classes

- **AllowAny** – Public endpoints (registration, login)  
- **IsAuthenticated** – Requires valid JWT token  
- **IsAdminUser** – Admin/staff users only  
- **IsSuperUserOnly** – Superuser operations only  
- **IsOwnerOrReadOnly** – Object ownership validation  


## 🏗️ API Structure

### URL Routing Hierarchy

```bash
/api/v1/
├── auth/                    # Authentication endpoints
├── admin-management/        # Admin operations
├── users/                   # User profile management
├── movies/                  # Movie catalog & discovery
├── favorites/               # User favorites & watchlist
└── recommendations/         # Recommendation algorithms
```

### HTTP Methods & Conventions

- GET - Retrieve data (list/detail)
- POST - Create new resources
- PUT - Full resource update
- PATCH - Partial resource update
- DELETE - Remove/deactivate resources


## 🚀 Core Endpoints

### Authentication Endpoints Summary

| Endpoint                              | Method | Description                                  | Permission        |
|---------------------------------------|--------|----------------------------------------------|-------------------|
| `/auth/register/`                     | POST   | User registration with email verification   | AllowAny          |
| `/auth/login/`                        | POST   | User login with JWT token generation        | AllowAny          |
| `/auth/logout/`                       | POST   | Logout with token blacklisting               | IsAuthenticated   |
| `/auth/token/refresh/`                | POST   | Refresh expired access token                 | AllowAny          |
| `/auth/token/verify/`                 | POST   | Verify token validity                        | AllowAny          |
| `/auth/verify-email/`                 | POST   | Email verification with token                | AllowAny          |
| `/auth/resend-verification/`          | POST   | Resend verification email                    | AllowAny          |
| `/auth/password/reset/`               | POST   | Password reset request                       | AllowAny          |
| `/auth/password/reset/confirm/`       | POST   | Password reset confirmation                  | AllowAny          |

### Movie Discovery Endpoints

| Endpoint                                      | Method | Description                          | Parameters                                                  |
|-----------------------------------------------|--------|--------------------------------------|-------------------------------------------------------------|
| `/movies/`                                    | GET    | List/search movies                   | `search`, `genre`, `min_rating`, `page`, `page_size`        |
| `/movies/{id}/`                               | GET    | Movie details by TMDb ID              | -                                                           |
| `/movies/search/`                             | GET    | Advanced movie search                 | `q`, `page`, `store_results`, `force_sync`                  |
| `/movies/popular/`                            | GET    | Popular movies from TMDb              | `page`, `store_results`                                     |
| `/movies/trending/`                           | GET    | Trending movies                       | `time_window` (`day`/`week`), `store_results`               |
| `/movies/top-rated/`                          | GET    | Top-rated movies                      | `page`, `store_results`                                     |
| `/movies/{id}/recommendations/`               | GET    | Movie recommendations                 | `limit`, `min_rating`, `force_sync`                         |
| `/movies/{id}/similar/`                       | GET    | Similar movies                        | `limit`, `min_rating`, `force_sync`                         |
| `/movies/{id}/genres/`                        | GET    | Movie genres                          | `include_stats`, `include_related`                          |

### User Management Endpoints

| Endpoint                                   | Method        | Description                     | Permission      |
|--------------------------------------------|---------------|---------------------------------|-----------------|
| `/users/profile/`                          | GET           | Get user profile                | IsAuthenticated |
| `/users/profile/`                          | PUT / PATCH   | Update user profile              | IsAuthenticated |
| `/users/profile/update/`                   | PUT / PATCH   | Update profile fields only       | IsAuthenticated |
| `/users/account/password/change/`          | POST          | Change password                  | IsAuthenticated |


### Favorites Endpoints 

| Endpoint                                    | Method  | Description                 | Permission      |
|---------------------------------------------|---------|-----------------------------|-----------------|
| `/favorites/`                               | GET     | List user favorites         | IsAuthenticated |
| `/favorites/create/`                        | POST    | Add movie to favorites      | IsAuthenticated |
| `/favorites/tmdb/create/`                   | POST    | Add by TMDb ID               | IsAuthenticated |
| `/favorites/{id}/`                          | GET     | Favorite details             | IsAuthenticated |
| `/favorites/{id}/update/`                   | PATCH   | Update favorite              | IsAuthenticated |
| `/favorites/{id}/delete/`                   | DELETE  | Remove favorite              | IsAuthenticated |
| `/favorites/toggle/`                        | POST    | Toggle favorite status       | IsAuthenticated |
| `/favorites/watchlist/`                     | GET     | User watchlist               | IsAuthenticated |
| `/favorites/watchlist/add/`                 | POST    | Add to watchlist             | IsAuthenticated |
| `/favorites/watchlist/remove/`              | POST    | Remove from watchlist        | IsAuthenticated |
| `/favorites/stats/`                         | GET     | User statistics              | IsAuthenticated |

### Genre Management Endpoints

| Endpoint                                      | Method  | Description         | Permission   |
|-----------------------------------------------|---------|---------------------|--------------|
| `/movies/genres/`                             | GET     | List all genres     | AllowAny     |
| `/movies/genres/create/`                      | POST    | Create genre        | IsAdminUser  |
| `/movies/genres/{id}/`                        | GET     | Genre details       | AllowAny     |
| `/movies/genres/{id}/update/`                 | PATCH   | Update genre        | IsAdminUser  |
| `/movies/genres/{id}/delete/`                 | DELETE  | Delete genre        | IsAdminUser  |
| `/movies/genres/{id}/movies/`                 | GET     | Movies by genre     | AllowAny     |


### Admin Operations Endpoints

| Endpoint                                          | Method  | Description                  | Permission       |
|---------------------------------------------------|---------|------------------------------|------------------|
| `/admin-management/admin/create/`                 | POST    | Create admin user            | IsSuperUserOnly  |
| `/admin-management/admin/promote/`                | POST    | Promote user to admin        | IsSuperUserOnly  |
| `/admin-management/admin/revoke/{id}/`            | DELETE  | Revoke admin privileges      | IsSuperUserOnly  |
| `/admin-management/admin/list/`                   | GET     | List admin users              | IsSuperUserOnly  |
| `/admin-management/superadmin/create/`            | POST    | Create superadmin            | IsSuperUserOnly  |

## 🔧 Quick Examples

### Complete User Registration Flow

#### 1. Register User
```bash
curl -X POST https://abdessamad.tech/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123!",
    "password_confirm": "SecurePass123!",
    "first_name": "Test",
    "last_name": "User"
  }'
```

#### 2. Verify Email (token received via email)
```bash
curl -X POST https://abdessamad.tech/api/v1/auth/verify-email/ \
  -H "Content-Type: application/json" \
  -d '{"token": "email_verification_token"}'
```

#### 3. Login to Get Tokens
```bash
curl -X POST https://abdessamad.tech/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123!"
  }'
```

### Movie Discovery Workflow

```bash
curl -X GET "https://abdessamad.tech/api/v1/movies/trending/?time_window=week"
```

```bash
curl -X GET "https://abdessamad.tech/api/v1/movies/search/?q=batman&page=1"
```

```bash
curl -X GET "https://abdessamad.tech/api/v1/movies/550/"
```

```bash
curl -X GET "https://abdessamad.tech/api/v1/movies/550/recommendations/?limit=10&min_rating=7.0"
```

```bash
curl -X GET "https://abdessamad.tech/api/v1/movies/550/similar/?limit=12&min_rating=6.0"
```

### Favorites Management Workflow

#### 1. Add Movie to Favorites (with Authentication)
```bash
curl -X POST https://abdessamad.tech/api/v1/favorites/create/ \
  -H "Authorization: Bearer your_access_token" \
  -H "Content-Type: application/json" \
  -d '{
    "movie": 550,
    "user_rating": 9,
    "notes": "One of the best movies ever made!",
    "is_watchlist": false
  }'
```

#### 2. Add Movie to Favorites by TMDb ID

```bash
curl -X POST https://abdessamad.tech/api/v1/favorites/tmdb/create/ \
  -H "Authorization: Bearer your_access_token" \
  -H "Content-Type: application/json" \
  -d '{
    "tmdb_id": "550",
    "user_rating": 8,
    "notes": "Must watch again!"
  }'
```

#### 3. Toggle Favorite Status (Quick Add/Remove)
```bash
curl -X POST https://abdessamad.tech/api/v1/favorites/tmdb/create/ \
  -H "Authorization: Bearer your_access_token" \
  -H "Content-Type: application/json" \
  -d '{
    "tmdb_id": "550",
    "user_rating": 8,
    "notes": "Must watch again!"
  }'
```

#### 4. Get User Favorites with Filters
```bash
curl -X GET "https://abdessamad.tech/api/v1/favorites/?rating_min=8&page=1" \
  -H "Authorization: Bearer your_access_token"
```

### Profile Management

#### 1. Get user profile

```bash
curl -X GET https://abdessamad.tech/api/v1/users/profile/ \
  -H "Authorization: Bearer your_access_token"
```

#### 2. Update profile

```bash
curl -X PATCH https://abdessamad.tech/api/v1/users/profile/ \
  -H "Authorization: Bearer your_access_token" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Updated",
    "bio": "Updated biography",
    "location": "New York, NY",
    "theme_preference": "dark"
  }'
```

#### 3. Change password

```bash
curl -X POST https://abdessamad.tech/api/v1/users/account/password/change/ \
  -H "Authorization: Bearer your_access_token" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "OldPass123!",
    "new_password": "NewSecurePass456!",
    "new_password_confirm": "NewSecurePass456!"
  }'
```

## 🛡️ Authentication Notes

- **JWT Tokens** expire in 1 hour
- **Refresh Tokens** expire in 7 days
- Include `Authorization: Bearer <token>` header for protected endpoints
- Use `/auth/token/refresh/` to get new access token

## 📈 Rate Limits

- **Anonymous**: 100 requests/hour
- **Authenticated**: 1000 requests/hour
- **Auth endpoints**: 10 requests/hour

## 🔗 Additional Resources

- **Full API Docs**: [https://abdessamad.tech/api/docs/](https://abdessamad.tech/api/docs/)
- **Interactive Docs**: [https://abdessamad.tech/api/redoc/](https://abdessamad.tech/api/redoc/)
- **OpenAPI Schema**: [https://abdessamad.tech/api/schema/](https://abdessamad.tech/api/schema/)
- **Frontend Demo**: [https://alx-project-nexus-h9z9.vercel.app/](https://alx-project-nexus-h9z9.vercel.app/)

---

*For complete endpoint documentation with detailed examples, visit the [interactive API documentation](https://abdessamad.tech/api/docs/).*
