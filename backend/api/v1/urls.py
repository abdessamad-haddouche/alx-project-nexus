"""
Main URL routing for API v1.
All v1 endpoints are routed through here.
"""
from django.urls import include, path

app_name = "api_v1"

urlpatterns = [
    # Authentication endpoints
    path("auth/", include("api.v1.authentication.urls")),
    # Admin management endpoints
    path("admin-management/", include("api.v1.admin.urls")),
    # User management endpoints
    path("users/", include("api.v1.users.urls")),
    # Movie catalog endpoints
    path("movies/", include("api.v1.movies.urls")),
    # Recommendation endpoints
    path("recommendations/", include("api.v1.recommendations.urls")),
    # User favorites endpoints
    path("favorites/", include("api.v1.favorites.urls")),
]
