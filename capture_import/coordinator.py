"""Application-level validation, preview, cancellation, and commit handoff."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path

from ._filesystem import require_plain_regular_file
from .baseline import capture_collection_baseline
from .errors import PackageChanged, PackageNotFound, PackageTooLarge
from .journal_repository import PackageImportJournalRepository
from .limits import MAX_PACKAGE_SIZE
from .lock import PackageImportLock
from .package import CapturePackageValidator, ValidatedCapturePackage
from .preview import PackageImportPreview, PackageImportPreviewBuilder, PreviewDecisionSet
from .processed_snapshot import (
    ProcessedArtifactSnapshotService,
    ProcessedSnapshotHandle,
)
from .snapshot import CapturePackageSnapshotService, SnapshotHandle
from .transaction import (
    PackageImportExecutionResult,
    PackageImportTransactionService,
    Schema3PackageImportTransactionService,
    Schema3TransactionGenesisResult,
)
from .workflow_models import PreparedArtifactSet


@dataclass(slots=True)
class PreparedPackageImport:
    """Owned snapshot(s) plus its exact validated package and preview."""

    snapshot: SnapshotHandle
    package: ValidatedCapturePackage
    preview: PackageImportPreview
    processed_snapshot: ProcessedSnapshotHandle | None = None
    closed: bool = False

    def cancel(self) -> None:
        if self.closed:
            return
        if self.processed_snapshot is not None:
            self.processed_snapshot.cleanup()
        self.snapshot.cleanup()
        self.closed = True


class PackageImportCoordinator:
    """Keep read-only preparation separate from explicit transactional commit."""

    def __init__(
        self,
        *,
        collection_path: str | os.PathLike[str],
        snapshots: CapturePackageSnapshotService,
        journals: PackageImportJournalRepository,
        transaction: PackageImportTransactionService,
        processed_snapshots: ProcessedArtifactSnapshotService | None = None,
        processed_transaction: Schema3PackageImportTransactionService | None = None,
    ) -> None:
        self._collection_path = Path(collection_path)
        self._snapshots = snapshots
        self._journals = journals
        self._transaction = transaction
        self._processed_snapshots = processed_snapshots
        self._processed_transaction = processed_transaction
        self._validator = CapturePackageValidator()
        self._preview_builder = PackageImportPreviewBuilder()

    def prepare(
        self,
        source_path: str | os.PathLike[str],
        *,
        processed_artifacts: PreparedArtifactSet | None = None,
    ) -> PreparedPackageImport:
        """Capture one immutable snapshot and build a read-only preview."""

        source = Path(source_path)
        digest = self._source_digest(source)
        snapshot = self._snapshots.create_snapshot(source, digest)
        processed_handle: ProcessedSnapshotHandle | None = None
        try:
            package = self._validator.validate_snapshot(snapshot, source.name)
            baseline = capture_collection_baseline(self._collection_path)
            audits = tuple(
                entry.terminal_audit
                for entry in self._journals.list_entries()
                if entry.terminal_audit is not None
            )
            preview = self._preview_builder.build(
                package, baseline, completed_audits=audits
            )
            if processed_artifacts is not None:
                if self._processed_snapshots is None:
                    raise ValueError(
                        "processed_artifacts provided but processed_snapshots service not configured"
                    )
                lock = PackageImportLock.acquire(self._transaction._lock_path)
                try:
                    processed_handle = self._processed_snapshots.seal(
                        processed_artifacts, package, import_lock=lock
                    )
                finally:
                    lock.release()
            return PreparedPackageImport(
                snapshot, package, preview, processed_handle
            )
        except Exception:
            if processed_handle is not None:
                processed_handle.cleanup()
            snapshot.cleanup()
            raise

    def commit(
        self,
        prepared: PreparedPackageImport,
        decisions: PreviewDecisionSet,
    ) -> PackageImportExecutionResult | Schema3TransactionGenesisResult:
        """Execute one still-owned prepared preview exactly once."""

        if not isinstance(prepared, PreparedPackageImport) or prepared.closed:
            raise PackageChanged()
        if prepared.processed_snapshot is not None:
            if self._processed_transaction is None:
                raise ValueError(
                    "processed preparation requires a Schema 3 transaction service"
                )
            prepared.closed = True
            return self._processed_transaction.execute_genesis(
                prepared.snapshot,
                prepared.processed_snapshot,
                prepared.package,
                prepared.preview,
                decisions,
            )
        try:
            return self._transaction.execute(
                prepared.snapshot,
                prepared.package,
                prepared.preview,
                decisions,
            )
        finally:
            prepared.closed = not prepared.snapshot.is_active

    @staticmethod
    def _source_digest(source: Path) -> str:
        try:
            before = require_plain_regular_file(source)
        except FileNotFoundError as error:
            raise PackageNotFound(error) from error
        except OSError as error:
            raise PackageChanged(error) from error
        if not 1 <= before.st_size <= MAX_PACKAGE_SIZE:
            raise PackageTooLarge()
        digest = sha256()
        length = 0
        try:
            with source.open("rb") as handle:
                opened = os.fstat(handle.fileno())
                if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                    raise PackageChanged()
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    length += len(chunk)
                    if length > MAX_PACKAGE_SIZE:
                        raise PackageTooLarge()
                    digest.update(chunk)
                after_handle = os.fstat(handle.fileno())
            after = require_plain_regular_file(source)
        except (PackageChanged, PackageTooLarge):
            raise
        except OSError as error:
            raise PackageChanged(error) from error
        stable = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
        if any(
            getattr(before, field) != getattr(after_handle, field)
            or getattr(before, field) != getattr(after, field)
            for field in stable
        ) or length != before.st_size:
            raise PackageChanged()
        return digest.hexdigest()
