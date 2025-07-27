"""
Recommendation engine API endpoints.
Handles personalized recommendations, similar movies, trending suggestions, etc.
"""
from django.urls import path

from . import views

app_name = "recommendations"

urlpatterns = [
    # Personalized recommendations
    path("", views.PersonalizedRecommendationsView.as_view(), name="personalized"),
    path("trending/", views.TrendingRecommendationsView.as_view(), name="trending"),
    path("discover/", views.DiscoveryRecommendationsView.as_view(), name="discover"),
]
