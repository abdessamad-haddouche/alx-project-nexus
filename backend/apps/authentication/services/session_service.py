"""
Essential session services for Movie Nexus.
"""


import logging
from typing import TYPE_CHECKING, Dict, Optional

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.constants import DeviceType, LoginMethod
from core.exceptions import SessionNotFoundException, ValidationException

# Type hints only
if TYPE_CHECKING:
    from ..models import User, UserSession
else:
    # Runtime imports
    from django.contrib.auth import get_user_model

    from ..models import UserSession

    User = get_user_model()

logger = logging.getLogger(__name__)


class SessionService:
    """
    Essential session service for Movie Nexus.
    Handles user session creation, termination, and management.
    """

    @staticmethod
    def create_user_session(
        user: "User",
        ip_address: str,
        user_agent: str,
        login_method: str = LoginMethod.PASSWORD,
        **extra_fields,
    ) -> "UserSession":
        """
        Create user session with device detection.

        Args:
            user: User instance
            ip_address: Client IP address
            user_agent: Client user agent string
            login_method: Authentication method used
            **extra_fields: Additional session fields

        Returns:
            UserSession instance

        Raises:
            ValidationException: If session creation fails
        """
        try:
            # Detect device type from user agent
            device_type = SessionService._detect_device_type(user_agent)

            # Create session using manager method
            session = UserSession.objects.create_session(
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
                login_method=login_method,
                device_type=device_type,
                **extra_fields,
            )

            logger.info(
                f"Session created for user {user.email}: {device_type} - {login_method}"
            )
            return session

        except Exception as e:
            logger.error(f"Session creation failed for {user.email}: {str(e)}")
            raise ValidationException(_("Failed to create user session"))

    @staticmethod
    @transaction.atomic
    def terminate_user_session(
        user: "User", session_key: str, reason: str = "user_logout"
    ) -> Dict:
        """
        Terminate specific user session.

        Args:
            user: User instance
            session_key: Session key to terminate
            reason: Reason for termination

        Returns:
            Dict containing termination status and details

        Raises:
            SessionNotFoundException: If session not found
        """
        try:
            # Get session
            try:
                session = UserSession.objects.get(
                    session_key=session_key, user=user, is_active=True
                )
            except UserSession.DoesNotExist:
                raise SessionNotFoundException(
                    _("Session not found or already terminated")
                )

            # Terminate session
            session.terminate(reason=reason)

            logger.info(
                f"Session terminated for {user.email}: {session_key} - {reason}"
            )

            return {
                "session_key": session_key,
                "user_email": user.email,
                "terminated": True,
                "reason": reason,
                "terminated_at": session.updated_at,
                "message": _("Session terminated successfully"),
            }

        except SessionNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Session termination failed for {user.email}: {str(e)}")
            raise ValidationException(_("Failed to terminate session"))

    @staticmethod
    @transaction.atomic
    def terminate_all_sessions(
        user: "User", exclude_session: str = None, reason: str = "logout_all_devices"
    ) -> Dict:
        """
        Terminate all user sessions with optional exclusion.

        Args:
            user: User instance
            exclude_session: Session key to exclude from termination (optional)
            reason: Reason for bulk termination

        Returns:
            Dict containing termination statistics
        """
        try:
            # Get active sessions
            active_sessions = UserSession.objects.active_for_user(user)

            # Exclude specific session if provided
            if exclude_session:
                active_sessions = active_sessions.exclude(session_key=exclude_session)

            # Count and terminate sessions
            session_count = active_sessions.count()
            terminated_sessions = []

            for session in active_sessions:
                session.terminate(reason=reason)
                terminated_sessions.append(
                    {
                        "session_key": session.session_key,
                        "device_type": session.device_type,
                        "login_method": session.login_method,
                        "last_activity": session.last_activity,
                    }
                )

            logger.info(
                f"All sessions terminated for {user.email}: {session_count} sessions "
                f"- {reason}"
            )

            return {
                "user_email": user.email,
                "terminated_count": session_count,
                "excluded_session": exclude_session,
                "reason": reason,
                "terminated_sessions": terminated_sessions,
                "message": _("All sessions terminated successfully"),
            }

        except Exception as e:
            logger.error(f"Bulk session termination failed for {user.email}: {str(e)}")
            raise ValidationException(_("Failed to terminate sessions"))

    @staticmethod
    def get_active_sessions(user: "User", include_details: bool = True) -> Dict:
        """
        Get all active sessions for user.

        Args:
            user: User instance
            include_details: Whether to include detailed session info

        Returns:
            Dict containing active sessions and statistics
        """
        try:
            active_sessions = UserSession.objects.active_for_user(user)

            sessions_data = []
            for session in active_sessions:
                session_info = {
                    "session_key": session.session_key,
                    "device_type": session.device_type,
                    "device_type_display": session.get_device_type_display(),
                    "login_method": session.login_method,
                    "login_method_display": session.get_login_method_display(),
                    "login_at": session.login_at,
                    "last_activity": session.last_activity,
                    "expires_at": session.expires_at,
                    "is_expired": session.is_expired,
                    "is_valid": session.is_valid,
                }

                # Add detailed info if requested
                if include_details:
                    session_info.update(
                        {
                            "ip_address": session.ip_address,
                            "user_agent": session.user_agent,
                            "session_duration": (
                                timezone.now() - session.login_at
                            ).total_seconds(),
                            "time_until_expiry": (
                                session.expires_at - timezone.now()
                            ).total_seconds()
                            if not session.is_expired
                            else 0,
                        }
                    )

                sessions_data.append(session_info)

            # Sort by last activity (most recent first)
            sessions_data.sort(key=lambda x: x["last_activity"], reverse=True)

            return {
                "user_email": user.email,
                "total_sessions": len(sessions_data),
                "sessions": sessions_data,
                "has_active_sessions": len(sessions_data) > 0,
            }

        except Exception as e:
            logger.error(f"Failed to get active sessions for {user.email}: {str(e)}")
            return {
                "user_email": user.email,
                "total_sessions": 0,
                "sessions": [],
                "has_active_sessions": False,
                "error": _("Failed to retrieve sessions"),
            }

    # ================================================================
    # HELPER METHODS (Private)
    # ================================================================

    @staticmethod
    def _detect_device_type(user_agent: str) -> str:
        """
        Detect device type from user agent string.

        Args:
            user_agent: User agent string

        Returns:
            Device type constant
        """
        if not user_agent:
            return DeviceType.UNKNOWN

        user_agent_lower = user_agent.lower()

        # Mobile device detection
        mobile_indicators = [
            "mobile",
            "android",
            "iphone",
            "ipod",
            "blackberry",
            "windows phone",
            "nokia",
            "opera mini",
            "mobile safari",
        ]

        # Tablet detection
        tablet_indicators = ["ipad", "tablet", "kindle"]

        # Check for tablet first (more specific)
        if any(indicator in user_agent_lower for indicator in tablet_indicators):
            return DeviceType.TABLET

        # Check for mobile
        if any(indicator in user_agent_lower for indicator in mobile_indicators):
            return DeviceType.MOBILE

        # Default to desktop
        return DeviceType.DESKTOP

    @staticmethod
    def verify_session(session_key: str, user: "User") -> Optional["UserSession"]:
        """
        Verify session is valid and update last activity.

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
                # Session expired, terminate it
                session.terminate(reason="session_expired")
                return None

        except UserSession.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Session verification failed: {str(e)}")
            return None

    @staticmethod
    def cleanup_expired_sessions() -> Dict:
        """
        Clean up expired sessions.

        Returns:
            Dict containing cleanup statistics
        """
        try:
            # Get expired sessions that are still active
            expired_sessions = UserSession.objects.filter(
                expires_at__lt=timezone.now(), is_active=True
            )

            count = expired_sessions.count()

            # Terminate expired sessions
            for session in expired_sessions:
                session.terminate(reason="session_expired")

            logger.info(f"Cleaned up {count} expired sessions")

            return {
                "expired_sessions_cleaned": count,
                "message": _("Expired sessions cleaned up successfully"),
            }

        except Exception as e:
            logger.error(f"Session cleanup failed: {str(e)}")
            return {"expired_sessions_cleaned": 0, "error": _("Session cleanup failed")}

    @staticmethod
    def get_session_statistics() -> Dict:
        """
        Get session usage statistics.

        Returns:
            Dict containing session statistics
        """
        try:
            now = timezone.now()

            stats = {
                "total_sessions": UserSession.objects.count(),
                "active_sessions": UserSession.objects.filter(is_active=True).count(),
                "expired_sessions": UserSession.objects.filter(
                    expires_at__lt=now
                ).count(),
                "sessions_by_device": {},
                "sessions_by_login_method": {},
            }

            # Count by device type
            for device_type in DeviceType.choices:
                count = UserSession.objects.filter(
                    device_type=device_type[0], is_active=True
                ).count()
                if count > 0:
                    stats["sessions_by_device"][device_type[1]] = count

            # Count by login method
            for login_method in LoginMethod.choices:
                count = UserSession.objects.filter(
                    login_method=login_method[0], is_active=True
                ).count()
                if count > 0:
                    stats["sessions_by_login_method"][login_method[1]] = count

            return stats

        except Exception as e:
            logger.error(f"Failed to get session statistics: {str(e)}")
            return {}

    @staticmethod
    def update_session_activity(session_key: str) -> bool:
        """
        Update session last activity timestamp.

        Args:
            session_key: Session key to update

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            session = UserSession.objects.get(session_key=session_key, is_active=True)

            # Only update if session is still valid
            if session.is_valid:
                session.last_activity = timezone.now()
                session.save(update_fields=["last_activity"])
                return True
            else:
                # Session expired, terminate it
                session.terminate(reason="session_expired")
                return False

        except UserSession.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Failed to update session activity: {str(e)}")
            return False


# ================================================================
# CONVENIENCE FUNCTIONS
# ================================================================


def create_user_session(
    user: "User",
    ip_address: str,
    user_agent: str,
    login_method: str = LoginMethod.PASSWORD,
    **extra_fields,
) -> "UserSession":
    """Convenience function for session creation."""
    return SessionService.create_user_session(
        user, ip_address, user_agent, login_method, **extra_fields
    )


def terminate_user_session(
    user: "User", session_key: str, reason: str = "user_logout"
) -> Dict:
    """Convenience function for session termination."""
    return SessionService.terminate_user_session(user, session_key, reason)


def terminate_all_sessions(
    user: "User", exclude_session: str = None, reason: str = "logout_all_devices"
) -> Dict:
    """Convenience function for bulk session termination."""
    return SessionService.terminate_all_sessions(user, exclude_session, reason)


def get_active_sessions(user: "User", include_details: bool = True) -> Dict:
    """Convenience function for getting active sessions."""
    return SessionService.get_active_sessions(user, include_details)
