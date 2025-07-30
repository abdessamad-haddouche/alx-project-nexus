"""
API response handlers for consistent response formatting.
Provides standardized success and error responses across all API endpoints.
"""

from typing import Any, Dict, Optional

from rest_framework import status
from rest_framework.response import Response

from django.utils import timezone


class APIResponse:
    """
    API response handler with consistent formatting.

    Usage:
        # Success responses
        return APIResponse.success("User created", user_data)
        return APIResponse.success("Login successful", tokens, status.HTTP_201_CREATED)

        # Error responses
        return APIResponse.error("Invalid credentials", status.HTTP_401_UNAUTHORIZED)
        return APIResponse.validation_error("Form errors", {"email": ["Required"]})
    """

    @staticmethod
    def _base_response(
        success: bool,
        message: str,
        data: Any = None,
        errors: Any = None,
        status_code: int = status.HTTP_200_OK,
        extra_fields: Optional[Dict] = None,
    ) -> Response:
        """
        Base response method for consistent formatting.

        Args:
            success: Whether the operation was successful
            message: Human-readable message
            data: Response data (for success)
            errors: Error details (for failures)
            status_code: HTTP status code
            extra_fields: Additional fields to include

        Returns:
            DRF Response object
        """
        response_data = {
            "success": success,
            "message": str(message),
            "timestamp": timezone.now().isoformat(),
        }

        # Add data for successful responses
        if success and data is not None:
            response_data["data"] = data

        # Add errors for failed responses
        if not success and errors is not None:
            response_data["errors"] = errors

        # Add any extra fields
        if extra_fields:
            response_data.update(extra_fields)

        return Response(response_data, status=status_code)

    # ================================================================
    # SUCCESS RESPONSES
    # ================================================================

    @staticmethod
    def success(
        message: str = "Operation successful",
        data: Any = None,
        status_code: int = status.HTTP_200_OK,
        **extra_fields,
    ) -> Response:
        """
        Standard success response.

        Args:
            message: Success message
            data: Response data
            status_code: HTTP status code (default: 200)
            **extra_fields: Additional fields

        Returns:
            Success Response
        """
        return APIResponse._base_response(
            success=True,
            message=message,
            data=data,
            status_code=status_code,
            extra_fields=extra_fields,
        )

    @staticmethod
    def created(
        message: str = "Resource created successfully", data: Any = None, **extra_fields
    ) -> Response:
        """
        Resource creation success response (201).

        Args:
            message: Creation message
            data: Created resource data
            **extra_fields: Additional fields

        Returns:
            201 Created Response
        """
        return APIResponse.success(
            message=message,
            data=data,
            status_code=status.HTTP_201_CREATED,
            **extra_fields,
        )

    @staticmethod
    def updated(
        message: str = "Resource updated successfully", data: Any = None, **extra_fields
    ) -> Response:
        """
        Resource update success response.

        Args:
            message: Update message
            data: Updated resource data
            **extra_fields: Additional fields

        Returns:
            Success Response
        """
        return APIResponse.success(message=message, data=data, **extra_fields)

    @staticmethod
    def deleted(
        message: str = "Resource deleted successfully", **extra_fields
    ) -> Response:
        """
        Resource deletion success response (204).

        Args:
            message: Deletion message
            **extra_fields: Additional fields

        Returns:
            204 No Content Response
        """
        return APIResponse.success(
            message=message, status_code=status.HTTP_204_NO_CONTENT, **extra_fields
        )

    # ================================================================
    # ERROR RESPONSES
    # ================================================================

    @staticmethod
    def error(
        message: str = "An error occurred",
        errors: Any = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        **extra_fields,
    ) -> Response:
        """
        Standard error response.

        Args:
            message: Error message
            errors: Error details
            status_code: HTTP status code (default: 400)
            **extra_fields: Additional fields

        Returns:
            Error Response
        """
        return APIResponse._base_response(
            success=False,
            message=message,
            errors=errors,
            status_code=status_code,
            extra_fields=extra_fields,
        )

    @staticmethod
    def validation_error(
        message: str = "Validation failed",
        field_errors: Optional[Dict] = None,
        **extra_fields,
    ) -> Response:
        """
        Validation error response (400).

        Args:
            message: Validation error message
            field_errors: Field-specific validation errors
            **extra_fields: Additional fields

        Returns:
            400 Bad Request Response
        """
        errors = {}
        if field_errors:
            errors["field_errors"] = field_errors

        return APIResponse.error(
            message=message,
            errors=errors,
            status_code=status.HTTP_400_BAD_REQUEST,
            **extra_fields,
        )

    @staticmethod
    def unauthorized(
        message: str = "Authentication credentials were not provided", **extra_fields
    ) -> Response:
        """
        Unauthorized error response (401).

        Args:
            message: Authentication error message
            **extra_fields: Additional fields

        Returns:
            401 Unauthorized Response
        """
        return APIResponse.error(
            message=message, status_code=status.HTTP_401_UNAUTHORIZED, **extra_fields
        )

    @staticmethod
    def forbidden(
        message: str = "You do not have permission to perform this action",
        **extra_fields,
    ) -> Response:
        """
        Forbidden error response (403).

        Args:
            message: Permission error message
            **extra_fields: Additional fields

        Returns:
            403 Forbidden Response
        """
        return APIResponse.error(
            message=message, status_code=status.HTTP_403_FORBIDDEN, **extra_fields
        )

    @staticmethod
    def not_found(message: str = "Resource not found", **extra_fields) -> Response:
        """
        Not found error response (404).

        Args:
            message: Not found message
            **extra_fields: Additional fields

        Returns:
            404 Not Found Response
        """
        return APIResponse.error(
            message=message, status_code=status.HTTP_404_NOT_FOUND, **extra_fields
        )

    @staticmethod
    def server_error(
        message: str = "Internal server error occurred", **extra_fields
    ) -> Response:
        """
        Server error response (500).

        Args:
            message: Server error message
            **extra_fields: Additional fields

        Returns:
            500 Internal Server Error Response
        """
        return APIResponse.error(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            **extra_fields,
        )

    # ================================================================
    # AUTHENTICATION-SPECIFIC RESPONSES
    # ================================================================

    @staticmethod
    def login_success(
        user_data: Dict, tokens: Dict, message: str = "Login successful"
    ) -> Response:
        """
        Login success response with user data and tokens.

        Args:
            user_data: User information
            tokens: JWT tokens
            message: Login success message

        Returns:
            Login Success Response
        """
        return APIResponse.success(
            message=message, data={"user": user_data, "tokens": tokens}
        )

    @staticmethod
    def registration_success(
        user_data: Dict,
        message: str = "Registration successful. Please check your"
        " email for verification.",
    ) -> Response:
        """
        Registration success response.

        Args:
            user_data: New user information
            message: Registration message

        Returns:
            Registration Success Response
        """
        return APIResponse.created(message=message, data={"user": user_data})

    @staticmethod
    def logout_success(message: str = "Logout successful") -> Response:
        """
        Logout success response.

        Args:
            message: Logout message

        Returns:
            Logout Success Response
        """
        return APIResponse.success(message=message)

    @staticmethod
    def token_refreshed(
        tokens: Dict, message: str = "Token refreshed successfully"
    ) -> Response:
        """
        Token refresh success response.

        Args:
            tokens: New JWT tokens
            message: Token refresh message

        Returns:
            Token Refresh Success Response
        """
        return APIResponse.success(message=message, data={"tokens": tokens})

    @staticmethod
    def email_verified(
        user_data: Dict, message: str = "Email verified successfully"
    ) -> Response:
        """
        Email verification success response.

        Args:
            user_data: User information
            message: Verification message

        Returns:
            Email Verification Success Response
        """
        return APIResponse.success(message=message, data={"user": user_data})
