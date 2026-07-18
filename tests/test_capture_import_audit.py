"""Focused tests for immutable capture-import audit contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from unittest.mock import patch
import unittest

from capture_import.audit import AuditCoin, AuditSession, deserialize, serialize
from capture_import.enums import (
    Composition,
    DuplicateDecision,
    ErrorCategory,
    ImageRole,
    ImportPhase,
    ImportRecordOutcome,
    ImportResult,
)
from capture_import.limits import AUDIT_SCHEMA_VERSION, SUPPORTED_SCHEMA

IMPORT_ID = "11111111-1111-4111-8111-111111111111"
DESKTOP_ID = "22222222-2222-4222-8222-222222222222"
NOW = "2026-07-18T12:00:00Z"
LATER = "2026-07-18T12:01:00+00:00"
PACKAGE_SHA = "a" * 64
FRONT_SHA = "b" * 64
REVERSE_SHA = "c" * 64


def make_audit_coin(
    source_id: str,
    position: int,
    outcome: ImportRecordOutcome,
) -> AuditCoin:
    decision = (
        DuplicateDecision.SKIP
        if outcome is ImportRecordOutcome.SKIPPED
        else DuplicateDecision.IMPORT_AS_NEW
    )
    committed = outcome is ImportRecordOutcome.COMMITTED
    desktop_id = DESKTOP_ID if committed else None
    managed = (
        (
            (
                ImageRole.FRONT,
                f"coin_photos/collection/imports/{IMPORT_ID}/{DESKTOP_ID}/front.jpg",
            ),
            (
                ImageRole.REVERSE,
                f"coin_photos/collection/imports/{IMPORT_ID}/{DESKTOP_ID}/reverse.jpg",
            ),
        )
        if committed
        else ()
    )
    return AuditCoin(
        source_coin_id=source_id,
        desktop_item_id=desktop_id,
        decision=decision,
        source_position=position,
        mint="Royal Canadian Mint",
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
        managed_image_paths=managed,
    )


def make_audit(phase: ImportPhase = ImportPhase.SUCCEEDED) -> AuditSession:
    if phase is ImportPhase.SUCCEEDED:
        outcomes = (ImportRecordOutcome.COMMITTED, ImportRecordOutcome.SKIPPED)
        imported_count = 1
    else:
        outcomes = (ImportRecordOutcome.NOT_COMMITTED, ImportRecordOutcome.SKIPPED)
        imported_count = 0
    coins = tuple(
        make_audit_coin(f"coin-{index + 1}", index, outcome)
        for index, outcome in enumerate(outcomes)
    )
    return AuditSession(
        audit_schema_version=AUDIT_SCHEMA_VERSION,
        import_id=IMPORT_ID,
        started_at=NOW,
        completed_at=LATER,
        package_filename_basename="Toronto_Expo.ca-package",
        package_sha256=PACKAGE_SHA,
        schema=SUPPORTED_SCHEMA,
        package_version="1.0",
        created_by="Coin Analyzer Mobile Companion",
        created_with="0.1.0",
        exported_at=NOW,
        session_id="session-1",
        session_name="Toronto Coin Expo",
        session_description="July 2026",
        session_date="2026-07-18",
        session_created_at=NOW,
        session_updated_at=NOW,
        coin_provenance=coins,
        proposed_count=2,
        imported_count=imported_count,
        skipped_count=1,
        phase=phase,
        final_status=ImportResult(phase.value),
        error_category=(
            ErrorCategory.ROLLED_BACK
            if phase is ImportPhase.ROLLED_BACK
            else None
        ),
    )


def assert_json_primitives(test: unittest.TestCase, value: object) -> None:
    if isinstance(value, dict):
        test.assertTrue(all(isinstance(key, str) for key in value))
        for item in value.values():
            assert_json_primitives(test, item)
    elif isinstance(value, list):
        for item in value:
            assert_json_primitives(test, item)
    else:
        test.assertIsInstance(value, (str, int, float, bool, type(None)))


class AuditOutcomeTests(unittest.TestCase):
    def test_succeeded_rolled_back_and_cancelled_round_trip(self) -> None:
        for phase in (
            ImportPhase.SUCCEEDED,
            ImportPhase.ROLLED_BACK,
            ImportPhase.CANCELLED,
        ):
            with self.subTest(phase=phase):
                audit = make_audit(phase)
                self.assertEqual(AuditSession.from_dict(audit.to_dict()), audit)
                self.assertEqual(deserialize(serialize(audit)), audit)

    def test_original_decision_is_preserved_when_not_committed(self) -> None:
        coin = make_audit(ImportPhase.ROLLED_BACK).coin_provenance[0]
        self.assertIs(coin.decision, DuplicateDecision.IMPORT_AS_NEW)
        self.assertIs(coin.outcome, ImportRecordOutcome.NOT_COMMITTED)
        self.assertIsNone(coin.desktop_item_id)
        self.assertEqual(coin.managed_image_paths, ())

    def test_rolled_back_and_cancelled_reject_surviving_committed_records(self) -> None:
        for phase in (ImportPhase.ROLLED_BACK, ImportPhase.CANCELLED):
            audit = make_audit(phase)
            committed = make_audit_coin(
                "coin-1", 0, ImportRecordOutcome.COMMITTED
            )
            invalid = replace(
                audit,
                coin_provenance=(committed, audit.coin_provenance[1]),
                imported_count=1,
            )
            with self.subTest(phase=phase):
                with self.assertRaisesRegex(ValueError, "cannot retain committed"):
                    invalid.validate()

    def test_succeeded_rejects_selected_but_uncommitted_records(self) -> None:
        audit = make_audit()
        uncommitted = make_audit_coin(
            "coin-1", 0, ImportRecordOutcome.NOT_COMMITTED
        )
        with self.assertRaisesRegex(ValueError, "selected, uncommitted"):
            replace(
                audit,
                coin_provenance=(uncommitted, audit.coin_provenance[1]),
                imported_count=0,
            ).validate()

    def test_partial_committed_state_is_rejected(self) -> None:
        committed = make_audit_coin("coin-1", 0, ImportRecordOutcome.COMMITTED)
        with self.assertRaisesRegex(ValueError, "managed path"):
            replace(committed, managed_image_paths=()).validate()
        with self.assertRaisesRegex(ValueError, "must not have managed"):
            replace(
                make_audit_coin("coin-1", 0, ImportRecordOutcome.NOT_COMMITTED),
                managed_image_paths=((ImageRole.FRONT, "images/front.jpg"),),
            ).validate()


class AuditSchemaTests(unittest.TestCase):
    def test_audit_values_are_frozen(self) -> None:
        for value in (make_audit(), make_audit().coin_provenance[0]):
            with self.subTest(dto=type(value).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, next(iter(value.__dataclass_fields__)), "changed")

    def test_missing_and_unknown_fields_fail_closed_at_each_level(self) -> None:
        payload = make_audit().to_dict()
        del payload["package_sha256"]
        with self.assertRaisesRegex(ValueError, "missing fields"):
            AuditSession.from_dict(payload)

        payload = make_audit().to_dict()
        payload["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            AuditSession.from_dict(payload)

        coin_payload = make_audit().coin_provenance[0].to_dict()
        coin_payload["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            AuditCoin.from_dict(coin_payload)

    def test_uuid_timestamp_hash_enum_boolean_and_number_validation(self) -> None:
        mutations = (
            ("import_id", "not-a-uuid"),
            ("started_at", "2026-07-18 12:00:00Z"),
            ("package_sha256", "A" * 64),
            ("phase", "DONE"),
            ("proposed_count", True),
        )
        for field, value in mutations:
            payload = make_audit().to_dict()
            payload[field] = value
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    AuditSession.from_dict(payload)

        for invalid in ("NaN", "Infinity", "1e2", -1.0):
            payload = make_audit().to_dict()
            payload["coin_provenance"][0]["actual_silver_weight_oz"] = invalid
            with self.subTest(asw=invalid):
                with self.assertRaises(ValueError):
                    AuditSession.from_dict(payload)

    def test_paths_and_hashes_are_strict(self) -> None:
        coin = make_audit().coin_provenance[0]
        with self.assertRaises(ValueError):
            replace(
                coin,
                managed_image_paths=(
                    (ImageRole.FRONT, "C:/Users/person/front.jpg"),
                    (ImageRole.REVERSE, "images/reverse.jpg"),
                ),
            ).validate()
        with self.assertRaises(ValueError):
            replace(
                coin,
                image_role_hashes=(
                    (ImageRole.FRONT, "B" * 64),
                    (ImageRole.REVERSE, REVERSE_SHA),
                ),
            ).validate()

    def test_positions_are_zero_based_ordered_and_contiguous(self) -> None:
        audit = make_audit()
        invalid_positions = ((0, 0), (1, 0), (0, 2), (1, 2))
        for positions in invalid_positions:
            coins = tuple(
                replace(coin, source_position=position)
                for coin, position in zip(audit.coin_provenance, positions)
            )
            with self.subTest(positions=positions):
                with self.assertRaisesRegex(ValueError, "contiguous"):
                    replace(audit, coin_provenance=coins).validate()

    def test_counts_and_phase_result_must_agree(self) -> None:
        with self.assertRaises(ValueError):
            replace(make_audit(), proposed_count=3).validate()
        with self.assertRaises(ValueError):
            replace(make_audit(), imported_count=0).validate()
        with self.assertRaises(ValueError):
            replace(make_audit(), skipped_count=0).validate()
        with self.assertRaises(ValueError):
            replace(make_audit(), final_status=ImportResult.CANCELLED).validate()


class AuditSerializationTests(unittest.TestCase):
    def test_serialization_is_deterministic_and_json_compatible(self) -> None:
        audit = make_audit()
        first = serialize(audit)
        self.assertEqual(first, serialize(audit))
        self.assertEqual(deserialize(first.encode("utf-8")), audit)
        assert_json_primitives(self, audit.to_dict())

    def test_json_byte_limit_exact_and_one_past(self) -> None:
        audit = make_audit()
        text = serialize(audit)
        exact = len(text.encode("utf-8"))
        with patch("capture_import.audit.MAX_JSON_BYTES", exact):
            self.assertEqual(deserialize(text), audit)
            self.assertEqual(serialize(audit), text)
            with self.assertRaisesRegex(ValueError, "byte limit"):
                deserialize(text + " ")
        with patch("capture_import.audit.MAX_JSON_BYTES", exact - 1):
            with self.assertRaisesRegex(ValueError, "byte limit"):
                serialize(audit)

    def test_duplicate_keys_invalid_utf8_and_absolute_fields_are_rejected(self) -> None:
        text = serialize(make_audit())
        duplicate = text.replace(
            '"audit_schema_version":"1.0"',
            '"audit_schema_version":"1.0","audit_schema_version":"1.0"',
            1,
        )
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            deserialize(duplicate)
        with self.assertRaisesRegex(ValueError, "strict UTF-8"):
            deserialize(b"\xff")
        payload = json.loads(text)
        self.assertNotIn("snapshot_relative_path", payload)
        self.assertNotIn("source_path", payload)
        self.assertNotIn("C:\\\\Users", text)


if __name__ == "__main__":
    unittest.main()
