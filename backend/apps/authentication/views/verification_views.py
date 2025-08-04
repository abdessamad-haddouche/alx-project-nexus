"""
Email verification and password reset views for Movie Nexus.
Handles email verification, resend verification, password reset requests and
confirmations.
"""

import logging

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from core.exceptions import TokenInvalidException, ValidationException
from core.responses import APIResponse

from ..serializers import (
    EmailVerificationSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ResendVerificationSerializer,
)
from ..services import verify_user_email
from ..services.email_service import EmailService
from ..services.token_service import TokenService

User = get_user_model()
logger = logging.getLogger(__name__)


class EmailVerificationView(APIView):
    """
    Email verification endpoint using token.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    serializer_class = EmailVerificationSerializer

    @extend_schema(
        operation_id="auth_verify_email",
        summary="Email Verification",
        description=(
            "Verify user email address using verification token. "
            "The token is typically sent via email during registration. "
            "Sends welcome email upon successful verification."
        ),
        tags=["Authentication"],
        request=EmailVerificationSerializer,
        responses={
            200: {
                "description": "Email verified successfully",
                "example": {
                    "success": True,
                    "message": "Email verified successfully",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "data": {
                        "user": {
                            "id": 1,
                            "email": "user@example.com",
                            "full_name": "John Doe",
                            "is_email_verified": True,
                        }
                    },
                },
            },
            400: {
                "description": "Invalid or expired token",
                "example": {
                    "success": False,
                    "message": "Invalid or expired verification token",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "errors": {
                        "field_errors": {
                            "token": ["This token is invalid or has expired"]
                        }
                    },
                },
            },
            429: {"description": "Rate limit exceeded"},
            500: {
                "description": "Server error",
                "example": {
                    "success": False,
                    "message": "Email verification failed. Please try again.",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
        },
        examples=[
            OpenApiExample(
                "Email Verification",
                summary="Verify email with token",
                description=(
                    "Standard email verification request with registration token"
                ),
                value={
                    "token": (
                        "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9."
                        "eyJ1c2VyX2lkIjoxLCJ0b2tlbl90eXBlIjoidmVyaWZpY2F0aW9uIn0..."
                    )
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        """Verify user email with token."""
        try:
            # Validate input data
            serializer = self.serializer_class(data=request.data)

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message=_("Invalid verification data"),
                    field_errors=serializer.errors,
                )

            # Get the VerificationToken instance from validated data
            verification_token = serializer.validated_data["token"]

            # Verify email using service
            try:
                result = verify_user_email(verification_token.token)

                user = result["user"]

                # Send welcome email if verification successful and not already verified
                if result["verified"] and not result.get("already_verified"):
                    EmailService.send_welcome_email(user)

                # Prepare response data
                user_data = {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "is_email_verified": user.is_email_verified,
                }

                message = result["message"]

                if result.get("already_verified"):
                    logger.info(
                        f"Email verification attempted for already verified user: "
                        f"{user.email}"
                    )
                else:
                    logger.info(f"Email verified successfully: {user.email}")

                return APIResponse.email_verified(user_data=user_data, message=message)

            except TokenInvalidException as e:
                logger.warning(f"Invalid verification token attempt: {str(e)}")
                return APIResponse.error(
                    message=str(e.detail), status_code=status.HTTP_400_BAD_REQUEST
                )

            except ValidationException as e:
                return APIResponse.validation_error(message=str(e.detail))

        except Exception as e:
            logger.error(f"Email verification error: {str(e)}")
            return APIResponse.server_error(
                message=_("Email verification failed. Please try again.")
            )


class ResendEmailVerificationView(APIView):
    """
    Resend email verification endpoint.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, UserRateThrottle]
    serializer_class = ResendVerificationSerializer

    @extend_schema(
        operation_id="auth_resend_verification",
        summary="Resend Email Verification",
        description=(
            "Resend email verification link to user who hasn't received or lost "
            "the original verification email."
        ),
        tags=["Authentication"],
        request=ResendVerificationSerializer,
        responses={
            200: {
                "description": "Verification email sent successfully",
                "example": {
                    "success": True,
                    "message": "Verification email sent successfully",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "data": {
                        "email": "user@example.com",
                        "message": "Verification email has been sent",
                    },
                },
            },
            400: {
                "description": "Invalid email or already verified",
                "example": {
                    "success": False,
                    "message": "Invalid email data",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "errors": {
                        "field_errors": {"email": ["Email is already verified"]}
                    },
                },
            },
            429: {"description": "Rate limit exceeded"},
            500: {
                "description": "Failed to send email",
                "example": {
                    "success": False,
                    "message": "Failed to resend verification email",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
        },
        examples=[
            OpenApiExample(
                "Resend Verification",
                summary="Resend verification email",
                description="Request new verification email for unverified account",
                value={"email": "user@example.com"},
                request_only=True,
            ),
            OpenApiExample(
                "Authenticated User Resend",
                summary="Resend for authenticated user",
                description=(
                    "Authenticated users don't need to provide email - "
                    "uses account email automatically"
                ),
                value={},
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        """Resend email verification."""
        try:
            # Handle authenticated user case
            data = request.data.copy()
            if request.user.is_authenticated and not data.get("email"):
                data["email"] = request.user.email

            # Use serializer for validation and logic
            serializer = self.serializer_class(data=data)

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message=_("Invalid email data"), field_errors=serializer.errors
                )

            # Create the verification token (serializer handles the logic)
            result = serializer.save()
            verification_token = result["verification"]
            user = result["user"]

            # Send verification email
            email_sent = EmailService.send_verification_email(
                user=user, verification_token=verification_token
            )

            if email_sent:
                logger.info(f"Verification email resent successfully: {user.email}")
                return APIResponse.success(
                    message=_("Verification email sent successfully"),
                    data=serializer.data,
                )
            else:
                logger.error(f"Failed to send verification email: {user.email}")
                return APIResponse.server_error(
                    message=_("Failed to send verification email")
                )

        except Exception as e:
            logger.error(f"Resend verification error: {str(e)}")
            return APIResponse.server_error(
                message=_("Failed to resend verification email")
            )


class PasswordResetRequestView(APIView):
    """
    Password reset request endpoint.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    serializer_class = PasswordResetRequestSerializer

    @extend_schema(
        operation_id="auth_password_reset_request",
        summary="Password Reset Request",
        description=(
            "Request password reset for user account. "
            "If email exists, a reset link will be sent. "
            "Always returns success for security (doesn't reveal if email exists)."
        ),
        tags=["Authentication"],
        request=PasswordResetRequestSerializer,
        responses={
            200: {
                "description": "Password reset request processed",
                "example": {
                    "success": True,
                    "message": (
                        "If an account exists with this email, password reset "
                        "instructions have been sent."
                    ),
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
            400: {
                "description": "Invalid email format",
                "example": {
                    "success": False,
                    "message": "Invalid email data",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "errors": {
                        "field_errors": {"email": ["Enter a valid email address"]}
                    },
                },
            },
            429: {"description": "Rate limit exceeded"},
            500: {
                "description": "Server error",
                "example": {
                    "success": False,
                    "message": "Failed to process password reset request",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
        },
        examples=[
            OpenApiExample(
                "Password Reset Request",
                summary="Request password reset",
                description="Send password reset instructions to email",
                value={"email": "user@example.com"},
                request_only=True,
            )
        ],
    )
    def post(self, request):
        """Request password reset."""
        try:
            # Validate input data
            serializer = self.serializer_class(data=request.data)

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message=_("Invalid email data"), field_errors=serializer.errors
                )

            # Get email from validated data
            email = serializer.validated_data["email"]

            # Check if user exists
            try:
                user = User.objects.get(email=email, is_active=True)

                # Create password reset token
                reset_token = TokenService.create_password_reset_token(user)

                # Send password reset email
                email_sent = EmailService.send_password_reset_email(
                    user=user, reset_token=reset_token
                )

                if email_sent:
                    logger.info(f"Password reset email sent: {user.email}")
                else:
                    logger.error(f"Failed to send password reset email: {user.email}")

            except User.DoesNotExist:
                logger.warning(
                    f"Password reset attempt for non-existent email: {email}"
                )
                pass

            return APIResponse.success(
                message=_(
                    "If an account exists with this email, password reset"
                    " instructions have been sent."
                )
            )

        except Exception as e:
            logger.error(f"Password reset request error: {str(e)}")
            return APIResponse.server_error(
                message=_("Failed to process password reset request")
            )


class PasswordResetConfirmView(APIView):
    """
    Password reset confirmation endpoint.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    serializer_class = PasswordResetConfirmSerializer

    @extend_schema(
        operation_id="auth_password_reset_confirm",
        summary="Password Reset Confirmation",
        description=(
            "Reset password using reset token and new password. "
            "Token is provided via email from password reset request. "
            "Terminates all user sessions for security."
        ),
        tags=["Authentication"],
        request=PasswordResetConfirmSerializer,
        responses={
            200: {
                "description": "Password reset successful",
                "example": {
                    "success": True,
                    "message": (
                        "Password reset successful. "
                        "Please log in with your new password."
                    ),
                    "timestamp": "2025-01-15T10:30:00Z",
                    "data": {
                        "user": {
                            "id": 1,
                            "email": "user@example.com",
                            "full_name": "John Doe",
                        }
                    },
                },
            },
            400: {
                "description": "Invalid token or password validation failed",
                "example": {
                    "success": False,
                    "message": "Invalid password reset data",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "errors": {
                        "field_errors": {
                            "token": ["This token is invalid or has expired"],
                            "password": ["Password too weak"],
                            "password_confirm": ["Passwords do not match"],
                        }
                    },
                },
            },
            429: {"description": "Rate limit exceeded"},
            500: {
                "description": "Server error",
                "example": {
                    "success": False,
                    "message": "Failed to reset password. Please try again.",
                    "timestamp": "2025-01-15T10:30:00Z",
                },
            },
        },
        examples=[
            OpenApiExample(
                "Password Reset Confirmation",
                summary="Confirm password reset",
                description="Reset password with token and new password",
                value={
                    "token": (
                        "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9."
                        "eyJ1c2VyX2lkIjoxLCJ0b2tlbl90eXBlIjoicGFzc3dvcmRfcmVzZXQifQ..."
                    ),
                    "password": "NewSecurePass123!",
                    "password_confirm": "NewSecurePass123!",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        """Confirm password reset with token."""
        try:
            # Validate input data
            serializer = self.serializer_class(data=request.data)

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message=_("Invalid password reset data"),
                    field_errors=serializer.errors,
                )

            # Get the VerificationToken instance from validated data
            verification_token = serializer.validated_data[
                "token"
            ]  # This is the VerificationToken object
            new_password = serializer.validated_data["password"]

            # Get user from the verification token
            user = verification_token.user

            # Mark token as used (this calls your model's verify() method)
            verification_token.verify()

            # Set new password
            user.set_password(new_password)
            user.save(update_fields=["password"])

            # Terminate all user sessions for security
            from ..services.session_service import terminate_all_sessions

            terminate_all_sessions(user=user, reason="password_reset")

            # Prepare response data
            user_data = {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
            }

            logger.info(f"Password reset completed successfully: {user.email}")

            return APIResponse.success(
                message=_(
                    "Password reset successful. Please log in with your new password."
                ),
                data={"user": user_data},
            )

        except ValidationException as e:
            logger.warning(f"Password reset validation failed: {str(e)}")
            return APIResponse.validation_error(
                message=str(e.detail),
                field_errors=getattr(e, "extra_data", {}).get("field_errors"),
            )

        except Exception as e:
            logger.error(f"Password reset confirmation error: {str(e)}")
            return APIResponse.server_error(
                message=_("Failed to reset password. Please try again.")
            )
