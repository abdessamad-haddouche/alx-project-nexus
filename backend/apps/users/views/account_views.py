"""
User account management views for Movie Nexus.
Handles password changes and account-related operations.
"""

import logging

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from django.utils.translation import gettext_lazy as _

from core.exceptions import AuthenticationException, ValidationException
from core.responses import APIResponse

from ..serializers import PasswordChangeSerializer

logger = logging.getLogger(__name__)


class PasswordChangeView(APIView):
    """
    Password change endpoint for authenticated users.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    serializer_class = PasswordChangeSerializer

    @extend_schema(
        operation_id="user_password_change",
        summary="Change Password",
        description=(
            "Change the authenticated user's password. "
            "Requires current password verification."
        ),
        tags=["User Management"],
        request=PasswordChangeSerializer,
        responses={
            200: {
                "description": "Password changed successfully",
                "example": {
                    "success": True,
                    "message": "Password changed successfully",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
            400: {
                "description": "Validation errors",
                "example": {
                    "success": False,
                    "message": "Password change data is invalid",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "errors": {
                        "field_errors": {
                            "current_password": ["Current password is incorrect"],
                            "new_password": ["Password too weak"],
                            "new_password_confirm": [
                                "Password confirmation does not match"
                            ],
                        }
                    },
                },
            },
            401: {
                "description": "Authentication required or current password incorrect",
                "example": {
                    "success": False,
                    "message": "Current password is incorrect",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
            429: {"description": "Rate limit exceeded"},
        },
        examples=[
            OpenApiExample(
                "Password Change Request",
                summary="Change user password",
                description=(
                    "Standard password change with current password verification"
                ),
                value={
                    "current_password": "oldPassword123!",
                    "new_password": "newSecurePassword456!",
                    "new_password_confirm": "newSecurePassword456!",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        """Handle password change with serializer validation."""
        try:
            # Initialize serializer with user context
            serializer = self.serializer_class(
                data=request.data, context={"user": request.user, "request": request}
            )

            # Validate input data
            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message=_("Password change data is invalid"),
                    field_errors=serializer.errors,
                )

            # Change password using serializer
            try:
                serializer.save()

                logger.info(
                    f"Password changed successfully for user: {request.user.email}"
                )

                return APIResponse.success(message=_("Password changed successfully"))

            except AuthenticationException as e:
                logger.warning(
                    f"Invalid current password attempt for user: {request.user.email}"
                )
                return APIResponse.unauthorized(message=str(e.detail))

            except ValidationException as e:
                return APIResponse.validation_error(
                    message=str(e.detail),
                    field_errors=getattr(e, "extra_data", {}).get("field_errors"),
                )

        except Exception as e:
            logger.error(f"Password change error for {request.user.email}: {str(e)}")
            return APIResponse.server_error(message=_("Failed to change password"))
