"""
Admin management serializers for Movie Nexus.
"""

from rest_framework import serializers

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core.constants import UserRole
from core.mixins.serializers import BaseAuthSerializerMixin

from ..models import UserProfile

User = get_user_model()


class AdminCreateSerializer(BaseAuthSerializerMixin, serializers.ModelSerializer):
    """
    Admin creation serializer.
    Creates new admin users with validation.
    """

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(
        choices=[UserRole.ADMIN, UserRole.MODERATOR], default=UserRole.ADMIN
    )

    # Read-only computed fields
    full_name = serializers.ReadOnlyField()
    display_name = serializers.ReadOnlyField()
    avatar_url = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
            "role",
            "phone_number",
            "date_of_birth",
            "avatar",
            # Read-only fields
            "id",
            "full_name",
            "display_name",
            "avatar_url",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_email_verified",
            "date_joined",
        ]
        extra_kwargs = {
            "email": {"required": True},
            "first_name": {"required": True},
            "last_name": {"required": True},
            "is_staff": {"read_only": True},
            "is_superuser": {"read_only": True},
            "date_joined": {"read_only": True},
        }

    def validate_email(self, value):
        """Validate email availability."""
        email = self.validate_email_format(value)

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(_("Admin with this email already exists"))

        return email

    def validate(self, attrs):
        """Validate admin creation data."""
        attrs = super().validate(attrs)
        return self.validate_password_confirmation(attrs)

    def validate_password(self, value):
        """Validate password strength for admin accounts."""
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(str(e))
        return value

    def validate_role(self, value):
        """Ensure role is appropriate for admin creation."""
        if value not in [UserRole.ADMIN, UserRole.MODERATOR]:
            raise serializers.ValidationError(
                _("Role must be either admin or moderator")
            )
        return value

    def create(self, validated_data):
        """Create admin user with appropriate permissions."""
        # Remove password_confirm
        validated_data.pop("password_confirm", None)
        role = validated_data.get("role", UserRole.ADMIN)

        # Set admin permissions based on role
        if role == UserRole.ADMIN:
            validated_data["is_staff"] = True
            validated_data["is_superuser"] = False
        elif role == UserRole.MODERATOR:
            validated_data["is_staff"] = True  # Moderators are staff
            validated_data["is_superuser"] = False

        # Email is pre-verified for admin accounts
        validated_data["is_email_verified"] = True

        # Create admin user
        admin_user = User.objects.create_user(**validated_data)

        # Create profile
        UserProfile.objects.create(user=admin_user)

        return {
            "user": admin_user,
            "role": role,
            "created_by": self.current_user,
        }

    def to_representation(self, instance):
        """Return admin creation success response."""
        user = instance["user"]
        role = instance["role"]
        created_by = instance["created_by"]

        return {
            "admin": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": role,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "is_email_verified": user.is_email_verified,
                "date_joined": user.date_joined,
            },
            "created_by": {
                "id": created_by.id,
                "email": created_by.email,
                "full_name": created_by.full_name,
            },
            "message": _("Admin account created successfully"),
        }


class SuperAdminCreateSerializer(BaseAuthSerializerMixin, serializers.ModelSerializer):
    """
    SuperAdmin creation serializer.
    Only for creating superuser accounts.
    """

    password = serializers.CharField(
        write_only=True, min_length=12
    )  # Stronger password requirement
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
            "phone_number",
            # Read-only fields
            "id",
            "full_name",
            "display_name",
            "avatar_url",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_email_verified",
            "date_joined",
        ]
        extra_kwargs = {
            "email": {"required": True},
            "first_name": {"required": True},
            "last_name": {"required": True},
            "is_staff": {"read_only": True},
            "is_superuser": {"read_only": True},
            "date_joined": {"read_only": True},
        }

    def validate_email(self, value):
        """Validate email availability."""
        email = self.validate_email_format(value)

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                _("SuperAdmin with this email already exists")
            )

        return email

    def validate(self, attrs):
        """Validate superadmin creation data."""
        attrs = super().validate(attrs)
        return self.validate_password_confirmation(attrs)

    def validate_password(self, value):
        """Extra strong password validation for superadmin."""
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(str(e))

        # Additional superadmin password requirements
        if len(value) < 12:
            raise serializers.ValidationError(
                _("SuperAdmin password must be at least 12 characters long")
            )

        return value

    def create(self, validated_data):
        """Create superadmin user."""
        # Remove password_confirm
        validated_data.pop("password_confirm", None)

        # Set superadmin permissions
        validated_data["is_staff"] = True
        validated_data["is_superuser"] = True
        validated_data["role"] = UserRole.SUPERADMIN
        validated_data["is_email_verified"] = True  # Pre-verified

        # Create superadmin user
        superadmin_user = User.objects.create_superuser(**validated_data)

        # Create profile
        UserProfile.objects.create(user=superadmin_user)

        return {
            "user": superadmin_user,
            "created_by": self.current_user,
        }

    def to_representation(self, instance):
        """Return superadmin creation success response."""
        user = instance["user"]
        created_by = instance["created_by"]

        return {
            "superadmin": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "is_email_verified": user.is_email_verified,
                "date_joined": user.date_joined,
            },
            "created_by": {
                "id": created_by.id,
                "email": created_by.email,
                "full_name": created_by.full_name,
            },
            "message": _("SuperAdmin account created successfully"),
        }


class AdminPromoteSerializer(BaseAuthSerializerMixin, serializers.Serializer):
    """
    Promote existing user to admin role.
    """

    user_id = serializers.IntegerField()
    role = serializers.ChoiceField(
        choices=[UserRole.ADMIN, UserRole.MODERATOR, UserRole.SUPERADMIN],
        default=UserRole.ADMIN,
    )

    def validate_user_id(self, value):
        """Validate user exists and can be promoted."""
        try:
            user = User.objects.get(id=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError(_("User not found"))

        # Check if user email is verified
        if not user.is_email_verified:
            raise serializers.ValidationError(
                _("User email must be verified before promotion")
            )

        return user

    def validate(self, attrs):
        """Validate the promotion request."""
        user = attrs["user_id"]  # This is the user object from validate_user_id
        target_role = attrs["role"]
        current_role = user.role

        # Prevent unnecessary promotions (same role)
        if current_role == target_role:
            raise serializers.ValidationError(
                _("User already has the role: {role}").format(role=target_role)
            )

        # Validate promotion logic based on target role
        if target_role == UserRole.SUPERADMIN:
            # Only non-superusers can be promoted to superadmin
            if user.is_superuser:
                raise serializers.ValidationError(_("User is already a superuser"))

        # Allow promotion/demotion between user, moderator, and admin
        # The only restriction is superuser promotion

        return attrs

    def create(self, validated_data):
        """Promote user to the specified role."""
        user = validated_data["user_id"]  # The user object from validation
        role = validated_data["role"]

        # Store previous role for response
        previous_role = user.role

        # Update user permissions based on role
        if role == UserRole.SUPERADMIN:
            user.role = role
            user.is_staff = True
            user.is_superuser = True
        elif role in [UserRole.ADMIN, UserRole.MODERATOR]:
            user.role = role
            user.is_staff = True
            user.is_superuser = False
        else:  # UserRole.USER
            user.role = role
            user.is_staff = False
            user.is_superuser = False

        user.save(update_fields=["role", "is_staff", "is_superuser", "updated_at"])

        return {
            "user": user,
            "previous_role": previous_role,
            "new_role": role,
            "promoted_by": self.current_user,
        }

    def to_representation(self, instance):
        """Return promotion success response."""
        user = instance["user"]
        previous_role = instance["previous_role"]
        new_role = instance["new_role"]
        promoted_by = instance["promoted_by"]

        return {
            "promoted_user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "previous_role": previous_role,
                "new_role": new_role,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
            },
            "promoted_by": {
                "id": promoted_by.id,
                "email": promoted_by.email,
                "full_name": promoted_by.full_name,
            },
            "message": _("User role changed from {prev} to {new} successfully").format(
                prev=previous_role, new=new_role
            ),
        }


class AdminRevokeSerializer(BaseAuthSerializerMixin, serializers.Serializer):
    """
    Revoke admin privileges from user.
    """

    def validate(self, attrs):
        """Validate revocation request."""
        # Prevent self-revocation
        if hasattr(self, "user_to_revoke") and self.user_to_revoke == self.current_user:
            raise serializers.ValidationError(
                _("You cannot revoke your own admin privileges")
            )
        return attrs

    def create(self, validated_data):
        """Revoke admin privileges."""
        user = self.user_to_revoke  # Set by the view

        # Store previous role for response
        previous_role = user.role

        # Revoke admin privileges
        user.role = UserRole.USER
        user.is_staff = False
        user.is_superuser = False

        user.save(update_fields=["role", "is_staff", "is_superuser", "updated_at"])

        return {
            "user": user,
            "previous_role": previous_role,
            "revoked_by": self.current_user,
        }

    def to_representation(self, instance):
        """Return revocation success response."""
        user = instance["user"]
        previous_role = instance["previous_role"]
        revoked_by = instance["revoked_by"]

        return {
            "revoked_user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "previous_role": previous_role,
                "new_role": UserRole.USER,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
            },
            "revoked_by": {
                "id": revoked_by.id,
                "email": revoked_by.email,
                "full_name": revoked_by.full_name,
            },
            "message": _("Admin privileges revoked successfully"),
        }


class AdminListSerializer(BaseAuthSerializerMixin, serializers.Serializer):
    """
    List all admin users.
    """

    def to_representation(self, instance):
        """Return list of admin users."""
        # Get all admin users (staff but not necessarily superuser)
        admin_users = (
            User.objects.filter(is_staff=True, is_active=True)
            .select_related("profile")
            .order_by("-date_joined")
        )

        admins_data = []
        for user in admin_users:
            admins_data.append(
                {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role,
                    "is_staff": user.is_staff,
                    "is_superuser": user.is_superuser,
                    "is_email_verified": user.is_email_verified,
                    "date_joined": user.date_joined,
                    "last_login": user.last_login,
                }
            )

        return {
            "admins": admins_data,
            "total_admins": len(admins_data),
            "message": _("Admin users retrieved successfully"),
        }
