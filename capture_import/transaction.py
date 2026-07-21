"""Atomic capture-package import transaction and compensation boundary."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Callable
from uuid import uuid4

from coin_collection import CoinCollection, CoinItem

from .audit import AuditCoin, AuditSession
from .baseline import require_collection_baseline
from .decisions import ImportDecisionModel
from .enums import (
    DuplicateDecision,
    ErrorCategory,
    ImageRole,
    ImportPhase,
    ImportResult,
)
from .errors import (
    CaptureImportError,
    PackageChanged,
    CollectionCommitFailed,
    JournalCorrupt,
    RecoveryRequired,
    RollbackFailed,
)
from .image_store import ManagedCollectionImageStore, ManagedImagePlan
from .journal import JournalEntry
from .journal_repository import PackageImportJournalRepository
from .limits import AUDIT_SCHEMA_VERSION, JOURNAL_SCHEMA_VERSION
from .lock import PackageImportLock
from .package import CapturePackageValidator, ValidatedCapturePackage
from .preview import PackageImportPreview, PreviewDecisionSet, ProposedCoin
from .snapshot import SnapshotHandle

Clock = Callable[[], str]
IdentifierFactory = Callable[[], str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _uuid() -> str:
    return str(uuid4())


@dataclass(frozen=True, slots=True)
class PackageImportExecutionResult:
    import_id: str | None
    status: ImportResult
    proposed_count: int
    imported_count: int
    skipped_count: int
    image_count: int
    desktop_item_ids: tuple[str, ...]


class PackageImportTransactionService:
    """Execute one confirmed batch while holding the shared collection lock."""

    def __init__(
        self,
        collection: CoinCollection,
        *,
        lock_path: str | os.PathLike[str],
        journal_repository: PackageImportJournalRepository,
        image_store: ManagedCollectionImageStore,
        clock: Clock = _utc_now,
        identifier_factory: IdentifierFactory = _uuid,
        ownership_token_factory: IdentifierFactory = _uuid,
    ) -> None:
        self._collection = collection
        self._lock_path = Path(lock_path)
        self._journals = journal_repository
        self._images = image_store
        self._clock = clock
        self._identifier_factory = identifier_factory
        self._ownership_token_factory = ownership_token_factory

    def execute(
        self,
        snapshot: SnapshotHandle,
        package: ValidatedCapturePackage,
        preview: PackageImportPreview,
        decisions: PreviewDecisionSet,
    ) -> PackageImportExecutionResult:
        """Commit the exact approved preview or compensate before returning."""

        ImportDecisionModel.validate(preview, decisions)
        if (
            package.package_sha256 != preview.package_sha256
            or package.package_byte_length != preview.package_byte_length
            or package.package_basename != preview.package_basename
        ):
            raise ValueError("package does not match preview identity.")
        revalidated = CapturePackageValidator().validate_snapshot(
            snapshot, package.package_basename
        )
        if revalidated != package:
            raise RecoveryRequired()
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

        import_id = self._identifier_factory()
        desktop_ids = tuple(self._identifier_factory() for _ in selected_ids)
        if len(set(desktop_ids)) != len(desktop_ids):
            raise CollectionCommitFailed()
        ownership_token = self._ownership_token_factory()
        source_to_desktop = dict(zip(selected_ids, desktop_ids, strict=True))
        plan = self._images.plan(
            package,
            import_id=import_id,
            ownership_token=ownership_token,
            source_to_desktop=source_to_desktop,
        )
        started_at = self._clock()
        journal: JournalEntry | None = None
        committed = False

        with PackageImportLock.acquire(
            self._lock_path, import_id=import_id
        ) as import_lock:
            try:
                locked_package = CapturePackageValidator().validate_snapshot(
                    snapshot, package.package_basename
                )
                if locked_package != package:
                    raise PackageChanged()
                require_collection_baseline(
                    self._collection.storage_path, preview.collection_baseline
                )
                existing = self._load_collection_strict()
                existing_ids = {item.id for item in existing}
                if existing_ids.intersection(desktop_ids):
                    raise CollectionCommitFailed()
                journal = self._journals.create(
                    self._new_journal(
                        snapshot,
                        package,
                        preview,
                        plan,
                        selected_ids,
                        desktop_ids,
                        started_at,
                    )
                )
                journal = self._transition(journal, ImportPhase.COPYING_IMAGES)

                def record_created(relative_path: str) -> None:
                    nonlocal journal
                    assert journal is not None
                    created = tuple(
                        sorted(set(journal.created_relative_paths) | {relative_path})
                    )
                    journal = self._journals.update(
                        journal,
                        replace(
                            journal,
                            created_relative_paths=created,
                            updated_at=self._clock(),
                        ),
                    )

                photos = self._images.copy(
                    snapshot,
                    package,
                    plan,
                    record_created,
                    import_lock=import_lock,
                )
                journal = self._transition(journal, ImportPhase.FILES_READY)
                new_items = self._build_items(
                    preview,
                    selected_ids,
                    source_to_desktop,
                    photos,
                    started_at,
                )
                prospective = existing + list(new_items)
                journal = self._transition(
                    journal, ImportPhase.COMMITTING_COLLECTION
                )
                require_collection_baseline(
                    self._collection.storage_path, preview.collection_baseline
                )
                if not self._collection.replace_items_for_import(
                    prospective,
                    expected_baseline=preview.collection_baseline,
                    import_lock=import_lock,
                ):
                    raise CollectionCommitFailed(self._collection.last_save_error)
                committed = True
                journal = self._journals.update(
                    journal,
                    replace(
                        journal,
                        committed_collection_item_ids=desktop_ids,
                        imported_count=len(desktop_ids),
                        updated_at=self._clock(),
                    ),
                )
                journal = self._journals.update(
                    journal,
                    replace(
                        journal,
                        phase=ImportPhase.COLLECTION_COMMITTED,
                        audit_finalization_pending=True,
                        updated_at=self._clock(),
                    ),
                )
                audit = self._audit(
                    package,
                    decisions,
                    source_to_desktop,
                    plan,
                    started_at,
                    ImportPhase.SUCCEEDED,
                    None,
                )
                try:
                    snapshot.cleanup()
                except Exception as error:
                    if snapshot.is_active:
                        snapshot.preserve_for_recovery()
                    raise RecoveryRequired(error) from error
                journal = self._journals.update(
                    journal,
                    replace(
                        journal,
                        phase=ImportPhase.SUCCEEDED,
                        snapshot_relative_path=None,
                        audit_finalization_pending=False,
                        cleanup_pending=False,
                        terminal_audit=audit,
                        updated_at=self._clock(),
                    ),
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
                if committed:
                    if isinstance(error, CaptureImportError):
                        raise
                    raise RecoveryRequired(error) from error
                if journal is not None and journal.phase is ImportPhase.COMMITTING_COLLECTION:
                    present = self._reserved_ids_present(desktop_ids)
                    if present:
                        if present == set(desktop_ids):
                            recovery = replace(
                                journal,
                                phase=ImportPhase.RECOVERY_REQUIRED,
                                committed_collection_item_ids=desktop_ids,
                                imported_count=len(desktop_ids),
                                audit_finalization_pending=True,
                                error_category=ErrorCategory.RECOVERY_REQUIRED,
                                updated_at=self._clock(),
                            )
                            self._journals.update(journal, recovery)
                            raise RecoveryRequired(error) from error
                        failed = replace(
                            journal,
                            phase=ImportPhase.ROLLBACK_FAILED,
                            error_category=ErrorCategory.ROLLBACK_FAILED,
                            updated_at=self._clock(),
                        )
                        self._journals.update(journal, failed)
                        raise RollbackFailed(error) from error
                self._rollback(
                    journal,
                    snapshot,
                    package,
                    preview,
                    decisions,
                    source_to_desktop,
                    plan,
                    started_at,
                    error,
                    import_lock,
                )
                raise

    def _reserved_ids_present(self, desktop_ids: tuple[str, ...]) -> set[str]:
        try:
            current = {item.id for item in self._load_collection_strict()}
        except CollectionCommitFailed as error:
            raise RecoveryRequired(error) from error
        return current.intersection(desktop_ids)

    def _new_journal(
        self,
        snapshot: SnapshotHandle,
        package: ValidatedCapturePackage,
        preview: PackageImportPreview,
        plan: ManagedImagePlan,
        selected_ids: tuple[str, ...],
        desktop_ids: tuple[str, ...],
        timestamp: str,
    ) -> JournalEntry:
        entry = JournalEntry(
            journal_schema_version=JOURNAL_SCHEMA_VERSION,
            import_id=plan.import_id,
            random_ownership_token=plan.ownership_token,
            phase=ImportPhase.PREPARED,
            created_at=timestamp,
            updated_at=timestamp,
            package_sha256=package.package_sha256,
            package_version=package.manifest.package_version,
            package_basename=package.package_basename,
            snapshot_relative_path=snapshot.descriptor.relative_path,
            snapshot_byte_length=snapshot.descriptor.byte_length,
            collection_baseline_sha256_or_sentinel=preview.collection_baseline.sha256_or_sentinel,
            collection_baseline_byte_length=preview.collection_baseline.byte_length,
            selected_source_coin_ids=selected_ids,
            desktop_item_ids=desktop_ids,
            import_root_relative_path=plan.import_root_relative_path,
            created_relative_paths=(),
            expected_relative_paths=plan.expected_relative_paths,
            committed_collection_item_ids=(),
            proposed_count=len(preview.proposals),
            imported_count=0,
            skipped_count=len(preview.proposals) - len(selected_ids),
            error_category=None,
            recovery_attempt_count=0,
            cleanup_pending=False,
            audit_finalization_pending=False,
            terminal_audit=None,
        )
        entry.validate()
        return entry

    def _transition(self, journal: JournalEntry, phase: ImportPhase) -> JournalEntry:
        return self._journals.update(
            journal, replace(journal, phase=phase, updated_at=self._clock())
        )

    def _load_collection_strict(self) -> list[CoinItem]:
        path = Path(self._collection.storage_path)
        if not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, list):
                raise ValueError("collection root must be an array")
            items = [CoinItem.from_dict(value) for value in payload]
            identifiers = [item.id for item in items]
            if any(not value for value in identifiers) or len(set(identifiers)) != len(identifiers):
                raise ValueError("collection IDs are invalid")
            return items
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise CollectionCommitFailed(error) from error

    def _build_items(
        self,
        preview: PackageImportPreview,
        selected_ids: tuple[str, ...],
        source_to_desktop: dict[str, str],
        photos: dict[str, tuple],
        canonical_timestamp: str,
    ) -> tuple[CoinItem, ...]:
        proposals = {value.source_coin_id: value for value in preview.proposals}
        result: list[CoinItem] = []
        date_added = canonical_timestamp[:10]
        for source_id in selected_ids:
            proposal: ProposedCoin = proposals[source_id]
            item_photos = list(photos[source_id])
            result.append(
                CoinItem(
                    id=source_to_desktop[source_id],
                    image_path=item_photos[0].path,
                    country=proposal.country,
                    denomination=proposal.denomination,
                    year=proposal.year,
                    grade="",
                    notes=proposal.notes,
                    date_added=date_added,
                    quantity=proposal.quantity,
                    photos=item_photos,
                    acquisition_date=proposal.acquisition_date,
                    purchase_price=proposal.purchase_price,
                    purchase_currency=proposal.purchase_currency,
                    purchase_source=proposal.purchase_source,
                )
            )
        return tuple(result)

    def _audit(
        self,
        package: ValidatedCapturePackage,
        decisions: PreviewDecisionSet,
        source_to_desktop: dict[str, str],
        plan: ManagedImagePlan,
        started_at: str,
        phase: ImportPhase,
        error_category: ErrorCategory | None,
    ) -> AuditSession:
        coin_by_id = {coin.id: coin for coin in package.manifest.coins}
        media_by_coin: dict[str, list] = {}
        paths_by_coin: dict[str, list] = {}
        for media in package.media:
            media_by_coin.setdefault(media.coin_id, []).append(media)
        for image in plan.media:
            paths_by_coin.setdefault(image.source_coin_id, []).append(image)
        provenance: list[AuditCoin] = []
        for decision in decisions:
            coin = coin_by_id[decision.source_coin_id]
            committed_id = (
                source_to_desktop.get(coin.id)
                if phase is ImportPhase.SUCCEEDED
                else None
            )
            provenance.append(
                AuditCoin(
                    source_coin_id=coin.id,
                    desktop_item_id=committed_id,
                    decision=decision.decision,
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
        imported = len(source_to_desktop) if phase is ImportPhase.SUCCEEDED else 0
        result = AuditSession(
            audit_schema_version=AUDIT_SCHEMA_VERSION,
            import_id=plan.import_id,
            started_at=started_at,
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
            skipped_count=sum(
                decision.decision is DuplicateDecision.SKIP for decision in decisions
            ),
            phase=phase,
            final_status=ImportResult(phase.value),
            error_category=error_category,
        )
        result.validate()
        return result

    def _rollback(
        self,
        journal: JournalEntry | None,
        snapshot: SnapshotHandle,
        package: ValidatedCapturePackage,
        preview: PackageImportPreview,
        decisions: PreviewDecisionSet,
        source_to_desktop: dict[str, str],
        plan: ManagedImagePlan,
        started_at: str,
        error: Exception,
        import_lock: PackageImportLock,
    ) -> None:
        rollback_error: Exception | None = None
        if journal is not None:
            try:
                journal = self._journals.update(
                    journal,
                    replace(
                        journal,
                        phase=ImportPhase.ROLLING_BACK,
                        updated_at=self._clock(),
                    ),
                )
            except Exception as transition_error:
                rollback_error = transition_error
        try:
            self._images.cleanup(
                plan,
                import_lock=import_lock,
                ownership_recorded=bool(
                    journal is not None and journal.created_relative_paths
                ),
            )
        except Exception as cleanup_error:
            rollback_error = cleanup_error
        audit = None
        category = None
        if journal is not None and rollback_error is None:
            category = (
                error.category
                if isinstance(error, CaptureImportError)
                else ErrorCategory.COLLECTION_COMMIT_FAILED
            )
            try:
                audit = self._audit(
                    package,
                    decisions,
                    source_to_desktop,
                    plan,
                    started_at,
                    ImportPhase.ROLLED_BACK,
                    category,
                )
            except Exception as journal_error:
                rollback_error = journal_error
        if rollback_error is None:
            try:
                snapshot.cleanup()
            except Exception as cleanup_error:
                if snapshot.is_active:
                    snapshot.preserve_for_recovery()
                rollback_error = cleanup_error
        elif snapshot.is_active:
            snapshot.preserve_for_recovery()
        if journal is not None and rollback_error is None:
            try:
                journal = self._journals.update(
                    journal,
                    replace(
                        journal,
                        phase=ImportPhase.ROLLED_BACK,
                        snapshot_relative_path=None,
                        created_relative_paths=(),
                        terminal_audit=audit,
                        error_category=category,
                        updated_at=self._clock(),
                    ),
                )
            except Exception as journal_error:
                rollback_error = journal_error
        if rollback_error is not None:
            if journal is not None and journal.phase is not ImportPhase.ROLLED_BACK:
                try:
                    self._journals.update(
                        journal,
                        replace(
                            journal,
                            phase=ImportPhase.ROLLBACK_FAILED,
                            error_category=ErrorCategory.ROLLBACK_FAILED,
                            updated_at=self._clock(),
                        ),
                    )
                except Exception:
                    pass
            raise RollbackFailed(rollback_error) from error
