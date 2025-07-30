"""
Session management views for Movie Nexus.
Handles user session listing, termination, and current session information.
"""

import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from django.utils.translation import gettext_lazy as _

from core.exceptions import SessionNotFoundException, ValidationException
from core.responses import APIResponse

from ..serializers import SessionTerminateSerializer, UserSessionSerializer
from ..services import (
    get_active_sessions,
    terminate_all_sessions,
    terminate_user_session,
)
from ..services.session_service import SessionService

logger = logging.getLogger(__name__)


class UserSessionListView(APIView):
    """
    List user's active sessions endpoint.

    GET /api/v1/auth/sessions/
    - Returns list of user's active sessions with device information

    Query Parameters:
    - include_details: boolean (default: true) - Include detailed session info
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        """Get list of user's active sessions."""
        try:
            user = request.user

            # Get query parameters
            include_details = (
                request.query_params.get("include_details", "true").lower() == "true"
            )

            # Get active sessions using service
            session_data = get_active_sessions(user, include_details=include_details)

            # Identify current session if possible
            current_session_key = getattr(request, "session_key", None)
            current_session_id = None

            # Try to get session ID from JWT token
            if hasattr(request, "auth") and request.auth:
                try:
                    from rest_framework_simplejwt.tokens import UntypedToken

                    token = UntypedToken(str(request.auth))
                    current_session_id = token.payload.get("session_id")
                except Exception:
                    pass

            # Mark current session in the response
            sessions = session_data.get("sessions", [])
            for session in sessions:
                if (
                    current_session_id
                    and session.get("session_key") == current_session_id
                ):
                    session["is_current"] = True
                elif (
                    current_session_key
                    and session.get("session_key") == current_session_key
                ):
                    session["is_current"] = True
                else:
                    session["is_current"] = False

            # Prepare response data
            response_data = {
                "total_sessions": session_data.get("total_sessions", 0),
                "has_active_sessions": session_data.get("has_active_sessions", False),
                "sessions": sessions,
                "current_session_identified": any(
                    s.get("is_current") for s in sessions
                ),
            }

            logger.info(
                f"Session list retrieved for user: {user.email} "
                f"({response_data['total_sessions']} sessions)"
            )

            return APIResponse.success(
                message=_("Active sessions retrieved successfully"), data=response_data
            )

        except Exception as e:
            logger.error(f"Session list error for {request.user.email}: {str(e)}")
            return APIResponse.server_error(message=_("Failed to retrieve sessions"))


class SessionTerminateView(APIView):
    """
    Session termination endpoint.

    POST /api/v1/auth/sessions/terminate/
    {
        "session_key": "session_key_here",    // Terminate specific session
        OR
        "session_id": "session_uuid_here",    // Terminate by session ID
        OR
        "terminate_all": true,                // Terminate all sessions
        OR
        "terminate_others": true              // Terminate all except current
    }
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    serializer_class = SessionTerminateSerializer

    def post(self, request):
        """Terminate user sessions."""
        try:
            user = request.user

            # Validate input data
            serializer = self.serializer_class(
                data=request.data, context={"request": request}
            )

            if not serializer.is_valid():
                return APIResponse.validation_error(
                    message=_("Invalid session termination data"),
                    field_errors=serializer.errors,
                )

            # Get validated data
            session_key = serializer.validated_data.get("session_key")
            session_id = serializer.validated_data.get("session_id")
            terminate_all = serializer.validated_data.get("terminate_all", False)
            terminate_others = serializer.validated_data.get("terminate_others", False)

            terminated_count = 0
            action_type = "unknown"

            try:
                if session_key:
                    # Terminate specific session by key
                    result = terminate_user_session(
                        user=user, session_key=session_key, reason="user_termination"
                    )
                    terminated_count = 1 if result["terminated"] else 0
                    action_type = "terminate_specific"

                elif session_id:
                    # Find session by ID and terminate
                    from ..models import UserSession

                    try:
                        session = UserSession.objects.get(
                            id=session_id, user=user, is_active=True
                        )
                        result = terminate_user_session(
                            user=user,
                            session_key=session.session_key,
                            reason="user_termination",
                        )
                        terminated_count = 1 if result["terminated"] else 0
                        action_type = "terminate_specific"

                    except UserSession.DoesNotExist:
                        raise SessionNotFoundException(_("Session not found"))

                elif terminate_all:
                    # Terminate all user sessions
                    result = terminate_all_sessions(user=user, reason="user_logout_all")
                    terminated_count = result["terminated_count"]
                    action_type = "terminate_all"

                elif terminate_others:
                    # Terminate all sessions except current
                    current_session_key = getattr(request, "session_key", None)

                    # Try to get current session from JWT token
                    if (
                        not current_session_key
                        and hasattr(request, "auth")
                        and request.auth
                    ):
                        try:
                            from rest_framework_simplejwt.tokens import UntypedToken

                            token = UntypedToken(str(request.auth))
                            current_session_id = token.payload.get("session_id")

                            if current_session_id:
                                from ..models import UserSession

                                try:
                                    current_session = UserSession.objects.get(
                                        id=current_session_id
                                    )
                                    current_session_key = current_session.session_key
                                except UserSession.DoesNotExist:
                                    pass
                        except Exception:
                            pass

                    result = terminate_all_sessions(
                        user=user,
                        exclude_session=current_session_key,
                        reason="user_logout_others",
                    )
                    terminated_count = result["terminated_count"]
                    action_type = "terminate_others"

                else:
                    return APIResponse.validation_error(
                        message=_("Must specify termination method")
                    )

                # Prepare response messages
                action_messages = {
                    "terminate_specific": _("Session terminated successfully"),
                    "terminate_all": _("All sessions terminated successfully"),
                    "terminate_others": _("Other sessions terminated successfully"),
                }

                message = action_messages.get(action_type, _("Sessions terminated"))

                logger.info(
                    f"Session termination completed for {user.email}: {action_type} - "
                    f"{terminated_count} sessions"
                )

                return APIResponse.success(
                    message=message,
                    data={
                        "terminated_count": terminated_count,
                        "action": action_type,
                        "user_email": user.email,
                    },
                )

            except SessionNotFoundException as e:
                logger.warning(
                    f"Session termination failed - session not found: {user.email}"
                )
                return APIResponse.not_found(message=str(e.detail))

            except ValidationException as e:
                return APIResponse.validation_error(message=str(e.detail))

        except Exception as e:
            logger.error(
                f"Session termination error for {request.user.email}: {str(e)}"
            )
            return APIResponse.server_error(message=_("Failed to terminate sessions"))


class CurrentSessionView(APIView):
    """
    Current session information endpoint.

    GET /api/v1/auth/sessions/current/
    - Returns information about the current user session
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        """Get current session information."""
        try:
            user = request.user
            current_session = None
            session_identified = False

            # Method 1: Try to get session from JWT token
            if hasattr(request, "auth") and request.auth:
                try:
                    from rest_framework_simplejwt.tokens import UntypedToken

                    token = UntypedToken(str(request.auth))
                    session_id = token.payload.get("session_id")

                    if session_id:
                        from ..models import UserSession

                        try:
                            current_session = UserSession.objects.get(
                                id=session_id, user=user, is_active=True
                            )
                            session_identified = True
                        except UserSession.DoesNotExist:
                            logger.warning(
                                f"Session ID from token not found: {session_id}"
                            )
                            pass
                except Exception as e:
                    logger.debug(f"Failed to extract session from JWT token: {str(e)}")
                    pass

            # Method 2: Try to get session from request session key
            if not current_session:
                session_key = getattr(request, "session_key", None)
                if session_key:
                    from ..models import UserSession

                    try:
                        current_session = UserSession.objects.get(
                            session_key=session_key, user=user, is_active=True
                        )
                        session_identified = True
                    except UserSession.DoesNotExist:
                        pass

            # Method 3: Fallback - get most recent active session
            if not current_session:
                from ..models import UserSession

                current_session = UserSession.objects.active_for_user(user).first()
                if current_session:
                    logger.info(
                        f"Using most recent session as current for user: {user.email}"
                    )

            # Prepare response
            if current_session:
                # Serialize session data
                session_serializer = UserSessionSerializer(
                    current_session, context={"request": request}
                )

                session_data = session_serializer.data
                session_data["is_current"] = True
                session_data["identification_method"] = (
                    "jwt_token"
                    if session_identified and hasattr(request, "auth")
                    else "session_key"
                    if session_identified
                    else "most_recent"
                )

                # Update session activity
                SessionService.update_session_activity(current_session.session_key)

                logger.info(f"Current session retrieved for user: {user.email}")

                return APIResponse.success(
                    message=_("Current session retrieved successfully"),
                    data={
                        "session": session_data,
                        "session_identified": session_identified,
                    },
                )
            else:
                logger.warning(f"No active sessions found for user: {user.email}")
                return APIResponse.success(
                    message=_("No active session found"),
                    data={"session": None, "session_identified": False},
                )

        except Exception as e:
            logger.error(f"Current session error for {request.user.email}: {str(e)}")
            return APIResponse.server_error(
                message=_("Failed to retrieve current session information")
            )
