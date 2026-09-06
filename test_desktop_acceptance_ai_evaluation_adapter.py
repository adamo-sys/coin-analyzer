import unittest

from ai_evaluation_contracts import EvaluationOutcomeClassification
from ai_evaluation_evaluator import evaluate_observed_result
from capture_import.desktop_acceptance_ai_evaluation_adapter import (
    adapt_desktop_acceptance_result,
)
from capture_import.desktop_acceptance_scoring import DesktopAcceptanceResult
from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
    EvaluationCase,
)


class DesktopAcceptanceAIEvaluationAdapterTests(unittest.TestCase):
    def test_identify_requires_explicit_candidate_id(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:identify",
            observed_action="identify",
            proposed_identity={
                "country": "Canada",
                "denomination": "10 cents",
                "year": "1858",
            },
        )

        with self.assertRaisesRegex(ValueError, "candidate_id"):
            adapt_desktop_acceptance_result(result)

    def test_identify_preserves_explicit_candidate_id(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:identify",
            observed_action="identify",
            proposed_identity={
                "country": "Canada",
                "denomination": "10 cents",
                "year": "1858",
            },
            provider_source_score=0.91,
        )

        observed = adapt_desktop_acceptance_result(
            result,
            candidate_id="candidate:1858-10c",
            evidence_refs=("ref:obverse", "ref:reverse"),
        )

        self.assertIsNotNone(observed)
        assert observed is not None
        self.assertEqual(observed.case_id, "case:identify")
        self.assertEqual(observed.candidate_id, "candidate:1858-10c")
        self.assertFalse(observed.abstained)
        self.assertEqual(
            observed.evidence_refs,
            ("ref:obverse", "ref:reverse"),
        )

    def test_adapter_does_not_manufacture_identity_from_proposal(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:identify",
            observed_action="identify",
            proposed_identity={
                "country": "Canada",
                "denomination": "10 cents",
                "year": "1858",
            },
        )

        observed = adapt_desktop_acceptance_result(
            result,
            candidate_id="caller-authoritative-id",
        )

        self.assertIsNotNone(observed)
        assert observed is not None
        self.assertEqual(
            observed.candidate_id,
            "caller-authoritative-id",
        )

    def test_provider_source_score_is_not_propagated(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:identify",
            observed_action="identify",
            proposed_identity={"country": "Canada"},
            provider_source_score=0.42,
        )

        observed = adapt_desktop_acceptance_result(
            result,
            candidate_id="candidate:explicit",
        )

        self.assertIsNotNone(observed)
        assert observed is not None
        self.assertFalse(hasattr(observed, "provider_source_score"))
        self.assertFalse(hasattr(observed, "confidence"))

    def test_abstain_maps_to_explicit_abstention(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:abstain",
            observed_action="abstain",
            proposed_identity=None,
        )

        observed = adapt_desktop_acceptance_result(
            result,
            evidence_refs=("ref:abstain",),
        )

        self.assertIsNotNone(observed)
        assert observed is not None
        self.assertEqual(observed.case_id, "case:abstain")
        self.assertTrue(observed.abstained)
        self.assertIsNone(observed.candidate_id)
        self.assertEqual(observed.evidence_refs, ("ref:abstain",))

    def test_non_identify_rejects_candidate_id(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:abstain",
            observed_action="abstain",
            proposed_identity=None,
        )

        with self.assertRaisesRegex(ValueError, "candidate_id"):
            adapt_desktop_acceptance_result(
                result,
                candidate_id="candidate:forbidden",
            )

    def test_unavailable_maps_to_no_observed_result(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:unavailable",
            observed_action="unavailable",
            proposed_identity=None,
        )

        observed = adapt_desktop_acceptance_result(result)

        self.assertIsNone(observed)

    def test_infrastructure_failure_maps_to_no_observed_result(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:infrastructure",
            observed_action="infrastructure_failure",
            proposed_identity=None,
        )

        observed = adapt_desktop_acceptance_result(result)

        self.assertIsNone(observed)

    def test_evidence_refs_must_satisfy_frozen_contract(self) -> None:
        result = DesktopAcceptanceResult(
            case_id="case:abstain",
            observed_action="abstain",
            proposed_identity=None,
        )

        with self.assertRaises(ValueError):
            adapt_desktop_acceptance_result(
                result,
                evidence_refs=("ref:z", "ref:a"),
            )

    def test_adapter_composes_with_deterministic_evaluator(self) -> None:
        case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:identify",
            allowed_candidate_ids=("candidate:1858-10c",),
        )
        result = DesktopAcceptanceResult(
            case_id="case:identify",
            observed_action="identify",
            proposed_identity={
                "country": "Canada",
                "denomination": "10 cents",
                "year": "1858",
            },
        )

        observed = adapt_desktop_acceptance_result(
            result,
            candidate_id="candidate:1858-10c",
        )
        outcome = evaluate_observed_result(case, observed)

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.CORRECT,
        )

    def test_unavailable_composes_as_invalid_or_missing(self) -> None:
        case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:unavailable",
            allowed_candidate_ids=("candidate:expected",),
        )
        result = DesktopAcceptanceResult(
            case_id="case:unavailable",
            observed_action="unavailable",
            proposed_identity=None,
        )

        observed = adapt_desktop_acceptance_result(result)
        outcome = evaluate_observed_result(case, observed)

        self.assertEqual(
            outcome.classification,
            EvaluationOutcomeClassification.INVALID_OR_MISSING,
        )
        self.assertEqual(
            outcome.reason_codes,
            ("missing_observed_result",),
        )


if __name__ == "__main__":
    unittest.main()
