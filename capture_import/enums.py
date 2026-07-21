"""Enumerations used by capture-package import domain contracts."""

from __future__ import annotations

from enum import Enum


class ImportPhase(str, Enum):
    """Durable phases in the package-import journal state machine."""

    PREPARED = "PREPARED"
    COPYING_IMAGES = "COPYING_IMAGES"
    FILES_READY = "FILES_READY"
    COMMITTING_COLLECTION = "COMMITTING_COLLECTION"
    COLLECTION_COMMITTED = "COLLECTION_COMMITTED"
    ROLLING_BACK = "ROLLING_BACK"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    ROLLBACK_FAILED = "ROLLBACK_FAILED"
    COMPACTING = "COMPACTING"
    # Schema-1 read-only history values. Schema 2 rejects them operationally.
    SUCCEEDED = "SUCCEEDED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"


class DuplicateDecision(str, Enum):
    """Collector choice for one proposed package coin."""

    SKIP = "SKIP"
    IMPORT_AS_NEW = "IMPORT_AS_NEW"


class DuplicateConfidence(str, Enum):
    """Strength of one explained duplicate signal."""

    EXACT = "EXACT"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    WEAK = "WEAK"


class DuplicateCategory(str, Enum):
    """Stable category for duplicate evidence shown during preview."""

    PACKAGE_REPLAY = "PACKAGE_REPLAY"
    SOURCE_AND_MEDIA = "SOURCE_AND_MEDIA"
    MEDIA_HASHES = "MEDIA_HASHES"
    IDENTITY_AND_ACQUISITION = "IDENTITY_AND_ACQUISITION"
    IDENTITY = "IDENTITY"
    ACQUISITION_DETAILS = "ACQUISITION_DETAILS"
    PARTIAL_MEDIA = "PARTIAL_MEDIA"


class ImportRecordOutcome(str, Enum):
    """Derived terminal outcome for one proposed source record."""

    SKIPPED = "SKIPPED"
    NOT_COMMITTED = "NOT_COMMITTED"
    COMMITTED = "COMMITTED"


class ImportResult(str, Enum):
    """Sanitized final result recorded by an import audit."""

    SUCCEEDED = "SUCCEEDED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    ROLLBACK_FAILED = "ROLLBACK_FAILED"
    FAILED = "FAILED"


class ErrorCategory(str, Enum):
    """Stable, path-free importer error categories."""

    PACKAGE_NOT_FOUND = "PACKAGE_NOT_FOUND"
    PACKAGE_NOT_ZIP = "PACKAGE_NOT_ZIP"
    PACKAGE_CHANGED = "PACKAGE_CHANGED"
    PACKAGE_LIMIT_EXCEEDED = "PACKAGE_LIMIT_EXCEEDED"
    ARCHIVE_ENTRY_UNSAFE = "ARCHIVE_ENTRY_UNSAFE"
    ARCHIVE_NAME_COLLISION = "ARCHIVE_NAME_COLLISION"
    ARCHIVE_ENTRY_UNREFERENCED = "ARCHIVE_ENTRY_UNREFERENCED"
    MANIFEST_MISSING = "MANIFEST_MISSING"
    MANIFEST_INVALID = "MANIFEST_INVALID"
    EMPTY_PACKAGE = "EMPTY_PACKAGE"
    UNSUPPORTED_PACKAGE_VERSION = "UNSUPPORTED_PACKAGE_VERSION"
    MEDIA_MISSING = "MEDIA_MISSING"
    MEDIA_INVALID = "MEDIA_INVALID"
    PREVIEW_STALE = "PREVIEW_STALE"
    COLLECTION_CHANGED = "COLLECTION_CHANGED"
    IMPORT_LOCKED = "IMPORT_LOCKED"
    MANAGED_PATH_COLLISION = "MANAGED_PATH_COLLISION"
    SNAPSHOT_FAILED = "SNAPSHOT_FAILED"
    SNAPSHOT_RECOVERY_REQUIRED = "SNAPSHOT_RECOVERY_REQUIRED"
    COPYING_IMAGES_FAILED = "COPYING_IMAGES_FAILED"
    COLLECTION_COMMIT_FAILED = "COLLECTION_COMMIT_FAILED"
    AUDIT_FINALIZATION_PENDING = "AUDIT_FINALIZATION_PENDING"
    ROLLED_BACK = "ROLLED_BACK"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    ROLLBACK_FAILED = "ROLLBACK_FAILED"
    JOURNAL_CORRUPT = "JOURNAL_CORRUPT"
    DUPLICATE_PACKAGE = "DUPLICATE_PACKAGE"
    UNSUPPORTED_DURABILITY_ENVIRONMENT = "UNSUPPORTED_DURABILITY_ENVIRONMENT"
    JOURNAL_GENERATION_EXHAUSTED = "JOURNAL_GENERATION_EXHAUSTED"
    IMPORT_STATE_LIMIT_EXCEEDED = "IMPORT_STATE_LIMIT_EXCEEDED"


class CollectionPublicationState(str, Enum):
    """Durable state of one collection publication artifact."""

    PLANNED = "PLANNED"
    CREATED = "CREATED"
    VERIFIED = "VERIFIED"
    EXCHANGED = "EXCHANGED"
    PUBLISHED = "PUBLISHED"
    RETAINED = "RETAINED"
    CLEANED = "CLEANED"


class CleanupStatus(str, Enum):
    """Append-only cleanup operation status."""

    INTENT = "INTENT"
    COMPLETE = "COMPLETE"


class TerminalCompactionStatus(str, Enum):
    """The two durable G/H compaction substates."""

    PLANNING_MANIFEST = "PLANNING_MANIFEST"
    READY_FOR_TERMINAL = "READY_FOR_TERMINAL"


class ImageRole(str, Enum):
    """Image roles supported by capture-package format 1.0."""

    FRONT = "front"
    REVERSE = "reverse"
    EDGE = "edge"


class Composition(str, Enum):
    """Composition values supported by capture-package format 1.0."""

    SILVER = "silver"
    GOLD = "gold"
    COPPER = "copper"
    NICKEL = "nickel"
    BRONZE = "bronze"
    BRASS = "brass"
    PLATINUM = "platinum"
    OTHER = "other"

HISTORY_PHASES = frozenset(
    {ImportPhase.SUCCEEDED, ImportPhase.ROLLED_BACK, ImportPhase.CANCELLED}
)
