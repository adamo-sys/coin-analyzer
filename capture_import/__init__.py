"""Pure domain contracts for Coin Analyzer capture-package imports."""

from .audit import AuditCoin, AuditSession, deserialize, serialize
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

__all__ = [
    "AuditCoin",
    "AuditSession",
    "CapturePackageSnapshotService",
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
    "capture_collection_baseline",
    "collection_matches_baseline",
    "deserialize",
    "serialize",
    "require_collection_baseline",
]
