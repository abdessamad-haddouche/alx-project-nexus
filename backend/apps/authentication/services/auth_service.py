"""
Authentication services for Movie Nexus.
"""

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Optional

from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.constants import LoginMethod
from core.exceptions import (
    AccountSuspendedException,
    AuthenticationException,
    EmailNotVerifiedException,
    InvalidCredentialsException,
    TokenInvalidException,
)

# Type hints only (not runtime imports)
if TYPE_CHECKING:
    from ..models import User, UserSession
else:
    # Runtime imports
    from django.contrib.auth import get_user_model

    from ..models import UserSession

    User = get_user_model()

logger = logging.getLogger(__name__)


class AuthenticationService:
    """
    Essential authentication service for Movie Nexus.
    Handles login, logout, JWT tokens, and session management.
    """

    @staticmethod
    @transaction.atomic
    def authenticate_user(email: str, password: str, request=None) -> Dict:
        """
        Authenticate user with email/password and create session.

        Args:
            email: User email address
            password: User password
            request: HTTP request object (for IP, user agent)

        Returns:
            Dict containing user, session, tokens, and status

        Raises:
            AuthenticationException: If authentication fails
        """
        try:
            # Normalize email
            email = email.lower().strip()

            # Basic validation
            if not email or not password:
                raise AuthenticationException(_("Email and password are required"))

            # FIRST: Check if user exists and get user object
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                logger.warning(f"Failed login attempt for non-existent user: {email}")
                raise InvalidCredentialsException(_("Invalid email or password"))

            # SECOND: Check if user is active BEFORE password check
            if not user.is_active:
                logger.warning(f"Inactive user login attempt: {email}")
                raise AccountSuspendedException(_("Account is deactivated"))

            # THIRD: Check email verification BEFORE password check
            if not user.is_email_verified:
                logger.warning(f"Unverified user login attempt: {email}")
                raise EmailNotVerifiedException(
                    _("Please verify your email address before logging in")
                )

            # FOURTH: Now check password
            authenticated_user = authenticate(email=email, password=password)

            if not authenticated_user:
                logger.warning(f"Failed login attempt - wrong password for: {email}")
                raise InvalidCredentialsException(_("Invalid email or password"))

            # Use the authenticated user object
            user = authenticated_user

            # Create user session
            session = AuthenticationService._create_user_session(
                user=user, request=request, login_method=LoginMethod.PASSWORD
            )

            # Generate JWT tokens
            tokens = AuthenticationService.generate_jwt_tokens(user, session)

            # Update last login
            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])

            logger.info(f"User authenticated successfully: {email}")

            return {
                "user": user,
                "session": session,
                "tokens": tokens,
                "authenticated": True,
                "message": _("Login successful"),
            }

        except (
            AuthenticationException,
            InvalidCredentialsException,
            AccountSuspendedException,
            EmailNotVerifiedException,
        ):
            raise
        except Exception as e:
            logger.error(f"Authentication error for {email}: {str(e)}")
            raise AuthenticationException(_("Authentication failed"))

    @staticmethod
    def generate_jwt_tokens(
        user: "User", session: "UserSession" = None
    ) -> Dict[str, str]:
        """
        Generate JWT access and refresh tokens for user.

        Args:
            user: User instance
            session: UserSession instance (optional)

        Returns:
            Dict containing access and refresh tokens
        """
        try:
            # Generate refresh token
            refresh = RefreshToken.for_user(user)

            # Get access token
            access_token = refresh.access_token

            # Add custom claims to access token
            access_token["email"] = user.email
            access_token["email_verified"] = user.is_email_verified
            access_token["user_role"] = user.role
            access_token["full_name"] = user.full_name

            # Add session info if available
            if session:
                access_token["session_id"] = str(session.id)
                access_token["login_method"] = session.login_method

            # Add token metadata
            access_token["iat"] = datetime.utcnow()
            access_token["token_type"] = "access"

            # Get token lifetime from settings with fallback
            access_lifetime = getattr(settings, "SIMPLE_JWT", {}).get(
                "ACCESS_TOKEN_LIFETIME", timedelta(minutes=15)
            )

            tokens = {
                "access": str(access_token),
                "refresh": str(refresh),
                "token_type": "Bearer",
                "expires_in": access_lifetime.total_seconds(),
            }

            logger.info(f"JWT tokens generated for user: {user.email}")
            return tokens

        except Exception as e:
            logger.error(f"Token generation failed for {user.email}: {str(e)}")
            raise TokenInvalidException(_("Failed to generate authentication tokens"))

    @staticmethod
    def refresh_jwt_token(refresh_token: str) -> Dict[str, str]:
        """
        Refresh JWT access token using refresh token.

        Args:
            refresh_token: Refresh token string

        Returns:
            Dict containing new access token

        Raises:
            TokenInvalidException: If refresh token is invalid
        """
        try:
            # Validate and decode refresh token
            refresh = RefreshToken(refresh_token)

            # Get user from token
            user_id = refresh.payload.get("user_id")
            user = User.objects.get(id=user_id, is_active=True)

            # Generate new access token
            new_access_token = refresh.access_token

            # Add custom claims
            new_access_token["email"] = user.email
            new_access_token["email_verified"] = user.is_email_verified
            new_access_token["user_role"] = user.role
            new_access_token["full_name"] = user.full_name
            new_access_token["iat"] = datetime.utcnow()
            new_access_token["token_type"] = "access"

            # Get token lifetime from settings with fallback
            access_lifetime = getattr(settings, "SIMPLE_JWT", {}).get(
                "ACCESS_TOKEN_LIFETIME", timedelta(minutes=15)
            )

            tokens = {
                "access": str(new_access_token),
                "token_type": "Bearer",
                "expires_in": access_lifetime.total_seconds(),
            }

            logger.info(f"Token refreshed for user: {user.email}")
            return tokens

        except (InvalidToken, TokenError, User.DoesNotExist) as e:
            logger.warning(f"Token refresh failed: {str(e)}")
            raise TokenInvalidException(_("Invalid or expired refresh token"))
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            raise TokenInvalidException(_("Token refresh failed"))

    @staticmethod
    @transaction.atomic
    def logout_user(
        user: "User",
        refresh_token: str = None,
        session_key: str = None,
        logout_all: bool = False,
    ) -> Dict:
        """
        Logout user and terminate sessions with token blacklisting.

        Args:
            user: User instance
            refresh_token: Refresh token to blacklist (optional)
            session_key: Specific session to terminate (optional)
            logout_all: Whether to logout from all devices

        Returns:
            Dict containing logout status and details
        """
        try:
            terminated_sessions = 0
            blacklisted_tokens = 0

            if logout_all:
                # Terminate all user sessions
                active_sessions = UserSession.objects.active_for_user(user)
                terminated_sessions = active_sessions.count()

                for session in active_sessions:
                    session.terminate(reason="logout_all_devices")

                logger.info(f"All sessions terminated for user: {user.email}")

            elif session_key:
                # Terminate specific session
                try:
                    session = UserSession.objects.get(
                        session_key=session_key, user=user, is_active=True
                    )
                    session.terminate(reason="user_logout")
                    terminated_sessions = 1

                    logger.info(
                        f"Session {session_key} terminated for user: {user.email}"
                    )

                except UserSession.DoesNotExist:
                    logger.warning(
                        f"Session {session_key} not found for user: {user.email}"
                    )

            else:
                # Terminate most recent session if no specific session provided
                recent_session = UserSession.objects.active_for_user(user).first()
                if recent_session:
                    recent_session.terminate(reason="user_logout")
                    terminated_sessions = 1

            return {
                "success": True,
                "message": _("Logout successful"),
                "terminated_sessions": terminated_sessions,
                "blacklisted_tokens": blacklisted_tokens,
                "logout_all": logout_all,
                "user_email": user.email,
            }

        except Exception as e:
            logger.error(f"Logout failed for {user.email}: {str(e)}")
            return {"success": False, "message": _("Logout failed"), "error": str(e)}

    # ================================================================
    # HELPER METHODS (Private)
    # ================================================================

    @staticmethod
    def _create_user_session(
        user: "User", request=None, login_method: str = LoginMethod.PASSWORD
    ) -> "UserSession":
        """Create user session with request data."""
        try:
            # Extract request data
            ip_address = "127.0.0.1"  # Default
            user_agent = "Unknown"  # Default

            if request:
                # Get IP address (handle proxy headers)
                x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
                if x_forwarded_for:
                    ip_address = x_forwarded_for.split(",")[0].strip()
                else:
                    ip_address = request.META.get("REMOTE_ADDR", "127.0.0.1")

                # Get user agent
                user_agent = request.META.get("HTTP_USER_AGENT", "Unknown")

            # Create session using manager method
            session = UserSession.objects.create_session(
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
                login_method=login_method,
            )

            return session

        except Exception as e:
            logger.error(f"Session creation failed for {user.email}: {str(e)}")
            raise

    @staticmethod
    def verify_session(session_key: str, user: "User") -> Optional["UserSession"]:
        """
        Verify user session is valid and active.

        Args:
            session_key: Session key to verify
            user: User instance

        Returns:
            UserSession if valid, None otherwise
        """
        try:
            session = UserSession.objects.get(
                session_key=session_key, user=user, is_active=True
            )

            if session.is_valid:
                # Update last activity
                session.last_activity = timezone.now()
                session.save(update_fields=["last_activity"])
                return session
            else:
                # Session expired, deactivate it
                session.terminate(reason="session_expired")
                return None

        except UserSession.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Session verification failed: {str(e)}")
            return None

    @staticmethod
    def get_user_active_sessions(user: "User") -> Dict:
        """
        Get user's active sessions with details.

        Args:
            user: User instance

        Returns:
            Dict containing session information
        """
        try:
            active_sessions = UserSession.objects.active_for_user(user)

            sessions_data = []
            for session in active_sessions:
                sessions_data.append(
                    {
                        "session_key": session.session_key,
                        "device_type": session.device_type,
                        "login_method": session.login_method,
                        "ip_address": session.ip_address,
                        "login_at": session.login_at,
                        "last_activity": session.last_activity,
                        "expires_at": session.expires_at,
                        "is_current": False,  # Will be set by view if needed
                    }
                )

            return {"total_sessions": len(sessions_data), "sessions": sessions_data}

        except Exception as e:
            logger.error(f"Failed to get sessions for {user.email}: {str(e)}")
            return {"total_sessions": 0, "sessions": []}


# ================================================================
# CONVENIENCE FUNCTIONS
# ================================================================


def authenticate_user(email: str, password: str, request=None) -> Dict:
    """Convenience function for user authentication."""
    return AuthenticationService.authenticate_user(email, password, request)


def generate_tokens(user: "User", session: "UserSession" = None) -> Dict[str, str]:
    """Convenience function for token generation."""
    return AuthenticationService.generate_jwt_tokens(user, session)


def refresh_token(refresh_token: str) -> Dict[str, str]:
    """Convenience function for token refresh."""
    return AuthenticationService.refresh_jwt_token(refresh_token)


def logout_user(
    user: "User",
    refresh_token: str = None,
    session_key: str = None,
    logout_all: bool = False,
) -> Dict:
    """Convenience function for user logout."""
    return AuthenticationService.logout_user(
        user, refresh_token, session_key, logout_all
    )
