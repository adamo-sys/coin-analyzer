"""Focused concrete Schema 3 post-genesis runtime tests."""

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

import capture_import.terminal_persistence as terminal_persistence
from coin_collection import CoinCollection
from capture_import.durable_models import (
    CleanupOperationV3,
    CleanupReceipt,
    CollectionPublicationArtifact,
    NativeObjectIdentity,
    OwnershipDescriptorV3,
    VerifiedImageV3,
)
from capture_import._filesystem import path_object_identity
from capture_import._json import canonical_json_bytes
from capture_import.cleanup_persistence import (
    DurableCleanupExecutor,
    Schema3CleanupProtocol,
)
from capture_import.durable_repository import (
    Schema2PackageImportJournalRepository,
    Schema3PackageImportJournalRepository,
    VersionedPackageImportJournalRepository,
)
from capture_import.enums import (
    CleanupStatus,
    CollectionPublicationState,
    ImportPhase,
    ImportResult,
    TerminalCompactionStatus,
)
from capture_import.errors import RecoveryRequired, SnapshotRecoveryRequired
from capture_import.lock import PackageImportLock
from capture_import.collection_persistence import DurableCollectionPublisher
from capture_import.decisions import ImportDecisionModel
from capture_import.models import CollectionBaseline
from capture_import.image_store import ManagedCollectionImageStore
from capture_import.processed_snapshot import ProcessedArtifactSnapshotService
from capture_import.schema3_runtime import Schema3PackageImportRecoveryService
from capture_import.snapshot import CapturePackageSnapshotService
from capture_import.terminal_persistence import (
    Schema3TerminalPersistenceService,
    TerminalPersistenceService,
)
from capture_import.recovery import UnifiedPackageImportRecoveryService
from tests.test_schema3_durable_contracts import (
    _generation,
    _identity,
    _successor,
    _uuid,
)
from tests.test_schema3_cleanup_recovery import _target
from tests.test_processed_artifact_snapshot import (
    _Ids as _ProcessedIds,
    _jpeg as _processed_jpeg,
    _package as _processed_package,
    _prepared as _processed_prepared,
)


class Schema3RuntimeDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.head = _generation()
        self.runtime = Schema3PackageImportRecoveryService.__new__(
            Schema3PackageImportRecoveryService
        )
        self.runtime._start_rollback = Mock(return_value="rollback")
        self.runtime._start_success_cleanup = Mock(return_value="success")
        self.runtime._recover_committing = Mock(return_value="committing")
        self.runtime._resume_cleanup = Mock(return_value="cleanup")
        self.runtime._terminal = Mock()
        self.runtime._terminal.recover_compacting.return_value = "terminal"
        self.lock = PackageImportLock.acquire(
            Path(self.temp.name) / "global.lock",
            import_id=self.head.import_id,
        )
        self.addCleanup(self.lock.release)

    def test_prepared_recovery_enters_concrete_rollback(self):
        self.assertEqual(
            self.runtime.recover_locked(self.head, self.lock), "rollback"
        )
        self.runtime._start_rollback.assert_called_once_with(
            self.head, self.lock
        )

    def test_files_ready_restart_rolls_back(self):
        head = SimpleNamespace(
            import_id=self.head.import_id,
            phase=ImportPhase.FILES_READY,
            cleanup_operations=(),
            validate=Mock(),
        )
        self.assertEqual(
            self.runtime.recover_locked(head, self.lock), "rollback"
        )

    def test_collection_committed_starts_success_cleanup(self):
        head = SimpleNamespace(
            import_id=self.head.import_id,
            phase=ImportPhase.COLLECTION_COMMITTED,
            cleanup_operations=(),
            validate=Mock(),
        )
        self.assertEqual(
            self.runtime.recover_locked(head, self.lock), "success"
        )

    def test_cleanup_authority_does_not_reopen_processed_snapshot(self):
        target = _target(self.head)
        operation = CleanupOperationV3(
            "ROLLBACK_ALL",
            _uuid(),
            1,
            (target,),
            (),
            CleanupStatus.INTENT,
            None,
        )
        head = SimpleNamespace(
            import_id=self.head.import_id,
            phase=ImportPhase.ROLLING_BACK,
            cleanup_operations=(operation,),
            validate=Mock(),
        )
        self.runtime._reopen = Mock(side_effect=AssertionError("must not reopen"))
        self.assertEqual(
            self.runtime.recover_locked(head, self.lock), "cleanup"
        )
        self.runtime._reopen.assert_not_called()

    def test_compacting_dispatches_typed_terminal_seam(self):
        head = SimpleNamespace(
            import_id=self.head.import_id,
            phase=ImportPhase.COMPACTING,
            cleanup_operations=(),
            validate=Mock(),
        )
        self.assertEqual(
            self.runtime.recover_locked(head, self.lock), "terminal"
        )

    def test_cancellation_before_committing_rolls_back(self):
        self.assertEqual(
            self.runtime.cancel_locked(self.head, self.lock), "rollback"
        )

    def test_cancellation_after_committing_is_disabled(self):
        head = SimpleNamespace(
            import_id=self.head.import_id,
            phase=ImportPhase.COMMITTING_COLLECTION,
        )
        with self.assertRaises(RecoveryRequired):
            self.runtime.cancel_locked(head, self.lock)


class _AppendingJournal:
    def __init__(self):
        self.entries = []

    def append(self, previous, current, *, import_lock):
        current.validate()
        self.entries.append(current)
        return current


class ForegroundProgressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.head = _generation()
        self.lock = PackageImportLock.acquire(
            Path(tempfile.gettempdir()) / f"{_uuid()}.lock",
            import_id=self.head.import_id,
        )
        self.addCleanup(self.lock.release)
        self.journal = _AppendingJournal()
        self.images = Mock()
        self.images.plan_processed.return_value = Mock()
        self.runtime = Schema3PackageImportRecoveryService(
            collection=Mock(),
            journals=self.journal,
            snapshots=Mock(),
            processed_snapshots=Mock(),
            images=self.images,
            publisher=Mock(),
            cleanup=Mock(),
            terminal=Mock(),
            clock=lambda: "2026-07-23T12:00:01Z",
            token_factory=_uuid,
        )
        expected = self.head.expected_image_inventory[0]
        self.verified = VerifiedImageV3(
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

    def _run_until_copy_crash(self, copy_effect):
        self.images.copy_processed.side_effect = copy_effect
        with patch.object(ImportDecisionModel, "validate"):
            with self.assertRaisesRegex(RuntimeError, "crash boundary"):
                self.runtime.progress_foreground_locked(
                    self.head,
                    Mock(),
                    Mock(),
                    Mock(),
                    Mock(),
                    Mock(),
                    self.lock,
                )

    def test_prepared_precedes_one_generation_per_verified_image(self):
        def copy(_processed, _plan, _created, **kwargs):
            kwargs["on_image_verified"](self.verified)
            raise RuntimeError("crash boundary")

        self._run_until_copy_crash(copy)
        self.assertEqual(
            [entry.phase for entry in self.journal.entries],
            [ImportPhase.COPYING_IMAGES, ImportPhase.COPYING_IMAGES],
        )
        self.assertEqual(
            [len(entry.verified_image_inventory) for entry in self.journal.entries],
            [0, 1],
        )

    def test_crash_after_image_sync_before_evidence_leaves_no_false_evidence(self):
        def copy(_processed, _plan, _created, **_kwargs):
            raise RuntimeError("crash boundary")

        self._run_until_copy_crash(copy)
        self.assertEqual(len(self.journal.entries), 1)
        self.assertEqual(
            self.journal.entries[0].phase, ImportPhase.COPYING_IMAGES
        )
        self.assertEqual(
            self.journal.entries[0].verified_image_inventory, ()
        )


class WideCleanupContractTests(unittest.TestCase):
    def test_schema3_cleanup_supports_full_width_above_301_targets(self):
        head = replace(_generation(), phase=ImportPhase.ROLLING_BACK)
        targets = tuple(
            _target(head, f"processed/{index:04d}.jpg")
            for index in range(302)
        )
        operation = CleanupOperationV3(
            "ROLLBACK_ALL",
            _uuid(),
            1,
            targets,
            (),
            CleanupStatus.INTENT,
            None,
        )
        generation = _successor(
            head,
            cleanup_operations=(operation,),
        )
        generation.validate()
        self.assertEqual(len(generation.cleanup_operations[0].targets), 302)
        with tempfile.TemporaryDirectory() as root:
            prepared = _generation(
                import_id=head.import_id,
                owner=head.random_ownership_token,
                snapshot_id=(
                    head.processed_snapshot_reference.processed_snapshot_id
                ),
                workflow_id=(
                    head.processed_snapshot_reference.workflow_execution_id
                ),
            )
            repository = Schema3PackageImportJournalRepository(
                Path(root) / "journals"
            )
            lock = PackageImportLock.acquire(
                Path(tempfile.gettempdir()) / f"{_uuid()}.lock",
                import_id=head.import_id,
            )
            self.addCleanup(lock.release)
            current = repository.create(prepared, import_lock=lock)
            current = repository.append(
                current,
                _successor(current, phase=ImportPhase.ROLLING_BACK),
                import_lock=lock,
            )
            protocol = Schema3CleanupProtocol(
                repository,
                Mock(),
                clock=lambda: "2026-07-23T12:00:01Z",
                token_factory=_uuid,
            )
            current = protocol.begin_rollback(
                current,
                targets=targets,
                import_lock=lock,
            )
            self.assertEqual(
                len(current.cleanup_operations[-1].targets), 302
            )

    def test_receipt_identity_must_equal_target_identity(self):
        with tempfile.TemporaryDirectory() as root:
            head = replace(_generation(), phase=ImportPhase.ROLLING_BACK)
            target = _target(head)
            receipt = CleanupReceipt(
                target.relative_path,
                NativeObjectIdentity("POSIX", "9", "9"),
                2,
            )
            operation = CleanupOperationV3(
                "ROLLBACK_ALL",
                _uuid(),
                1,
                (target,),
                (receipt,),
                CleanupStatus.INTENT,
                None,
            )
            lock = PackageImportLock.acquire(
                Path(tempfile.gettempdir()) / f"{_uuid()}.lock",
                import_id=head.import_id,
            )
            self.addCleanup(lock.release)
            executor = DurableCleanupExecutor(
                {"PROCESSED_SNAPSHOT": Path(root)}
            )
            with self.assertRaises(RecoveryRequired):
                executor.verify_operation(
                    operation,
                    import_id=head.import_id,
                    ownership_token=head.random_ownership_token,
                    import_lock=lock,
                    allow_next_absent=False,
                )

    def test_extra_owned_directory_member_blocks_before_deletion(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            owned = root_path / "owned"
            owned.mkdir()
            planned = owned / "planned.jpg"
            planned.write_bytes(b"x")
            (owned / "third-party.txt").write_bytes(b"extra")
            head = replace(_generation(), phase=ImportPhase.ROLLING_BACK)

            def native(path):
                return NativeObjectIdentity.from_native(
                    path_object_identity(path), windows=os.name == "nt"
                )

            targets = (
                OwnershipDescriptorV3(
                    "PROCESSED_SNAPSHOT",
                    "owned/planned.jpg",
                    "FILE",
                    head.random_ownership_token,
                    1,
                    sha256(b"x").hexdigest(),
                    native(owned),
                    native(planned),
                ),
                OwnershipDescriptorV3(
                    "PROCESSED_SNAPSHOT",
                    "owned",
                    "DIRECTORY",
                    head.random_ownership_token,
                    None,
                    None,
                    native(root_path),
                    native(owned),
                ),
            )
            operation = CleanupOperationV3(
                "ROLLBACK_ALL",
                _uuid(),
                1,
                targets,
                (),
                CleanupStatus.INTENT,
                None,
            )
            lock = PackageImportLock.acquire(
                Path(tempfile.gettempdir()) / f"{_uuid()}.lock",
                import_id=head.import_id,
            )
            self.addCleanup(lock.release)
            executor = DurableCleanupExecutor(
                {"PROCESSED_SNAPSHOT": root_path}
            )
            with self.assertRaises(RecoveryRequired):
                executor.verify_operation(
                    operation,
                    import_id=head.import_id,
                    ownership_token=head.random_ownership_token,
                    import_lock=lock,
                    allow_next_absent=False,
                )
            self.assertTrue(planned.exists())
            self.assertTrue((owned / "third-party.txt").exists())


class CollectionObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.import_id = _uuid()
        self.publisher = DurableCollectionPublisher(self.root / "collection.json")
        self.baseline = CollectionBaseline("MISSING_COLLECTION_V1", 0)
        self.payload = b"[]"
        self.temporary, self.backup = self.publisher.plan(
            self.payload,
            baseline=self.baseline,
            import_id=self.import_id,
            temporary_token=_uuid(),
            backup_token=_uuid(),
        )
        self.lock = PackageImportLock.acquire(
            self.root / "global.lock", import_id=self.import_id
        )
        self.addCleanup(self.lock.release)

    def _observe(self):
        from hashlib import sha256
        return self.publisher.observe_planned(
            self.temporary,
            self.backup,
            import_id=self.import_id,
            baseline=self.baseline,
            prospective_byte_length=len(self.payload),
            prospective_sha256=sha256(self.payload).hexdigest(),
            observation_generation=1,
            import_lock=self.lock,
        )

    @staticmethod
    def _verified(artifact, path):
        return replace(
            artifact,
            state=CollectionPublicationState.VERIFIED,
            object_identity=NativeObjectIdentity.from_native(
                path_object_identity(path), windows=os.name == "nt"
            ),
            verified_byte_length=artifact.expected_byte_length,
            verified_sha256=artifact.expected_sha256,
            verified_generation=1,
            current_relative_name=artifact.relative_name,
        )

    def test_exact_baseline_and_prospective_are_distinct(self):
        self.assertEqual(self._observe().state, "EXACT_BASELINE")
        (self.root / "collection.json").write_bytes(self.payload)
        self.temporary = self._verified(
            self.temporary, self.root / "collection.json"
        )
        observation = self._observe()
        self.assertEqual(observation.state, "EXACT_PROSPECTIVE")
        self.assertEqual(
            observation.published_artifact.state,
            CollectionPublicationState.PUBLISHED,
        )
        self.assertEqual(
            observation.published_artifact.current_relative_name,
            "collection.json",
        )

    def test_third_party_destination_blocks(self):
        (self.root / "collection.json").write_bytes(b"third-party")
        self.assertEqual(self._observe().state, "CONFLICTING")

    def test_exact_baseline_allows_only_exact_planned_temporary(self):
        baseline_payload = b"[{\"baseline\":true}]"
        collection = self.root / "existing.json"
        collection.write_bytes(baseline_payload)
        baseline = CollectionBaseline(
            sha256(baseline_payload).hexdigest(), len(baseline_payload)
        )
        publisher = DurableCollectionPublisher(collection)
        temporary, backup = publisher.plan(
            self.payload,
            baseline=baseline,
            import_id=self.import_id,
            temporary_token=_uuid(),
            backup_token=_uuid(),
        )
        (self.root / temporary.relative_name).write_bytes(self.payload)
        temporary = self._verified(
            temporary, self.root / temporary.relative_name
        )
        observation = publisher.observe_planned(
            temporary,
            backup,
            import_id=self.import_id,
            baseline=baseline,
            prospective_byte_length=len(self.payload),
            prospective_sha256=sha256(self.payload).hexdigest(),
            observation_generation=1,
            import_lock=self.lock,
        )
        self.assertEqual(observation.state, "EXACT_BASELINE")
        (self.root / temporary.relative_name).write_bytes(b"foreign")
        self.assertEqual(
            publisher.observe_planned(
                temporary,
                backup,
                import_id=self.import_id,
                baseline=baseline,
                prospective_byte_length=len(self.payload),
                prospective_sha256=sha256(self.payload).hexdigest(),
                observation_generation=1,
                import_lock=self.lock,
            ).state,
            "CONFLICTING",
        )

    def test_same_bytes_with_replaced_temporary_identity_blocks(self):
        temporary_path = self.root / self.temporary.relative_name
        temporary_path.write_bytes(self.payload)
        self.temporary = self._verified(
            self.temporary, temporary_path
        )
        (self.root / "collection.json").write_bytes(self.payload)
        temporary_path.unlink()
        self.assertEqual(self._observe().state, "CONFLICTING")


class _ReceiptExecutor:
    def verify_operation(self, operation, **_kwargs):
        operation.validate()

    def remove(self, target, **_kwargs):
        return target.object_identity

    remove_v3 = remove


def _terminal_audit(head):
    return {
        "audit_schema_version": "1.0",
        "import_id": head.import_id,
        "started_at": head.created_at,
        "completed_at": "2026-07-23T12:00:02Z",
        "package_filename_basename": head.package_basename,
        "package_sha256": head.package_sha256,
        "schema": "coin-analyzer.capture-import-audit",
        "package_version": head.package_version,
        "created_by": "tests",
        "created_with": "tests",
        "exported_at": None,
        "session_id": None,
        "session_name": None,
        "session_description": None,
        "session_date": None,
        "session_created_at": None,
        "session_updated_at": None,
        "coin_provenance": [
            {
                "source_coin_id": "source-1",
                "desktop_item_id": head.desktop_item_ids[0],
                "decision": "IMPORT_AS_NEW",
                "source_position": 0,
                "mint": None,
                "composition": None,
                "is_bullion": False,
                "actual_silver_weight_oz": None,
                "source_created_at": None,
                "source_updated_at": None,
                "source_quantity": 1,
                "image_role_hashes": {"front": "b" * 64},
                "managed_image_paths": [
                    head.expected_image_inventory[0].relative_path
                ],
            }
        ],
        "proposed_count": 1,
        "imported_count": 1,
        "skipped_count": 0,
        "phase": "SUCCEEDED",
        "final_status": "SUCCEEDED",
        "error_category": None,
    }


def _non_success_audit(head, result):
    audit = _terminal_audit(head)
    audit.update(
        {
            "imported_count": 0,
            "phase": result.value,
            "final_status": result.value,
            "error_category": (
                "ROLLED_BACK"
                if result is ImportResult.ROLLED_BACK
                else None
            ),
        }
    )
    return audit


class Schema3UnifiedStartupIntegrationTests(unittest.TestCase):
    def test_pa_rm27_startup_derives_processed_reference_from_journal(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            workspace = root_path / "workspace"
            workspace.mkdir()
            processed_root = root_path / "processed"
            processed = ProcessedArtifactSnapshotService(
                processed_root,
                clock=lambda: "2026-07-23T12:00:00Z",
                identifier_factory=_ProcessedIds(),
            )
            payload = _processed_jpeg()
            lock_path = root_path / "global.lock"
            lock = PackageImportLock.acquire(lock_path)
            handle = processed.seal(
                _processed_prepared(workspace, payload),
                _processed_package(payload),
                import_lock=lock,
            )
            descriptor = handle.manifest.artifacts[0]
            head = _generation(
                snapshot_id=handle.manifest.processed_snapshot_id,
                workflow_id=handle.manifest.workflow_execution_id,
            )
            head = replace(
                head,
                processed_snapshot_reference=handle.journal_reference(),
                processed_media_commitment=handle.media_commitment(
                    ("coin-1",)
                ),
                selected_source_coin_ids=("coin-1",),
                expected_image_inventory=(
                    replace(
                        head.expected_image_inventory[0],
                        byte_length=descriptor.byte_length,
                        sha256=descriptor.sha256,
                        width=descriptor.width,
                        height=descriptor.height,
                        source_snapshot_id=(
                            handle.manifest.processed_snapshot_id
                        ),
                        source_coin_id=descriptor.source_coin_id,
                        source_artifact_key=descriptor.artifact_key,
                        variant=descriptor.variant,
                    ),
                ),
            )
            head.validate()
            versioned = VersionedPackageImportJournalRepository(
                root_path / "journals"
            )
            versioned.create(head, import_lock=lock)
            handle.close()
            lock.release()

            raw = CapturePackageSnapshotService(root_path / "raw")
            schema3_journals = Schema3PackageImportJournalRepository(
                versioned.root
            )
            collection_path = root_path / "collection.json"
            images = ManagedCollectionImageStore(root_path / "images")
            terminal = Schema3TerminalPersistenceService(
                schema3_journals,
                root_path / "history",
                clock=lambda: "2026-07-23T12:00:01Z",
                token_factory=_uuid,
            )
            cleanup = Schema3CleanupProtocol(
                schema3_journals,
                DurableCleanupExecutor(
                    {
                        "COLLECTION": root_path,
                        "MANAGED_IMAGE": root_path / "images",
                        "PROCESSED_SNAPSHOT": processed_root,
                        "SNAPSHOT": root_path / "raw",
                    }
                ),
                clock=lambda: "2026-07-23T12:00:01Z",
                token_factory=_uuid,
            )
            runtime = Schema3PackageImportRecoveryService(
                collection=CoinCollection(str(collection_path)),
                journals=schema3_journals,
                snapshots=raw,
                processed_snapshots=processed,
                images=images,
                publisher=DurableCollectionPublisher(collection_path),
                cleanup=cleanup,
                terminal=terminal,
                clock=lambda: "2026-07-23T12:00:01Z",
                token_factory=_uuid,
            )
            unified = UnifiedPackageImportRecoveryService(
                lock_path=lock_path,
                journals=versioned,
                schema1_terminal=TerminalPersistenceService(
                    Schema2PackageImportJournalRepository(versioned.root),
                    root_path / "legacy-history",
                    clock=lambda: "2026-07-23T12:00:01Z",
                    token_factory=_uuid,
                ),
                schema2_snapshots=raw,
                schema3_snapshots=processed,
                schema3_terminal=terminal,
                recover_schema2_locked=lambda _head, _lock: None,
                schema3_runtime=runtime,
            )
            snapshot = (
                processed_root
                / head.processed_snapshot_reference.processed_snapshot_id
            )

            def durable_bytes():
                return {
                    path.relative_to(root_path).as_posix(): path.read_bytes()
                    for path in root_path.rglob("*")
                    if path.is_file() and path.name != "global.lock"
                }

            before = durable_bytes()
            for _attempt in range(2):
                with self.assertRaises(SnapshotRecoveryRequired):
                    unified.reconcile_pending_imports()
                self.assertTrue(snapshot.is_dir())
                self.assertEqual(durable_bytes(), before)


class Schema3TerminalIntegrationTests(unittest.TestCase):
    def test_pa_rm29_compaction_requires_dual_cleanup(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            head = _generation()
            lock = PackageImportLock.acquire(
                root_path / "global.lock", import_id=head.import_id
            )
            try:
                journals = Schema3PackageImportJournalRepository(
                    root_path / "journals"
                )
                current = journals.create(head, import_lock=lock)
                current = journals.append(
                    current,
                    _successor(
                        current,
                        phase=ImportPhase.ROLLING_BACK,
                        pending_terminal_audit={},
                    ),
                    import_lock=lock,
                )
                operation = CleanupOperationV3(
                    "ROLLBACK_ALL",
                    _uuid(),
                    current.generation + 1,
                    (
                        _target(current, "processed/root", "PROCESSED_SNAPSHOT"),
                        _target(current, "raw/package", "SNAPSHOT"),
                    ),
                    (),
                    CleanupStatus.INTENT,
                    None,
                )
                current = journals.append(
                    current,
                    _successor(current, cleanup_operations=(operation,)),
                    import_lock=lock,
                )
                terminal = Schema3TerminalPersistenceService(
                    journals,
                    root_path / "history",
                    clock=lambda: "2026-07-23T12:00:02Z",
                    token_factory=_uuid,
                )
                journal_dir = journals.root / current.import_id
                before = {
                    path.name: path.read_bytes()
                    for path in journal_dir.iterdir()
                    if path.is_file()
                }
                for _attempt in range(2):
                    with self.assertRaises(RecoveryRequired):
                        terminal.compact(
                            current,
                            result=ImportResult.ROLLED_BACK,
                            error_category="ROLLED_BACK",
                            import_lock=lock,
                        )
                    self.assertEqual(
                        {
                            path.name: path.read_bytes()
                            for path in journal_dir.iterdir()
                            if path.is_file()
                        },
                        before,
                    )
                    self.assertFalse((root_path / "history").exists())
            finally:
                lock.release()

    def _inject_compaction_crash(
        self,
        boundary,
        terminal,
        journals,
        current,
        lock,
    ):
        def compact():
            terminal.compact(
                current,
                result=ImportResult.SUCCEEDED,
                import_lock=lock,
            )

        if boundary == "before_g":
            context = patch.object(
                journals,
                "append",
                side_effect=OSError("crash before G"),
            )
        elif boundary == "after_g_temporary":
            def leave_g(directory, temporary, _final, payload):
                journals._write_direct_exclusive(
                    directory, temporary, payload
                )
                terminal_persistence.sync_directory(directory)
                raise OSError("crash after G temporary")

            context = patch.object(
                journals, "_write_and_publish", side_effect=leave_g
            )
        elif boundary == "before_manifest":
            context = patch.object(
                terminal,
                "_write_manifest",
                side_effect=OSError("crash before manifest"),
            )
        elif boundary == "after_manifest_temporary":
            def leave_manifest(
                directory, planning, payload, *, import_lock
            ):
                journals._write_direct_exclusive(
                    directory,
                    planning.retirement_manifest_temporary_name,
                    payload,
                )
                terminal_persistence.sync_directory(directory)
                raise OSError("crash after manifest temporary")

            context = patch.object(
                terminal,
                "_write_manifest",
                side_effect=leave_manifest,
            )
        elif boundary == "before_h":
            real_append = journals.append

            def stop_before_h(previous, candidate, *, import_lock):
                if (
                    candidate.compaction is not None
                    and candidate.compaction.status
                    is TerminalCompactionStatus.READY_FOR_TERMINAL
                ):
                    raise OSError("crash before H")
                return real_append(
                    previous, candidate, import_lock=import_lock
                )

            context = patch.object(
                journals, "append", side_effect=stop_before_h
            )
        elif boundary == "after_h_temporary":
            real_publish = journals._write_and_publish
            publications = 0

            def leave_h(directory, temporary, final, payload):
                nonlocal publications
                publications += 1
                if publications == 2:
                    journals._write_direct_exclusive(
                        directory, temporary, payload
                    )
                    terminal_persistence.sync_directory(directory)
                    raise OSError("crash after H temporary")
                return real_publish(
                    directory, temporary, final, payload
                )

            context = patch.object(
                journals, "_write_and_publish", side_effect=leave_h
            )
        elif boundary == "before_terminal_temporary":
            context = patch.object(
                terminal,
                "_publish_pending",
                side_effect=OSError("crash before terminal temporary"),
            )
        elif boundary == "after_terminal_temporary":
            real_publish_entry = (
                terminal_persistence
                .publish_open_file_no_replace_in_directory
            )

            def stop_terminal_publish(
                handle, directory, source_name, target_name
            ):
                if target_name.startswith(".pending-"):
                    raise OSError("crash after terminal temporary")
                return real_publish_entry(
                    handle, directory, source_name, target_name
                )

            context = patch.object(
                terminal_persistence,
                "publish_open_file_no_replace_in_directory",
                side_effect=stop_terminal_publish,
            )
        elif boundary == "pending_history":
            context = patch.object(
                terminal,
                "_retire",
                side_effect=OSError("crash with pending history"),
            )
        elif boundary == "late_retirement":
            context = patch(
                "capture_import.terminal_persistence.os.rmdir",
                side_effect=OSError(
                    "crash after retirement manifest deletion"
                ),
            )
        else:
            raise AssertionError(f"unknown crash boundary: {boundary}")

        with context:
            with self.assertRaises(OSError):
                compact()

    def _assert_success_terminal_recovery(
        self,
        pending_assertion=None,
        *,
        crash_boundary="late_retirement",
    ):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            head = _generation()
            lock = PackageImportLock.acquire(
                Path(tempfile.gettempdir()) / f"{_uuid()}.lock",
                import_id=head.import_id,
            )
            self.addCleanup(lock.release)
            journals = Schema3PackageImportJournalRepository(
                root_path / "journals"
            )
            current = journals.create(head, import_lock=lock)
            expected = current.expected_image_inventory[0]
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
            current = journals.append(
                current,
                _successor(
                    current,
                    phase=ImportPhase.COPYING_IMAGES,
                ),
                import_lock=lock,
            )
            current = journals.append(
                current,
                _successor(
                    current,
                    verified_image_inventory=(verified,),
                ),
                import_lock=lock,
            )
            current = journals.append(
                current,
                _successor(current, phase=ImportPhase.FILES_READY),
                import_lock=lock,
            )
            prospective = b"[]"
            temporary = CollectionPublicationArtifact(
                "TEMPORARY",
                f".collection-{current.import_id}-{_uuid()}.tmp",
                _uuid(),
                "PROSPECTIVE_BYTES",
                len(prospective),
                sha256(prospective).hexdigest(),
                _identity(),
                CollectionPublicationState.PLANNED,
            )
            current = journals.append(
                current,
                _successor(
                    current,
                    phase=ImportPhase.COMMITTING_COLLECTION,
                    prospective_collection_byte_length=len(prospective),
                    prospective_collection_sha256=sha256(
                        prospective
                    ).hexdigest(),
                    collection_publication="INTENT",
                    collection_temporary_artifact=temporary,
                ),
                import_lock=lock,
            )
            published = replace(
                temporary,
                state=CollectionPublicationState.PUBLISHED,
                object_identity=_identity(),
                verified_byte_length=len(prospective),
                verified_sha256=sha256(prospective).hexdigest(),
                verified_generation=current.generation,
                current_relative_name="collection.json",
                published_relative_name="collection.json",
                publication_generation=current.generation + 1,
            )
            current = journals.append(
                current,
                _successor(
                    current,
                    phase=ImportPhase.COLLECTION_COMMITTED,
                    collection_publication="VERIFIED",
                    collection_temporary_artifact=published,
                    committed_collection_item_ids=current.desktop_item_ids,
                    imported_count=1,
                    pending_terminal_audit=_terminal_audit(current),
                ),
                import_lock=lock,
            )
            cleanup_roots = {
                "PROCESSED_SNAPSHOT": root_path / "processed-cleanup",
                "SNAPSHOT": root_path / "raw-cleanup",
            }
            cleanup_targets = {}
            for root_name, owned_root in cleanup_roots.items():
                owned_root.mkdir()
                path = owned_root / "owned.bin"
                payload = root_name.encode()
                path.write_bytes(payload)
                cleanup_targets[root_name] = OwnershipDescriptorV3(
                    root_name,
                    path.name,
                    "FILE",
                    current.random_ownership_token,
                    len(payload),
                    sha256(payload).hexdigest(),
                    NativeObjectIdentity.from_native(
                        path_object_identity(owned_root),
                        windows=os.name == "nt",
                    ),
                    NativeObjectIdentity.from_native(
                        path_object_identity(path),
                        windows=os.name == "nt",
                    ),
                )
            cleanup = Schema3CleanupProtocol(
                journals,
                DurableCleanupExecutor(cleanup_roots),
                clock=lambda: "2026-07-23T12:00:03Z",
                token_factory=_uuid,
            )
            current = cleanup.begin(
                current,
                kind="SUCCESS_PROCESSED_SNAPSHOT",
                targets=(cleanup_targets["PROCESSED_SNAPSHOT"],),
                import_lock=lock,
            )
            current = cleanup.complete(current, import_lock=lock)
            current = cleanup.release_processed_reference(
                current, import_lock=lock
            )
            current = cleanup.begin(
                current,
                kind="SUCCESS_SNAPSHOT",
                targets=(cleanup_targets["SNAPSHOT"],),
                import_lock=lock,
            )
            current = cleanup.complete(current, import_lock=lock)
            terminal = Schema3TerminalPersistenceService(
                journals,
                root_path / "history",
                clock=lambda: "2026-07-23T12:00:04Z",
                token_factory=_uuid,
            )
            if pending_assertion is not None:
                with patch.object(
                    terminal,
                    "_retire",
                    side_effect=OSError(
                        "simulated crash before retirement"
                    ),
                ):
                    with self.assertRaises(OSError):
                        terminal.compact(
                            current,
                            result=ImportResult.SUCCEEDED,
                            import_lock=lock,
                        )
                lock.release()
                pending_assertion(
                    root_path, current, journals, terminal
                )
                return
            collection_path = root_path / "collection.json"
            runtime = Schema3PackageImportRecoveryService(
                collection=CoinCollection(str(collection_path)),
                journals=journals,
                snapshots=CapturePackageSnapshotService(
                    root_path / "raw-runtime"
                ),
                processed_snapshots=ProcessedArtifactSnapshotService(
                    root_path / "processed-runtime"
                ),
                images=ManagedCollectionImageStore(
                    root_path / "images-runtime"
                ),
                publisher=DurableCollectionPublisher(collection_path),
                cleanup=cleanup,
                terminal=terminal,
                clock=lambda: "2026-07-23T12:00:05Z",
                token_factory=_uuid,
            )
            self._inject_compaction_crash(
                crash_boundary,
                terminal,
                journals,
                current,
                lock,
            )
            active = journals.root / current.import_id
            if active.exists():
                recovered_head = journals.load(
                    current.import_id, import_lock=lock
                )
                record = runtime.recover_locked(recovered_head, lock)
            else:
                record = terminal.resume_pending(
                    current.import_id, import_lock=lock
                )
            self.assertEqual(record.terminal_schema_version, "2.0")
            self.assertEqual(record.processed_media_proof.outcome, "RETAINED")
            self.assertFalse(active.exists())
            self.assertFalse(
                (
                    journals.root / f".retire-{current.import_id}"
                ).exists()
            )
            final = terminal.list_final()
            self.assertEqual(final, (record,))
            self.assertEqual(terminal.pending_import_ids(), ())
            before = (root_path / "history" / f"{current.import_id}.json").read_bytes()
            self.assertEqual(terminal.list_final(), (record,))
            self.assertEqual(
                (root_path / "history" / f"{current.import_id}.json").read_bytes(),
                before,
            )
            self.assertEqual(
                terminal.resume_pending(current.import_id, import_lock=lock),
                record,
            )
            self.assertEqual(
                (root_path / "history" / f"{current.import_id}.json").read_bytes(),
                before,
            )

    def test_pa_rm30_processed_terminal_compaction_replay(self):
        boundaries = (
            "before_g",
            "after_g_temporary",
            "before_manifest",
            "after_manifest_temporary",
            "before_h",
            "after_h_temporary",
            "before_terminal_temporary",
            "after_terminal_temporary",
            "pending_history",
            "late_retirement",
        )
        for boundary in boundaries:
            with self.subTest(boundary=boundary):
                self._assert_success_terminal_recovery(
                    crash_boundary=boundary
                )

    def test_pa_rm31_processed_chain_retirement(self):
        self._assert_success_terminal_recovery()

    def test_pa_rm32_processed_success_is_inert(self):
        self._assert_success_terminal_recovery()

    def test_pa_rm39_terminal_processed_proof_mismatch(self):
        def assert_pending_mismatch(root_path, current, journals, terminal):
            pending = (
                root_path
                / "history"
                / f".pending-{current.import_id}.json"
            )
            value = json.loads(pending.read_bytes())
            value["processed_media_proof"]["manifest_sha256"] = "e" * 64
            pending.write_bytes(canonical_json_bytes(value))

            collection_path = root_path / "collection.json"
            raw = CapturePackageSnapshotService(root_path / "raw")
            processed = ProcessedArtifactSnapshotService(
                root_path / "processed"
            )
            images = ManagedCollectionImageStore(root_path / "images")
            cleanup = Schema3CleanupProtocol(
                journals,
                DurableCleanupExecutor(
                    {
                        "COLLECTION": root_path,
                        "MANAGED_IMAGE": root_path / "images",
                        "PROCESSED_SNAPSHOT": root_path / "processed",
                        "SNAPSHOT": root_path / "raw",
                    }
                ),
                clock=lambda: "2026-07-23T12:00:05Z",
                token_factory=_uuid,
            )
            runtime = Schema3PackageImportRecoveryService(
                collection=CoinCollection(str(collection_path)),
                journals=journals,
                snapshots=raw,
                processed_snapshots=processed,
                images=images,
                publisher=DurableCollectionPublisher(collection_path),
                cleanup=cleanup,
                terminal=terminal,
                clock=lambda: "2026-07-23T12:00:05Z",
                token_factory=_uuid,
            )
            unified = UnifiedPackageImportRecoveryService(
                lock_path=root_path / "global.lock",
                journals=VersionedPackageImportJournalRepository(
                    journals.root
                ),
                schema1_terminal=TerminalPersistenceService(
                    Schema2PackageImportJournalRepository(journals.root),
                    root_path / "legacy-history",
                    clock=lambda: "2026-07-23T12:00:05Z",
                    token_factory=_uuid,
                ),
                schema2_snapshots=raw,
                schema3_snapshots=processed,
                schema3_terminal=terminal,
                recover_schema2_locked=lambda _head, _lock: None,
                schema3_runtime=runtime,
            )

            def tree_bytes():
                return {
                    path.relative_to(root_path).as_posix(): path.read_bytes()
                    for path in root_path.rglob("*")
                    if path.is_file()
                    and path.name != "global.lock"
                }

            before = tree_bytes()
            for _attempt in range(2):
                with self.assertRaises(RecoveryRequired):
                    unified.reconcile_pending_imports()
                self.assertEqual(tree_bytes(), before)

        self._assert_success_terminal_recovery(
            pending_assertion=assert_pending_mismatch
        )

    def test_pa_rm40_repeated_processed_recovery_is_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            head = _generation()
            lock_path = root_path / "global.lock"
            lock = PackageImportLock.acquire(
                lock_path, import_id=head.import_id
            )
            journals = Schema3PackageImportJournalRepository(
                root_path / "journals"
            )
            current = journals.create(head, import_lock=lock)
            current = journals.append(
                current,
                _successor(
                    current,
                    phase=ImportPhase.ROLLING_BACK,
                    pending_terminal_audit=_non_success_audit(
                        current, ImportResult.ROLLED_BACK
                    ),
                ),
                import_lock=lock,
            )
            roots = {
                "PROCESSED_SNAPSHOT": root_path / "processed",
                "SNAPSHOT": root_path / "raw",
            }
            targets = []
            for index, (root_name, owned_root) in enumerate(
                roots.items()
            ):
                owned_root.mkdir()
                path = owned_root / f"owned-{index}.bin"
                payload = f"payload-{index}".encode()
                path.write_bytes(payload)
                targets.append(
                    OwnershipDescriptorV3(
                        root_name,
                        path.name,
                        "FILE",
                        current.random_ownership_token,
                        len(payload),
                        sha256(payload).hexdigest(),
                        NativeObjectIdentity.from_native(
                            path_object_identity(owned_root),
                            windows=os.name == "nt",
                        ),
                        NativeObjectIdentity.from_native(
                            path_object_identity(path),
                            windows=os.name == "nt",
                        ),
                    )
                )
            cleanup = Schema3CleanupProtocol(
                journals,
                DurableCleanupExecutor(roots),
                clock=lambda: "2026-07-23T12:00:05Z",
                token_factory=_uuid,
            )
            current = cleanup.begin_rollback(
                current,
                targets=tuple(targets),
                import_lock=lock,
            )
            collection_path = root_path / "collection.json"
            raw = CapturePackageSnapshotService(roots["SNAPSHOT"])
            processed = ProcessedArtifactSnapshotService(
                roots["PROCESSED_SNAPSHOT"]
            )
            terminal = Schema3TerminalPersistenceService(
                journals,
                root_path / "history",
                clock=lambda: "2026-07-23T12:00:06Z",
                token_factory=_uuid,
            )
            runtime = Schema3PackageImportRecoveryService(
                collection=CoinCollection(str(collection_path)),
                journals=journals,
                snapshots=raw,
                processed_snapshots=processed,
                images=ManagedCollectionImageStore(root_path / "images"),
                publisher=DurableCollectionPublisher(collection_path),
                cleanup=cleanup,
                terminal=terminal,
                clock=lambda: "2026-07-23T12:00:05Z",
                token_factory=_uuid,
            )
            first = runtime.recover_locked(current, lock)
            second = runtime.recover_locked(first, lock)
            record = runtime.recover_locked(second, lock)
            self.assertEqual(record.result, ImportResult.ROLLED_BACK)
            lock.release()

            unified = UnifiedPackageImportRecoveryService(
                lock_path=lock_path,
                journals=VersionedPackageImportJournalRepository(
                    journals.root
                ),
                schema1_terminal=TerminalPersistenceService(
                    Schema2PackageImportJournalRepository(journals.root),
                    root_path / "legacy-history",
                    clock=lambda: "2026-07-23T12:00:06Z",
                    token_factory=_uuid,
                ),
                schema2_snapshots=raw,
                schema3_snapshots=processed,
                schema3_terminal=terminal,
                recover_schema2_locked=lambda _head, _lock: None,
                schema3_runtime=runtime,
            )
            final_path = root_path / "history" / f"{head.import_id}.json"
            before = final_path.read_bytes()
            self.assertEqual(unified.reconcile_pending_imports(), ())
            self.assertEqual(unified.reconcile_pending_imports(), ())
            self.assertEqual(final_path.read_bytes(), before)

    def test_pa_rm33_rollback_and_cancel_terminal_recovery_is_inert(self):
        for result in (ImportResult.ROLLED_BACK, ImportResult.CANCELLED):
            with self.subTest(result=result.value), tempfile.TemporaryDirectory() as root:
                root_path = Path(root)
                head = _generation()
                lock = PackageImportLock.acquire(
                    Path(tempfile.gettempdir()) / f"{_uuid()}.lock",
                    import_id=head.import_id,
                )
                try:
                    journals = Schema3PackageImportJournalRepository(
                        root_path / "journals"
                    )
                    current = journals.create(head, import_lock=lock)
                    current = journals.append(
                        current,
                        _successor(
                            current,
                            phase=ImportPhase.ROLLING_BACK,
                            pending_terminal_audit=_non_success_audit(
                                current, result
                            ),
                        ),
                        import_lock=lock,
                    )
                    cleanup = Schema3CleanupProtocol(
                        journals,
                        _ReceiptExecutor(),
                        clock=lambda: "2026-07-23T12:00:03Z",
                        token_factory=_uuid,
                    )
                    current = cleanup.begin_rollback(
                        current,
                        targets=(
                            _target(
                                current,
                                "processed/root",
                                "PROCESSED_SNAPSHOT",
                            ),
                            _target(current, "raw/package", "SNAPSHOT"),
                        ),
                        import_lock=lock,
                    )
                    current = cleanup.advance(
                        current, import_lock=lock
                    )
                    current = cleanup.release_processed_reference(
                        current, import_lock=lock
                    )
                    current = cleanup.complete(
                        current, import_lock=lock
                    )
                    terminal = Schema3TerminalPersistenceService(
                        journals,
                        root_path / "history",
                        clock=lambda: "2026-07-23T12:00:04Z",
                        token_factory=_uuid,
                    )
                    if result is ImportResult.ROLLED_BACK:
                        real_rename = (
                            terminal_persistence
                            .rename_entry_no_replace_in_directory
                        )

                        def crash_before_final(
                            directory, source_name, target_name
                        ):
                            if source_name.startswith(".pending-"):
                                raise OSError(
                                    "simulated crash before final history"
                                )
                            return real_rename(
                                directory, source_name, target_name
                            )

                        with patch.object(
                            terminal_persistence,
                            "rename_entry_no_replace_in_directory",
                            side_effect=crash_before_final,
                        ):
                            with self.assertRaises(OSError):
                                terminal.compact(
                                    current,
                                    result=result,
                                    error_category="ROLLED_BACK",
                                    import_lock=lock,
                                )
                        self.assertFalse(
                            (journals.root / current.import_id).exists()
                        )
                        self.assertFalse(
                            (
                                journals.root
                                / f".retire-{current.import_id}"
                            ).exists()
                        )
                        record = terminal.resume_pending(
                            current.import_id, import_lock=lock
                        )
                    else:
                        record = terminal.compact(
                            current,
                            result=result,
                            error_category=None,
                            import_lock=lock,
                        )
                    self.assertEqual(
                        record.processed_media_proof.outcome, "REMOVED"
                    )
                    final_path = (
                        root_path
                        / "history"
                        / f"{current.import_id}.json"
                    )
                    before = final_path.read_bytes()
                    self.assertEqual(terminal.list_final(), (record,))
                    self.assertEqual(final_path.read_bytes(), before)
                finally:
                    lock.release()


if __name__ == "__main__":
    unittest.main()
