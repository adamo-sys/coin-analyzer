"""Concrete post-genesis Schema 3 execution and restart progression."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Callable
import os

from coin_collection import CoinCollection

from ._json import canonical_json_bytes
from .baseline import capture_collection_baseline, require_collection_baseline
from .cleanup_persistence import Schema3CleanupProtocol
from .collection_persistence import (
    DurableCollectionPublisher,
    serialize_collection_items,
)
from .decisions import ImportDecisionModel
from .durable_models import (
    OperationalJournalGenerationV3,
    OwnershipDescriptorV3,
    TerminalHistoryRecordV2,
)
from .durable_repository import Schema3PackageImportJournalRepository
from .enums import (
    CleanupStatus,
    DuplicateDecision,
    ErrorCategory,
    ImportPhase,
    ImportResult,
)
from .errors import RecoveryRequired
from .image_store import ManagedCollectionImageStore
from .lock import PackageImportLock, require_verified_import_lock
from .models import CollectionBaseline, ImportDecision
from .package import CapturePackageValidator
from .preview import PackageImportPreview, PreviewDecisionSet
from .processed_snapshot import ProcessedArtifactSnapshotService
from .snapshot import CapturePackageSnapshotService
from .terminal_persistence import Schema3TerminalPersistenceService
from .transaction import PackageImportTransactionService

Clock = Callable[[], str]
TokenFactory = Callable[[], str]


class Schema3PackageImportRecoveryService:
    """Advance one Schema 3 head while the caller retains the global lock."""

    def __init__(
        self,
        *,
        collection: CoinCollection,
        journals: Schema3PackageImportJournalRepository,
        snapshots: CapturePackageSnapshotService,
        processed_snapshots: ProcessedArtifactSnapshotService,
        images: ManagedCollectionImageStore,
        publisher: DurableCollectionPublisher,
        cleanup: Schema3CleanupProtocol,
        terminal: Schema3TerminalPersistenceService,
        clock: Clock,
        token_factory: TokenFactory,
    ) -> None:
        self._collection = collection
        self._journals = journals
        self._snapshots = snapshots
        self._processed = processed_snapshots
        self._images = images
        self._publisher = publisher
        self._cleanup = cleanup
        self._terminal = terminal
        self._clock = clock
        self._token_factory = token_factory

    def _append(self, previous, import_lock, **changes):
        require_verified_import_lock(import_lock, import_id=previous.import_id)
        successor = replace(
            previous,
            generation=previous.generation + 1,
            previous_generation_sha256=sha256(
                canonical_json_bytes(previous.to_dict())
            ).hexdigest(),
            transition_id=previous.next_generation_token,
            next_generation_token=self._token_factory(),
            updated_at=self._clock(),
            **changes,
        )
        successor.validate()
        return self._journals.append(
            previous, successor, import_lock=import_lock
        )

    @staticmethod
    def _v3(target):
        if isinstance(target, OwnershipDescriptorV3):
            return target
        return OwnershipDescriptorV3(
            target.root,
            target.relative_path,
            target.object_kind,
            target.ownership_token,
            target.expected_byte_length,
            target.expected_sha256,
            target.parent_identity,
            target.object_identity,
        )

    def _reopen(self, head, import_lock):
        if (
            head.package_snapshot_relative_path is None
            or head.processed_snapshot_reference is None
        ):
            raise RecoveryRequired()
        raw = self._snapshots.resume_snapshot(
            head.package_snapshot_relative_path,
            head.package_sha256,
            head.snapshot_byte_length,
        )
        processed = self._processed.open_snapshot(
            head.processed_snapshot_reference.processed_snapshot_id,
            import_lock=import_lock,
        )
        package = CapturePackageValidator().validate_snapshot(
            raw, head.package_basename
        )
        if (
            processed.journal_reference() != head.processed_snapshot_reference
            or processed.media_commitment(head.selected_source_coin_ids)
            != head.processed_media_commitment
        ):
            raise RecoveryRequired()
        mapping = dict(
            zip(
                head.selected_source_coin_ids,
                head.desktop_item_ids,
                strict=True,
            )
        )
        plan = self._images.plan_processed(
            processed,
            package,
            import_id=head.import_id,
            ownership_token=head.random_ownership_token,
            source_to_desktop=mapping,
        )
        return raw, processed, package, plan, mapping

    def progress_foreground_locked(
        self,
        head: OperationalJournalGenerationV3,
        raw,
        processed,
        package,
        preview: PackageImportPreview,
        decisions: PreviewDecisionSet,
        import_lock: PackageImportLock,
    ) -> OperationalJournalGenerationV3:
        """Use the original decision context through collection publication."""

        require_verified_import_lock(import_lock, import_id=head.import_id)
        ImportDecisionModel.validate(preview, decisions)
        mapping = dict(
            zip(head.selected_source_coin_ids, head.desktop_item_ids, strict=True)
        )
        plan = self._images.plan_processed(
            processed,
            package,
            import_id=head.import_id,
            ownership_token=head.random_ownership_token,
            source_to_desktop=mapping,
        )
        current = self._append(
            head, import_lock, phase=ImportPhase.COPYING_IMAGES
        )

        def verified(evidence):
            nonlocal current
            current = self._append(
                current,
                import_lock,
                verified_image_inventory=(
                    *current.verified_image_inventory,
                    evidence,
                ),
            )

        photos = self._images.copy_processed(
            processed,
            plan,
            lambda _path: None,
            import_lock=import_lock,
            on_image_verified=verified,
        )
        current = self._append(
            current, import_lock, phase=ImportPhase.FILES_READY
        )
        existing = PackageImportTransactionService._load_collection_strict(self)
        items = PackageImportTransactionService._build_items(
            self,
            preview,
            head.selected_source_coin_ids,
            mapping,
            photos,
            head.created_at,
        )
        prospective = serialize_collection_items((*existing, *items))
        baseline = preview.collection_baseline
        temporary, backup = self._publisher.plan(
            prospective,
            baseline=baseline,
            import_id=head.import_id,
            temporary_token=self._token_factory(),
            backup_token=self._token_factory(),
        )
        current = self._append(
            current,
            import_lock,
            phase=ImportPhase.COMMITTING_COLLECTION,
            prospective_collection_byte_length=len(prospective),
            prospective_collection_sha256=sha256(prospective).hexdigest(),
            collection_publication="INTENT",
            collection_temporary_artifact=temporary,
            collection_backup_artifact=backup,
        )
        def record_temporary(artifact):
            nonlocal current
            current = self._append(
                current, import_lock, collection_temporary_artifact=artifact
            )

        temporary = self._publisher.create_temporary(
            temporary,
            prospective,
            generation=current.generation + 1,
            import_lock=import_lock,
            on_created=record_temporary,
        )
        current = self._append(
            current, import_lock, collection_temporary_artifact=temporary
        )
        if backup is not None and os.name == "nt":
            def record_backup(artifact):
                nonlocal current
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
                current, import_lock, collection_backup_artifact=backup
            )
        def record_exchange(prospective_artifact, backup_artifact):
            nonlocal current
            current = self._append(
                current,
                import_lock,
                collection_temporary_artifact=prospective_artifact,
                collection_backup_artifact=backup_artifact,
            )

        published, retained = self._publisher.publish(
            temporary,
            backup,
            baseline=baseline,
            exchange_generation=current.generation + 1,
            publication_generation=current.generation + 1,
            import_lock=import_lock,
            on_exchanged=record_exchange,
        )
        current = self._append(
            current,
            import_lock,
            phase=ImportPhase.COLLECTION_COMMITTED,
            collection_publication="VERIFIED",
            collection_temporary_artifact=published,
            collection_backup_artifact=retained,
            committed_collection_item_ids=head.desktop_item_ids,
            imported_count=len(head.desktop_item_ids),
            pending_terminal_audit=PackageImportTransactionService._audit(
                self,
                package,
                decisions,
                mapping,
                plan,
                head.created_at,
                ImportPhase.SUCCEEDED,
                None,
            ).to_dict(),
        )
        raw.preserve_for_recovery()
        processed.close()
        return self._start_success_cleanup(current, import_lock)

    def recover_locked(
        self,
        head: OperationalJournalGenerationV3,
        import_lock: PackageImportLock,
    ) -> OperationalJournalGenerationV3 | TerminalHistoryRecordV2:
        require_verified_import_lock(import_lock, import_id=head.import_id)
        head.validate()
        if head.phase is ImportPhase.COMPACTING:
            return self._terminal.recover_compacting(
                head, import_lock=import_lock
            )
        if head.cleanup_operations:
            return self._resume_cleanup(head, import_lock)
        if head.phase is ImportPhase.COLLECTION_COMMITTED:
            return self._start_success_cleanup(head, import_lock)
        if head.phase is ImportPhase.COMMITTING_COLLECTION:
            return self._recover_committing(head, import_lock)
        if head.phase in {
            ImportPhase.PREPARED,
            ImportPhase.COPYING_IMAGES,
            ImportPhase.FILES_READY,
            ImportPhase.ROLLING_BACK,
            ImportPhase.RECOVERY_REQUIRED,
            ImportPhase.ROLLBACK_FAILED,
        }:
            return self._start_rollback(head, import_lock)
        raise RecoveryRequired()

    def cancel_locked(self, head, import_lock):
        """Convert only pre-publication cancellation into durable rollback."""

        require_verified_import_lock(import_lock, import_id=head.import_id)
        if head.phase in {
            ImportPhase.COMMITTING_COLLECTION,
            ImportPhase.COLLECTION_COMMITTED,
            ImportPhase.COMPACTING,
        }:
            raise RecoveryRequired()
        return self._start_rollback(
            head, import_lock, result=ImportResult.CANCELLED
        )

    def _recover_committing(self, head, import_lock):
        baseline = CollectionBaseline(
            head.collection_baseline_sha256_or_sentinel,
            head.collection_baseline_byte_length,
        )
        observation = self._publisher.observe_planned(
            head.collection_temporary_artifact,
            head.collection_backup_artifact,
            import_id=head.import_id,
            baseline=baseline,
            prospective_byte_length=head.prospective_collection_byte_length,
            prospective_sha256=head.prospective_collection_sha256,
            observation_generation=head.generation + 1,
            import_lock=import_lock,
        )
        if observation.state == "EXACT_BASELINE":
            return self._start_rollback(head, import_lock)
        if observation.state != "EXACT_PROSPECTIVE":
            raise RecoveryRequired()
        if observation.published_artifact is None:
            raise RecoveryRequired()
        raw, processed, _package, plan, _mapping = self._reopen(
            head, import_lock
        )
        try:
            self._images.reconcile_processed_copy(
                plan, head.verified_image_inventory
            )
            photos = self._images.photos_from_processed_plan(plan)
            self._images.validate_processed_photos(plan, photos)
            decisions = PreviewDecisionSet(
                preview_fingerprint="0" * 64,
                decisions=tuple(
                    ImportDecision(
                        coin.id,
                        DuplicateDecision.IMPORT_AS_NEW
                        if coin.id in head.selected_source_coin_ids
                        else DuplicateDecision.SKIP,
                    )
                    for coin in _package.manifest.coins
                ),
            )
            current = self._append(
                head,
                import_lock,
                phase=ImportPhase.COLLECTION_COMMITTED,
                collection_publication="VERIFIED",
                collection_temporary_artifact=observation.published_artifact,
                collection_backup_artifact=(
                    observation.retained_backup_artifact
                ),
                committed_collection_item_ids=head.desktop_item_ids,
                imported_count=len(head.desktop_item_ids),
                pending_terminal_audit=PackageImportTransactionService._audit(
                    self,
                    _package,
                    decisions,
                    _mapping,
                    plan,
                    head.created_at,
                    ImportPhase.SUCCEEDED,
                    None,
                ).to_dict(),
            )
        finally:
            raw.preserve_for_recovery()
            processed.close()
        return self._start_success_cleanup(current, import_lock)

    def _start_rollback(
        self,
        head,
        import_lock,
        *,
        result: ImportResult = ImportResult.ROLLED_BACK,
    ):
        raw, processed, _package, plan, _mapping = self._reopen(
            head, import_lock
        )
        try:
            if head.verified_image_inventory:
                self._images.reconcile_processed_copy(
                    plan, head.verified_image_inventory
                )
            targets = []
            for artifact in (
                head.collection_temporary_artifact,
                head.collection_backup_artifact,
            ):
                if (
                    artifact is not None
                    and artifact.object_identity is not None
                    and artifact.current_relative_name is not None
                ):
                    targets.append(
                        OwnershipDescriptorV3(
                            "COLLECTION",
                            artifact.current_relative_name,
                            "FILE",
                            head.random_ownership_token,
                            artifact.expected_byte_length,
                            artifact.expected_sha256,
                            artifact.expected_parent_identity,
                            artifact.object_identity,
                        )
                    )
            if (self._images.root / plan.import_root_relative_path).exists():
                targets.extend(
                    self._v3(item)
                    for item in self._images.ownership_descriptors(
                        plan, require_complete=False
                    )
                )
            targets.extend(processed.cleanup_targets(head.random_ownership_token))
            targets.extend(
                self._v3(item)
                for item in raw.ownership_descriptors(
                    head.random_ownership_token
                )
            )
            current = head
            if current.phase is not ImportPhase.ROLLING_BACK:
                decisions = PreviewDecisionSet(
                    preview_fingerprint="0" * 64,
                    decisions=tuple(
                        ImportDecision(
                            coin.id,
                            DuplicateDecision.IMPORT_AS_NEW
                            if coin.id in head.selected_source_coin_ids
                            else DuplicateDecision.SKIP,
                        )
                        for coin in _package.manifest.coins
                    ),
                )
                terminal_phase = (
                    ImportPhase.CANCELLED
                    if result is ImportResult.CANCELLED
                    else ImportPhase.ROLLED_BACK
                )
                category = (
                    None
                    if result is ImportResult.CANCELLED
                    else ErrorCategory.ROLLED_BACK
                )
                audit = PackageImportTransactionService._audit(
                    self,
                    _package,
                    decisions,
                    _mapping,
                    plan,
                    head.created_at,
                    terminal_phase,
                    category,
                )
                current = self._append(
                    head,
                    import_lock,
                    phase=ImportPhase.ROLLING_BACK,
                    pending_terminal_audit=audit.to_dict(),
                )
            processed.close()
            raw.preserve_for_recovery()
            return self._cleanup.begin_rollback(
                current,
                targets=tuple(targets),
                import_lock=import_lock,
            )
        except BaseException:
            if processed.is_active:
                processed.close()
            if raw.is_active:
                raw.preserve_for_recovery()
            raise

    def _start_success_cleanup(self, head, import_lock):
        if head.processed_snapshot_reference is None:
            if head.package_snapshot_relative_path is None:
                return head
            raw = self._snapshots.resume_snapshot(
                head.package_snapshot_relative_path,
                head.package_sha256,
                head.snapshot_byte_length,
            )
            try:
                raw_targets = tuple(
                    self._v3(item)
                    for item in raw.ownership_descriptors(
                        head.random_ownership_token
                    )
                )
                raw.preserve_for_recovery()
                return self._cleanup.begin_success_next(
                    head,
                    processed_targets=(),
                    raw_targets=raw_targets,
                    import_lock=import_lock,
                )
            except BaseException:
                if raw.is_active:
                    raw.preserve_for_recovery()
                raise
        raw, processed, _package, _plan, _mapping = self._reopen(
            head, import_lock
        )
        processed_targets = processed.cleanup_targets(
            head.random_ownership_token
        )
        raw_targets = tuple(
            self._v3(item)
            for item in raw.ownership_descriptors(head.random_ownership_token)
        )
        baseline_targets = ()
        retained = head.collection_backup_artifact
        if (
            retained is not None
            and retained.object_identity is not None
            and retained.current_relative_name is not None
        ):
            baseline_targets = (
                OwnershipDescriptorV3(
                    "COLLECTION",
                    retained.current_relative_name,
                    "FILE",
                    head.random_ownership_token,
                    retained.expected_byte_length,
                    retained.expected_sha256,
                    retained.expected_parent_identity,
                    retained.object_identity,
                ),
            )
        processed.close()
        raw.preserve_for_recovery()
        return self._cleanup.begin_success_next(
            head,
            baseline_targets=baseline_targets,
            processed_targets=processed_targets,
            raw_targets=raw_targets,
            import_lock=import_lock,
        )

    def _resume_cleanup(self, head, import_lock):
        current = head
        operation = current.cleanup_operations[-1]
        if operation.status is CleanupStatus.INTENT:
            processed_indices = [
                index
                for index, target in enumerate(operation.targets)
                if target.root == "PROCESSED_SNAPSHOT"
            ]
            processed_done = processed_indices and all(
                index < len(operation.receipts) for index in processed_indices
            )
            raw_started = any(
                index < len(operation.receipts) and target.root == "SNAPSHOT"
                for index, target in enumerate(operation.targets)
            )
            if (
                operation.kind == "ROLLBACK_ALL"
                and processed_done
                and not raw_started
                and current.processed_snapshot_reference is not None
            ):
                current = self._cleanup.release_processed_reference(
                    current, import_lock=import_lock
                )
            current = self._cleanup.advance(current, import_lock=import_lock)
            operation = current.cleanup_operations[-1]
        if operation.status is CleanupStatus.COMPLETE:
            if (
                operation.kind == "SUCCESS_PROCESSED_SNAPSHOT"
                and current.processed_snapshot_reference is not None
            ):
                current = self._cleanup.release_processed_reference(
                    current, import_lock=import_lock
                )
            if operation.kind != "ROLLBACK_ALL":
                current = self._start_success_cleanup(current, import_lock)
        return self._compact_if_eligible(current, import_lock)

    def _compact_if_eligible(self, head, import_lock):
        if (
            not isinstance(head, OperationalJournalGenerationV3)
            or head.package_snapshot_relative_path is not None
            or head.processed_snapshot_reference is not None
            or not head.cleanup_operations
            or any(
                operation.status is not CleanupStatus.COMPLETE
                for operation in head.cleanup_operations
            )
        ):
            return head
        if head.phase is ImportPhase.COLLECTION_COMMITTED:
            result = ImportResult.SUCCEEDED
            category = None
        elif head.phase is ImportPhase.ROLLING_BACK:
            if head.pending_terminal_audit is None:
                raise RecoveryRequired()
            result = ImportResult(
                head.pending_terminal_audit["final_status"]
            )
            if result not in {
                ImportResult.ROLLED_BACK,
                ImportResult.CANCELLED,
            }:
                raise RecoveryRequired()
            category = (
                None
                if result is ImportResult.CANCELLED
                else ErrorCategory.ROLLED_BACK.value
            )
        else:
            raise RecoveryRequired()
        return self._terminal.compact(
            head,
            result=result,
            error_category=category,
            import_lock=import_lock,
        )
