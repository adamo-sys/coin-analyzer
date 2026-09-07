import json
import unittest
from dataclasses import FrozenInstanceError

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
    EvaluationCase,
    EvaluationOutcomeClassification,
)
from ai_execution_audit import (
    AIExecutionAuditRecord,
    AI_EXECUTION_AUDIT_SCHEMA_VERSION,
    HumanDisposition,
    PersistenceDisposition,
    build_ai_execution_audit_record,
    serialize_ai_execution_audit_record,
)
from identification_specialist import IdentificationSpecialistRequest
from identification_specialist_execution import (
    DETERMINISTIC_IDENTIFICATION_EXECUTOR,
    execute_and_compare_identification,
)


class AIExecutionAuditContractTests(unittest.TestCase):
    def setUp(self):
        self.request = IdentificationSpecialistRequest(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:coin-001",
            candidate_ids=("candidate:a", "candidate:b"),
            eligible_candidate_ids=("candidate:b",),
            evidence_refs=("evidence:obverse", "evidence:reverse"),
        )
        self.evaluation_case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:coin-001",
            allowed_candidate_ids=("candidate:b",),
            evidence_refs=("evidence:obverse", "evidence:reverse"),
        )
        self.report = execute_and_compare_identification(
            self.request,
            DETERMINISTIC_IDENTIFICATION_EXECUTOR,
            self.evaluation_case,
        )

    def build(self, **overrides):
        arguments = {
            "execution_id": "exec-001",
            "occurred_at": "2026-09-07T22:55:00Z",
            "workflow_id": "visual-identification-v1",
            "request": self.request,
            "report": self.report,
            "human_disposition": HumanDisposition.ACCEPTED,
            "persistence_disposition": PersistenceDisposition.COMMITTED,
        }
        arguments.update(overrides)
        return build_ai_execution_audit_record(**arguments)

    def test_build_reuses_existing_execution_and_outcome_identity(self):
        record = self.build()
        self.assertEqual(record.schema_version, AI_EXECUTION_AUDIT_SCHEMA_VERSION)
        self.assertEqual(record.executor_id, self.report.execution.executor_id)
        self.assertEqual(record.case_id, self.request.case_id)
        self.assertIs(record.evidence_refs, self.request.evidence_refs)
        self.assertIs(record.authorized_candidate_ids, self.request.candidate_ids)
        self.assertEqual(record.selected_candidate_id, "candidate:b")
        self.assertFalse(record.abstained)
        self.assertTrue(record.verifier_accepted)
        self.assertEqual(record.verifier_reason_codes, ())
        self.assertIs(
            record.evaluation_classification,
            EvaluationOutcomeClassification.CORRECT,
        )

    def test_record_is_frozen_and_slotted(self):
        record = self.build()
        with self.assertRaises(FrozenInstanceError):
            record.execution_id = "different"
        self.assertFalse(hasattr(record, "__dict__"))

    def test_serialization_is_deterministic_and_has_exact_bounded_schema(self):
        record = self.build()
        first = serialize_ai_execution_audit_record(record)
        second = serialize_ai_execution_audit_record(record)
        self.assertEqual(first, second)

        payload = json.loads(first)
        self.assertEqual(
            set(payload),
            {
                "schema_version",
                "execution_id",
                "occurred_at",
                "workflow_id",
                "executor_id",
                "case_id",
                "evidence_refs",
                "authorized_candidate_ids",
                "selected_candidate_id",
                "abstained",
                "verifier_accepted",
                "verifier_reason_codes",
                "evaluation_classification",
                "evaluation_reason_codes",
                "human_disposition",
                "persistence_disposition",
            },
        )
        self.assertEqual(payload["evaluation_classification"], "CORRECT")
        self.assertEqual(payload["human_disposition"], "accepted")
        self.assertEqual(payload["persistence_disposition"], "committed")

    def test_serialized_schema_has_no_arbitrary_sensitive_payload_channels(self):
        serialized = serialize_ai_execution_audit_record(self.build()).lower()
        forbidden = (
            "api_key",
            "authorization",
            "prompt",
            "base64",
            "image_bytes",
            "exception",
            "traceback",
            "collection",
            "reasoning",
            "command",
            "environment",
        )
        for token in forbidden:
            self.assertNotIn(token, serialized)

    def test_invalid_execution_and_workflow_labels_fail_closed(self):
        for name, value in (
            ("execution_id", "bad id with spaces"),
            ("workflow_id", ""),
            ("execution_id", "x" * 129),
        ):
            with self.subTest(name=name, value=value):
                with self.assertRaises(ValueError):
                    self.build(**{name: value})

    def test_timestamp_must_be_explicit_utc_rfc3339_seconds(self):
        for value in (
            "2026-09-07 22:55:00Z",
            "2026-09-07T22:55:00+00:00",
            "2026-09-07T22:55Z",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.build(occurred_at=value)

    def test_selected_candidate_must_be_authorized_and_match_abstention_state(self):
        base = self.build()
        unauthorized = AIExecutionAuditRecord(
            **{
                field: getattr(base, field)
                for field in base.__dataclass_fields__
                if field != "selected_candidate_id"
            },
            selected_candidate_id="candidate:unauthorized",
        )
        with self.assertRaises(ValueError):
            unauthorized.validate()

        contradictory = AIExecutionAuditRecord(
            **{
                field: getattr(base, field)
                for field in base.__dataclass_fields__
                if field != "abstained"
            },
            abstained=True,
        )
        with self.assertRaises(ValueError):
            contradictory.validate()

    def test_dispositions_are_strict_enum_values(self):
        base = self.build()
        invalid_human = AIExecutionAuditRecord(
            **{
                field: getattr(base, field)
                for field in base.__dataclass_fields__
                if field != "human_disposition"
            },
            human_disposition="accepted",
        )
        with self.assertRaises(TypeError):
            invalid_human.validate()

        invalid_persistence = AIExecutionAuditRecord(
            **{
                field: getattr(base, field)
                for field in base.__dataclass_fields__
                if field != "persistence_disposition"
            },
            persistence_disposition="committed",
        )
        with self.assertRaises(TypeError):
            invalid_persistence.validate()

    def test_nonaccepted_human_outcomes_cannot_claim_persistence(self):
        for human_disposition in (
            HumanDisposition.REJECTED,
            HumanDisposition.DEFERRED,
            HumanDisposition.CANCELLED,
            HumanDisposition.NOT_REACHED,
        ):
            with self.subTest(human_disposition=human_disposition):
                with self.assertRaises(ValueError):
                    self.build(
                        human_disposition=human_disposition,
                        persistence_disposition=PersistenceDisposition.COMMITTED,
                    )

                record = self.build(
                    human_disposition=human_disposition,
                    persistence_disposition=PersistenceDisposition.NOT_ATTEMPTED,
                )
                record.validate()

    def test_accepted_human_outcome_may_record_failed_or_blocked_persistence(self):
        for persistence_disposition in (
            PersistenceDisposition.REJECTED_STALE,
            PersistenceDisposition.BLOCKED_LOAD_FAILURE,
            PersistenceDisposition.FAILED,
            PersistenceDisposition.NOT_ATTEMPTED,
        ):
            with self.subTest(persistence_disposition=persistence_disposition):
                record = self.build(
                    persistence_disposition=persistence_disposition,
                )
                record.validate()


if __name__ == "__main__":
    unittest.main()
