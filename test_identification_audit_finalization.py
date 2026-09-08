import tempfile
import unittest
from pathlib import Path

from ai_evaluation_contracts import CURRENT_AI_EVALUATION_SCHEMA_VERSION, EvaluationCase
from ai_execution_audit import HumanDisposition, PersistenceDisposition
from ai_execution_audit_store import (
    AIExecutionAuditDuplicateExecution,
    AIExecutionAuditStore,
)
from identification_audit_finalization import finalize_identification_execution_audit
from identification_specialist import (
    IdentificationSpecialistRequest,
    run_identification_specialist,
)
from identification_specialist_execution import (
    IdentificationSpecialistExecutor,
    execute_and_compare_identification,
)


class IdentificationAuditFinalizationTests(unittest.TestCase):
    def setUp(self):
        self.request = IdentificationSpecialistRequest(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:coin-001",
            candidate_ids=("candidate:a", "candidate:b"),
            eligible_candidate_ids=("candidate:b",),
            evidence_refs=("evidence:obverse", "evidence:reverse"),
        )
        self.case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:coin-001",
            allowed_candidate_ids=("candidate:b",),
            evidence_refs=("evidence:obverse", "evidence:reverse"),
        )
        self.calls = 0

        def execute(request):
            self.calls += 1
            return run_identification_specialist(request)

        self.executor = IdentificationSpecialistExecutor(
            executor_id="counted-specialist-v1",
            execute=execute,
        )
        self.report = execute_and_compare_identification(
            self.request,
            self.executor,
            self.case,
        )
        self.assertEqual(self.calls, 1)

    def finalize(self, store, **overrides):
        arguments = {
            "execution_id": "exec-001",
            "occurred_at": "2026-09-08T00:35:00Z",
            "workflow_id": "identification-specialist-v1",
            "request": self.request,
            "report": self.report,
            "human_disposition": HumanDisposition.ACCEPTED,
            "persistence_disposition": PersistenceDisposition.COMMITTED,
            "store": store,
        }
        arguments.update(overrides)
        return finalize_identification_execution_audit(**arguments)

    def test_finalization_appends_exactly_one_validated_record(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AIExecutionAuditStore(Path(directory) / "ai-audit.jsonl")
            record = self.finalize(store)

            stored = store.read_all()
            self.assertEqual(stored, (record,))
            self.assertEqual(record.executor_id, self.report.execution.executor_id)
            self.assertEqual(record.case_id, self.request.case_id)
            self.assertIs(record.evidence_refs, self.request.evidence_refs)
            self.assertIs(record.authorized_candidate_ids, self.request.candidate_ids)

    def test_finalization_does_not_reexecute_specialist(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AIExecutionAuditStore(Path(directory) / "ai-audit.jsonl")
            self.finalize(store)
            self.assertEqual(self.calls, 1)

    def test_invalid_disposition_fails_before_audit_file_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ai-audit.jsonl"
            store = AIExecutionAuditStore(path)
            with self.assertRaises(ValueError):
                self.finalize(
                    store,
                    human_disposition=HumanDisposition.REJECTED,
                    persistence_disposition=PersistenceDisposition.COMMITTED,
                )
            self.assertFalse(path.exists())
            self.assertEqual(self.calls, 1)

    def test_duplicate_execution_id_fails_closed_without_reexecution(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AIExecutionAuditStore(Path(directory) / "ai-audit.jsonl")
            first = self.finalize(store)
            with self.assertRaises(AIExecutionAuditDuplicateExecution):
                self.finalize(store)
            self.assertEqual(store.read_all(), (first,))
            self.assertEqual(self.calls, 1)

    def test_store_type_is_explicit(self):
        with self.assertRaises(TypeError):
            self.finalize(object())
        self.assertEqual(self.calls, 1)


if __name__ == "__main__":
    unittest.main()
