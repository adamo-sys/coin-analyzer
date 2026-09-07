import unittest
from pathlib import Path

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
)
from capture_import.desktop_acceptance_ai_evaluation_cases import (
    adapt_desktop_acceptance_manifest_cases,
)
from capture_import.desktop_acceptance_set import (
    DesktopAcceptanceCase,
    DesktopAcceptanceManifest,
)


def _manifest_case(
    case_id: str,
    expected_action: str,
) -> DesktopAcceptanceCase:
    return DesktopAcceptanceCase(
        case_id=case_id,
        specimen_id=f"specimen-{case_id[-3:]}",
        repeated_case_id=None,
        expected_action=expected_action,
        expected_identity={},
        reserved_attribution={},
        capture_conditions={},
        capture_difference_fields=None,
        capture_difference_rationale=None,
        cohorts=("synthetic",),
        stability=False,
        privacy_classification="synthetic",
        prior_benchmark_use={},
        ground_truth_review={},
        action_review={},
        images=(),
        notes="synthetic adapter test",
    )


def _manifest(
    cases: tuple[DesktopAcceptanceCase, ...],
) -> DesktopAcceptanceManifest:
    return DesktopAcceptanceManifest(
        root=Path("."),
        cases=cases,
        canonicalization_policy={},
        freeze={},
        stability_relevant_cohorts=(),
    )


class DesktopAcceptanceAIEvaluationCasesTests(unittest.TestCase):
    def test_identify_case_uses_explicit_authoritative_candidate_id(self) -> None:
        manifest = _manifest(
            (_manifest_case("case-001", "identify"),)
        )

        cases = adapt_desktop_acceptance_manifest_cases(
            manifest,
            candidate_ids_by_case={
                "case-001": "candidate:authoritative",
            },
        )

        self.assertEqual(len(cases), 1)
        self.assertEqual(
            cases[0].schema_version,
            CURRENT_AI_EVALUATION_SCHEMA_VERSION,
        )
        self.assertEqual(cases[0].case_id, "case-001")
        self.assertEqual(
            cases[0].allowed_candidate_ids,
            ("candidate:authoritative",),
        )
        self.assertFalse(cases[0].require_abstention)

    def test_abstain_case_requires_explicit_abstention(self) -> None:
        manifest = _manifest(
            (_manifest_case("case-001", "abstain"),)
        )

        cases = adapt_desktop_acceptance_manifest_cases(
            manifest,
            candidate_ids_by_case={},
        )

        self.assertEqual(cases[0].allowed_candidate_ids, ())
        self.assertTrue(cases[0].require_abstention)

    def test_adapter_preserves_case_order_and_identity(self) -> None:
        manifest = _manifest(
            (
                _manifest_case("case-001", "identify"),
                _manifest_case("case-002", "abstain"),
                _manifest_case("case-003", "identify"),
            )
        )

        cases = adapt_desktop_acceptance_manifest_cases(
            manifest,
            candidate_ids_by_case={
                "case-001": "candidate:first",
                "case-003": "candidate:third",
            },
        )

        self.assertEqual(
            tuple(case.case_id for case in cases),
            ("case-001", "case-002", "case-003"),
        )

    def test_adapter_does_not_manufacture_candidate_from_expected_identity(
        self,
    ) -> None:
        manifest_case = _manifest_case("case-001", "identify")
        object.__setattr__(
            manifest_case,
            "expected_identity",
            {
                "country": "Canada",
                "denomination": "1 dollar",
                "year": "1967",
            },
        )

        manifest = _manifest((manifest_case,))

        cases = adapt_desktop_acceptance_manifest_cases(
            manifest,
            candidate_ids_by_case={
                "case-001": "candidate:explicit",
            },
        )

        self.assertEqual(
            cases[0].allowed_candidate_ids,
            ("candidate:explicit",),
        )
        self.assertNotIn(
            "Canada",
            cases[0].allowed_candidate_ids[0],
        )
        self.assertNotIn(
            "1967",
            cases[0].allowed_candidate_ids[0],
        )

    def test_missing_identify_candidate_mapping_fails_closed(self) -> None:
        manifest = _manifest(
            (_manifest_case("case-001", "identify"),)
        )

        with self.assertRaisesRegex(ValueError, "missing"):
            adapt_desktop_acceptance_manifest_cases(
                manifest,
                candidate_ids_by_case={},
            )

    def test_extra_candidate_mapping_for_abstain_fails_closed(self) -> None:
        manifest = _manifest(
            (_manifest_case("case-001", "abstain"),)
        )

        with self.assertRaisesRegex(ValueError, "extra"):
            adapt_desktop_acceptance_manifest_cases(
                manifest,
                candidate_ids_by_case={
                    "case-001": "candidate:forbidden",
                },
            )

    def test_unknown_candidate_mapping_case_fails_closed(self) -> None:
        manifest = _manifest(
            (_manifest_case("case-001", "identify"),)
        )

        with self.assertRaisesRegex(ValueError, "extra"):
            adapt_desktop_acceptance_manifest_cases(
                manifest,
                candidate_ids_by_case={
                    "case-001": "candidate:accepted",
                    "case-999": "candidate:unknown",
                },
            )

    def test_unsorted_manifest_cases_fail_closed(self) -> None:
        manifest = _manifest(
            (
                _manifest_case("case-002", "abstain"),
                _manifest_case("case-001", "identify"),
            )
        )

        with self.assertRaisesRegex(ValueError, "sorted"):
            adapt_desktop_acceptance_manifest_cases(
                manifest,
                candidate_ids_by_case={
                    "case-001": "candidate:accepted",
                },
            )

    def test_duplicate_manifest_case_ids_fail_closed(self) -> None:
        manifest = _manifest(
            (
                _manifest_case("case-001", "identify"),
                _manifest_case("case-001", "identify"),
            )
        )

        with self.assertRaisesRegex(ValueError, "unique"):
            adapt_desktop_acceptance_manifest_cases(
                manifest,
                candidate_ids_by_case={
                    "case-001": "candidate:accepted",
                },
            )

    def test_unsupported_expected_action_fails_closed(self) -> None:
        manifest = _manifest(
            (_manifest_case("case-001", "unknown"),)
        )

        with self.assertRaisesRegex(ValueError, "unsupported"):
            adapt_desktop_acceptance_manifest_cases(
                manifest,
                candidate_ids_by_case={},
            )

    def test_invalid_candidate_id_is_rejected_by_evaluation_contract(
        self,
    ) -> None:
        manifest = _manifest(
            (_manifest_case("case-001", "identify"),)
        )

        with self.assertRaises(ValueError):
            adapt_desktop_acceptance_manifest_cases(
                manifest,
                candidate_ids_by_case={
                    "case-001": "",
                },
            )

    def test_adapter_is_deterministic(self) -> None:
        manifest = _manifest(
            (
                _manifest_case("case-001", "identify"),
                _manifest_case("case-002", "abstain"),
            )
        )
        mapping = {
            "case-001": "candidate:accepted",
        }

        first = adapt_desktop_acceptance_manifest_cases(
            manifest,
            candidate_ids_by_case=mapping,
        )
        second = adapt_desktop_acceptance_manifest_cases(
            manifest,
            candidate_ids_by_case=mapping,
        )

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
