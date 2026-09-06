import unittest

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
    EvaluationCase,
    EvaluationOutcomeClassification,
)
from capture_import.desktop_acceptance_ai_evaluation_bridge import (
    evaluate_desktop_acceptance_result,
)
from capture_import.desktop_acceptance_scoring import DesktopAcceptanceResult


def _candidate_case(case_id: str = "case:001") -> EvaluationCase:
    return EvaluationCase(
        schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
        case_id=case_id,
        allowed_candidate_ids=("candidate:accepted",),
    )


class DesktopAcceptanceAIEvaluationBridgeTests(unittest.TestCase):
    def test_identify_composes_through_existing_adapter_and_evaluator(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:001",
            observed_action="identify",
            proposed_identity={"country": "Canada"},
        )

        outcome = evaluate_desktop_acceptance_result(
            _candidate_case(),
            result,
            candidate_id="candidate:accepted",
        )

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.CORRECT,
        )
        self.assertEqual(outcome.reason_codes, ())

    def test_unlisted_identify_is_incorrect(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:001",
            observed_action="identify",
            proposed_identity={"country": "Canada"},
        )

        outcome = evaluate_desktop_acceptance_result(
            _candidate_case(),
            result,
            candidate_id="candidate:other",
        )

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.INCORRECT,
        )
        self.assertEqual(
            outcome.reason_codes,
            ("candidate_not_allowed",),
        )

    def test_abstain_remains_explicit_abstention(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:001",
            observed_action="abstain",
            proposed_identity=None,
        )

        outcome = evaluate_desktop_acceptance_result(
            _candidate_case(),
            result,
        )

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.ABSTAINED,
        )

    def test_unavailable_preserves_provider_unavailable_reason(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:001",
            observed_action="unavailable",
            proposed_identity=None,
        )

        outcome = evaluate_desktop_acceptance_result(
            _candidate_case(),
            result,
            evidence_refs=("ref:provider",),
        )

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.INVALID_OR_MISSING,
        )
        self.assertEqual(
            outcome.reason_codes,
            ("provider_unavailable",),
        )
        self.assertEqual(
            outcome.evidence_refs,
            ("ref:provider",),
        )

    def test_infrastructure_failure_preserves_reason(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:001",
            observed_action="infrastructure_failure",
            proposed_identity=None,
        )

        outcome = evaluate_desktop_acceptance_result(
            _candidate_case(),
            result,
            evidence_refs=("ref:infra",),
        )

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.INVALID_OR_MISSING,
        )
        self.assertEqual(
            outcome.reason_codes,
            ("infrastructure_failure",),
        )
        self.assertEqual(
            outcome.evidence_refs,
            ("ref:infra",),
        )

    def test_case_identity_mismatch_fails_closed(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:other",
            observed_action="abstain",
            proposed_identity=None,
        )

        with self.assertRaisesRegex(ValueError, "case_id"):
            evaluate_desktop_acceptance_result(
                _candidate_case(),
                result,
            )

    def test_unavailable_rejects_candidate_id(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:001",
            observed_action="unavailable",
            proposed_identity=None,
        )

        with self.assertRaisesRegex(ValueError, "candidate_id"):
            evaluate_desktop_acceptance_result(
                _candidate_case(),
                result,
                candidate_id="candidate:forbidden",
            )

    def test_infrastructure_failure_rejects_candidate_id(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:001",
            observed_action="infrastructure_failure",
            proposed_identity=None,
        )

        with self.assertRaisesRegex(ValueError, "candidate_id"):
            evaluate_desktop_acceptance_result(
                _candidate_case(),
                result,
                candidate_id="candidate:forbidden",
            )

    def test_invalid_authoritative_case_still_fails_closed(self) -> None:
        case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:invalid",
        )
        result = DesktopAcceptanceResult(
            case_id="case:invalid",
            observed_action="unavailable",
            proposed_identity=None,
        )

        with self.assertRaises(ValueError):
            evaluate_desktop_acceptance_result(case, result)

    def test_bridge_is_deterministic(self) -> None:
        case = _candidate_case()
        result = DesktopAcceptanceResult(
            case_id="case:001",
            observed_action="infrastructure_failure",
            proposed_identity=None,
        )

        first = evaluate_desktop_acceptance_result(case, result)
        second = evaluate_desktop_acceptance_result(case, result)

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
