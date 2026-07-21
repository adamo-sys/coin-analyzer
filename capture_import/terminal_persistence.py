"""Sanitized terminal compaction and ordered operational-chain retirement.

Durable Persistence §§644–904; RM-21–RM-28.
"""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import uuid4

from ._filesystem import (
    delete_open_file,
    handle_matches_path,
    handle_object_identity,
    open_existing_binary_for_delete,
    open_exclusive_binary,
    open_plain_directory_handle,
    path_object_identity,
    publish_open_file_no_replace_in_directory,
    rename_entry_no_replace_in_directory,
    sync_directory,
)
from ._json import canonical_json_bytes, parse_bounded_json_object
from .durable_models import (
    CompactionCommitPlan,
    ManifestObjectEntry,
    NativeObjectIdentity,
    OperationalChainProof,
    OperationalJournalGeneration,
    RetirementManifest,
    TerminalCleanupSummary,
    TerminalCollectionProof,
    TerminalCompaction,
    TerminalHistoryRecord,
    TerminalManagedImageProof,
)
from .durable_repository import Schema2PackageImportJournalRepository
from .enums import ImportPhase, ImportResult, TerminalCompactionStatus
from .errors import JournalCorrupt, RecoveryRequired
from .limits import MAX_JSON_BYTES
from .lock import PackageImportLock, require_verified_import_lock

Clock = Callable[[], str]
TokenFactory = Callable[[], str]


def _identity(value: tuple[int, int]) -> NativeObjectIdentity:
    return NativeObjectIdentity.from_native(value, windows=os.name == "nt")


def _identity_hash(value: NativeObjectIdentity) -> str:
    return sha256(canonical_json_bytes(value.to_dict())).hexdigest()


class TerminalPersistenceService:
    """Compact one eligible active chain into privacy-complete history."""

    def __init__(
        self,
        journals: Schema2PackageImportJournalRepository,
        history_root: str | os.PathLike[str],
        *,
        clock: Clock,
        token_factory: TokenFactory = lambda: str(uuid4()),
    ) -> None:
        self._journals = journals
        self._history = Path(history_root).absolute()
        self._clock = clock
        self._token_factory = token_factory

    def compact(
        self,
        head: OperationalJournalGeneration,
        *,
        result: ImportResult,
        import_lock: PackageImportLock,
        error_category: str | None = None,
    ) -> TerminalHistoryRecord:
        """Publish G/H, pending history, retire the chain, and finalize history."""

        require_verified_import_lock(import_lock, import_id=head.import_id)
        head.validate()
        if result not in {ImportResult.SUCCEEDED, ImportResult.ROLLED_BACK, ImportResult.CANCELLED}:
            raise ValueError("Compaction requires a terminal audit outcome.")
        if head.phase not in {
            ImportPhase.COLLECTION_COMMITTED,
            ImportPhase.ROLLING_BACK,
        } or head.snapshot_relative_path is not None:
            raise RecoveryRequired()
        if result is ImportResult.SUCCEEDED:
            if (
                head.phase is not ImportPhase.COLLECTION_COMMITTED
                or head.collection_temporary_artifact is None
                or head.collection_temporary_artifact.state.value != "PUBLISHED"
                or (
                    head.collection_backup_artifact is not None
                    and head.collection_backup_artifact.state.value != "CLEANED"
                )
            ):
                raise RecoveryRequired()
        elif head.phase is not ImportPhase.ROLLING_BACK:
            raise RecoveryRequired()
        if not head.cleanup_operations or any(operation.status.value != "COMPLETE" for operation in head.cleanup_operations):
            raise RecoveryRequired()
        if head.pending_terminal_audit is None:
            raise RecoveryRequired()
        os.makedirs(self._history, exist_ok=True)
        with open_plain_directory_handle(self._journals.root) as journal_parent, open_plain_directory_handle(self._history) as history_parent, open_plain_directory_handle(self._journals.root / head.import_id) as import_directory:
            owner_raw = (import_directory.path / "owner.json").read_bytes()
            completed_at = self._clock()
            g_transition = self._token_factory()
            h_transition = self._token_factory()
            h_token = self._token_factory()
            terminal_token = self._token_factory()
            retirement_token = self._token_factory()
            g_number = head.generation + 1
            h_number = g_number + 1
            if h_number > 4095:
                raise RecoveryRequired()
            planning = TerminalCompaction(
                schema_version="1.0", status=TerminalCompactionStatus.PLANNING_MANIFEST,
                final_phase=result, result=result, completed_at=completed_at,
                terminal_pending_name=f".pending-{head.import_id}.json",
                terminal_temporary_name=f".pending-{head.import_id}-{terminal_token}.tmp",
                terminal_token=terminal_token,
                retirement_directory_name=f".retire-{head.import_id}",
                retirement_manifest_name="retirement-manifest.json",
                retirement_manifest_temporary_name=f".retirement-manifest-{retirement_token}.tmp",
                retirement_token=retirement_token,
                manifest_generation_first=0, manifest_generation_last=g_number,
                manifest_generation_count=g_number + 1,
                compaction_commit_generation=h_number,
                compaction_commit_transition_id=h_transition,
                compaction_commit_filename=self._journals.generation_name(h_number, h_transition),
                owner_record_sha256=sha256(owner_raw).hexdigest(),
                history_parent_identity=_identity(history_parent.identity),
                journal_parent_identity=_identity(journal_parent.identity),
                operational_directory_identity=_identity(import_directory.identity),
            )
            g = replace(
                head, generation=g_number,
                previous_generation_sha256=sha256(canonical_json_bytes(head.to_dict())).hexdigest(),
                transition_id=g_transition, next_generation_token=h_token,
                phase=ImportPhase.COMPACTING, resume_phase=None,
                updated_at=completed_at, snapshot_relative_path=None,
                collection_temporary_artifact=None, collection_backup_artifact=None,
                compaction=planning, error_category=None,
            )
            g = self._journals.append(head, g, import_lock=import_lock)
            manifest = self._build_manifest(
                g,
                planning,
                import_directory,
                import_lock=import_lock,
            )
            manifest_payload = canonical_json_bytes(manifest.to_dict())
            manifest_identity = self._write_manifest(
                import_directory,
                planning,
                manifest_payload,
                import_lock=import_lock,
            )
            outcome_payload = self._outcome_payload(g, result, error_category)
            outcome_hash = sha256(canonical_json_bytes(outcome_payload)).hexdigest()
            ready = replace(
                planning, status=TerminalCompactionStatus.READY_FOR_TERMINAL,
                manifest_byte_length=len(manifest_payload), manifest_sha256=sha256(manifest_payload).hexdigest(),
                manifest_object_identity=manifest_identity, outcome_payload_sha256=outcome_hash,
            )
            h = replace(
                g, generation=h_number,
                previous_generation_sha256=sha256(canonical_json_bytes(g.to_dict())).hexdigest(),
                transition_id=h_transition, next_generation_token=None,
                compaction=ready,
            )
            h = self._journals.append(g, h, import_lock=import_lock)
            record = self._publish_pending(
                h,
                manifest,
                manifest_payload,
                outcome_payload,
                history_parent,
                import_lock=import_lock,
            )
            self._retire(
                record,
                manifest,
                history_parent,
                journal_parent,
                import_lock=import_lock,
            )
            return record

    def list_final(self) -> tuple[TerminalHistoryRecord, ...]:
        """Return privacy-complete final history in deterministic import-ID order."""

        if not self._history.exists():
            return ()
        records: list[TerminalHistoryRecord] = []
        for path in sorted(self._history.iterdir(), key=lambda value: value.name):
            if path.name.startswith(".pending-") or path.name.endswith(".tmp"):
                continue
            if path.suffix != ".json":
                raise RecoveryRequired()
            records.append(self._read_terminal_record(path))
        return tuple(records)

    def pending_import_ids(self) -> tuple[str, ...]:
        """Enumerate deterministic pending authorities for startup recovery."""

        if not self._history.exists():
            return ()
        result: list[str] = []
        for path in sorted(self._history.iterdir(), key=lambda value: value.name):
            if not path.name.startswith(".pending-") or path.suffix != ".json":
                continue
            record = self._read_terminal_record(path)
            if path.name != f".pending-{record.import_id}.json":
                raise RecoveryRequired()
            result.append(record.import_id)
        return tuple(result)

    def resume_pending(
        self,
        import_id: str,
        *,
        import_lock: PackageImportLock,
    ) -> TerminalHistoryRecord:
        """Resume manifest-governed retirement from an exact pending authority.

        Durable Persistence "Replay authority"; RM-23 through RM-26.
        """

        require_verified_import_lock(import_lock, import_id=import_id)
        pending_path = self._history / f".pending-{import_id}.json"
        record = self._read_terminal_record(pending_path)
        if record.import_id != import_id:
            raise RecoveryRequired()
        active = self._journals.root / import_id
        retiring = self._journals.root / f".retire-{import_id}"
        candidates = tuple(path for path in (active, retiring) if path.exists())
        if len(candidates) != 1:
            raise RecoveryRequired()
        operational = candidates[0]
        with open_plain_directory_handle(operational) as directory:
            manifest_path = directory.path / "retirement-manifest.json"
            raw, identity = self._read_bound_file(manifest_path)
            proof = record.operational_chain_proof
            if (
                len(raw) != proof.retirement_manifest_byte_length
                or sha256(raw).hexdigest() != proof.retirement_manifest_sha256
                or _identity_hash(_identity(identity))
                != proof.retirement_manifest_identity_sha256
                or _identity_hash(_identity(directory.identity))
                != proof.operational_directory_identity_sha256
            ):
                raise RecoveryRequired()
            try:
                manifest = RetirementManifest.from_dict(
                    parse_bounded_json_object(raw, "retirement manifest")
                )
            except Exception as error:
                raise RecoveryRequired(error) from error
        with open_plain_directory_handle(
            self._history
        ) as history_parent, open_plain_directory_handle(
            self._journals.root
        ) as journal_parent:
            self._retire(
                record,
                manifest,
                history_parent,
                journal_parent,
                import_lock=import_lock,
            )
        return self._read_terminal_record(self._history / f"{import_id}.json")

    def resume_compaction(
        self,
        import_id: str,
        *,
        import_lock: PackageImportLock,
    ) -> TerminalHistoryRecord:
        """Resume G/M/H/terminal publication before manifest-governed retirement.

        Durable Persistence "Terminal compaction"; RM-21.a through RM-21.k.
        """

        require_verified_import_lock(import_lock, import_id=import_id)
        pending = self._history / f".pending-{import_id}.json"
        if pending.exists():
            return self.resume_pending(import_id, import_lock=import_lock)
        head = self._journals.load(import_id, import_lock=import_lock)
        if head.phase is not ImportPhase.COMPACTING or head.compaction is None:
            raise RecoveryRequired()
        os.makedirs(self._history, exist_ok=True)
        with open_plain_directory_handle(
            self._journals.root
        ) as journal_parent, open_plain_directory_handle(
            self._history
        ) as history_parent, open_plain_directory_handle(
            self._journals.root / import_id
        ) as import_directory:
            manifest, manifest_payload, manifest_identity = self._reconcile_manifest(
                head,
                import_directory,
                import_lock=import_lock,
            )
            if head.compaction.status is TerminalCompactionStatus.PLANNING_MANIFEST:
                outcome_payload = self._outcome_payload(
                    head, head.compaction.result, head.error_category
                )
                ready = replace(
                    head.compaction,
                    status=TerminalCompactionStatus.READY_FOR_TERMINAL,
                    manifest_byte_length=len(manifest_payload),
                    manifest_sha256=sha256(manifest_payload).hexdigest(),
                    manifest_object_identity=manifest_identity,
                    outcome_payload_sha256=sha256(
                        canonical_json_bytes(outcome_payload)
                    ).hexdigest(),
                )
                h = replace(
                    head,
                    generation=head.compaction.compaction_commit_generation,
                    previous_generation_sha256=sha256(
                        canonical_json_bytes(head.to_dict())
                    ).hexdigest(),
                    transition_id=head.compaction.compaction_commit_transition_id,
                    next_generation_token=None,
                    compaction=ready,
                )
                head = self._journals.append(head, h, import_lock=import_lock)
            outcome_payload = self._outcome_payload(
                head, head.compaction.result, head.error_category
            )
            record = self._reconcile_terminal_publication(
                head,
                manifest,
                manifest_payload,
                outcome_payload,
                history_parent,
                import_lock=import_lock,
            )
            self._retire(
                record,
                manifest,
                history_parent,
                journal_parent,
                import_lock=import_lock,
            )
            return record

    def _reconcile_manifest(
        self,
        head,
        directory,
        *,
        import_lock: PackageImportLock,
    ):
        require_verified_import_lock(import_lock, import_id=head.import_id)
        planning = head.compaction
        if planning is None:
            raise RecoveryRequired()
        manifest = self._build_manifest(
            head
            if planning.status is TerminalCompactionStatus.PLANNING_MANIFEST
            else self._journals.load_chain(
                head.import_id,
                import_lock=import_lock,
            )[-2],
            planning,
            directory,
            import_lock=import_lock,
        )
        payload = canonical_json_bytes(manifest.to_dict())
        final = directory.path / planning.retirement_manifest_name
        temporary = directory.path / planning.retirement_manifest_temporary_name
        final_exists = final.exists()
        temporary_exists = temporary.exists()
        if final_exists and temporary_exists:
            raise RecoveryRequired()
        if temporary_exists:
            try:
                raw, _candidate_identity = self._read_bound_file(temporary)
            except RecoveryRequired:
                raw = None
            if raw != payload:
                require_verified_import_lock(import_lock, import_id=head.import_id)
                handle = open_existing_binary_for_delete(temporary)
                try:
                    delete_open_file(handle, temporary)
                finally:
                    handle.close()
                sync_directory(directory)
            else:
                require_verified_import_lock(import_lock, import_id=head.import_id)
                with open_existing_binary_for_delete(temporary) as handle:
                    publish_open_file_no_replace_in_directory(
                        handle,
                        directory,
                        planning.retirement_manifest_temporary_name,
                        planning.retirement_manifest_name,
                    )
                sync_directory(directory)
        elif not final_exists:
            self._write_manifest(
                directory,
                planning,
                payload,
                import_lock=import_lock,
            )
        raw, identity = self._read_bound_file(final)
        if raw != payload:
            raise RecoveryRequired()
        native_identity = _identity(identity)
        if planning.status is TerminalCompactionStatus.READY_FOR_TERMINAL:
            if (
                len(raw) != planning.manifest_byte_length
                or sha256(raw).hexdigest() != planning.manifest_sha256
                or native_identity != planning.manifest_object_identity
            ):
                raise RecoveryRequired()
        return manifest, payload, native_identity

    def _reconcile_terminal_publication(
        self,
        h,
        manifest,
        manifest_payload,
        outcome_payload,
        history_parent,
        *,
        import_lock: PackageImportLock,
    ) -> TerminalHistoryRecord:
        require_verified_import_lock(import_lock, import_id=h.import_id)
        temporary = self._history / h.compaction.terminal_temporary_name
        pending = self._history / h.compaction.terminal_pending_name
        temporary_exists = temporary.exists()
        pending_exists = pending.exists()
        if temporary_exists and pending_exists:
            raise RecoveryRequired()
        if pending_exists:
            record = self._read_terminal_record(pending)
            self._verify_terminal_authority(record, h)
            return record
        if temporary_exists:
            try:
                record = self._read_terminal_record(temporary)
                self._verify_terminal_authority(record, h)
            except RecoveryRequired:
                require_verified_import_lock(import_lock, import_id=h.import_id)
                handle = open_existing_binary_for_delete(temporary)
                try:
                    delete_open_file(handle, temporary)
                finally:
                    handle.close()
                sync_directory(history_parent)
            else:
                require_verified_import_lock(import_lock, import_id=h.import_id)
                with open_existing_binary_for_delete(temporary) as handle:
                    publish_open_file_no_replace_in_directory(
                        handle,
                        history_parent,
                        h.compaction.terminal_temporary_name,
                        h.compaction.terminal_pending_name,
                    )
                sync_directory(history_parent)
                return record
        return self._publish_pending(
            h,
            manifest,
            manifest_payload,
            outcome_payload,
            history_parent,
            import_lock=import_lock,
        )

    @staticmethod
    def _verify_terminal_authority(
        record: TerminalHistoryRecord, h: OperationalJournalGeneration
    ) -> None:
        h_path_name = Schema2PackageImportJournalRepository.generation_name(
            h.generation, h.transition_id
        )
        if (
            record.import_id != h.import_id
            or record.outcome_payload_sha256
            != h.compaction.outcome_payload_sha256
            or record.operational_chain_proof.compaction_commit_generation
            != h.generation
            or record.operational_chain_proof.compaction_commit_transition_id
            != h.transition_id
            or h_path_name != h.compaction.compaction_commit_filename
        ):
            raise RecoveryRequired()

    def _build_manifest(
        self,
        g,
        planning,
        directory,
        *,
        import_lock: PackageImportLock,
    ) -> RetirementManifest:
        generations: list[ManifestObjectEntry] = []
        for entry in self._journals.load_chain(
            g.import_id,
            import_lock=import_lock,
        ):
            if entry.generation > g.generation:
                break
            name = self._journals.generation_name(entry.generation, entry.transition_id)
            path = directory.path / name
            raw = path.read_bytes()
            generations.append(
                ManifestObjectEntry(
                    basename=name, byte_length=len(raw), sha256=sha256(raw).hexdigest(),
                    object_identity=_identity(path_object_identity(path)),
                    generation=entry.generation, transition_id=entry.transition_id,
                )
            )
        owner_path = directory.path / "owner.json"
        owner_raw = owner_path.read_bytes()
        return RetirementManifest(
            schema_version="1.0", import_id=g.import_id,
            random_ownership_token_sha256=sha256(g.random_ownership_token.encode("ascii")).hexdigest(),
            operational_directory_identity=_identity(directory.identity),
            owner_record=ManifestObjectEntry(
                basename="owner.json", byte_length=len(owner_raw), sha256=sha256(owner_raw).hexdigest(),
                object_identity=_identity(path_object_identity(owner_path)),
            ),
            generations=tuple(generations),
            compaction_commit=CompactionCommitPlan(
                generation=planning.compaction_commit_generation,
                transition_id=planning.compaction_commit_transition_id,
                basename=planning.compaction_commit_filename,
            ),
        )

    def _write_manifest(
        self,
        directory,
        planning,
        payload: bytes,
        *,
        import_lock: PackageImportLock,
    ) -> NativeObjectIdentity:
        require_verified_import_lock(import_lock)
        temporary = planning.retirement_manifest_temporary_name
        final = planning.retirement_manifest_name
        handle = open_exclusive_binary(directory.path / temporary)
        try:
            require_verified_import_lock(import_lock)
            handle.write(payload); handle.flush(); os.fsync(handle.fileno()); handle.seek(0)
            if handle.read(len(payload) + 1) != payload or not handle_matches_path(handle, directory.path / temporary):
                raise RecoveryRequired()
            require_verified_import_lock(import_lock)
            publish_open_file_no_replace_in_directory(handle, directory, temporary, final)
            sync_directory(directory)
        finally:
            handle.close()
        return _identity(path_object_identity(directory.path / final))

    def _outcome_payload(self, head, result, error_category) -> dict[str, Any]:
        audit = self._sanitize_audit(head.pending_terminal_audit)
        ids_hash = sha256(canonical_json_bytes(list(head.committed_collection_item_ids))).hexdigest()
        if result is ImportResult.SUCCEEDED:
            collection = TerminalCollectionProof(
                "PUBLISHED", head.collection_baseline_sha256_or_sentinel,
                head.collection_baseline_byte_length, head.prospective_collection_sha256,
                head.prospective_collection_byte_length, len(head.committed_collection_item_ids), ids_hash,
            )
            image_outcome = "RETAINED"
        else:
            collection = TerminalCollectionProof(
                "UNCHANGED", head.collection_baseline_sha256_or_sentinel,
                head.collection_baseline_byte_length, head.collection_baseline_sha256_or_sentinel,
                head.collection_baseline_byte_length, 0,
                sha256(canonical_json_bytes([])).hexdigest(),
            )
            image_outcome = "REMOVED" if head.verified_image_inventory else "NONE"
        image_aggregate = sha256(canonical_json_bytes([
            [item.role, item.byte_length, item.sha256] for item in head.verified_image_inventory
        ])).hexdigest()
        cleanup = tuple(self._cleanup_summary(operation) for operation in head.cleanup_operations)
        return {
            "terminal_schema_version": "1.0", "import_id": head.import_id,
            "final_phase": result.value, "result": result.value,
            "transaction_created_at": head.created_at, "completed_at": head.compaction.completed_at,
            "package_sha256": head.package_sha256, "package_version": head.package_version,
            "package_basename": head.package_basename, "proposed_count": head.proposed_count,
            "imported_count": len(head.committed_collection_item_ids) if result is ImportResult.SUCCEEDED else 0,
            "skipped_count": head.skipped_count,
            "collection_proof": collection.to_dict(),
            "managed_image_proof": TerminalManagedImageProof(image_outcome, len(head.verified_image_inventory), image_aggregate).to_dict(),
            "cleanup_summaries": [value.to_dict() for value in cleanup],
            "audit": audit, "error_category": error_category,
        }

    @staticmethod
    def _sanitize_audit(audit: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(audit)
        result["audit_schema_version"] = "2.0"
        coins = []
        for coin in result.get("coin_provenance", []):
            cleaned = dict(coin)
            cleaned.pop("managed_image_paths", None)
            coins.append(cleaned)
        result["coin_provenance"] = coins
        return result

    @staticmethod
    def _cleanup_summary(operation) -> TerminalCleanupSummary:
        aggregate = sha256(canonical_json_bytes([
            [target.root, target.object_kind, target.expected_byte_length, target.expected_sha256, _identity_hash(receipt.removed_object_identity)]
            for target, receipt in zip(operation.targets, operation.receipts, strict=True)
        ])).hexdigest()
        return TerminalCleanupSummary(
            operation.kind, "COMPLETED", len(operation.targets), len(operation.receipts),
            operation.intent_generation, operation.completed_generation, aggregate,
        )

    def _publish_pending(
        self,
        h,
        manifest,
        manifest_payload,
        outcome_payload,
        history_parent,
        *,
        import_lock: PackageImportLock,
    ) -> TerminalHistoryRecord:
        require_verified_import_lock(import_lock, import_id=h.import_id)
        h_path = self._journals.root / h.import_id / self._journals.generation_name(h.generation, h.transition_id)
        h_raw = h_path.read_bytes()
        temp_path = self._history / h.compaction.terminal_temporary_name
        handle = open_exclusive_binary(temp_path)
        try:
            require_verified_import_lock(import_lock, import_id=h.import_id)
            terminal_identity = _identity(handle_object_identity(handle))
            proof = OperationalChainProof(
                manifest_generation_count=h.compaction.manifest_generation_count,
                manifest_head_sha256=h.previous_generation_sha256,
                compaction_commit_generation=h.generation,
                compaction_commit_transition_id=h.transition_id,
                compaction_commit_byte_length=len(h_raw),
                compaction_commit_sha256=sha256(h_raw).hexdigest(),
                compaction_commit_object_identity_sha256=_identity_hash(_identity(path_object_identity(h_path))),
                owner_record_sha256=h.compaction.owner_record_sha256,
                owner_token_sha256=sha256(h.random_ownership_token.encode("ascii")).hexdigest(),
                operational_directory_identity_sha256=_identity_hash(h.compaction.operational_directory_identity),
                terminal_object_identity_sha256=_identity_hash(terminal_identity),
                retirement_manifest_identity_sha256=_identity_hash(h.compaction.manifest_object_identity),
                retirement_manifest_byte_length=len(manifest_payload),
                retirement_manifest_sha256=sha256(manifest_payload).hexdigest(),
            )
            record = TerminalHistoryRecord(
                terminal_schema_version="1.0", import_id=h.import_id,
                final_phase=ImportResult(outcome_payload["final_phase"]), result=ImportResult(outcome_payload["result"]),
                transaction_created_at=outcome_payload["transaction_created_at"], completed_at=outcome_payload["completed_at"],
                package_sha256=h.package_sha256, package_version=h.package_version, package_basename=h.package_basename,
                proposed_count=outcome_payload["proposed_count"], imported_count=outcome_payload["imported_count"], skipped_count=outcome_payload["skipped_count"],
                collection_proof=TerminalCollectionProof(**outcome_payload["collection_proof"]),
                managed_image_proof=TerminalManagedImageProof(**outcome_payload["managed_image_proof"]),
                cleanup_summaries=tuple(TerminalCleanupSummary(**value) for value in outcome_payload["cleanup_summaries"]),
                outcome_payload_sha256=h.compaction.outcome_payload_sha256,
                operational_chain_proof=proof, audit=outcome_payload["audit"], error_category=outcome_payload["error_category"],
            )
            payload = canonical_json_bytes(record.to_dict())
            if len(payload) > MAX_JSON_BYTES:
                raise RecoveryRequired()
            handle.write(payload); handle.flush(); os.fsync(handle.fileno()); handle.seek(0)
            if (
                handle.read(len(payload) + 1) != payload
                or _identity(handle_object_identity(handle)) != terminal_identity
            ):
                raise RecoveryRequired()
            require_verified_import_lock(import_lock, import_id=h.import_id)
            publish_open_file_no_replace_in_directory(handle, history_parent, h.compaction.terminal_temporary_name, h.compaction.terminal_pending_name)
            sync_directory(history_parent)
        finally:
            handle.close()
        return record

    def _retire(
        self,
        record,
        manifest,
        history_parent,
        journal_parent,
        *,
        import_lock: PackageImportLock,
    ) -> None:
        require_verified_import_lock(import_lock, import_id=record.import_id)
        active_name = record.import_id
        retirement_name = f".retire-{record.import_id}"
        active = self._journals.root / active_name
        retirement = self._journals.root / retirement_name
        active_exists = active.exists()
        retirement_exists = retirement.exists()
        if active_exists == retirement_exists:
            raise RecoveryRequired()
        if active_exists:
            if _identity(path_object_identity(active)) != manifest.operational_directory_identity:
                raise RecoveryRequired()
            require_verified_import_lock(import_lock, import_id=record.import_id)
            rename_entry_no_replace_in_directory(
                journal_parent, active_name, retirement_name
            )
            sync_directory(journal_parent)
        if _identity(path_object_identity(retirement)) != manifest.operational_directory_identity:
            raise RecoveryRequired()
        with open_plain_directory_handle(retirement) as directory:
            deletion_order = [
                (
                    manifest.compaction_commit.basename,
                    record.operational_chain_proof.compaction_commit_sha256,
                    None,
                    record.operational_chain_proof.compaction_commit_object_identity_sha256,
                ),
                *((entry.basename, entry.sha256, entry.object_identity, None) for entry in reversed(manifest.generations)),
                ("owner.json", manifest.owner_record.sha256, manifest.owner_record.object_identity, None),
                (
                    "retirement-manifest.json",
                    record.operational_chain_proof.retirement_manifest_sha256,
                    None,
                    record.operational_chain_proof.retirement_manifest_identity_sha256,
                ),
            ]
            actual = set(
                os.listdir(directory.descriptor)
                if directory.descriptor is not None
                else os.listdir(directory.path)
            )
            if not directory.verify_path():
                raise RecoveryRequired()
            allowed_suffixes = [
                {name for name, _digest, _identity_value, _identity_digest in deletion_order[index:]}
                for index in range(len(deletion_order) + 1)
            ]
            try:
                start = allowed_suffixes.index(actual)
            except ValueError as error:
                raise RecoveryRequired(error) from error
            for name, digest, expected_identity, expected_identity_hash in deletion_order[start:]:
                require_verified_import_lock(import_lock, import_id=record.import_id)
                self._delete_verified(
                    directory,
                    name,
                    digest,
                    expected_identity=expected_identity,
                    expected_identity_hash=expected_identity_hash,
                )
            sync_directory(directory)
        require_verified_import_lock(import_lock, import_id=record.import_id)
        os.rmdir(retirement)
        sync_directory(journal_parent)
        pending = f".pending-{record.import_id}.json"
        final = f"{record.import_id}.json"
        pending_exists = (self._history / pending).exists()
        final_exists = (self._history / final).exists()
        if pending_exists == final_exists:
            raise RecoveryRequired()
        if pending_exists:
            require_verified_import_lock(import_lock, import_id=record.import_id)
            rename_entry_no_replace_in_directory(history_parent, pending, final)
            sync_directory(history_parent)
        if self._read_terminal_record(self._history / final) != record:
            raise RecoveryRequired()

    @staticmethod
    def _read_bound_file(path: Path) -> tuple[bytes, tuple[int, int]]:
        handle = open_existing_binary_for_delete(path)
        try:
            identity = handle_object_identity(handle)
            size = os.fstat(handle.fileno()).st_size
            if not 1 <= size <= MAX_JSON_BYTES:
                raise RecoveryRequired()
            raw = handle.read(MAX_JSON_BYTES + 1)
            if len(raw) != size or not handle_matches_path(handle, path):
                raise RecoveryRequired()
            return raw, identity
        finally:
            handle.close()

    def _read_terminal_record(self, path: Path) -> TerminalHistoryRecord:
        raw, identity_value = self._read_bound_file(path)
        try:
            record = TerminalHistoryRecord.from_dict(
                parse_bounded_json_object(raw, "terminal history")
            )
            if (
                _identity_hash(_identity(identity_value))
                != record.operational_chain_proof.terminal_object_identity_sha256
            ):
                raise RecoveryRequired()
            return record
        except Exception as error:
            if isinstance(error, RecoveryRequired):
                raise
            raise RecoveryRequired(error) from error

    @staticmethod
    def _delete_verified(
        directory,
        name: str,
        expected_sha256: str,
        *,
        expected_identity: NativeObjectIdentity | None = None,
        expected_identity_hash: str | None = None,
    ) -> None:
        path = directory.path / name
        handle = open_existing_binary_for_delete(path)
        deleted = False
        try:
            digest = sha256(handle.read()).hexdigest()
            if digest != expected_sha256 or not handle_matches_path(handle, path):
                raise RecoveryRequired()
            identity = handle_object_identity(handle)
            native_identity = _identity(identity)
            if expected_identity is not None and native_identity != expected_identity:
                raise RecoveryRequired()
            if (
                expected_identity_hash is not None
                and _identity_hash(native_identity) != expected_identity_hash
            ):
                raise RecoveryRequired()
            delete_open_file(handle, path)
            deleted = True
            if handle_object_identity(handle) != identity:
                raise RecoveryRequired()
        finally:
            handle.close()
        if not deleted or path.exists() or not directory.verify_path():
            raise RecoveryRequired()
        sync_directory(directory)
