"""Pure domain contracts for Coin Analyzer capture-package imports."""

from .audit import AuditCoin, AuditSession, deserialize, serialize
from .archive import ArchiveEntry, CapturePackageArchiveReader, ValidatedArchiveIndex
from .baseline import (
    capture_collection_baseline,
    collection_matches_baseline,
    require_collection_baseline,
)
from .enums import (
    Composition,
    DuplicateDecision,
    ErrorCategory,
    ImageRole,
    ImportPhase,
    ImportRecordOutcome,
    ImportResult,
)
from .journal import JournalEntry
from .lock import LockMetadata, PackageImportLock
from .manifest import CapturePackageManifestParser
from .media import CapturePackageMediaValidator, ValidatedMedia
from .models import (
    CollectionBaseline,
    ImportDecision,
    ImportSession,
    PackageCoin,
    PackageImage,
    PackageManifest,
    PackageSession,
    PreviewCoin,
)
from .snapshot import (
    CapturePackageSnapshotService,
    SnapshotDescriptor,
    SnapshotHandle,
    SnapshotOwner,
)
from .package import CapturePackageValidator, ValidatedCapturePackage
from .validation_limits import ValidationLimits

__all__ = [
    "AuditCoin",
    "AuditSession",
    "ArchiveEntry",
    "CapturePackageArchiveReader",
    "CapturePackageManifestParser",
    "CapturePackageMediaValidator",
    "CapturePackageSnapshotService",
    "CapturePackageValidator",
    "CollectionBaseline",
    "Composition",
    "DuplicateDecision",
    "ErrorCategory",
    "ImageRole",
    "ImportDecision",
    "ImportPhase",
    "ImportRecordOutcome",
    "ImportResult",
    "ImportSession",
    "JournalEntry",
    "LockMetadata",
    "PackageCoin",
    "PackageImage",
    "PackageManifest",
    "PackageImportLock",
    "PackageSession",
    "PreviewCoin",
    "SnapshotDescriptor",
    "SnapshotHandle",
    "SnapshotOwner",
    "ValidatedArchiveIndex",
    "ValidatedCapturePackage",
    "ValidatedMedia",
    "ValidationLimits",
    "capture_collection_baseline",
    "collection_matches_baseline",
    "deserialize",
    "serialize",
    "require_collection_baseline",
]
