"""
Reusable model mixins for common functionality across all apps.
Each mixin provides a specific piece of functionality that can be composed together.
"""

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ..constants import TMDbSyncStatus
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
# TMDB INTEGRATION MIXINS
# ================================================================


class TMDbMixin(models.Model):
    """
    Mixin for models that sync with TMDb API.
    Provides TMDb ID tracking and synchronization metadata.
    """

    tmdb_id = models.PositiveIntegerField(
        _("TMDb ID"),
        unique=True,
        db_index=True,
        help_text=_("The Movie Database unique identifier"),
    )

    last_synced = models.DateTimeField(
        _("last synced"),
        null=True,
        blank=True,
        db_index=True,
        help_text=_("Last time data was synchronized with TMDb"),
    )

    sync_status = models.CharField(
        _("sync status"),
        max_length=20,
        choices=TMDbSyncStatus.choices,
        default=TMDbSyncStatus.PENDING,
        db_index=True,
        help_text=_("Status of last TMDb synchronization"),
    )

    sync_retries = models.PositiveSmallIntegerField(
        _("sync retries"),
        default=0,
        help_text=_("Number of sync retry attempts"),
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["tmdb_id"]),
            models.Index(fields=["last_synced"]),
            models.Index(fields=["sync_status"]),
            models.Index(fields=["tmdb_id", "sync_status"]),
        ]

    def mark_sync_success(self):
        """Mark synchronization as successful."""
        self.sync_status = TMDbSyncStatus.SUCCESS
        self.last_synced = timezone.now()
        self.sync_retries = 0
        self.save(update_fields=["sync_status", "last_synced", "sync_retries"])

    def mark_sync_failed(self):
        """Mark synchronization as failed and increment retries."""
        self.sync_status = TMDbSyncStatus.FAILED
        self.sync_retries += 1
        self.save(update_fields=["sync_status", "sync_retries"])

    def needs_sync(self, hours=24):
        """
        Check if model needs synchronization.

        Args:
            hours: Hours since last sync to consider stale

        Returns:
            bool: True if sync is needed
        """
        if not self.last_synced:
            return True

        if self.sync_status == TMDbSyncStatus.FAILED:
            return True

        stale_threshold = timezone.now() - timedelta(hours=hours)
        return self.last_synced < stale_threshold

    @property
    def sync_age_hours(self):
        """Get age of last sync in hours."""
        if not self.last_synced:
            return None
        return (timezone.now() - self.last_synced).total_seconds() / 3600


class PopularityMixin(models.Model):
    """
    Mixin for models with popularity and rating data.
    Used for movies, TV shows, and people.
    """

    popularity = models.FloatField(
        _("popularity"),
        default=0.0,
        db_index=True,
        help_text=_("TMDb popularity score"),
    )

    vote_average = models.FloatField(
        _("vote average"),
        default=0.0,
        db_index=True,
        help_text=_("Average user rating (0-10)"),
    )

    vote_count = models.PositiveIntegerField(
        _("vote count"),
        default=0,
        db_index=True,
        help_text=_("Total number of votes"),
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["popularity"]),
            models.Index(fields=["vote_average"]),
            models.Index(fields=["vote_count"]),
            models.Index(fields=["popularity", "vote_average"]),
        ]

    @property
    def is_popular(self):
        """Check if item is considered popular (popularity > 50)."""
        return self.popularity > 50.0

    @property
    def is_highly_rated(self):
        """Check if item is highly rated (average > 7.0 with min votes)."""
        return self.vote_average > 7.0 and self.vote_count >= 100

    @property
    def rating_stars(self):
        """Convert 0-10 rating to 0-5 stars."""
        return round(self.vote_average / 2, 1)


class ReleaseMixin(models.Model):
    """Mixin for release date information."""

    release_date = models.DateField(
        _("release date"),
        null=True,
        blank=True,
        db_index=True,
        help_text=_("Official release date"),
    )

    class Meta:
        abstract = True

    @property
    def release_year(self):
        return self.release_date.year if self.release_date else None


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


class TMDbContentMixin(TMDbMixin, PopularityMixin, ReleaseMixin):
    """
    Composite mixin for TMDb content (movies, TV shows).
    Combines sync, popularity, and release functionality.
    """

    class Meta:
        abstract = True


class TMDbPersonMixin(TMDbMixin, PopularityMixin):
    """
    Composite mixin for TMDb people (actors, directors).
    Combines sync and popularity (no release date for people).
    """

    class Meta:
        abstract = True
