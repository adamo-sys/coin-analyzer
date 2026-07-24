"""Sprint 8 Unit 7D-A Schema 3 durable contracts and repository tests."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from capture_import._json import canonical_json_bytes
from capture_import.durable_models import (
    CleanupOperationV3,
    CleanupReceipt,
    ExpectedImageV3,
    JournalOwnerRecord,
    JournalOwnerRecordV2,
    NativeObjectIdentity,
    OperationalJournalGeneration,
    OperationalJournalGenerationV3,
    OwnershipDescriptorV3,
    ProcessedMediaCommitment,
    ProcessedMediaMappingEntry,
    ProcessedSnapshotReference,
    processed_media_mapping_sha256,
)
from capture_import.durable_repository import (
    Schema2PackageImportJournalRepository,
    Schema3PackageImportJournalRepository,
    VersionedPackageImportJournalRepository,
)
from capture_import.enums import CleanupStatus, ErrorCategory, ImportPhase
from capture_import.errors import JournalCorrupt, RecoveryRequired
from capture_import.limits import (
    MAX_CLEANUP_OPERATIONS_V3,
    MAX_CLEANUP_TARGETS_V3,
    PROCESSED_DURABLE_JOURNAL_SCHEMA_VERSION,
    PROCESSED_JOURNAL_OWNER_SCHEMA_VERSION,
    PROCESSED_MEDIA_COMMITMENT_SCHEMA_VERSION,
)
from capture_import.lock import PackageImportLock


def _uuid() -> str:
    return str(uuid4())


def _identity() -> NativeObjectIdentity:
    return NativeObjectIdentity("POSIX", "1", "2")


def _reference(snapshot_id: str, workflow_id: str) -> ProcessedSnapshotReference:
    root = f"processed-snapshots/{snapshot_id}"
    return ProcessedSnapshotReference(
        processed_snapshot_id=snapshot_id,
        workflow_execution_id=workflow_id,
        root_relative_path=root,
        manifest_relative_path=f"{root}/manifest.json",
        completion_relative_path=f"{root}/complete.json",
        manifest_byte_length=101,
        completion_byte_length=102,
        manifest_sha256="c" * 64,
        completion_sha256="e" * 64,
        artifact_count=1,
        aggregate_byte_length=12,
        artifact_inventory_sha256="d" * 64,
    )


def _mapping() -> tuple[ProcessedMediaMappingEntry, ...]:
    return (
        ProcessedMediaMappingEntry(
            source_coin_id="source-1",
            role="front",
            artifact_key="normalized/source-1/front",
            artifact_sha256="b" * 64,
            variant="NORMALIZED",
        ),
    )


def _commitment(snapshot_id: str) -> ProcessedMediaCommitment:
    mapping = _mapping()
    return ProcessedMediaCommitment(
        commitment_schema_version="1.0",
        processed_snapshot_id_sha256=sha256(snapshot_id.encode("utf-8")).hexdigest(),
        source_package_sha256="a" * 64,
        artifact_count=1,
        aggregate_byte_length=12,
        artifact_inventory_sha256="d" * 64,
        manifest_sha256="c" * 64,
        ordered_mapping=mapping,
        persisted_mapping_sha256=processed_media_mapping_sha256(mapping),
    )


def _generation(
    *,
    import_id: str | None = None,
    owner: str | None = None,
    snapshot_id: str | None = None,
    workflow_id: str | None = None,
) -> OperationalJournalGenerationV3:
    import_id = import_id or _uuid()
    snapshot_id = snapshot_id or _uuid()
    workflow_id = workflow_id or _uuid()
    reference = _reference(snapshot_id, workflow_id)
    return OperationalJournalGenerationV3(
        journal_schema_version="3.0",
        import_id=import_id,
        random_ownership_token=owner or _uuid(),
        generation=0,
        previous_generation_sha256=None,
        transition_id=_uuid(),
        next_generation_token=_uuid(),
        phase=ImportPhase.PREPARED,
        resume_phase=None,
        created_at="2026-07-23T12:00:00Z",
        updated_at="2026-07-23T12:00:00Z",
        package_sha256="a" * 64,
        package_version="1.0",
        package_basename="test.ca-package",
        snapshot_byte_length=123,
        package_snapshot_relative_path="snapshots/test/package.ca-package",
        processed_snapshot_reference=reference,
        processed_media_commitment=_commitment(snapshot_id),
        collection_baseline_sha256_or_sentinel="MISSING_COLLECTION_V1",
        collection_baseline_byte_length=0,
        prospective_collection_byte_length=None,
        prospective_collection_sha256=None,
        selected_source_coin_ids=("source-1",),
        desktop_item_ids=(_uuid(),),
        import_root_relative_path=f"imports/{import_id}",
        expected_image_inventory=(
            ExpectedImageV3(
                relative_path=f"imports/{import_id}/coin/front.jpg",
                role="front",
                byte_length=12,
                sha256="b" * 64,
                media_type="image/jpeg",
                width=10,
                height=10,
                source_kind="PROCESSED_SNAPSHOT",
                source_snapshot_id=snapshot_id,
                source_coin_id="source-1",
                source_artifact_key="normalized/source-1/front",
                variant="NORMALIZED",
            ),
        ),
        verified_image_inventory=(),
        committed_collection_item_ids=(),
        proposed_count=1,
        imported_count=0,
        skipped_count=0,
        collection_publication="NONE",
        collection_temporary_artifact=None,
        collection_backup_artifact=None,
        cleanup_operations=(),
        pending_terminal_audit=None,
        compaction=None,
        error_category=None,
        recovery_attempt_count=0,
    )


def _successor(
    previous: OperationalJournalGenerationV3,
    **changes,
) -> OperationalJournalGenerationV3:
    values = {
        "generation": previous.generation + 1,
        "previous_generation_sha256": sha256(
            canonical_json_bytes(previous.to_dict())
        ).hexdigest(),
        "transition_id": _uuid(),
        "next_generation_token": _uuid(),
        "updated_at": "2026-07-23T12:00:01Z",
    }
    values.update(changes)
    return replace(previous, **values)


class Schema3DurableModelTests(unittest.TestCase):
    def test_frozen_versions_and_effective_field_sets(self) -> None:
        generation = _generation()
        self.assertEqual(PROCESSED_DURABLE_JOURNAL_SCHEMA_VERSION, "3.0")
        self.assertEqual(PROCESSED_JOURNAL_OWNER_SCHEMA_VERSION, "2.0")
        self.assertEqual(PROCESSED_MEDIA_COMMITMENT_SCHEMA_VERSION, "1.0")
        self.assertEqual(frozenset(generation.to_dict()), generation.FIELDS)
        self.assertNotIn("snapshot_relative_path", generation.FIELDS)
        self.assertIn("package_snapshot_relative_path", generation.FIELDS)
        self.assertIn("processed_snapshot_reference", generation.FIELDS)
        self.assertIn("processed_media_commitment", generation.FIELDS)

    def test_closed_models_reject_missing_and_extra_fields(self) -> None:
        values = _generation().to_dict()
        for mutation in (
            lambda item: item.pop("processed_media_commitment"),
            lambda item: item.update({"unknown": True}),
        ):
            candidate = dict(values)
            mutation(candidate)
            with self.assertRaises(ValueError):
                OperationalJournalGenerationV3.from_dict(candidate)
        reference = _reference(_uuid(), _uuid()).to_dict()
        reference["unknown"] = True
        with self.assertRaises(ValueError):
            ProcessedSnapshotReference.from_dict(reference)

    def test_canonical_round_trip_is_byte_stable(self) -> None:
        generation = _generation()
        payload = canonical_json_bytes(generation.to_dict())
        loaded = OperationalJournalGenerationV3.from_dict(json.loads(payload))
        self.assertEqual(loaded, generation)
        self.assertEqual(canonical_json_bytes(loaded.to_dict()), payload)

    def test_mapping_and_commitment_digests_are_deterministic(self) -> None:
        mapping = _mapping()
        expected = sha256(
            b"coin-analyzer.processed-media-mapping.v1\0"
            + canonical_json_bytes([item.to_dict() for item in mapping])
        ).hexdigest()
        self.assertEqual(processed_media_mapping_sha256(mapping), expected)
        commitment = _commitment(_uuid())
        commitment.validate()
        with self.assertRaises(ValueError):
            replace(commitment, persisted_mapping_sha256="0" * 64).validate()

    def test_actual_schema3_inventories_must_be_non_empty(self) -> None:
        generation = _generation()
        with self.assertRaises(ValueError):
            replace(generation, selected_source_coin_ids=()).validate()
        with self.assertRaises(ValueError):
            replace(generation, expected_image_inventory=()).validate()

    def test_processed_reference_and_commitment_must_match(self) -> None:
        generation = _generation()
        with self.assertRaises(ValueError):
            replace(
                generation,
                processed_media_commitment=replace(
                    generation.processed_media_commitment,
                    manifest_sha256="f" * 64,
                ),
            ).validate()

    def test_cleanup_bounds_are_exact(self) -> None:
        self.assertEqual(MAX_CLEANUP_OPERATIONS_V3, 4)
        self.assertEqual(MAX_CLEANUP_TARGETS_V3, 1024)
        token = _uuid()
        targets = tuple(
            OwnershipDescriptorV3(
                root="PROCESSED_SNAPSHOT",
                relative_path=f"artifacts/{index:04d}.jpg",
                object_kind="FILE",
                ownership_token=token,
                expected_byte_length=1,
                expected_sha256="a" * 64,
                parent_identity=_identity(),
                object_identity=_identity(),
            )
            for index in range(MAX_CLEANUP_TARGETS_V3)
        )
        operation = CleanupOperationV3(
            kind="SUCCESS_PROCESSED_SNAPSHOT",
            intent_id=_uuid(),
            intent_generation=1,
            targets=targets,
            receipts=(),
            status=CleanupStatus.INTENT,
            completed_generation=None,
        )
        operation.validate()
        with self.assertRaises(ValueError):
            replace(
                operation,
                targets=operation.targets
                + (
                    replace(
                        operation.targets[-1],
                        relative_path="artifacts/overflow.jpg",
                    ),
                ),
            ).validate()

    def test_all_twelve_processed_failure_categories_are_closed(self) -> None:
        expected = {
            "PROCESSED_CONTRACT_VIOLATION",
            "PROCESSED_CONTAINMENT_VIOLATION",
            "PROCESSED_DIGEST_MISMATCH",
            "PROCESSED_SIZE_MISMATCH",
            "UNSUPPORTED_PROCESSED_SNAPSHOT_VERSION",
            "DUPLICATE_PROCESSED_ARTIFACT",
            "PROCESSED_ARTIFACT_MISSING",
            "PROCESSED_OWNERSHIP_LOST",
            "PROCESSED_SOURCE_MUTATION",
            "PROCESSED_JOURNAL_INCONSISTENCY",
            "PROCESSED_CLEANUP_FAILED",
            "PROCESSED_RECOVERY_REQUIRED",
        }
        actual = {item.value for item in ErrorCategory if item.value in expected}
        self.assertEqual(actual, expected)

    def test_schema2_and_schema3_cross_parsers_reject(self) -> None:
        schema3 = _generation().to_dict()
        with self.assertRaises(ValueError):
            OperationalJournalGeneration.from_dict(schema3)
        schema2 = _generation().schema2_projection().to_dict()
        with self.assertRaises(ValueError):
            OperationalJournalGenerationV3.from_dict(schema2)
        owner2 = JournalOwnerRecordV2(
            "2.0",
            "3.0",
            _uuid(),
            _uuid(),
            "2026-07-23T12:00:00Z",
            f"00000000-{_uuid()}.json",
            "a" * 64,
            _uuid(),
            f".next-00000000-{_uuid()}.tmp",
        )
        with self.assertRaises(ValueError):
            JournalOwnerRecord.from_dict(owner2.to_dict())

    def test_schema2_serialized_field_set_and_round_trip_are_unchanged(self) -> None:
        schema2 = _generation().schema2_projection()
        payload = canonical_json_bytes(schema2.to_dict())
        loaded = OperationalJournalGeneration.from_dict(json.loads(payload))
        self.assertEqual(canonical_json_bytes(loaded.to_dict()), payload)
        self.assertNotIn("processed_snapshot_reference", loaded.to_dict())
        self.assertNotIn("processed_media_commitment", loaded.to_dict())
        self.assertIn("snapshot_relative_path", loaded.to_dict())


class Schema3RepositoryTests(unittest.TestCase):
    def _lock(self, import_id: str | None) -> PackageImportLock:
        lock = PackageImportLock.acquire(
            Path(tempfile.gettempdir()) / f"{_uuid()}.lock",
            import_id=import_id,
        )
        self.addCleanup(lock.release)
        return lock

    def test_owner2_and_generation3_publication_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            generation = _generation()
            lock = self._lock(generation.import_id)
            repository = Schema3PackageImportJournalRepository(
                Path(root) / "journals",
                token_factory=lambda: _uuid(),
            )
            self.assertEqual(
                repository.create(generation, import_lock=lock), generation
            )
            owner = json.loads(
                (
                    Path(root)
                    / "journals"
                    / generation.import_id
                    / "owner.json"
                ).read_bytes()
            )
            self.assertEqual(owner["owner_schema_version"], "2.0")
            self.assertEqual(owner["journal_schema_version"], "3.0")
            self.assertEqual(repository.load(generation.import_id, import_lock=lock), generation)
            before = tuple(
                sorted(
                    path.name
                    for path in (
                        Path(root) / "journals" / generation.import_id
                    ).iterdir()
                )
            )
            with self.assertRaises(JournalCorrupt):
                repository.create(generation, import_lock=lock)
            after = tuple(
                sorted(
                    path.name
                    for path in (
                        Path(root) / "journals" / generation.import_id
                    ).iterdir()
                )
            )
            self.assertEqual(after, before)

    def test_allowed_transition_appends_and_forbidden_commitment_mutation_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            generation = _generation()
            lock = self._lock(generation.import_id)
            repository = Schema3PackageImportJournalRepository(Path(root) / "journals")
            current = repository.create(generation, import_lock=lock)
            copying = _successor(current, phase=ImportPhase.COPYING_IMAGES)
            current = repository.append(current, copying, import_lock=lock)
            forbidden = _successor(
                current,
                processed_media_commitment=replace(
                    current.processed_media_commitment,
                    aggregate_byte_length=13,
                ),
            )
            with self.assertRaises((JournalCorrupt, ValueError)):
                repository.append(current, forbidden, import_lock=lock)

    def test_processed_cleanup_completion_then_release_is_the_only_null_transition(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            generation = _generation()
            lock = self._lock(generation.import_id)
            repository = Schema3PackageImportJournalRepository(Path(root) / "journals")
            current = repository.create(generation, import_lock=lock)
            current = repository.append(
                current,
                _successor(current, phase=ImportPhase.ROLLING_BACK),
                import_lock=lock,
            )
            target = OwnershipDescriptorV3(
                root="PROCESSED_SNAPSHOT",
                relative_path="processed-snapshots/root",
                object_kind="DIRECTORY",
                ownership_token=_uuid(),
                expected_byte_length=None,
                expected_sha256=None,
                parent_identity=_identity(),
                object_identity=_identity(),
            )
            intent = CleanupOperationV3(
                kind="SUCCESS_PROCESSED_SNAPSHOT",
                intent_id=_uuid(),
                intent_generation=current.generation + 1,
                targets=(target,),
                receipts=(),
                status=CleanupStatus.INTENT,
                completed_generation=None,
            )
            current = repository.append(
                current,
                _successor(current, cleanup_operations=(intent,)),
                import_lock=lock,
            )
            with self.assertRaises(ValueError):
                replace(
                    _successor(current),
                    processed_snapshot_reference=None,
                ).validate()
            receipt = CleanupReceipt(
                target_relative_path=target.relative_path,
                removed_object_identity=target.object_identity,
                removal_generation=current.generation + 1,
            )
            receipted = replace(intent, receipts=(receipt,))
            current = repository.append(
                current,
                _successor(current, cleanup_operations=(receipted,)),
                import_lock=lock,
            )
            complete = replace(
                receipted,
                status=CleanupStatus.COMPLETE,
                completed_generation=current.generation + 1,
            )
            current = repository.append(
                current,
                _successor(current, cleanup_operations=(complete,)),
                import_lock=lock,
            )
            raw_target = replace(
                target,
                root="SNAPSHOT",
                relative_path="snapshots/root",
            )
            raw_intent = CleanupOperationV3(
                kind="SUCCESS_SNAPSHOT",
                intent_id=_uuid(),
                intent_generation=current.generation + 1,
                targets=(raw_target,),
                receipts=(),
                status=CleanupStatus.INTENT,
                completed_generation=None,
            )
            with self.assertRaises(ValueError):
                _successor(
                    current,
                    cleanup_operations=(complete, raw_intent),
                ).validate()
            released = _successor(current, processed_snapshot_reference=None)
            current = repository.append(current, released, import_lock=lock)
            self.assertIsNone(current.processed_snapshot_reference)
            self.assertEqual(
                current.processed_media_commitment,
                generation.processed_media_commitment,
            )
            raw_intent = replace(
                raw_intent,
                intent_generation=current.generation + 1,
            )
            current = repository.append(
                current,
                _successor(
                    current,
                    cleanup_operations=(complete, raw_intent),
                ),
                import_lock=lock,
            )
            self.assertEqual(current.cleanup_operations[-1], raw_intent)

    def test_valid_successor_candidate_is_reconciled(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            generation = _generation()
            lock = self._lock(generation.import_id)
            repository = Schema3PackageImportJournalRepository(Path(root) / "journals")
            current = repository.create(generation, import_lock=lock)
            candidate = _successor(current, phase=ImportPhase.COPYING_IMAGES)
            candidate_name = repository.temporary_name(
                candidate.generation, current.next_generation_token
            )
            directory = Path(root) / "journals" / current.import_id
            (directory / candidate_name).write_bytes(
                canonical_json_bytes(candidate.to_dict())
            )
            loaded = repository.load(current.import_id, import_lock=lock)
            self.assertEqual(loaded, candidate)
            self.assertFalse((directory / candidate_name).exists())
            self.assertTrue(
                (
                    directory
                    / repository.generation_name(
                        candidate.generation, candidate.transition_id
                    )
                ).exists()
            )

    def test_bounded_malformed_successor_candidate_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            generation = _generation()
            lock = self._lock(generation.import_id)
            repository = Schema3PackageImportJournalRepository(Path(root) / "journals")
            current = repository.create(generation, import_lock=lock)
            candidate_name = repository.temporary_name(
                1, current.next_generation_token
            )
            candidate = (
                Path(root) / "journals" / current.import_id / candidate_name
            )
            candidate.write_bytes(b'{"journal_schema_version":')
            loaded = repository.load(current.import_id, import_lock=lock)
            self.assertEqual(loaded, current)
            self.assertFalse(candidate.exists())

    def test_complete_mixed_version_successor_candidate_is_preserved_and_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            generation = _generation()
            lock = self._lock(generation.import_id)
            repository = Schema3PackageImportJournalRepository(Path(root) / "journals")
            current = repository.create(generation, import_lock=lock)
            candidate_name = repository.temporary_name(
                1, current.next_generation_token
            )
            schema2_candidate = replace(
                current.schema2_projection(),
                generation=1,
                previous_generation_sha256=sha256(
                    canonical_json_bytes(current.to_dict())
                ).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.COPYING_IMAGES,
                updated_at="2026-07-23T12:00:01Z",
            )
            candidate = (
                Path(root) / "journals" / current.import_id / candidate_name
            )
            candidate.write_bytes(canonical_json_bytes(schema2_candidate.to_dict()))
            with self.assertRaises(JournalCorrupt):
                repository.load(current.import_id, import_lock=lock)
            self.assertTrue(candidate.exists())

    def test_schema_specific_repositories_reject_mixed_versions(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            generation = _generation()
            lock = self._lock(generation.import_id)
            path = Path(root) / "journals"
            schema3 = Schema3PackageImportJournalRepository(path)
            schema3.create(generation, import_lock=lock)
            with self.assertRaises(JournalCorrupt):
                Schema2PackageImportJournalRepository(path).load(
                    generation.import_id, import_lock=lock
                )

    def test_versioned_dispatch_rejects_conflicting_owner_generation_identity(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            generation = _generation()
            lock = self._lock(generation.import_id)
            path = Path(root) / "journals"
            repository = VersionedPackageImportJournalRepository(path)
            repository.create(generation, import_lock=lock)
            owner_path = path / generation.import_id / "owner.json"
            owner = json.loads(owner_path.read_bytes())
            owner["owner_schema_version"] = "1.0"
            owner["journal_schema_version"] = "2.0"
            owner_path.write_bytes(canonical_json_bytes(owner))
            with self.assertRaises(JournalCorrupt):
                repository.load(generation.import_id, import_lock=lock)

    def test_versioned_dispatch_enumerates_distinct_schema2_and_schema3_ids(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            lock = self._lock(None)
            repository = VersionedPackageImportJournalRepository(
                Path(root) / "journals"
            )
            schema3 = _generation()
            schema2 = _generation(import_id=_uuid()).schema2_projection()
            repository.create(schema2, import_lock=lock)
            repository.create(schema3, import_lock=lock)
            heads = repository.list_heads(import_lock=lock)
            self.assertEqual(
                {type(item) for item in heads},
                {OperationalJournalGeneration, OperationalJournalGenerationV3},
            )
            self.assertEqual(
                {item.import_id for item in heads},
                {schema2.import_id, schema3.import_id},
            )

    def test_genesis_candidate_without_publication_is_reconciled(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            generation = _generation()
            lock = self._lock(generation.import_id)
            repository = Schema3PackageImportJournalRepository(Path(root) / "journals")
            original_publish = repository._write_and_publish

            def leave_candidate(directory, temporary_name, final_name, payload):
                repository._write_direct_exclusive(
                    directory, temporary_name, payload
                )
                raise RecoveryRequired()

            repository._write_and_publish = leave_candidate
            with self.assertRaises(RecoveryRequired):
                repository.create(generation, import_lock=lock)
            repository._write_and_publish = original_publish
            self.assertEqual(
                repository.load(generation.import_id, import_lock=lock),
                generation,
            )


if __name__ == "__main__":
    unittest.main()
