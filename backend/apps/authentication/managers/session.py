"""
Custom managers for UserSession model.
"""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.constants import DeviceType, LoginMethod


class UserSessionManager(models.Manager):
    """
    Custom manager for UserSession.
    """

    def get_queryset(self):
        """Optimize default queryset with select_related for user data."""
        return super().get_queryset().select_related("user").filter(is_active=True)

    def get_by_session_key(self, session_key):
        """Get session by session key."""
        return self.get(session_key=session_key)

    def get_valid_session(self, session_key):
        """Get valid (active, non-expired) session by key."""
        session = self.get_by_session_key(session_key)
        if not session.is_valid:
            raise ValueError(_("Invalid or expired session"))
        return session

    def active_for_user(self, user):
        """Get all active sessions for a specific user."""
        return self.filter(user=user).order_by("-last_activity")

    def valid_sessions(self):
        """Get all valid (active, non-expired) sessions."""
        now = timezone.now()
        return self.filter(expires_at__gt=now)

    def create_session(
        self,
        user,
        ip_address,
        user_agent,
        login_method=LoginMethod.PASSWORD,
        **extra_fields,
    ):
        """Create a new user session."""
        # Simple device type detection
        device_type = DeviceType.DESKTOP  # Default value

        if "device_type" not in extra_fields:
            # Device detection logic
            if user_agent:
                user_agent_lower = user_agent.lower()

                # Check for tablet first (more specific)
                if any(
                    tablet in user_agent_lower
                    for tablet in ["ipad", "tablet", "kindle"]
                ):
                    device_type = DeviceType.TABLET
                # Check for mobile
                elif any(
                    mobile in user_agent_lower
                    for mobile in [
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
                ):
                    device_type = DeviceType.MOBILE
                # Desktop is already set as default
            else:
                device_type = DeviceType.UNKNOWN

            extra_fields["device_type"] = device_type

        # Create the session with all fields
        session = self.create(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            login_method=login_method,
            **extra_fields,  # This now includes device_type
        )

        return session

    def terminate_user_sessions(self, user, exclude_session=None):
        """Terminate all sessions for a user."""
        sessions = self.active_for_user(user)

        if exclude_session:
            sessions = sessions.exclude(session_key=exclude_session)

        count = sessions.count()
        for session in sessions:
            session.terminate()

        return count
