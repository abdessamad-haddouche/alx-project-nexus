"""
Custom managers for mixin functionality.
Provides optimized database queries and common filtering methods.
"""

from django.db import models
from django.utils import timezone

from .querysets import ActiveQuerySet, AuditableQuerySet, SoftDeleteQuerySet

# ================================================================
# MANAGERS
# ================================================================


class ActiveManager(models.Manager):
    """Manager for models with ActiveMixin."""

    def get_queryset(self):
        """Return custom queryset with active filtering methods."""
        return ActiveQuerySet(self.model, using=self._db)

    def active(self):
        """Get only active records."""
        return self.get_queryset().active()

    def inactive(self):
        """Get only inactive records."""
        return self.get_queryset().inactive()


class SoftDeleteManager(models.Manager):
    """Manager for models with SoftDeleteMixin."""

    def get_queryset(self):
        """Return only non-deleted records by default."""
        return SoftDeleteQuerySet(self.model, using=self._db).not_deleted()

    def all_with_deleted(self):
        """Get all records including soft-deleted ones."""
        return SoftDeleteQuerySet(self.model, using=self._db)

    def deleted_only(self):
        """Get only soft-deleted records."""
        return SoftDeleteQuerySet(self.model, using=self._db).deleted()


class AuditableManager(models.Manager):
    """Manager for models with AuditableMixin."""

    def get_queryset(self):
        """Return custom queryset with audit methods."""
        return AuditableQuerySet(self.model, using=self._db)

    def created_by(self, user):
        """Get records created by specific user."""
        return self.get_queryset().created_by_user(user)

    def with_audit_info(self):
        """Optimize query to include audit information."""
        return self.get_queryset().with_audit_info()


# ================================================================
# COMBINED MANAGERS
# ================================================================


class BaseManager(models.Manager):
    """
    Combined manager for BaseModelMixin (TimeStamped + Active).
    """

    def get_queryset(self):
        """Return queryset with active filtering."""
        return ActiveQuerySet(self.model, using=self._db).active()

    def all_records(self):
        """Get all records including inactive ones."""
        return ActiveQuerySet(self.model, using=self._db)

    def active(self):
        """Get only active records."""
        return self.get_queryset().active()

    def recent(self, days=7):
        """Get records created in the last N days."""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        return self.get_queryset().filter(created_at__gte=cutoff_date)


class FullAuditManager(models.Manager):
    """
    Manager combining Active, SoftDelete, and Auditable functionality.
    For models requiring complete audit trail.
    """

    def get_queryset(self):
        """Return queryset with all audit functionality."""
        return self._get_combined_queryset().active().not_deleted()

    def _get_combined_queryset(self):
        """Get base queryset with all mixin methods."""

        class CombinedQuerySet(ActiveQuerySet, SoftDeleteQuerySet, AuditableQuerySet):
            pass

        return CombinedQuerySet(self.model, using=self._db)

    def all_records(self):
        """Get all records including inactive and deleted ones."""
        return self._get_combined_queryset()

    def with_deleted(self):
        """Get active records including soft-deleted ones."""
        return self._get_combined_queryset().active()

    def deleted_only(self):
        """Get only soft-deleted records."""
        return self._get_combined_queryset().deleted()

    def created_by(self, user):
        """Get records created by specific user."""
        return self.get_queryset().created_by_user(user)
