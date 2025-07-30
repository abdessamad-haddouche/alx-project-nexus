"""
Email service for Movie Nexus authentication.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from core.constants import VerificationType

from ..models import VerificationToken

User = get_user_model()
logger = logging.getLogger(__name__)


class EmailService:
    """
    Essential email service for authentication workflows.
    """

    @staticmethod
    def send_verification_email(user, verification_token=None):
        """
        Send email verification to user.

        Args:
            user: User instance
            verification_token: VerificationToken instance (optional)

        Returns:
            bool: True if email sent successfully
        """
        try:
            # Create verification token if not provided
            if not verification_token:
                verification_token = VerificationToken.objects.create(
                    user=user,
                    email=user.email,
                    verification_type=VerificationType.REGISTRATION,
                )

            # Build verification URL
            verification_url = EmailService._build_verification_url(
                verification_token.token
            )

            # Email context
            context = {
                "user": user,
                "verification_url": verification_url,
                "site_name": getattr(settings, "SITE_NAME", "Movie Nexus"),
                "expires_hours": 24,
            }

            # Send email
            subject = f"Verify your {context['site_name']} account"

            # Simple email body
            message = f"""
Hi {user.first_name},

Welcome to {context['site_name']}!
Please verify your email address by clicking the link below:

{verification_url}

This link will expire in {context['expires_hours']} hours.

If you didn't create an account, please ignore this email.

Best regards,
The {context['site_name']} Team
            """.strip()

            success = send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

            if success:
                logger.info(f"Verification email sent to {user.email}")
                return True
            else:
                logger.error(f"Failed to send verification email to {user.email}")
                return False

        except Exception as e:
            logger.error(f"Error sending verification email to {user.email}: {str(e)}")
            return False

    @staticmethod
    def send_password_reset_email(user, reset_token):
        """
        Send password reset email to user.

        Args:
            user: User instance
            reset_token: VerificationToken instance for password reset

        Returns:
            bool: True if email sent successfully
        """
        try:
            # Build reset URL
            reset_url = EmailService._build_password_reset_url(reset_token.token)

            # Email context
            context = {
                "user": user,
                "reset_url": reset_url,
                "site_name": getattr(settings, "SITE_NAME", "Movie Nexus"),
                "expires_hours": 1,
            }

            # Send email
            subject = f"Reset your {context['site_name']} password"

            message = f"""
Hi {user.first_name},

You requested a password reset for your {context['site_name']} account.

Click the link below to reset your password:

{reset_url}

This link will expire in {context['expires_hours']} hour.

If you didn't request this reset, please ignore this email.

Best regards,
The {context['site_name']} Team
            """.strip()

            success = send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

            if success:
                logger.info(f"Password reset email sent to {user.email}")
                return True
            else:
                logger.error(f"Failed to send password reset email to {user.email}")
                return False

        except Exception as e:
            logger.error(
                f"Error sending password reset email to {user.email}: {str(e)}"
            )
            return False

    @staticmethod
    def send_welcome_email(user):
        """
        Send welcome email after successful email verification.

        Args:
            user: User instance

        Returns:
            bool: True if email sent successfully
        """
        try:
            # Email context
            context = {
                "user": user,
                "site_name": getattr(settings, "SITE_NAME", "Movie Nexus"),
                "login_url": EmailService._build_login_url(),
            }

            # Send email
            subject = f"Welcome to {context['site_name']}!"

            message = f"""
Hi {user.first_name},

Welcome to {context['site_name']}! Your email has been verified successfully.

You can now:
- Discover amazing movies
- Get personalized recommendations
- Create your favorites list
- Build custom watchlists

Get started: {context['login_url']}

Happy movie watching!

Best regards,
The {context['site_name']} Team
            """.strip()

            success = send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

            if success:
                logger.info(f"Welcome email sent to {user.email}")
                return True
            else:
                logger.error(f"Failed to send welcome email to {user.email}")
                return False

        except Exception as e:
            logger.error(f"Error sending welcome email to {user.email}: {str(e)}")
            return False

    @staticmethod
    def resend_verification_email(user):
        """
        Resend verification email to user.

        Args:
            user: User instance

        Returns:
            bool: True if email sent successfully
        """
        try:
            # Check if user is already verified
            if user.is_email_verified:
                logger.warning(
                    f"Attempted to resend verification to already verified user: "
                    f"{user.email}"
                )
                return False

            # Deactivate existing verification tokens
            VerificationToken.objects.filter(
                user=user,
                verification_type=VerificationType.REGISTRATION,
                is_active=True,
                is_used=False,
            ).update(is_active=False)

            # Create new verification token
            verification_token = VerificationToken.objects.create(
                user=user,
                email=user.email,
                verification_type=VerificationType.REGISTRATION,
            )

            # Send verification email
            return EmailService.send_verification_email(user, verification_token)

        except Exception as e:
            logger.error(
                f"Error resending verification email to {user.email}: {str(e)}"
            )
            return False

    # ================================================================
    # HELPER METHODS
    # ================================================================

    @staticmethod
    def _build_verification_url(token):
        """Build email verification URL."""
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        return f"{frontend_url}/auth/verify-email?token={token}"

    @staticmethod
    def _build_password_reset_url(token):
        """Build password reset URL."""
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        return f"{frontend_url}/auth/reset-password?token={token}"

    @staticmethod
    def _build_login_url():
        """Build login URL."""
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        return f"{frontend_url}/auth/login"

    @staticmethod
    def test_email_configuration():
        """
        Test email configuration.

        Returns:
            bool: True if email is configured correctly
        """
        try:
            # Check required settings
            required_settings = ["EMAIL_HOST", "EMAIL_PORT", "DEFAULT_FROM_EMAIL"]
            missing_settings = [
                setting
                for setting in required_settings
                if not hasattr(settings, setting) or not getattr(settings, setting)
            ]

            if missing_settings:
                logger.error(f"Missing email settings: {missing_settings}")
                return False

            # Try sending a test email (in development)
            if settings.DEBUG:
                logger.info("Email configuration appears correct")
                return True
            else:
                # In production, you might want to send an actual test email
                logger.info("Email configuration check passed")
                return True

        except Exception as e:
            logger.error(f"Email configuration test failed: {str(e)}")
            return False
