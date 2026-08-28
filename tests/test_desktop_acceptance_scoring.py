from __future__ import annotations

from pathlib import Path
import unittest

from capture_import.desktop_acceptance_canonicalization import (
    load_desktop_acceptance_canonicalization_policy,
)
from capture_import.desktop_acceptance_scoring import (
    DesktopAcceptanceResult,
    DesktopAcceptanceScoringError,
    score_desktop_acceptance_results,
)
from capture_import.desktop_acceptance_set import DesktopAcceptanceCase, DesktopAcceptanceManifest


def _case(case_id: str, specimen_id: str, action: str = "identify") -> DesktopAcceptanceCase:
    return DesktopAcceptanceCase(
        case_id=case_id, specimen_id=specimen_id, repeated_case_id=None,
        expected_action=action,
        expected_identity={"country": "CAN", "denomination": "25 cents", "year": "1964"},
        reserved_attribution={"mint": None, "mint_mark": None, "variety": None,
                              "catalog_reference": None},
        capture_conditions={}, capture_difference_fields=None,
        capture_difference_rationale=None, cohorts=("standard",), stability=False,
        privacy_classification="synthetic", prior_benchmark_use={"used": False},
        ground_truth_review={}, action_review={}, images=(), notes="synthetic",
    )


class DesktopAcceptanceScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_desktop_acceptance_canonicalization_policy()

    def setUp(self):
        self.manifest = DesktopAcceptanceManifest(
            root=Path("."),
            cases=(
                _case("case-001", "specimen-001"),
                _case("case-002", "specimen-001"),
                _case("case-003", "specimen-002"),
                _case("case-004", "specimen-003", "abstain"),
            ),
            canonicalization_policy={}, freeze={},
            stability_relevant_cohorts=("standard",),
        )

    def test_scores_canonical_identity_and_specimen_weighting(self):
        results = (
            DesktopAcceptanceResult("case-001", "identify", {
                "country": "Canada", "denomination": "quarter", "year": "１９６４"}),
            DesktopAcceptanceResult("case-002", "identify", {
                "country": "CA", "denomination": "25 cents", "year": "1964"}),
            DesktopAcceptanceResult("case-003", "identify", {
                "country": "CAN", "denomination": "25 cents", "year": "1964"}),
            DesktopAcceptanceResult("case-004", "abstain", None),
        )
        report = score_desktop_acceptance_results(self.manifest, results, self.policy)
        identity = report["complete_identity_correctness"]
        self.assertEqual(identity["specimen_weighted"], {
            "numerator": 3, "denominator": 4, "rate": 0.75, "specimens": 2,
        })
        self.assertEqual(identity["case_weighted_diagnostic"]["numerator"], 2)
        self.assertEqual(identity["case_weighted_diagnostic"]["denominator"], 3)
        self.assertEqual(report["action_correctness"]["specimen_weighted"]["rate"], 1.0)
        self.assertFalse(report["per_case"][0]["exact_identity_diagnostic"])
        self.assertTrue(report["per_case"][0]["complete_identity_correct"])

    def test_partial_identity_gets_no_complete_credit(self):
        results = (
            DesktopAcceptanceResult("case-001", "identify", {"country": "CAN"}),
            DesktopAcceptanceResult("case-002", "abstain", None),
            DesktopAcceptanceResult("case-003", "unavailable", None),
            DesktopAcceptanceResult("case-004", "abstain", None),
        )
        report = score_desktop_acceptance_results(self.manifest, results, self.policy)
        self.assertFalse(report["per_case"][0]["complete_identity_correct"])
        self.assertIsNone(report["per_case"][0]["canonical_proposed_identity"])

    def test_infrastructure_is_explicit_and_excluded(self):
        results = (
            DesktopAcceptanceResult("case-001", "infrastructure_failure", None),
            DesktopAcceptanceResult("case-002", "identify", {
                "country": "CAN", "denomination": "25 cents", "year": "1964"}),
            DesktopAcceptanceResult("case-003", "identify", {
                "country": "CAN", "denomination": "25 cents", "year": "1964"}),
            DesktopAcceptanceResult("case-004", "abstain", None),
        )
        report = score_desktop_acceptance_results(self.manifest, results, self.policy)
        self.assertEqual(report["infrastructure_failures"]["case_ids"], ["case-001"])
        self.assertEqual(report["action_correctness"]["case_weighted_diagnostic"]["denominator"], 3)
        self.assertIsNone(report["per_case"][0]["action_correct"])

    def test_missing_duplicate_or_unsorted_results_fail_closed(self):
        valid = DesktopAcceptanceResult("case-001", "abstain", None)
        for results in ((valid,), (valid, valid)):
            with self.subTest(results=results):
                with self.assertRaises(DesktopAcceptanceScoringError):
                    score_desktop_acceptance_results(self.manifest, results, self.policy)

    def test_system_confidence_and_invalid_source_scores_are_rejected(self):
        with self.assertRaisesRegex(DesktopAcceptanceScoringError, "confidence"):
            DesktopAcceptanceResult("case-001", "abstain", None, system_confidence=0.9)
        for score in (float("nan"), float("inf"), True):
            with self.subTest(score=score):
                with self.assertRaisesRegex(DesktopAcceptanceScoringError, "finite"):
                    DesktopAcceptanceResult(
                        "case-001", "abstain", None, provider_source_score=score
                    )

    def test_report_is_deterministic_and_labels_source_score_uncalibrated(self):
        results = (
            DesktopAcceptanceResult("case-001", "abstain", None, 0.75),
            DesktopAcceptanceResult("case-002", "abstain", None),
            DesktopAcceptanceResult("case-003", "abstain", None),
            DesktopAcceptanceResult("case-004", "abstain", None),
        )
        first = score_desktop_acceptance_results(self.manifest, results, self.policy)
        self.assertEqual(first, score_desktop_acceptance_results(self.manifest, results, self.policy))
        self.assertEqual(first["per_case"][0]["provider_source_score_semantics"], "uncalibrated")
        self.assertIsNone(first["per_case"][0]["system_confidence"])


if __name__ == "__main__":
    unittest.main()
