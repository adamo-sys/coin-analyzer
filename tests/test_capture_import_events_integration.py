"""Integration tests for event emission in transaction and recovery services."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coin_collection import CoinCollection

from capture_import.baseline import capture_collection_baseline
from capture_import.enums import ImportPhase, ImportResult
from capture_import.events import EventType, ImportEventBus
from capture_import.image_store import ManagedCollectionImageStore
from capture_import.journal_repository import PackageImportJournalRepository
from capture_import.package import CapturePackageValidator
from capture_import.preview import PackageImportPreviewBuilder
from capture_import.recovery import PackageImportRecoveryService
from capture_import.snapshot import CapturePackageSnapshotService
from capture_import.transaction import PackageImportTransactionService
from tests.capture_package_fixtures import package_bytes

NOW = "2026-07-21T12:00:00Z"
IMPORT_ID = "11111111-1111-4111-8111-111111111111"
DESKTOP_ID = "22222222-2222-4222-8222-222222222222"
OWNER_TOKEN = "33333333-3333-4333-8333-333333333333"
SNAPSHOT_TOKEN = "e" * 64


class TransactionEventIntegrationTests(unittest.TestCase):
    """Prove that PackageImportTransactionService emits structured events."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.collection_path = self.root / "data" / "collection.json"
        self.package_path = self.root / "matrix.ca-package"
        self.payload = package_bytes()
        self.package_path.write_bytes(self.payload)
        self.collection = CoinCollection(str(self.collection_path))
        self.snapshot_root = self.root / "data" / "imports" / "snapshots"
        self.snapshots = CapturePackageSnapshotService(
            self.snapshot_root,
            token_factory=lambda: SNAPSHOT_TOKEN,
            clock=lambda: NOW,
        )
        self.snapshot = self.snapshots.create_snapshot(
            self.package_path, sha256(self.payload).hexdigest()
        )
        self.package = CapturePackageValidator().validate_snapshot(
            self.snapshot, self.package_path.name
        )
        self.preview = PackageImportPreviewBuilder().build(
            self.package, capture_collection_baseline(self.collection_path)
        )
        self.journals = PackageImportJournalRepository(
            self.root / "data" / "imports" / "journals"
        )
        self.images = ManagedCollectionImageStore(
            self.root / "coin_photos" / "collection"
        )
        self.event_bus = ImportEventBus(clock=lambda: NOW)
        identifiers = iter((IMPORT_ID, DESKTOP_ID))
        self.transaction = PackageImportTransactionService(
            self.collection,
            lock_path=self.root / "data" / "imports" / "package_import.lock",
            journal_repository=self.journals,
            image_store=self.images,
            clock=lambda: NOW,
            identifier_factory=lambda: next(identifiers),
            ownership_token_factory=lambda: OWNER_TOKEN,
            event_bus=self.event_bus,
        )

    def tearDown(self) -> None:
        if self.snapshot.is_active:
            try:
                self.snapshot.cleanup()
            except Exception:
                pass
        self.temporary.cleanup()

    def _execute(self):
        return self.transaction.execute(
            self.snapshot, self.package, self.preview, self.preview.decisions
        )

    def test_successful_import_emits_full_event_sequence(self) -> None:
        result = self._execute()
        self.assertEqual(result.status, ImportResult.SUCCEEDED)
        events = self.event_bus.events
        types = [e.event_type for e in events]
        self.assertIn(EventType.IMPORT_STARTED, types)
        self.assertIn(EventType.PACKAGE_VALIDATED, types)
        self.assertIn(EventType.COLLECTION_CREATED, types)
        self.assertIn(EventType.IMAGES_IMPORTED, types)
        self.assertIn(EventType.COLLECTION_COMMITTED, types)
        self.assertIn(EventType.IMPORT_COMPLETE, types)

        started = self.event_bus.by_type(EventType.IMPORT_STARTED)[0]
        self.assertEqual(started.context["package_basename"], self.package_path.name)

        completed = self.event_bus.by_type(EventType.IMPORT_COMPLETE)[0]
        self.assertEqual(completed.context["status"], "SUCCEEDED")
        self.assertEqual(completed.context["imported_count"], 1)

    def test_rollback_emits_rollback_events(self) -> None:
        """Use OSError (caught by Exception) to trigger the rollback path."""
        original = self.journals.create

        def create_then_crash(entry):
            original(entry)
            raise OSError("injected crash after journal creation")

        with patch.object(self.journals, "create", side_effect=create_then_crash):
            with self.assertRaises(Exception):
                self._execute()

        if self.snapshot.is_active:
            self.snapshot.preserve_for_recovery()

        types = [e.event_type for e in self.event_bus.events]
        self.assertIn(EventType.IMPORT_STARTED, types)
        self.assertIn(EventType.PACKAGE_VALIDATED, types)
        self.assertIn(EventType.ROLLBACK_STARTED, types)
        self.assertIn(EventType.ROLLBACK_COMPLETE, types)

        started = self.event_bus.by_type(EventType.ROLLBACK_STARTED)[0]
        self.assertEqual(started.severity.value, "WARNING")
        self.assertIn("injected crash", started.context["reason"])

    def test_cancellation_emits_cancelled_event(self) -> None:
        cancelled = [False]

        def check_cancelled():
            return cancelled[0]

        self.transaction._is_cancelled = check_cancelled
        # Cancel after journal is created (inside the lock)
        original_create = self.journals.create

        def create_and_cancel(entry):
            result = original_create(entry)
            cancelled[0] = True
            return result

        with patch.object(self.journals, "create", side_effect=create_and_cancel):
            with self.assertRaises(Exception):
                self._execute()

        types = [e.event_type for e in self.event_bus.events]
        self.assertIn(EventType.IMPORT_STARTED, types)
        self.assertIn(EventType.CANCELLED, types)

        cancelled_event = self.event_bus.by_type(EventType.CANCELLED)[0]
        self.assertEqual(cancelled_event.context["reason"], "cancelled by caller")


class RecoveryEventIntegrationTests(unittest.TestCase):
    """Prove that PackageImportRecoveryService emits structured events."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.collection_path = self.root / "data" / "collection.json"
        self.package_path = self.root / "matrix.ca-package"
        self.payload = package_bytes()
        self.package_path.write_bytes(self.payload)
        self.collection = CoinCollection(str(self.collection_path))
        self.snapshot_root = self.root / "data" / "imports" / "snapshots"
        self.snapshots = CapturePackageSnapshotService(
            self.snapshot_root,
            token_factory=lambda: SNAPSHOT_TOKEN,
            clock=lambda: NOW,
        )
        self.snapshot = self.snapshots.create_snapshot(
            self.package_path, sha256(self.payload).hexdigest()
        )
        self.package = CapturePackageValidator().validate_snapshot(
            self.snapshot, self.package_path.name
        )
        self.preview = PackageImportPreviewBuilder().build(
            self.package, capture_collection_baseline(self.collection_path)
        )
        self.journals = PackageImportJournalRepository(
            self.root / "data" / "imports" / "journals"
        )
        self.images = ManagedCollectionImageStore(
            self.root / "coin_photos" / "collection"
        )
        self.event_bus = ImportEventBus(clock=lambda: NOW)
        identifiers = iter((IMPORT_ID, DESKTOP_ID))
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
            try:
                self.snapshot.cleanup()
            except Exception:
                pass
        self.temporary.cleanup()

    def test_recovery_from_files_ready_emits_triggered_and_complete(self) -> None:
        original = self.journals.update
        crashed = False

        def crash_after_files_ready(previous, current):
            nonlocal crashed
            result = original(previous, current)
            if not crashed and current.phase is ImportPhase.FILES_READY:
                crashed = True
                raise OSError("crash after FILES_READY")
            return result

        with patch.object(self.journals, "update", side_effect=crash_after_files_ready):
            with self.assertRaises(Exception):
                self.transaction.execute(
                    self.snapshot, self.package, self.preview, self.preview.decisions
                )

        if self.snapshot.is_active:
            self.snapshot.preserve_for_recovery()

        recovery = PackageImportRecoveryService(
            collection_path=self.collection_path,
            lock_path=self.root / "data" / "imports" / "package_import.lock",
            journals=self.journals,
            snapshots=CapturePackageSnapshotService(self.snapshot_root),
            images=self.images,
            clock=lambda: NOW,
            event_bus=self.event_bus,
        )

        recovery.reconcile_pending_imports()

        types = [e.event_type for e in self.event_bus.events]
        self.assertIn(EventType.RECOVERY_TRIGGERED, types)
        self.assertIn(EventType.RECOVERY_COMPLETE, types)

        triggered = self.event_bus.by_type(EventType.RECOVERY_TRIGGERED)[0]
        self.assertEqual(triggered.context["journal_phase"], "FILES_READY")

        completed = self.event_bus.by_type(EventType.RECOVERY_COMPLETE)[0]
        self.assertEqual(completed.context["final_phase"], "ROLLED_BACK")


if __name__ == "__main__":
    unittest.main()
