"""
Essential OAuth services for Movie Nexus.
"""

import logging
from typing import TYPE_CHECKING, Dict

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from core.constants import AuthProvider, LoginMethod
from core.exceptions import AuthenticationException, ValidationException

# Type hints only
if TYPE_CHECKING:
    from apps.users.models import Profile as UserProfile

    from ..models import SocialAuth, User, UserSession
else:
    # Runtime imports
    from django.contrib.auth import get_user_model

    from apps.users.models import Profile as UserProfile

    from ..models import SocialAuth, UserSession

    User = get_user_model()

logger = logging.getLogger(__name__)


class OAuthService:
    """
    Essential OAuth service for Movie Nexus.
    Handles Google OAuth login and account linking.
    """

    @staticmethod
    @transaction.atomic
    def google_oauth_login(access_token: str, request=None) -> Dict:
        """
        Google OAuth login/registration flow.

        Args:
            access_token: Google OAuth access token
            request: HTTP request object (for session creation)

        Returns:
            Dict containing user, session, tokens, and status

        Raises:
            ValidationException: If OAuth validation fails
            AuthenticationException: If authentication fails
        """
        try:
            # Validate Google token and get user data
            google_user_data = OAuthService.validate_oauth_token(
                access_token, AuthProvider.GOOGLE
            )

            google_id = str(google_user_data["id"])
            google_email = google_user_data["email"].lower().strip()

            # Try to find existing social auth
            try:
                social_auth = SocialAuth.objects.get(
                    provider=AuthProvider.GOOGLE,
                    provider_user_id=google_id,
                    is_active=True,
                )
                user = social_auth.user
                created = False

                # Update access token
                social_auth.access_token = access_token
                social_auth.provider_data = google_user_data
                social_auth.save(
                    update_fields=["access_token", "provider_data", "updated_at"]
                )

            except SocialAuth.DoesNotExist:
                # Try to find user by email
                try:
                    user = User.objects.get(email=google_email, is_active=True)
                    created = False
                except User.DoesNotExist:
                    # Create new user
                    user = OAuthService._create_user_from_google(google_user_data)
                    created = True

                # Create social auth record
                social_auth = SocialAuth.objects.create(
                    user=user,
                    provider=AuthProvider.GOOGLE,
                    provider_user_id=google_id,
                    provider_email=google_email,
                    access_token=access_token,
                    provider_data=google_user_data,
                )

            # Create user session
            session = UserSession.objects.create_session(
                user=user,
                ip_address=request.META.get("REMOTE_ADDR", "127.0.0.1")
                if request
                else "127.0.0.1",
                user_agent=request.META.get("HTTP_USER_AGENT", "Unknown")
                if request
                else "Unknown",
                login_method=LoginMethod.GOOGLE,
            )

            # Generate JWT tokens (import here to avoid circular imports)
            from .auth_service import AuthenticationService

            tokens = AuthenticationService.generate_jwt_tokens(user, session)

            logger.info(
                f"Google OAuth login successful: {google_email} (created: {created})"
            )

            return {
                "user": user,
                "social_auth": social_auth,
                "session": session,
                "tokens": tokens,
                "created": created,
                "authenticated": True,
                "message": _("Google login successful"),
            }

        except (ValidationException, AuthenticationException):
            raise
        except Exception as e:
            logger.error(f"Google OAuth login failed: {str(e)}")
            raise AuthenticationException(_("Google authentication failed"))

    @staticmethod
    @transaction.atomic
    def link_social_account(
        user: "User", access_token: str, provider: str = AuthProvider.GOOGLE
    ) -> Dict:
        """
        Link OAuth account to existing authenticated user.

        Args:
            user: Authenticated user instance
            access_token: OAuth access token
            provider: OAuth provider (default: Google)

        Returns:
            Dict containing social auth info and status

        Raises:
            ValidationException: If linking fails
        """
        try:
            # Validate OAuth token
            provider_data = OAuthService.validate_oauth_token(access_token, provider)

            provider_user_id = str(provider_data["id"])
            provider_email = provider_data["email"].lower().strip()

            # Check if this OAuth account is already linked to another user
            existing_social = SocialAuth.objects.filter(
                provider=provider, provider_user_id=provider_user_id, is_active=True
            ).first()

            if existing_social and existing_social.user != user:
                raise ValidationException(
                    _("This social account is already linked to another user")
                )

            # Create or update social auth
            social_auth, created = SocialAuth.objects.update_or_create(
                user=user,
                provider=provider,
                provider_user_id=provider_user_id,
                defaults={
                    "provider_email": provider_email,
                    "access_token": access_token,
                    "provider_data": provider_data,
                    "is_active": True,
                },
            )

            logger.info(
                f"Social account linked: {user.email} -> {provider} "
                f"(created: {created})"
            )

            return {
                "user": user,
                "social_auth": social_auth,
                "linked": True,
                "created": created,
                "message": _("Social account linked successfully")
                if created
                else _("Social account updated"),
            }

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Social account linking failed for {user.email}: {str(e)}")
            raise ValidationException(_("Failed to link social account"))

    @staticmethod
    def validate_oauth_token(access_token: str, provider: str) -> Dict:
        """
        Validate OAuth token and return user data.

        Args:
            access_token: OAuth access token
            provider: OAuth provider

        Returns:
            Dict containing user data from OAuth provider

        Raises:
            ValidationException: If token validation fails
        """
        try:
            if not access_token or len(access_token.strip()) < 20:
                raise ValidationException(_("Invalid access token"))

            if provider == AuthProvider.GOOGLE:
                return OAuthService._validate_google_token(access_token)
            else:
                raise ValidationException(_("Unsupported OAuth provider"))

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"OAuth token validation failed: {str(e)}")
            raise ValidationException(_("OAuth token validation failed"))

    # ================================================================
    # HELPER METHODS (Private)
    # ================================================================

    @staticmethod
    def _validate_google_token(access_token: str) -> Dict:
        """
        Validate Google OAuth token.

        Note: This is a simplified version for deadline.
        In production, you'd verify with Google's API.
        """
        try:
            # TODO: In production, verify token with Google API
            # For now, return mock data for development

            # In real implementation, you would do:
            # response = requests.get(
            #     'https://www.googleapis.com/oauth2/v2/userinfo',
            #     headers={'Authorization': f'Bearer {access_token}'}
            # )
            # return response.json()

            # Mock data for development (REMOVE IN PRODUCTION)
            mock_data = {
                "id": "123456789",
                "email": "test@gmail.com",
                "name": "Test User",
                "given_name": "Test",
                "family_name": "User",
                "picture": "https://example.com/photo.jpg",
                "verified_email": True,
            }

            logger.warning("Using mock Google OAuth data - REPLACE IN PRODUCTION")
            return mock_data

        except Exception as e:
            logger.error(f"Google token validation failed: {str(e)}")
            raise ValidationException(_("Invalid Google token"))

    @staticmethod
    def _create_user_from_google(google_data: Dict) -> "User":
        """Create new user from Google OAuth data."""
        try:
            email = google_data["email"].lower().strip()

            # Parse name
            first_name = google_data.get("given_name", "").strip() or "User"
            last_name = google_data.get("family_name", "").strip() or ""

            # If no given/family names, parse from full name
            if not first_name or first_name == "User":
                full_name = google_data.get("name", "").strip()
                if full_name:
                    name_parts = full_name.split(" ", 1)
                    first_name = name_parts[0] or "User"
                    last_name = name_parts[1] if len(name_parts) > 1 else ""

            # Create user
            user = User.objects.create_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_email_verified=True,  # Google emails are pre-verified
                avatar=google_data.get("picture", ""),
            )

            # Create profile
            UserProfile.objects.create(user=user)

            logger.info(f"New user created from Google OAuth: {email}")
            return user

        except Exception as e:
            logger.error(f"Failed to create user from Google data: {str(e)}")
            raise

    @staticmethod
    def get_user_social_accounts(user: "User") -> Dict:
        """
        Get all linked social accounts for user.

        Args:
            user: User instance

        Returns:
            Dict containing social accounts info
        """
        try:
            social_accounts = SocialAuth.objects.filter(user=user, is_active=True)

            accounts_data = []
            for account in social_accounts:
                accounts_data.append(
                    {
                        "id": account.id,
                        "provider": account.provider,
                        "provider_display": account.get_provider_display(),
                        "provider_email": account.provider_email,
                        "created_at": account.created_at,
                        "is_active": account.is_active,
                    }
                )

            return {"total_accounts": len(accounts_data), "accounts": accounts_data}

        except Exception as e:
            logger.error(f"Failed to get social accounts for {user.email}: {str(e)}")
            return {"total_accounts": 0, "accounts": []}


# ================================================================
# CONVENIENCE FUNCTIONS
# ================================================================


def google_oauth_login(access_token: str, request=None) -> Dict:
    """Convenience function for Google OAuth login."""
    return OAuthService.google_oauth_login(access_token, request)


def link_social_account(
    user: "User", access_token: str, provider: str = AuthProvider.GOOGLE
) -> Dict:
    """Convenience function for linking social accounts."""
    return OAuthService.link_social_account(user, access_token, provider)


def validate_oauth_token(access_token: str, provider: str) -> Dict:
    """Convenience function for OAuth token validation."""
    return OAuthService.validate_oauth_token(access_token, provider)
