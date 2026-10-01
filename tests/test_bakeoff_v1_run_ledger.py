"""Focused validation tests for the Bake-Off v1 normalized run ledger."""

from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from tools.bakeoff_v1_run_ledger import RunLedgerValidationError, validate_run_record

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks" / "bakeoff-v1" / "manifest.json"
SIDECAR = ROOT / "benchmarks" / "bakeoff-v1" / "manifest.sha256"
EXPECTED_CORPUS_SEAL = "1caa322927e4147f2f5e02d0cdb7a0069917da16277c2424700e9dd6d694ded1"


def valid_record() -> dict[str, object]:
    return {
        "schema_version": "1",
        "benchmark_version": "1.0",
        "corpus_manifest_sha256": SIDECAR.read_text(encoding="ascii").strip(),
        "task_id": "BO1-TASK-PACKETS",
        "contestant": {
            "contestant_id": "native-codex-agents-v1",
            "model": "declared-model",
            "harness": None,
            "memory_layer": None,
            "skills_or_instructions_layer": "AGENTS.md",
            "control_orchestration_layer": None,
            "tool_permissions": ["filesystem-read", "filesystem-write"],
            "network_policy": "network_and_provider_access_forbidden",
            "context_policy": "native",
            "environment_metadata": {"os": "Windows"},
        },
        "run_id": "bo1-task-packets-native-001",
        "starting_sha": "9369b3f6d830d2f0ee7fe41cdabc8c57d7b77612",
        "ending_sha": None,
        "started_at_utc": "2026-09-30T12:00:00Z",
        "ended_at_utc": "2026-09-30T12:01:00Z",
        "terminal_status": "completed",
        "measurements": {
            "wall_seconds": {"availability": "measured", "value": 60, "provenance": ["host-clock"]},
            "agent_turns": {"availability": "unavailable", "value": None, "provenance": []},
            "required_validation": {"availability": "derived", "value": "passed", "provenance": ["test-output"]},
            "independent_review": {"availability": "not_yet_graded", "value": None, "provenance": []},
        },
        "human_interventions": [
            {
                "timestamp_utc": "2026-09-30T12:00:30Z",
                "intervention_type": "environment_clarification",
                "reason": "recorded for comparison",
                "actor_category": "human_operator",
                "execution_changed": False,
            }
        ],
        "artifacts": ["outcome-packet.json"],
    }


class BakeoffV1RunLedgerTests(unittest.TestCase):
    def test_freeze_grade_record_requires_an_external_corpus_seal(self) -> None:
        with self.assertRaisesRegex(RunLedgerValidationError, "external corpus seal"):
            validate_run_record(valid_record(), MANIFEST, SIDECAR, expected_corpus_seal=None)
        validated = validate_run_record(valid_record(), MANIFEST, SIDECAR, expected_corpus_seal=EXPECTED_CORPUS_SEAL)
        self.assertEqual(validated["task_id"], "BO1-TASK-PACKETS")

    def test_accepts_baseline_style_record_with_null_layers_and_unavailable_telemetry(self) -> None:
        record = valid_record()
        validated = validate_run_record(record, MANIFEST, SIDECAR, expected_corpus_seal=EXPECTED_CORPUS_SEAL)
        self.assertEqual(validated["contestant"]["memory_layer"], None)
        self.assertEqual(validated["measurements"]["agent_turns"]["availability"], "unavailable")

    def test_accepts_measured_and_derived_measurements_with_provenance(self) -> None:
        record = valid_record()
        validated = validate_run_record(record, MANIFEST, SIDECAR, expected_corpus_seal=EXPECTED_CORPUS_SEAL)
        self.assertEqual(validated["measurements"]["wall_seconds"]["value"], 60)
        self.assertEqual(validated["measurements"]["required_validation"]["provenance"], ["test-output"])

    def test_rejects_manifest_task_and_start_sha_mismatches(self) -> None:
        for field, value in (("task_id", "UNKNOWN"), ("starting_sha", "0" * 40)):
            record = valid_record()
            record[field] = value
            with self.assertRaises(RunLedgerValidationError):
                validate_run_record(record, MANIFEST, SIDECAR, expected_corpus_seal=EXPECTED_CORPUS_SEAL)

    def test_rejects_end_before_start_and_zero_for_unavailable_measurement(self) -> None:
        record = valid_record()
        record["ended_at_utc"] = "2026-09-30T11:59:59Z"
        with self.assertRaisesRegex(RunLedgerValidationError, "end"):
            validate_run_record(record, MANIFEST, SIDECAR, expected_corpus_seal=EXPECTED_CORPUS_SEAL)
        record = valid_record()
        record["measurements"] = deepcopy(record["measurements"])
        record["measurements"]["agent_turns"]["value"] = 0
        with self.assertRaisesRegex(RunLedgerValidationError, "unavailable"):
            validate_run_record(record, MANIFEST, SIDECAR, expected_corpus_seal=EXPECTED_CORPUS_SEAL)

    def test_rejects_invalid_availability_and_duplicate_run_context(self) -> None:
        record = valid_record()
        record["measurements"] = deepcopy(record["measurements"])
        record["measurements"]["agent_turns"]["availability"] = "unknown"
        with self.assertRaises(RunLedgerValidationError):
            validate_run_record(record, MANIFEST, SIDECAR, expected_corpus_seal=EXPECTED_CORPUS_SEAL)
        with self.assertRaisesRegex(RunLedgerValidationError, "duplicate"):
            validate_run_record(valid_record(), MANIFEST, SIDECAR, expected_corpus_seal=EXPECTED_CORPUS_SEAL, known_run_ids={"bo1-task-packets-native-001"})


if __name__ == "__main__":
    unittest.main()
