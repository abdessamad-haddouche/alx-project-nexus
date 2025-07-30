"""
authentication views for Movie Nexus.
Handles user registration, login, and logout with professional error.
"""

import logging

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from django.utils.translation import gettext_lazy as _

from core.exceptions import (
    AccountSuspendedException,
    AuthenticationException,
    EmailNotVerifiedException,
    InvalidCredentialsException,
    ValidationException,
)
from core.responses import APIResponse

from ..serializers import UserLoginSerializer, UserRegistrationSerializer
from ..services import authenticate_user, create_user_account, logout_user
from ..services.email_service import EmailService

logger = logging.getLogger(__name__)


class UserRegistrationView(APIView):
    """
    User registration endpoint with email verification.

    POST /api/v1/auth/register/
    {
        "email": "abdessamad@root.com",
        "password": "securepass123",
        "password_confirm": "securepass123",
        "first_name": "Abdessamad",
        "last_name": "Haddouche",
        "phone_number": "+1234567890",  // optional
        "date_of_birth": "1990-01-01"   // optional
    }
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    serializer_class = UserRegistrationSerializer

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

    POST /api/v1/auth/login/
    {
        "email": "abdessamad@root.com",
        "password": "securepass123"
    }
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    serializer_class = UserLoginSerializer

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
    User logout endpoint with session termination.

    POST /api/v1/auth/logout/
    {
        "logout_all": false,     // optional - logout from all devices
        "refresh_token": "..."   // optional - token to blacklist
    }
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request):
        """Handle user logout."""
        try:
            # Get logout options
            logout_all = request.data.get("logout_all", False)
            refresh_token = request.data.get("refresh_token")

            # Get current user
            user = request.user

            # Get current session key if available
            session_key = getattr(request, "session_key", None)

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

                return APIResponse.logout_success(message=message)
            else:
                logger.warning(
                    f"Logout partially failed for {user.email}: "
                    f"{logout_result.get('error')}"
                )
                return APIResponse.success(
                    message=_("Logout completed with some issues")
                )

        except Exception as e:
            user_email = (
                request.user.email if request.user.is_authenticated else "unknown"
            )
            logger.error(f"Logout error for {user_email}: {str(e)}")
            return APIResponse.server_error(
                message=_("Logout failed. Please try again.")
            )
