"""Sprint 5C schema-2 durability contract and repository tests."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from capture_import._json import canonical_json_bytes
from capture_import.durable_models import (
    CleanupOperation,
    CleanupReceipt,
    CollectionPublicationArtifact,
    ExpectedImageEvidence,
    NativeObjectIdentity,
    OperationalJournalGeneration,
    OwnershipDescriptor,
    VerifiedImageEvidence,
    validate_collection_publication_pair,
)
from capture_import.durable_repository import Schema2PackageImportJournalRepository
from capture_import.enums import CleanupStatus, CollectionPublicationState, ImportPhase
from capture_import.errors import JournalCorrupt, RecoveryRequired
from capture_import.lock import PackageImportLock


def _uuid() -> str:
    return str(uuid4())


def _identity() -> NativeObjectIdentity:
    return NativeObjectIdentity("POSIX", "1", "2")


def _generation(*, import_id: str, owner: str) -> OperationalJournalGeneration:
    return OperationalJournalGeneration(
        journal_schema_version="2.0",
        import_id=import_id,
        random_ownership_token=owner,
        generation=0,
        previous_generation_sha256=None,
        transition_id=_uuid(),
        next_generation_token=_uuid(),
        phase=ImportPhase.PREPARED,
        resume_phase=None,
        created_at="2026-07-20T12:00:00Z",
        updated_at="2026-07-20T12:00:00Z",
        package_sha256="a" * 64,
        package_version="1.0",
        package_basename="test.ca-package",
        snapshot_byte_length=123,
        snapshot_relative_path="snapshots/test/package.ca-package",
        collection_baseline_sha256_or_sentinel="MISSING_COLLECTION_V1",
        collection_baseline_byte_length=0,
        prospective_collection_byte_length=None,
        prospective_collection_sha256=None,
        selected_source_coin_ids=("source-1",),
        desktop_item_ids=(_uuid(),),
        import_root_relative_path="imports/test",
        expected_image_inventory=(
            ExpectedImageEvidence(
                relative_path="imports/test/front.jpg",
                role="front",
                byte_length=12,
                sha256="b" * 64,
                media_type="image/jpeg",
                width=10,
                height=10,
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


def _fully_receipted_cleanup() -> CleanupOperation:
    target = OwnershipDescriptor(
        root="SNAPSHOT",
        relative_path="snapshot/package.ca-package",
        object_kind="FILE",
        ownership_token=_uuid(),
        expected_byte_length=12,
        expected_sha256="c" * 64,
        parent_identity=_identity(),
        object_identity=_identity(),
    )
    return CleanupOperation(
        kind="SUCCESS_SNAPSHOT",
        intent_id=_uuid(),
        intent_generation=2,
        targets=(target,),
        receipts=(
            CleanupReceipt(
                target_relative_path=target.relative_path,
                removed_object_identity=target.object_identity,
                removal_generation=3,
            ),
        ),
        status=CleanupStatus.INTENT,
        completed_generation=None,
    )


class DurableContractTests(unittest.TestCase):
    def _lock(self, import_id: str) -> PackageImportLock:
        lock = PackageImportLock.acquire(
            Path(tempfile.gettempdir()) / f"{_uuid()}.lock",
            import_id=import_id,
        )
        self.addCleanup(lock.release)
        return lock

    def _verified_image(self, expected: ExpectedImageEvidence) -> VerifiedImageEvidence:
        return VerifiedImageEvidence(
            relative_path=expected.relative_path,
            role=expected.role,
            byte_length=expected.byte_length,
            sha256=expected.sha256,
            media_type=expected.media_type,
            width=expected.width,
            height=expected.height,
            parent_identity=_identity(),
            object_identity=_identity(),
        )

    def _build_committing_collection(
        self, repository: Schema2PackageImportJournalRepository, genesis: OperationalJournalGeneration, import_lock: PackageImportLock
    ) -> OperationalJournalGeneration:
        """Build a chain: PREPARED -> COPYING_IMAGES -> FILES_READY -> COMMITTING_COLLECTION."""
        current = genesis
        # PREPARED -> COPYING_IMAGES
        next_gen = replace(
            current,
            generation=current.generation + 1,
            previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
            transition_id=_uuid(),
            next_generation_token=_uuid(),
            phase=ImportPhase.COPYING_IMAGES,
            updated_at="2026-07-20T12:00:01Z",
        )
        current = repository.append(current, next_gen, import_lock=import_lock)

        # Same-phase: add verified image
        image = self._verified_image(current.expected_image_inventory[0])
        next_gen = replace(
            current,
            generation=current.generation + 1,
            previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
            transition_id=_uuid(),
            next_generation_token=_uuid(),
            verified_image_inventory=(image,),
            updated_at="2026-07-20T12:00:02Z",
        )
        current = repository.append(current, next_gen, import_lock=import_lock)

        # COPYING_IMAGES -> FILES_READY
        next_gen = replace(
            current,
            generation=current.generation + 1,
            previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
            transition_id=_uuid(),
            next_generation_token=_uuid(),
            phase=ImportPhase.FILES_READY,
            updated_at="2026-07-20T12:00:03Z",
        )
        current = repository.append(current, next_gen, import_lock=import_lock)

        # FILES_READY -> COMMITTING_COLLECTION
        prospective = b'[{"id": "' + current.desktop_item_ids[0].encode() + b'"}]'
        artifact = CollectionPublicationArtifact(
            kind="TEMPORARY",
            relative_name=".collection-test.tmp",
            token=_uuid(),
            relationship="PROSPECTIVE_BYTES",
            expected_byte_length=len(prospective),
            expected_sha256=sha256(prospective).hexdigest(),
            expected_parent_identity=_identity(),
            state=CollectionPublicationState.PLANNED,
        )
        next_gen = replace(
            current,
            generation=current.generation + 1,
            previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
            transition_id=_uuid(),
            next_generation_token=_uuid(),
            phase=ImportPhase.COMMITTING_COLLECTION,
            prospective_collection_byte_length=len(prospective),
            prospective_collection_sha256=sha256(prospective).hexdigest(),
            collection_publication="INTENT",
            collection_temporary_artifact=artifact,
            updated_at="2026-07-20T12:00:04Z",
        )
        current = repository.append(current, next_gen, import_lock=import_lock)
        return current

    def test_recovery_required_transition_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            repository = Schema2PackageImportJournalRepository(Path(root) / "journals")
            genesis = _generation(import_id=_uuid(), owner=_uuid())
            import_lock = self._lock(genesis.import_id)
            current = repository.create(genesis, import_lock=import_lock)

            recovery = replace(
                current,
                generation=1,
                previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.RECOVERY_REQUIRED,
                resume_phase=ImportPhase.PREPARED,
                error_category="RECOVERY_REQUIRED",
                recovery_attempt_count=1,
                updated_at="2026-07-20T12:00:01Z",
            )
            result = repository.append(current, recovery, import_lock=import_lock)
            self.assertEqual(result.phase, ImportPhase.RECOVERY_REQUIRED)
            self.assertEqual(result.resume_phase, ImportPhase.PREPARED)
            self.assertEqual(result.error_category, "RECOVERY_REQUIRED")

    def test_rollback_failed_transition_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            repository = Schema2PackageImportJournalRepository(Path(root) / "journals")
            genesis = _generation(import_id=_uuid(), owner=_uuid())
            import_lock = self._lock(genesis.import_id)
            current = repository.create(genesis, import_lock=import_lock)

            # PREPARED -> ROLLING_BACK
            rolling = replace(
                current,
                generation=1,
                previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.ROLLING_BACK,
                updated_at="2026-07-20T12:00:01Z",
            )
            current = repository.append(current, rolling, import_lock=import_lock)

            # ROLLING_BACK -> ROLLBACK_FAILED
            failed = replace(
                current,
                generation=2,
                previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.ROLLBACK_FAILED,
                resume_phase=ImportPhase.ROLLING_BACK,
                error_category="ROLLBACK_FAILED",
                recovery_attempt_count=1,
                updated_at="2026-07-20T12:00:02Z",
            )
            result = repository.append(current, failed, import_lock=import_lock)
            self.assertEqual(result.phase, ImportPhase.ROLLBACK_FAILED)
            self.assertEqual(result.resume_phase, ImportPhase.ROLLING_BACK)

    def test_recovery_required_same_phase_increments_attempt_counter(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            repository = Schema2PackageImportJournalRepository(Path(root) / "journals")
            genesis = _generation(import_id=_uuid(), owner=_uuid())
            import_lock = self._lock(genesis.import_id)
            current = repository.create(genesis, import_lock=import_lock)

            recovery = replace(
                current,
                generation=1,
                previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.RECOVERY_REQUIRED,
                resume_phase=ImportPhase.PREPARED,
                error_category="RECOVERY_REQUIRED",
                recovery_attempt_count=1,
                updated_at="2026-07-20T12:00:01Z",
            )
            current = repository.append(current, recovery, import_lock=import_lock)

            retry = replace(
                current,
                generation=2,
                previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                recovery_attempt_count=2,
                updated_at="2026-07-20T12:00:02Z",
            )
            result = repository.append(current, retry, import_lock=import_lock)
            self.assertEqual(result.recovery_attempt_count, 2)

    def test_recovery_required_to_rolling_back_replay(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            repository = Schema2PackageImportJournalRepository(Path(root) / "journals")
            genesis = _generation(import_id=_uuid(), owner=_uuid())
            import_lock = self._lock(genesis.import_id)
            current = repository.create(genesis, import_lock=import_lock)

            # Enter recovery
            recovery = replace(
                current,
                generation=1,
                previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.RECOVERY_REQUIRED,
                resume_phase=ImportPhase.PREPARED,
                error_category="RECOVERY_REQUIRED",
                recovery_attempt_count=1,
                updated_at="2026-07-20T12:00:01Z",
            )
            current = repository.append(current, recovery, import_lock=import_lock)

            # Exit to ROLLING_BACK
            rollback = replace(
                current,
                generation=2,
                previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.ROLLING_BACK,
                resume_phase=None,
                error_category=None,
                pending_terminal_audit={"audit_schema_version": "2.0"},
                updated_at="2026-07-20T12:00:02Z",
            )
            result = repository.append(current, rollback, import_lock=import_lock)
            self.assertEqual(result.phase, ImportPhase.ROLLING_BACK)
            self.assertIsNone(result.resume_phase)
            self.assertIsNone(result.error_category)

    def test_recovery_required_to_collection_committed_replay(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            repository = Schema2PackageImportJournalRepository(Path(root) / "journals")
            genesis = _generation(import_id=_uuid(), owner=_uuid())
            import_lock = self._lock(genesis.import_id)
            current = repository.create(genesis, import_lock=import_lock)

            # Build chain up to COMMITTING_COLLECTION
            current = self._build_committing_collection(repository, current, import_lock)

            # COMMITTING_COLLECTION -> RECOVERY_REQUIRED
            recovery = replace(
                current,
                generation=current.generation + 1,
                previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.RECOVERY_REQUIRED,
                resume_phase=ImportPhase.COMMITTING_COLLECTION,
                error_category="RECOVERY_REQUIRED",
                recovery_attempt_count=1,
                updated_at="2026-07-20T12:00:05Z",
            )
            current = repository.append(current, recovery, import_lock=import_lock)

            # RECOVERY_REQUIRED -> COLLECTION_COMMITTED
            artifact = current.collection_temporary_artifact
            assert artifact is not None
            published_artifact = replace(
                artifact,
                state=CollectionPublicationState.PUBLISHED,
                object_identity=_identity(),
                verified_byte_length=artifact.expected_byte_length,
                verified_sha256=artifact.expected_sha256,
                verified_generation=current.generation,
                published_relative_name="collection.json",
                publication_generation=current.generation + 1,
            )
            committed = replace(
                current,
                generation=current.generation + 1,
                previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.COLLECTION_COMMITTED,
                resume_phase=None,
                error_category=None,
                collection_publication="VERIFIED",
                collection_temporary_artifact=published_artifact,
                committed_collection_item_ids=current.desktop_item_ids,
                imported_count=1,
                pending_terminal_audit={"audit_schema_version": "2.0"},
                updated_at="2026-07-20T12:00:06Z",
            )
            result = repository.append(current, committed, import_lock=import_lock)
            self.assertEqual(result.phase, ImportPhase.COLLECTION_COMMITTED)
            self.assertIsNone(result.resume_phase)
            self.assertIsNone(result.error_category)
            self.assertEqual(result.committed_collection_item_ids, result.desktop_item_ids)

    def test_rollback_failed_to_rolling_back_replay(self) -> None:
            artifact = current.collection_temporary_artifact
            assert artifact is not None
            print(f"DEBUG artifact expected_byte_length={artifact.expected_byte_length}, expected_sha256={artifact.expected_sha256}")
            published_artifact = replace(
                artifact,
                state=CollectionPublicationState.PUBLISHED,
                object_identity=_identity(),
                verified_byte_length=artifact.expected_byte_length,
                verified_sha256=artifact.expected_sha256,
                verified_generation=current.generation,
                published_relative_name="collection.json",
                publication_generation=current.generation + 1,
            )
            print(f"DEBUG published verified_byte_length={published_artifact.verified_byte_length}, verified_sha256={published_artifact.verified_sha256}, verified_generation={published_artifact.verified_generation}")
            print(f"DEBUG published expected_byte_length={published_artifact.expected_byte_length}, expected_sha256={published_artifact.expected_sha256}")
            print(f"DEBUG match byte_length={published_artifact.verified_byte_length == published_artifact.expected_byte_length}")
            print(f"DEBUG match sha256={published_artifact.verified_sha256 == published_artifact.expected_sha256}")
            try:
                published_artifact.validate()
                print("DEBUG published artifact validates OK")
            except Exception as e:
                print(f"DEBUG published artifact validation FAILED: {e}")
            committed = replace(
                current,
                generation=current.generation + 1,
                previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.COLLECTION_COMMITTED,
                resume_phase=None,
                error_category=None,
                collection_publication="VERIFIED",
                collection_temporary_artifact=published_artifact,
                committed_collection_item_ids=current.desktop_item_ids,
                imported_count=1,
                pending_terminal_audit={"audit_schema_version": "2.0"},
                updated_at="2026-07-20T12:00:06Z",
            )
            print(f"DEBUG committed artifact: {committed.collection_temporary_artifact}")
            try:
                committed.validate()
                print("DEBUG committed validates OK")
            except Exception as e:
                print(f"DEBUG committed validation FAILED: {e}")
            result = repository.append(current, committed, import_lock=import_lock)
            self.assertEqual(result.phase, ImportPhase.COLLECTION_COMMITTED)
            self.assertIsNone(result.resume_phase)
            self.assertIsNone(result.error_category)
            self.assertEqual(result.committed_collection_item_ids, result.desktop_item_ids)
            artifact = current.collection_temporary_artifact
            assert artifact is not None
            published_artifact = replace(
                artifact,
                state=CollectionPublicationState.PUBLISHED,
                object_identity=_identity(),
                verified_byte_length=artifact.expected_byte_length,
                verified_sha256=artifact.expected_sha256,
                verified_generation=current.generation,
                published_relative_name="collection.json",
                publication_generation=current.generation + 1,
            )
            artifact = current.collection_temporary_artifact
            assert artifact is not None
            published_artifact = replace(
                artifact,
                state=CollectionPublicationState.PUBLISHED,
                object_identity=_identity(),
                published_relative_name="collection.json",
                publication_generation=current.generation + 1,
            )
            committed = replace(
                current,
                generation=current.generation + 1,
                previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.COLLECTION_COMMITTED,
                resume_phase=None,
                error_category=None,
                collection_publication="VERIFIED",
                collection_temporary_artifact=published_artifact,
                committed_collection_item_ids=current.desktop_item_ids,
                imported_count=1,
                pending_terminal_audit={"audit_schema_version": "2.0"},
                updated_at="2026-07-20T12:00:06Z",
            )
            result = repository.append(current, committed, import_lock=import_lock)
            self.assertEqual(result.phase, ImportPhase.COLLECTION_COMMITTED)
            self.assertIsNone(result.resume_phase)
            self.assertIsNone(result.error_category)
            self.assertEqual(result.committed_collection_item_ids, result.desktop_item_ids)

    def test_rollback_failed_to_rolling_back_replay(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            repository = Schema2PackageImportJournalRepository(Path(root) / "journals")
            genesis = _generation(import_id=_uuid(), owner=_uuid())
            import_lock = self._lock(genesis.import_id)
            current = repository.create(genesis, import_lock=import_lock)

            # PREPARED -> ROLLING_BACK
            rolling = replace(
                current,
                generation=1,
                previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.ROLLING_BACK,
                updated_at="2026-07-20T12:00:01Z",
            )
            current = repository.append(current, rolling, import_lock=import_lock)

            # ROLLING_BACK -> ROLLBACK_FAILED
            failed = replace(
                current,
                generation=2,
                previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.ROLLBACK_FAILED,
                resume_phase=ImportPhase.ROLLING_BACK,
                error_category="ROLLBACK_FAILED",
                recovery_attempt_count=1,
                updated_at="2026-07-20T12:00:02Z",
            )
            current = repository.append(current, failed, import_lock=import_lock)

            # ROLLBACK_FAILED -> ROLLING_BACK (retry)
            retry = replace(
                current,
                generation=3,
                previous_generation_sha256=sha256(canonical_json_bytes(current.to_dict())).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.ROLLING_BACK,
                resume_phase=None,
                error_category=None,
                pending_terminal_audit={"audit_schema_version": "2.0"},
                updated_at="2026-07-20T12:00:03Z",
            )
            result = repository.append(current, retry, import_lock=import_lock)
            self.assertEqual(result.phase, ImportPhase.ROLLING_BACK)
            self.assertIsNone(result.resume_phase)

    def test_recovery_required_missing_resume_phase_rejected(self) -> None:
        genesis = _generation(import_id=_uuid(), owner=_uuid())
        with self.assertRaises(ValueError) as ctx:
            replace(
                genesis,
                phase=ImportPhase.RECOVERY_REQUIRED,
                resume_phase=None,
                error_category="RECOVERY_REQUIRED",
            ).validate()
        self.assertIn("resume phase", str(ctx.exception).lower())

    def test_normal_phase_with_resume_phase_rejected(self) -> None:
        genesis = _generation(import_id=_uuid(), owner=_uuid())
        with self.assertRaises(ValueError) as ctx:
            replace(
                genesis,
                resume_phase=ImportPhase.PREPARED,
            ).validate()
        self.assertIn("resume phase", str(ctx.exception).lower())
    def test_rm20e_fully_receipted_intent_is_a_valid_durable_state(self) -> None:
        operation = _fully_receipted_cleanup()
        operation.validate()
        self.assertEqual(operation.status, CleanupStatus.INTENT)
        self.assertIsNone(operation.completed_generation)

    def test_rm20e_only_completion_successor_follows_fully_receipted_intent(self) -> None:
        operation = _fully_receipted_cleanup()
        import_id = _uuid()
        owner = _uuid()
        previous = replace(
            _generation(import_id=import_id, owner=owner),
            generation=3,
            previous_generation_sha256="d" * 64,
            phase=ImportPhase.COLLECTION_COMMITTED,
            cleanup_operations=(operation,),
        )
        completed = replace(
            operation,
            status=CleanupStatus.COMPLETE,
            completed_generation=4,
        )
        current = replace(
            previous,
            generation=4,
            cleanup_operations=(completed,),
        )
        Schema2PackageImportJournalRepository._validate_cleanup_transition(
            previous, current
        )

        changed_target = replace(
            operation.targets[0], relative_path="snapshot/other.ca-package"
        )
        invalid = replace(
            current,
            cleanup_operations=(replace(completed, targets=(changed_target,)),),
        )
        with self.assertRaises(JournalCorrupt):
            Schema2PackageImportJournalRepository._validate_cleanup_transition(
                previous, invalid
            )

    def test_rm17_posix_backup_has_no_identity_before_exchange(self) -> None:
        artifact = CollectionPublicationArtifact(
            kind="BACKUP",
            relative_name=".collection-test.tmp",
            token=_uuid(),
            relationship="BASELINE_BYTES",
            expected_byte_length=2,
            expected_sha256="c" * 64,
            expected_parent_identity=_identity(),
            state=CollectionPublicationState.PLANNED,
        )
        artifact.validate()
        with self.assertRaises(ValueError):
            validate_collection_publication_pair(
                artifact,
                replace(
                artifact,
                state=CollectionPublicationState.VERIFIED,
                object_identity=_identity(),
                verified_byte_length=2,
                verified_sha256="c" * 64,
                verified_generation=4,
                current_relative_name=artifact.relative_name,
                ),
                platform="POSIX",
            )

    def test_rm03_append_only_generation_uses_predecessor_commitment(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            repository = Schema2PackageImportJournalRepository(Path(root) / "journals")
            first = _generation(import_id=_uuid(), owner=_uuid())
            import_lock = PackageImportLock.acquire(
                Path(tempfile.gettempdir()) / f"{_uuid()}.lock",
                import_id=first.import_id,
            )
            self.addCleanup(import_lock.release)
            persisted = repository.create(first, import_lock=import_lock)
            second = replace(
                first,
                generation=1,
                previous_generation_sha256=sha256(canonical_json_bytes(first.to_dict())).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.COPYING_IMAGES,
                updated_at="2026-07-20T12:00:01Z",
            )
            repository.append(persisted, second, import_lock=import_lock)
            self.assertEqual(
                repository.load(first.import_id, import_lock=import_lock),
                second,
            )
            self.assertEqual(
                repository.load_chain(first.import_id, import_lock=import_lock),
                (first, second),
            )

    def test_rm03_rejects_wrong_previous_hash(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            repository = Schema2PackageImportJournalRepository(Path(root) / "journals")
            first = _generation(import_id=_uuid(), owner=_uuid())
            import_lock = PackageImportLock.acquire(
                Path(tempfile.gettempdir()) / f"{_uuid()}.lock",
                import_id=first.import_id,
            )
            self.addCleanup(import_lock.release)
            repository.create(first, import_lock=import_lock)
            second = replace(
                first,
                generation=1,
                previous_generation_sha256="d" * 64,
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.COPYING_IMAGES,
            )
            with self.assertRaises(Exception):
                repository.append(first, second, import_lock=import_lock)

    def test_rm03_authorized_partial_successor_is_removed_and_head_is_retained(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            repository = Schema2PackageImportJournalRepository(
                Path(root) / "journals"
            )
            first = _generation(import_id=_uuid(), owner=_uuid())
            import_lock = PackageImportLock.acquire(
                Path(tempfile.gettempdir()) / f"{_uuid()}.lock",
                import_id=first.import_id,
            )
            self.addCleanup(import_lock.release)
            repository.create(first, import_lock=import_lock)
            candidate = (
                repository.root
                / first.import_id
                / repository.temporary_name(1, first.next_generation_token)
            )
            candidate.write_bytes(b'{"journal_schema_version":')
            self.assertEqual(
                repository.load(first.import_id, import_lock=import_lock),
                first,
            )
            self.assertFalse(candidate.exists())

    def test_rm38_lost_global_lease_blocks_generation_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            repository = Schema2PackageImportJournalRepository(
                Path(root) / "journals"
            )
            first = _generation(import_id=_uuid(), owner=_uuid())
            import_lock = PackageImportLock.acquire(
                Path(tempfile.gettempdir()) / f"{_uuid()}.lock",
                import_id=first.import_id,
            )
            repository.create(first, import_lock=import_lock)
            import_lock.release()
            second = replace(
                first,
                generation=1,
                previous_generation_sha256=sha256(
                    canonical_json_bytes(first.to_dict())
                ).hexdigest(),
                transition_id=_uuid(),
                next_generation_token=_uuid(),
                phase=ImportPhase.COPYING_IMAGES,
            )
            with self.assertRaises(RecoveryRequired):
                repository.append(first, second, import_lock=import_lock)


if __name__ == "__main__":
    unittest.main()
