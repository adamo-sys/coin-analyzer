"""Focused Sprint 8 Unit 7B processed-artifact durability tests."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from PIL import Image

import capture_import.processed_snapshot as processed_snapshot_module
from capture_import._filesystem import (
    handle_object_identity,
    open_exclusive_child_binary,
    open_plain_child_directory,
    open_plain_child_file_readonly,
    open_plain_directory_handle,
)
from capture_import._json import canonical_json_bytes
from capture_import.enums import ImageRole
from capture_import.errors import SnapshotFailed, SnapshotRecoveryRequired
from capture_import.lock import PackageImportLock
from capture_import.media import ValidatedMedia
from capture_import.package import ValidatedCapturePackage
from capture_import.processed_snapshot import (
    ProcessedArtifactDescriptor,
    ProcessedArtifactObject,
    ProcessedArtifactSnapshotService,
    ProcessedSnapshotCompletion,
    ProcessedSnapshotManifest,
    ProcessedSnapshotOwner,
    SourceArtifactLink,
)
from capture_import.workflow_models import (
    PreparedArtifactDescriptor,
    PreparedArtifactSet,
    PreparedWorkspaceLease,
)

_NOW = "2026-07-23T12:00:00Z"
_PACKAGE_SHA = "a" * 64


def _jpeg(width: int = 9, height: int = 7) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), (30, 90, 150)).save(
        output,
        format="JPEG",
        quality=92,
        progressive=False,
        exif=b"",
    )
    return output.getvalue()


def _overwrite_shared(path: Path, payload: bytes) -> None:
    if os.name != "nt":
        path.write_bytes(payload)
        return
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    )
    create_file.restype = ctypes.c_void_p
    handle = create_file(
        str(path),
        0x40000000,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x00000080,
        None,
    )
    if handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), "test mutation open failed")
    try:
        written = ctypes.c_uint32()
        if not kernel32.WriteFile(
            handle,
            payload,
            len(payload),
            ctypes.byref(written),
            None,
        ):
            raise OSError(ctypes.get_last_error(), "test mutation write failed")
        if not kernel32.SetEndOfFile(handle):
            raise OSError(ctypes.get_last_error(), "test mutation truncate failed")
    finally:
        kernel32.CloseHandle(handle)


class _Ids:
    def __init__(self) -> None:
        self._value = 0

    def __call__(self) -> str:
        self._value += 1
        return f"00000000-0000-4000-8000-{self._value:012d}"


def _package(payload: bytes) -> ValidatedCapturePackage:
    media = ValidatedMedia(
        coin_id="coin-1",
        role=ImageRole.FRONT,
        archive_path="images/front.jpg",
        mime_type="image/jpeg",
        byte_length=len(payload),
        width=9,
        height=7,
        sha256=sha256(b"original-package-image").hexdigest(),
    )
    return ValidatedCapturePackage(
        package_basename="capture.ca-package",
        package_sha256=_PACKAGE_SHA,
        package_byte_length=123,
        archive=None,  # type: ignore[arg-type]
        manifest=SimpleNamespace(package_version="1.0"),  # type: ignore[arg-type]
        media=(media,),
    )


def _prepared(workspace: Path, payload: bytes) -> PreparedArtifactSet:
    artifact_path = workspace / "normalized" / "coin-1" / "front.jpg"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_bytes(payload)
    root = open_plain_directory_handle(workspace)
    normalized = open_plain_child_directory(root, "normalized")
    coin = open_plain_child_directory(normalized, "coin-1")
    handle = open_plain_child_file_readonly(coin, "front.jpg")
    descriptor = PreparedArtifactDescriptor(
        artifact_key="normalized-coin-1-front",
        source_coin_id="coin-1",
        role="front",
        variant="NORMALIZED",
        content_type="image/jpeg",
        expected_byte_length=len(payload),
        expected_sha256=sha256(payload).hexdigest(),
        workspace_relative_path="normalized/coin-1/front.jpg",
        root_identity=root.identity,
        parent_identity=coin.identity,
        file_identity=handle_object_identity(handle),
    )
    return PreparedArtifactSet(
        (descriptor,),
        PreparedWorkspaceLease(
            workspace,
            root,
            (handle,),
            ((normalized, coin),),
        ),
    )


class PreparedArtifactOwnershipTests(unittest.TestCase):
    def test_claim_is_single_use_and_preserves_active_handles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            prepared = _prepared(Path(temporary), _jpeg())
            claimed = prepared.claim()
            self.assertTrue(claimed.is_active)
            with self.assertRaisesRegex(RuntimeError, "already claimed"):
                prepared.claim()
            prepared.close()
            self.assertTrue(claimed.is_active)
            claimed.close()
            self.assertFalse(claimed.is_active)

    def test_close_if_unclaimed_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            prepared = _prepared(Path(temporary), _jpeg())
            prepared.close_if_unclaimed()
            prepared.close_if_unclaimed()
            self.assertFalse(prepared.is_active)

    def test_close_before_claim_prevents_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            prepared = _prepared(Path(temporary), _jpeg())
            prepared.close()
            with self.assertRaises(OSError):
                prepared.claim()
            self.assertFalse(prepared.is_claimed)

    def test_failed_claim_retains_caller_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            prepared = _prepared(workspace, _jpeg())
            _overwrite_shared(
                workspace / "normalized" / "coin-1" / "front.jpg",
                b"changed",
            )
            with self.assertRaises(OSError):
                prepared.claim()
            self.assertFalse(prepared.is_claimed)
            self.assertTrue(prepared.is_active)
            prepared.close_if_unclaimed()
            self.assertFalse(prepared.is_active)

    def test_partial_construction_failure_closes_supplied_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            root = open_plain_directory_handle(workspace)
            lease = PreparedWorkspaceLease(workspace, root, ())
            with self.assertRaises(ValueError):
                PreparedArtifactSet((), lease)
            self.assertFalse(lease.is_active)


class ProcessedSnapshotLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.workspace = self.base / "workspace"
        self.workspace.mkdir()
        self.root = self.base / "processed-snapshots"
        self.service = ProcessedArtifactSnapshotService(
            self.root,
            clock=lambda: _NOW,
            identifier_factory=_Ids(),
            chunk_size=17,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _seal(self):
        payload = _jpeg()
        prepared = _prepared(self.workspace, payload)
        lock = PackageImportLock.acquire(self.base / "import.lock")
        try:
            handle = self.service.seal(
                prepared,
                _package(payload),
                import_lock=lock,
            )
        finally:
            lock.release()
        return handle, payload

    def _snapshot_path(self, handle) -> Path:
        return self.root / handle.manifest.processed_snapshot_id

    def _cleanup_orphans(self) -> tuple[str, ...]:
        lock = PackageImportLock.acquire(self.base / "import.lock")
        try:
            return self.service.cleanup_orphaned_snapshots(
                (),
                import_lock=lock,
            )
        finally:
            lock.release()

    def _make_incomplete_orphan(
        self,
        *,
        keep: set[str],
        replacements: dict[str, bytes] | None = None,
    ) -> tuple[str, Path]:
        handle, _ = self._seal()
        snapshot_id = handle.manifest.processed_snapshot_id
        snapshot = self._snapshot_path(handle)
        handle.close()
        for name in {
            "owner.json",
            "lease.lock",
            "artifacts",
            "manifest.json",
            "complete.json",
        } - keep:
            path = snapshot / name
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        for relative_path, payload in (replacements or {}).items():
            (snapshot / relative_path).write_bytes(payload)
        return snapshot_id, snapshot

    def test_seal_is_exact_canonical_and_independently_verifiable(self) -> None:
        handle, payload = self._seal()
        handle.validate()
        descriptor = handle.manifest.artifacts[0]
        self.assertEqual(descriptor.relative_path, f"artifacts/000-{sha256(payload).hexdigest()}.jpg")
        self.assertNotIn(str(self.workspace), str(handle.manifest.to_dict()))
        snapshot = self.root / handle.manifest.processed_snapshot_id
        self.assertEqual(os.fstat(handle._lease_handle.fileno()).st_size, 0)
        with handle.open_artifact(0) as artifact:
            self.assertEqual(artifact.read(), payload)
        shutil.rmtree(self.workspace)
        self.assertFalse(self.workspace.exists())
        handle.cleanup()
        self.assertFalse(snapshot.exists())

    def test_closed_models_round_trip_and_reject_unknown_fields(self) -> None:
        handle, _ = self._seal()
        manifest = ProcessedSnapshotManifest.from_dict(handle.manifest.to_dict())
        owner = ProcessedSnapshotOwner.from_dict(handle.owner.to_dict())
        completion = ProcessedSnapshotCompletion.from_dict(
            handle.completion.to_dict()
        )
        self.assertEqual(manifest, handle.manifest)
        self.assertEqual(owner, handle.owner)
        self.assertEqual(completion, handle.completion)
        invalid = handle.manifest.to_dict()
        invalid["unknown"] = True
        with self.assertRaisesRegex(ValueError, "closed schema"):
            ProcessedSnapshotManifest.from_dict(invalid)
        handle.cleanup()

    def test_manifest_descriptor_contains_source_link_not_workspace_facts(self) -> None:
        handle, _ = self._seal()
        data = handle.manifest.artifacts[0].to_dict()
        self.assertEqual(
            data["source_artifact"],
            SourceArtifactLink(
                "images/front.jpg",
                sha256(b"original-package-image").hexdigest(),
            ).to_dict(),
        )
        self.assertNotIn("workspace_relative_path", data)
        self.assertNotIn("file_identity", data)
        handle.cleanup()

    def test_artifact_corruption_fails_closed(self) -> None:
        handle, _ = self._seal()
        self.addCleanup(handle.close)
        snapshot = self.root / handle.manifest.processed_snapshot_id
        artifact_path = snapshot / Path(
            handle.manifest.artifacts[0].relative_path
        )
        _overwrite_shared(artifact_path, b"corrupt")
        with self.assertRaises(SnapshotRecoveryRequired):
            handle.validate()
        handle.close()

    def test_cleanup_is_bounded_to_owned_snapshot(self) -> None:
        handle, _ = self._seal()
        sibling = self.root / "unrelated"
        sibling.mkdir()
        (sibling / "keep.txt").write_text("keep", encoding="utf-8")
        handle.cleanup()
        self.assertEqual((sibling / "keep.txt").read_text(encoding="utf-8"), "keep")

    def test_existing_snapshot_id_fails_without_overwrite_or_leak(self) -> None:
        payload = _jpeg()
        prepared = _prepared(self.workspace, payload)
        collision = self.root / "00000000-0000-4000-8000-000000000001"
        collision.mkdir(parents=True)
        marker = collision / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        lock = PackageImportLock.acquire(self.base / "import.lock")
        try:
            with self.assertRaises(SnapshotFailed):
                self.service.seal(prepared, _package(payload), import_lock=lock)
        finally:
            lock.release()
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
        self.assertFalse(prepared.is_active)

    def test_invalid_identifier_after_transfer_closes_claimed_handles(self) -> None:
        service = ProcessedArtifactSnapshotService(
            self.root,
            clock=lambda: _NOW,
            identifier_factory=lambda: "invalid",
        )
        payload = _jpeg()
        prepared = _prepared(self.workspace, payload)
        lock = PackageImportLock.acquire(self.base / "import.lock")
        try:
            with self.assertRaises(SnapshotFailed):
                service.seal(prepared, _package(payload), import_lock=lock)
        finally:
            lock.release()
        self.assertTrue(prepared.is_claimed)
        self.assertFalse(prepared.is_active)
        self.assertFalse(self.root.exists() and any(self.root.iterdir()))

    def test_failure_after_artifact_copy_cleans_only_proven_partial_state(self) -> None:
        calls = iter((_NOW, "not-a-timestamp"))
        service = ProcessedArtifactSnapshotService(
            self.root,
            clock=lambda: next(calls),
            identifier_factory=_Ids(),
        )
        payload = _jpeg()
        prepared = _prepared(self.workspace, payload)
        lock = PackageImportLock.acquire(self.base / "import.lock")
        try:
            with self.assertRaises(SnapshotFailed):
                service.seal(prepared, _package(payload), import_lock=lock)
        finally:
            lock.release()
        self.assertFalse(self.root.exists() and any(self.root.iterdir()))
        self.assertFalse(prepared.is_active)

    @unittest.skipIf(
        os.name == "nt",
        "Windows prevents this pathname replacement while the identity handle is held.",
    )
    def test_replaced_artifact_path_is_detected_by_identity(self) -> None:
        handle, payload = self._seal()
        snapshot = self.root / handle.manifest.processed_snapshot_id
        path = snapshot / Path(handle.manifest.artifacts[0].relative_path)
        replacement = path.with_name("replacement.jpg")
        replacement.write_bytes(payload)
        os.replace(replacement, path)
        with self.assertRaises(SnapshotRecoveryRequired):
            handle.validate()
        handle.close()

    @unittest.skipIf(
        os.name == "nt",
        "Windows holds the intermediate directory against pathname replacement.",
    )
    def test_pa_rm01_handoff_source_replacement_fails_closed(self) -> None:
        payload = _jpeg()
        prepared = _prepared(self.workspace, payload)
        normalized = self.workspace / "normalized"
        displaced = self.workspace / "displaced"
        normalized.rename(displaced)
        normalized.symlink_to(self.base / "escape", target_is_directory=True)
        with self.assertRaises(SnapshotFailed):
            lock = PackageImportLock.acquire(self.base / "import.lock")
            try:
                self.service.seal(
                    prepared,
                    _package(payload),
                    import_lock=lock,
                )
            finally:
                lock.release()
        self.assertFalse(self.root.exists() and any(self.root.iterdir()))
        prepared.close_if_unclaimed()

    def test_pa_rm02_cancel_after_transfer_before_root(self) -> None:
        def cancel_after_transfer():
            raise RuntimeError("injected coordinator cancellation")

        service = ProcessedArtifactSnapshotService(
            self.root,
            clock=lambda: _NOW,
            identifier_factory=cancel_after_transfer,
        )
        payload = _jpeg()
        prepared = _prepared(self.workspace, payload)
        lock = PackageImportLock.acquire(self.base / "import.lock")
        try:
            with self.assertRaises(SnapshotFailed):
                service.seal(prepared, _package(payload), import_lock=lock)
        finally:
            lock.release()
        self.assertTrue(prepared.is_claimed)
        self.assertFalse(prepared.is_active)
        self.assertFalse(self.root.exists() and any(self.root.iterdir()))

    def test_pa_rm03_partial_owner_preserved_and_blocks(self) -> None:
        _snapshot_id, snapshot = self._make_incomplete_orphan(
            keep={"owner.json"},
            replacements={"owner.json": b"{\"partial\":"},
        )
        with self.assertRaises(SnapshotRecoveryRequired) as caught:
            self._cleanup_orphans()
        self.assertTrue(snapshot.exists())
        self.assertNotIn(str(snapshot), str(caught.exception))

    def test_pa_rm04_owner_only_orphan_cleanup(self) -> None:
        snapshot_id, snapshot = self._make_incomplete_orphan(
            keep={"owner.json"},
        )
        self.assertEqual(self._cleanup_orphans(), (snapshot_id,))
        self.assertFalse(snapshot.exists())

    def test_pa_rm05_partial_artifact_cleanup(self) -> None:
        handle, _ = self._seal()
        snapshot_id = handle.manifest.processed_snapshot_id
        snapshot = self._snapshot_path(handle)
        artifact = snapshot / handle.manifest.artifacts[0].relative_path
        handle.close()
        (snapshot / "manifest.json").unlink()
        (snapshot / "complete.json").unlink()
        artifact.write_bytes(b"partial")
        self.assertEqual(self._cleanup_orphans(), (snapshot_id,))
        self.assertFalse(snapshot.exists())

    def test_pa_rm06_complete_unsealed_artifact_is_cleanup_only(self) -> None:
        handle, _ = self._seal()
        snapshot_id = handle.manifest.processed_snapshot_id
        snapshot = self._snapshot_path(handle)
        handle.close()
        (snapshot / "manifest.json").unlink()
        (snapshot / "complete.json").unlink()
        self.assertEqual(self._cleanup_orphans(), (snapshot_id,))
        self.assertFalse(snapshot.exists())

    def test_pa_rm07_source_mutation_during_seal(self) -> None:
        payload = _jpeg()
        prepared = _prepared(self.workspace, payload)
        source = self.workspace / "normalized" / "coin-1" / "front.jpg"
        original_read = self.service._read_exact
        reads = 0

        def mutate_during_read(handle, expected):
            nonlocal reads
            result = original_read(handle, expected)
            reads += 1
            if reads == 1:
                _overwrite_shared(source, b"changed-during-bounded-copy")
            return result

        lock = PackageImportLock.acquire(self.base / "import.lock")
        try:
            with mock.patch.object(
                self.service,
                "_read_exact",
                side_effect=mutate_during_read,
            ):
                with self.assertRaises(SnapshotFailed):
                    self.service.seal(
                        prepared,
                        _package(payload),
                        import_lock=lock,
                    )
        finally:
            lock.release()
        self.assertFalse(self.root.exists() and any(self.root.iterdir()))
        self.assertTrue(prepared.is_claimed)
        self.assertFalse(prepared.is_active)

    def test_pa_rm08_artifacts_without_manifest_cleanup(self) -> None:
        handle, _ = self._seal()
        snapshot_id = handle.manifest.processed_snapshot_id
        snapshot = self._snapshot_path(handle)
        handle.close()
        (snapshot / "manifest.json").unlink()
        (snapshot / "complete.json").unlink()
        self.assertEqual(self._cleanup_orphans(), (snapshot_id,))
        self.assertFalse(snapshot.exists())

    def test_pa_rm09_manifest_candidate_reconciliation(self) -> None:
        snapshot_id, snapshot = self._make_incomplete_orphan(
            keep={"owner.json", "lease.lock", "artifacts", "manifest.json"},
            replacements={"manifest.json": b"{\"partial\":"},
        )
        self.assertEqual(self._cleanup_orphans(), (snapshot_id,))
        self.assertFalse(snapshot.exists())

    def test_pa_rm10_manifest_without_completion_not_adopted(self) -> None:
        snapshot_id, snapshot = self._make_incomplete_orphan(
            keep={"owner.json", "lease.lock", "artifacts", "manifest.json"},
        )
        self.assertEqual(self._cleanup_orphans(), (snapshot_id,))
        self.assertFalse(snapshot.exists())

    def test_pa_rm11_completion_candidate_reconciliation(self) -> None:
        snapshot_id, snapshot = self._make_incomplete_orphan(
            keep={
                "owner.json",
                "lease.lock",
                "artifacts",
                "manifest.json",
                "complete.json",
            },
            replacements={"complete.json": b"{\"partial\":"},
        )
        self.assertEqual(self._cleanup_orphans(), (snapshot_id,))
        self.assertFalse(snapshot.exists())

    def test_pa_rm11_canonical_conflicting_completion_is_preserved(self) -> None:
        handle, _ = self._seal()
        snapshot = self._snapshot_path(handle)
        completion = handle.completion.to_dict()
        handle.close()
        completion["ownership_token_sha256"] = "f" * 64
        (snapshot / "complete.json").write_bytes(
            canonical_json_bytes(completion)
        )
        with self.assertRaises(SnapshotRecoveryRequired):
            self._cleanup_orphans()
        self.assertTrue(snapshot.exists())

    def test_pa_rm12_complete_prejournal_orphan_cleanup(self) -> None:
        handle, _ = self._seal()
        snapshot_id = handle.manifest.processed_snapshot_id
        snapshot = self._snapshot_path(handle)
        handle.close()
        self.assertEqual(self._cleanup_orphans(), (snapshot_id,))
        self.assertFalse(snapshot.exists())

    def test_pa_rm27_referenced_processed_snapshot_not_orphaned(self) -> None:
        handle, _ = self._seal()
        snapshot_id = handle.manifest.processed_snapshot_id
        snapshot = self._snapshot_path(handle)
        handle.close()
        before = {
            path.relative_to(snapshot).as_posix(): path.read_bytes()
            for path in snapshot.rglob("*")
            if path.is_file()
        }
        lock = PackageImportLock.acquire(self.base / "import.lock")
        try:
            self.assertEqual(
                self.service.cleanup_orphaned_snapshots(
                    (snapshot_id,), import_lock=lock
                ),
                (),
            )
            self.assertEqual(
                self.service.cleanup_orphaned_snapshots(
                    (snapshot_id,), import_lock=lock
                ),
                (),
            )
        finally:
            lock.release()
        after = {
            path.relative_to(snapshot).as_posix(): path.read_bytes()
            for path in snapshot.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)

    def test_pa_rm28_uncertain_processed_orphan_preserved(self) -> None:
        handle, payload = self._seal()
        snapshot = self._snapshot_path(handle)
        artifact = handle.manifest.artifacts[0].relative_path
        expected = {
            "owner.json": canonical_json_bytes(handle.owner.to_dict()),
            "lease.lock": b"",
            artifact: payload,
            "manifest.json": canonical_json_bytes(handle.manifest.to_dict()),
            "complete.json": canonical_json_bytes(handle.completion.to_dict()),
        }
        lock = PackageImportLock.acquire(self.base / "import.lock")
        try:
            for _attempt in range(2):
                with self.assertRaises(SnapshotRecoveryRequired):
                    self.service.cleanup_orphaned_snapshots(
                        (), import_lock=lock, wait_seconds=0
                    )
        finally:
            lock.release()
        handle.close()
        after = {
            path.relative_to(snapshot).as_posix(): path.read_bytes()
            for path in snapshot.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, expected)
        self.assertEqual(self._cleanup_orphans(), (handle.manifest.processed_snapshot_id,))

    def test_pa_rm36_processed_root_capability_failure(self) -> None:
        payload = _jpeg()
        lock = PackageImportLock.acquire(self.base / "import.lock")
        try:
            for attempt in range(2):
                workspace = self.base / f"unsupported-{attempt}"
                workspace.mkdir()
                prepared = _prepared(workspace, payload)
                with mock.patch.object(
                    processed_snapshot_module,
                    "ensure_plain_directory",
                    side_effect=OSError("unsupported processed root"),
                ):
                    with self.assertRaises(SnapshotFailed):
                        self.service.seal(
                            prepared,
                            _package(payload),
                            import_lock=lock,
                        )
                self.assertFalse(
                    self.root.exists() and any(self.root.iterdir())
                )
        finally:
            lock.release()

    def test_pa_rm37_processed_lease_is_bounded(self) -> None:
        handle, _ = self._seal()
        snapshot_id = handle.manifest.processed_snapshot_id
        lock = PackageImportLock.acquire(self.base / "import.lock")
        try:
            for invalid in (float("nan"), float("inf"), -1, 31):
                with self.subTest(invalid=invalid):
                    with self.assertRaises(ValueError):
                        self.service.open_snapshot(
                            snapshot_id,
                            import_lock=lock,
                            wait_seconds=invalid,
                        )
            with self.assertRaises(SnapshotRecoveryRequired):
                self.service.open_snapshot(
                    snapshot_id,
                    import_lock=lock,
                    wait_seconds=0,
                )
            with self.assertRaises(SnapshotRecoveryRequired):
                self.service.open_snapshot(
                    snapshot_id,
                    import_lock=lock,
                    wait_seconds=0,
                )
        finally:
            lock.release()
        handle.cleanup()

    def test_pa_rm38_processed_inventory_conflict(self) -> None:
        handle, _ = self._seal()
        snapshot = self._snapshot_path(handle)
        handle.close()
        extra = snapshot / "unexpected.bin"
        extra.write_bytes(b"preserve")
        before = {
            path.relative_to(snapshot).as_posix(): path.read_bytes()
            for path in snapshot.rglob("*")
            if path.is_file()
        }
        for _attempt in range(2):
            with self.assertRaises(SnapshotRecoveryRequired) as caught:
                self._cleanup_orphans()
        self.assertEqual(extra.read_bytes(), b"preserve")
        self.assertNotIn(str(snapshot), str(caught.exception))
        self.assertEqual(
            {
                path.relative_to(snapshot).as_posix(): path.read_bytes()
                for path in snapshot.rglob("*")
                if path.is_file()
            },
            before,
        )

    @unittest.skipIf(
        os.name == "nt",
        "POSIX CI exercises canonical duplicate and reparse inventory objects.",
    )
    def test_pa_rm38_reparse_or_casefold_duplicate_is_preserved(self) -> None:
        handle, _ = self._seal()
        snapshot = self._snapshot_path(handle)
        artifact = snapshot / handle.manifest.artifacts[0].relative_path
        handle.close()
        duplicate = artifact.with_name(artifact.name.upper())
        duplicate.symlink_to(artifact.name)
        with self.assertRaises(SnapshotRecoveryRequired):
            self._cleanup_orphans()
        self.assertTrue(duplicate.is_symlink())

    def test_pa_rm41_owner_then_lease_crash_is_cleanup_only(self) -> None:
        payload = _jpeg()
        prepared = _prepared(self.workspace, payload)
        lock = PackageImportLock.acquire(self.base / "import.lock")
        try:
            with mock.patch.object(
                self.service,
                "_acquire_zero_byte_lease",
                side_effect=RuntimeError("crash after lease publication"),
            ):
                with self.assertRaises(SnapshotFailed):
                    self.service.seal(
                        prepared, _package(payload), import_lock=lock
                    )
            self.assertFalse(self.root.exists() and any(self.root.iterdir()))
            self.assertEqual(
                self.service.cleanup_orphaned_snapshots(
                    (), import_lock=lock
                ),
                (),
            )
            self.assertEqual(
                self.service.cleanup_orphaned_snapshots(
                    (), import_lock=lock
                ),
                (),
            )
        finally:
            lock.release()

    def test_snapshot_parent_sync_brackets_root_lifecycle(self) -> None:
        original = processed_snapshot_module.sync_directory
        synced = []

        def record(directory):
            synced.append(directory.path)
            return original(directory)

        with mock.patch.object(
            processed_snapshot_module,
            "sync_directory",
            side_effect=record,
        ):
            handle, _ = self._seal()
            snapshot = self._snapshot_path(handle)
            self.assertIn(self.root, synced)
            first_parent = synced.index(self.root)
            first_root = synced.index(snapshot)
            self.assertLess(first_parent, first_root)
            handle.cleanup()
        self.assertEqual(synced[-1], self.root)

    def test_extra_member_before_completion_prevents_receipt_publication(self) -> None:
        payload = _jpeg()
        prepared = _prepared(self.workspace, payload)
        original = self.service._verify_precompletion
        snapshot_path = None

        def inject(root, *args):
            nonlocal snapshot_path
            snapshot_path = root
            (root / "unexpected.bin").write_bytes(b"conflict")
            return original(root, *args)

        lock = PackageImportLock.acquire(self.base / "import.lock")
        try:
            with mock.patch.object(
                self.service,
                "_verify_precompletion",
                side_effect=inject,
            ):
                with self.assertRaises(SnapshotRecoveryRequired):
                    self.service.seal(
                        prepared,
                        _package(payload),
                        import_lock=lock,
                    )
        finally:
            lock.release()
        self.assertIsNotNone(snapshot_path)
        self.assertFalse((snapshot_path / "complete.json").exists())
        self.assertEqual(
            (snapshot_path / "unexpected.bin").read_bytes(),
            b"conflict",
        )

    def test_partial_publication_disappearance_is_not_cleanup_success(self) -> None:
        payload = _jpeg()
        prepared = _prepared(self.workspace, payload)

        def disappear(parent, writable, path, state):
            path.unlink()
            raise OSError("injected disappearance")

        lock = PackageImportLock.acquire(self.base / "import.lock")
        try:
            with mock.patch.object(
                self.service,
                "_reopen_readonly",
                side_effect=disappear,
            ):
                with self.assertRaises(SnapshotRecoveryRequired):
                    self.service.seal(
                        prepared,
                        _package(payload),
                        import_lock=lock,
                    )
        finally:
            lock.release()
        self.assertEqual(len(list(self.root.iterdir())), 1)
        self.assertFalse(prepared.is_active)

    def test_partial_publication_replacement_is_preserved(self) -> None:
        payload = _jpeg()
        prepared = _prepared(self.workspace, payload)

        def replace_candidate(parent, writable, path, state):
            replacement = path.with_name("replacement.bin")
            replacement.write_bytes(b"replacement")
            writable.close()
            os.replace(replacement, path)
            raise OSError("injected replacement")

        lock = PackageImportLock.acquire(self.base / "import.lock")
        try:
            with mock.patch.object(
                self.service,
                "_reopen_readonly",
                side_effect=replace_candidate,
            ):
                with self.assertRaises(SnapshotRecoveryRequired):
                    self.service.seal(
                        prepared,
                        _package(payload),
                        import_lock=lock,
                    )
        finally:
            lock.release()
        snapshots = list(self.root.iterdir())
        self.assertEqual(len(snapshots), 1)
        preserved_payloads = [
            path.read_bytes()
            for path in snapshots[0].iterdir()
            if path.is_file()
        ]
        self.assertIn(b"replacement", preserved_payloads)
        self.assertFalse(prepared.is_active)

    def test_cleanup_can_retry_after_predeletion_failure(self) -> None:
        handle, _ = self._seal()
        snapshot = self._snapshot_path(handle)
        original = processed_snapshot_module.delete_open_file
        with mock.patch.object(
            processed_snapshot_module,
            "delete_open_file",
            side_effect=OSError("injected pre-delete failure"),
        ):
            with self.assertRaises(SnapshotRecoveryRequired):
                handle.cleanup()
        self.assertTrue(snapshot.exists())
        with mock.patch.object(
            processed_snapshot_module,
            "delete_open_file",
            side_effect=original,
        ):
            handle.cleanup()
        self.assertFalse(snapshot.exists())

    def test_reopen_failure_closes_untransferred_read_handle(self) -> None:
        parent = open_plain_directory_handle(self.root.parent)
        self.root.mkdir()
        parent.close()
        parent = open_plain_directory_handle(self.root)
        path = self.root / "candidate.bin"
        writable = open_exclusive_child_binary(parent, path.name)
        state = {"handles": [(writable, path)]}
        real_identity = handle_object_identity(writable)
        calls = 0

        def fail_after_open(_handle):
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_identity
            raise OSError("injected post-open identity failure")

        with mock.patch.object(
            processed_snapshot_module,
            "handle_object_identity",
            side_effect=fail_after_open,
        ):
            with self.assertRaises(OSError):
                self.service._reopen_readonly(
                    parent,
                    writable,
                    path,
                    state,
                )
        writable.close()
        path.unlink()
        parent.close()


class ModelBoundaryTests(unittest.TestCase):
    def test_descriptor_rejects_progressive_path_shape_and_bounds(self) -> None:
        link = SourceArtifactLink("images/front.jpg", "b" * 64)
        descriptor = ProcessedArtifactDescriptor(
            "key",
            "coin",
            "front",
            "NORMALIZED",
            "artifacts/000-" + ("a" * 64) + ".jpg",
            "image/jpeg",
            1,
            "a" * 64,
            1,
            1,
            link,
        )
        descriptor.validate()
        with self.assertRaises(ValueError):
            replace(descriptor, byte_length=0).validate()

    def test_closed_models_reject_wrong_json_types(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            workspace = base / "workspace"
            workspace.mkdir()
            service = ProcessedArtifactSnapshotService(
                base / "snapshots",
                clock=lambda: _NOW,
                identifier_factory=_Ids(),
            )
            payload = _jpeg()
            lock = PackageImportLock.acquire(base / "import.lock")
            try:
                handle = service.seal(
                    _prepared(workspace, payload),
                    _package(payload),
                    import_lock=lock,
                )
            finally:
                lock.release()
            cases = (
                (
                    SourceArtifactLink,
                    handle.manifest.artifacts[0].source_artifact.to_dict(),
                    "package_media_relative_path",
                    1,
                ),
                (
                    ProcessedArtifactDescriptor,
                    handle.manifest.artifacts[0].to_dict(),
                    "artifact_key",
                    1,
                ),
                (
                    ProcessedArtifactObject,
                    handle.completion.artifact_objects[0].to_dict(),
                    "sha256",
                    1,
                ),
                (
                    ProcessedSnapshotOwner,
                    handle.owner.to_dict(),
                    "owner_schema_version",
                    1,
                ),
                (
                    ProcessedSnapshotManifest,
                    handle.manifest.to_dict(),
                    "artifact_count",
                    True,
                ),
                (
                    ProcessedSnapshotCompletion,
                    handle.completion.to_dict(),
                    "artifact_objects",
                    {},
                ),
            )
            for model, value, field, invalid in cases:
                with self.subTest(model=model.__name__, field=field):
                    value[field] = invalid
                    with self.assertRaises(ValueError):
                        model.from_dict(value)
            nested_identity = handle.completion.artifact_objects[0].to_dict()
            nested_identity["parent_identity"]["platform"] = 1
            with self.assertRaises(ValueError):
                ProcessedArtifactObject.from_dict(nested_identity)
            handle.cleanup()

    def test_descriptor_rejects_non_nfc_controls_and_unsafe_paths(self) -> None:
        link = SourceArtifactLink("images/front.jpg", "b" * 64)
        descriptor = ProcessedArtifactDescriptor(
            "key",
            "coin",
            "front",
            "NORMALIZED",
            "artifacts/000-" + ("a" * 64) + ".jpg",
            "image/jpeg",
            1,
            "a" * 64,
            1,
            1,
            link,
        )
        for invalid in ("e\u0301", "bad\u0085"):
            with self.subTest(key=repr(invalid)):
                with self.assertRaises(ValueError):
                    replace(descriptor, artifact_key=invalid).validate()
        for invalid in (
            "../escape.jpg",
            "artifacts//bad.jpg",
            "artifacts/bad.jpg.",
            "artifacts\\bad.jpg",
            "C:/bad.jpg",
        ):
            with self.subTest(path=invalid):
                with self.assertRaises(ValueError):
                    replace(descriptor, relative_path=invalid).validate()

    def test_canonical_manifest_conflict_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            workspace = base / "workspace"
            workspace.mkdir()
            root = base / "snapshots"
            service = ProcessedArtifactSnapshotService(
                root,
                clock=lambda: _NOW,
                identifier_factory=_Ids(),
            )
            payload = _jpeg()
            lock = PackageImportLock.acquire(base / "import.lock")
            try:
                handle = service.seal(
                    _prepared(workspace, payload),
                    _package(payload),
                    import_lock=lock,
                )
            finally:
                lock.release()
            snapshot = root / handle.manifest.processed_snapshot_id
            conflicting = handle.manifest.to_dict()
            handle.close()
            (snapshot / "complete.json").unlink()
            conflicting["created_at"] = "2026-07-23T12:00:01Z"
            (snapshot / "manifest.json").write_bytes(
                canonical_json_bytes(conflicting)
            )
            lock = PackageImportLock.acquire(base / "import.lock")
            try:
                with self.assertRaises(SnapshotRecoveryRequired):
                    service.cleanup_orphaned_snapshots(
                        (),
                        import_lock=lock,
                    )
            finally:
                lock.release()
            self.assertTrue(snapshot.exists())


if __name__ == "__main__":
    unittest.main()
