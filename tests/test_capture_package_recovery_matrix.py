"""Systematic crash/restart matrix for the capture-package transaction engine."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coin_collection import CoinCollection

from capture_import.baseline import capture_collection_baseline
from capture_import.enums import ImportPhase
from capture_import.errors import RecoveryRequired, SnapshotRecoveryRequired
from capture_import.image_store import ManagedCollectionImageStore
from capture_import.journal_repository import PackageImportJournalRepository
from capture_import.package import CapturePackageValidator
from capture_import.preview import PackageImportPreviewBuilder
from capture_import.recovery import PackageImportRecoveryService
from capture_import.snapshot import CapturePackageSnapshotService
from capture_import.transaction import PackageImportTransactionService
from tests.capture_package_fixtures import package_bytes

NOW = "2026-07-19T12:00:00Z"
IMPORT_ID = "11111111-1111-4111-8111-111111111111"
DESKTOP_ID = "22222222-2222-4222-8222-222222222222"
OWNER_TOKEN = "33333333-3333-4333-8333-333333333333"
SNAPSHOT_TOKEN = "e" * 64


class CapturePackageRecoveryMatrixTests(unittest.TestCase):
    """Inject crashes at durable boundaries and prove deterministic restart."""

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

    def test_before_journal_creation_has_no_durable_side_effects(self) -> None:
        with patch.object(
            self.journals,
            "create",
            side_effect=KeyboardInterrupt("before journal creation"),
        ):
            with self.assertRaises(KeyboardInterrupt):
                self._execute()
        self.assertEqual(self.journals.list_entries(), ())
        self.assertFalse(self.collection_path.exists())
        self.assertFalse((self.images.root / "imports" / IMPORT_ID).exists())

    def test_after_journal_creation_recovers_to_stable_rollback(self) -> None:
        original = self.journals.create

        def create_then_crash(entry):
            original(entry)
            raise KeyboardInterrupt("after journal creation")

        with patch.object(self.journals, "create", side_effect=create_then_crash):
            with self.assertRaises(KeyboardInterrupt):
                self._execute()
        self._abandon_snapshot()
        self._assert_recovery(ImportPhase.ROLLED_BACK)

    def test_during_journal_update_rolls_back_deterministically(self) -> None:
        original = self.journals._write_bound
        failed = False

        def fail_once(*args, **kwargs):
            nonlocal failed
            if not failed:
                failed = True
                raise OSError("injected journal persistence failure")
            return original(*args, **kwargs)

        with patch.object(self.journals, "_write_bound", side_effect=fail_once):
            with self.assertRaises(RecoveryRequired):
                self._execute()
        self.assertTrue(failed)
        self.assertIs(self.journals.load(IMPORT_ID).phase, ImportPhase.ROLLED_BACK)

    def test_after_copying_images_transition_recovers_to_rollback(self) -> None:
        self._crash_after_update(lambda current: current.phase is ImportPhase.COPYING_IMAGES)
        self._assert_recovery(ImportPhase.ROLLED_BACK)

    def test_after_first_managed_image_recovers_without_orphans(self) -> None:
        self._crash_after_update(
            lambda current: current.phase is ImportPhase.COPYING_IMAGES
            and any(path.lower().endswith((".jpg", ".jpeg", ".png")) for path in current.created_relative_paths)
        )
        self._assert_recovery(ImportPhase.ROLLED_BACK)

    def test_after_all_managed_images_before_files_ready_recovers(self) -> None:
        self._crash_after_update(
            lambda current: current.phase is ImportPhase.COPYING_IMAGES
            and current.created_relative_paths == current.expected_relative_paths
        )
        self._assert_recovery(ImportPhase.ROLLED_BACK)

    def test_after_files_ready_before_metadata_recovers_to_rollback(self) -> None:
        self._crash_after_update(lambda current: current.phase is ImportPhase.FILES_READY)
        self._assert_recovery(ImportPhase.ROLLED_BACK)

    def test_after_committing_collection_before_metadata_recovers_to_rollback(self) -> None:
        self._crash_after_update(
            lambda current: current.phase is ImportPhase.COMMITTING_COLLECTION
            and not current.committed_collection_item_ids
        )
        self._assert_recovery(ImportPhase.ROLLED_BACK)

    def test_during_metadata_persistence_recovers_without_duplicates(self) -> None:
        original = self.collection.replace_items_for_import

        def persist_then_crash(*args, **kwargs):
            result = original(*args, **kwargs)
            self.assertTrue(result)
            raise KeyboardInterrupt("during metadata persistence")

        with patch.object(
            self.collection,
            "replace_items_for_import",
            side_effect=persist_then_crash,
        ):
            with self.assertRaises(KeyboardInterrupt):
                self._execute()
        self._abandon_snapshot()
        self._assert_recovery(ImportPhase.SUCCEEDED, expected_collection_ids=(DESKTOP_ID,))

    def test_after_collection_committed_recovers_without_duplicates(self) -> None:
        self._crash_after_update(
            lambda current: current.phase is ImportPhase.COLLECTION_COMMITTED
        )
        self._assert_recovery(ImportPhase.SUCCEEDED, expected_collection_ids=(DESKTOP_ID,))

    def test_interrupted_recovery_resumes_idempotently(self) -> None:
        self._crash_after_update(lambda current: current.phase is ImportPhase.FILES_READY)
        recovery = self._recovery()
        original = self.journals.update
        crashed = False

        def interrupt_rolling_back(previous, current):
            nonlocal crashed
            result = original(previous, current)
            if current.phase is ImportPhase.ROLLING_BACK and not crashed:
                crashed = True
                raise KeyboardInterrupt("interrupted recovery")
            return result

        with patch.object(
            self.journals, "update", side_effect=interrupt_rolling_back
        ):
            with self.assertRaises(KeyboardInterrupt):
                recovery.reconcile_pending_imports()
        self.assertTrue(crashed)
        resumed = CapturePackageSnapshotService(self.snapshot_root).resume_snapshot(
            f"{SNAPSHOT_TOKEN}/package.ca-package",
            sha256(self.payload).hexdigest(),
            len(self.payload),
        )
        resumed.preserve_for_recovery()
        self._assert_recovery(ImportPhase.ROLLED_BACK)

    def test_repeated_interrupted_recovery_has_stable_evidence(self) -> None:
        self._crash_after_update(lambda current: current.phase is ImportPhase.FILES_READY)
        for attempt in range(2):
            recovery = self._recovery()
            original = self.journals.update
            crashed = False

            def interrupt_recovery(previous, current):
                nonlocal crashed
                result = original(previous, current)
                if not crashed and current.phase in {
                    ImportPhase.RECOVERY_REQUIRED,
                    ImportPhase.ROLLING_BACK,
                }:
                    crashed = True
                    raise KeyboardInterrupt(f"interrupted recovery {attempt}")
                return result

            with patch.object(self.journals, "update", side_effect=interrupt_recovery):
                with self.assertRaises(KeyboardInterrupt):
                    recovery.reconcile_pending_imports()
            self.assertTrue(crashed)
        self._assert_recovery(ImportPhase.ROLLED_BACK)

    def test_terminal_success_is_stable_under_repeated_recovery(self) -> None:
        self._execute()
        first = self._recovery().reconcile_pending_imports()
        second = self._recovery().reconcile_pending_imports()
        self.assertEqual(first, second)
        self.assertEqual(first, ())
        self.assertEqual(self._collection_ids(), (DESKTOP_ID,))

    def test_repeated_recovery_after_rollback_is_byte_stable(self) -> None:
        """RM-24: Run recovery twice after rollback — second is a no-op."""
        self._crash_after_update(lambda current: current.phase is ImportPhase.FILES_READY)
        first = self._recovery().reconcile_pending_imports()
        self.assertEqual(len(first), 1)
        self.assertIs(first[0].phase, ImportPhase.ROLLED_BACK)
        stable = self.journals.load(IMPORT_ID)
        for _ in range(2):
            subsequent = self._recovery().reconcile_pending_imports()
            self.assertEqual(subsequent, ())
            self.assertEqual(self.journals.load(IMPORT_ID), stable)
        self.assertEqual(self._collection_ids(), ())
        self.assertFalse((self.images.root / "imports" / IMPORT_ID).exists())
        self.assertFalse((self.snapshot_root / SNAPSHOT_TOKEN).exists())

    def test_startup_after_success_repeatedly_skips_retained_history(self) -> None:
        """RM-27: Reconcile terminal success repeatedly — no mutation."""
        self._execute()
        self.assertEqual(self._collection_ids(), (DESKTOP_ID,))
        first = self._recovery().reconcile_pending_imports()
        self.assertEqual(first, ())
        stable = self.journals.load(IMPORT_ID)
        for _ in range(3):
            subsequent = self._recovery().reconcile_pending_imports()
            self.assertEqual(subsequent, ())
            self.assertEqual(self.journals.load(IMPORT_ID), stable)
        self.assertEqual(self._collection_ids(), (DESKTOP_ID,))

    def test_startup_after_rollback_repeatedly_skips_retained_history(self) -> None:
        """RM-28: Reconcile terminal rollback repeatedly — no mutation."""
        original = self.journals.create

        def create_then_crash(entry):
            original(entry)
            raise KeyboardInterrupt("after journal creation")

        with patch.object(self.journals, "create", side_effect=create_then_crash):
            with self.assertRaises(KeyboardInterrupt):
                self._execute()
        self._abandon_snapshot()
        first = self._recovery().reconcile_pending_imports()
        self.assertEqual(len(first), 1)
        self.assertIs(first[0].phase, ImportPhase.ROLLED_BACK)
        stable = self.journals.load(IMPORT_ID)
        for _ in range(3):
            subsequent = self._recovery().reconcile_pending_imports()
            self.assertEqual(subsequent, ())
            self.assertEqual(self.journals.load(IMPORT_ID), stable)
        self.assertEqual(self._collection_ids(), ())
        self.assertFalse((self.images.root / "imports" / IMPORT_ID).exists())
        self.assertFalse((self.snapshot_root / SNAPSHOT_TOKEN).exists())

    def test_documented_matrix_has_exactly_41_resolvable_scenarios(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        matrix = repository / "docs" / "DESKTOP_PACKAGE_IMPORT_RECOVERY_MATRIX.md"
        rows = [
            line
            for line in matrix.read_text(encoding="utf-8").splitlines()
            if line.startswith("| RM-")
        ]
        self.assertEqual(len(rows), 41)
        identifiers = [row.split("|")[1].strip() for row in rows]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        references = [row.split("|")[-2].strip().strip("`") for row in rows]
        self.assertEqual(len(references), len(set(references)),
                         "Each RM scenario must have a unique automated test")
        for row in rows:
            reference = row.split("|")[-2].strip().strip("`")
            relative, method = reference.split("::", 1)
            source = repository / relative
            self.assertTrue(source.is_file(), reference)
            self.assertIn(f"def {method}(", source.read_text(encoding="utf-8"))
        repository = Path(__file__).resolve().parents[1]
        matrix = repository / "docs" / "DESKTOP_PACKAGE_IMPORT_RECOVERY_MATRIX.md"
        rows = [
            line
            for line in matrix.read_text(encoding="utf-8").splitlines()
            if line.startswith("| RM-")
        ]
        self.assertGreaterEqual(len(rows), 39)
        identifiers = [row.split("|")[1].strip() for row in rows]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        for row in rows:
            reference = row.split("|")[-2].strip().strip("`")
            relative, method = reference.split("::", 1)
            source = repository / relative
            self.assertTrue(source.is_file(), reference)
            self.assertIn(f"def {method}(", source.read_text(encoding="utf-8"))

    def _execute(self):
        return self.transaction.execute(
            self.snapshot, self.package, self.preview, self.preview.decisions
        )

    def _crash_after_update(self, predicate) -> None:
        original = self.journals.update
        crashed = False

        def update_then_crash(previous, current):
            nonlocal crashed
            result = original(previous, current)
            if not crashed and predicate(current):
                crashed = True
                raise KeyboardInterrupt(f"crash after {current.phase.value}")
            return result

        with patch.object(self.journals, "update", side_effect=update_then_crash):
            with self.assertRaises(KeyboardInterrupt):
                self._execute()
        self.assertTrue(crashed)
        self._abandon_snapshot()

    def _abandon_snapshot(self) -> None:
        if self.snapshot.is_active:
            self.snapshot.preserve_for_recovery()

    def _recovery(self) -> PackageImportRecoveryService:
        return PackageImportRecoveryService(
            collection_path=self.collection_path,
            lock_path=self.root / "data" / "imports" / "package_import.lock",
            journals=self.journals,
            snapshots=CapturePackageSnapshotService(self.snapshot_root),
            images=self.images,
            clock=lambda: NOW,
        )

    def _assert_recovery(
        self,
        phase: ImportPhase,
        *,
        expected_collection_ids: tuple[str, ...] = (),
    ) -> None:
        first = self._recovery().reconcile_pending_imports()
        self.assertEqual(len(first), 1)
        self.assertIs(first[0].phase, phase)
        stable = self.journals.load(IMPORT_ID)
        second = self._recovery().reconcile_pending_imports()
        self.assertEqual(second, ())
        self.assertEqual(self.journals.load(IMPORT_ID), stable)
        self.assertEqual(self._collection_ids(), expected_collection_ids)
        import_root = self.images.root / "imports" / IMPORT_ID
        if phase is ImportPhase.SUCCEEDED:
            self.assertTrue(import_root.is_dir())
            collection = CoinCollection(str(self.collection_path))
            referenced = [
                self.root / Path(photo.path)
                for item in collection.items
                for photo in item.photos
            ]
            self.assertTrue(referenced)
            self.assertTrue(all(path.is_file() for path in referenced))
        else:
            self.assertFalse(import_root.exists())
        self.assertFalse((self.snapshot_root / SNAPSHOT_TOKEN).exists())

    def _collection_ids(self) -> tuple[str, ...]:
        if not self.collection_path.exists():
            return ()
        return tuple(item.id for item in CoinCollection(str(self.collection_path)).items)


if __name__ == "__main__":
    unittest.main()
