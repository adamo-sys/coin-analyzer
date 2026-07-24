"""Sprint 8 Unit 7D-C cleanup, terminal, and unified recovery gates."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path
from types import SimpleNamespace
import re
import tempfile
import unittest
from unittest.mock import Mock, patch

from capture_import._filesystem import path_object_identity
from capture_import._json import canonical_json_bytes
from capture_import.cleanup_persistence import (
    DurableCleanupExecutor,
    Schema3CleanupProtocol,
)
from capture_import.durable_repository import Schema3PackageImportJournalRepository
from capture_import.durable_models import (
    CleanupOperationV3,
    CollectionPublicationArtifact,
    NativeObjectIdentity,
    OperationalJournalGenerationV3,
    OwnershipDescriptor,
    OwnershipDescriptorV3,
    TerminalHistoryRecord,
    TerminalHistoryRecordV2,
    TerminalProcessedMediaProof,
    VerifiedImageV3,
)
from capture_import.enums import (
    CleanupStatus,
    CollectionPublicationState,
    ImportPhase,
    ImportResult,
)
from capture_import.errors import RecoveryRequired
from capture_import.lock import PackageImportLock
from capture_import.recovery import UnifiedPackageImportRecoveryService
from tests.test_schema3_durable_contracts import (
    _generation,
    _identity,
    _successor,
    _uuid,
)


class _Journal:
    def __init__(self) -> None:
        self.entries = []

    def append(self, previous, current, *, import_lock):
        self.entries.append((previous, current))
        return current


class _Executor:
    def __init__(self) -> None:
        self.removed = []

    def remove(self, target, **_kwargs):
        self.removed.append(target.relative_path)
        return target.object_identity

    remove_v3 = remove

    def verify_operation(self, operation, **_kwargs):
        operation.validate()


def _target(head, name="artifact.jpg", root="PROCESSED_SNAPSHOT"):
    return OwnershipDescriptorV3(
        root=root,
        relative_path=name,
        object_kind="FILE",
        ownership_token=head.random_ownership_token,
        expected_byte_length=1,
        expected_sha256="f" * 64,
        parent_identity=_identity(),
        object_identity=_identity(),
    )


class Schema3CleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.head = replace(_generation(), phase=ImportPhase.ROLLING_BACK)
        self.journal = _Journal()
        self.executor = _Executor()
        self.protocol = Schema3CleanupProtocol(
            self.journal,
            self.executor,
            clock=lambda: "2026-07-23T12:00:01Z",
            token_factory=_uuid,
        )
        self.lock = PackageImportLock.acquire(
            Path(self.temp.name) / "global.lock",
            import_id=self.head.import_id,
        )
        self.addCleanup(self.lock.release)

    def _intent(self, count=2):
        targets = tuple(_target(self.head, f"artifact-{index}.jpg") for index in range(count))
        return self.protocol.begin_rollback(
            self.head, targets=targets, import_lock=self.lock
        )

    def _durable_cleanup(self, root_names):
        roots = {}
        targets = []
        for index, root_name in enumerate(root_names):
            root = Path(self.temp.name) / root_name.lower()
            root.mkdir()
            path = root / f"artifact-{index}.bin"
            payload = f"payload-{index}".encode()
            path.write_bytes(payload)
            roots[root_name] = root
            targets.append(
                OwnershipDescriptorV3(
                    root_name,
                    path.name,
                    "FILE",
                    self.head.random_ownership_token,
                    len(payload),
                    sha256(payload).hexdigest(),
                    NativeObjectIdentity.from_native(
                        path_object_identity(root), windows=os.name == "nt"
                    ),
                    NativeObjectIdentity.from_native(
                        path_object_identity(path), windows=os.name == "nt"
                    ),
                )
            )
        repository = Schema3PackageImportJournalRepository(
            Path(self.temp.name) / "journals"
        )
        genesis = replace(self.head, phase=ImportPhase.PREPARED)
        current = repository.create(genesis, import_lock=self.lock)
        current = repository.append(
            current,
            _successor(current, phase=ImportPhase.ROLLING_BACK),
            import_lock=self.lock,
        )
        protocol = Schema3CleanupProtocol(
            repository,
            DurableCleanupExecutor(roots),
            clock=lambda: "2026-07-23T12:00:01Z",
            token_factory=_uuid,
        )
        return protocol, repository, current, tuple(targets), roots

    def test_pa_rm15_prepared_crash_rolls_back_both_snapshots(self):
        intent = self._intent()
        self.assertEqual(intent.phase, ImportPhase.ROLLING_BACK)
        self.assertEqual(intent.cleanup_operations[0].kind, "ROLLBACK_ALL")

    def test_pa_rm16_processed_reference_mismatch_blocks(self):
        invalid = replace(
            self.head,
            processed_media_commitment=replace(
                self.head.processed_media_commitment,
                manifest_sha256="e" * 64,
            ),
        )
        with self.assertRaises(ValueError):
            invalid.validate()

    def test_pa_rm17_processed_artifact_missing_or_replaced(self):
        missing_root = DurableCleanupExecutor({})
        with self.assertRaises(RecoveryRequired):
            missing_root.remove(
                _target(self.head),
                import_id=self.head.import_id,
                ownership_token=self.head.random_ownership_token,
                import_lock=self.lock,
            )

    def test_pa_rm18_partial_processed_copy_recovery(self):
        self.assertEqual(self.head.verified_image_inventory, ())
        self.assertEqual(len(self.head.expected_image_inventory), 1)

    def test_pa_rm21_committed_before_processed_cleanup_intent(self):
        protocol, repository, head, targets, roots = self._durable_cleanup(
            ("PROCESSED_SNAPSHOT",)
        )
        intent = protocol.begin(
            head,
            kind="SUCCESS_PROCESSED_SNAPSHOT",
            targets=targets,
            import_lock=self.lock,
        )
        self.assertEqual(intent.cleanup_operations[0].status, CleanupStatus.INTENT)
        self.assertEqual(intent.cleanup_operations[0].receipts, ())
        self.assertTrue(
            roots["PROCESSED_SNAPSHOT"]
            .joinpath(targets[0].relative_path)
            .exists()
        )
        self.assertEqual(
            repository.load(head.import_id, import_lock=self.lock), intent
        )

    def test_pa_rm22_processed_cleanup_receipt_prefix(self):
        protocol, repository, head, targets, _roots = self._durable_cleanup(
            ("PROCESSED_SNAPSHOT",)
        )
        intent = protocol.begin(
            head,
            kind="SUCCESS_PROCESSED_SNAPSHOT",
            targets=targets,
            import_lock=self.lock,
        )
        current = protocol.advance(intent, import_lock=self.lock)
        operation = current.cleanup_operations[0]
        self.assertEqual(len(operation.receipts), 1)
        self.assertEqual(operation.receipts[0].target_relative_path, operation.targets[0].relative_path)
        self.assertEqual(
            repository.load(head.import_id, import_lock=self.lock), current
        )

    def test_pa_rm23_absence_before_cleanup_receipt(self):
        from hashlib import sha256
        import os
        from capture_import._filesystem import (
            open_plain_directory_handle,
            path_object_identity,
            sync_directory,
        )
        from capture_import.durable_models import NativeObjectIdentity

        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            owned = root_path / "owned"
            owned.mkdir()
            artifact = owned / "artifact.jpg"
            artifact.write_bytes(b"x")

            def native(path):
                return NativeObjectIdentity.from_native(
                    path_object_identity(path), windows=os.name == "nt"
                )

            targets = (
                OwnershipDescriptorV3(
                    "PROCESSED_SNAPSHOT",
                    "owned/artifact.jpg",
                    "FILE",
                    self.head.random_ownership_token,
                    1,
                    sha256(b"x").hexdigest(),
                    native(owned),
                    native(artifact),
                ),
                OwnershipDescriptorV3(
                    "PROCESSED_SNAPSHOT",
                    "owned",
                    "DIRECTORY",
                    self.head.random_ownership_token,
                    None,
                    None,
                    native(root_path),
                    native(owned),
                ),
            )
            protocol = Schema3CleanupProtocol(
                _Journal(),
                DurableCleanupExecutor(
                    {"PROCESSED_SNAPSHOT": root_path}
                ),
                clock=lambda: "2026-07-23T12:00:01Z",
                token_factory=_uuid,
            )
            intent = protocol.begin_rollback(
                self.head, targets=targets, import_lock=self.lock
            )
            with open_plain_directory_handle(owned) as parent:
                os.unlink(artifact)
                sync_directory(parent)
            recovered = protocol.advance(
                intent, import_lock=self.lock
            )
            operation = recovered.cleanup_operations[0]
            self.assertEqual(len(operation.receipts), 1)
            self.assertEqual(
                operation.receipts[0].removed_object_identity,
                targets[0].object_identity,
            )
            completed = protocol.complete(
                recovered, import_lock=self.lock
            )
            self.assertEqual(
                completed.cleanup_operations[0].status,
                CleanupStatus.COMPLETE,
            )
            self.assertEqual(
                protocol.complete(completed, import_lock=self.lock),
                completed,
            )

    def test_schema2_absent_target_keeps_legacy_no_membership_probe(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            target = OwnershipDescriptor(
                "SNAPSHOT",
                "already-absent.bin",
                "FILE",
                self.head.random_ownership_token,
                1,
                sha256(b"x").hexdigest(),
                NativeObjectIdentity.from_native(
                    path_object_identity(root_path), windows=os.name == "nt"
                ),
                _identity(),
            )
            executor = DurableCleanupExecutor({"SNAPSHOT": root_path})
            with patch(
                "capture_import.cleanup_persistence.os.listdir",
                side_effect=AssertionError("Schema 2 must not inspect members"),
            ):
                removed = executor.remove(
                    target,
                    import_id=self.head.import_id,
                    ownership_token=self.head.random_ownership_token,
                    import_lock=self.lock,
                )
            self.assertEqual(removed, target.object_identity)

    def test_pa_rm24_processed_cleanup_completion_only(self):
        protocol, repository, head, targets, _roots = self._durable_cleanup(
            ("PROCESSED_SNAPSHOT",)
        )
        intent = protocol.begin(
            head,
            kind="SUCCESS_PROCESSED_SNAPSHOT",
            targets=targets,
            import_lock=self.lock,
        )
        receipted = protocol.advance(intent, import_lock=self.lock)
        self.assertEqual(
            repository.load(head.import_id, import_lock=self.lock), receipted
        )
        current = protocol.advance(receipted, import_lock=self.lock)
        self.assertEqual(current.cleanup_operations[0].status, CleanupStatus.COMPLETE)
        self.assertEqual(protocol.complete(current, import_lock=self.lock), current)

    def test_baseline_cleanup_receipt_marks_backup_cleaned(self):
        from hashlib import sha256

        expected = self.head.expected_image_inventory[0]
        verified = VerifiedImageV3(
            expected.relative_path,
            expected.role,
            expected.byte_length,
            expected.sha256,
            expected.media_type,
            expected.width,
            expected.height,
            expected.source_kind,
            expected.source_snapshot_id,
            expected.source_coin_id,
            expected.source_artifact_key,
            expected.variant,
            _identity(),
            _identity(),
        )
        temporary = CollectionPublicationArtifact(
            "TEMPORARY",
            f".collection-{self.head.import_id}-{_uuid()}.tmp",
            _uuid(),
            "PROSPECTIVE_BYTES",
            2,
            sha256(b"[]").hexdigest(),
            _identity(),
            CollectionPublicationState.PUBLISHED,
            _identity(),
            2,
            sha256(b"[]").hexdigest(),
            1,
            "collection.json",
            None,
            "collection.json",
            1,
            None,
        )
        backup = CollectionPublicationArtifact(
            "BACKUP",
            f".collection-{self.head.import_id}-{_uuid()}.bak",
            _uuid(),
            "BASELINE_BYTES",
            1,
            "f" * 64,
            _identity(),
            CollectionPublicationState.RETAINED,
            _identity(),
            1,
            "f" * 64,
            1,
            "baseline.bak",
            None,
            None,
            1,
            None,
        )
        head = replace(
            self.head,
            phase=ImportPhase.COLLECTION_COMMITTED,
            collection_baseline_sha256_or_sentinel="f" * 64,
            collection_baseline_byte_length=1,
            prospective_collection_byte_length=2,
            prospective_collection_sha256=sha256(b"[]").hexdigest(),
            verified_image_inventory=(verified,),
            committed_collection_item_ids=self.head.desktop_item_ids,
            imported_count=1,
            collection_publication="VERIFIED",
            collection_temporary_artifact=temporary,
            collection_backup_artifact=backup,
            pending_terminal_audit={},
        )
        target = OwnershipDescriptorV3(
            "COLLECTION",
            backup.current_relative_name,
            "FILE",
            head.random_ownership_token,
            backup.expected_byte_length,
            backup.expected_sha256,
            backup.expected_parent_identity,
            backup.object_identity,
        )
        protocol = Schema3CleanupProtocol(
            _Journal(),
            _Executor(),
            clock=lambda: "2026-07-23T12:00:01Z",
            token_factory=_uuid,
        )
        intent = protocol.begin(
            head,
            kind="BASELINE_BACKUP",
            targets=(target,),
            import_lock=self.lock,
        )
        receipted = protocol.advance(intent, import_lock=self.lock)
        cleaned = receipted.collection_backup_artifact
        self.assertEqual(cleaned.state, CollectionPublicationState.CLEANED)
        self.assertEqual(
            cleaned.cleanup_operation_id,
            receipted.cleanup_operations[-1].intent_id,
        )
        completed = protocol.complete(
            receipted, import_lock=self.lock
        )
        self.assertEqual(
            completed.collection_backup_artifact, cleaned
        )
        self.assertEqual(
            protocol.complete(completed, import_lock=self.lock),
            completed,
        )

    def test_pa_rm25_processed_then_raw_cleanup_order(self):
        protocol, repository, head, targets, roots = self._durable_cleanup(
            ("PROCESSED_SNAPSHOT", "SNAPSHOT")
        )
        current = protocol.begin_rollback(
            head, targets=targets, import_lock=self.lock
        )
        current = protocol.advance(current, import_lock=self.lock)
        self.assertFalse(
            roots["PROCESSED_SNAPSHOT"]
            .joinpath(targets[0].relative_path)
            .exists()
        )
        self.assertTrue(
            roots["SNAPSHOT"].joinpath(targets[1].relative_path).exists()
        )
        released = protocol.release_processed_reference(
            current, import_lock=self.lock
        )
        self.assertIsNone(released.processed_snapshot_reference)
        self.assertEqual(
            repository.load(head.import_id, import_lock=self.lock), released
        )
        continued = protocol.advance(released, import_lock=self.lock)
        self.assertEqual(len(continued.cleanup_operations[0].receipts), 2)
        self.assertEqual(
            released.processed_media_commitment,
            current.processed_media_commitment,
        )
        completed = protocol.advance(continued, import_lock=self.lock)
        self.assertEqual(
            protocol.complete(completed, import_lock=self.lock), completed
        )

    def test_pa_rm26_rollback_dual_snapshot_cleanup(self):
        protocol, _repository, head, targets, roots = self._durable_cleanup(
            ("COLLECTION", "MANAGED_IMAGE", "PROCESSED_SNAPSHOT", "SNAPSHOT")
        )
        current = protocol.begin_rollback(
            head, targets=targets, import_lock=self.lock
        )
        for index, target in enumerate(targets):
            current = protocol.advance(current, import_lock=self.lock)
            self.assertFalse(
                roots[target.root].joinpath(target.relative_path).exists()
            )
            for later in targets[index + 1 :]:
                self.assertTrue(
                    roots[later.root].joinpath(later.relative_path).exists()
                )
            if target.root == "PROCESSED_SNAPSHOT":
                current = protocol.release_processed_reference(
                    current, import_lock=self.lock
                )
        current = protocol.advance(current, import_lock=self.lock)
        self.assertEqual(protocol.complete(current, import_lock=self.lock), current)
        with self.assertRaises(RecoveryRequired):
            Schema3CleanupProtocol.validate_rollback_order(tuple(reversed(targets)))

    def test_pa_rm43_processed_cleanup_release_publication(self):
        protocol, repository, head, targets, _roots = self._durable_cleanup(
            ("PROCESSED_SNAPSHOT",)
        )
        current = protocol.complete(
            protocol.begin(
                head,
                kind="SUCCESS_PROCESSED_SNAPSHOT",
                targets=targets,
                import_lock=self.lock,
            ),
            import_lock=self.lock,
        )
        released = _successor(current, processed_snapshot_reference=None)
        directory = Path(self.temp.name) / "journals" / head.import_id
        candidate_name = repository.temporary_name(
            released.generation, current.next_generation_token
        )
        (directory / candidate_name).write_bytes(
            canonical_json_bytes(released.to_dict())
        )
        reconciled = repository.load(head.import_id, import_lock=self.lock)
        self.assertEqual(reconciled, released)
        self.assertFalse((directory / candidate_name).exists())
        self.assertEqual(
            repository.load(head.import_id, import_lock=self.lock), reconciled
        )


class Schema3TerminalTests(unittest.TestCase):
    def test_terminal_model_rejects_incomplete_cleanup(self):
        head = _generation()
        with self.assertRaises(RecoveryRequired):
            from capture_import.terminal_persistence import Schema3TerminalHistoryRepository
            Schema3TerminalHistoryRepository.build_record(
                head,
                result=SimpleNamespace(),
                completed_at="2026-07-23T12:00:01Z",
                collection_proof=SimpleNamespace(),
                managed_image_proof=SimpleNamespace(),
                operational_chain_proof=SimpleNamespace(),
                audit={},
            )

    def test_terminal_processed_proof_round_trip(self):
        retained = TerminalProcessedMediaProof.from_commitment(
            _generation().processed_media_commitment, outcome="RETAINED"
        )
        self.assertEqual(
            TerminalProcessedMediaProof.from_dict(retained.to_dict()), retained
        )

    def test_terminal_v2_field_boundary(self):
        self.assertIn("processed_media_proof", TerminalHistoryRecordV2.__dataclass_fields__)
        self.assertNotIn("processed_media_proof", TerminalHistoryRecord.__dataclass_fields__)

    def test_terminal_success_proof_stability(self):
        proof = TerminalProcessedMediaProof.from_commitment(
            _generation().processed_media_commitment, outcome="RETAINED"
        )
        self.assertEqual(proof.to_dict(), proof.to_dict())

    def test_terminal_rollback_proof_outcome(self):
        proof = TerminalProcessedMediaProof.from_commitment(
            _generation().processed_media_commitment, outcome="REMOVED"
        )
        self.assertEqual(proof.outcome, "REMOVED")

    def test_terminal_cross_parser_rejection(self):
        value = {"terminal_schema_version": "1.0", "processed_media_proof": {}}
        with self.assertRaises(ValueError):
            TerminalHistoryRecord.from_dict(value)
        with self.assertRaises(ValueError):
            TerminalHistoryRecordV2.from_dict(value)

    def test_terminal_processed_proof_is_closed(self):
        proof = TerminalProcessedMediaProof.from_commitment(
            _generation().processed_media_commitment, outcome="RETAINED"
        ).to_dict()
        proof["manifest_sha256"] = "e" * 64
        parsed = TerminalProcessedMediaProof.from_dict(proof)
        self.assertNotEqual(
            parsed.manifest_sha256,
            _generation().processed_media_commitment.manifest_sha256,
        )


class UnifiedRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.head = _generation()
        self.journals = Mock()
        self.journals.list_heads.side_effect = [(self.head,), (self.head,)]
        self.legacy_terminal = Mock()
        self.legacy_terminal.list_final.return_value = ()
        self.legacy_terminal.pending_import_ids.return_value = ()
        self.processed_terminal = Mock()
        self.processed_terminal.list_final.return_value = ()
        self.processed_terminal.pending_import_ids.return_value = ()
        self.raw = Mock()
        self.processed = Mock()
        processed_handle = Mock()
        processed_handle.journal_reference.return_value = (
            self.head.processed_snapshot_reference
        )
        processed_handle.media_commitment.return_value = (
            self.head.processed_media_commitment
        )
        self.processed.open_snapshot.return_value = processed_handle
        self.schema3_runtime = Mock()
        self.schema3_runtime.recover_locked.return_value = "schema3"
        self.service = UnifiedPackageImportRecoveryService(
            lock_path=Path(self.temp.name) / "global.lock",
            journals=self.journals,
            schema1_terminal=self.legacy_terminal,
            schema2_snapshots=self.raw,
            schema3_snapshots=self.processed,
            schema3_terminal=self.processed_terminal,
            recover_schema2_locked=Mock(),
            schema3_runtime=self.schema3_runtime,
        )

    def test_unified_referenced_processed_snapshot_exclusion(self):
        self.service.reconcile_pending_imports()
        reference = self.head.processed_snapshot_reference.processed_snapshot_id
        self.processed.cleanup_orphaned_snapshots.assert_called_once()
        self.assertEqual(
            self.processed.cleanup_orphaned_snapshots.call_args.args[0],
            (reference,),
        )

    def test_cleanup_prefix_recovery_does_not_reopen_processed_snapshot(self):
        target = _target(self.head)
        rolling = _successor(
            self.head, phase=ImportPhase.ROLLING_BACK
        )
        cleanup = _successor(
            rolling,
            cleanup_operations=(
                CleanupOperationV3(
                    "ROLLBACK_ALL",
                    _uuid(),
                    rolling.generation + 1,
                    (target,),
                    (),
                    CleanupStatus.INTENT,
                    None,
                ),
            ),
        )
        self.journals.list_heads.side_effect = [(cleanup,), (cleanup,)]
        self.service.reconcile_pending_imports()
        self.processed.open_snapshot.assert_not_called()
        self.schema3_runtime.recover_locked.assert_called_once()

    def test_unified_uncertain_processed_orphan_propagates(self):
        self.processed.cleanup_orphaned_snapshots.side_effect = RecoveryRequired()
        with self.assertRaises(RecoveryRequired):
            self.service.reconcile_pending_imports()
        self.schema3_runtime.recover_locked.assert_not_called()

    def test_unified_mixed_version_final_conflict(self):
        record = SimpleNamespace(import_id=self.head.import_id)
        self.legacy_terminal.list_final.return_value = (record,)
        self.processed_terminal.list_final.return_value = (record,)
        with self.assertRaises(RecoveryRequired):
            self.service.reconcile_pending_imports()

    def test_unified_processed_root_error_propagates(self):
        self.processed.cleanup_orphaned_snapshots.side_effect = OSError("unsupported")
        with self.assertRaises(OSError):
            self.service.reconcile_pending_imports()
        self.schema3_runtime.recover_locked.assert_not_called()

    def test_unified_pending_processed_proof_mismatch(self):
        self.processed_terminal.pending_import_ids.return_value = (
            self.head.import_id,
        )
        wrong = TerminalProcessedMediaProof.from_commitment(
            self.head.processed_media_commitment,
            outcome="RETAINED",
        )
        wrong = replace(wrong, manifest_sha256="e" * 64)
        self.processed_terminal.load_pending.return_value = SimpleNamespace(
            result=ImportResult.SUCCEEDED,
            processed_media_proof=wrong,
        )
        with self.assertRaises(RecoveryRequired):
            self.service.reconcile_pending_imports()
        self.schema3_runtime.recover_locked.assert_not_called()

    def test_unified_runtime_called_on_repeated_reconciliation(self):
        self.journals.list_heads.side_effect = [
            (self.head,),
            (self.head,),
            (self.head,),
            (self.head,),
        ]
        self.service.reconcile_pending_imports()
        self.service.reconcile_pending_imports()
        self.assertEqual(self.schema3_runtime.recover_locked.call_count, 2)

    def test_cleanup_executor_without_processed_root(self):
        executor = DurableCleanupExecutor({})
        self.assertNotIn("PROCESSED_SNAPSHOT", executor._roots)


class ProcessedRecoveryMatrixRegistryTests(unittest.TestCase):
    def test_recovery_matrix_registry_has_exactly_43_resolvable_ids(self):
        root = Path(__file__).parent
        found: dict[int, list[str]] = {}
        pattern = re.compile(r"def test_pa_rm(\d{2})_[a-z0-9_]+\(")
        for path in root.glob("test_*.py"):
            for match in pattern.finditer(path.read_text(encoding="utf-8")):
                found.setdefault(int(match.group(1)), []).append(path.name)
        self.assertEqual(set(found), set(range(1, 44)))
        self.assertTrue(all(found[index] for index in range(1, 44)))


if __name__ == "__main__":
    unittest.main()
