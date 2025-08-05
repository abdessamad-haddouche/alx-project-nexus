"""
Admin management views for Movie Nexus.
Handles admin creation, promotion, revocation, and listing.
"""

import logging

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache

from core.exceptions import (
    PermissionException,
    UserNotFoundException,
    ValidationException,
)

# BaseAPIViewMixin not implemented yet
from core.permissions import IsSuperUserOnly
from core.responses import APIResponse

from ..serializers.admin import (
    AdminCreateSerializer,
    AdminListSerializer,
    AdminPromoteSerializer,
    AdminRevokeSerializer,
    SuperAdminCreateSerializer,
)
from ..services.admin_service import AdminService

User = get_user_model()
logger = logging.getLogger(__name__)


@method_decorator(never_cache, name="dispatch")
class AdminCreateView(APIView):
    """
    Create new admin user.

    **Permissions:** SuperUser only
    **HTTP Methods:** POST
    **Rate Limit:** 10 requests per hour
    """

    permission_classes = [IsAuthenticated, IsSuperUserOnly]
    serializer_class = AdminCreateSerializer

    def get_serializer(self, *args, **kwargs):
        """Get serializer instance with context."""
        kwargs["context"] = self.get_serializer_context()
        return self.serializer_class(*args, **kwargs)

    def get_serializer_context(self):
        """Get serializer context with request."""
        return {"request": self.request}

    @extend_schema(
        operation_id="admin_management_create",
        summary="Create Admin User",
        description=(
            "Create a new admin user account with staff privileges. "
            "Only superusers can create admin accounts. "
            "The new admin will have access to Django admin panel"
            " and elevated permissions."
        ),
        tags=["Admin Management"],
        request=AdminCreateSerializer,
        responses={
            201: {
                "description": "Admin account created successfully",
                "example": {
                    "success": True,
                    "message": "Admin account created successfully",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "data": {
                        "user": {
                            "id": 2,
                            "email": "admin@example.com",
                            "full_name": "Admin User",
                            "role": "admin",
                            "is_staff": True,
                            "date_joined": "2025-01-15T10:30:00Z",
                        }
                    },
                },
            },
            400: {
                "description": "Validation errors",
                "example": {
                    "success": False,
                    "message": "Email already exists",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "errors": {
                        "field_errors": {
                            "email": ["User with this email already exists"]
                        }
                    },
                },
            },
            403: {
                "description": "Permission denied - superuser required",
                "example": {
                    "success": False,
                    "message": "You do not have permission to create admin accounts",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
            500: {"description": "Server error"},
        },
    )
    def post(self, request: Request) -> Response:
        """
        Create new admin user.
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Create admin user
            result = serializer.save()

            logger.info(
                f"Admin user created: {result['user'].email} by {request.user.email}"
            )

            return APIResponse.success(
                data=serializer.data,
                message=_("Admin account created successfully"),
                status_code=status.HTTP_201_CREATED,
            )

        except ValidationException as e:
            logger.warning(f"Admin creation validation failed: {str(e)}")
            return APIResponse.error(
                message=str(e.detail),
                errors=getattr(e, "extra_data", {}),
                status_code=e.status_code,
            )
        except PermissionException as e:
            logger.warning(f"Admin creation permission denied: {str(e)}")
            return APIResponse.error(message=str(e.detail), status_code=e.status_code)
        except Exception as e:
            logger.error(f"Admin creation failed: {str(e)}")
            return APIResponse.error(
                message=_("Failed to create admin account"),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@method_decorator(never_cache, name="dispatch")
class SuperAdminCreateView(APIView):
    """
    Create new superadmin user.

    **Permissions:** SuperUser only
    **HTTP Methods:** POST
    **Rate Limit:** 5 requests per hour
    """

    permission_classes = [IsAuthenticated, IsSuperUserOnly]
    serializer_class = SuperAdminCreateSerializer

    def get_serializer(self, *args, **kwargs):
        """Get serializer instance with context."""
        kwargs["context"] = self.get_serializer_context()
        return self.serializer_class(*args, **kwargs)

    def get_serializer_context(self):
        """Get serializer context with request."""
        return {"request": self.request}

    @extend_schema(
        operation_id="admin_management_create_superadmin",
        summary="Create SuperAdmin User",
        description=(
            "Create a new superadmin user account with full system privileges. "
            "Only existing superusers can create other superadmin accounts. "
            "SuperAdmins have unrestricted access to all system functions and"
            " can manage other admins. "
        ),
        tags=["Admin Management"],
        request=SuperAdminCreateSerializer,
        responses={
            201: {
                "description": "SuperAdmin account created successfully",
                "example": {
                    "success": True,
                    "message": "SuperAdmin account created successfully",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "data": {
                        "user": {
                            "id": 3,
                            "email": "superadmin@example.com",
                            "full_name": "Super Admin",
                            "role": "superadmin",
                            "is_staff": True,
                            "is_superuser": True,
                            "date_joined": "2025-01-15T10:30:00Z",
                        }
                    },
                },
            },
            400: {"description": "Validation errors"},
            403: {"description": "Permission denied - superuser required"},
            500: {"description": "Server error"},
        },
    )
    def post(self, request: Request) -> Response:
        """
        Create new superadmin user.
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Create superadmin user
            result = serializer.save()

            logger.info(
                f"SuperAdmin user created: {result['user'].email} "
                f"by {request.user.email}"
            )

            return APIResponse.success(
                data=serializer.data,
                message=_("SuperAdmin account created successfully"),
                status_code=status.HTTP_201_CREATED,
            )

        except ValidationException as e:
            logger.warning(f"SuperAdmin creation validation failed: {str(e)}")
            return APIResponse.error(
                message=str(e.detail),
                errors=getattr(e, "extra_data", {}),
                status_code=e.status_code,
            )
        except PermissionException as e:
            logger.warning(f"SuperAdmin creation permission denied: {str(e)}")
            return APIResponse.error(message=str(e.detail), status_code=e.status_code)
        except Exception as e:
            logger.error(f"SuperAdmin creation failed: {str(e)}")
            return APIResponse.error(
                message=_("Failed to create SuperAdmin account"),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@method_decorator(never_cache, name="dispatch")
class AdminPromoteView(APIView):
    """
    Promote existing user to admin role.

    **Permissions:** SuperUser only
    **HTTP Methods:** POST
    """

    permission_classes = [IsAuthenticated, IsSuperUserOnly]
    serializer_class = AdminPromoteSerializer

    def get_serializer(self, *args, **kwargs):
        """Get serializer instance with context."""
        kwargs["context"] = self.get_serializer_context()
        return self.serializer_class(*args, **kwargs)

    def get_serializer_context(self):
        """Get serializer context with request."""
        return {"request": self.request}

    @extend_schema(
        operation_id="admin_management_promote_user",
        summary="Promote User to Admin",
        description=(
            "Promote an existing regular user to admin role. "
            "Only superusers can promote users to admin status. "
            "The target user must exist, be active, and not already "
            "have admin privileges. "
            "This grants the user access to admin functions and Django admin panel."
        ),
        tags=["Admin Management"],
        request=AdminPromoteSerializer,
        responses={
            200: {
                "description": "User promoted successfully",
                "example": {
                    "success": True,
                    "message": "User promoted successfully",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "data": {
                        "user": {
                            "id": 5,
                            "email": "user@example.com",
                            "full_name": "John Doe",
                            "role": "admin",
                            "is_staff": True,
                            "promoted_at": "2025-01-15T10:30:00Z",
                        }
                    },
                },
            },
            400: {
                "description": "Validation errors",
                "example": {
                    "success": False,
                    "message": "User not found or already has admin privileges",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
            403: {"description": "Permission denied - superuser required"},
            500: {"description": "Server error"},
        },
    )
    def post(self, request: Request) -> Response:
        """
        Promote user to admin role.
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Promote user
            result = serializer.save()

            user = result["user"]
            new_role = result["new_role"]

            logger.info(
                f"User promoted: {user.email} to {new_role} by {request.user.email}"
            )

            return APIResponse.success(
                data=serializer.data,
                message=_("User promoted successfully"),
                status_code=status.HTTP_200_OK,
            )

        except ValidationException as e:
            logger.warning(f"User promotion validation failed: {str(e)}")
            return APIResponse.error(
                message=str(e.detail),
                errors=getattr(e, "extra_data", {}),
                status_code=e.status_code,
            )
        except PermissionException as e:
            logger.warning(f"User promotion permission denied: {str(e)}")
            return APIResponse.error(message=str(e.detail), status_code=e.status_code)
        except Exception as e:
            logger.error(f"User promotion failed: {str(e)}")
            return APIResponse.error(
                message=_("Failed to promote user"),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@method_decorator(never_cache, name="dispatch")
class AdminRevokeView(APIView):
    """
    Revoke admin privileges from user.

    **Permissions:** SuperUser only
    **HTTP Methods:** DELETE
    """

    permission_classes = [IsAuthenticated, IsSuperUserOnly]
    serializer_class = AdminRevokeSerializer

    def get_serializer(self, *args, **kwargs):
        """Get serializer instance with context."""
        kwargs["context"] = self.get_serializer_context()
        return self.serializer_class(*args, **kwargs)

    def get_serializer_context(self):
        """Get serializer context with request."""
        return {"request": self.request}

    @extend_schema(
        operation_id="admin_management_revoke_privileges",
        summary="Revoke Admin Privileges",
        description=(
            "Revoke admin privileges from a user, converting them back to "
            "regular user status. "
            "Only superusers can revoke admin privileges. "
            "Cannot revoke privileges from other superusers - only regular admins. "
            "This removes access to admin functions and Django admin panel."
        ),
        tags=["Admin Management"],
        parameters=[
            OpenApiParameter(
                name="user_id",
                type=int,
                location=OpenApiParameter.PATH,
                description="ID of the admin user to revoke privileges from",
                required=True,
            ),
        ],
        responses={
            200: {
                "description": "Admin privileges revoked successfully",
                "example": {
                    "success": True,
                    "message": "Admin privileges revoked successfully",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "data": {
                        "user": {
                            "id": 5,
                            "email": "user@example.com",
                            "full_name": "John Doe",
                            "role": "user",
                            "is_staff": False,
                            "revoked_at": "2025-01-15T10:30:00Z",
                        }
                    },
                },
            },
            400: {
                "description": "Validation errors",
                "example": {
                    "success": False,
                    "message": "Cannot revoke privileges from superuser",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
            403: {"description": "Permission denied - superuser required"},
            404: {
                "description": "User not found",
                "example": {
                    "success": False,
                    "message": "User not found",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
            500: {"description": "Server error"},
        },
    )
    def delete(self, request: Request, user_id: int) -> Response:
        """
        Revoke admin privileges from user.
        """
        try:
            # Get user to revoke
            try:
                user_to_revoke = User.objects.get(id=user_id, is_active=True)
            except User.DoesNotExist:
                raise UserNotFoundException(_("User not found"))

            # Validate revocation using serializer
            serializer = self.get_serializer(data={})
            serializer.user_to_revoke = user_to_revoke  # Pass user to serializer
            serializer.is_valid(raise_exception=True)

            # Revoke admin privileges
            serializer.save()

            logger.info(
                f"Admin privileges revoked: {user_to_revoke.email} "
                f"by {request.user.email}"
            )

            return APIResponse.success(
                data=serializer.data,
                message=_("Admin privileges revoked successfully"),
                status_code=status.HTTP_200_OK,
            )

        except UserNotFoundException as e:
            logger.warning(f"User not found for revocation: {user_id}")
            return APIResponse.error(message=str(e.detail), status_code=e.status_code)
        except PermissionException as e:
            logger.warning(f"Permission denied for admin revocation: {str(e)}")
            return APIResponse.error(message=str(e.detail), status_code=e.status_code)
        except ValidationException as e:
            logger.warning(f"Admin revocation validation failed: {str(e)}")
            return APIResponse.error(
                message=str(e.detail),
                errors=getattr(e, "extra_data", {}),
                status_code=e.status_code,
            )
        except Exception as e:
            logger.error(f"Admin revocation failed: {str(e)}")
            return APIResponse.error(
                message=_("Failed to revoke admin privileges"),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@method_decorator(never_cache, name="dispatch")
class AdminListView(APIView):
    """
    List all admin users.

    **Permissions:** SuperUser only
    **HTTP Methods:** GET
    """

    permission_classes = [IsAuthenticated, IsSuperUserOnly]
    serializer_class = AdminListSerializer

    def get_serializer(self, *args, **kwargs):
        """Get serializer instance with context."""
        kwargs["context"] = self.get_serializer_context()
        return self.serializer_class(*args, **kwargs)

    def get_serializer_context(self):
        """Get serializer context with request."""
        return {"request": self.request}

    @extend_schema(
        operation_id="admin_management_list",
        summary="List Admin Users",
        description=(
            "Get a comprehensive list of all admin users in the system. "
            "Only superusers can view the admin user list. "
            "Includes filtering options and system statistics. "
            "Useful for admin management and system oversight."
        ),
        tags=["Admin Management"],
        parameters=[
            OpenApiParameter(
                name="include_superusers",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Include superusers in the returned list",
                default=True,
            ),
            OpenApiParameter(
                name="role",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter results by specific admin role",
                enum=["admin", "moderator", "superadmin"],
            ),
        ],
        responses={
            200: {
                "description": "Admin users retrieved successfully",
                "example": {
                    "success": True,
                    "message": "Admin users retrieved successfully",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "data": {
                        "users": [
                            {
                                "id": 1,
                                "email": "admin@example.com",
                                "full_name": "Admin User",
                                "role": "admin",
                                "is_staff": True,
                                "is_superuser": False,
                                "date_joined": "2025-01-10T10:30:00Z",
                                "last_login": "2025-01-15T09:00:00Z",
                            }
                        ],
                        "statistics": {
                            "total_staff": 5,
                            "total_superusers": 2,
                            "total_regular_admins": 3,
                            "filtered_count": 5,
                        },
                    },
                },
            },
            403: {"description": "Permission denied - superuser required"},
            500: {"description": "Server error"},
        },
    )
    def get(self, request: Request) -> Response:
        """
        Get list of all admin users.
        """
        try:
            # Get query parameters
            include_superusers = (
                request.query_params.get("include_superusers", "true").lower() == "true"
            )
            role_filter = request.query_params.get("role")

            # Get admin users
            admin_users = AdminService.get_admin_users(
                include_superusers=include_superusers
            )

            # Apply role filter if specified
            if role_filter:
                admin_users = [user for user in admin_users if user.role == role_filter]

            # Serialize the response
            serializer = self.get_serializer()
            data = serializer.to_representation(admin_users)

            # Add basic statistics (since get_admin_statistics was removed)
            total_staff = User.objects.filter(is_staff=True, is_active=True).count()
            total_superusers = User.objects.filter(
                is_superuser=True, is_active=True
            ).count()
            total_regular_admins = User.objects.filter(
                is_staff=True, is_superuser=False, is_active=True
            ).count()

            statistics = {
                "total_staff": total_staff,
                "total_superusers": total_superusers,
                "total_regular_admins": total_regular_admins,
                "filtered_count": len(admin_users),
            }

            data["statistics"] = statistics

            logger.info(f"Admin list requested by {request.user.email}")

            return APIResponse.success(
                data=data,
                message=_("Admin users retrieved successfully"),
                status_code=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Failed to list admin users: {str(e)}")
            return APIResponse.error(
                message=_("Failed to retrieve admin users"),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
