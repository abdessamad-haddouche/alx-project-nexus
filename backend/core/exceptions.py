"""
Custom exception classes for consistent error handling across the application.
"""
from typing import Any, Dict, Optional

from rest_framework import status
from rest_framework.exceptions import APIException

from django.utils.translation import gettext_lazy as _


class BaseAPIException(APIException):
    """Base exception class for all custom API exceptions."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _("An unexpected error occurred.")
    default_code = "internal_error"

    def __init__(
        self,
        detail: Optional[str] = None,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the exception with optional overrides

        Args:
            detail: Custom error message
            code: Custom error code
            status_code: Custom HTTP status code
            extra_data: Additional data to include in error response
        """
        if status_code:
            self.status_code = status_code

        if detail is None:
            detail = self.default_detail

        if code is None:
            code = self.default_code

        self.extra_data = extra_data or {}

        super().__init__(detail, code)

    def get_full_details(self) -> Dict[str, Any]:
        """
        Return full error details including extra data.

        Returns:
            Dictionary containing error details
        """
        details = {
            "code": self.get_codes(),
            "message": str(self.detail),
            "status_code": self.status_code,
        }

        if self.extra_data:
            details["extra"] = self.extra_data

        return details

    def __str__(self) -> str:
        """Return a readable string representation of the exception."""
        base_msg = f"[{self.status_code}] {self.default_code}: {self.detail}"
        if self.extra_data:
            return f"{base_msg} | Extra data: {self.extra_data}"
        return base_msg


# =============================================================================
# CLIENT ERROR EXCEPTIONS (4xx)
# =============================================================================


class ClientErrorException(BaseAPIException):
    """Base class for all client error exceptions (4xx status codes)."""

    pass


# 400 Bad Request
class BadRequestException(ClientErrorException):
    """Generic bad request exception for malformed requests."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _("The request could not be understood by the server.")
    default_code = "bad_request"


class ValidationException(ClientErrorException):
    """Raised when data validation fails."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _("The provided data failed validation.")
    default_code = "validation_error"

    def __init__(self, field_errors: Optional[Dict[str, str]] = None, **kwargs):
        """
        Initialize with optional field-specific errors.

        Args:
            field_errors: Dictionary of field names to error messages
        """
        if field_errors:
            kwargs["extra_data"] = {"field_errors": field_errors}
        super().__init__(**kwargs)


class InvalidInputException(ClientErrorException):
    """Raised when input data format or values are invalid."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _("Invalid input data provided.")
    default_code = "invalid_input"


# 401 Unauthorized
class AuthenticationException(ClientErrorException):
    """Base class for authentication-related exceptions."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _("Authentication credentials were not provided or are invalid.")
    default_code = "authentication_failed"


class UnauthorizedException(AuthenticationException):
    """Raised when user is not authenticated."""

    default_detail = _("Authentication credentials are required.")
    default_code = "not_authenticated"


class InvalidCredentialsException(AuthenticationException):
    """Raised when provided credentials are invalid."""

    default_detail = _("Invalid email or password.")
    default_code = "invalid_credentials"


class TokenExpiredException(AuthenticationException):
    """Raised when authentication token has expired."""

    default_detail = _("Authentication token has expired.")
    default_code = "token_expired"


class TokenInvalidException(AuthenticationException):
    """Raised when authentication token is malformed or invalid."""

    default_detail = _("Authentication token is invalid.")
    default_code = "token_invalid"


# 403 Forbidden
class PermissionException(ClientErrorException):
    """Base class for permission-related exceptions."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _("You do not have permission to perform this action.")
    default_code = "permission_denied"


class ForbiddenException(PermissionException):
    """Generic permission denied exception."""

    pass


class InsufficientPermissionsException(PermissionException):
    """Raised when user has insufficient permissions for the action."""

    default_detail = _("Your account lacks the required permissions.")
    default_code = "insufficient_permissions"


class EmailNotVerifiedException(PermissionException):
    """Raised when action requires email verification."""

    default_detail = _("Email verification is required to perform this action.")
    default_code = "email_verification_required"


class AccountSuspendedException(PermissionException):
    """Raised when user account is suspended."""

    default_detail = _("Your account has been suspended.")
    default_code = "account_suspended"


# 404 Not Found
class ResourceException(ClientErrorException):
    """Base class for resource-related exceptions."""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _("The requested resource was not found.")
    default_code = "resource_not_found"


class NotFoundException(ResourceException):
    """Generic resource not found exception."""

    pass


class UserNotFoundException(ResourceException):
    """Raised when a user cannot be found."""

    default_detail = _("User not found.")
    default_code = "user_not_found"


class MovieNotFoundException(ResourceException):
    """Raised when a movie cannot be found."""

    default_detail = _("Movie not found.")
    default_code = "movie_not_found"


# 429 Too Many Requests
class RateLimitException(ClientErrorException):
    """Raised when API rate limit is exceeded."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = _("API rate limit exceeded. Please try again later.")
    default_code = "rate_limit_exceeded"

    def __init__(self, retry_after: Optional[int] = None, **kwargs):
        """
        Initialize with optional retry-after information.

        Args:
            retry_after: Seconds until rate limit resets
        """
        if retry_after:
            kwargs["extra_data"] = {"retry_after": retry_after}
        super().__init__(**kwargs)


# =============================================================================
# SERVER ERROR EXCEPTIONS (5xx)
# =============================================================================


class ServerErrorException(BaseAPIException):
    """Base class for all server error exceptions (5xx status codes)."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _("An internal server error occurred.")
    default_code = "internal_server_error"


class ServiceUnavailableException(ServerErrorException):
    """Raised when service is temporarily unavailable."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = _("Service is temporarily unavailable.")
    default_code = "service_unavailable"


class ExternalServiceException(ServerErrorException):
    """Base class for external service errors."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = _("External service error occurred.")
    default_code = "external_service_error"


class TMDbAPIException(ExternalServiceException):
    """Raised when TMDb API calls fail."""

    default_detail = _("TMDb service is currently unavailable.")
    default_code = "tmdb_service_error"


class DatabaseException(ServerErrorException):
    """Raised when database operations fail."""

    default_detail = _("Database operation failed.")
    default_code = "database_error"
