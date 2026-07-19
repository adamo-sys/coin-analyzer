"""Focused tests for the exclusive package-import lock lease."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import math
import os
from pathlib import Path
import tempfile
import unittest

from capture_import.errors import ImportLocked, RecoveryRequired
from capture_import.limits import IMPORT_LOCK_SCHEMA_VERSION, MAX_LOCK_WAIT_SECONDS
from capture_import.lock import LockMetadata, PackageImportLock

NOW = "2026-07-18T12:00:00Z"
TOKEN = "a" * 64
IMPORT_ID = "11111111-1111-4111-8111-111111111111"


class PackageImportLockTests(unittest.TestCase):
    def acquire(self, path: Path) -> PackageImportLock:
        return PackageImportLock.acquire(
            path,
            import_id=IMPORT_ID,
            clock=lambda: NOW,
            token_factory=lambda: TOKEN,
            process_id=1234,
            hostname="test-host",
        )

    def test_lock_metadata_round_trip_is_strict_and_immutable(self) -> None:
        metadata = LockMetadata(
            IMPORT_LOCK_SCHEMA_VERSION,
            1234,
            "test-host",
            NOW,
            TOKEN,
            IMPORT_ID,
        )
        self.assertEqual(LockMetadata.from_dict(metadata.to_dict()), metadata)
        with self.assertRaises(FrozenInstanceError):
            metadata.hostname = "changed"  # type: ignore[misc]
        for payload in (
            {**metadata.to_dict(), "unknown": True},
            {key: value for key, value in metadata.to_dict().items() if key != "hostname"},
            {**metadata.to_dict(), "random_lock_token": "unsafe"},
            {**metadata.to_dict(), "process_id": True},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    LockMetadata.from_dict(payload)

    def test_acquire_writes_exact_metadata_and_release_deletes_owned_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "imports" / "package_import.lock"
            lease = self.acquire(path)
            try:
                self.assertTrue(lease.is_held)
                self.assertEqual(lease.verify_ownership(), lease.metadata)
            finally:
                lease.release()
            self.assertFalse(path.exists())
            self.assertFalse(lease.is_held)
            lease.release()

    def test_context_manager_releases_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "package_import.lock"
            with self.acquire(path):
                self.assertTrue(path.exists())
            self.assertFalse(path.exists())

    def test_contention_is_non_destructive_and_never_clears_existing_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "package_import.lock"
            first = self.acquire(path)
            try:
                with self.assertRaises(ImportLocked):
                    self.acquire(path)
                self.assertTrue(first.is_held)
                self.assertEqual(first.verify_ownership(), first.metadata)
            finally:
                first.release()

    def test_preexisting_uncertain_lock_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "package_import.lock"
            path.write_text("stale-or-hostile", encoding="utf-8")
            with self.assertRaises(ImportLocked):
                self.acquire(path)
            self.assertEqual(path.read_text(encoding="utf-8"), "stale-or-hostile")

    def test_release_requires_exact_on_disk_token_and_preserves_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "package_import.lock"
            lease = self.acquire(path)
            hostile = {**lease.metadata.to_dict(), "random_lock_token": "b" * 64}
            from capture_import._json import canonical_json_bytes

            lease._handle.seek(0)
            lease._handle.truncate()
            lease._handle.write(canonical_json_bytes(hostile))
            lease._handle.flush()
            with self.assertRaises(RecoveryRequired):
                lease.release()
            self.assertTrue(path.exists())
            self.assertNotIn(str(path), str(RecoveryRequired(path)))
            path.unlink()

    def test_release_never_deletes_a_replacement_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "package_import.lock"
            moved = Path(temporary) / "original.lock"
            lease = self.acquire(path)
            try:
                os.replace(path, moved)
            except PermissionError:
                lease.release()
                self.assertFalse(path.exists())
                return
            path.write_text("replacement", encoding="utf-8")
            with self.assertRaises(RecoveryRequired):
                lease.release()
            self.assertEqual(path.read_text(encoding="utf-8"), "replacement")
            self.assertTrue(moved.exists())
            path.unlink()
            moved.unlink()

    def test_wait_arguments_are_bounded_and_typed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "package_import.lock"
            for kwargs in (
                {"wait_seconds": -1},
                {"wait_seconds": True},
                {"wait_seconds": math.nan},
                {"wait_seconds": math.inf},
                {"wait_seconds": -math.inf},
                {"wait_seconds": 10**1000},
                {"wait_seconds": MAX_LOCK_WAIT_SECONDS + 0.001},
                {"poll_seconds": 0},
                {"poll_seconds": True},
                {"poll_seconds": math.nan},
                {"poll_seconds": math.inf},
            ):
                with self.subTest(kwargs=kwargs):
                    with self.assertRaises(ValueError):
                        PackageImportLock.acquire(path, **kwargs)
            lease = PackageImportLock.acquire(
                path,
                wait_seconds=MAX_LOCK_WAIT_SECONDS,
                clock=lambda: NOW,
                token_factory=lambda: TOKEN,
                process_id=1234,
                hostname="test-host",
            )
            lease.release()
