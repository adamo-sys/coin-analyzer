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
from .collection_persistence import (
    DurableCollectionPublisher,
    serialize_collection_items,
)
from .coordinator import PackageImportCoordinator, PreparedPackageImport
from .duplicates import DuplicateCandidate, PackageDuplicateDetectionService
from .journal import JournalEntry
from .journal_repository import PackageImportJournalRepository
from .durable_repository import Schema2PackageImportJournalRepository
from .terminal_persistence import TerminalPersistenceService
from .image_store import ManagedCollectionImageStore, ManagedImage, ManagedImagePlan
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
from .recovery import PackageImportRecoveryService
from .transaction import PackageImportExecutionResult, PackageImportTransactionService
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
    "DurableCollectionPublisher",
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
    "ManagedCollectionImageStore",
    "ManagedImage",
    "ManagedImagePlan",
    "LockMetadata",
    "PackageCoin",
    "PackageImage",
    "PackageManifest",
    "PackageImportLock",
    "PackageImportCoordinator",
    "PackageImportExecutionResult",
    "PackageImportJournalRepository",
    "Schema2PackageImportJournalRepository",
    "PackageImportRecoveryService",
    "PackageImportTransactionService",
    "PackageImportPreview",
    "PackageImportPreviewBuilder",
    "PackageDuplicateDetectionService",
    "PackageSession",
    "PreviewCoin",
    "PreviewDecisionSet",
    "PreviewImage",
    "PreparedPackageImport",
    "ProposedCoin",
    "SnapshotDescriptor",
    "SnapshotHandle",
    "SnapshotOwner",
    "TerminalPersistenceService",
    "ValidatedArchiveIndex",
    "ValidatedCapturePackage",
    "ValidatedMedia",
    "ValidationLimits",
    "UnmappedFact",
    "capture_collection_baseline",
    "collection_matches_baseline",
    "deserialize",
    "serialize",
    "serialize_collection_items",
    "require_collection_baseline",
]
