"""Fail-closed restart reconciliation for durable package imports."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable

from coin_collection import CoinItem, ItemPhoto, PhotoRole

from .audit import AuditCoin, AuditSession
from .enums import (
    DuplicateDecision,
    ErrorCategory,
    HISTORY_PHASES,
    ImportPhase,
    ImportResult,
)
from .errors import RecoveryRequired, RollbackFailed
from .events import ImportEventBus
from .image_store import ManagedCollectionImageStore
from .journal import JournalEntry
from .journal_repository import PackageImportJournalRepository
from .limits import AUDIT_SCHEMA_VERSION
from .lock import PackageImportLock
from .package import CapturePackageValidator, ValidatedCapturePackage
from .snapshot import CapturePackageSnapshotService, SnapshotHandle

from .durable_models import (
    OperationalJournalGeneration,
    OperationalJournalGenerationV3,
    TerminalProcessedMediaProof,
)
from .durable_repository import VersionedPackageImportJournalRepository
from .lock import require_verified_import_lock
from .processed_snapshot import ProcessedArtifactSnapshotService
from .terminal_persistence import (
    Schema3TerminalPersistenceService,
    TerminalPersistenceService,
)
from .schema3_runtime import Schema3PackageImportRecoveryService

Clock = Callable[[], str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class PackageImportRecoveryService:
    """Reconcile pending journals exactly once under the shared lock."""

    def __init__(
        self,
        *,
        collection_path: str | Path,
        lock_path: str | Path,
        journals: PackageImportJournalRepository,
        snapshots: CapturePackageSnapshotService,
        images: ManagedCollectionImageStore,
        clock: Clock = _utc_now,
        event_bus: ImportEventBus | None = None,
    ) -> None:
        self._collection_path = Path(collection_path)
        self._lock_path = Path(lock_path)
        self._journals = journals
        self._snapshots = snapshots
        self._images = images
        self._clock = clock
        self._event_bus = event_bus

    def reconcile_pending_imports(self) -> tuple[JournalEntry, ...]:
        """Reconcile every non-history journal or fail without broad cleanup."""

        results: list[JournalEntry] = []
        with PackageImportLock.acquire(self._lock_path) as import_lock:
            entries = self._journals.list_entries()
            references = tuple(
                entry.snapshot_relative_path
                for entry in entries
                if entry.snapshot_relative_path is not None
            )
            self._snapshots.cleanup_orphaned_snapshots(
                references,
                import_lock=import_lock,
            )
            for entry in entries:
                if entry.phase in HISTORY_PHASES:
                    if entry.phase is ImportPhase.SUCCEEDED and entry.cleanup_pending:
                        results.append(
                            self._journals.update(
                                entry,
                                replace(
                                    entry,
                                    cleanup_pending=False,
                                    updated_at=self._clock(),
                                ),
                            )
                        )
                    continue
                results.append(self._reconcile_locked(entry, import_lock))
        return tuple(results)

    def _reconcile_locked(
        self,
        entry: JournalEntry,
        import_lock: PackageImportLock,
    ) -> JournalEntry:
        current = self._journals.load(entry.import_id)
        if current != entry:
            raise RecoveryRequired()
        current = self._enter_recovery(current)
        collection_items = self._collection_items()
        collection_ids = set(collection_items)
        reserved = set(current.desktop_item_ids)
        present = reserved.intersection(collection_ids)
        if present and present != reserved:
            self._fail_ambiguous_commit(current)
        handle, package, plan = self._reopen(current)
        try:
            if present == reserved and reserved:
                if not self._reserved_records_match(
                    current, package, plan, collection_items
                ):
                    self._fail_ambiguous_commit(current)
                return self._finish_committed(current, handle, package, plan)
            return self._finish_rollback(
                current,
                handle,
                package,
                plan,
                import_lock,
            )
        except BaseException:
            if handle.is_active:
                handle.preserve_for_recovery()
            raise

    def _fail_ambiguous_commit(self, current: JournalEntry) -> None:
        if current.phase is ImportPhase.RECOVERY_REQUIRED:
            failed = replace(
                current,
                error_category=ErrorCategory.RECOVERY_REQUIRED,
                updated_at=self._clock(),
            )
            self._journals.update(current, failed)
            raise RecoveryRequired()
        failed = replace(
            current,
            phase=ImportPhase.ROLLBACK_FAILED,
            error_category=ErrorCategory.ROLLBACK_FAILED,
            updated_at=self._clock(),
        )
        self._journals.update(current, failed)
        raise RollbackFailed()

    def _enter_recovery(self, current: JournalEntry) -> JournalEntry:
        if self._event_bus is not None:
            self._event_bus.record_recovery_triggered(
                import_id=current.import_id,
                journal_phase=current.phase.value,
                recovery_attempt_count=current.recovery_attempt_count + 1,
            )
        if current.phase is ImportPhase.RECOVERY_REQUIRED:
            return self._journals.update(
                current,
                replace(
                    current,
                    recovery_attempt_count=current.recovery_attempt_count + 1,
                    updated_at=self._clock(),
                ),
            )
        if current.phase is ImportPhase.ROLLBACK_FAILED:
            return self._journals.update(
                current,
                replace(
                    current,
                    phase=ImportPhase.ROLLING_BACK,
                    recovery_attempt_count=current.recovery_attempt_count + 1,
                    error_category=None,
                    updated_at=self._clock(),
                ),
            )
        return self._journals.update(
            current,
            replace(
                current,
                phase=ImportPhase.RECOVERY_REQUIRED,
                error_category=ErrorCategory.RECOVERY_REQUIRED,
                recovery_attempt_count=current.recovery_attempt_count + 1,
                audit_finalization_pending=bool(
                    current.committed_collection_item_ids
                ),
                updated_at=self._clock(),
            ),
        )

    def _reopen(self, journal: JournalEntry):
        if journal.snapshot_relative_path is None:
            raise RecoveryRequired()
        handle = self._snapshots.resume_snapshot(
            journal.snapshot_relative_path,
            journal.package_sha256,
            journal.snapshot_byte_length,
        )
        package = CapturePackageValidator().validate_snapshot(
            handle, journal.package_basename
        )
        mapping = dict(
            zip(
                journal.selected_source_coin_ids,
                journal.desktop_item_ids,
                strict=True,
            )
        )
        plan = self._images.plan(
            package,
            import_id=journal.import_id,
            ownership_token=journal.random_ownership_token,
            source_to_desktop=mapping,
        )
        if (
            plan.import_root_relative_path != journal.import_root_relative_path
            or plan.expected_relative_paths != journal.expected_relative_paths
        ):
            raise RecoveryRequired()
        return handle, package, plan

    def _finish_committed(self, journal, handle, package, plan) -> JournalEntry:
        if self._event_bus is not None:
            self._event_bus.record_progress(
                import_id=journal.import_id,
                stage="recovery_finish_committed",
                current=1,
                total=1,
            )
        self._images.verify(plan)
        current = journal
        if current.committed_collection_item_ids != current.desktop_item_ids:
            current = self._journals.update(
                current,
                replace(
                    current,
                    committed_collection_item_ids=current.desktop_item_ids,
                    imported_count=len(current.desktop_item_ids),
                    audit_finalization_pending=True,
                    updated_at=self._clock(),
                ),
            )
        if current.phase is not ImportPhase.COLLECTION_COMMITTED:
            current = self._journals.update(
                current,
                replace(
                    current,
                    phase=ImportPhase.COLLECTION_COMMITTED,
                    error_category=None,
                    audit_finalization_pending=True,
                    updated_at=self._clock(),
                ),
            )
        audit = self._audit(current, package, plan, ImportPhase.SUCCEEDED, None)
        try:
            handle.cleanup()
        except Exception as error:
            if handle.is_active:
                handle.preserve_for_recovery()
            raise RecoveryRequired(error) from error
        result = self._journals.update(
            current,
            replace(
                current,
                phase=ImportPhase.SUCCEEDED,
                snapshot_relative_path=None,
                error_category=None,
                audit_finalization_pending=False,
                cleanup_pending=False,
                terminal_audit=audit,
                updated_at=self._clock(),
            ),
        )
        if self._event_bus is not None:
            self._event_bus.record_recovery_complete(
                import_id=result.import_id,
                final_phase="SUCCEEDED",
            )
        return result
    def _finish_rollback(
        self,
        journal,
        handle,
        package,
        plan,
        import_lock: PackageImportLock,
    ) -> JournalEntry:
        current = journal
        if current.phase is not ImportPhase.ROLLING_BACK:
            current = self._journals.update(
                current,
                replace(
                    current,
                    phase=ImportPhase.ROLLING_BACK,
                    error_category=None,
                    updated_at=self._clock(),
                ),
            )
        self._images.cleanup(plan, import_lock=import_lock)
        audit = self._audit(
            current,
            package,
            plan,
            ImportPhase.ROLLED_BACK,
            ErrorCategory.ROLLED_BACK,
        )
        try:
            handle.cleanup()
        except Exception as error:
            if handle.is_active:
                handle.preserve_for_recovery()
            raise RecoveryRequired(error) from error
        result = self._journals.update(
            current,
            replace(
                current,
                phase=ImportPhase.ROLLED_BACK,
                snapshot_relative_path=None,
                created_relative_paths=(),
                committed_collection_item_ids=(),
                imported_count=0,
                error_category=ErrorCategory.ROLLED_BACK,
                audit_finalization_pending=False,
                terminal_audit=audit,
                updated_at=self._clock(),
            ),
        )
        if self._event_bus is not None:
            self._event_bus.record_recovery_complete(
                import_id=result.import_id,
                final_phase="ROLLED_BACK",
            )
        return result

    def _collection_items(self) -> dict[str, CoinItem]:
        if not self._collection_path.exists():
            return {}
        try:
            with self._collection_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, list):
                raise ValueError
            items = [CoinItem.from_dict(value) for value in payload]
            identifiers = [item.id for item in items]
            if any(not value for value in identifiers) or len(set(identifiers)) != len(identifiers):
                raise ValueError
            return {item.id: item for item in items}
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise RecoveryRequired(error) from error

    @staticmethod
    def _reserved_records_match(
        journal: JournalEntry,
        package: ValidatedCapturePackage,
        plan,
        collection_items: dict[str, CoinItem],
    ) -> bool:
        coins = {coin.id: coin for coin in package.manifest.coins}
        photos_by_source: dict[str, list[ItemPhoto]] = {
            source_id: [] for source_id, _ in plan.source_to_desktop
        }
        photo_roles = {
            "front": PhotoRole.FRONT,
            "reverse": PhotoRole.BACK,
            "edge": PhotoRole.EDGE,
        }
        for image in plan.media:
            photos = photos_by_source[image.source_coin_id]
            photos.append(
                ItemPhoto(
                    path=image.collection_path,
                    role=photo_roles[image.role.value],
                    is_primary=image.role.value == "front",
                    display_order=len(photos),
                )
            )
        for source_id, desktop_id in plan.source_to_desktop:
            actual = collection_items.get(desktop_id)
            coin = coins.get(source_id)
            if actual is None or coin is None:
                return False
            photos = photos_by_source[source_id]
            expected = CoinItem(
                id=desktop_id,
                image_path=photos[0].path,
                country=coin.country,
                denomination=coin.denomination,
                year=coin.year,
                grade="",
                notes=coin.notes,
                date_added=journal.created_at[:10],
                quantity=coin.quantity,
                photos=photos,
                acquisition_date=coin.purchase_date,
                purchase_price=coin.purchase_price,
                purchase_currency=coin.purchase_currency,
                purchase_source=coin.seller,
            )
            if actual.to_dict() != expected.to_dict():
                return False
        return True

    def _audit(
        self,
        journal: JournalEntry,
        package: ValidatedCapturePackage,
        plan,
        phase: ImportPhase,
        error_category: ErrorCategory | None,
    ) -> AuditSession:
        selected = set(journal.selected_source_coin_ids)
        desktop_by_source = dict(plan.source_to_desktop)
        media_by_coin: dict[str, list] = {}
        paths_by_coin: dict[str, list] = {}
        for media in package.media:
            media_by_coin.setdefault(media.coin_id, []).append(media)
        for image in plan.media:
            paths_by_coin.setdefault(image.source_coin_id, []).append(image)
        provenance: list[AuditCoin] = []
        for coin in sorted(package.manifest.coins, key=lambda value: value.position):
            decision = (
                DuplicateDecision.IMPORT_AS_NEW
                if coin.id in selected
                else DuplicateDecision.SKIP
            )
            committed_id = (
                desktop_by_source.get(coin.id)
                if phase is ImportPhase.SUCCEEDED and coin.id in selected
                else None
            )
            provenance.append(
                AuditCoin(
                    source_coin_id=coin.id,
                    desktop_item_id=committed_id,
                    decision=decision,
                    source_position=coin.position,
                    mint=coin.mint,
                    composition=coin.composition,
                    is_bullion=coin.is_bullion,
                    actual_silver_weight_oz=(
                        None
                        if coin.asw_troy_ounces is None
                        else format(coin.asw_troy_ounces, "f")
                    ),
                    source_created_at=coin.created_at,
                    source_updated_at=coin.updated_at,
                    source_quantity=coin.quantity,
                    image_role_hashes=tuple(
                        sorted(
                            ((value.role, value.sha256) for value in media_by_coin[coin.id]),
                            key=lambda value: value[0].value,
                        )
                    ),
                    managed_image_paths=(
                        tuple(
                            sorted(
                                (
                                    (value.role, value.managed_relative_path)
                                    for value in paths_by_coin.get(coin.id, ())
                                ),
                                key=lambda value: value[0].value,
                            )
                        )
                        if committed_id is not None
                        else ()
                    ),
                )
            )
        imported = len(selected) if phase is ImportPhase.SUCCEEDED else 0
        audit = AuditSession(
            audit_schema_version=AUDIT_SCHEMA_VERSION,
            import_id=journal.import_id,
            started_at=journal.created_at,
            completed_at=self._clock(),
            package_filename_basename=package.package_basename,
            package_sha256=package.package_sha256,
            schema=package.manifest.schema,
            package_version=package.manifest.package_version,
            created_by=package.manifest.created_by,
            created_with=package.manifest.created_with,
            exported_at=package.manifest.exported_at,
            session_id=package.manifest.session.id,
            session_name=package.manifest.session.name,
            session_description=package.manifest.session.description,
            session_date=package.manifest.session.session_date,
            session_created_at=package.manifest.session.created_at,
            session_updated_at=package.manifest.session.updated_at,
            coin_provenance=tuple(provenance),
            proposed_count=len(provenance),
            imported_count=imported,
            skipped_count=len(provenance) - len(selected),
            phase=phase,
            final_status=ImportResult(phase.value),
            error_category=error_category,
        )
        audit.validate()
        return audit


LockedRecovery = Callable[
    [OperationalJournalGeneration, PackageImportLock],
    object,
]


class UnifiedPackageImportRecoveryService:
    """Build one versioned recovery/orphan view under one global lock."""

    def __init__(
        self,
        *,
        lock_path: str | Path,
        journals: VersionedPackageImportJournalRepository,
        schema1_terminal: TerminalPersistenceService,
        schema2_snapshots: CapturePackageSnapshotService,
        schema3_snapshots: ProcessedArtifactSnapshotService,
        schema3_terminal: Schema3TerminalPersistenceService,
        recover_schema2_locked: LockedRecovery,
        schema3_runtime: Schema3PackageImportRecoveryService,
    ) -> None:
        self._lock_path = Path(lock_path)
        self._journals = journals
        self._schema1_terminal = schema1_terminal
        self._schema2_snapshots = schema2_snapshots
        self._schema3_snapshots = schema3_snapshots
        self._schema3_terminal = schema3_terminal
        self._recover_schema2_locked = recover_schema2_locked
        self._schema3_runtime = schema3_runtime

    def reconcile_pending_imports(self) -> tuple[object, ...]:
        results: list[object] = []
        with PackageImportLock.acquire(self._lock_path) as import_lock:
            require_verified_import_lock(import_lock)
            schema1_final = self._schema1_terminal.list_final()
            schema3_final = self._schema3_terminal.list_final()
            schema1_ids = {record.import_id for record in schema1_final}
            schema3_ids = {record.import_id for record in schema3_final}
            if schema1_ids.intersection(schema3_ids):
                raise RecoveryRequired()
            schema1_pending = set(self._schema1_terminal.pending_import_ids())
            schema3_pending = set(self._schema3_terminal.pending_import_ids())
            if (
                schema1_pending.intersection(schema3_pending)
                or schema1_pending.intersection(schema3_ids)
                or schema3_pending.intersection(schema1_ids)
            ):
                raise RecoveryRequired()
            for import_id in sorted(schema1_pending):
                results.append(
                    self._schema1_terminal.resume_pending(
                        import_id,
                        import_lock=import_lock,
                    )
                )
            heads = self._journals.list_heads(import_lock=import_lock)
            head_ids = [head.import_id for head in heads]
            if (
                len(set(head_ids)) != len(head_ids)
                or set(head_ids).intersection(schema1_ids | schema3_ids)
            ):
                raise RecoveryRequired()
            by_id = {head.import_id: head for head in heads}
            for import_id in schema3_pending:
                head = by_id.get(import_id)
                if not isinstance(head, OperationalJournalGenerationV3):
                    raise RecoveryRequired()
                pending = self._schema3_terminal.load_pending(import_id)
                expected = TerminalProcessedMediaProof.from_commitment(
                    head.processed_media_commitment,
                    outcome=(
                        "RETAINED"
                        if pending.result is ImportResult.SUCCEEDED
                        else "REMOVED"
                    ),
                )
                if pending.processed_media_proof != expected:
                    raise RecoveryRequired()
            for import_id in sorted(schema3_pending):
                results.append(
                    self._schema3_terminal.resume_pending(
                        import_id,
                        import_lock=import_lock,
                    )
                )
            heads = tuple(
                head
                for head in heads
                if head.import_id not in schema3_pending
            )
            raw_references = tuple(
                (
                    head.package_snapshot_relative_path
                    if isinstance(head, OperationalJournalGenerationV3)
                    else head.snapshot_relative_path
                )
                for head in heads
                if (
                    head.package_snapshot_relative_path
                    if isinstance(head, OperationalJournalGenerationV3)
                    else head.snapshot_relative_path
                )
                is not None
            )
            processed_references = tuple(
                head.processed_snapshot_reference.processed_snapshot_id
                for head in heads
                if isinstance(head, OperationalJournalGenerationV3)
                and head.processed_snapshot_reference is not None
            )
            for head in heads:
                if (
                    not isinstance(head, OperationalJournalGenerationV3)
                    or head.processed_snapshot_reference is None
                ):
                    continue
                if head.cleanup_operations:
                    # Once durable deletion authority exists, the full sealed
                    # inventory is intentionally no longer reopenable.  The
                    # Schema 3 cleanup-prefix verifier owns all later reads.
                    continue
                handle = self._schema3_snapshots.open_snapshot(
                    head.processed_snapshot_reference.processed_snapshot_id,
                    import_lock=import_lock,
                )
                try:
                    if (
                        handle.journal_reference()
                        != head.processed_snapshot_reference
                        or handle.media_commitment(
                            head.selected_source_coin_ids
                        )
                        != head.processed_media_commitment
                    ):
                        raise RecoveryRequired()
                finally:
                    handle.close()
            self._schema2_snapshots.cleanup_orphaned_snapshots(
                raw_references,
                import_lock=import_lock,
            )
            self._schema3_snapshots.cleanup_orphaned_snapshots(
                processed_references,
                import_lock=import_lock,
            )
            for head in heads:
                require_verified_import_lock(
                    import_lock, import_id=head.import_id
                )
                if isinstance(head, OperationalJournalGenerationV3):
                    results.append(
                        self._schema3_runtime.recover_locked(head, import_lock)
                    )
                else:
                    results.append(
                        self._recover_schema2_locked(head, import_lock)
                    )
        return tuple(results)
