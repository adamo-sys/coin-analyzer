"""Authoritative schema-2 import execution and startup-recovery services.

Durable Persistence "Persistence order", "Locking and cancellation model",
and RM-10 through RM-29.  This module is deliberately the application-facing
composition layer: lower persistence services never acquire the global lease.
"""

from __future__ import annotations

from dataclasses import replace
from contextlib import nullcontext
from hashlib import sha256
import os
from pathlib import Path
from typing import Callable
from uuid import uuid4

from coin_collection import CoinCollection

from ._json import canonical_json_bytes
from .collection_persistence import (
    DurableCollectionPublisher,
    serialize_collection_items,
)
from .cleanup_persistence import DurableCleanupExecutor
from .baseline import capture_collection_baseline
from .coordinator import PackageImportCoordinator, PreparedPackageImport
from .decisions import ImportDecisionModel
from .durable_models import (
    CleanupOperation,
    CleanupReceipt,
    OperationalJournalGeneration,
    OwnershipDescriptor,
    NativeObjectIdentity,
)
from .durable_repository import Schema2PackageImportJournalRepository
from .enums import (
    CleanupStatus,
    CollectionPublicationState,
    DuplicateDecision,
    ErrorCategory,
    ImportPhase,
    ImportResult,
    HISTORY_PHASES,
)
from .errors import CollectionCommitFailed, PackageChanged, RecoveryRequired
from .image_store import ManagedCollectionImageStore
from .lock import PackageImportLock, require_verified_import_lock
from ._filesystem import path_object_identity
from .package import CapturePackageValidator, ValidatedCapturePackage
from .preview import PackageImportPreview, PreviewDecisionSet
from .preview import PackageImportPreviewBuilder
from .models import ImportDecision
from .snapshot import CapturePackageSnapshotService, SnapshotHandle
from .terminal_persistence import TerminalPersistenceService
from .journal_repository import PackageImportJournalRepository
from .transaction import (
    PackageImportExecutionResult,
    PackageImportTransactionService,
    _utc_now,
)

Clock = Callable[[], str]
IdentifierFactory = Callable[[], str]


class Schema2PackageImportTransactionService(PackageImportTransactionService):
    """Execute the user-confirmed import exclusively through journal schema 2."""

    def __init__(
        self,
        collection: CoinCollection,
        *,
        lock_path: str | os.PathLike[str],
        journals: Schema2PackageImportJournalRepository,
        history_root: str | os.PathLike[str],
        snapshots: CapturePackageSnapshotService,
        image_store: ManagedCollectionImageStore,
        clock: Clock = _utc_now,
        identifier_factory: IdentifierFactory = lambda: str(uuid4()),
        ownership_token_factory: IdentifierFactory = lambda: str(uuid4()),
    ) -> None:
        # The base class supplies only deterministic CoinItem/audit construction.
        super().__init__(
            collection,
            lock_path=lock_path,
            journal_repository=journals,  # type: ignore[arg-type]
            image_store=image_store,
            clock=clock,
            identifier_factory=identifier_factory,
            ownership_token_factory=ownership_token_factory,
        )
        self._schema2_journals = journals
        self._snapshots = snapshots
        self._publisher = DurableCollectionPublisher(collection.storage_path)
        self._cleanup = DurableCleanupExecutor(
            {
                "SNAPSHOT": snapshots.root,
                "MANAGED_IMAGE": image_store.root,
                "COLLECTION": Path(collection.storage_path).absolute().parent,
            }
        )
        self._terminal = TerminalPersistenceService(
            journals,
            history_root,
            clock=clock,
            token_factory=identifier_factory,
        )

    def execute(
        self,
        snapshot: SnapshotHandle,
        package: ValidatedCapturePackage,
        preview: PackageImportPreview,
        decisions: PreviewDecisionSet,
        *,
        import_id: str,
        import_lock: PackageImportLock,
    ) -> PackageImportExecutionResult:
        """Perform one schema-2 transaction; ambiguous failure remains recoverable."""

        ImportDecisionModel.validate(preview, decisions)
        if (
            package.package_sha256 != preview.package_sha256
            or package.package_byte_length != preview.package_byte_length
            or package.package_basename != preview.package_basename
        ):
            raise PackageChanged()
        selected_ids = tuple(
            decision.source_coin_id
            for decision in decisions
            if decision.decision is DuplicateDecision.IMPORT_AS_NEW
        )
        if not selected_ids:
            snapshot.cleanup()
            return PackageImportExecutionResult(
                import_id=None,
                status=ImportResult.SUCCEEDED,
                proposed_count=len(preview.proposals),
                imported_count=0,
                skipped_count=len(preview.proposals),
                image_count=0,
                desktop_item_ids=(),
            )

        desktop_ids = tuple(self._identifier_factory() for _ in selected_ids)
        if len(set(desktop_ids)) != len(desktop_ids):
            raise CollectionCommitFailed()
        ownership_token = self._ownership_token_factory()
        mapping = dict(zip(selected_ids, desktop_ids, strict=True))
        plan = self._images.plan(
            package,
            import_id=import_id,
            ownership_token=ownership_token,
            source_to_desktop=mapping,
        )
        started_at = self._clock()

        with nullcontext(import_lock):
            current: OperationalJournalGeneration | None = None
            try:
                require_verified_import_lock(import_lock, import_id=import_id)
                locked_package = CapturePackageValidator().validate_snapshot(
                    snapshot,
                    package.package_basename,
                )
                if locked_package != package:
                    raise PackageChanged()
                from .baseline import require_collection_baseline

                require_collection_baseline(
                    self._collection.storage_path,
                    preview.collection_baseline,
                )
                existing = self._load_collection_strict()
                if {item.id for item in existing}.intersection(desktop_ids):
                    raise CollectionCommitFailed()
                expected_images = self._images.expected_evidence(package, plan)
                current = self._schema2_journals.create(
                    self._genesis(
                        snapshot,
                        package,
                        preview,
                        selected_ids,
                        desktop_ids,
                        import_id,
                        plan.import_root_relative_path,
                        ownership_token,
                        expected_images,
                        started_at,
                    ),
                    import_lock=import_lock,
                )
                current = self._append_phase(
                    current,
                    ImportPhase.COPYING_IMAGES,
                    import_lock,
                )
                photos = self._images.copy(
                    snapshot,
                    package,
                    plan,
                    lambda _path: None,
                    import_lock=import_lock,
                )
                for evidence in self._images.verified_evidence(package, plan):
                    current = self._append(
                        current,
                        import_lock,
                        verified_image_inventory=(
                            *current.verified_image_inventory,
                            evidence,
                        ),
                    )
                current = self._append_phase(
                    current,
                    ImportPhase.FILES_READY,
                    import_lock,
                )
                items = self._build_items(
                    preview,
                    selected_ids,
                    mapping,
                    photos,
                    started_at,
                )
                prospective = serialize_collection_items((*existing, *items))
                temporary, backup = self._publisher.plan(
                    prospective,
                    baseline=preview.collection_baseline,
                    import_id=import_id,
                    temporary_token=self._identifier_factory(),
                    backup_token=self._identifier_factory(),
                )
                current = self._append_phase(
                    current,
                    ImportPhase.COMMITTING_COLLECTION,
                    import_lock,
                    prospective_collection_byte_length=len(prospective),
                    prospective_collection_sha256=sha256(prospective).hexdigest(),
                    collection_publication="INTENT",
                    collection_temporary_artifact=temporary,
                    collection_backup_artifact=backup,
                )

                def record_temporary(artifact) -> None:
                    nonlocal current
                    assert current is not None
                    current = self._append(
                        current,
                        import_lock,
                        collection_temporary_artifact=artifact,
                    )

                temporary = self._publisher.create_temporary(
                    temporary,
                    prospective,
                    generation=current.generation + 1,
                    import_lock=import_lock,
                    on_created=record_temporary,
                )
                current = self._append(
                    current,
                    import_lock,
                    collection_temporary_artifact=temporary,
                )
                if backup is not None and os.name == "nt":

                    def record_backup(artifact) -> None:
                        nonlocal current
                        assert current is not None
                        current = self._append(
                            current,
                            import_lock,
                            collection_backup_artifact=artifact,
                        )

                    backup = self._publisher.create_windows_backup(
                        backup,
                        generation=current.generation + 1,
                        import_lock=import_lock,
                        on_created=record_backup,
                    )
                    current = self._append(
                        current,
                        import_lock,
                        collection_backup_artifact=backup,
                    )

                def record_exchange(prospective_artifact, backup_artifact) -> None:
                    nonlocal current
                    assert current is not None
                    current = self._append(
                        current,
                        import_lock,
                        collection_temporary_artifact=prospective_artifact,
                        collection_backup_artifact=backup_artifact,
                    )

                published, retained = self._publisher.publish(
                    temporary,
                    backup,
                    baseline=preview.collection_baseline,
                    exchange_generation=current.generation + 1,
                    publication_generation=current.generation + 1,
                    import_lock=import_lock,
                    on_exchanged=record_exchange,
                )
                audit = self._audit(
                    package,
                    decisions,
                    mapping,
                    plan,
                    started_at,
                    ImportPhase.SUCCEEDED,
                    None,
                )
                current = self._append_phase(
                    current,
                    ImportPhase.COLLECTION_COMMITTED,
                    import_lock,
                    collection_publication="VERIFIED",
                    collection_temporary_artifact=published,
                    collection_backup_artifact=retained,
                    committed_collection_item_ids=desktop_ids,
                    imported_count=len(desktop_ids),
                    pending_terminal_audit=audit.to_dict(),
                )
                if retained is not None:
                    target = OwnershipDescriptor(
                        root="COLLECTION",
                        relative_path=retained.current_relative_name,
                        object_kind="FILE",
                        ownership_token=ownership_token,
                        expected_byte_length=retained.expected_byte_length,
                        expected_sha256=retained.expected_sha256,
                        parent_identity=retained.expected_parent_identity,
                        object_identity=retained.object_identity,
                    )
                    current = self._cleanup_backup(
                        current,
                        retained,
                        target,
                        import_lock,
                    )
                snapshot_targets = self._snapshots.ownership_descriptors(
                    snapshot,
                    ownership_token,
                )
                current = self._cleanup_snapshot(
                    current,
                    snapshot,
                    snapshot_targets,
                    import_lock,
                )
                self._terminal.compact(
                    current,
                    result=ImportResult.SUCCEEDED,
                    import_lock=import_lock,
                )
                return PackageImportExecutionResult(
                    import_id=import_id,
                    status=ImportResult.SUCCEEDED,
                    proposed_count=len(preview.proposals),
                    imported_count=len(desktop_ids),
                    skipped_count=len(preview.proposals) - len(desktop_ids),
                    image_count=len(plan.media),
                    desktop_item_ids=desktop_ids,
                )
            except Exception as error:
                if current is not None and snapshot.is_active:
                    snapshot.preserve_for_recovery()
                if current is not None:
                    raise RecoveryRequired(error) from error
                raise

    def _genesis(
        self,
        snapshot,
        package,
        preview,
        selected_ids,
        desktop_ids,
        import_id,
        import_root,
        ownership_token,
        expected_images,
        timestamp,
    ) -> OperationalJournalGeneration:
        return OperationalJournalGeneration(
            journal_schema_version="2.0",
            import_id=import_id,
            random_ownership_token=ownership_token,
            generation=0,
            previous_generation_sha256=None,
            transition_id=self._identifier_factory(),
            next_generation_token=self._identifier_factory(),
            phase=ImportPhase.PREPARED,
            resume_phase=None,
            created_at=timestamp,
            updated_at=timestamp,
            package_sha256=package.package_sha256,
            package_version=package.manifest.package_version,
            package_basename=package.package_basename,
            snapshot_byte_length=snapshot.descriptor.byte_length,
            snapshot_relative_path=snapshot.descriptor.relative_path,
            collection_baseline_sha256_or_sentinel=preview.collection_baseline.sha256_or_sentinel,
            collection_baseline_byte_length=preview.collection_baseline.byte_length,
            prospective_collection_byte_length=None,
            prospective_collection_sha256=None,
            selected_source_coin_ids=selected_ids,
            desktop_item_ids=desktop_ids,
            import_root_relative_path=import_root,
            expected_image_inventory=expected_images,
            verified_image_inventory=(),
            committed_collection_item_ids=(),
            proposed_count=len(preview.proposals),
            imported_count=0,
            skipped_count=len(preview.proposals) - len(selected_ids),
            collection_publication="NONE",
            collection_temporary_artifact=None,
            collection_backup_artifact=None,
            cleanup_operations=(),
            pending_terminal_audit=None,
            compaction=None,
            error_category=None,
            recovery_attempt_count=0,
        )

    def _append_phase(self, previous, phase, import_lock, **changes):
        return self._append(previous, import_lock, phase=phase, **changes)

    def _append(self, previous, import_lock, **changes):
        successor = replace(
            previous,
            generation=previous.generation + 1,
            previous_generation_sha256=sha256(
                canonical_json_bytes(previous.to_dict())
            ).hexdigest(),
            transition_id=self._identifier_factory(),
            next_generation_token=self._identifier_factory(),
            updated_at=self._clock(),
            **changes,
        )
        return self._schema2_journals.append(
            previous,
            successor,
            import_lock=import_lock,
        )

    def _cleanup_backup(self, current, retained, target, import_lock):
        operation = CleanupOperation(
            kind="BASELINE_BACKUP",
            intent_id=self._identifier_factory(),
            intent_generation=current.generation + 1,
            targets=(target,),
            receipts=(),
            status=CleanupStatus.INTENT,
            completed_generation=None,
        )
        current = self._append(
            current,
            import_lock,
            cleanup_operations=(*current.cleanup_operations, operation),
        )
        removed_identity = self._cleanup.remove(
            target,
            import_id=current.import_id,
            ownership_token=current.random_ownership_token,
            import_lock=import_lock,
        )
        receipt = CleanupReceipt(
            target_relative_path=target.relative_path,
            removed_object_identity=removed_identity,
            removal_generation=current.generation + 1,
        )
        operation = replace(operation, receipts=(receipt,))
        current = self._append(
            current,
            import_lock,
            collection_backup_artifact=replace(
                retained,
                state=CollectionPublicationState.CLEANED,
                cleanup_operation_id=operation.intent_id,
            ),
            cleanup_operations=(*current.cleanup_operations[:-1], operation),
        )
        operation = replace(
            operation,
            status=CleanupStatus.COMPLETE,
            completed_generation=current.generation + 1,
        )
        return self._append(
            current,
            import_lock,
            cleanup_operations=(*current.cleanup_operations[:-1], operation),
        )

    def _cleanup_snapshot(self, current, snapshot, targets, import_lock):
        operation = CleanupOperation(
            kind="SUCCESS_SNAPSHOT",
            intent_id=self._identifier_factory(),
            intent_generation=current.generation + 1,
            targets=targets,
            receipts=(),
            status=CleanupStatus.INTENT,
            completed_generation=None,
        )
        current = self._append(
            current,
            import_lock,
            cleanup_operations=(*current.cleanup_operations, operation),
        )
        require_verified_import_lock(import_lock, import_id=current.import_id)
        snapshot.preserve_for_recovery()
        for target in targets:
            removed_identity = self._cleanup.remove(
                target,
                import_id=current.import_id,
                ownership_token=current.random_ownership_token,
                import_lock=import_lock,
            )
            receipt = CleanupReceipt(
                target_relative_path=target.relative_path,
                removed_object_identity=removed_identity,
                removal_generation=current.generation + 1,
            )
            operation = replace(operation, receipts=(*operation.receipts, receipt))
            current = self._append(
                current,
                import_lock,
                snapshot_relative_path=None,
                cleanup_operations=(*current.cleanup_operations[:-1], operation),
            )
        operation = replace(
            operation,
            status=CleanupStatus.COMPLETE,
            completed_generation=current.generation + 1,
        )
        return self._append(
            current,
            import_lock,
            cleanup_operations=(*current.cleanup_operations[:-1], operation),
        )


class Schema2PackageImportCoordinator(PackageImportCoordinator):
    """Own the in-process handoff and the one verified global execution lease."""

    def __init__(
        self,
        *,
        collection_path: str | os.PathLike[str],
        lock_path: str | os.PathLike[str],
        snapshots: CapturePackageSnapshotService,
        journals: Schema2PackageImportJournalRepository,
        terminal: TerminalPersistenceService,
        transaction: Schema2PackageImportTransactionService,
        identifier_factory: IdentifierFactory = lambda: str(uuid4()),
    ) -> None:
        self._collection_path = Path(collection_path)
        self._lock_path = Path(lock_path)
        self._snapshots = snapshots
        self._journals = journals
        self._terminal = terminal
        self._transaction = transaction
        self._identifier_factory = identifier_factory
        self._validator = CapturePackageValidator()
        self._preview_builder = PackageImportPreviewBuilder()

    def prepare(self, source_path: str | os.PathLike[str]) -> PreparedPackageImport:
        source = Path(source_path)
        digest = self._source_digest(source)
        snapshot = self._snapshots.create_snapshot(source, digest)
        try:
            package = self._validator.validate_snapshot(snapshot, source.name)
            preview = self._preview_builder.build(
                package,
                capture_collection_baseline(self._collection_path),
                completed_audits=tuple(
                    record.audit for record in self._terminal.list_final()
                ),
            )
            return PreparedPackageImport(snapshot, package, preview)
        except Exception:
            snapshot.cleanup()
            raise

    def commit(
        self,
        prepared: PreparedPackageImport,
        decisions: PreviewDecisionSet,
    ) -> PackageImportExecutionResult:
        if not isinstance(prepared, PreparedPackageImport) or prepared.closed:
            raise PackageChanged()
        import_id = self._identifier_factory()
        try:
            with PackageImportLock.acquire(
                self._lock_path,
                import_id=import_id,
            ) as import_lock:
                return self._transaction.execute(
                    prepared.snapshot,
                    prepared.package,
                    prepared.preview,
                    decisions,
                    import_id=import_id,
                    import_lock=import_lock,
                )
        finally:
            prepared.closed = not prepared.snapshot.is_active


class Schema2PackageImportRecoveryService:
    """Reconcile schema-2 authorities under one startup-owned global lease."""

    def __init__(
        self,
        *,
        lock_path: str | os.PathLike[str],
        journals: Schema2PackageImportJournalRepository,
        terminal: TerminalPersistenceService,
        snapshots: CapturePackageSnapshotService,
        transaction: Schema2PackageImportTransactionService,
    ) -> None:
        self._lock_path = Path(lock_path)
        self._journals = journals
        self._terminal = terminal
        self._snapshots = snapshots
        self._transaction = transaction

    def reconcile_pending_imports(self) -> tuple[object, ...]:
        """Finish every deterministic schema-2 state or fail closed."""

        results: list[object] = []
        with PackageImportLock.acquire(self._lock_path) as import_lock:
            require_verified_import_lock(import_lock)
            for import_id in self._terminal.pending_import_ids():
                results.append(
                    self._terminal.resume_pending(
                        import_id,
                        import_lock=import_lock,
                    )
                )
            legacy_names = self._validated_legacy_terminal_names()
            heads = self._journals.list_heads(
                import_lock=import_lock,
                validated_legacy_names=legacy_names,
            )
            references = tuple(
                head.snapshot_relative_path
                for head in heads
                if head.snapshot_relative_path is not None
            )
            self._snapshots.cleanup_orphaned_snapshots(
                references,
                import_lock=import_lock,
            )
            for head in heads:
                if head.phase is ImportPhase.COMPACTING:
                    results.append(
                        self._terminal.resume_compaction(
                            head.import_id,
                            import_lock=import_lock,
                        )
                    )
                elif head.phase is ImportPhase.COLLECTION_COMMITTED:
                    results.append(self._finish_success(head, import_lock))
                elif head.phase in {
                    ImportPhase.PREPARED,
                    ImportPhase.COPYING_IMAGES,
                    ImportPhase.FILES_READY,
                    ImportPhase.ROLLING_BACK,
                }:
                    results.append(self._finish_rollback(head, import_lock))
                elif head.phase is ImportPhase.COMMITTING_COLLECTION:
                    results.append(self._recover_committing(head, import_lock))
                else:
                    raise RecoveryRequired()
        return tuple(results)

    def _validated_legacy_terminal_names(self) -> frozenset[str]:
        if not self._journals.root.exists():
            return frozenset()
        names = frozenset(
            path.name
            for path in self._journals.root.iterdir()
            if path.is_file() and path.suffix == ".json"
        )
        if not names:
            return names
        legacy = PackageImportJournalRepository(self._journals.root)
        for name in names:
            entry = legacy.load(Path(name).stem)
            if entry.phase not in HISTORY_PHASES:
                raise RecoveryRequired()
        return names

    def _reopen(self, head):
        if head.snapshot_relative_path is None:
            raise RecoveryRequired()
        snapshot = self._snapshots.resume_snapshot(
            head.snapshot_relative_path,
            head.package_sha256,
            head.snapshot_byte_length,
        )
        package = CapturePackageValidator().validate_snapshot(
            snapshot,
            head.package_basename,
        )
        mapping = dict(
            zip(
                head.selected_source_coin_ids,
                head.desktop_item_ids,
                strict=True,
            )
        )
        plan = self._transaction._images.plan(
            package,
            import_id=head.import_id,
            ownership_token=head.random_ownership_token,
            source_to_desktop=mapping,
        )
        return snapshot, package, plan, mapping

    def _finish_success(self, head, import_lock):
        current = head
        snapshot = None
        try:
            snapshot_operation = next(
                (
                    operation
                    for operation in current.cleanup_operations
                    if operation.kind == "SUCCESS_SNAPSHOT"
                ),
                None,
            )
            if (
                current.snapshot_relative_path is not None
                and snapshot_operation is None
            ):
                snapshot, _package, _plan, _mapping = self._reopen(current)
            retained = current.collection_backup_artifact
            if (
                retained is not None
                and retained.state is CollectionPublicationState.RETAINED
            ):
                target = OwnershipDescriptor(
                    root="COLLECTION",
                    relative_path=retained.current_relative_name,
                    object_kind="FILE",
                    ownership_token=current.random_ownership_token,
                    expected_byte_length=retained.expected_byte_length,
                    expected_sha256=retained.expected_sha256,
                    parent_identity=retained.expected_parent_identity,
                    object_identity=retained.object_identity,
                )
                existing = next(
                    (
                        operation
                        for operation in current.cleanup_operations
                        if operation.kind == "BASELINE_BACKUP"
                    ),
                    None,
                )
                if existing is None:
                    current = self._transaction._cleanup_backup(
                        current,
                        retained,
                        target,
                        import_lock,
                    )
                elif existing.status is CleanupStatus.INTENT:
                    current = self._resume_cleanup(
                        current,
                        existing,
                        import_lock,
                        cleaned_backup=retained,
                    )
            if snapshot_operation is None:
                if snapshot is None:
                    raise RecoveryRequired()
                targets = self._snapshots.ownership_descriptors(
                    snapshot,
                    current.random_ownership_token,
                )
                current = self._transaction._cleanup_snapshot(
                    current,
                    snapshot,
                    targets,
                    import_lock,
                )
            elif snapshot_operation.status is CleanupStatus.INTENT:
                if snapshot is not None and snapshot.is_active:
                    snapshot.preserve_for_recovery()
                current = self._resume_cleanup(
                    current,
                    snapshot_operation,
                    import_lock,
                    clear_snapshot=True,
                )
            return self._terminal.compact(
                current,
                result=ImportResult.SUCCEEDED,
                import_lock=import_lock,
            )
        except BaseException:
            if snapshot is not None and snapshot.is_active:
                snapshot.preserve_for_recovery()
            raise

    def _recover_committing(self, head, import_lock):
        observed = capture_collection_baseline(
            self._transaction._collection.storage_path
        )
        baseline_matches = (
            observed.sha256_or_sentinel
            == head.collection_baseline_sha256_or_sentinel
            and observed.byte_length == head.collection_baseline_byte_length
        )
        prospective_matches = (
            head.prospective_collection_sha256 is not None
            and observed.sha256_or_sentinel == head.prospective_collection_sha256
            and observed.byte_length == head.prospective_collection_byte_length
        )
        if baseline_matches:
            return self._finish_rollback(head, import_lock)
        if not prospective_matches:
            raise RecoveryRequired()
        snapshot, package, plan, mapping = self._reopen(head)
        try:
            self._transaction._images.verify(plan)
            temporary = head.collection_temporary_artifact
            if temporary is None or temporary.object_identity is None:
                raise RecoveryRequired()
            collection_path = Path(
                self._transaction._collection.storage_path
            ).absolute()
            actual_identity = NativeObjectIdentity.from_native(
                path_object_identity(collection_path),
                windows=os.name == "nt",
            )
            if actual_identity != temporary.object_identity:
                raise RecoveryRequired()
            published = replace(
                temporary,
                state=CollectionPublicationState.PUBLISHED,
                current_relative_name=collection_path.name,
                published_relative_name=collection_path.name,
                publication_generation=head.generation + 1,
            )
            backup = head.collection_backup_artifact
            retained = None
            if backup is not None:
                backup_name = backup.current_relative_name or backup.relative_name
                backup_path = collection_path.parent / backup_name
                if not backup_path.is_file():
                    raise RecoveryRequired()
                self._transaction._publisher._verify_exact(
                    backup_path,
                    backup.expected_byte_length,
                    backup.expected_sha256,
                )
                backup_identity = NativeObjectIdentity.from_native(
                    path_object_identity(backup_path),
                    windows=os.name == "nt",
                )
                if (
                    backup.object_identity is not None
                    and backup_identity != backup.object_identity
                ):
                    raise RecoveryRequired()
                retained = replace(
                    backup,
                    state=CollectionPublicationState.RETAINED,
                    object_identity=backup_identity,
                    verified_byte_length=backup.expected_byte_length,
                    verified_sha256=backup.expected_sha256,
                    verified_generation=(
                        backup.verified_generation or head.generation + 1
                    ),
                    current_relative_name=backup_name,
                    publication_generation=head.generation + 1,
                )
            decisions = PreviewDecisionSet(
                preview_fingerprint="0" * 64,
                decisions=tuple(
                    ImportDecision(
                        coin.id,
                        DuplicateDecision.IMPORT_AS_NEW
                        if coin.id in mapping
                        else DuplicateDecision.SKIP,
                    )
                    for coin in package.manifest.coins
                ),
            )
            audit = self._transaction._audit(
                package,
                decisions,
                mapping,
                plan,
                head.created_at,
                ImportPhase.SUCCEEDED,
                None,
            )
            current = self._transaction._append_phase(
                head,
                ImportPhase.COLLECTION_COMMITTED,
                import_lock,
                collection_publication="VERIFIED",
                collection_temporary_artifact=published,
                collection_backup_artifact=retained,
                committed_collection_item_ids=head.desktop_item_ids,
                imported_count=len(head.desktop_item_ids),
                pending_terminal_audit=audit.to_dict(),
            )
        except BaseException:
            if snapshot.is_active:
                snapshot.preserve_for_recovery()
            raise
        if snapshot.is_active:
            snapshot.preserve_for_recovery()
        return self._finish_success(current, import_lock)

    def _resume_cleanup(
        self,
        current,
        operation,
        import_lock,
        *,
        clear_snapshot: bool = False,
        cleaned_backup=None,
    ):
        for target in operation.targets[len(operation.receipts) :]:
            removed_identity = self._transaction._cleanup.remove(
                target,
                import_id=current.import_id,
                ownership_token=current.random_ownership_token,
                import_lock=import_lock,
            )
            receipt = CleanupReceipt(
                target_relative_path=target.relative_path,
                removed_object_identity=removed_identity,
                removal_generation=current.generation + 1,
            )
            operation = replace(
                operation,
                receipts=(*operation.receipts, receipt),
            )
            changes = {
                "cleanup_operations": (
                    *current.cleanup_operations[:-1],
                    operation,
                )
            }
            if clear_snapshot:
                changes["snapshot_relative_path"] = None
            if cleaned_backup is not None:
                changes["collection_backup_artifact"] = replace(
                    cleaned_backup,
                    state=CollectionPublicationState.CLEANED,
                    cleanup_operation_id=operation.intent_id,
                )
            current = self._transaction._append(
                current,
                import_lock,
                **changes,
            )
        operation = replace(
            operation,
            status=CleanupStatus.COMPLETE,
            completed_generation=current.generation + 1,
        )
        return self._transaction._append(
            current,
            import_lock,
            cleanup_operations=(
                *current.cleanup_operations[:-1],
                operation,
            ),
        )

    def _finish_rollback(self, head, import_lock):
        from .baseline import require_collection_baseline
        from .models import CollectionBaseline

        require_collection_baseline(
            self._transaction._collection.storage_path,
            CollectionBaseline(
                head.collection_baseline_sha256_or_sentinel,
                head.collection_baseline_byte_length,
            ),
        )
        existing_operation = next(
            (
                operation
                for operation in head.cleanup_operations
                if operation.kind == "ROLLBACK_ALL"
            ),
            None,
        )
        if existing_operation is not None:
            current = head
            if existing_operation.status is CleanupStatus.INTENT:
                current = self._resume_cleanup(
                    current,
                    existing_operation,
                    import_lock,
                    clear_snapshot=True,
                )
            return self._terminal.compact(
                current,
                result=ImportResult.ROLLED_BACK,
                error_category=ErrorCategory.ROLLED_BACK.value,
                import_lock=import_lock,
            )
        snapshot, package, plan, mapping = self._reopen(head)
        current = head
        decisions = PreviewDecisionSet(
            preview_fingerprint="0" * 64,
            decisions=tuple(
                ImportDecision(
                    coin.id,
                    DuplicateDecision.IMPORT_AS_NEW
                    if coin.id in mapping
                    else DuplicateDecision.SKIP,
                )
                for coin in package.manifest.coins
            ),
        )
        audit = self._transaction._audit(
            package,
            decisions,
            mapping,
            plan,
            head.created_at,
            ImportPhase.ROLLED_BACK,
            ErrorCategory.ROLLED_BACK,
        )
        current = self._transaction._append_phase(
            current,
            ImportPhase.ROLLING_BACK,
            import_lock,
            pending_terminal_audit=audit.to_dict(),
        )
        try:
            targets = []
            for artifact in (
                current.collection_temporary_artifact,
                current.collection_backup_artifact,
            ):
                if (
                    artifact is None
                    or artifact.object_identity is None
                    or artifact.current_relative_name is None
                ):
                    continue
                targets.append(
                    OwnershipDescriptor(
                        root="COLLECTION",
                        relative_path=artifact.current_relative_name,
                        object_kind="FILE",
                        ownership_token=current.random_ownership_token,
                        expected_byte_length=artifact.expected_byte_length,
                        expected_sha256=artifact.expected_sha256,
                        parent_identity=artifact.expected_parent_identity,
                        object_identity=artifact.object_identity,
                    )
                )
            if (self._transaction._images.root / plan.import_root_relative_path).exists():
                targets.extend(
                    self._transaction._images.ownership_descriptors(
                        plan,
                        require_complete=False,
                    )
                )
            targets.extend(
                self._snapshots.ownership_descriptors(
                    snapshot,
                    current.random_ownership_token,
                )
            )
            operation = CleanupOperation(
                kind="ROLLBACK_ALL",
                intent_id=self._transaction._identifier_factory(),
                intent_generation=current.generation + 1,
                targets=tuple(targets),
                receipts=(),
                status=CleanupStatus.INTENT,
                completed_generation=None,
            )
            current = self._transaction._append(
                current,
                import_lock,
                cleanup_operations=(*current.cleanup_operations, operation),
            )
            snapshot.preserve_for_recovery()
            for target in targets:
                removed_identity = self._transaction._cleanup.remove(
                    target,
                    import_id=current.import_id,
                    ownership_token=current.random_ownership_token,
                    import_lock=import_lock,
                )
                receipt = CleanupReceipt(
                    target_relative_path=target.relative_path,
                    removed_object_identity=removed_identity,
                    removal_generation=current.generation + 1,
                )
                operation = replace(
                    operation,
                    receipts=(*operation.receipts, receipt),
                )
                current = self._transaction._append(
                    current,
                    import_lock,
                    snapshot_relative_path=(
                        None
                        if target.root == "SNAPSHOT"
                        else current.snapshot_relative_path
                    ),
                    cleanup_operations=(
                        *current.cleanup_operations[:-1],
                        operation,
                    ),
                )
            operation = replace(
                operation,
                status=CleanupStatus.COMPLETE,
                completed_generation=current.generation + 1,
            )
            current = self._transaction._append(
                current,
                import_lock,
                cleanup_operations=(
                    *current.cleanup_operations[:-1],
                    operation,
                ),
            )
            return self._terminal.compact(
                current,
                result=ImportResult.ROLLED_BACK,
                error_category=ErrorCategory.ROLLED_BACK.value,
                import_lock=import_lock,
            )
        except BaseException:
            if snapshot.is_active:
                snapshot.preserve_for_recovery()
            raise
