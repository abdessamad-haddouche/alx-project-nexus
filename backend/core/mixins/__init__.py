"""
Core mixins package for Movie Nexus.
Provides reusable model mixins for common functionality.
"""

from .managers import (
    ActiveManager,
    AuditableManager,
    BaseManager,
    FullAuditManager,
    SoftDeleteManager,
)
from .models import (  # Base mixins; Advanced mixins; Audit mixins; Composite mixins
    ActiveMixin,
    AuditableMixin,
    BaseModelMixin,
    CreatedByMixin,
    FullAuditMixin,
    MetadataMixin,
    SoftDeleteMixin,
    TimeStampedMixin,
    UpdatedByMixin,
    UUIDMixin,
)
from .querysets import ActiveQuerySet, AuditableQuerySet, SoftDeleteQuerySet
from .serializers import (
    BaseAuthSerializerMixin,
    EmailValidationMixin,
    LoginValidationMixin,
    PasswordValidationMixin,
    TimestampMixin,
    UserContextMixin,
)

__all__ = [
    # Model mixins
    "TimeStampedMixin",
    "UUIDMixin",
    "ActiveMixin",
    "SoftDeleteMixin",
    "AuditableMixin",
    "MetadataMixin",
    "CreatedByMixin",
    "UpdatedByMixin",
    "BaseModelMixin",
    "FullAuditMixin",
    # Managers Mixins
    "ActiveManager",
    "SoftDeleteManager",
    "AuditableManager",
    "BaseManager",
    "FullAuditManager",
    # QuerySets
    "ActiveQuerySet",
    "SoftDeleteQuerySet",
    "AuditableQuerySet",
    # Serializers Mixins
    "TimestampMixin",
    "UserContextMixin",
    "PasswordValidationMixin",
    "LoginValidationMixin",
    "EmailValidationMixin",
    "BaseAuthSerializerMixin",
]
