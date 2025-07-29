"""
Custom querysets for mixin functionality.
Provides optimized database queries and common filtering methods.
"""

from django.db import models
from django.utils import timezone


class ActiveQuerySet(models.QuerySet):
    """QuerySet for models with ActiveMixin."""

    def active(self):
        """Filter only active records."""
        return self.filter(is_active=True)

    def inactive(self):
        """Filter only inactive records."""
        return self.filter(is_active=False)

    def activate(self):
        """Bulk activate records."""
        return self.update(is_active=True)

    def deactivate(self):
        """Bulk deactivate records."""
        return self.update(is_active=False)


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet for models with SoftDeleteMixin."""

    def not_deleted(self):
        """Filter only non-deleted records."""
        return self.filter(is_deleted=False)

    def deleted(self):
        """Filter only soft-deleted records."""
        return self.filter(is_deleted=True)

    def delete(self):
        """Soft delete all records in queryset."""
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        """Permanently delete all records in queryset."""
        return super().delete()

    def restore(self):
        """Restore all soft-deleted records in queryset."""
        return self.update(is_deleted=False, deleted_at=None, deleted_by=None)


class AuditableQuerySet(models.QuerySet):
    """QuerySet for models with AuditableMixin."""

    def created_by_user(self, user):
        """Filter records created by specific user."""
        return self.filter(created_by=user)

    def updated_by_user(self, user):
        """Filter records last updated by specific user."""
        return self.filter(updated_by=user)

    def with_creator(self):
        """Optimize query to include creator information."""
        return self.select_related("created_by")

    def with_updater(self):
        """Optimize query to include updater information."""
        return self.select_related("updated_by")

    def with_audit_info(self):
        """Optimize query to include all audit information."""
        return self.select_related("created_by", "updated_by")
