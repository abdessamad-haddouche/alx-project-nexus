"""
Admin management views for Movie Nexus.
Handles admin creation, promotion, revocation, and listing.
"""

import logging

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

    def post(self, request: Request) -> Response:
        """
        Create new admin user.

        **Request Body:**
        ```json
        {
            "email": "admin@example.com",
            "password": "StrongPassword123!",
            "password_confirm": "StrongPassword123!",
            "first_name": "Admin",
            "last_name": "User",
            "role": "admin",
            "phone_number": "+1234567890",
            "date_of_birth": "1990-01-01"
        }
        ```
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

    def post(self, request: Request) -> Response:
        """
        Create new superadmin user.

        **Request Body:**
        ```json
        {
            "email": "superadmin@example.com",
            "password": "VeryStrongPassword123!",
            "password_confirm": "VeryStrongPassword123!",
            "first_name": "Super",
            "last_name": "Admin",
            "phone_number": "+1234567890"
        }
        ```
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

    def post(self, request: Request) -> Response:
        """
        Promote user to admin role.

        **Request Body:**
        ```json
        {
            "user_id": 123,
            "role": "admin"
        }
        ```
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

    def delete(self, request: Request, user_id: int) -> Response:
        """
        Revoke admin privileges from user.

        **URL Parameters:**
        - `user_id`: ID of user to revoke admin privileges from
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

    def get(self, request: Request) -> Response:
        """
        Get list of all admin users.

        **Query Parameters:**
        - `include_superusers`: Include superusers in list (default: true)
        - `role`: Filter by role ("admin", "moderator", "superadmin")
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
