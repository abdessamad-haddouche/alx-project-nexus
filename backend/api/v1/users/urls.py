"""
User management API endpoints.
Handles user profiles, preferences, settings, etc.
"""
from django.urls import path

app_name = "users"

urlpatterns = [
    # # Current user profile
    # path("me/", views.CurrentUserProfileView.as_view(), name="current-user"),
    # path("me/profile/", views.UserProfileUpdateView.as_view(), name="profile-update"),
    # # Avatar management
    # path('me/avatar/', views.AvatarUploadView.as_view(), name='avatar-upload'),
    # path('me/avatar/delete/', views.AvatarDeleteView.as_view(), name='avatar-delete'),
]
