"""Focused exact-byte persistence service tests for Sprint 5C."""

from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from hashlib import sha256
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from capture_import._json import canonical_json_bytes
from capture_import.baseline import capture_collection_baseline
from capture_import.collection_persistence import DurableCollectionPublisher
from capture_import.durable_models import (
    CleanupOperation,
    CleanupReceipt,
    CollectionPublicationArtifact,
    ExpectedImageEvidence,
    NativeObjectIdentity,
    OperationalJournalGeneration,
    OwnershipDescriptor,
    VerifiedImageEvidence,
)
from capture_import.durable_repository import Schema2PackageImportJournalRepository
from capture_import.enums import (
    CleanupStatus,
    CollectionPublicationState,
    ImportPhase,
    ImportResult,
)
from capture_import.terminal_persistence import TerminalPersistenceService
from capture_import.lock import PackageImportLock


def _uuid() -> str:
    return str(uuid4())


def _identity() -> NativeObjectIdentity:
    return NativeObjectIdentity("WINDOWS", "0000000000000001", "0" * 31 + "2")


def _successor(
    previous: OperationalJournalGeneration,
    phase: ImportPhase | None = None,
    **changes,
) -> OperationalJournalGeneration:
    return replace(
        previous,
        generation=previous.generation + 1,
        previous_generation_sha256=sha256(
            canonical_json_bytes(previous.to_dict())
        ).hexdigest(),
        transition_id=_uuid(),
        next_generation_token=_uuid(),
        phase=previous.phase if phase is None else phase,
        updated_at="2026-07-20T12:00:01Z",
        **changes,
    )


def _terminal_audit(import_id: str, desktop_id: str) -> dict:
    timestamp = "2026-07-20T12:00:00Z"
    return {
        "audit_schema_version": "2.0",
        "import_id": import_id,
        "started_at": timestamp,
        "completed_at": "2026-07-20T12:00:02Z",
        "package_filename_basename": "test.ca-package",
        "package_sha256": "a" * 64,
        "schema": "coin-analyzer.capture-package",
        "package_version": "1.0",
        "created_by": "Coin Analyzer Mobile Companion",
        "created_with": "0.2.0",
        "exported_at": timestamp,
        "session_id": "session-1",
        "session_name": "Test",
        "session_description": "",
        "session_date": None,
        "session_created_at": timestamp,
        "session_updated_at": timestamp,
        "coin_provenance": [
            {
                "source_coin_id": "source-1",
                "desktop_item_id": desktop_id,
                "decision": "IMPORT_AS_NEW",
                "source_position": 0,
                "mint": "",
                "composition": "silver",
                "is_bullion": False,
                "actual_silver_weight_oz": None,
                "source_created_at": timestamp,
                "source_updated_at": timestamp,
                "source_quantity": 1,
                "image_role_hashes": {"front": sha256(b"img").hexdigest()},
            }
        ],
        "proposed_count": 1,
        "imported_count": 1,
        "skipped_count": 0,
        "phase": "SUCCEEDED",
        "final_status": "SUCCEEDED",
        "error_category": None,
    }


class DurableCollectionPublisherTests(unittest.TestCase):
    """Durable Persistence collection protocol; RM-16 through RM-18."""

    def test_rm18_missing_baseline_publishes_exact_bytes_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            collection = Path(root) / "collection.json"
            baseline = capture_collection_baseline(collection)
            payload = b'[\n  {"id": "new"}\n]'
            publisher = DurableCollectionPublisher(collection)
            import_lock = PackageImportLock.acquire(
                Path(tempfile.gettempdir()) / f"{_uuid()}.lock",
                import_id=_uuid(),
            )
            self.addCleanup(import_lock.release)
            temporary, backup = publisher.plan(
                payload,
                baseline=baseline,
                import_id=_uuid(),
                temporary_token=_uuid(),
                backup_token=_uuid(),
            )
            self.assertIsNone(backup)
            verified = publisher.create_temporary(
                temporary,
                payload,
                generation=2,
                import_lock=import_lock,
            )
            published, retained = publisher.publish(
                verified,
                None,
                baseline=baseline,
                exchange_generation=3,
                publication_generation=4,
                import_lock=import_lock,
            )
            self.assertIsNone(retained)
            self.assertEqual(published.state, CollectionPublicationState.PUBLISHED)
            self.assertEqual(collection.read_bytes(), payload)
            publisher.verify_committed(len(payload), published.expected_sha256)

    def test_rm17_existing_baseline_is_retained_until_explicit_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            collection = Path(root) / "collection.json"
            baseline_payload = b'[\n  {"id": "old"}\n]'
            prospective_payload = b'[\n  {"id": "old"},\n  {"id": "new"}\n]'
            collection.write_bytes(baseline_payload)
            baseline = capture_collection_baseline(collection)
            publisher = DurableCollectionPublisher(collection)
            import_lock = PackageImportLock.acquire(
                Path(tempfile.gettempdir()) / f"{_uuid()}.lock",
                import_id=_uuid(),
            )
            self.addCleanup(import_lock.release)
            temporary, backup = publisher.plan(
                prospective_payload,
                baseline=baseline,
                import_id=_uuid(),
                temporary_token=_uuid(),
                backup_token=_uuid(),
            )
            self.assertIsNotNone(backup)
            verified = publisher.create_temporary(
                temporary,
                prospective_payload,
                generation=2,
                import_lock=import_lock,
            )
            if __import__("os").name == "nt":
                backup = publisher.create_windows_backup(
                    backup,
                    generation=3,
                    import_lock=import_lock,
                )
            published, retained = publisher.publish(
                verified,
                backup,
                baseline=baseline,
                exchange_generation=4,
                publication_generation=5,
                import_lock=import_lock,
            )
            self.assertEqual(collection.read_bytes(), prospective_payload)
            self.assertIsNotNone(retained)
            retained_path = collection.parent / retained.current_relative_name
            self.assertEqual(retained_path.read_bytes(), baseline_payload)
            publisher.cleanup_backup(retained, import_lock=import_lock)
            self.assertFalse(retained_path.exists())
            publisher.verify_committed(
                len(prospective_payload), published.expected_sha256
            )


class TerminalPersistenceTests(unittest.TestCase):
    """Durable Persistence terminal compaction; RM-21 through RM-28."""

    def test_rm21_compaction_retires_operational_paths_before_final_history(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            journals = Schema2PackageImportJournalRepository(
                root_path / "journals"
            )
            import_id = _uuid()
            owner = _uuid()
            import_lock = PackageImportLock.acquire(
                Path(tempfile.gettempdir()) / f"{_uuid()}.lock",
                import_id=import_id,
            )
            self.addCleanup(import_lock.release)
            expected = ExpectedImageEvidence(
                relative_path=f"imports/{import_id}/coin/front.jpg",
                role="front",
                byte_length=3,
                sha256=sha256(b"img").hexdigest(),
                media_type="image/jpeg",
                width=1,
                height=1,
            )
            genesis = OperationalJournalGeneration(
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
                snapshot_byte_length=12,
                snapshot_relative_path="snapshot/package.ca-package",
                collection_baseline_sha256_or_sentinel="MISSING_COLLECTION_V1",
                collection_baseline_byte_length=0,
                prospective_collection_byte_length=None,
                prospective_collection_sha256=None,
                selected_source_coin_ids=("source-1",),
                desktop_item_ids=(_uuid(),),
                import_root_relative_path=f"imports/{import_id}",
                expected_image_inventory=(expected,),
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
            current = journals.create(genesis, import_lock=import_lock)
            current = journals.append(
                current,
                _successor(current, ImportPhase.COPYING_IMAGES),
                import_lock=import_lock,
            )
            verified = VerifiedImageEvidence(
                **expected.to_dict(),
                parent_identity=_identity(),
                object_identity=_identity(),
            )
            current = journals.append(
                current,
                _successor(
                    current, verified_image_inventory=(verified,)
                ),
                import_lock=import_lock,
            )
            current = journals.append(
                current,
                _successor(current, ImportPhase.FILES_READY),
                import_lock=import_lock,
            )
            prospective = b"[]"
            artifact = CollectionPublicationArtifact(
                kind="TEMPORARY",
                relative_name=f".collection-{import_id}-{_uuid()}.tmp",
                token=_uuid(),
                relationship="PROSPECTIVE_BYTES",
                expected_byte_length=len(prospective),
                expected_sha256=sha256(prospective).hexdigest(),
                expected_parent_identity=_identity(),
                state=CollectionPublicationState.PUBLISHED,
                object_identity=_identity(),
                verified_byte_length=len(prospective),
                verified_sha256=sha256(prospective).hexdigest(),
                verified_generation=current.generation + 1,
                current_relative_name="collection.json",
                published_relative_name="collection.json",
                publication_generation=current.generation + 2,
            )
            current = journals.append(
                current,
                _successor(
                    current,
                    ImportPhase.COMMITTING_COLLECTION,
                    prospective_collection_byte_length=len(prospective),
                    prospective_collection_sha256=sha256(prospective).hexdigest(),
                    collection_publication="INTENT",
                    collection_temporary_artifact=replace(
                        artifact,
                        state=CollectionPublicationState.VERIFIED,
                        current_relative_name=artifact.relative_name,
                        published_relative_name=None,
                        publication_generation=None,
                    ),
                ),
                import_lock=import_lock,
            )
            current = journals.append(
                current,
                _successor(
                    current,
                    ImportPhase.COLLECTION_COMMITTED,
                    collection_publication="VERIFIED",
                    collection_temporary_artifact=artifact,
                    committed_collection_item_ids=current.desktop_item_ids,
                    imported_count=1,
                    pending_terminal_audit=_terminal_audit(
                        import_id, current.desktop_item_ids[0]
                    ),
                ),
                import_lock=import_lock,
            )
            target = OwnershipDescriptor(
                root="SNAPSHOT",
                relative_path="snapshot/package.ca-package",
                object_kind="FILE",
                ownership_token=owner,
                expected_byte_length=12,
                expected_sha256="a" * 64,
                parent_identity=_identity(),
                object_identity=_identity(),
            )
            operation = CleanupOperation(
                kind="SUCCESS_SNAPSHOT",
                intent_id=_uuid(),
                intent_generation=current.generation + 1,
                targets=(target,),
                receipts=(),
                status=CleanupStatus.INTENT,
                completed_generation=None,
            )
            current = journals.append(
                current,
                _successor(current, cleanup_operations=(operation,)),
                import_lock=import_lock,
            )
            receipt = CleanupReceipt(
                target_relative_path=target.relative_path,
                removed_object_identity=target.object_identity,
                removal_generation=current.generation + 1,
            )
            operation = replace(operation, receipts=(receipt,))
            current = journals.append(
                current,
                _successor(
                    current,
                    snapshot_relative_path=None,
                    cleanup_operations=(operation,),
                ),
                import_lock=import_lock,
            )
            operation = replace(
                operation,
                status=CleanupStatus.COMPLETE,
                completed_generation=current.generation + 1,
            )
            current = journals.append(
                current,
                _successor(current, cleanup_operations=(operation,)),
                import_lock=import_lock,
            )
            service = TerminalPersistenceService(
                journals,
                root_path / "history",
                clock=lambda: "2026-07-20T12:00:02Z",
            )
            original_manifest = service._write_manifest

            def interrupt_after_manifest(*args, **kwargs):
                original_manifest(*args, **kwargs)
                raise KeyboardInterrupt("RM-21 interrupted after manifest")

            with patch.object(
                service, "_write_manifest", side_effect=interrupt_after_manifest
            ):
                with self.assertRaises(KeyboardInterrupt):
                    service.compact(
                        current,
                        result=ImportResult.SUCCEEDED,
                        import_lock=import_lock,
                    )

            resumed_service = TerminalPersistenceService(
                journals,
                root_path / "history",
                clock=lambda: "2026-07-20T12:00:02Z",
            )
            original_delete = resumed_service._delete_verified
            calls = 0

            def interrupt_retirement(
                directory, name, expected_sha256, **identity_expectations
            ):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise KeyboardInterrupt("RM-23 interrupted retirement")
                return original_delete(
                    directory,
                    name,
                    expected_sha256,
                    **identity_expectations,
                )

            with patch.object(
                resumed_service,
                "_delete_verified",
                side_effect=interrupt_retirement,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    resumed_service.resume_compaction(
                        import_id,
                        import_lock=import_lock,
                    )
            terminal = TerminalPersistenceService(
                journals,
                root_path / "history",
                clock=lambda: "2026-07-20T12:00:02Z",
            ).resume_pending(import_id, import_lock=import_lock)
            terminal.validate()
            self.assertFalse((journals.root / import_id).exists())
            final = root_path / "history" / f"{import_id}.json"
            self.assertTrue(final.is_file())
            raw = final.read_text(encoding="utf-8")
            self.assertNotIn("snapshot/package.ca-package", raw)
            self.assertNotIn(owner, raw)
            stable = final.read_bytes()
            self.assertEqual(
                TerminalPersistenceService(
                    journals,
                    root_path / "history",
                    clock=lambda: "2026-07-20T12:00:02Z",
                )._read_terminal_record(final),
                terminal,
            )
            self.assertEqual(final.read_bytes(), stable)



if __name__ == "__main__":
    unittest.main()
