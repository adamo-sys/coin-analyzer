"""Focused tests for immutable capture-package snapshots."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

from capture_import.errors import (
    PackageChanged,
    PackageNotFound,
    PackageTooLarge,
    SnapshotFailed,
    SnapshotRecoveryRequired,
)
from capture_import.limits import SNAPSHOT_SCHEMA_VERSION
from capture_import.snapshot import (
    CapturePackageSnapshotService,
    LEASE_FILENAME,
    OWNER_FILENAME,
    PACKAGE_FILENAME,
    SnapshotDescriptor,
    SnapshotOwner,
)
from capture_import._advisory import acquire_advisory_lock

NOW = "2026-07-18T12:00:00Z"
TOKEN = "c" * 64
PACKAGE_BYTES = b"PK\x03\x04bounded-test-package"
PACKAGE_SHA = hashlib.sha256(PACKAGE_BYTES).hexdigest()


def service(root: Path, **kwargs: object) -> CapturePackageSnapshotService:
    return CapturePackageSnapshotService(
        root,
        clock=lambda: NOW,
        token_factory=lambda: TOKEN,
        process_id=1234,
        hostname="test-host",
        **kwargs,
    )


class SnapshotMetadataTests(unittest.TestCase):
    def test_owner_and_descriptor_are_strict_immutable_contracts(self) -> None:
        owner = SnapshotOwner(SNAPSHOT_SCHEMA_VERSION, "host", 1, NOW, TOKEN)
        self.assertEqual(SnapshotOwner.from_dict(owner.to_dict()), owner)
        descriptor = SnapshotDescriptor(
            TOKEN, f"{TOKEN}/{PACKAGE_FILENAME}", PACKAGE_SHA, len(PACKAGE_BYTES)
        )
        self.assertEqual(SnapshotDescriptor.from_dict(descriptor.to_dict()), descriptor)
        with self.assertRaises(FrozenInstanceError):
            descriptor.byte_length = 1  # type: ignore[misc]
        with self.assertRaises(ValueError):
            SnapshotDescriptor.from_dict({**descriptor.to_dict(), "extra": True})
        with self.assertRaises(ValueError):
            replace(descriptor, relative_path=f"other/{PACKAGE_FILENAME}").validate()


class CapturePackageSnapshotServiceTests(unittest.TestCase):
    def test_create_validate_and_cleanup_owned_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "personal-source-name.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            snapshot_service = service(root, chunk_size=3)
            handle = snapshot_service.create_snapshot(source, PACKAGE_SHA)
            directory = root / TOKEN
            package_path = directory / PACKAGE_FILENAME
            self.assertEqual(handle.descriptor.relative_path, f"{TOKEN}/{PACKAGE_FILENAME}")
            self.assertNotIn(source.name, handle.descriptor.relative_path)
            self.assertEqual(package_path.read_bytes(), PACKAGE_BYTES)
            self.assertEqual(handle.descriptor.byte_length, len(PACKAGE_BYTES))
            self.assertEqual(handle.descriptor.sha256, PACKAGE_SHA)
            self.assertEqual(
                json.loads((directory / OWNER_FILENAME).read_text(encoding="utf-8")),
                handle.owner.to_dict(),
            )
            self.assertTrue((directory / LEASE_FILENAME).is_file())
            try:
                try:
                    contender = (directory / LEASE_FILENAME).open("r+b")
                except PermissionError:
                    contender = None
                if contender is not None:
                    with contender:
                        with self.assertRaises(BlockingIOError):
                            acquire_advisory_lock(contender)
                handle.validate()
            finally:
                handle.cleanup()
            self.assertFalse(directory.exists())
            handle.cleanup()

    def test_digest_mismatch_removes_partial_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            with self.assertRaises(PackageChanged):
                service(root).create_snapshot(source, "0" * 64)
            self.assertEqual(list(root.iterdir()), [])

    def test_missing_empty_and_oversized_sources_fail_without_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "snapshots"
            with self.assertRaises(PackageNotFound):
                service(root).create_snapshot(base / "missing.ca-package", PACKAGE_SHA)
            empty = base / "empty.ca-package"
            empty.write_bytes(b"")
            with self.assertRaises(PackageTooLarge):
                service(root).create_snapshot(empty, hashlib.sha256(b"").hexdigest())
            source = base / "large.ca-package"
            source.write_bytes(b"12345")
            with self.assertRaises(PackageTooLarge):
                service(root, maximum_package_size=4).create_snapshot(
                    source, hashlib.sha256(b"12345").hexdigest()
                )
            self.assertFalse(root.exists())

    def test_injected_package_ceiling_accepts_exact_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "snapshots"
            for index, raw in enumerate((b"1", b"1234")):
                source = base / f"source-{index}.ca-package"
                source.write_bytes(raw)
                snapshot_service = CapturePackageSnapshotService(
                    root,
                    maximum_package_size=4,
                    token_factory=lambda index=index: f"{index + 1:064x}",
                    clock=lambda: NOW,
                    process_id=1234,
                    hostname="test-host",
                )
                handle = snapshot_service.create_snapshot(
                    source, hashlib.sha256(raw).hexdigest()
                )
                self.assertEqual(handle.descriptor.byte_length, len(raw))
                handle.cleanup()

    def test_token_directory_collision_never_reuses_or_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            directory = base / "snapshots" / TOKEN
            directory.mkdir(parents=True)
            marker = directory / "unrelated.txt"
            marker.write_text("preserve", encoding="utf-8")
            with self.assertRaises(SnapshotFailed):
                service(base / "snapshots").create_snapshot(source, PACKAGE_SHA)
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_integrity_change_after_acceptance_is_detected_and_cleanup_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            handle = service(root).create_snapshot(source, PACKAGE_SHA)
            package_path = root / TOKEN / PACKAGE_FILENAME
            package_path.chmod(stat.S_IWRITE | stat.S_IREAD)
            package_path.write_bytes(b"changed")
            with self.assertRaises(PackageChanged):
                handle.validate()
            handle.cleanup()
            self.assertFalse((root / TOKEN).exists())

    def test_revalidation_rejects_growth_before_unbounded_reading(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(b"1234")
            root = base / "snapshots"
            snapshot_service = service(root, maximum_package_size=4, chunk_size=1)
            handle = snapshot_service.create_snapshot(
                source, hashlib.sha256(b"1234").hexdigest()
            )
            package_path = root / TOKEN / PACKAGE_FILENAME
            package_path.chmod(stat.S_IWRITE | stat.S_IREAD)
            package_path.write_bytes(b"12345")
            with self.assertRaises(PackageChanged):
                handle.validate()
            handle.cleanup()

    def test_corrupt_owner_blocks_cleanup_without_broad_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            handle = service(root).create_snapshot(source, PACKAGE_SHA)
            owner_path = root / TOKEN / OWNER_FILENAME
            correct_owner = owner_path.read_bytes()
            owner_path.write_text("{}", encoding="utf-8")
            with self.assertRaises(SnapshotRecoveryRequired):
                handle.cleanup()
            self.assertTrue((root / TOKEN).exists())
            owner_path.write_bytes(correct_owner)
            handle.cleanup()

    def test_unexpected_snapshot_entry_preserves_all_ownership_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            handle = service(root).create_snapshot(source, PACKAGE_SHA)
            directory = root / TOKEN
            unexpected = directory / "unexpected.txt"
            unexpected.write_text("preserve", encoding="utf-8")
            with self.assertRaises(SnapshotRecoveryRequired):
                handle.cleanup()
            self.assertEqual(
                {child.name for child in directory.iterdir()},
                {OWNER_FILENAME, LEASE_FILENAME, PACKAGE_FILENAME, unexpected.name},
            )
            unexpected.unlink()
            handle.cleanup()

    def test_cleanup_never_deletes_a_replacement_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            handle = service(root).create_snapshot(source, PACKAGE_SHA)
            lease_path = root / TOKEN / LEASE_FILENAME
            moved = root / TOKEN / "original.lease"
            try:
                os.replace(lease_path, moved)
            except PermissionError:
                handle.cleanup()
                self.assertFalse((root / TOKEN).exists())
                return
            lease_path.write_bytes(b"replacement")
            with self.assertRaises(SnapshotRecoveryRequired):
                handle.cleanup()
            self.assertEqual(lease_path.read_bytes(), b"replacement")
            lease_path.unlink()
            os.replace(moved, lease_path)
            handle.cleanup()

    def test_unsafe_ancestor_is_rejected_before_any_child_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            target = base / "outside"
            target.mkdir()
            linked_root = base / "linked-root"
            try:
                linked_root.symlink_to(target, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"Directory symlinks are unavailable: {error}")
            with self.assertRaises(SnapshotFailed):
                service(linked_root / "snapshots").create_snapshot(source, PACKAGE_SHA)
            self.assertFalse((target / "snapshots").exists())

    def test_source_change_during_copy_is_rejected(self) -> None:
        class MutatingService(CapturePackageSnapshotService):
            def _copy_exclusive(self, source: Path, destination: Path) -> tuple[str, int]:
                result = super()._copy_exclusive(source, destination)
                source.write_bytes(PACKAGE_BYTES + b"changed")
                return result

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            snapshot_service = MutatingService(
                root,
                clock=lambda: NOW,
                token_factory=lambda: TOKEN,
                process_id=1234,
                hostname="test-host",
            )
            with self.assertRaises(PackageChanged):
                snapshot_service.create_snapshot(source, PACKAGE_SHA)
            self.assertEqual(list(root.iterdir()), [])

    def test_copy_interruption_removes_only_partial_owned_snapshot(self) -> None:
        class InterruptingService(CapturePackageSnapshotService):
            def _copy_exclusive(self, source: Path, destination: Path) -> tuple[str, int]:
                with self._open_exclusive(destination) as target:
                    target.write(b"partial")
                raise OSError("simulated interruption")

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            snapshot_service = InterruptingService(
                root,
                clock=lambda: NOW,
                token_factory=lambda: TOKEN,
                process_id=1234,
                hostname="test-host",
            )
            with self.assertRaises(SnapshotFailed):
                snapshot_service.create_snapshot(source, PACKAGE_SHA)
            self.assertEqual(list(root.iterdir()), [])

    def test_constructor_boundaries_reject_booleans_and_invalid_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "snapshots"
            for kwargs in (
                {"maximum_package_size": 0},
                {"maximum_package_size": True},
                {"chunk_size": 0},
                {"chunk_size": True},
            ):
                with self.subTest(kwargs=kwargs):
                    with self.assertRaises(ValueError):
                        CapturePackageSnapshotService(root, **kwargs)
