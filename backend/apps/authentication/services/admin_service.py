"""
Admin management service for Movie Nexus.
Handles admin user creation, promotion, and management operations.
"""

import logging
from typing import TYPE_CHECKING, Dict, List

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from core.constants import UserRole
from core.exceptions import PermissionException, ValidationException

# Type hints only
if TYPE_CHECKING:
    from apps.users.models import Profile as UserProfile

    from ..models import User
else:
    # Runtime imports
    from django.contrib.auth import get_user_model

    from apps.users.models import Profile as UserProfile

logger = logging.getLogger(__name__)


class AdminService:
    """
    Admin management service.
    Handles admin creation, promotion, revocation, and management.
    """

    @staticmethod
    @transaction.atomic
    def create_admin_user(
        creator: "User",
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        role: str = UserRole.ADMIN,
        **extra_fields,
    ) -> Dict:
        """
        Create new admin user with proper validation and permissions.

        Args:
            creator: User creating the admin (must be superuser)
            email: Admin email address
            password: Admin password
            first_name: Admin first name
            last_name: Admin last name
            role: Admin role (ADMIN or MODERATOR)
            **extra_fields: Additional user fields

        Returns:
            Dict containing created admin and operation details

        Raises:
            PermissionException: If creator lacks permission
            ValidationException: If data validation fails
        """
        try:
            # Validate creator permissions
            if not creator.is_superuser:
                raise PermissionException(
                    _("Only superusers can create admin accounts")
                )

            # Normalize data
            email = email.lower().strip()
            first_name = first_name.strip()
            last_name = last_name.strip()

            # Basic validation
            if not all([email, password, first_name, last_name]):
                raise ValidationException(
                    _("Email, password, first name, and last name are required")
                )

            # Validate role
            if role not in [UserRole.ADMIN, UserRole.MODERATOR]:
                raise ValidationException(_("Role must be either admin or moderator"))

            # Check if user already exists
            if User.objects.filter(email=email).exists():
                raise ValidationException(_("User with this email already exists"))

            # Validate password strength
            try:
                validate_password(password)
            except ValidationError as e:
                raise ValidationException(
                    detail=_("Password does not meet requirements"),
                    field_errors={"password": str(e)},
                )

            # Set admin permissions based on role
            if role == UserRole.ADMIN:
                extra_fields.update(
                    {"is_staff": True, "is_superuser": False, "role": UserRole.ADMIN}
                )
            elif role == UserRole.MODERATOR:
                extra_fields.update(
                    {
                        "is_staff": True,
                        "is_superuser": False,
                        "role": UserRole.MODERATOR,
                    }
                )

            # Admin accounts are pre-verified
            extra_fields["is_email_verified"] = True

            # Create admin user
            admin_user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                **extra_fields,
            )

            # Create profile
            profile = UserProfile.objects.create(user=admin_user)

            logger.info(
                f"Admin user created: {email} (role: {role}) by {creator.email}"
            )

            return {
                "admin_user": admin_user,
                "profile": profile,
                "role": role,
                "created_by": creator,
                "message": _("Admin account created successfully"),
            }

        except (PermissionException, ValidationException):
            raise
        except Exception as e:
            logger.error(f"Failed to create admin user {email}: {str(e)}")
            raise ValidationException(_("Failed to create admin account"))

    @staticmethod
    @transaction.atomic
    def create_superadmin_user(
        creator: "User",
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        **extra_fields,
    ) -> Dict:
        """
        Create new superadmin user (highest privilege level).

        Args:
            creator: User creating the superadmin (must be superuser)
            email: SuperAdmin email address
            password: SuperAdmin password (must be strong)
            first_name: SuperAdmin first name
            last_name: SuperAdmin last name
            **extra_fields: Additional user fields

        Returns:
            Dict containing created superadmin and operation details

        Raises:
            PermissionException: If creator lacks permission
            ValidationException: If data validation fails
        """
        try:
            # Validate creator permissions - only superusers can create superusers
            if not creator.is_superuser:
                raise PermissionException(
                    _("Only superusers can create superadmin accounts")
                )

            # Normalize data
            email = email.lower().strip()
            first_name = first_name.strip()
            last_name = last_name.strip()

            # Basic validation
            if not all([email, password, first_name, last_name]):
                raise ValidationException(
                    _("Email, password, first name, and last name are required")
                )

            # Check if user already exists
            if User.objects.filter(email=email).exists():
                raise ValidationException(_("User with this email already exists"))

            # Extra strong password validation for superadmin
            try:
                validate_password(password)
            except ValidationError as e:
                raise ValidationException(
                    detail=_("Password does not meet requirements"),
                    field_errors={"password": str(e)},
                )

            if len(password) < 12:
                raise ValidationException(
                    _("SuperAdmin password must be at least 12 characters long")
                )

            # Set superadmin permissions
            extra_fields.update(
                {
                    "is_staff": True,
                    "is_superuser": True,
                    "role": UserRole.SUPERADMIN,
                    "is_email_verified": True,  # Pre-verified
                }
            )

            # Create superadmin user
            superadmin_user = User.objects.create_superuser(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                **extra_fields,
            )

            # Create profile
            profile = UserProfile.objects.create(user=superadmin_user)

            logger.info(f"SuperAdmin user created: {email} by {creator.email}")

            return {
                "superadmin_user": superadmin_user,
                "profile": profile,
                "created_by": creator,
                "message": _("SuperAdmin account created successfully"),
            }

        except (PermissionException, ValidationException):
            raise
        except Exception as e:
            logger.error(f"Failed to create superadmin user {email}: {str(e)}")
            raise ValidationException(_("Failed to create superadmin account"))

    @staticmethod
    @transaction.atomic
    def promote_user_to_admin(
        promoter: "User", user_id: int, role: str = UserRole.ADMIN
    ) -> Dict:
        """
        Promote existing user to admin role.

        Args:
            promoter: User performing the promotion (must be superuser)
            user_id: ID of user to promote
            role: Role to promote to (ADMIN or MODERATOR)

        Returns:
            Dict containing promotion details

        Raises:
            PermissionException: If promoter lacks permission
            ValidationException: If promotion is invalid
        """
        try:
            # Validate promoter permissions
            if not promoter.is_superuser:
                raise PermissionException(
                    _("Only superusers can promote users to admin")
                )

            # Get user to promote
            try:
                user = User.objects.get(id=user_id, is_active=True)
            except User.DoesNotExist:
                raise ValidationException(_("User not found"))

            # Validate role
            if role not in [UserRole.ADMIN, UserRole.MODERATOR]:
                raise ValidationException(_("Role must be either admin or moderator"))

            # Check if user is already admin/superuser
            if user.is_staff or user.is_superuser:
                raise ValidationException(_("User is already an admin or superuser"))

            # Check if user email is verified
            if not user.is_email_verified:
                raise ValidationException(
                    _("User email must be verified before promotion")
                )

            # Store previous role for logging
            previous_role = user.role

            # Promote user
            user.role = role
            user.is_staff = True
            user.is_superuser = False  # Promotion only sets staff, not superuser

            user.save(update_fields=["role", "is_staff", "is_superuser", "updated_at"])

            logger.info(
                f"User promoted: {user.email} from {previous_role} to {role} "
                f"by {promoter.email}"
            )

            return {
                "promoted_user": user,
                "previous_role": previous_role,
                "new_role": role,
                "promoted_by": promoter,
                "message": _("User promoted to {role} successfully").format(role=role),
            }

        except (PermissionException, ValidationException):
            raise
        except Exception as e:
            logger.error(f"Failed to promote user {user_id}: {str(e)}")
            raise ValidationException(_("Failed to promote user"))

    @staticmethod
    @transaction.atomic
    def revoke_admin_privileges(revoker: "User", user_id: int) -> Dict:
        """
        Revoke admin privileges from user.

        Args:
            revoker: User performing the revocation (must be superuser)
            user_id: ID of admin user to demote

        Returns:
            Dict containing revocation details

        Raises:
            PermissionException: If revoker lacks permission or tries self-revocation
            ValidationException: If revocation is invalid
        """
        try:
            # Validate revoker permissions
            if not revoker.is_superuser:
                raise PermissionException(
                    _("Only superusers can revoke admin privileges")
                )

            # Get user to revoke
            try:
                user = User.objects.get(id=user_id, is_active=True)
            except User.DoesNotExist:
                raise ValidationException(_("User not found"))

            # Prevent self-revocation
            if user == revoker:
                raise PermissionException(
                    _("You cannot revoke your own admin privileges")
                )

            # Check if user is actually an admin (but not superuser)
            if not user.is_staff:
                raise ValidationException(_("User is not an admin"))

            if user.is_superuser:
                raise PermissionException(
                    _("Cannot revoke superuser privileges through this method")
                )

            # Store previous role for logging
            previous_role = user.role

            # Revoke admin privileges
            user.role = UserRole.USER
            user.is_staff = False
            user.is_superuser = False

            user.save(update_fields=["role", "is_staff", "is_superuser", "updated_at"])

            logger.info(
                f"Admin privileges revoked: {user.email} from {previous_role} "
                f"by {revoker.email}"
            )

            return {
                "revoked_user": user,
                "previous_role": previous_role,
                "new_role": UserRole.USER,
                "revoked_by": revoker,
                "message": _("Admin privileges revoked successfully"),
            }

        except (PermissionException, ValidationException):
            raise
        except Exception as e:
            logger.error(
                f"Failed to revoke admin privileges for user {user_id}: {str(e)}"
            )
            raise ValidationException(_("Failed to revoke admin privileges"))

    # ================================================================
    # HELPER METHODS
    # ================================================================

    @staticmethod
    def get_admin_users(include_superusers: bool = True) -> List["User"]:
        """
        Get all admin users.

        Args:
            include_superusers: Whether to include superusers in results

        Returns:
            List of admin User instances
        """
        try:
            queryset = User.objects.filter(is_staff=True, is_active=True)

            if not include_superusers:
                queryset = queryset.filter(is_superuser=False)

            return list(queryset.select_related("profile").order_by("-date_joined"))

        except Exception as e:
            logger.error(f"Failed to get admin users: {str(e)}")
            return []

    @staticmethod
    def validate_admin_permissions(user: "User", required_level: str = "admin") -> bool:
        """
        Validate user has required admin permissions.

        Args:
            user: User to validate
            required_level: Required permission level ("admin", "superuser")

        Returns:
            True if user has required permissions
        """
        if not user or not user.is_authenticated:
            return False

        if required_level == "superuser":
            return user.is_superuser
        elif required_level == "admin":
            return user.is_staff or user.is_superuser
        else:
            return False


# ================================================================
# CONVENIENCE FUNCTIONS
# ================================================================


def create_admin_user(
    creator: "User",
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    role: str = UserRole.ADMIN,
    **extra_fields,
) -> Dict:
    """Convenience function for admin creation."""
    return AdminService.create_admin_user(
        creator, email, password, first_name, last_name, role, **extra_fields
    )


def create_superadmin_user(
    creator: "User",
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    **extra_fields,
) -> Dict:
    """Convenience function for superadmin creation."""
    return AdminService.create_superadmin_user(
        creator, email, password, first_name, last_name, **extra_fields
    )


def promote_user_to_admin(
    promoter: "User", user_id: int, role: str = UserRole.ADMIN
) -> Dict:
    """Convenience function for user promotion."""
    return AdminService.promote_user_to_admin(promoter, user_id, role)


def revoke_admin_privileges(revoker: "User", user_id: int) -> Dict:
    """Convenience function for admin privilege revocation."""
    return AdminService.revoke_admin_privileges(revoker, user_id)
