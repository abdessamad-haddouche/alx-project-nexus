"""
Reusable model mixins for common functionality across all apps.
Each mixin provides a specific piece of functionality that can be composed together.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .managers import (
    ActiveManager,
    AuditableManager,
    BaseManager,
    FullAuditManager,
    SoftDeleteManager,
)

# ================================================================
# CORE TIMESTAMP & IDENTITY MIXINS
# ================================================================


class TimeStampedMixin(models.Model):
    """
    Mixin providing automatic timestamp tracking.
    """

    created_at = models.DateTimeField(
        _("created at"),
        auto_now_add=True,
        db_index=True,
        help_text=_("Date and time when the record was created"),
    )
    updated_at = models.DateTimeField(
        _("updated at"),
        auto_now=True,
        db_index=True,
        help_text=_("Date and time when the record was last updated"),
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
        ]

    @property
    def created_at_formatted(self):
        """Return formatted created_at timestamp."""
        return (
            self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None
        )

    @property
    def updated_at_formatted(self):
        """Return formatted updated_at timestamp."""
        return (
            self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None
        )

    @property
    def record_age_in_days(self):
        """Get age of record in days."""
        if not self.created_at:
            return 0
        return (timezone.now() - self.created_at).days


class UUIDMixin(models.Model):
    """
    Mixin providing UUID as primary key.
    Better for security and distributed systems.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("Unique identifier for this record"),
    )

    class Meta:
        abstract = True


# ================================================================
# STATE MANAGEMENT MIXINS
# ================================================================


class ActiveMixin(models.Model):
    """
    Mixin for enable/disable functionality.
    """

    is_active = models.BooleanField(
        _("is active"),
        default=True,
        db_index=True,
        help_text=_("Designates whether this record should be treated as active"),
    )

    objects = ActiveManager()

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["is_active"]),
        ]

    def activate(self):
        """Activate the record."""
        self.is_active = True
        self.save(update_fields=["is_active"])

    def deactivate(self):
        """Deactivate the record."""
        self.is_active = False
        self.save(update_fields=["is_active"])

    def toggle_active(self):
        """Toggle active status."""
        self.is_active = not self.is_active
        self.save(update_fields=["is_active"])


class SoftDeleteMixin(models.Model):
    """
    Mixin implementing soft delete functionality.
    Records are marked as deleted instead of being removed.
    """

    is_deleted = models.BooleanField(
        _("is deleted"), default=False, db_index=True, help_text=_("Soft delete flag")
    )

    deleted_at = models.DateTimeField(
        _("deleted at"),
        null=True,
        blank=True,
        db_index=True,
        help_text=_("Date and time when the record was soft deleted"),
    )

    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_deletions",
        verbose_name=_("deleted by"),
        help_text=_("User who deleted this record"),
    )

    objects = SoftDeleteManager()

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["is_deleted"]),
            models.Index(fields=["is_deleted", "created_at"]),
        ]

    def delete(
        self, using=None, keep_parents=False, hard_delete=False, deleted_by=None
    ):
        """
        Soft delete by default, with option for hard delete.

        Args:
            using: Database alias
            keep_parents: Keep parent records
            hard_delete: Perform actual database deletion
            deleted_by: User performing the deletion
        """
        if hard_delete:
            return super().delete(using=using, keep_parents=keep_parents)

        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])

    def restore(self):
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])

    @property
    def is_permanently_deleted(self):
        """Check if record is soft deleted."""
        return self.is_deleted


# ================================================================
# USER AUDIT MIXINS
# ================================================================


class CreatedByMixin(models.Model):
    """
    Mixin that tracks who created a record.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_created",
        verbose_name=_("created by"),
        help_text=_("User who created this record"),
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["created_by"]),
        ]


class UpdatedByMixin(models.Model):
    """
    Mixin that tracks who last updated a record.
    """

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_updated",
        verbose_name=_("updated by"),
        help_text=_("User who last updated this record"),
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["updated_by"]),
        ]


class AuditableMixin(CreatedByMixin, UpdatedByMixin):
    """
    Complete audit trail mixin combining created_by and updated_by.
    """

    objects = AuditableManager()

    class Meta:
        abstract = True

    def save_with_user(self, user, *args, **kwargs):
        """
        Save method that automatically sets audit fields.

        Args:
            user: User performing the action
        """
        if user and user.is_authenticated:
            if not self.pk:  # New record
                self.created_by = user
            self.updated_by = user
        return super().save(*args, **kwargs)


class MetadataMixin(models.Model):
    """
    Mixin for storing additional metadata as JSON.
    Flexible for storing extra data from APIs, user preferences, etc.
    """

    metadata = models.JSONField(
        _("metadata"),
        default=dict,
        blank=True,
        help_text=_("Additional data stored as JSON"),
    )

    class Meta:
        abstract = True

    def set_metadata(self, key, value, save=True):
        """Set a metadata key-value pair."""
        if not isinstance(self.metadata, dict):
            self.metadata = {}
        self.metadata[key] = value
        if save:
            self.save(update_fields=["metadata"])

    def get_metadata(self, key, default=None):
        """Get a metadata value by key."""
        if isinstance(self.metadata, dict):
            return self.metadata.get(key, default)
        return default

    def remove_metadata(self, key, save=True):
        """Remove a metadata key."""
        if isinstance(self.metadata, dict) and key in self.metadata:
            del self.metadata[key]
            if save:
                self.save(update_fields=["metadata"])


# ================================================================
# COMPOSITE MIXINS (MOST COMMONLY USED)
# ================================================================


class BaseModelMixin(TimeStampedMixin, ActiveMixin):
    """
    Base mixin combining the most common functionality.
    """

    objects = BaseManager()

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class FullAuditMixin(BaseModelMixin, AuditableMixin, SoftDeleteMixin):
    """
    Comprehensive mixin with all audit features.
    Use for sensitive data requiring complete tracking.
    """

    objects = FullAuditManager()

    class Meta:
        abstract = True
        ordering = ["-created_at"]
