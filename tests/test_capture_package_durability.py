"""Focused Sprint 5B filesystem durability and cleanup-ordering tests."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from atomic_json import write_json_atomically
from coin_collection import CoinCollection

from capture_import._advisory import release_advisory_lock
from capture_import.baseline import capture_collection_baseline
from capture_import._filesystem import (
    delete_open_file,
    open_existing_binary_for_delete,
    path_object_identity,
)
from capture_import.enums import ImportPhase
from capture_import.errors import (
    CaptureImportError,
    ImageCopyFailed,
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
from tests.capture_package_fixtures import package_bytes

NOW = "2026-07-19T12:00:00Z"
IMPORT_ID = "11111111-1111-4111-8111-111111111111"
DESKTOP_ID = "22222222-2222-4222-8222-222222222222"
OWNER_TOKEN = "33333333-3333-4333-8333-333333333333"
SNAPSHOT_TOKEN = "a" * 64


class _TransformingHandle:
    def __init__(self, handle, transform):
        self._handle = handle
        self._transform = transform

    def write(self, payload):
        return self._handle.write(self._transform(payload))

    def __getattr__(self, name):
        return getattr(self._handle, name)


class CapturePackageDurabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.collection_path = self.root / "data" / "collection.json"
        self.package_path = self.root / "show.ca-package"
        self.payload = package_bytes()
        self.package_path.write_bytes(self.payload)
        self.collection = CoinCollection(str(self.collection_path))
        self.snapshot_root = self.root / "data" / "imports" / "snapshots"
        self.snapshot_service = CapturePackageSnapshotService(
            self.snapshot_root,
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
        self.journals = PackageImportJournalRepository(
            self.root / "data" / "imports" / "journals"
        )
        self.images = ManagedCollectionImageStore(
            self.root / "coin_photos" / "collection"
        )
        self.transaction = self._transaction()

    def tearDown(self) -> None:
        if self.snapshot.is_active:
            self.snapshot.cleanup()
        self.temporary.cleanup()

    def test_same_length_persisted_corruption_blocks_files_ready(self) -> None:
        real_open = self._image_open_function()
        phases: list[ImportPhase] = []
        original_update = self.journals.update

        def corrupting_open(path):
            handle = real_open(path)
            if Path(path).stem == "front":
                return _TransformingHandle(
                    handle,
                    lambda payload: bytes([payload[0] ^ 1]) + payload[1:],
                )
            return handle

        def record_update(previous, current):
            phases.append(current.phase)
            return original_update(previous, current)

        with patch(
            "capture_import.image_store.open_exclusive_binary",
            side_effect=corrupting_open,
        ), patch.object(self.journals, "update", side_effect=record_update):
            with self.assertRaises(ImageCopyFailed):
                self._execute()

        self.assertNotIn(ImportPhase.FILES_READY, phases)
        self.assertIs(self.journals.load(IMPORT_ID).phase, ImportPhase.ROLLED_BACK)

    def test_short_persisted_write_blocks_files_ready(self) -> None:
        real_open = self._image_open_function()

        def short_open(path):
            handle = real_open(path)
            if Path(path).stem == "front":
                return _TransformingHandle(handle, lambda payload: payload[:-1])
            return handle

        with patch(
            "capture_import.image_store.open_exclusive_binary",
            side_effect=short_open,
        ):
            with self.assertRaises(ImageCopyFailed):
                self._execute()

        self.assertIs(self.journals.load(IMPORT_ID).phase, ImportPhase.ROLLED_BACK)

    def test_destination_pathname_replacement_is_detected(self) -> None:
        from capture_import import image_store as image_store_module

        real_matches = image_store_module.handle_matches_path
        replaced = False

        def replace_before_identity_check(handle, path):
            nonlocal replaced
            path = Path(path)
            if path.stem == "front" and not replaced:
                replaced = True
                displaced = path.with_name(path.name + ".displaced")
                path.rename(displaced)
                path.write_bytes(b"replacement")
            return real_matches(handle, path)

        with patch(
            "capture_import.image_store.handle_matches_path",
            side_effect=replace_before_identity_check,
        ):
            with PackageImportLock.acquire(
                self.root / "direct-image.lock",
                import_id=IMPORT_ID,
            ) as import_lock:
                with self.assertRaises(ImageCopyFailed):
                    self.images.copy(
                        self.snapshot,
                        self.package,
                        self._plan(),
                        lambda relative_path: None,
                        import_lock=import_lock,
                    )

        self.assertTrue(replaced)
        replacement = (
            self.images.root
            / "imports"
            / IMPORT_ID
            / DESKTOP_ID
            / next(
                image.managed_relative_path.rsplit("/", 1)[-1]
                for image in self._plan().media
                if image.role.value == "front"
            )
        )
        self.assertTrue(
            replacement.is_file(),
            [str(path) for path in self.images.root.rglob("*")],
        )
        self.assertEqual(replacement.read_bytes(), b"replacement")
        with PackageImportLock.acquire(
            self.root / "direct-image.lock",
            import_id=IMPORT_ID,
        ) as import_lock:
            with self.assertRaises(RecoveryRequired):
                self.images.cleanup(
                    self._plan(),
                    import_lock=import_lock,
                )
        self.assertEqual(replacement.read_bytes(), b"replacement")

    def test_journal_parent_replacement_fails_closed(self) -> None:
        plan = self._plan()
        journal = self.transaction._new_journal(
            self.snapshot,
            self.package,
            self.preview,
            plan,
            ("coin-1",),
            (DESKTOP_ID,),
            NOW,
        )
        journal = self.journals.create(journal)
        displaced = self.journals.root.with_name("journals-displaced")

        def replace_parent(path, payload, **kwargs):
            self.journals.root.rename(displaced)
            self.journals.root.mkdir()
            write_json_atomically(path, payload, **kwargs)

        self.journals._atomic_writer = replace_parent
        with self.assertRaises(RecoveryRequired):
            self.journals.update(
                journal, replace(journal, phase=ImportPhase.COPYING_IMAGES)
            )

        self.assertTrue(self.journals.root.is_dir())
        if os.name == "nt":
            self.assertFalse(displaced.exists())
            self.assertEqual(self.journals.load(IMPORT_ID), journal)
        else:
            self.assertTrue(displaced.is_dir())
            self.assertEqual(tuple(self.journals.root.iterdir()), ())

    def test_journal_replacement_after_enumeration_fails_closed(self) -> None:
        plan = self._plan()
        journal = self.journals.create(
            self.transaction._new_journal(
                self.snapshot,
                self.package,
                self.preview,
                plan,
                ("coin-1",),
                (DESKTOP_ID,),
                NOW,
            )
        )
        original_load = self.journals._load_bound
        replaced = False

        def replace_before_load(import_id, directory):
            nonlocal replaced
            if not replaced:
                replaced = True
                path = self.journals.root / f"{IMPORT_ID}.json"
                replacement = path.with_suffix(".replacement")
                replacement.write_bytes(path.read_bytes())
                os.replace(replacement, path)
            return original_load(import_id, directory)

        with patch.object(self.journals, "_load_bound", side_effect=replace_before_load):
            with self.assertRaises(Exception):
                self.journals.list_entries()
        self.assertTrue(replaced)
        self.assertEqual(self.journals.load(IMPORT_ID), journal)

    @unittest.skipIf(os.name == "nt", "POSIX atomic exchange regression")
    def test_posix_journal_substitution_before_exchange_is_preserved(self) -> None:
        plan = self._plan()
        journal = self.journals.create(
            self.transaction._new_journal(
                self.snapshot,
                self.package,
                self.preview,
                plan,
                ("coin-1",),
                (DESKTOP_ID,),
                NOW,
            )
        )
        current = replace(journal, phase=ImportPhase.COPYING_IMAGES)
        journal_path = self.journals.root / f"{IMPORT_ID}.json"
        original_exchange = __import__(
            "capture_import.journal_repository", fromlist=["exchange_paths_in_directory"]
        ).exchange_paths_in_directory
        substituted_identity = None

        def substitute_then_exchange(directory, first, second):
            nonlocal substituted_identity
            if substituted_identity is None:
                replacement = self.journals.root / ".equal-byte-replacement"
                replacement.write_bytes(journal_path.read_bytes())
                os.replace(replacement, journal_path)
                info = journal_path.lstat()
                substituted_identity = (info.st_dev, info.st_ino)
            return original_exchange(directory, first, second)

        with patch(
            "capture_import.journal_repository.exchange_paths_in_directory",
            side_effect=substitute_then_exchange,
        ):
            with self.assertRaises(RecoveryRequired):
                self.journals.update(journal, current)
        info = journal_path.lstat()
        self.assertEqual((info.st_dev, info.st_ino), substituted_identity)
        self.assertEqual(self.journals.load(IMPORT_ID), journal)

    @unittest.skipIf(os.name == "nt", "POSIX atomic exchange regression")
    def test_posix_failed_restore_preserves_substituted_journal(self) -> None:
        plan = self._plan()
        journal = self.journals.create(
            self.transaction._new_journal(
                self.snapshot,
                self.package,
                self.preview,
                plan,
                ("coin-1",),
                (DESKTOP_ID,),
                NOW,
            )
        )
        current = replace(journal, phase=ImportPhase.COPYING_IMAGES)
        journal_path = self.journals.root / f"{IMPORT_ID}.json"
        original_payload = journal_path.read_bytes()
        original_exchange = __import__(
            "capture_import.journal_repository", fromlist=["exchange_paths_in_directory"]
        ).exchange_paths_in_directory
        calls = 0
        substituted_identity = None

        def exchange_then_fail_restore(directory, first, second):
            nonlocal calls, substituted_identity
            calls += 1
            if calls == 1:
                replacement = self.journals.root / ".equal-byte-replacement"
                replacement.write_bytes(original_payload)
                os.replace(replacement, journal_path)
                info = journal_path.lstat()
                substituted_identity = (info.st_dev, info.st_ino)
                return original_exchange(directory, first, second)
            raise OSError("simulated restoration failure")

        with patch(
            "capture_import.journal_repository.exchange_paths_in_directory",
            side_effect=exchange_then_fail_restore,
        ):
            with self.assertRaises(RecoveryRequired):
                self.journals.update(journal, current)
        preserved = tuple(self.journals.root.glob(".*.tmp"))
        self.assertEqual(len(preserved), 1)
        info = preserved[0].lstat()
        self.assertEqual((info.st_dev, info.st_ino), substituted_identity)
        self.assertEqual(preserved[0].read_bytes(), original_payload)

    def test_success_crash_before_snapshot_cleanup_remains_preterminal(self) -> None:
        with patch.object(
            self.snapshot,
            "cleanup",
            side_effect=KeyboardInterrupt("before snapshot deletion"),
        ):
            with self.assertRaises(KeyboardInterrupt):
                self._execute()
        self.snapshot.preserve_for_recovery()
        pending = self.journals.load(IMPORT_ID)
        self.assertIs(pending.phase, ImportPhase.COLLECTION_COMMITTED)
        self.assertFalse(pending.cleanup_pending)
        self.assertIsNotNone(pending.snapshot_relative_path)

        recovered = self._recovery(dead_process=True).reconcile_pending_imports()

        self.assertEqual(len(recovered), 1)
        self.assertIs(recovered[0].phase, ImportPhase.SUCCEEDED)
        self.assertFalse((self.snapshot_root / SNAPSHOT_TOKEN).exists())

    def test_success_crash_after_snapshot_cleanup_never_exposes_terminal_state(self) -> None:
        original_cleanup = self.snapshot.cleanup

        def delete_then_crash():
            original_cleanup()
            raise KeyboardInterrupt("after snapshot deletion")

        with patch.object(self.snapshot, "cleanup", side_effect=delete_then_crash):
            with self.assertRaises(KeyboardInterrupt):
                self._execute()
        pending = self.journals.load(IMPORT_ID)
        self.assertIs(pending.phase, ImportPhase.COLLECTION_COMMITTED)
        self.assertIsNotNone(pending.snapshot_relative_path)
        self.assertIsNone(pending.terminal_audit)
        self.assertFalse((self.snapshot_root / SNAPSHOT_TOKEN).exists())

        with self.assertRaises(SnapshotRecoveryRequired):
            self._recovery(dead_process=True).reconcile_pending_imports()

    def test_success_crash_during_snapshot_cleanup_remains_preterminal(self) -> None:
        def partially_delete_then_crash():
            self.assertIs(
                self.journals.load(IMPORT_ID).phase,
                ImportPhase.COLLECTION_COMMITTED,
            )
            (self.snapshot_root / SNAPSHOT_TOKEN / "snapshot-owner.json").unlink()
            raise KeyboardInterrupt("during snapshot deletion")

        with patch.object(
            self.snapshot, "cleanup", side_effect=partially_delete_then_crash
        ):
            with self.assertRaises(KeyboardInterrupt):
                self._execute()
        release_advisory_lock(self.snapshot._lease_handle)
        self.snapshot._lease_handle.close()
        self.snapshot._cleaned = True
        pending = self.journals.load(IMPORT_ID)
        self.assertIs(pending.phase, ImportPhase.COLLECTION_COMMITTED)
        self.assertIsNone(pending.terminal_audit)
        with self.assertRaises(SnapshotRecoveryRequired):
            self._recovery(dead_process=True).reconcile_pending_imports()

    def test_rollback_snapshot_cleanup_precedes_terminal_state(self) -> None:
        original_cleanup = self.snapshot.cleanup

        def assert_preterminal_then_delete():
            self.assertIs(
                self.journals.load(IMPORT_ID).phase,
                ImportPhase.ROLLING_BACK,
            )
            original_cleanup()

        with patch.object(self.collection, "replace_items_for_import", return_value=False), patch.object(
            self.snapshot, "cleanup", side_effect=assert_preterminal_then_delete
        ):
            with self.assertRaises(Exception):
                self._execute()

        self.assertIs(self.journals.load(IMPORT_ID).phase, ImportPhase.ROLLED_BACK)
        self.assertFalse((self.snapshot_root / SNAPSHOT_TOKEN).exists())

    def test_managed_image_replacement_after_inventory_is_rejected(self) -> None:
        plan = self._plan()
        with PackageImportLock.acquire(
            self.root / "direct-image.lock",
            import_id=IMPORT_ID,
        ) as import_lock:
            self.images.copy(
                self.snapshot,
                self.package,
                plan,
                lambda _relative_path: None,
                import_lock=import_lock,
            )
        target = next(
            self.images.root.joinpath(*Path(image.managed_relative_path).parts)
            for image in plan.media
            if image.role.value == "front"
        )
        original_open = __import__(
            "capture_import.image_store", fromlist=["open_existing_binary_for_delete"]
        ).open_existing_binary_for_delete
        replaced = False

        def replace_before_open(path):
            nonlocal replaced
            if Path(path) == target and not replaced:
                replaced = True
                replacement = target.with_suffix(".replacement")
                replacement.write_bytes(target.read_bytes())
                os.replace(replacement, target)
            return original_open(path)

        with patch(
            "capture_import.image_store.open_existing_binary_for_delete",
            side_effect=replace_before_open,
        ):
            with self.assertRaises(RecoveryRequired):
                self.images.verify(plan)
        self.assertTrue(replaced)

    @unittest.skipUnless(os.name == "nt", "Windows reparse-point policy")
    def test_windows_reparse_substitution_is_rejected(self) -> None:
        target = self.root / "real-file.bin"
        target.write_bytes(b"data")
        substituted = self.root / "substituted.bin"
        try:
            os.symlink(target, substituted)
        except OSError as error:
            self.skipTest(f"Windows symbolic links unavailable: {error}")
        with self.assertRaises(OSError):
            path_object_identity(substituted)

        directory_target = self.root / "real-directory"
        directory_target.mkdir()
        directory_substitution = self.root / "substituted-directory"
        os.symlink(directory_target, directory_substitution, target_is_directory=True)
        with self.assertRaises(OSError):
            path_object_identity(directory_substitution)

    @unittest.skipUnless(os.name == "nt", "Windows reparse race policy")
    def test_windows_reparse_swap_between_check_and_open_is_rejected(self) -> None:
        target = self.root / "validated-file.bin"
        target.write_bytes(b"validated")
        attacker_target = self.root / "attacker-file.bin"
        attacker_target.write_bytes(b"attacker")
        try:
            probe = self.root / "symlink-probe"
            os.symlink(attacker_target, probe)
            probe.unlink()
        except OSError as error:
            self.skipTest(f"Windows symbolic links unavailable: {error}")

        module = __import__(
            "capture_import._filesystem", fromlist=["_open_windows_binary"]
        )
        original_open = module._open_windows_binary
        swapped = False

        def swap_before_native_open(path, **kwargs):
            nonlocal swapped
            if Path(path) == target and not swapped:
                swapped = True
                target.unlink()
                os.symlink(attacker_target, target)
            return original_open(path, **kwargs)

        with patch(
            "capture_import._filesystem._open_windows_binary",
            side_effect=swap_before_native_open,
        ):
            with self.assertRaises(OSError):
                open_existing_binary_for_delete(target)
        self.assertTrue(swapped)
        self.assertTrue(target.is_symlink())

    @unittest.skipIf(os.name == "nt", "POSIX read-only delete-open policy")
    def test_posix_delete_open_accepts_read_only_regular_file(self) -> None:
        target = self.root / "read-only-delete.bin"
        target.write_bytes(b"verified bytes")
        target.chmod(0o400)

        with open_existing_binary_for_delete(target) as handle:
            self.assertEqual(handle.read(), b"verified bytes")
            delete_open_file(handle, target)

        self.assertFalse(target.exists())

    def test_preterminal_missing_snapshot_fails_recovery_deterministically(self) -> None:
        original_update = self.journals.update

        def crash_before_files_ready(previous, current):
            if current.phase is ImportPhase.FILES_READY:
                raise KeyboardInterrupt("preterminal crash")
            return original_update(previous, current)

        with patch.object(self.journals, "update", side_effect=crash_before_files_ready):
            with self.assertRaises(KeyboardInterrupt):
                self._execute()
        self.snapshot.preserve_for_recovery()
        resumed = CapturePackageSnapshotService(self.snapshot_root).resume_snapshot(
            f"{SNAPSHOT_TOKEN}/package.ca-package",
            sha256(self.payload).hexdigest(),
            len(self.payload),
        )
        resumed.cleanup()

        with self.assertRaises(SnapshotRecoveryRequired):
            self._recovery(dead_process=True).reconcile_pending_imports()
        with self.assertRaises(SnapshotRecoveryRequired):
            self._recovery(dead_process=True).reconcile_pending_imports()

    def _execute(self):
        return self.transaction.execute(
            self.snapshot,
            self.package,
            self.preview,
            self.preview.decisions,
        )

    def _transaction(self):
        identifiers = iter((IMPORT_ID, DESKTOP_ID))
        return PackageImportTransactionService(
            self.collection,
            lock_path=self.root / "data" / "imports" / "package_import.lock",
            journal_repository=self.journals,
            image_store=self.images,
            clock=lambda: NOW,
            identifier_factory=lambda: next(identifiers),
            ownership_token_factory=lambda: OWNER_TOKEN,
        )

    def _plan(self):
        return self.images.plan(
            self.package,
            import_id=IMPORT_ID,
            ownership_token=OWNER_TOKEN,
            source_to_desktop={"coin-1": DESKTOP_ID},
        )

    def _recovery(self, *, dead_process: bool):
        return PackageImportRecoveryService(
            collection_path=self.collection_path,
            lock_path=self.root / "data" / "imports" / "package_import.lock",
            journals=self.journals,
            snapshots=CapturePackageSnapshotService(
                self.snapshot_root,
                process_is_live=(lambda process_id: not dead_process),
            ),
            images=self.images,
            clock=lambda: NOW,
        )

    @staticmethod
    def _image_open_function():
        from capture_import import image_store as image_store_module

        return image_store_module.open_exclusive_binary


if __name__ == "__main__":
    unittest.main()
