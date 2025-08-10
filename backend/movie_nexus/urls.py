"""
Main project URL configuration.
"""
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request):
    """API root endpoint providing basic information and navigation."""
    return Response(
        {
            "message": "Welcome to Movie Nexus API",
            "version": "v1.0.0",
            "description": "Professional Movie Recommendation Backend - ALX ProDev Capstone",
            "documentation": {
                "swagger": request.build_absolute_uri("/api/docs/"),
                "redoc": request.build_absolute_uri("/api/redoc/"),
                "schema": request.build_absolute_uri("/api/schema/"),
            },
            "endpoints": {
                "authentication": "/api/v1/auth/",
                "movies": "/api/v1/movies/",
                "favorites": "/api/v1/favorites/",
                "users": "/api/v1/users/",
            },
            "status": "active",
            "developer": {
                "name": "Abdessamad Haddouche",
                "github": "https://github.com/abdessamad-haddouche/alx-project-nexus",
            },
        }
    )


# Custom 404 handler for API endpoints
def custom_404_view(request, exception=None):
    """Return JSON 404 response for API endpoints."""
    return JsonResponse(
        {
            "success": False,
            "message": "API endpoint not found",
            "status_code": 404,
            "available_endpoints": {
                "authentication": "/api/v1/auth/",
                "movies": "/api/v1/movies/",
                "favorites": "/api/v1/favorites/",
                "users": "/api/v1/users/",
                "documentation": "/api/docs/",
            },
        },
        status=404,
    )


urlpatterns = [
    # API Root
    path("api/v1/", api_root, name="api-root"),
    # Django admin
    path("admin/", admin.site.urls),
    # API v1 endpoints
    path("api/v1/", include("api.v1.urls")),
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Custom error handlers
handler404 = custom_404_view

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
