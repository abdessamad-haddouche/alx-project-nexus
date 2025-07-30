"""
Email verification and password reset views for Movie Nexus.
Handles email verification, resend verification, password reset requests and
confirmations.
"""

import logging

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

    POST /api/v1/auth/verify-email/
    {
        "token": "verification_token_here"
    }
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    serializer_class = EmailVerificationSerializer

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
                result = verify_user_email(
                    verification_token.token
                )  # Pass the token string here

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

    POST /api/v1/auth/resend-verification/
    {
        "email": "user@example.com"
    }
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, UserRateThrottle]
    serializer_class = ResendVerificationSerializer

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

    POST /api/v1/auth/password/reset/
    {
        "email": "user@example.com"
    }
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    serializer_class = PasswordResetRequestSerializer

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
                # For security, don't reveal if email exists
                logger.warning(
                    f"Password reset attempt for non-existent email: {email}"
                )
                pass

            # Always return success for security (don't reveal if email exists)
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

    POST /api/v1/auth/password/reset/confirm/
    {
        "token": "reset_token_here",
        "password": "new_secure_password",
        "password_confirm": "new_secure_password"
    }
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    serializer_class = PasswordResetConfirmSerializer

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

            # Get validated data
            token = serializer.validated_data["token"]
            new_password = serializer.validated_data["password"]

            # Validate and use token
            try:
                token_data = TokenService.verify_and_use_token(token)
                user = token_data["user"]

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
                        "Password reset successful. Please log in with your new"
                        " password."
                    ),
                    data={"user": user_data},
                )

            except TokenInvalidException as e:
                logger.warning(f"Invalid password reset token attempt: {str(e)}")
                return APIResponse.error(
                    message=str(e.detail), status_code=status.HTTP_400_BAD_REQUEST
                )

            except ValidationException as e:
                return APIResponse.validation_error(
                    message=str(e.detail),
                    field_errors=getattr(e, "extra_data", {}).get("field_errors"),
                )

        except Exception as e:
            logger.error(f"Password reset confirmation error: {str(e)}")
            return APIResponse.server_error(
                message=_("Failed to reset password. Please try again.")
            )
