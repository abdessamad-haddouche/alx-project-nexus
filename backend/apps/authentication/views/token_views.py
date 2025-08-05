"""
JWT token management views for Movie Nexus.
Handles JWT token refresh and verification for secure API access.
"""

import logging

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken, UntypedToken

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from core.exceptions import TokenInvalidException
from core.responses import APIResponse

from ..serializers import TokenRefreshSerializer, TokenVerifySerializer
from ..services import refresh_token
from ..services.session_service import SessionService

User = get_user_model()
logger = logging.getLogger(__name__)


class TokenRefreshView(APIView):
    """
    JWT token refresh endpoint.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    serializer_class = TokenRefreshSerializer

    @extend_schema(
        operation_id="auth_token_refresh",
        summary="Refresh JWT Token",
        description=(
            "Refresh an expired access token using a valid refresh token. "
            "Returns a new access token and optionally a new refresh token."
        ),
        tags=["Authentication"],
        request=TokenRefreshSerializer,
        responses={
            200: {
                "description": "Token refreshed successfully",
                "example": {
                    "success": True,
                    "message": "Token refreshed successfully",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "data": {
                        "tokens": {
                            "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    },
                },
            },
            400: {
                "description": "Validation errors",
                "example": {
                    "success": False,
                    "message": "Invalid refresh token data",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "errors": {
                        "field_errors": {"refresh": ["Refresh token is required"]}
                    },
                },
            },
            401: {
                "description": "Invalid or expired refresh token",
                "example": {
                    "success": False,
                    "message": "Invalid or expired refresh token",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
            429: {"description": "Rate limit exceeded"},
        },
        examples=[
            OpenApiExample(
                "Token Refresh Request",
                summary="Refresh expired access token",
                description="Use refresh token to get new access token",
                value={
                    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9."
                    "eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTY0..."
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        """Refresh JWT access token using refresh token."""
        try:
            # Validate input using serializer
            serializer = self.serializer_class(data=request.data)

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message=_("Invalid refresh token data"),
                    field_errors=serializer.errors,
                )

            # Get validated refresh token
            refresh_token_string = serializer.validated_data["refresh"]

            try:
                # Refresh token using service
                tokens = refresh_token(refresh_token_string)

                # Get user information from token for logging
                refresh = RefreshToken(refresh_token_string)
                user_id = refresh.payload.get("user_id")

                try:
                    user = User.objects.get(id=user_id, is_active=True)

                    # Update session activity if session_id is in token
                    session_id = refresh.payload.get("session_id")
                    if session_id:
                        SessionService.update_session_activity(session_id)

                    logger.info(f"Token refreshed successfully for user: {user.email}")

                    return APIResponse.token_refreshed(
                        tokens=tokens, message=_("Token refreshed successfully")
                    )

                except User.DoesNotExist:
                    logger.warning(
                        f"Token refresh attempted for non-existent user ID: {user_id}"
                    )
                    return APIResponse.unauthorized(
                        message=_("User associated with token no longer exists")
                    )

            except TokenInvalidException as e:
                logger.warning(f"Invalid token refresh attempt: {str(e)}")
                return APIResponse.unauthorized(message=str(e.detail))

            except (InvalidToken, TokenError) as e:
                logger.warning(f"JWT token refresh failed: {str(e)}")
                return APIResponse.unauthorized(
                    message=_("Invalid or expired refresh token")
                )

        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            return APIResponse.server_error(
                message=_("Token refresh failed. Please try again.")
            )


class TokenVerifyView(APIView):
    """
    JWT token verification endpoint.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, UserRateThrottle]
    serializer_class = TokenVerifySerializer

    @extend_schema(
        operation_id="auth_token_verify",
        summary="Verify JWT Token",
        description=(
            "Verify the validity of an access token and return token information. "
            "Checks token signature, expiration, and user existence. "
            "Returns detailed token claims and user information if valid."
        ),
        tags=["Authentication"],
        request=TokenVerifySerializer,
        responses={
            200: {
                "description": "Token is valid",
                "example": {
                    "success": True,
                    "message": "Token is valid",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "data": {
                        "valid": True,
                        "token_claims": {
                            "user_id": "1",
                            "email": "user@example.com",
                            "email_verified": True,
                            "user_role": "user",
                            "full_name": "John Doe",
                            "session_id": "abc123",
                            "token_type": "access",
                            "issued_at": 1642678800,
                            "expires_at": 1642682400,
                        },
                        "user": {
                            "id": 1,
                            "email": "user@example.com",
                            "full_name": "John Doe",
                            "is_active": True,
                            "is_email_verified": True,
                        },
                    },
                },
            },
            400: {
                "description": "Validation errors",
                "example": {
                    "success": False,
                    "message": "Invalid token data",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "errors": {"field_errors": {"token": ["Token is required"]}},
                },
            },
            401: {
                "description": "Invalid or expired token",
                "example": {
                    "success": False,
                    "message": "Invalid or expired token",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
            429: {"description": "Rate limit exceeded"},
        },
        examples=[
            OpenApiExample(
                "Token Verification Request",
                summary="Verify access token validity",
                description="Check if access token is still valid and get user info",
                value={
                    "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9."
                    "eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNjQ..."
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        """Verify JWT token validity."""
        try:
            # Validate input using serializer
            serializer = self.serializer_class(data=request.data)

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message=_("Invalid token data"),
                    field_errors=serializer.errors,
                )

            # Get validated token
            token_string = serializer.validated_data["token"]

            try:
                # Verify token using JWT library
                UntypedToken(token_string)

                # If we get here, token is valid - now extract user info
                from rest_framework_simplejwt.tokens import AccessToken

                try:
                    access_token = AccessToken(token_string)
                    user_id = access_token.payload.get("user_id")

                    # Verify user still exists and is active
                    try:
                        user = User.objects.get(id=user_id, is_active=True)

                        # Extract token claims for response
                        token_claims = {
                            "user_id": str(user.id),
                            "email": access_token.payload.get("email", user.email),
                            "email_verified": access_token.payload.get(
                                "email_verified", user.is_email_verified
                            ),
                            "user_role": access_token.payload.get(
                                "user_role", user.role
                            ),
                            "full_name": access_token.payload.get(
                                "full_name", user.full_name
                            ),
                            "session_id": access_token.payload.get("session_id"),
                            "token_type": access_token.payload.get(
                                "token_type", "access"
                            ),
                            "issued_at": access_token.payload.get("iat"),
                            "expires_at": access_token.payload.get("exp"),
                        }

                        # Update session activity if session_id is present
                        session_id = access_token.payload.get("session_id")
                        if session_id:
                            SessionService.update_session_activity(session_id)

                        logger.info(
                            f"Token verified successfully for user: {user.email}"
                        )

                        return APIResponse.success(
                            message=_("Token is valid"),
                            data={
                                "valid": True,
                                "token_claims": token_claims,
                                "user": {
                                    "id": user.id,
                                    "email": user.email,
                                    "full_name": user.full_name,
                                    "is_active": user.is_active,
                                    "is_email_verified": user.is_email_verified,
                                },
                            },
                        )

                    except User.DoesNotExist:
                        logger.warning(
                            f"Token verification failed - user not found: {user_id}"
                        )
                        return APIResponse.unauthorized(
                            message=_("User associated with token no longer exists")
                        )

                except (InvalidToken, TokenError) as e:
                    logger.warning(f"Access token parsing failed: {str(e)}")
                    return APIResponse.unauthorized(
                        message=_("Invalid access token format")
                    )

            except (InvalidToken, TokenError) as e:
                logger.warning(f"Token verification failed: {str(e)}")
                return APIResponse.unauthorized(message=_("Invalid or expired token"))

        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            return APIResponse.server_error(
                message=_("Token verification failed. Please try again.")
            )
