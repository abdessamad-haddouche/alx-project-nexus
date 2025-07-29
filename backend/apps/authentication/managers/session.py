"""
Custom managers for UserSession model.
"""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.constants import DeviceType, LoginMethod, SessionStatus
from core.exceptions import SessionNotFoundException, ValidationException


class UserSessionManager(models.Manager):
    """
    Custom manager for UserSession with session-specific queries and optimizations.
    """

    def get_queryset(self):
        """Optimize default queryset with select_related for user data."""
        return super().get_queryset().select_related("user").filter(is_active=True)

    def all_with_inactive(self):
        """Get all sessions including inactive ones."""
        return super().get_queryset().select_related("user")

    def get_by_session_key(self, session_key):
        """
        Get session by session key with proper exception handling.

        Args:
            session_key: Session key string

        Returns:
            UserSession instance

        Raises:
            UserNotFoundException: If session not found
        """
        try:
            return self.get(session_key=session_key)
        except self.model.DoesNotExist:
            raise SessionNotFoundException(
                detail=_("Session not found"),
                extra_data={"session_key": session_key},
            )

    def get_valid_session(self, session_key):
        """
        Get valid (active, non-expired) session by key.

        Args:
            session_key: Session key string

        Returns:
            UserSession instance

        Raises:
            UserNotFoundException: If session not found
            ValidationException: If session is invalid
        """
        session = self.get_by_session_key(session_key)

        if not session.is_valid:
            if session.is_expired:
                raise ValidationException(
                    detail=_("Session has expired"),
                    extra_data={
                        "session_key": session_key,
                        "expired_at": session.expires_at,
                    },
                )
            elif session.status != SessionStatus.ACTIVE:
                raise ValidationException(
                    detail=_("Session is not active"),
                    extra_data={"session_key": session_key, "status": session.status},
                )
            else:
                raise ValidationException(
                    detail=_("Session is invalid"),
                    extra_data={"session_key": session_key},
                )

        return session

    def active_for_user(self, user):
        """
        Get all active sessions for a specific user.

        Args:
            user: User instance

        Returns:
            QuerySet of active UserSession instances
        """
        return self.filter(user=user, status=SessionStatus.ACTIVE).order_by(
            "-last_activity"
        )

    def by_device_type(self, device_type):
        """
        Get sessions by device type.

        Args:
            device_type: DeviceType enum value

        Returns:
            QuerySet of UserSession instances
        """
        return self.filter(device_type=device_type)

    def by_login_method(self, login_method):
        """
        Get sessions by login method.

        Args:
            login_method: LoginMethod enum value

        Returns:
            QuerySet of UserSession instances
        """
        return self.filter(login_method=login_method)

    def desktop_sessions(self):
        """Get all desktop sessions."""
        return self.by_device_type(DeviceType.DESKTOP)

    def mobile_sessions(self):
        """Get all mobile sessions."""
        return self.by_device_type(DeviceType.MOBILE)

    def password_logins(self):
        """Get all password-based login sessions."""
        return self.by_login_method(LoginMethod.PASSWORD)

    def oauth_logins(self):
        """Get all OAuth-based login sessions."""
        return self.filter(
            login_method__in=[
                LoginMethod.GOOGLE,
                LoginMethod.FACEBOOK,
                LoginMethod.APPLE,
            ]
        )

    def valid_sessions(self):
        """
        Get all valid (active, non-expired) sessions.

        Returns:
            QuerySet of valid UserSession instances
        """
        now = timezone.now()
        return self.filter(status=SessionStatus.ACTIVE, expires_at__gt=now)

    def expired_sessions(self):
        """
        Get all expired sessions.

        Returns:
            QuerySet of expired UserSession instances
        """
        now = timezone.now()
        return self.filter(expires_at__lte=now)

    def sessions_by_ip(self, ip_address):
        """
        Get sessions from specific IP address.

        Args:
            ip_address: IP address to filter by

        Returns:
            QuerySet of UserSession instances
        """
        return self.filter(ip_address=ip_address)

    def _parse_user_agent(self, user_agent):
        """
        Parse user agent string to extract device information.

        Args:
            user_agent: User agent string

        Returns:
            dict: Parsed device information
        """

        device_info = {
            "browser": "Unknown",
            "os": "Unknown",
            "device_type": DeviceType.UNKNOWN,
        }

        # TODO: Implement a user agent parset

        return device_info

    def create_session(
        self,
        user,
        ip_address,
        user_agent,
        login_method=LoginMethod.PASSWORD,
        **extra_fields,
    ):
        """
        Create a new user session.

        Args:
            user: User instance
            ip_address: Client IP address
            user_agent: User agent string
            login_method: Authentication method used
            **extra_fields: Additional fields

        Returns:
            UserSession instance
        """
        # Parse device information from user agent
        device_info = self._parse_user_agent(user_agent)

        session = self.create(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            login_method=login_method,
            device_info=device_info,
            device_type=device_info.get("device_type", DeviceType.UNKNOWN),
            **extra_fields,
        )

        return session

    def create_password_session(self, user, ip_address, user_agent, **extra_fields):
        """
        Create session for password-based login.

        Args:
            user: User instance
            ip_address: Client IP address
            user_agent: User agent string
            **extra_fields: Additional fields

        Returns:
            UserSession instance
        """
        return self.create_session(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            login_method=LoginMethod.PASSWORD,
            **extra_fields,
        )

    def create_oauth_session(
        self, user, provider, ip_address, user_agent, **extra_fields
    ):
        """
        Create session for OAuth-based login.

        Args:
            user: User instance
            provider: OAuth provider (google, facebook, etc.)
            ip_address: Client IP address
            user_agent: User agent string
            **extra_fields: Additional fields

        Returns:
            UserSession instance
        """
        # Map provider to login method
        provider_map = {
            "google": LoginMethod.GOOGLE,
            "facebook": LoginMethod.FACEBOOK,
            "apple": LoginMethod.APPLE,
        }

        login_method = provider_map.get(provider, LoginMethod.OAUTH)

        return self.create_session(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            login_method=login_method,
            **extra_fields,
        )

    def terminate_session(self, session_key, reason="user_logout"):
        """
        Terminate a specific session.

        Args:
            session_key: Session key to terminate
            reason: Reason for termination

        Returns:
            UserSession instance
        """
        session = self.get_by_session_key(session_key)
        session.terminate(reason)
        return session

    def terminate_user_sessions(self, user, reason="security", exclude_session=None):
        """
        Terminate all sessions for a user.

        Args:
            user: User instance
            reason: Reason for termination
            exclude_session: Session key to exclude from termination

        Returns:
            int: Number of sessions terminated
        """
        sessions = self.active_for_user(user)

        if exclude_session:
            sessions = sessions.exclude(session_key=exclude_session)

        count = sessions.count()
        for session in sessions:
            session.terminate(reason)

        return count

    def cleanup_expired_sessions(self):
        """
        Clean up expired sessions.

        Returns:
            int: Number of sessions cleaned up
        """
        return self.model.cleanup_expired()

    def cleanup_old_sessions(self, days_old=30):
        """
        Clean up old terminated sessions.

        Args:
            days_old: Remove sessions older than this many days

        Returns:
            int: Number of sessions cleaned up
        """
        return self.model.cleanup_old_terminated(days_old)
