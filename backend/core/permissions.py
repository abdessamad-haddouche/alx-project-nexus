"""
Custom permission classes for Movie Nexus API.
"""

import logging
from typing import Any

from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import View

from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

User = get_user_model()


# =========================================================================
# BASE PERMISSION CLASSES
# =========================================================================


class BasePermission(permissions.BasePermission):
    """
    Base permission class with enhanced logging and error messages.

    Provides common functionality for all custom permissions.
    """

    def has_permission(self, request: Request, view: View) -> bool:
        """
        Base permission check with logging.
        Override in subclasses.
        """
        return True

    def has_object_permission(self, request: Request, view: View, obj: Any) -> bool:
        """
        Base object permission check with logging.
        Override in subclasses.
        """
        return True

    def log_permission_denied(self, request: Request, reason: str):
        """Log permission denial for security monitoring."""
        user_info = (
            f"User: {request.user.id if request.user.is_authenticated else 'Anonymous'}"
        )
        logger.warning(
            f"Permission denied - {reason} | {user_info} | Path: {request.path}"
        )


# =========================================================================
# ADMIN PERMISSION CLASSES
# =========================================================================


class IsAdminUser(BasePermission):
    """
    Permission class that allows access only to admin users.

    Checks for:
    - User authentication
    - Admin status (is_staff=True or is_superuser=True)

    Usage:
        permission_classes = [IsAuthenticated, IsAdminUser]
    """

    message = "Admin access required. Only administrators can perform this action."

    def has_permission(self, request: Request, view: View) -> bool:
        """Check if user is authenticated admin."""
        if not request.user or not request.user.is_authenticated:
            self.log_permission_denied(
                request, "User not authenticated for admin action"
            )
            return False

        is_admin = request.user.is_staff or request.user.is_superuser

        if not is_admin:
            self.log_permission_denied(request, "Non-admin user attempted admin action")
            return False

        logger.info("Admin access granted to user {request.user.id}")
        return True


class IsSuperUserOnly(BasePermission):
    """
    Permission class that allows access only to superusers.

    More restrictive than IsAdminUser - requires is_superuser=True.
    Use for highly sensitive operations.
    """

    message = "Superuser access required. Only superusers can perform this action."

    def has_permission(self, request: Request, view: View) -> bool:
        """Check if user is authenticated superuser."""
        if not request.user or not request.user.is_authenticated:
            self.log_permission_denied(
                request, "User not authenticated for superuser action"
            )
            return False

        if not request.user.is_superuser:
            self.log_permission_denied(
                request, "Non-superuser attempted superuser action"
            )
            return False

        logger.info(f"Superuser access granted to user {request.user.id}")
        return True


class IsAdminOrReadOnly(BasePermission):
    """
    Permission class that allows:
    - Read access (GET, HEAD, OPTIONS) for any authenticated user
    - Write access (POST, PUT, PATCH, DELETE) only for admins
    """

    message = "Admin access required for write operations."

    def has_permission(self, request: Request, view: View) -> bool:
        """Check permission based on HTTP method."""
        # Allow read access for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated

        # Require admin for write operations
        if not request.user or not request.user.is_authenticated:
            self.log_permission_denied(
                request, "User not authenticated for write operation"
            )
            return False

        is_admin = request.user.is_staff or request.user.is_superuser

        if not is_admin:
            self.log_permission_denied(
                request, "Non-admin user attempted write operation"
            )
            return False

        return True


# =========================================================================
# OWNERSHIP PERMISSION CLASSES
# =========================================================================


class IsOwnerOrReadOnly(BasePermission):
    """
    Permission class that allows:
    - Read access for any authenticated user
    - Write access only for the object owner or admins

    Requires the object to have a 'user' or 'owner' field.
    """

    message = "You can only modify your own resources."

    def has_object_permission(self, request: Request, view: View, obj: Any) -> bool:
        """Check if user owns the object or is admin."""
        # Allow read access for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated

        if not request.user or not request.user.is_authenticated:
            self.log_permission_denied(
                request, "User not authenticated for ownership check"
            )
            return False

        # Admin users can modify anything
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Check object ownership
        owner = (
            getattr(obj, "user", None)
            or getattr(obj, "owner", None)
            or getattr(obj, "created_by", None)
        )

        if owner is None:
            logger.warning(f"Object {obj} has no owner field for permission check")
            return False

        is_owner = owner == request.user

        if not is_owner:
            self.log_permission_denied(
                request, "User attempted to modify non-owned object"
            )

        return is_owner


class IsOwnerOrAdmin(BasePermission):
    """
    Permission class that allows access only to:
    - Object owner
    - Admin users

    More restrictive than IsOwnerOrReadOnly - no read access for non-owners.
    """

    message = "You can only access your own resources or admin resources."

    def has_object_permission(self, request: Request, view: View, obj: Any) -> bool:
        """Check if user owns the object or is admin."""
        if not request.user or not request.user.is_authenticated:
            self.log_permission_denied(
                request, "User not authenticated for ownership check"
            )
            return False

        # Admin users can access anything
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Check object ownership
        owner = (
            getattr(obj, "user", None)
            or getattr(obj, "owner", None)
            or getattr(obj, "created_by", None)
        )

        if owner is None:
            logger.warning(f"Object {obj} has no owner field for permission check")
            return False

        is_owner = owner == request.user

        if not is_owner:
            self.log_permission_denied(
                request, "User attempted to access non-owned object"
            )

        return is_owner


# =========================================================================
# METHOD-SPECIFIC PERMISSION CLASSES
# =========================================================================


class ReadOnlyPermission(BasePermission):
    """
    Permission class that allows only read operations (GET, HEAD, OPTIONS).

    Use for endpoints that should never allow modifications.
    """

    message = "This endpoint is read-only."

    def has_permission(self, request: Request, view: View) -> bool:
        """Allow only safe HTTP methods."""
        if request.method not in permissions.SAFE_METHODS:
            self.log_permission_denied(
                request, "Write operation attempted on read-only endpoint"
            )
            return False

        return request.user and request.user.is_authenticated


class CreateOnlyPermission(BasePermission):
    """
    Permission class that allows only creation (POST) operations.

    Use for endpoints like registration where only creation should be allowed.
    """

    message = "This endpoint allows only creation operations."

    def has_permission(self, request: Request, view: View) -> bool:
        """Allow only POST method."""
        if request.method != "POST":
            self.log_permission_denied(
                request, "Non-POST operation attempted on create-only endpoint"
            )
            return False

        return True


# =========================================================================
# ROLE-BASED PERMISSION CLASSES
# =========================================================================


class HasRequiredRole(BasePermission):
    """
    Permission class that checks for specific user roles.

    Usage:
        class MyView(APIView):
            permission_classes = [HasRequiredRole]
            required_roles = ['admin', 'moderator']
    """

    message = "You do not have the required role to access this resource."

    def has_permission(self, request: Request, view: View) -> bool:
        """Check if user has required roles."""
        if not request.user or not request.user.is_authenticated:
            self.log_permission_denied(request, "User not authenticated for role check")
            return False

        required_roles = getattr(view, "required_roles", [])

        if not required_roles:
            # No specific roles required
            return True

        user_role = getattr(request.user, "role", None)

        if user_role is None:
            logger.warning(f"User {request.user.id} has no role assigned")
            return False

        if user_role not in required_roles:
            self.log_permission_denied(
                request,
                f"User role '{user_role}' not in required roles {required_roles}",
            )
            return False

        return True


class IsModeratorOrAdmin(BasePermission):
    """
    Permission class for moderator-level access.

    Allows access to users with:
    - is_staff=True (admin)
    - is_superuser=True (superuser)
    - role='moderator' (if using role field)
    """

    message = "Moderator or admin access required."

    def has_permission(self, request: Request, view: View) -> bool:
        """Check if user is moderator or admin."""
        if not request.user or not request.user.is_authenticated:
            self.log_permission_denied(
                request, "User not authenticated for moderator check"
            )
            return False

        # Check admin status
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Check moderator role (if role field exists)
        user_role = getattr(request.user, "role", None)
        if user_role == "moderator":
            return True

        self.log_permission_denied(request, "User is not moderator or admin")
        return False


# =========================================================================
# CUSTOM BUSINESS LOGIC PERMISSIONS
# =========================================================================


class CanManageMovies(BasePermission):
    """
    Custom permission for movie management operations.

    Business logic:
    - Admins can manage all movies
    - Moderators can manage non-premium movies
    - Regular users cannot manage movies
    """

    message = "You do not have permission to manage movies."

    def has_permission(self, request: Request, view: View) -> bool:
        """Check movie management permission."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Admins can manage all movies
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Moderators can manage movies (business rule)
        user_role = getattr(request.user, "role", None)
        if user_role == "moderator":
            return True

        self.log_permission_denied(request, "User cannot manage movies")
        return False

    def has_object_permission(self, request: Request, view: View, obj: Any) -> bool:
        """Check permission for specific movie object."""
        if not self.has_permission(request, view):
            return False

        # Admins can manage any movie
        if request.user.is_staff or request.user.is_superuser:
            return True

        return True


class CanAccessRecommendations(BasePermission):
    """
    Permission for accessing recommendation features.

    Business logic:
    - All authenticated users can view recommendations
    - Only admins can create/modify recommendation algorithms
    """

    message = "You do not have permission to access recommendations."

    def has_permission(self, request: Request, view: View) -> bool:
        """Check recommendation access permission."""
        if not request.user or not request.user.is_authenticated:
            self.log_permission_denied(
                request, "User not authenticated for recommendations"
            )
            return False

        # Read access for all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write access only for admins
        if request.user.is_staff or request.user.is_superuser:
            return True

        self.log_permission_denied(request, "User cannot modify recommendations")
        return False


# =========================================================================
# UTILITY PERMISSION FUNCTIONS
# =========================================================================


def is_admin_user(user) -> bool:
    """
    Utility function to check if user is admin.

    Args:
        user: User instance

    Returns:
        bool: True if user is admin
    """
    if not user or not user.is_authenticated:
        return False

    return user.is_staff or user.is_superuser


def is_owner_or_admin(user, obj) -> bool:
    """
    Utility function to check if user owns object or is admin.

    Args:
        user: User instance
        obj: Object to check ownership

    Returns:
        bool: True if user owns object or is admin
    """
    if not user or not user.is_authenticated:
        return False

    # Admin check
    if user.is_staff or user.is_superuser:
        return True

    # Ownership check
    owner = (
        getattr(obj, "user", None)
        or getattr(obj, "owner", None)
        or getattr(obj, "created_by", None)
    )
    return owner == user


def has_role(user, role: str) -> bool:
    """
    Utility function to check if user has specific role.

    Args:
        user: User instance
        role: Role string to check

    Returns:
        bool: True if user has role
    """
    if not user or not user.is_authenticated:
        return False

    user_role = getattr(user, "role", None)
    return user_role == role


# =========================================================================
# PERMISSION COMBINATIONS
# =========================================================================


class IsAuthenticatedAndAdmin(permissions.IsAuthenticated, IsAdminUser):
    """
    Combination permission requiring both authentication and admin status.
    Useful for critical admin operations.
    """

    pass


class IsAuthenticatedAndOwner(permissions.IsAuthenticated, IsOwnerOrReadOnly):
    """
    Combination permission requiring authentication and ownership.
    Useful for user profile operations.
    """

    pass
