"""Focused tests for capture-import journal phase contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
import unittest

from capture_import.audit import AuditCoin, AuditSession
from capture_import.enums import (
    Composition,
    DuplicateDecision,
    ErrorCategory,
    ImageRole,
    ImportPhase,
    ImportRecordOutcome,
    ImportResult,
)
from capture_import.journal import JournalEntry, validate_same_phase_update
from capture_import.limits import (
    AUDIT_SCHEMA_VERSION,
    JOURNAL_SCHEMA_VERSION,
    MAX_PACKAGE_SIZE,
    MISSING_COLLECTION_SENTINEL,
    SUPPORTED_SCHEMA,
)

IMPORT_ID = "11111111-1111-4111-8111-111111111111"
TOKEN = "33333333-3333-4333-8333-333333333333"
DESKTOP_ID = "22222222-2222-4222-8222-222222222222"
NOW = "2026-07-18T12:00:00Z"
LATER = "2026-07-18T12:01:00Z"
PACKAGE_SHA = "a" * 64
BASELINE_SHA = "b" * 64
FRONT_SHA = "c" * 64
REVERSE_SHA = "d" * 64
IMPORT_ROOT = f"coin_photos/collection/imports/{IMPORT_ID}"
EXPECTED_PATHS = (
    f"{IMPORT_ROOT}/.import-owner.json",
    f"{IMPORT_ROOT}/{DESKTOP_ID}/front.jpg",
    f"{IMPORT_ROOT}/{DESKTOP_ID}/reverse.jpg",
)


def make_audit_coin(
    source_id: str,
    position: int,
    outcome: ImportRecordOutcome,
) -> AuditCoin:
    committed = outcome is ImportRecordOutcome.COMMITTED
    skipped = outcome is ImportRecordOutcome.SKIPPED
    return AuditCoin(
        source_coin_id=source_id,
        desktop_item_id=DESKTOP_ID if committed else None,
        decision=(
            DuplicateDecision.SKIP if skipped else DuplicateDecision.IMPORT_AS_NEW
        ),
        source_position=position,
        mint="",
        composition=Composition.SILVER,
        is_bullion=False,
        actual_silver_weight_oz="0.6",
        source_created_at=NOW,
        source_updated_at=NOW,
        source_quantity=1,
        image_role_hashes=(
            (ImageRole.FRONT, FRONT_SHA),
            (ImageRole.REVERSE, REVERSE_SHA),
        ),
        managed_image_paths=(
            (
                (ImageRole.FRONT, EXPECTED_PATHS[1]),
                (ImageRole.REVERSE, EXPECTED_PATHS[2]),
            )
            if committed
            else ()
        ),
    )


def make_terminal_audit(phase: ImportPhase) -> AuditSession:
    committed = phase is ImportPhase.SUCCEEDED
    coins = (
        make_audit_coin(
            "coin-1",
            0,
            (
                ImportRecordOutcome.COMMITTED
                if committed
                else ImportRecordOutcome.NOT_COMMITTED
            ),
        ),
        make_audit_coin("coin-2", 1, ImportRecordOutcome.SKIPPED),
    )
    return AuditSession(
        audit_schema_version=AUDIT_SCHEMA_VERSION,
        import_id=IMPORT_ID,
        started_at=NOW,
        completed_at=LATER,
        package_filename_basename="Toronto.ca-package",
        package_sha256=PACKAGE_SHA,
        schema=SUPPORTED_SCHEMA,
        package_version="1.0",
        created_by="Coin Analyzer Mobile Companion",
        created_with="0.1.0",
        exported_at=NOW,
        session_id="session-1",
        session_name="Toronto Coin Expo",
        session_description="",
        session_date="2026-07-18",
        session_created_at=NOW,
        session_updated_at=NOW,
        coin_provenance=coins,
        proposed_count=2,
        imported_count=1 if committed else 0,
        skipped_count=1,
        phase=phase,
        final_status=ImportResult(phase.value),
        error_category=None if committed else ErrorCategory.ROLLED_BACK,
    )


def make_journal(phase: ImportPhase = ImportPhase.PREPARED) -> JournalEntry:
    created_paths: tuple[str, ...] = ()
    committed_ids: tuple[str, ...] = ()
    imported_count = 0
    snapshot_path: str | None = "snapshot-token/package.ca-package"
    error_category: ErrorCategory | None = None
    audit_pending = False
    terminal_audit: AuditSession | None = None
    recovery_attempts = 0

    if phase is ImportPhase.COPYING_IMAGES:
        created_paths = EXPECTED_PATHS[:1]
    elif phase in {
        ImportPhase.FILES_READY,
        ImportPhase.COMMITTING_COLLECTION,
    }:
        created_paths = EXPECTED_PATHS
    elif phase is ImportPhase.COLLECTION_COMMITTED:
        created_paths = EXPECTED_PATHS
        committed_ids = (DESKTOP_ID,)
        imported_count = 1
        audit_pending = True
    elif phase is ImportPhase.SUCCEEDED:
        created_paths = EXPECTED_PATHS
        committed_ids = (DESKTOP_ID,)
        imported_count = 1
        snapshot_path = None
        terminal_audit = make_terminal_audit(phase)
    elif phase is ImportPhase.ROLLING_BACK:
        created_paths = EXPECTED_PATHS[:1]
        error_category = ErrorCategory.COLLECTION_COMMIT_FAILED
    elif phase in {ImportPhase.ROLLED_BACK, ImportPhase.CANCELLED}:
        snapshot_path = None
        terminal_audit = make_terminal_audit(phase)
        error_category = (
            ErrorCategory.ROLLED_BACK if phase is ImportPhase.ROLLED_BACK else None
        )
    elif phase is ImportPhase.RECOVERY_REQUIRED:
        created_paths = EXPECTED_PATHS[:1]
        error_category = ErrorCategory.RECOVERY_REQUIRED
        recovery_attempts = 1
    elif phase is ImportPhase.ROLLBACK_FAILED:
        created_paths = EXPECTED_PATHS[:1]
        error_category = ErrorCategory.ROLLBACK_FAILED
        recovery_attempts = 1

    return JournalEntry(
        journal_schema_version=JOURNAL_SCHEMA_VERSION,
        import_id=IMPORT_ID,
        random_ownership_token=TOKEN,
        phase=phase,
        created_at=NOW,
        updated_at=NOW,
        package_sha256=PACKAGE_SHA,
        package_version="1.0",
        package_basename="Toronto.ca-package",
        snapshot_relative_path=snapshot_path,
        snapshot_byte_length=4096,
        collection_baseline_sha256_or_sentinel=BASELINE_SHA,
        collection_baseline_byte_length=1024,
        selected_source_coin_ids=("coin-1",),
        desktop_item_ids=(DESKTOP_ID,),
        import_root_relative_path=IMPORT_ROOT,
        created_relative_paths=created_paths,
        expected_relative_paths=EXPECTED_PATHS,
        committed_collection_item_ids=committed_ids,
        proposed_count=2,
        imported_count=imported_count,
        skipped_count=1,
        error_category=error_category,
        recovery_attempt_count=recovery_attempts,
        cleanup_pending=False,
        audit_finalization_pending=audit_pending,
        terminal_audit=terminal_audit,
    )


class JournalPhaseTests(unittest.TestCase):
    def test_one_valid_record_for_every_durable_phase(self) -> None:
        for phase in ImportPhase:
            with self.subTest(phase=phase):
                journal = make_journal(phase)
                journal.validate()
                self.assertEqual(JournalEntry.from_dict(journal.to_dict()), journal)

    def test_impossible_phase_combinations_fail_closed(self) -> None:
        cases = (
            replace(make_journal(), created_relative_paths=EXPECTED_PATHS[:1]),
            replace(
                make_journal(ImportPhase.COPYING_IMAGES),
                committed_collection_item_ids=(DESKTOP_ID,),
                imported_count=1,
            ),
            replace(
                make_journal(ImportPhase.FILES_READY),
                created_relative_paths=EXPECTED_PATHS[:1],
            ),
            replace(
                make_journal(ImportPhase.COMMITTING_COLLECTION),
                audit_finalization_pending=True,
            ),
            replace(
                make_journal(ImportPhase.COLLECTION_COMMITTED),
                committed_collection_item_ids=(),
                imported_count=0,
            ),
            replace(
                make_journal(ImportPhase.COLLECTION_COMMITTED),
                audit_finalization_pending=False,
            ),
            replace(
                make_journal(ImportPhase.SUCCEEDED),
                committed_collection_item_ids=(),
                imported_count=0,
            ),
            replace(
                make_journal(ImportPhase.ROLLING_BACK),
                committed_collection_item_ids=(DESKTOP_ID,),
                imported_count=1,
            ),
            replace(
                make_journal(ImportPhase.ROLLED_BACK),
                created_relative_paths=EXPECTED_PATHS[:1],
            ),
            replace(
                make_journal(ImportPhase.CANCELLED),
                created_relative_paths=EXPECTED_PATHS[:1],
            ),
            replace(
                make_journal(ImportPhase.RECOVERY_REQUIRED), error_category=None
            ),
            replace(make_journal(ImportPhase.ROLLBACK_FAILED), error_category=None),
        )
        self.assertEqual(len(cases), len(ImportPhase) + 1)
        for invalid in cases:
            with self.subTest(phase=invalid.phase):
                with self.assertRaises(ValueError):
                    invalid.validate()

    def test_committed_ids_are_empty_or_complete_and_ordered(self) -> None:
        other_id = "44444444-4444-4444-8444-444444444444"
        base = replace(
            make_journal(ImportPhase.RECOVERY_REQUIRED),
            selected_source_coin_ids=("coin-1", "coin-3"),
            desktop_item_ids=(DESKTOP_ID, other_id),
            proposed_count=3,
            skipped_count=1,
        )
        with self.assertRaisesRegex(ValueError, "empty or the complete"):
            replace(
                base,
                committed_collection_item_ids=(DESKTOP_ID,),
                imported_count=1,
            ).validate()
        committed_recovery = replace(
            base,
            committed_collection_item_ids=(DESKTOP_ID, other_id),
            imported_count=2,
            created_relative_paths=EXPECTED_PATHS,
            audit_finalization_pending=True,
        )
        committed_recovery.validate()
        with self.assertRaisesRegex(ValueError, "complete files"):
            replace(
                committed_recovery,
                created_relative_paths=EXPECTED_PATHS[:1],
            ).validate()
        with self.assertRaisesRegex(ValueError, "pending audit"):
            replace(committed_recovery, audit_finalization_pending=False).validate()

    def test_committing_collection_permits_complete_reconciled_commit(self) -> None:
        uncommitted = make_journal(ImportPhase.COMMITTING_COLLECTION)
        committed = replace(
            uncommitted,
            updated_at=LATER,
            committed_collection_item_ids=(DESKTOP_ID,),
            imported_count=1,
        )
        committed.validate()
        validate_same_phase_update(uncommitted, committed)
        with self.assertRaisesRegex(ValueError, "cannot forget committed"):
            validate_same_phase_update(committed, uncommitted)

    def test_terminal_records_have_zero_surviving_state_after_rollback(self) -> None:
        for phase in (ImportPhase.ROLLED_BACK, ImportPhase.CANCELLED):
            journal = make_journal(phase)
            self.assertEqual(journal.imported_count, 0)
            self.assertEqual(journal.committed_collection_item_ids, ())
            self.assertEqual(journal.created_relative_paths, ())
            self.assertIsNone(journal.snapshot_relative_path)
            journal.validate()

    def test_terminal_audit_must_match_phase_identity_and_counts(self) -> None:
        succeeded = make_journal(ImportPhase.SUCCEEDED)
        with self.assertRaises(ValueError):
            replace(succeeded, terminal_audit=None).validate()
        with self.assertRaises(ValueError):
            replace(
                succeeded,
                terminal_audit=replace(
                    succeeded.terminal_audit,
                    import_id="55555555-5555-4555-8555-555555555555",
                ),
            ).validate()
        with self.assertRaises(ValueError):
            replace(
                succeeded,
                snapshot_relative_path="snapshot-token/package.ca-package",
            ).validate()


class JournalUpdateTests(unittest.TestCase):
    def test_copy_progress_is_monotonic(self) -> None:
        first = make_journal(ImportPhase.COPYING_IMAGES)
        complete = replace(
            first, updated_at=LATER, created_relative_paths=EXPECTED_PATHS
        )
        validate_same_phase_update(first, complete)
        with self.assertRaisesRegex(ValueError, "cannot forget"):
            validate_same_phase_update(complete, first)

    def test_succeeded_may_only_clear_cleanup_pending(self) -> None:
        pending = replace(make_journal(ImportPhase.SUCCEEDED), cleanup_pending=True)
        cleaned = replace(pending, updated_at=LATER, cleanup_pending=False)
        validate_same_phase_update(pending, cleaned)
        validate_same_phase_update(cleaned, cleaned)
        with self.assertRaisesRegex(ValueError, "only clear"):
            validate_same_phase_update(cleaned, pending)

    def test_same_phase_update_rejects_immutable_identity_change(self) -> None:
        previous = make_journal(ImportPhase.COPYING_IMAGES)
        current = replace(previous, updated_at=LATER, package_sha256="e" * 64)
        with self.assertRaisesRegex(ValueError, "Immutable journal field"):
            validate_same_phase_update(previous, current)

    def test_recovery_attempt_count_cannot_regress(self) -> None:
        previous = replace(
            make_journal(ImportPhase.RECOVERY_REQUIRED), recovery_attempt_count=2
        )
        current = replace(previous, updated_at=LATER, recovery_attempt_count=1)
        with self.assertRaisesRegex(ValueError, "cannot decrease"):
            validate_same_phase_update(previous, current)


class JournalBoundaryAndSchemaTests(unittest.TestCase):
    def test_snapshot_size_boundaries(self) -> None:
        for size in (1, MAX_PACKAGE_SIZE - 1, MAX_PACKAGE_SIZE):
            replace(make_journal(), snapshot_byte_length=size).validate()
        for invalid in (0, -1, MAX_PACKAGE_SIZE + 1, True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    replace(make_journal(), snapshot_byte_length=invalid).validate()

    def test_missing_and_unknown_fields_fail_closed(self) -> None:
        payload = make_journal().to_dict()
        del payload["random_ownership_token"]
        with self.assertRaisesRegex(ValueError, "missing fields"):
            JournalEntry.from_dict(payload)
        payload = make_journal().to_dict()
        payload["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            JournalEntry.from_dict(payload)

    def test_uuid_hash_timestamp_boolean_and_path_validation(self) -> None:
        mutations = (
            ("import_id", "not-a-uuid"),
            ("package_sha256", "A" * 64),
            ("created_at", "2026-07-18 12:00:00Z"),
            ("cleanup_pending", 0),
            ("import_root_relative_path", "C:/Users/private"),
        )
        for field, value in mutations:
            payload = make_journal().to_dict()
            payload[field] = value
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    JournalEntry.from_dict(payload)

    def test_missing_collection_baseline_is_exact(self) -> None:
        valid = replace(
            make_journal(),
            collection_baseline_sha256_or_sentinel=MISSING_COLLECTION_SENTINEL,
            collection_baseline_byte_length=0,
        )
        valid.validate()
        with self.assertRaises(ValueError):
            replace(valid, collection_baseline_byte_length=1).validate()

    def test_journal_is_frozen_deterministic_and_json_compatible(self) -> None:
        journal = make_journal()
        self.assertEqual(journal.to_dict(), journal.to_dict())
        json.dumps(journal.to_dict())
        with self.assertRaises(FrozenInstanceError):
            journal.phase = ImportPhase.COPYING_IMAGES  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
