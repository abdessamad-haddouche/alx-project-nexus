"""
Authentication views for Movie Nexus.
Handles user registration, login, and logout.
"""

import logging

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from django.utils.translation import gettext_lazy as _

from apps.users.services import create_user_account
from core.exceptions import (
    AccountSuspendedException,
    AuthenticationException,
    EmailNotVerifiedException,
    InvalidCredentialsException,
    ValidationException,
)
from core.responses import APIResponse

from ..serializers import UserLoginSerializer, UserRegistrationSerializer
from ..services import authenticate_user, logout_user
from ..services.email_service import EmailService

logger = logging.getLogger(__name__)


class UserRegistrationView(APIView):
    """
    User registration endpoint with email verification.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    serializer_class = UserRegistrationSerializer

    @extend_schema(
        operation_id="auth_register",
        summary="User Registration",
        description=(
            "Register a new user account. "
            "An email verification link will be sent to the provided email address."
        ),
        tags=["Authentication"],
        request=UserRegistrationSerializer,
        responses={
            201: {
                "description": "User registered successfully",
                "example": {
                    "success": True,
                    "message": (
                        "Registration successful. "
                        "Please check your email for verification."
                    ),
                    "timestamp": "2025-01-15T10:30:00Z",
                    "data": {
                        "user": {
                            "id": 1,
                            "email": "user@example.com",
                            "full_name": "John Doe",
                            "is_email_verified": False,
                            "date_joined": "2025-01-15T10:30:00Z",
                        }
                    },
                },
            },
            400: {
                "description": "Validation errors",
                "example": {
                    "success": False,
                    "message": "Registration data is invalid",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "errors": {
                        "field_errors": {
                            "email": ["User with this email already exists"],
                            "password": ["Password too weak"],
                        }
                    },
                },
            },
            429: {"description": "Rate limit exceeded"},
        },
        examples=[
            OpenApiExample(
                "Registration Request",
                summary="Complete registration example",
                description="Example of a user registration with all fields",
                value={
                    "email": "john.doe@example.com",
                    "password": "SecurePass123!",
                    "password_confirm": "SecurePass123!",
                    "first_name": "John",
                    "last_name": "Doe",
                    "phone_number": "+1234567890",
                    "date_of_birth": "1990-01-01",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Minimal Registration",
                summary="Registration with required fields only",
                description="Example with only required fields",
                value={
                    "email": "jane@example.com",
                    "password": "SecurePass123!",
                    "password_confirm": "SecurePass123!",
                    "first_name": "Jane",
                    "last_name": "Smith",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        """Handle user registration."""
        try:
            # Validate input data
            serializer = self.serializer_class(data=request.data)

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message=_("Registration data is invalid"),
                    field_errors=serializer.errors,
                )

            # Create user account using service
            result = create_user_account(**serializer.validated_data)

            # Send verification email
            user = result["user"]
            verification_token = result["verification_token"]

            email_sent = EmailService.send_verification_email(
                user=user, verification_token=verification_token
            )

            if not email_sent:
                logger.warning(f"Failed to send verification email to {user.email}")
                # Don't fail the registration, just log the issue

            # Prepare response data
            user_data = {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "is_email_verified": user.is_email_verified,
                "date_joined": user.date_joined.isoformat(),
            }

            logger.info(f"User registered successfully: {user.email}")

            return APIResponse.registration_success(
                user_data=user_data,
                message=_(
                    "Registration successful. Please check your email for verification."
                ),
            )

        except ValidationException as e:
            logger.warning(f"Registration validation failed: {str(e)}")
            return APIResponse.validation_error(
                message=str(e.detail),
                field_errors=getattr(e, "extra_data", {}).get("field_errors"),
            )

        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return APIResponse.server_error(
                message=_("Registration failed. Please try again.")
            )


class UserLoginView(APIView):
    """
    User login endpoint with JWT token generation.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    serializer_class = UserLoginSerializer

    @extend_schema(
        operation_id="auth_login",
        summary="User Login",
        description=(
            "Authenticate user and return JWT tokens. "
            "Creates a new session with device tracking."
        ),
        tags=["Authentication"],
        request=UserLoginSerializer,
        responses={
            200: {
                "description": "Login successful",
                "example": {
                    "success": True,
                    "message": "Login successful",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "data": {
                        "user": {
                            "id": 1,
                            "email": "user@example.com",
                            "full_name": "John Doe",
                            "avatar_url": (
                                "https://ui-avatars.com/api/?name=JD"
                                "&background=6366f1&color=fff&size=200"
                            ),
                            "is_email_verified": True,
                            "role": "user",
                            "last_login": "2025-01-15T10:30:00Z",
                        },
                        "tokens": {
                            "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        },
                    },
                },
            },
            401: {
                "description": "Authentication failed",
                "example": {
                    "success": False,
                    "message": "Invalid email or password",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
            403: {
                "description": "Account not verified or suspended",
                "example": {
                    "success": False,
                    "message": "Please verify your email address before logging in",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
            429: {"description": "Rate limit exceeded"},
        },
        examples=[
            OpenApiExample(
                "Login Request",
                summary="User login credentials",
                description="Standard email and password login",
                value={"email": "user@example.com", "password": "SecurePass123!"},
                request_only=True,
            )
        ],
    )
    def post(self, request):
        """Handle user login."""
        try:
            # Validate input data
            serializer = self.serializer_class(
                data=request.data, context={"request": request}
            )

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message=_("Login data is invalid"), field_errors=serializer.errors
                )

            # Authenticate user using service
            email = serializer.validated_data["email"]
            password = serializer.validated_data["password"]

            auth_result = authenticate_user(
                email=email, password=password, request=request
            )

            # Prepare response data
            user = auth_result["user"]
            tokens = auth_result["tokens"]

            user_data = {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "avatar_url": user.avatar_url,
                "is_email_verified": user.is_email_verified,
                "role": user.role,
                "last_login": user.last_login.isoformat() if user.last_login else None,
            }

            logger.info(f"User logged in successfully: {user.email}")

            # Create API response
            return APIResponse.login_success(
                user_data=user_data, tokens=tokens, message=_("Login successful")
            )

        except InvalidCredentialsException as e:
            logger.warning(f"Invalid login attempt: {request.META.get('REMOTE_ADDR')}")
            return APIResponse.unauthorized(message=str(e.detail))

        except EmailNotVerifiedException as e:
            logger.warning(
                f"Unverified user login attempt: {request.data.get('email')}"
            )
            return APIResponse.forbidden(message=str(e.detail))

        except AccountSuspendedException as e:
            logger.warning(f"Suspended user login attempt: {request.data.get('email')}")
            return APIResponse.forbidden(message=str(e.detail))

        except AuthenticationException as e:
            logger.warning(f"Authentication failed: {str(e)}")
            return APIResponse.unauthorized(message=str(e.detail))

        except ValidationException as e:
            return APIResponse.validation_error(
                message=str(e.detail),
                field_errors=getattr(e, "extra_data", {}).get("field_errors"),
            )

        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return APIResponse.server_error(
                message=_("Login failed. Please try again.")
            )


class UserLogoutView(APIView):
    """
    User logout endpoint with session termination and JWT blacklisting.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    @extend_schema(
        operation_id="auth_logout",
        summary="User Logout",
        description=(
            "Logout user and terminate sessions. "
            "Automatically blacklists access token from Authorization header."
        ),
        tags=["Authentication"],
        request={
            "type": "object",
            "properties": {
                "logout_all": {
                    "type": "boolean",
                    "description": "Logout from all devices",
                    "default": False,
                },
                "refresh_token": {
                    "type": "string",
                    "description": "Refresh token to blacklist (optional)",
                },
            },
        },
        responses={
            200: {
                "description": "Logout successful",
                "example": {
                    "success": True,
                    "message": "Logout successful",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "data": {
                        "tokens_blacklisted": {
                            "access_token": True,
                            "refresh_token": False,
                        },
                        "sessions_terminated": 1,
                    },
                },
            },
            401: {
                "description": "Authentication required",
                "example": {
                    "success": False,
                    "message": "Authentication credentials were not provided",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
        },
        examples=[
            OpenApiExample(
                "Standard Logout",
                summary="Logout from current device",
                description=(
                    "Standard logout from current session - "
                    "access token automatically blacklisted"
                ),
                value={},
                request_only=True,
            ),
            OpenApiExample(
                "Logout All Devices",
                summary="Logout from all devices",
                description="Terminate all active sessions and blacklist tokens",
                value={"logout_all": True},
                request_only=True,
            ),
            OpenApiExample(
                "Logout with Refresh Token Blacklist",
                summary="Logout and blacklist specific refresh token",
                description="Logout and explicitly blacklist provided refresh token",
                value={
                    "logout_all": False,
                    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        """Handle user logout with JWT token blacklisting."""
        print(f"AUTH HEADER: {request.META.get('HTTP_AUTHORIZATION')}")
        print(f"USER: {request.user}")
        print(f"IS AUTHENTICATED: {request.user.is_authenticated}")
        try:
            # Get logout options
            logout_all = request.data.get("logout_all", False)
            refresh_token = request.data.get("refresh_token")

            # Get current user
            user = request.user

            # Get current session key if available
            session_key = getattr(request, "session_key", None)

            # Track blacklisting results
            tokens_blacklisted = {"access_token": False, "refresh_token": False}

            # Blacklist access token from Authorization header
            auth_header = request.META.get("HTTP_AUTHORIZATION")
            if auth_header and auth_header.startswith("Bearer "):
                access_token = auth_header.split(" ")[1]
                try:
                    from datetime import datetime

                    from rest_framework_simplejwt.token_blacklist.models import (
                        BlacklistedToken,
                        OutstandingToken,
                    )
                    from rest_framework_simplejwt.tokens import AccessToken

                    from django.utils import timezone

                    # Create AccessToken instance and blacklist it
                    token = AccessToken(access_token)
                    jti = token.payload.get("jti")

                    if jti:
                        # Convert timestamps to timezone-aware datetime objects
                        created_at = timezone.make_aware(
                            datetime.fromtimestamp(token.payload.get("iat", 0))
                        )
                        expires_at = timezone.make_aware(
                            datetime.fromtimestamp(token.payload.get("exp", 0))
                        )

                        # Get or create outstanding token
                        (
                            outstanding_token,
                            created,
                        ) = OutstandingToken.objects.get_or_create(
                            jti=jti,
                            defaults={
                                "token": access_token,
                                "created_at": created_at,
                                "expires_at": expires_at,
                                "user": user,
                            },
                        )

                        # Blacklist the token
                        BlacklistedToken.objects.get_or_create(token=outstanding_token)
                        tokens_blacklisted["access_token"] = True
                        logger.info(f"Access token blacklisted for user: {user.email}")

                except Exception as e:
                    logger.warning(
                        f"Failed to blacklist access token for {user.email}: {e}"
                    )

            # Blacklist refresh token if provided
            if refresh_token:
                try:
                    from rest_framework_simplejwt.tokens import RefreshToken

                    refresh = RefreshToken(refresh_token)
                    refresh.blacklist()
                    tokens_blacklisted["refresh_token"] = True
                    logger.info(f"Refresh token blacklisted for user: {user.email}")
                except Exception as e:
                    logger.warning(
                        f"Failed to blacklist refresh token for {user.email}: {e}"
                    )

            # Logout user using service
            logout_result = logout_user(
                user=user,
                refresh_token=refresh_token,
                session_key=session_key,
                logout_all=logout_all,
            )

            if logout_result["success"]:
                logger.info(f"User logged out successfully: {user.email}")

                # Customize message based on logout type
                if logout_all:
                    message = _("Logged out from all devices successfully")
                else:
                    message = _("Logout successful")

                # Prepare response data
                response_data = {
                    "tokens_blacklisted": tokens_blacklisted,
                    "sessions_terminated": logout_result.get("terminated_sessions", 0),
                    "logout_all": logout_all,
                    "user_email": user.email,
                }

                return APIResponse.success(message=message, data=response_data)
            else:
                logger.warning(
                    f"Logout partially failed for {user.email}: "
                    f"{logout_result.get('error')}"
                )

                # Still return success with tokens blacklisted
                response_data = {
                    "tokens_blacklisted": tokens_blacklisted,
                    "sessions_terminated": logout_result.get("terminated_sessions", 0),
                    "logout_all": logout_all,
                    "user_email": user.email,
                    "partial_failure": True,
                }

                return APIResponse.success(
                    message=_(
                        "Logout completed with some session issues, "
                        "but tokens blacklisted"
                    ),
                    data=response_data,
                )

        except Exception as e:
            user_email = (
                request.user.email if request.user.is_authenticated else "unknown"
            )
            logger.error(f"Logout error for {user_email}: {str(e)}")
            return APIResponse.server_error(
                message=_("Logout failed. Please try again.")
            )
