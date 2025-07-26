"""
Core abstract models providing common functionality across all apps.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    """
    Abstract model providing self-managed created_at and updated_at fields.
    All models should inherit from this for consistent timestamp tracking.
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
        ordering = ["-created_at"]  # Descending order
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
        ]

    @property
    def created_at_formatted(self):
        """Return formatted created_at timestamp."""
        if self.created_at:
            return self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        return None

    @property
    def updated_at_formatted(self):
        """Return formatted updated_at timestamp."""
        if self.updated_at:
            return self.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        return None


class UUIDModel(models.Model):
    """
    Abstract model using UUID as primary key instead of auto-incrementing integers.
    Provides better security and distributed system compatibility.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("Unique identifier for this record"),
    )

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """
    Abstract model implementing soft delete functionality.
    Records are marked as deleted instead of being removed from database.
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

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["is_deleted", "-created_at"]),
        ]

    def delete(self, using=None, keep_parents=False, hard_delete=False):
        """
        Soft delete by default, with option for hard delete.
        """
        if hard_delete:
            return super().delete(using=using, keep_parents=keep_parents)

        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])

    def restore(self):
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])


class ActiveModel(models.Model):
    """
    Abstract model providing is_active flag for enabling/disabling records.
    """

    is_active = models.BooleanField(
        _("is active"),
        default=True,
        db_index=True,
        help_text=_("Designates whether this record should be treated as active"),
    )

    class Meta:
        abstract = True
        indexes = [models.Index(fields=["is_active", "created_at"])]

    def activate(self):
        """Activate the record."""
        self.is_active = True
        self.save(update_fields=["is_active"])

    def deactivate(self):
        """Deactivate the record."""
        self.is_active = False
        self.save(update_fields=["is_active"])


class PublishableModel(models.Model):
    """
    Abstract model for content that can be published/unpublished with scheduling.
    """

    is_published = models.BooleanField(
        _("is published"),
        default=False,
        db_index=True,
        help_text=_("Designates whether this content is published"),
    )
    published_at = models.DateTimeField(
        _("published at"),
        null=True,
        blank=True,
        db_index=True,
        help_text=_("Date and time when the content was/will be published"),
    )
    unpublished_at = models.DateTimeField(
        _("unpublished at"),
        null=True,
        blank=True,
        help_text=_("Date and time when the content will be unpublished"),
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["is_published", "published_at"]),
        ]

    def publish(self, published_at=None):
        """Publish the content."""
        self.is_published = True
        self.published_at = published_at or timezone.now()
        self.save(update_fields=["is_published", "published_at"])

    def unpublish(self):
        """Unpublish the content."""
        self.is_published = False
        self.unpublished_at = timezone.now()
        self.save(update_fields=["is_published", "unpublished_at"])

    @property
    def is_scheduled(self):
        """Check if content is scheduled for future publishing."""
        if not self.published_at:
            return False
        return self.published_at > timezone.now()


class AuditableModel(models.Model):
    """
    Abstract model that tracks who created and last modified a record.
    Provides complete audit trail for sensitive data.
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

    def save_with_user(self, user, *args, **kwargs):
        """
        Save method that automatically sets created_by and updated_by.
        Pass the current user when saving the model.
        """
        if user is not None:
            if not self.pk:
                self.created_by = user
            self.updated_by = user
        return super().save(*args, **kwargs)


class BaseModel(TimeStampedModel, ActiveModel):
    """
    Base model combining TimeStamped and Active functionality.
    Most models in the project should inherit from this.
    """

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class FullAuditModel(BaseModel, AuditableModel, SoftDeleteModel):
    """
    Comprehensive base model with all audit features.
    Use for sensitive data requiring complete tracking.
    """

    class Meta:
        abstract = True
        ordering = ["-created_at"]
