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
    DuplicateCategory,
    DuplicateConfidence,
    DuplicateDecision,
    ErrorCategory,
    ImageRole,
    ImportPhase,
    ImportRecordOutcome,
    ImportResult,
)
from .decisions import ImportDecisionModel
from .duplicates import DuplicateCandidate, PackageDuplicateDetectionService
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
from .preview import (
    PackageImportPreview,
    PackageImportPreviewBuilder,
    PreviewDecisionSet,
    PreviewImage,
    ProposedCoin,
    UnmappedFact,
)
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
    "DuplicateCandidate",
    "DuplicateCategory",
    "DuplicateConfidence",
    "DuplicateDecision",
    "ErrorCategory",
    "ImageRole",
    "ImportDecision",
    "ImportDecisionModel",
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
    "PackageImportPreview",
    "PackageImportPreviewBuilder",
    "PackageDuplicateDetectionService",
    "PackageSession",
    "PreviewCoin",
    "PreviewDecisionSet",
    "PreviewImage",
    "ProposedCoin",
    "SnapshotDescriptor",
    "SnapshotHandle",
    "SnapshotOwner",
    "ValidatedArchiveIndex",
    "ValidatedCapturePackage",
    "ValidatedMedia",
    "ValidationLimits",
    "UnmappedFact",
    "capture_collection_baseline",
    "collection_matches_baseline",
    "deserialize",
    "serialize",
    "require_collection_baseline",
]
