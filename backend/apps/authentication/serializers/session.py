"""
Session serializers for Movie Nexus.
"""

from rest_framework import serializers

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from core.mixins.serializers import BaseAuthSerializerMixin

from ..models import UserSession

User = get_user_model()


class UserSessionSerializer(BaseAuthSerializerMixin, serializers.ModelSerializer):
    """
    Essential user session serializer for viewing sessions.
    """

    # Read-only computed fields
    user_email = serializers.EmailField(source="user.email", read_only=True)
    login_method_display = serializers.CharField(
        source="get_login_method_display", read_only=True
    )
    device_type_display = serializers.CharField(
        source="get_device_type_display", read_only=True
    )
    is_expired = serializers.ReadOnlyField()
    is_valid = serializers.ReadOnlyField()
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = [
            "id",
            "user",
            "user_email",
            "session_key",
            "login_method",
            "login_method_display",
            "device_type",
            "device_type_display",
            "ip_address",
            "user_agent",
            "login_at",
            "last_activity",
            "expires_at",
            "is_active",
            "is_expired",
            "is_valid",
            "is_current",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "user": {"read_only": True},
            "session_key": {"read_only": True},
            "login_at": {"read_only": True},
            "last_activity": {"read_only": True},
        }

    def get_is_current(self, obj):
        """Check if this is the current user's session."""
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user == obj.user:
            # You could implement session key comparison here if needed
            return True
        return False

    def to_representation(self, instance):
        """Customize representation based on user permissions."""
        data = super().to_representation(instance)

        # Hide sensitive data if not owner
        request = self.context.get("request")
        if request and request.user != instance.user and not request.user.is_staff:
            # Hide sensitive fields for non-owners
            sensitive_fields = ["ip_address", "user_agent", "session_key"]
            for field in sensitive_fields:
                data.pop(field, None)

        return data


class SessionListSerializer(BaseAuthSerializerMixin, serializers.Serializer):
    """
    Essential serializer for listing user sessions.
    """

    def to_representation(self, instance):
        """Return list of user sessions."""
        user = self.context.get("user") or self.current_user

        if not user:
            return {"sessions": []}

        # Get user's active sessions
        sessions = UserSession.objects.active_for_user(user)

        # Serialize sessions
        session_serializer = UserSessionSerializer(
            sessions, many=True, context=self.context
        )

        return {
            "sessions": session_serializer.data,
            "total_sessions": sessions.count(),
            "message": _("Active sessions retrieved successfully"),
        }


class SessionTerminateSerializer(BaseAuthSerializerMixin, serializers.Serializer):
    """
    Essential serializer for terminating sessions.
    """

    session_id = serializers.UUIDField(required=False)
    terminate_all = serializers.BooleanField(default=False)
    terminate_others = serializers.BooleanField(default=False)

    def validate(self, attrs):
        """Validate session termination request."""
        session_id = attrs.get("session_id")
        terminate_all = attrs.get("terminate_all")
        terminate_others = attrs.get("terminate_others")

        # Must specify either session_id or terminate_all/others
        if not session_id and not terminate_all and not terminate_others:
            raise serializers.ValidationError(
                _("Must specify session_id, terminate_all, or terminate_others")
            )

        # Can't specify both session_id and terminate_all/others
        if session_id and (terminate_all or terminate_others):
            raise serializers.ValidationError(
                _("Cannot specify session_id with terminate_all or terminate_others")
            )

        # Validate session exists and belongs to user
        if session_id:
            try:
                session = UserSession.objects.get(
                    id=session_id, user=self.current_user, is_active=True
                )
                attrs["session"] = session
            except UserSession.DoesNotExist:
                raise serializers.ValidationError(_("Session not found"))

        return attrs

    def create(self, validated_data):
        """Terminate session(s)."""
        user = self.current_user
        session = validated_data.get("session")
        terminate_all = validated_data.get("terminate_all")
        terminate_others = validated_data.get("terminate_others")

        terminated_count = 0

        if session:
            # Terminate specific session
            session.terminate("user_request")
            terminated_count = 1

        elif terminate_all:
            # Terminate all user sessions
            terminated_count = UserSession.objects.terminate_user_sessions(user)

        elif terminate_others:
            # Terminate all other sessions (keep current)
            request = self.context.get("request")
            current_session_key = (
                getattr(request, "session_key", None) if request else None
            )
            terminated_count = UserSession.objects.terminate_user_sessions(
                user, exclude_session=current_session_key
            )

        return {
            "terminated_count": terminated_count,
            "action": "terminate_specific"
            if session
            else "terminate_all"
            if terminate_all
            else "terminate_others",
        }

    def to_representation(self, instance):
        """Return session termination response."""
        terminated_count = instance["terminated_count"]
        action = instance["action"]

        action_messages = {
            "terminate_specific": _("Session terminated successfully"),
            "terminate_all": _("All sessions terminated successfully"),
            "terminate_others": _("Other sessions terminated successfully"),
        }

        message = action_messages.get(action, _("Sessions terminated"))

        return {
            "message": message,
            "terminated_count": terminated_count,
            "action": action,
        }


class CurrentSessionSerializer(BaseAuthSerializerMixin, serializers.Serializer):
    """
    Essential serializer for getting current session info.
    """

    def to_representation(self, instance):
        """Return current session information."""
        request = self.context.get("request")
        user = self.current_user

        if not user or not request:
            return {"session": None}

        # Try to find current session (simplified approach)
        current_session = UserSession.objects.active_for_user(user).first()

        if current_session:
            session_serializer = UserSessionSerializer(
                current_session, context=self.context
            )
            return {
                "session": session_serializer.data,
                "message": _("Current session retrieved successfully"),
            }

        return {
            "session": None,
            "message": _("No active session found"),
        }
