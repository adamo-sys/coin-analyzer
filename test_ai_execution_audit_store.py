from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from ai_evaluation_contracts import EvaluationOutcomeClassification
from ai_execution_audit import (
    AI_EXECUTION_AUDIT_SCHEMA_VERSION,
    AIExecutionAuditRecord,
    HumanDisposition,
    PersistenceDisposition,
    serialize_ai_execution_audit_record,
)
from ai_execution_audit_store import (
    AIExecutionAuditDuplicateExecution,
    AIExecutionAuditStore,
    AIExecutionAuditStoreCorrupt,
    AIExecutionAuditStoreLocked,
    parse_ai_execution_audit_record,
)
from capture_import.lock import PackageImportLock


def _record(execution_id: str = "exec-001") -> AIExecutionAuditRecord:
    record = AIExecutionAuditRecord(
        schema_version=AI_EXECUTION_AUDIT_SCHEMA_VERSION,
        execution_id=execution_id,
        occurred_at="2026-09-07T23:10:00Z",
        workflow_id="visual-identification",
        executor_id="deterministic-identification-v1",
        case_id="case-001",
        evidence_refs=("evidence-001",),
        authorized_candidate_ids=("coin-001", "coin-002"),
        selected_candidate_id="coin-001",
        abstained=False,
        verifier_accepted=True,
        verifier_reason_codes=(),
        evaluation_classification=EvaluationOutcomeClassification.CORRECT,
        evaluation_reason_codes=(),
        human_disposition=HumanDisposition.ACCEPTED,
        persistence_disposition=PersistenceDisposition.COMMITTED,
    )
    record.validate()
    return record


class AIExecutionAuditParsingTests(unittest.TestCase):
    def test_round_trip_preserves_record_exactly(self) -> None:
        original = _record()
        parsed = parse_ai_execution_audit_record(
            serialize_ai_execution_audit_record(original)
        )
        self.assertEqual(parsed, original)

    def test_unknown_field_is_rejected(self) -> None:
        payload = json.loads(serialize_ai_execution_audit_record(_record()))
        payload["prompt"] = "must never become an audit metadata channel"
        with self.assertRaises(AIExecutionAuditStoreCorrupt):
            parse_ai_execution_audit_record(json.dumps(payload))

    def test_missing_field_is_rejected(self) -> None:
        payload = json.loads(serialize_ai_execution_audit_record(_record()))
        del payload["workflow_id"]
        with self.assertRaises(AIExecutionAuditStoreCorrupt):
            parse_ai_execution_audit_record(json.dumps(payload))

    def test_duplicate_json_key_is_rejected(self) -> None:
        valid = serialize_ai_execution_audit_record(_record())
        duplicate = valid[:-1] + ',"execution_id":"other"}'
        with self.assertRaises(AIExecutionAuditStoreCorrupt):
            parse_ai_execution_audit_record(duplicate)

    def test_unsupported_enum_value_is_rejected(self) -> None:
        payload = json.loads(serialize_ai_execution_audit_record(_record()))
        payload["human_disposition"] = "auto_approved"
        with self.assertRaises(AIExecutionAuditStoreCorrupt):
            parse_ai_execution_audit_record(json.dumps(payload))


class AIExecutionAuditStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.audit_path = self.root / "ai-execution-audit.jsonl"
        self.store = AIExecutionAuditStore(self.audit_path)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_missing_store_reads_as_empty(self) -> None:
        self.assertEqual(self.store.read_all(), ())
        self.assertFalse(self.audit_path.exists())

    def test_append_creates_one_canonical_jsonl_record(self) -> None:
        record = _record()
        self.store.append(record)

        self.assertEqual(self.store.read_all(), (record,))
        self.assertEqual(
            self.audit_path.read_text(encoding="utf-8"),
            serialize_ai_execution_audit_record(record) + "\n",
        )

    def test_multiple_appends_preserve_prior_records_and_order(self) -> None:
        first = _record("exec-001")
        second = replace(first, execution_id="exec-002", occurred_at="2026-09-07T23:11:00Z")

        self.store.append(first)
        bytes_after_first = self.audit_path.read_bytes()
        self.store.append(second)

        self.assertEqual(self.store.read_all(), (first, second))
        self.assertTrue(self.audit_path.read_bytes().startswith(bytes_after_first))

    def test_duplicate_execution_id_is_rejected_without_changing_bytes(self) -> None:
        record = _record()
        self.store.append(record)
        before = self.audit_path.read_bytes()

        with self.assertRaises(AIExecutionAuditDuplicateExecution):
            self.store.append(record)

        self.assertEqual(self.audit_path.read_bytes(), before)

    def test_corrupt_existing_store_blocks_append_without_overwrite(self) -> None:
        corrupt = b'{"schema_version":"1"}\n'
        self.audit_path.write_bytes(corrupt)

        with self.assertRaises(AIExecutionAuditStoreCorrupt):
            self.store.append(_record())

        self.assertEqual(self.audit_path.read_bytes(), corrupt)

    def test_missing_trailing_newline_is_corruption(self) -> None:
        self.audit_path.write_text(
            serialize_ai_execution_audit_record(_record()),
            encoding="utf-8",
        )
        with self.assertRaises(AIExecutionAuditStoreCorrupt):
            self.store.read_all()

    def test_blank_jsonl_line_is_corruption(self) -> None:
        self.audit_path.write_text(
            serialize_ai_execution_audit_record(_record()) + "\n\n",
            encoding="utf-8",
        )
        with self.assertRaises(AIExecutionAuditStoreCorrupt):
            self.store.read_all()

    def test_duplicate_execution_ids_on_disk_are_corruption(self) -> None:
        line = serialize_ai_execution_audit_record(_record()) + "\n"
        self.audit_path.write_text(line + line, encoding="utf-8")
        with self.assertRaises(AIExecutionAuditStoreCorrupt):
            self.store.read_all()

    def test_symlink_store_is_rejected_when_supported(self) -> None:
        target = self.root / "target.jsonl"
        target.write_text("", encoding="utf-8")
        try:
            self.audit_path.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are unavailable")
        with self.assertRaises(AIExecutionAuditStoreCorrupt):
            self.store.read_all()

    def test_cooperating_writer_lock_fails_closed(self) -> None:
        with PackageImportLock.acquire(self.store.lock_path):
            with self.assertRaises(AIExecutionAuditStoreLocked):
                self.store.append(_record())
        self.assertFalse(self.audit_path.exists())

    def test_store_api_has_no_delete_or_update_operation(self) -> None:
        forbidden = {"delete", "remove", "update", "replace", "truncate", "clear"}
        public_names = {
            name for name in dir(AIExecutionAuditStore) if not name.startswith("_")
        }
        self.assertTrue(forbidden.isdisjoint(public_names))

    def test_audit_path_is_independent_of_collection_path(self) -> None:
        collection = self.root / "collection.json"
        collection.write_bytes(b'{"authoritative":"unchanged"}')
        before = collection.read_bytes()

        self.store.append(_record())

        self.assertEqual(collection.read_bytes(), before)
        self.assertTrue(self.audit_path.exists())


if __name__ == "__main__":
    unittest.main()
