"""Focused tests for immutable capture-package snapshots."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest import mock

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

    def test_open_snapshot_rejects_replacement_owner_with_equal_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            handle = service(root).create_snapshot(source, PACKAGE_SHA)
            owner_path = root / TOKEN / OWNER_FILENAME
            moved = root / TOKEN / "original-owner.json"
            original = owner_path.read_bytes()
            os.replace(owner_path, moved)
            owner_path.write_bytes(original)
            try:
                with self.assertRaises(PackageChanged):
                    with handle.open_package():
                        self.fail("A replacement owner must be rejected before yield.")
            finally:
                owner_path.unlink()
                os.replace(moved, owner_path)
                handle.cleanup()

    @unittest.skipUnless(os.name != "nt", "POSIX permits replacing an open lease pathname")
    def test_open_snapshot_rejects_lease_replacement_at_close(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            handle = service(root).create_snapshot(source, PACKAGE_SHA)
            lease_path = root / TOKEN / LEASE_FILENAME
            moved = root / TOKEN / "original.lease"
            package_handle = None
            try:
                with self.assertRaises(PackageChanged):
                    with handle.open_package() as package_handle:
                        os.replace(lease_path, moved)
                        lease_path.write_bytes(b"replacement")
                self.assertIsNotNone(package_handle)
                self.assertTrue(package_handle.closed)
            finally:
                if lease_path.exists():
                    lease_path.unlink()
                if moved.exists():
                    os.replace(moved, lease_path)
                handle.cleanup()

    @unittest.skipUnless(os.name != "nt", "POSIX permits renaming a leased directory")
    def test_open_snapshot_rejects_token_directory_replacement_at_close(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            handle = service(root).create_snapshot(source, PACKAGE_SHA)
            directory = root / TOKEN
            moved = root / f"{TOKEN}-original"
            replacement_created = False
            try:
                with self.assertRaises(PackageChanged):
                    with handle.open_package():
                        os.replace(directory, moved)
                        directory.mkdir()
                        replacement_created = True
                        for name in (OWNER_FILENAME, LEASE_FILENAME, PACKAGE_FILENAME):
                            shutil.copyfile(moved / name, directory / name)
            finally:
                if replacement_created and directory.exists():
                    shutil.rmtree(directory)
                if moved.exists():
                    os.replace(moved, directory)
                handle.cleanup()

    def test_open_snapshot_preserves_body_exception_and_closes_handle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            handle = service(root).create_snapshot(source, PACKAGE_SHA)
            package_handle = None
            try:
                with self.assertRaisesRegex(RuntimeError, "body failure"):
                    with handle.open_package() as package_handle:
                        raise RuntimeError("body failure")
                self.assertIsNotNone(package_handle)
                self.assertTrue(package_handle.closed)
            finally:
                handle.cleanup()

    @unittest.skipUnless(os.name != "nt", "POSIX permits concurrent package mutation")
    def test_open_snapshot_detects_package_mutation_during_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            handle = service(root).create_snapshot(source, PACKAGE_SHA)
            package_path = root / TOKEN / PACKAGE_FILENAME
            package_handle = None
            try:
                package_path.chmod(stat.S_IWRITE | stat.S_IREAD)
                with self.assertRaises(PackageChanged):
                    with handle.open_package() as package_handle:
                        package_path.write_bytes(PACKAGE_BYTES + b"changed")
                self.assertIsNotNone(package_handle)
                self.assertTrue(package_handle.closed)
            finally:
                package_path.write_bytes(PACKAGE_BYTES)
                handle.cleanup()

    def test_open_snapshot_closes_package_when_post_open_binding_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            snapshot_service = service(root)
            handle = snapshot_service.create_snapshot(source, PACKAGE_SHA)
            package_path = root / TOKEN / PACKAGE_FILENAME
            moved = root / TOKEN / "moved-package.ca-package"
            try:
                with mock.patch.object(
                    snapshot_service,
                    "_verify_snapshot_binding",
                    side_effect=[None, SnapshotRecoveryRequired()],
                ):
                    with self.assertRaises(PackageChanged):
                        with handle.open_package():
                            self.fail("Binding failure must occur before yield.")
                os.replace(package_path, moved)
                os.replace(moved, package_path)
            finally:
                if moved.exists() and not package_path.exists():
                    os.replace(moved, package_path)
                handle.cleanup()

    @unittest.skipUnless(os.name != "nt", "POSIX permits replacing an open package pathname")
    def test_open_snapshot_rejects_exact_byte_package_path_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            handle = service(root).create_snapshot(source, PACKAGE_SHA)
            package_path = root / TOKEN / PACKAGE_FILENAME
            moved = base / "original-package.ca-package"
            package_handle = None
            try:
                with self.assertRaises(PackageChanged):
                    with handle.open_package() as package_handle:
                        os.replace(package_path, moved)
                        package_path.write_bytes(PACKAGE_BYTES)
                self.assertIsNotNone(package_handle)
                self.assertTrue(package_handle.closed)
                self.assertEqual(package_path.read_bytes(), PACKAGE_BYTES)
            finally:
                if package_path.exists():
                    package_path.unlink()
                if moved.exists():
                    os.replace(moved, package_path)
                handle.cleanup()

    @unittest.skipUnless(os.name != "nt", "POSIX permits renaming a live snapshot root")
    def test_open_snapshot_rejects_snapshot_root_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            moved = base / "snapshots-original"
            handle = service(root).create_snapshot(source, PACKAGE_SHA)
            package_handle = None
            try:
                with self.assertRaises(PackageChanged):
                    with handle.open_package() as package_handle:
                        os.replace(root, moved)
                        shutil.copytree(moved, root)
                self.assertIsNotNone(package_handle)
                self.assertTrue(package_handle.closed)
                self.assertTrue((root / TOKEN / PACKAGE_FILENAME).is_file())
            finally:
                if root.exists():
                    shutil.rmtree(root)
                if moved.exists():
                    os.replace(moved, root)
                handle.cleanup()

    @unittest.skipUnless(os.name != "nt", "POSIX permits renaming a snapshot parent")
    def test_open_snapshot_rejects_parent_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            parent = base / "imports"
            root = parent / "snapshots"
            moved = base / "imports-original"
            handle = service(root).create_snapshot(source, PACKAGE_SHA)
            package_handle = None
            try:
                with self.assertRaises(PackageChanged):
                    with handle.open_package() as package_handle:
                        os.replace(parent, moved)
                        shutil.copytree(moved, parent)
                self.assertIsNotNone(package_handle)
                self.assertTrue(package_handle.closed)
                self.assertTrue((root / TOKEN / PACKAGE_FILENAME).is_file())
            finally:
                if parent.exists():
                    shutil.rmtree(parent)
                if moved.exists():
                    os.replace(moved, parent)
                handle.cleanup()

    @unittest.skipUnless(os.name != "nt", "POSIX symlink swap coverage")
    def test_open_snapshot_rejects_owner_symlink_swap_without_deleting_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            handle = service(root).create_snapshot(source, PACKAGE_SHA)
            owner_path = root / TOKEN / OWNER_FILENAME
            moved = base / "original-owner.json"
            try:
                os.replace(owner_path, moved)
                owner_path.symlink_to(moved)
                with self.assertRaises(PackageChanged):
                    with handle.open_package():
                        self.fail("A symlink replacement must fail before yield.")
                self.assertTrue(owner_path.is_symlink())
                self.assertEqual(moved.read_bytes(), owner_path.read_bytes())
            finally:
                if owner_path.is_symlink():
                    owner_path.unlink()
                if moved.exists():
                    os.replace(moved, owner_path)
                handle.cleanup()

    @unittest.skipUnless(os.name != "nt", "POSIX hard-link swap coverage")
    def test_open_snapshot_rejects_owner_hard_link_swap_without_deleting_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source.ca-package"
            source.write_bytes(PACKAGE_BYTES)
            root = base / "snapshots"
            handle = service(root).create_snapshot(source, PACKAGE_SHA)
            owner_path = root / TOKEN / OWNER_FILENAME
            moved = base / "original-owner.json"
            replacement_source = base / "replacement-owner.json"
            owner_bytes = owner_path.read_bytes()
            try:
                os.replace(owner_path, moved)
                replacement_source.write_bytes(owner_bytes)
                os.link(replacement_source, owner_path)
                with self.assertRaises(PackageChanged):
                    with handle.open_package():
                        self.fail("A hard-link replacement must fail before yield.")
                self.assertEqual(owner_path.read_bytes(), owner_bytes)
                self.assertTrue(owner_path.exists())
            finally:
                if owner_path.exists():
                    owner_path.unlink()
                if replacement_source.exists():
                    replacement_source.unlink()
                if moved.exists():
                    os.replace(moved, owner_path)
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
