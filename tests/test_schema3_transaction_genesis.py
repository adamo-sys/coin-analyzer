"""Sprint 8 Unit 7D-B provenance, processed-image, and genesis tests."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from coin_collection import (
    CaptureImportMediaProvenance,
    CoinCollection,
    ItemPhoto,
)
from capture_import.coordinator import (
    PackageImportCoordinator,
    PreparedPackageImport,
)
from capture_import.durable_models import (
    ProcessedMediaCommitment,
    ProcessedMediaMappingEntry,
    ProcessedSnapshotReference,
    processed_media_mapping_sha256,
)
from capture_import.durable_repository import (
    Schema3PackageImportJournalRepository,
)
from capture_import.enums import DuplicateDecision, ImageRole, ImportResult
from capture_import.errors import ImageCopyFailed, PackageChanged, RecoveryRequired
from capture_import.image_store import ManagedCollectionImageStore
from capture_import.lock import PackageImportLock
from capture_import.processed_snapshot import (
    ProcessedArtifactDescriptor,
    ProcessedSnapshotManifest,
    SourceArtifactLink,
    artifact_inventory_sha256,
)
from capture_import.transaction import (
    PackageImportExecutionResult,
    Schema3PackageImportTransactionService,
    Schema3TransactionGenesisResult,
)


def _uuid() -> str:
    return str(uuid4())


def _provenance(**changes) -> CaptureImportMediaProvenance:
    values = {
        "schema_version": "1.0",
        "import_id": _uuid(),
        "source_kind": "PROCESSED_SNAPSHOT",
        "package_sha256": "a" * 64,
        "processed_snapshot_id": _uuid(),
        "artifact_key": "normalized/source-1/front",
        "artifact_sha256": "b" * 64,
        "variant": "NORMALIZED",
    }
    values.update(changes)
    return CaptureImportMediaProvenance(**values)


def _fixture(payload: bytes = b"exact-processed-jpeg"):
    package_sha = "a" * 64
    snapshot_id = _uuid()
    workflow_id = _uuid()
    artifact_sha = sha256(payload).hexdigest()
    descriptor = ProcessedArtifactDescriptor(
        artifact_key="normalized/source-1/front",
        source_coin_id="source-1",
        role="front",
        variant="NORMALIZED",
        relative_path=f"artifacts/000-{artifact_sha}.jpg",
        content_type="image/jpeg",
        byte_length=len(payload),
        sha256=artifact_sha,
        width=10,
        height=10,
        source_artifact=SourceArtifactLink(
            package_media_relative_path="images/front.jpg",
            package_media_sha256="f" * 64,
        ),
    )
    manifest = ProcessedSnapshotManifest(
        manifest_schema_version="1.0",
        processed_snapshot_id=snapshot_id,
        workflow_execution_id=workflow_id,
        ownership_token_sha256="1" * 64,
        created_at="2026-07-23T12:00:00Z",
        source_package_sha256=package_sha,
        source_package_byte_length=123,
        source_package_version="1.0",
        artifact_count=1,
        aggregate_byte_length=len(payload),
        artifact_inventory_sha256=artifact_inventory_sha256((descriptor,)),
        artifacts=(descriptor,),
    )
    package_media = SimpleNamespace(
        coin_id="source-1",
        role=ImageRole.FRONT,
        archive_path="images/front.jpg",
        sha256="f" * 64,
    )
    package = SimpleNamespace(
        package_sha256=package_sha,
        package_byte_length=123,
        package_basename="test.ca-package",
        manifest=SimpleNamespace(
            package_version="1.0",
            coins=(SimpleNamespace(id="source-1"),),
        ),
        media=(package_media,),
    )
    return payload, descriptor, manifest, package


class FakeProcessedSnapshot:
    def __init__(self, payload: bytes, manifest: ProcessedSnapshotManifest):
        self.payload = payload
        self.manifest = manifest
        self.validation_count = 0
        self.cleaned = False
        self.closed = False
        self.fail_validation = False
        self.opened_indices: list[int] = []

    @property
    def is_active(self) -> bool:
        return not self.cleaned and not self.closed

    def validate(self) -> None:
        self.validation_count += 1
        if self.fail_validation:
            raise ValueError("processed snapshot invalid")

    @contextmanager
    def open_artifact(self, index: int):
        self.validate()
        self.opened_indices.append(index)
        try:
            yield BytesIO(self.payload)
        finally:
            self.validate()

    def journal_reference(self) -> ProcessedSnapshotReference:
        return ProcessedSnapshotReference(
            processed_snapshot_id=self.manifest.processed_snapshot_id,
            workflow_execution_id=self.manifest.workflow_execution_id,
            root_relative_path=(
                f"processed-snapshots/{self.manifest.processed_snapshot_id}"
            ),
            manifest_relative_path=(
                f"processed-snapshots/{self.manifest.processed_snapshot_id}/manifest.json"
            ),
            completion_relative_path=(
                f"processed-snapshots/{self.manifest.processed_snapshot_id}/complete.json"
            ),
            manifest_byte_length=100,
            completion_byte_length=100,
            manifest_sha256="c" * 64,
            completion_sha256="d" * 64,
            artifact_count=self.manifest.artifact_count,
            aggregate_byte_length=self.manifest.aggregate_byte_length,
            artifact_inventory_sha256=self.manifest.artifact_inventory_sha256,
        )

    def media_commitment(
        self, selected_source_coin_ids: tuple[str, ...]
    ) -> ProcessedMediaCommitment:
        selected = set(selected_source_coin_ids)
        mapping = tuple(
            ProcessedMediaMappingEntry(
                item.source_coin_id,
                item.role,
                item.artifact_key,
                item.sha256,
                item.variant,
            )
            for item in self.manifest.artifacts
            if item.source_coin_id in selected
        )
        return ProcessedMediaCommitment(
            commitment_schema_version="1.0",
            processed_snapshot_id_sha256=sha256(
                self.manifest.processed_snapshot_id.encode()
            ).hexdigest(),
            source_package_sha256=self.manifest.source_package_sha256,
            artifact_count=self.manifest.artifact_count,
            aggregate_byte_length=self.manifest.aggregate_byte_length,
            artifact_inventory_sha256=self.manifest.artifact_inventory_sha256,
            manifest_sha256="c" * 64,
            ordered_mapping=mapping,
            persisted_mapping_sha256=processed_media_mapping_sha256(mapping),
        )

    def cleanup(self) -> None:
        self.cleaned = True

    def close(self) -> None:
        self.closed = True


class FakeRawSnapshot:
    def __init__(self):
        self.descriptor = SimpleNamespace(
            byte_length=123,
            relative_path="snapshots/raw/package.ca-package",
        )
        self.cleaned = False
        self.preserved = False
        self.validation_count = 0

    @property
    def is_active(self) -> bool:
        return not self.cleaned and not self.preserved

    def validate(self) -> None:
        self.validation_count += 1

    def cleanup(self) -> None:
        self.cleaned = True

    def preserve_for_recovery(self) -> None:
        self.preserved = True


class ProvenanceTests(unittest.TestCase):
    def test_legacy_item_photo_round_trip_is_unchanged(self) -> None:
        payload = {
            "path": "front.jpg",
            "role": "FRONT",
            "is_primary": True,
            "notes": "",
            "display_order": 0,
        }
        photo = ItemPhoto.from_dict(payload)
        self.assertIsNotNone(photo)
        self.assertEqual(photo.to_dict(), payload)
        self.assertNotIn("capture_import_media", photo.to_dict())

    def test_valid_closed_provenance_round_trips(self) -> None:
        provenance = _provenance()
        photo = ItemPhoto("front.jpg", capture_import_media=provenance)
        loaded = ItemPhoto.from_dict(photo.to_dict())
        self.assertEqual(loaded.capture_import_media, provenance)
        self.assertEqual(
            frozenset(photo.to_dict()["capture_import_media"]),
            CaptureImportMediaProvenance.FIELDS,
        )

    def test_invalid_or_extra_provenance_is_rejected(self) -> None:
        for invalid in (
            {**_provenance().to_dict(), "extra": "field"},
            {**_provenance().to_dict(), "source_kind": "RAW_PACKAGE"},
            {**_provenance().to_dict(), "artifact_sha256": "bad"},
        ):
            with self.assertRaises(ValueError):
                ItemPhoto.from_dict(
                    {
                        "path": "front.jpg",
                        "capture_import_media": invalid,
                    }
                )


class ProcessedImagePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = ManagedCollectionImageStore(self.root / "images")
        self.payload, self.descriptor, self.manifest, self.package = _fixture()
        self.snapshot = FakeProcessedSnapshot(self.payload, self.manifest)
        self.import_id = _uuid()
        self.ownership_token = _uuid()
        self.desktop_id = _uuid()

    def _plan(self):
        return self.store.plan_processed(
            self.snapshot,
            self.package,
            import_id=self.import_id,
            ownership_token=self.ownership_token,
            source_to_desktop={"source-1": self.desktop_id},
        )

    def _lock(self):
        lock = PackageImportLock.acquire(
            self.root / f"{_uuid()}.lock",
            import_id=self.import_id,
        )
        self.addCleanup(lock.release)
        return lock

    def test_exact_processed_manifest_planning_and_evidence(self) -> None:
        plan = self._plan()
        self.assertEqual(len(plan.media), 1)
        image = plan.media[0]
        self.assertEqual(image.source_artifact_key, self.descriptor.artifact_key)
        self.assertEqual(image.variant, self.descriptor.variant)
        self.assertEqual(image.sha256, self.descriptor.sha256)
        expected = self.store.expected_evidence_processed(plan)[0]
        self.assertEqual(expected.source_snapshot_id, self.manifest.processed_snapshot_id)
        self.assertEqual(expected.source_kind, "PROCESSED_SNAPSHOT")

    def test_mismapped_and_replaced_or_extra_snapshot_evidence_rejects(self) -> None:
        self.package.media[0].archive_path = "images/wrong.jpg"
        with self.assertRaises(ValueError):
            self._plan()
        self.package.media[0].archive_path = "images/front.jpg"
        self.snapshot.fail_validation = True
        with self.assertRaises(ValueError):
            self._plan()

    def test_copy_uses_only_open_artifact_and_persists_exact_bytes(self) -> None:
        plan = self._plan()
        photos = self.store.copy_processed(
            self.snapshot,
            plan,
            lambda _path: None,
            import_lock=self._lock(),
        )
        image = plan.media[0]
        persisted = self.store.root / image.managed_relative_path
        self.assertEqual(persisted.read_bytes(), self.payload)
        self.assertEqual(self.snapshot.opened_indices, [0])
        provenance = photos["source-1"][0].capture_import_media
        self.assertIsNotNone(provenance)
        self.assertEqual(provenance.artifact_key, self.descriptor.artifact_key)
        self.assertEqual(provenance.artifact_sha256, self.descriptor.sha256)

    def test_missing_or_corrupt_artifact_never_falls_back_to_raw(self) -> None:
        plan = self._plan()
        self.snapshot.payload = b"corrupt"
        with self.assertRaises(ImageCopyFailed):
            self.store.copy_processed(
                self.snapshot,
                plan,
                lambda _path: None,
                import_lock=self._lock(),
            )
        self.assertFalse(hasattr(self.snapshot, "open_package"))

    def test_missing_processed_artifact_fails_closed(self) -> None:
        plan = self._plan()

        @contextmanager
        def missing(_index: int):
            self.snapshot.validate()
            raise FileNotFoundError("artifact missing")
            yield

        self.snapshot.open_artifact = missing
        with self.assertRaises(ImageCopyFailed):
            self.store.copy_processed(
                self.snapshot,
                plan,
                lambda _path: None,
                import_lock=self._lock(),
            )

    def test_pa_rm19_complete_copy_produces_exact_verified_v3_evidence(self) -> None:
        plan = self._plan()
        self.store.copy_processed(
            self.snapshot,
            plan,
            lambda _path: None,
            import_lock=self._lock(),
        )
        verified = self.store.verified_evidence_processed(plan)
        self.assertEqual(len(verified), 1)
        self.assertEqual(verified[0].sha256, self.descriptor.sha256)
        self.assertEqual(
            verified[0].source_artifact_key,
            self.descriptor.artifact_key,
        )

    def test_live_manifest_mapping_is_rechecked_before_copy(self) -> None:
        plan = self._plan()
        tampered = replace(
            plan,
            media=(
                replace(
                    plan.media[0],
                    source_artifact_key="normalized/source-1/wrong",
                ),
            ),
        )
        with self.assertRaises(ImageCopyFailed):
            self.store.copy_processed(
                self.snapshot,
                tampered,
                lambda _path: None,
                import_lock=self._lock(),
            )

    def test_pa_rm20_collection_provenance_mismatch_is_rejected(self) -> None:
        plan = self._plan()
        photos = self.store.copy_processed(
            self.snapshot,
            plan,
            lambda _path: None,
            import_lock=self._lock(),
        )
        original = photos["source-1"][0]
        mismatched = ItemPhoto(
            path=original.path,
            role=original.role,
            capture_import_media=replace(
                original.capture_import_media,
                artifact_key="normalized/source-1/wrong",
            ),
        )
        with self.assertRaises(ValueError):
            self.store.validate_processed_photos(
                plan, {"source-1": (mismatched,)}
            )


class Schema3GenesisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.collection = CoinCollection(str(self.root / "collection.json"))
        self.journals = Schema3PackageImportJournalRepository(
            self.root / "journals"
        )
        self.images = ManagedCollectionImageStore(self.root / "images")
        self.payload, _descriptor, self.manifest, self.package = _fixture()
        self.processed = FakeProcessedSnapshot(self.payload, self.manifest)
        self.raw = FakeRawSnapshot()
        self.preview = SimpleNamespace(
            package_sha256=self.package.package_sha256,
            package_byte_length=self.package.package_byte_length,
            package_basename=self.package.package_basename,
            proposals=(SimpleNamespace(source_coin_id="source-1"),),
            collection_baseline=SimpleNamespace(
                sha256_or_sentinel="MISSING_COLLECTION_V1",
                byte_length=0,
            ),
        )

    def _service(self) -> Schema3PackageImportTransactionService:
        identifiers = iter((_uuid(), _uuid(), _uuid(), _uuid()))
        runtime = Mock()

        def finish_foreground(journal, raw, processed, *_args):
            raw.preserve_for_recovery()
            processed.close()
            return journal

        runtime.progress_foreground_locked.side_effect = finish_foreground
        return Schema3PackageImportTransactionService(
            self.collection,
            lock_path=self.root / "global.lock",
            journals=self.journals,
            image_store=self.images,
            clock=lambda: "2026-07-23T12:00:00Z",
            identifier_factory=lambda: next(identifiers),
            ownership_token_factory=_uuid,
            runtime=runtime,
        )

    @staticmethod
    def _decisions(selected: bool):
        return (
            SimpleNamespace(
                source_coin_id="source-1",
                decision=(
                    DuplicateDecision.IMPORT_AS_NEW
                    if selected
                    else DuplicateDecision.SKIP
                ),
            ),
        )

    def _execute(self, *, selected: bool):
        with (
            patch(
                "capture_import.transaction.ImportDecisionModel.validate"
            ),
            patch(
                "capture_import.transaction.CapturePackageValidator.validate_snapshot",
                return_value=self.package,
            ),
            patch("capture_import.transaction.require_collection_baseline"),
        ):
            return self._service().execute_genesis(
                self.raw,
                self.processed,
                self.package,
                self.preview,
                self._decisions(selected),
            )

    def test_schema3_prepared_genesis_contains_complete_commitments(self) -> None:
        result = self._execute(selected=True)
        self.assertIsInstance(result, Schema3TransactionGenesisResult)
        journal = result.journal
        self.assertEqual(journal.journal_schema_version, "3.0")
        self.assertEqual(journal.selected_source_coin_ids, ("source-1",))
        self.assertEqual(len(journal.expected_image_inventory), 1)
        self.assertEqual(
            journal.processed_snapshot_reference.processed_snapshot_id,
            self.manifest.processed_snapshot_id,
        )
        self.assertEqual(
            journal.processed_media_commitment.source_package_sha256,
            self.package.package_sha256,
        )
        self.assertTrue(self.processed.closed)
        self.assertTrue(self.raw.preserved)

    def test_pa_rm13_zero_selection_is_no_journal_processed_then_raw_cleanup(self) -> None:
        order: list[str] = []
        self.processed.cleanup = lambda: (
            order.append("processed"),
            setattr(self.processed, "cleaned", True),
        )
        self.raw.cleanup = lambda: (
            order.append("raw"),
            setattr(self.raw, "cleaned", True),
        )
        result = self._execute(selected=False)
        self.assertIsInstance(result, PackageImportExecutionResult)
        self.assertEqual(result.status, ImportResult.SUCCEEDED)
        self.assertEqual(order, ["processed", "raw"])
        self.assertFalse((self.root / "journals").exists())

    def test_zero_selection_cleanup_failure_is_not_retried(self) -> None:
        cleanup_calls = 0

        def fail_processed_cleanup() -> None:
            nonlocal cleanup_calls
            cleanup_calls += 1
            raise OSError("simulated processed cleanup failure")

        self.processed.cleanup = fail_processed_cleanup
        with self.assertRaises(OSError):
            self._execute(selected=False)
        self.assertEqual(cleanup_calls, 1)
        self.assertFalse(self.raw.cleaned)
        self.assertFalse((self.root / "journals").exists())

    def test_pa_rm14_under_lock_failure_creates_no_journal_or_images(self) -> None:
        self.processed.fail_validation = True
        with self.assertRaises(ValueError):
            self._execute(selected=True)
        self.assertTrue(self.processed.cleaned)
        self.assertTrue(self.raw.cleaned)
        self.assertFalse((self.root / "journals").exists())
        self.assertFalse((self.root / "images").exists())

    def test_package_processed_linkage_mismatch_fails_before_genesis(self) -> None:
        self.processed.manifest = replace(
            self.processed.manifest,
            source_package_sha256="e" * 64,
        )
        with self.assertRaises(PackageChanged):
            self._execute(selected=True)
        self.assertTrue(self.processed.cleaned)
        self.assertTrue(self.raw.cleaned)
        self.assertFalse((self.root / "journals").exists())

    def test_pa_rm42_publication_start_preserves_both_snapshots(self) -> None:
        with (
            patch(
                "capture_import.transaction.ImportDecisionModel.validate"
            ),
            patch(
                "capture_import.transaction.CapturePackageValidator.validate_snapshot",
                return_value=self.package,
            ),
            patch("capture_import.transaction.require_collection_baseline"),
            patch.object(
                self.journals,
                "create",
                side_effect=RecoveryRequired(),
            ),
        ):
            service = self._service()
            service._schema3_journals = self.journals
            with self.assertRaises(RecoveryRequired):
                service.execute_genesis(
                    self.raw,
                    self.processed,
                    self.package,
                    self.preview,
                    self._decisions(True),
                )
        self.assertTrue(self.processed.closed)
        self.assertTrue(self.raw.preserved)
        self.assertFalse(self.processed.cleaned)
        self.assertFalse(self.raw.cleaned)

    def test_authoritative_global_lock_is_acquired_exactly_once(self) -> None:
        original = PackageImportLock.acquire
        with (
            patch(
                "capture_import.transaction.ImportDecisionModel.validate"
            ),
            patch(
                "capture_import.transaction.CapturePackageValidator.validate_snapshot",
                return_value=self.package,
            ),
            patch("capture_import.transaction.require_collection_baseline"),
            patch(
                "capture_import.transaction.PackageImportLock.acquire",
                wraps=original,
            ) as acquire,
        ):
            self._service().execute_genesis(
                self.raw,
                self.processed,
                self.package,
                self.preview,
                self._decisions(True),
            )
        acquire.assert_called_once()

    def test_coordinator_handoff_is_exactly_once(self) -> None:
        result = Mock(spec=Schema3TransactionGenesisResult)
        processed_transaction = Mock(spec=Schema3PackageImportTransactionService)
        processed_transaction.execute_genesis.return_value = result
        coordinator = PackageImportCoordinator(
            collection_path=self.root / "collection.json",
            snapshots=Mock(),
            journals=Mock(),
            transaction=Mock(),
            processed_snapshots=Mock(),
            processed_transaction=processed_transaction,
        )
        prepared = PreparedPackageImport(
            snapshot=self.raw,
            package=self.package,
            preview=self.preview,
            processed_snapshot=self.processed,
        )
        decisions = self._decisions(True)
        self.assertIs(coordinator.commit(prepared, decisions), result)
        processed_transaction.execute_genesis.assert_called_once_with(
            self.raw,
            self.processed,
            self.package,
            self.preview,
            decisions,
        )
        with self.assertRaises(PackageChanged):
            coordinator.commit(prepared, decisions)
        self.assertEqual(processed_transaction.execute_genesis.call_count, 1)


if __name__ == "__main__":
    unittest.main()
