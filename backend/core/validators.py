"""
Custom validators for model fields and serializers.
"""

import re
from enum import Enum
from typing import Optional

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class PasswordStrength(Enum):
    """Password strength levels with predefined requirements."""

    LOOSE = "loose"
    MEDIUM = "medium"
    STRICT = "strict"


class PasswordStrengthValidator:
    """Validate password strength with configurable security levels"""

    STRENGTH_CONFIGS = {
        PasswordStrength.LOOSE: {
            "min_length": 6,
            "require_uppercase": False,
            "require_lowercase": True,
            "require_digits": True,
            "require_special": False,
            "description": "Basic security - minimum requirements",
        },
        PasswordStrength.MEDIUM: {
            "min_length": 8,
            "require_uppercase": True,
            "require_lowercase": True,
            "require_digits": True,
            "require_special": False,
            "description": "Standard security - recommended for most users",
        },
        PasswordStrength.STRICT: {
            "min_length": 12,
            "require_uppercase": True,
            "require_lowercase": True,
            "require_digits": True,
            "require_special": True,
            "description": "High security - recommended for admin accounts",
        },
    }

    def __init__(
        self,
        strength: Optional[PasswordStrength] = PasswordStrength.MEDIUM,
        min_length: Optional[int] = None,
        require_uppercase: Optional[bool] = None,
        require_lowercase: Optional[bool] = None,
        require_digits: Optional[bool] = None,
        require_special: Optional[bool] = None,
        special_chars: str = '!@#$%^&*(),.?":{}|<>',
    ):
        """
        Initialize password validator.

        Args:
            strength: Predefined strength level (defaults to MEDIUM)
            min_length: Minimum password length (overrides strength setting)
            require_uppercase: Require uppercase letters (overrides strength setting)
            require_lowercase: Require lowercase letters (overrides strength setting)
            require_digits: Require numeric digits (overrides strength setting)
            require_special: Require special characters (overrides strength setting)
            special_chars: Allowed special characters
        """
        # Start with strength configuration (default to MEDIUM)
        config = self.STRENGTH_CONFIGS[strength]
        self.strength_level = strength

        # Apply strength config as base, then override with any explicit parameters
        self.min_length = min_length if min_length is not None else config["min_length"]
        self.require_uppercase = (
            require_uppercase
            if require_uppercase is not None
            else config["require_uppercase"]
        )
        self.require_lowercase = (
            require_lowercase
            if require_lowercase is not None
            else config["require_lowercase"]
        )
        self.require_digits = (
            require_digits if require_digits is not None else config["require_digits"]
        )
        self.require_special = (
            require_special
            if require_special is not None
            else config["require_special"]
        )
        self.special_chars = special_chars

    def __call__(self, password: str, user=None) -> None:
        """Make the validator callable by Django."""
        return self.validate(password, user)

    def validate(self, password: str, user=None) -> None:
        """
        Validate password against configured requirements.

        Args:
            password: Password to validate
            user: User instance (for additional checks)

        Raises:
            ValidationError: If password doesn't meet requirements
        """
        errors = []

        # Length check
        if len(password) < self.min_length:
            errors.append(
                ValidationError(
                    _(f"Password must be at least {self.min_length} characters long."),
                    code="password_too_short",
                )
            )

        # Character requirement
        if self.require_uppercase and not re.search(r"[A-Z]", password):
            errors.append(
                ValidationError(
                    _("Password must contain at least one uppercase letter."),
                    code="password_no_upper",
                )
            )

        if self.require_lowercase and not re.search(r"[a-z]", password):
            errors.append(
                ValidationError(
                    _("Password must contain at least one lowercase letter."),
                    code="password_no_lower",
                )
            )

        if self.require_digits and not re.search(r"\d", password):
            errors.append(
                ValidationError(
                    _("Password must contain at least one digit."),
                    code="password_no_digit",
                )
            )

        if self.require_special and not re.search(
            f"[{re.escape(self.special_chars)}]", password
        ):
            errors.append(
                ValidationError(
                    _("Password must contain at least one special character."),
                    code="password_no_special",
                )
            )

        # User-specific validations
        if user:
            if (
                hasattr(user, "username")
                and user.username
                and user.username.lower() in password.lower()
            ):
                errors.append(
                    ValidationError(
                        _("Password cannot contain your username."),
                        code="password_contains_username",
                    )
                )

            if (
                hasattr(user, "email")
                and user.email
                and user.email.split("@")[0].lower() in password.lower()
            ):
                errors.append(
                    ValidationError(
                        _("Password cannot contain your email address."),
                        code="password_contains_email",
                    )
                )

        # Common password check
        if self._is_common_password(password):
            errors.append(
                ValidationError(
                    _("This password is too common. Please choose a different one."),
                    code="password_too_common",
                )
            )

        if errors:
            raise ValidationError(errors)

    def _is_common_password(self, password: str) -> bool:
        """Check if password is in common passwords list."""
        common_passwords = {
            "password",
            "123456",
            "12345678",
            "qwerty",
            "abc123",
            "password123",
            "admin",
            "letmein",
            "welcome",
            "monkey",
            "111111",
            "dragon",
            "master",
            "sunshine",
            "iloveyou",
        }
        return password.lower() in common_passwords

    def get_help_text(self) -> str:
        """Generate help text based on current configuration."""
        if self.strength_level:
            config = self.STRENGTH_CONFIGS[self.strength_level]
            strength_label = f"Password strength: {self.strength_level.value.title()}"
            base_text = f"{strength_label} - {config['description']}"
        else:
            base_text = "Custom password requirements"

        requirements = []
        requirements.append(_(f"At least {self.min_length} characters"))

        if self.require_uppercase:
            requirements.append(_("One uppercase letter"))
        if self.require_lowercase:
            requirements.append(_("One lowercase letter"))
        if self.require_digits:
            requirements.append(_("One digit"))
        if self.require_special:
            requirements.append(_("One special character"))

        return f"{base_text}. Requirements: {', '.join(requirements)}"


def validate_username(value: str) -> None:
    """
    Validate username format and availability.

    Args:
        value: Username to validate

    Raises:
        ValidationError: If username is invalid
    """
    # Format validation
    if not re.match(r"^[a-zA-Z0-9_-]{3,30}$", value):
        raise ValidationError(
            _(
                "Username must be 3–30 characters long and contain only "
                "letters, numbers, underscores, or hyphens."
            ),
            code="invalid_username_format",
        )

    # Reserved usernames
    reserved_usernames = {
        "admin",
        "api",
        "www",
        "mail",
        "ftp",
        "localhost",
        "root",
        "support",
        "noreply",
        "postmaster",
        "hostmaster",
        "webmaster",
    }

    if value.lower() in reserved_usernames:
        raise ValidationError(
            _("This username is reserved and cannot be used."), code="username_reserved"
        )
