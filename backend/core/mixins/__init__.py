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
    # Managers
    "ActiveManager",
    "SoftDeleteManager",
    "AuditableManager",
    "BaseManager",
    "FullAuditManager",
    # QuerySets
    "ActiveQuerySet",
    "SoftDeleteQuerySet",
    "AuditableQuerySet",
]
