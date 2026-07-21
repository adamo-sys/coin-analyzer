"""Focused Sprint 5 import execution and compensation tests."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from coin_collection import CoinCollection, CoinItem, PhotoRole
from coin_collection_gui import CoinCollectionGUI

from capture_import.baseline import capture_collection_baseline
from capture_import.decisions import ImportDecisionModel
from capture_import.enums import DuplicateDecision, ImportPhase, ImportResult
from capture_import.errors import (
    CollectionChanged,
    CollectionCommitFailed,
    ImageCollision,
    JournalCorrupt,
    PackageChanged,
    RecoveryRequired,
    SnapshotRecoveryRequired,
)
from capture_import.image_store import ManagedCollectionImageStore
from capture_import.journal_repository import PackageImportJournalRepository
from capture_import.lock import PackageImportLock
from capture_import.package import CapturePackageValidator
from capture_import.preview import PackageImportPreviewBuilder
from capture_import.recovery import PackageImportRecoveryService
from capture_import.snapshot import CapturePackageSnapshotService
from capture_import.transaction import PackageImportTransactionService
from capture_import.durable_repository import Schema2PackageImportJournalRepository
from capture_import.schema2_runtime import Schema2PackageImportTransactionService
from capture_import.schema2_runtime import Schema2PackageImportRecoveryService
from capture_import.terminal_persistence import TerminalPersistenceService
from tests.capture_package_fixtures import package_bytes

NOW = "2026-07-19T12:00:00Z"
IMPORT_ID = "11111111-1111-4111-8111-111111111111"
DESKTOP_ID = "22222222-2222-4222-8222-222222222222"
OWNER_TOKEN = "33333333-3333-4333-8333-333333333333"
SNAPSHOT_TOKEN = "a" * 64


class CapturePackageExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.collection_path = self.root / "data" / "collection.json"
        self.package_path = self.root / "show.ca-package"
        self.payload = package_bytes()
        self.package_path.write_bytes(self.payload)
        self.collection = CoinCollection(str(self.collection_path))
        self.snapshot_service = CapturePackageSnapshotService(
            self.root / "data" / "imports" / "snapshots",
            token_factory=lambda: SNAPSHOT_TOKEN,
            clock=lambda: NOW,
        )
        self.snapshot = self.snapshot_service.create_snapshot(
            self.package_path, sha256(self.payload).hexdigest()
        )
        self.package = CapturePackageValidator().validate_snapshot(
            self.snapshot, self.package_path.name
        )
        self.preview = PackageImportPreviewBuilder().build(
            self.package, capture_collection_baseline(self.collection_path)
        )
        identifiers = iter((IMPORT_ID, DESKTOP_ID))
        self.journals = PackageImportJournalRepository(
            self.root / "data" / "imports" / "journals"
        )
        self.images = ManagedCollectionImageStore(
            self.root / "coin_photos" / "collection"
        )
        self.transaction = PackageImportTransactionService(
            self.collection,
            lock_path=self.root / "data" / "imports" / "package_import.lock",
            journal_repository=self.journals,
            image_store=self.images,
            clock=lambda: NOW,
            identifier_factory=lambda: next(identifiers),
            ownership_token_factory=lambda: OWNER_TOKEN,
        )

    def tearDown(self) -> None:
        if self.snapshot.is_active:
            self.snapshot.cleanup()
        self.temporary.cleanup()

    def test_successful_import_is_durable_and_audited(self) -> None:
        result = self.transaction.execute(
            self.snapshot, self.package, self.preview, self.preview.decisions
        )

        self.assertIs(result.status, ImportResult.SUCCEEDED)
        self.assertEqual(result.imported_count, 1)
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(result.image_count, 2)
        self.assertFalse(self.snapshot.is_active)
        reloaded = CoinCollection(str(self.collection_path))
        self.assertEqual(len(reloaded.items), 1)
        item = reloaded.items[0]
        self.assertEqual(item.id, DESKTOP_ID)
        self.assertEqual(item.quantity, 1)
        self.assertEqual(
            tuple(photo.role for photo in item.photos),
            (PhotoRole.FRONT, PhotoRole.BACK),
        )
        self.package_path.unlink()
        for photo in item.photos:
            self.assertFalse(Path(photo.path).is_absolute())
            absolute = self.root / Path(photo.path)
            self.assertTrue(absolute.is_file())
        journal = self.journals.load(IMPORT_ID)
        self.assertIs(journal.phase, ImportPhase.SUCCEEDED)
        self.assertIsNotNone(journal.terminal_audit)
        self.assertIsNone(journal.snapshot_relative_path)
        self.assertFalse(journal.cleanup_pending)

    def test_schema2_runtime_is_privacy_complete_after_success(self) -> None:
        identifiers = iter((DESKTOP_ID,))

        def identifier() -> str:
            return next(identifiers, str(uuid4()))

        journals = Schema2PackageImportJournalRepository(
            self.root / "data" / "imports" / "schema2-journals"
        )
        transaction = Schema2PackageImportTransactionService(
            self.collection,
            lock_path=self.root / "data" / "imports" / "package_import.lock",
            journals=journals,
            history_root=self.root / "data" / "imports" / "history",
            snapshots=self.snapshot_service,
            image_store=self.images,
            clock=lambda: NOW,
            identifier_factory=identifier,
            ownership_token_factory=lambda: OWNER_TOKEN,
        )

        with PackageImportLock.acquire(
            self.root / "data" / "imports" / "package_import.lock",
            import_id=IMPORT_ID,
        ) as import_lock:
            result = transaction.execute(
                self.snapshot,
                self.package,
                self.preview,
                self.preview.decisions,
                import_id=IMPORT_ID,
                import_lock=import_lock,
            )

        self.assertIs(result.status, ImportResult.SUCCEEDED)
        self.assertFalse((journals.root / IMPORT_ID).exists())
        terminal = (
            self.root / "data" / "imports" / "history" / f"{IMPORT_ID}.json"
        )
        self.assertTrue(terminal.is_file())
        self.assertNotIn(SNAPSHOT_TOKEN, terminal.read_text(encoding="utf-8"))
        self.assertEqual(
            CoinCollection(str(self.collection_path)).items[0].id,
            DESKTOP_ID,
        )

    def test_schema2_startup_recovery_finishes_committed_import(self) -> None:
        identifiers = iter((DESKTOP_ID,))

        def identifier() -> str:
            return next(identifiers, str(uuid4()))

        journals = Schema2PackageImportJournalRepository(
            self.root / "data" / "imports" / "schema2-journals"
        )
        history = self.root / "data" / "imports" / "history"
        lock_path = self.root / "data" / "imports" / "package_import.lock"
        transaction = Schema2PackageImportTransactionService(
            self.collection,
            lock_path=lock_path,
            journals=journals,
            history_root=history,
            snapshots=self.snapshot_service,
            image_store=self.images,
            clock=lambda: NOW,
            identifier_factory=identifier,
            ownership_token_factory=lambda: OWNER_TOKEN,
        )
        with PackageImportLock.acquire(
            lock_path,
            import_id=IMPORT_ID,
        ) as import_lock, patch.object(
            transaction,
            "_cleanup_snapshot",
            side_effect=KeyboardInterrupt("RM-19 crash before cleanup intent"),
        ):
            with self.assertRaises(KeyboardInterrupt):
                transaction.execute(
                    self.snapshot,
                    self.package,
                    self.preview,
                    self.preview.decisions,
                    import_id=IMPORT_ID,
                    import_lock=import_lock,
                )
        self._abandon_snapshot_lease()
        terminal = TerminalPersistenceService(
            journals,
            history,
            clock=lambda: NOW,
        )
        recovery = Schema2PackageImportRecoveryService(
            lock_path=lock_path,
            journals=journals,
            terminal=terminal,
            snapshots=self.snapshot_service,
            transaction=transaction,
        )

        first = recovery.reconcile_pending_imports()
        second = recovery.reconcile_pending_imports()

        self.assertEqual(len(first), 1)
        self.assertEqual(second, ())
        self.assertTrue((history / f"{IMPORT_ID}.json").is_file())
        self.assertEqual(
            [item.id for item in CoinCollection(str(self.collection_path)).items],
            [DESKTOP_ID],
        )

    def test_schema2_startup_recovery_rolls_back_precommit_images(self) -> None:
        identifiers = iter((DESKTOP_ID,))

        def identifier() -> str:
            return next(identifiers, str(uuid4()))

        journals = Schema2PackageImportJournalRepository(
            self.root / "data" / "imports" / "schema2-journals"
        )
        history = self.root / "data" / "imports" / "history"
        lock_path = self.root / "data" / "imports" / "package_import.lock"
        transaction = Schema2PackageImportTransactionService(
            self.collection,
            lock_path=lock_path,
            journals=journals,
            history_root=history,
            snapshots=self.snapshot_service,
            image_store=self.images,
            clock=lambda: NOW,
            identifier_factory=identifier,
            ownership_token_factory=lambda: OWNER_TOKEN,
        )
        original_append_phase = transaction._append_phase

        def crash_before_files_ready(current, phase, import_lock, **changes):
            if phase is ImportPhase.FILES_READY:
                raise KeyboardInterrupt("RM-15 crash before FILES_READY")
            return original_append_phase(current, phase, import_lock, **changes)

        with PackageImportLock.acquire(
            lock_path,
            import_id=IMPORT_ID,
        ) as import_lock, patch.object(
            transaction,
            "_append_phase",
            side_effect=crash_before_files_ready,
        ):
            with self.assertRaises(KeyboardInterrupt):
                transaction.execute(
                    self.snapshot,
                    self.package,
                    self.preview,
                    self.preview.decisions,
                    import_id=IMPORT_ID,
                    import_lock=import_lock,
                )
        self._abandon_snapshot_lease()
        terminal = TerminalPersistenceService(
            journals,
            history,
            clock=lambda: NOW,
        )
        recovery = Schema2PackageImportRecoveryService(
            lock_path=lock_path,
            journals=journals,
            terminal=terminal,
            snapshots=self.snapshot_service,
            transaction=transaction,
        )

        recovery.reconcile_pending_imports()

        self.assertFalse(self.collection_path.exists())
        self.assertFalse((self.images.root / "imports" / IMPORT_ID).exists())
        self.assertTrue((history / f"{IMPORT_ID}.json").is_file())

    def test_schema2_recovery_resumes_snapshot_cleanup_after_unreceipted_delete(self) -> None:
        identifiers = iter((DESKTOP_ID,))

        def identifier() -> str:
            return next(identifiers, str(uuid4()))

        journals = Schema2PackageImportJournalRepository(
            self.root / "data" / "imports" / "schema2-journals"
        )
        history = self.root / "data" / "imports" / "history"
        lock_path = self.root / "data" / "imports" / "package_import.lock"
        transaction = Schema2PackageImportTransactionService(
            self.collection,
            lock_path=lock_path,
            journals=journals,
            history_root=history,
            snapshots=self.snapshot_service,
            image_store=self.images,
            clock=lambda: NOW,
            identifier_factory=identifier,
            ownership_token_factory=lambda: OWNER_TOKEN,
        )
        original_remove = transaction._cleanup.remove
        interrupted = False

        def interrupt_after_package_delete(target, **kwargs):
            nonlocal interrupted
            result = original_remove(target, **kwargs)
            if target.relative_path.endswith("/package.ca-package") and not interrupted:
                interrupted = True
                raise KeyboardInterrupt("RM-20.c after durable absence")
            return result

        with PackageImportLock.acquire(
            lock_path,
            import_id=IMPORT_ID,
        ) as import_lock, patch.object(
            transaction._cleanup,
            "remove",
            side_effect=interrupt_after_package_delete,
        ):
            with self.assertRaises(KeyboardInterrupt):
                transaction.execute(
                    self.snapshot,
                    self.package,
                    self.preview,
                    self.preview.decisions,
                    import_id=IMPORT_ID,
                    import_lock=import_lock,
                )
        recovery = Schema2PackageImportRecoveryService(
            lock_path=lock_path,
            journals=journals,
            terminal=TerminalPersistenceService(
                journals,
                history,
                clock=lambda: NOW,
            ),
            snapshots=self.snapshot_service,
            transaction=transaction,
        )

        recovery.reconcile_pending_imports()

        self.assertTrue(interrupted)
        self.assertFalse((self.snapshot_service.root / SNAPSHOT_TOKEN).exists())
        self.assertTrue((history / f"{IMPORT_ID}.json").is_file())

    def test_schema2_recovery_recognizes_exact_post_publication_bytes(self) -> None:
        identifiers = iter((DESKTOP_ID,))

        def identifier() -> str:
            return next(identifiers, str(uuid4()))

        journals = Schema2PackageImportJournalRepository(
            self.root / "data" / "imports" / "schema2-journals"
        )
        history = self.root / "data" / "imports" / "history"
        lock_path = self.root / "data" / "imports" / "package_import.lock"
        transaction = Schema2PackageImportTransactionService(
            self.collection,
            lock_path=lock_path,
            journals=journals,
            history_root=history,
            snapshots=self.snapshot_service,
            image_store=self.images,
            clock=lambda: NOW,
            identifier_factory=identifier,
            ownership_token_factory=lambda: OWNER_TOKEN,
        )
        original_append_phase = transaction._append_phase

        def crash_before_collection_outcome(current, phase, import_lock, **changes):
            if phase is ImportPhase.COLLECTION_COMMITTED:
                raise KeyboardInterrupt("RM-18 before collection outcome generation")
            return original_append_phase(current, phase, import_lock, **changes)

        with PackageImportLock.acquire(
            lock_path,
            import_id=IMPORT_ID,
        ) as import_lock, patch.object(
            transaction,
            "_append_phase",
            side_effect=crash_before_collection_outcome,
        ):
            with self.assertRaises(KeyboardInterrupt):
                transaction.execute(
                    self.snapshot,
                    self.package,
                    self.preview,
                    self.preview.decisions,
                    import_id=IMPORT_ID,
                    import_lock=import_lock,
                )
        self._abandon_snapshot_lease()
        recovery = Schema2PackageImportRecoveryService(
            lock_path=lock_path,
            journals=journals,
            terminal=TerminalPersistenceService(
                journals,
                history,
                clock=lambda: NOW,
            ),
            snapshots=self.snapshot_service,
            transaction=transaction,
        )

        recovery.reconcile_pending_imports()

        self.assertEqual(
            [item.id for item in CoinCollection(str(self.collection_path)).items],
            [DESKTOP_ID],
        )
        self.assertTrue((history / f"{IMPORT_ID}.json").is_file())

    def test_collection_failure_rolls_back_images_snapshot_and_journal(self) -> None:
        with patch.object(
            self.collection, "replace_items_for_import", return_value=False
        ):
            with self.assertRaises(CollectionCommitFailed):
                self.transaction.execute(
                    self.snapshot,
                    self.package,
                    self.preview,
                    self.preview.decisions,
                )

        self.assertFalse(self.collection_path.exists())
        self.assertFalse(self.snapshot.is_active)
        self.assertFalse(
            (self.images.root / "imports" / IMPORT_ID).exists()
        )
        journal = self.journals.load(IMPORT_ID)
        self.assertIs(journal.phase, ImportPhase.ROLLED_BACK)
        self.assertEqual(journal.created_relative_paths, ())
        self.assertIsNotNone(journal.terminal_audit)

    def test_journal_create_is_exclusive(self) -> None:
        # Exercise the real transaction up to a durable terminal journal first.
        self.transaction.execute(
            self.snapshot, self.package, self.preview, self.preview.decisions
        )
        existing = self.journals.load(IMPORT_ID)
        duplicate = replace(
            existing,
            phase=ImportPhase.PREPARED,
            snapshot_relative_path=f"{SNAPSHOT_TOKEN}/package.ca-package",
            created_relative_paths=(),
            committed_collection_item_ids=(),
            imported_count=0,
            cleanup_pending=False,
            audit_finalization_pending=False,
            terminal_audit=None,
        )
        with self.assertRaises(JournalCorrupt):
            self.journals.create(duplicate)

    def test_stale_collection_baseline_fails_before_durable_import_state(self) -> None:
        self.collection_path.write_bytes(b"[]\n")

        with self.assertRaises(CollectionChanged):
            self.transaction.execute(
                self.snapshot, self.package, self.preview, self.preview.decisions
            )

        self.assertEqual(self.collection_path.read_bytes(), b"[]\n")
        self.assertEqual(self.journals.list_entries(), ())
        self.assertFalse(self.snapshot.is_active)
        self.assertFalse((self.images.root / "imports" / IMPORT_ID).exists())

    def test_all_skip_performs_no_collection_image_or_journal_mutation(self) -> None:
        decisions = ImportDecisionModel.apply(
            self.preview,
            self.preview.decisions,
            "coin-1",
            DuplicateDecision.SKIP,
        )

        result = self.transaction.execute(
            self.snapshot, self.package, self.preview, decisions
        )

        self.assertEqual(result.imported_count, 0)
        self.assertEqual(result.skipped_count, 1)
        self.assertFalse(self.collection_path.exists())
        self.assertEqual(self.journals.list_entries(), ())
        self.assertFalse(self.snapshot.is_active)

    def test_import_root_collision_is_preserved_and_reported(self) -> None:
        collision = self.images.root / "imports" / IMPORT_ID
        collision.mkdir(parents=True)
        sentinel = collision / "collector-owned.txt"
        sentinel.write_bytes(b"do not delete")

        with self.assertRaises(ImageCollision):
            self.transaction.execute(
                self.snapshot, self.package, self.preview, self.preview.decisions
            )

        self.assertEqual(sentinel.read_bytes(), b"do not delete")
        self.assertFalse(self.collection_path.exists())
        self.assertIs(self.journals.load(IMPORT_ID).phase, ImportPhase.ROLLED_BACK)

    def test_restart_recovery_rolls_back_complete_uncommitted_images(self) -> None:
        original_update = self.journals.update

        def crash_before_files_ready(previous, current):
            if current.phase is ImportPhase.FILES_READY:
                raise KeyboardInterrupt("simulated process crash")
            return original_update(previous, current)

        with patch.object(self.journals, "update", side_effect=crash_before_files_ready):
            with self.assertRaises(KeyboardInterrupt):
                self.transaction.execute(
                    self.snapshot,
                    self.package,
                    self.preview,
                    self.preview.decisions,
                )
        self._abandon_snapshot_lease()

        recovered = self._recovery().reconcile_pending_imports()

        self.assertEqual(len(recovered), 1)
        self.assertIs(recovered[0].phase, ImportPhase.ROLLED_BACK)
        self.assertFalse(self.collection_path.exists())
        self.assertFalse((self.images.root / "imports" / IMPORT_ID).exists())

    def test_restart_recovery_finalizes_commit_without_duplicate_records(self) -> None:
        original_update = self.journals.update

        def crash_after_collection_write(previous, current):
            if current.phase is ImportPhase.COLLECTION_COMMITTED:
                raise KeyboardInterrupt("simulated process crash")
            return original_update(previous, current)

        with patch.object(self.journals, "update", side_effect=crash_after_collection_write):
            with self.assertRaises(KeyboardInterrupt):
                self.transaction.execute(
                    self.snapshot,
                    self.package,
                    self.preview,
                    self.preview.decisions,
                )
        self._abandon_snapshot_lease()

        first = self._recovery().reconcile_pending_imports()
        second = self._recovery().reconcile_pending_imports()

        self.assertEqual(first[0].phase, ImportPhase.SUCCEEDED)
        self.assertEqual(second, ())
        reloaded = CoinCollection(str(self.collection_path))
        self.assertEqual([item.id for item in reloaded.items], [DESKTOP_ID])

    def test_reserved_desktop_id_collision_fails_before_durable_state(self) -> None:
        existing = self._existing_item(DESKTOP_ID)
        self.collection.items = [existing]
        self.assertTrue(self.collection.save_collection())
        preview = PackageImportPreviewBuilder().build(
            self.package, capture_collection_baseline(self.collection_path)
        )

        with self.assertRaises(CollectionCommitFailed):
            self.transaction.execute(
                self.snapshot, self.package, preview, preview.decisions
            )

        reloaded = CoinCollection(str(self.collection_path))
        self.assertEqual([item.to_dict() for item in reloaded.items], [existing.to_dict()])
        self.assertEqual(self.journals.list_entries(), ())
        self.assertFalse((self.images.root / "imports" / IMPORT_ID).exists())

    def test_recovery_rejects_unrelated_record_using_reserved_id(self) -> None:
        existing = self._existing_item(DESKTOP_ID)
        self.collection.items = [existing]
        self.assertTrue(self.collection.save_collection())
        preview = PackageImportPreviewBuilder().build(
            self.package, capture_collection_baseline(self.collection_path)
        )
        plan = self.images.plan(
            self.package,
            import_id=IMPORT_ID,
            ownership_token=OWNER_TOKEN,
            source_to_desktop={"coin-1": DESKTOP_ID},
        )
        journal = self.transaction._new_journal(
            self.snapshot,
            self.package,
            preview,
            plan,
            ("coin-1",),
            (DESKTOP_ID,),
            NOW,
        )
        journal = self.journals.create(journal)
        journal = self.journals.update(
            journal, replace(journal, phase=ImportPhase.COPYING_IMAGES)
        )
        journal = self.journals.update(
            journal,
            replace(
                journal,
                created_relative_paths=plan.expected_relative_paths,
            ),
        )
        journal = self.journals.update(
            journal, replace(journal, phase=ImportPhase.FILES_READY)
        )
        self.journals.update(
            journal, replace(journal, phase=ImportPhase.COMMITTING_COLLECTION)
        )
        self._abandon_snapshot_lease()

        with self.assertRaises(RecoveryRequired):
            self._recovery().reconcile_pending_imports()

        self.assertIs(self.journals.load(IMPORT_ID).phase, ImportPhase.RECOVERY_REQUIRED)
        reloaded = CoinCollection(str(self.collection_path))
        self.assertEqual([item.to_dict() for item in reloaded.items], [existing.to_dict()])

    def test_snapshot_is_revalidated_under_lock_before_journal_creation(self) -> None:
        with patch(
            "capture_import.transaction.CapturePackageValidator.validate_snapshot",
            side_effect=(self.package, PackageChanged()),
        ):
            with self.assertRaises(PackageChanged):
                self.transaction.execute(
                    self.snapshot,
                    self.package,
                    self.preview,
                    self.preview.decisions,
                )

        self.assertEqual(self.journals.list_entries(), ())
        self.assertFalse((self.images.root / "imports" / IMPORT_ID).exists())
        self.assertFalse(self.snapshot.is_active)

    def test_startup_recovery_reconciles_before_import_is_enabled(self) -> None:
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.app = SimpleNamespace(collection=self.collection)
        recovery = Mock()
        coordinator = object()
        with patch(
            "coin_collection_gui.build_default_import_services",
            return_value=(recovery, coordinator),
        ):
            self.assertTrue(gui.initialize_capture_import_recovery())

        recovery.reconcile_pending_imports.assert_called_once_with()
        self.assertTrue(gui.capture_import_ready)
        self.assertEqual(gui.capture_import_menu_state(), "normal")
        self.assertIs(gui.capture_import_coordinator, coordinator)

    def test_startup_recovery_failure_keeps_import_disabled(self) -> None:
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.app = SimpleNamespace(collection=self.collection)
        recovery = Mock()
        recovery.reconcile_pending_imports.side_effect = RecoveryRequired()
        with patch(
            "coin_collection_gui.build_default_import_services",
            return_value=(recovery, object()),
        ):
            self.assertFalse(gui.initialize_capture_import_recovery())

        self.assertFalse(gui.capture_import_ready)
        self.assertEqual(gui.capture_import_menu_state(), "disabled")
        self.assertEqual(
            gui.capture_import_recovery_message,
            RecoveryRequired().safe_message,
        )

    def test_startup_recovery_removes_only_proven_orphan_snapshot(self) -> None:
        orphan_root = self.root / "orphan-snapshots"
        creator = CapturePackageSnapshotService(
            orphan_root,
            token_factory=lambda: "b" * 64,
            clock=lambda: NOW,
            process_id=999999,
            hostname="test-host",
            process_is_live=lambda process_id: False,
        )
        orphan = creator.create_snapshot(
            self.package_path, sha256(self.payload).hexdigest()
        )
        orphan.preserve_for_recovery()
        cleanup_service = CapturePackageSnapshotService(
            orphan_root,
            hostname="test-host",
            process_is_live=lambda process_id: False,
        )
        recovery = PackageImportRecoveryService(
            collection_path=self.collection_path,
            lock_path=self.root / "orphan-import.lock",
            journals=PackageImportJournalRepository(self.root / "orphan-journals"),
            snapshots=cleanup_service,
            images=self.images,
            clock=lambda: NOW,
        )

        self.assertEqual(recovery.reconcile_pending_imports(), ())
        self.assertFalse((orphan_root / ("b" * 64)).exists())
        self.assertEqual(recovery.reconcile_pending_imports(), ())

    def test_unprovable_orphan_blocks_startup_and_preserves_evidence(self) -> None:
        orphan_root = self.root / "unprovable-snapshots"
        directory = orphan_root / ("c" * 64)
        directory.mkdir(parents=True)
        evidence = directory / "unexpected.txt"
        evidence.write_bytes(b"preserve")
        recovery = PackageImportRecoveryService(
            collection_path=self.collection_path,
            lock_path=self.root / "unprovable-import.lock",
            journals=PackageImportJournalRepository(self.root / "unprovable-journals"),
            snapshots=CapturePackageSnapshotService(orphan_root),
            images=self.images,
            clock=lambda: NOW,
        )

        with self.assertRaises(SnapshotRecoveryRequired):
            recovery.reconcile_pending_imports()

        self.assertEqual(evidence.read_bytes(), b"preserve")

    def test_journal_created_before_lock_acquisition_is_recovered_same_pass(self) -> None:
        plan = self.images.plan(
            self.package,
            import_id=IMPORT_ID,
            ownership_token=OWNER_TOKEN,
            source_to_desktop={"coin-1": DESKTOP_ID},
        )
        pending = self.transaction._new_journal(
            self.snapshot,
            self.package,
            self.preview,
            plan,
            ("coin-1",),
            (DESKTOP_ID,),
            NOW,
        )
        self._abandon_snapshot_lease()
        recovery = self._recovery()
        real_acquire = PackageImportLock.acquire

        @contextmanager
        def acquire_after_journal_creation():
            with real_acquire(
                self.root / "data" / "imports" / "package_import.lock"
            ) as held:
                self.journals.create(pending)
                yield held

        with patch.object(
            PackageImportLock,
            "acquire",
            side_effect=lambda *args, **kwargs: acquire_after_journal_creation(),
        ):
            recovered = recovery.reconcile_pending_imports()

        self.assertEqual(len(recovered), 1)
        self.assertIs(recovered[0].phase, ImportPhase.ROLLED_BACK)
        self.assertFalse(
            (self.root / "data" / "imports" / "snapshots" / SNAPSHOT_TOKEN).exists()
        )

    def test_unleased_orphan_with_live_recorded_pid_blocks_startup(self) -> None:
        orphan_root = self.root / "live-pid-snapshots"
        creator = CapturePackageSnapshotService(
            orphan_root,
            token_factory=lambda: "d" * 64,
            clock=lambda: NOW,
            process_id=424242,
            hostname="test-host",
            process_is_live=lambda process_id: True,
        )
        orphan = creator.create_snapshot(
            self.package_path, sha256(self.payload).hexdigest()
        )
        orphan.preserve_for_recovery()
        cleanup_service = CapturePackageSnapshotService(
            orphan_root,
            hostname="test-host",
            process_is_live=lambda process_id: True,
        )

        with self.assertRaises(SnapshotRecoveryRequired):
            with PackageImportLock.acquire(
                self.root / "live-pid-import.lock"
            ) as import_lock:
                cleanup_service.cleanup_orphaned_snapshots(
                    (),
                    import_lock=import_lock,
                )

        directory = orphan_root / ("d" * 64)
        self.assertTrue(directory.is_dir())
        self.assertTrue((directory / "package.ca-package").is_file())
        self.assertTrue((directory / "snapshot-owner.json").is_file())

    def test_cross_midnight_commit_and_recovery_share_journal_date(self) -> None:
        before_midnight = "2026-07-19T23:59:59Z"
        after_midnight = "2026-07-20T00:00:01Z"
        clock_calls = 0

        def crossing_clock() -> str:
            nonlocal clock_calls
            clock_calls += 1
            return before_midnight if clock_calls == 1 else after_midnight

        identifiers = iter((IMPORT_ID, DESKTOP_ID))
        transaction = PackageImportTransactionService(
            self.collection,
            lock_path=self.root / "data" / "imports" / "package_import.lock",
            journal_repository=self.journals,
            image_store=self.images,
            clock=crossing_clock,
            identifier_factory=lambda: next(identifiers),
            ownership_token_factory=lambda: OWNER_TOKEN,
        )
        original_update = self.journals.update

        def crash_after_collection_write(previous, current):
            if current.phase is ImportPhase.COLLECTION_COMMITTED:
                raise KeyboardInterrupt("simulated cross-midnight crash")
            return original_update(previous, current)

        with patch.object(self.journals, "update", side_effect=crash_after_collection_write):
            with self.assertRaises(KeyboardInterrupt):
                transaction.execute(
                    self.snapshot,
                    self.package,
                    self.preview,
                    self.preview.decisions,
                )
        self._abandon_snapshot_lease()
        committed = CoinCollection(str(self.collection_path))
        self.assertEqual(committed.items[0].date_added, "2026-07-19")

        recovered = self._recovery().reconcile_pending_imports()

        self.assertIs(recovered[0].phase, ImportPhase.SUCCEEDED)
        reloaded = CoinCollection(str(self.collection_path))
        self.assertEqual(reloaded.items[0].date_added, "2026-07-19")

    def _abandon_snapshot_lease(self) -> None:
        self.snapshot.preserve_for_recovery()

    def _recovery(self) -> PackageImportRecoveryService:
        return PackageImportRecoveryService(
            collection_path=self.collection_path,
            lock_path=self.root / "data" / "imports" / "package_import.lock",
            journals=self.journals,
            snapshots=CapturePackageSnapshotService(
                self.root / "data" / "imports" / "snapshots"
            ),
            images=self.images,
            clock=lambda: NOW,
        )

    @staticmethod
    def _existing_item(identifier: str) -> CoinItem:
        return CoinItem(
            id=identifier,
            image_path="collector-owned.jpg",
            country="Unrelated",
            denomination="Record",
            year="1900",
            grade="VF",
            notes="must remain unchanged",
            date_added="2020-01-01",
        )


if __name__ == "__main__":
    unittest.main()
