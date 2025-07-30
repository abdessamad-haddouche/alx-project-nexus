"""
JWT token management views for Movie Nexus.
Handles JWT token refresh and verification for secure API access.
"""

import logging

from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken, UntypedToken

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from core.exceptions import TokenInvalidException
from core.responses import APIResponse

from ..services import refresh_token
from ..services.session_service import SessionService

User = get_user_model()
logger = logging.getLogger(__name__)


class TokenRefreshView(APIView):
    """
    JWT token refresh endpoint.

    POST /api/v1/auth/token/refresh/
    {
        "refresh": "refresh_token_here"
    }
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request):
        """Refresh JWT access token using refresh token."""
        try:
            # Get refresh token from request
            refresh_token_string = request.data.get("refresh")

            if not refresh_token_string:
                return APIResponse.validation_error(
                    message=_("Refresh token is required"),
                    field_errors={"refresh": _("Refresh token is required")},
                )

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

    POST /api/v1/auth/token/verify/
    {
        "token": "access_token_here"
    }
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, UserRateThrottle]

    def post(self, request):
        """Verify JWT token validity."""
        try:
            # Get token from request
            token_string = request.data.get("token")

            if not token_string:
                return APIResponse.validation_error(
                    message=_("Token is required"),
                    field_errors={"token": _("Token is required")},
                )

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


class TokenBlacklistView(APIView):
    """
    JWT token blacklist endpoint.
    Allows users to manually blacklist their refresh tokens.

    POST /api/v1/auth/token/blacklist/
    {
        "refresh": "refresh_token_here"
    }
    """

    permission_classes = [AllowAny]  # Allow both authenticated and anonymous
    throttle_classes = [AnonRateThrottle, UserRateThrottle]

    def post(self, request):
        """Blacklist a refresh token."""
        try:
            # Get refresh token from request
            refresh_token_string = request.data.get("refresh")

            if not refresh_token_string:
                return APIResponse.validation_error(
                    message=_("Refresh token is required"),
                    field_errors={"refresh": _("Refresh token is required")},
                )

            try:
                # Create refresh token object and blacklist it
                refresh = RefreshToken(refresh_token_string)

                # Get user info before blacklisting
                user_id = refresh.payload.get("user_id")
                user_email = "unknown"

                try:
                    user = User.objects.get(id=user_id)
                    user_email = user.email
                except User.DoesNotExist:
                    pass

                # Blacklist the token
                refresh.blacklist()

                logger.info(f"Token blacklisted successfully for user: {user_email}")

                return APIResponse.success(message=_("Token blacklisted successfully"))

            except (InvalidToken, TokenError) as e:
                logger.warning(f"Token blacklist failed - invalid token: {str(e)}")
                return APIResponse.unauthorized(message=_("Invalid refresh token"))

        except Exception as e:
            logger.error(f"Token blacklist error: {str(e)}")
            return APIResponse.server_error(
                message=_("Token blacklist failed. Please try again.")
            )


class TokenInfoView(APIView):
    """
    JWT token information endpoint.
    Returns detailed information about the provided token.

    POST /api/v1/auth/token/info/
    {
        "token": "access_token_here"
    }
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, UserRateThrottle]

    def post(self, request):
        """Get detailed information about a JWT token."""
        try:
            # Get token from request
            token_string = request.data.get("token")

            if not token_string:
                return APIResponse.validation_error(
                    message=_("Token is required"),
                    field_errors={"token": _("Token is required")},
                )

            try:
                # Parse token to get information
                from datetime import datetime

                from rest_framework_simplejwt.tokens import AccessToken

                access_token = AccessToken(token_string)
                payload = access_token.payload

                # Extract token information
                issued_at = datetime.fromtimestamp(payload.get("iat", 0))
                expires_at = datetime.fromtimestamp(payload.get("exp", 0))
                now = datetime.now()

                token_info = {
                    "token_type": payload.get("token_type", "access"),
                    "user_id": payload.get("user_id"),
                    "email": payload.get("email"),
                    "user_role": payload.get("user_role"),
                    "session_id": payload.get("session_id"),
                    "issued_at": issued_at.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "is_expired": now > expires_at,
                    "time_to_expiry": (expires_at - now).total_seconds()
                    if now < expires_at
                    else 0,
                    "email_verified": payload.get("email_verified"),
                }

                # Get user information if user exists
                user_info = None
                user_id = payload.get("user_id")
                if user_id:
                    try:
                        user = User.objects.get(id=user_id)
                        user_info = {
                            "id": user.id,
                            "email": user.email,
                            "full_name": user.full_name,
                            "is_active": user.is_active,
                            "is_email_verified": user.is_email_verified,
                            "role": user.role,
                        }
                    except User.DoesNotExist:
                        user_info = {"error": "User not found"}

                return APIResponse.success(
                    message=_("Token information retrieved successfully"),
                    data={
                        "token_info": token_info,
                        "user_info": user_info,
                    },
                )

            except (InvalidToken, TokenError) as e:
                logger.warning(f"Token info request failed - invalid token: {str(e)}")
                return APIResponse.unauthorized(message=_("Invalid or expired token"))

        except Exception as e:
            logger.error(f"Token info error: {str(e)}")
            return APIResponse.server_error(
                message=_("Failed to get token information")
            )
