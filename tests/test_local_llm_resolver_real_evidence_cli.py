"""Focused tests for bridging real OCR evaluation evidence into the local resolver."""

from __future__ import annotations

import unittest

from capture_import.local_llm_resolver_real_evidence_cli import cases_from_evaluation_report


class LocalResolverRealEvidenceBridgeTests(unittest.TestCase):
    def test_projects_raw_ocr_evidence_without_ground_truth_leakage(self) -> None:
        report = {
            "schema": "coin-analyzer-ocr-evaluation-report",
            "dataset_version": "v1",
            "cases": [
                {
                    "case_id": "real-case",
                    "identity_certain": True,
                    "expected": {
                        "country": "Canada",
                        "denomination": "50 cents",
                        "year": "1908",
                    },
                    "ocr_evaluated": True,
                    "raw_observations": [
                        {"raw_text": "EDWARDVS VII DEI GRATIA REX"},
                        {"raw_text": "NEWFOUNDLAND 50 CENTS 1908"},
                    ],
                    "raw_candidates": [
                        {"field_name": "country", "normalized_value": "Canada"},
                        {"field_name": "denomination", "normalized_value": "50 cents"},
                        {"field_name": "year", "normalized_value": "1908"},
                    ],
                }
            ],
        }

        cases = cases_from_evaluation_report(report)

        self.assertEqual(len(cases), 1)
        case = cases[0]
        self.assertEqual(case.case_id, "real-case")
        self.assertEqual(case.evidence.ocr_text, (
            "EDWARDVS VII DEI GRATIA REX",
            "NEWFOUNDLAND 50 CENTS 1908",
        ))
        self.assertEqual(case.evidence.candidate_countries, ("Canada",))
        self.assertEqual(case.evidence.candidate_denominations, ("50 cents",))
        self.assertEqual(case.evidence.candidate_years, ("1908",))
        self.assertNotIn("1908", case.evidence.ocr_text[0])
        self.assertEqual(case.expected["year"], "1908")

    def test_preserves_conflicting_candidates_for_resolver(self) -> None:
        report = {
            "schema": "coin-analyzer-ocr-evaluation-report",
            "cases": [
                {
                    "case_id": "conflict",
                    "identity_certain": True,
                    "expected": {"country": "India", "denomination": "1 rupee", "year": "1918"},
                    "ocr_evaluated": True,
                    "raw_observations": [{"raw_text": "ONE RUPEE INDIA 1918"}],
                    "raw_candidates": [
                        {"field_name": "country", "normalized_value": "India"},
                        {"field_name": "year", "normalized_value": "1918"},
                        {"field_name": "year", "normalized_value": "1913"},
                        {"field_name": "denomination", "normalized_value": "1 rupee"},
                    ],
                }
            ],
        }

        case = cases_from_evaluation_report(report)[0]
        self.assertEqual(case.evidence.candidate_years, ("1918", "1913"))

    def test_skips_infrastructure_failed_unevaluated_rows(self) -> None:
        report = {
            "schema": "coin-analyzer-ocr-evaluation-report",
            "cases": [
                {
                    "case_id": "not-run",
                    "identity_certain": True,
                    "expected": {"country": "Canada", "denomination": "1 cent", "year": "2000"},
                    "ocr_evaluated": False,
                }
            ],
        }
        self.assertEqual(cases_from_evaluation_report(report), ())

    def test_rejects_wrong_report_schema(self) -> None:
        with self.assertRaises(ValueError):
            cases_from_evaluation_report({"schema": "wrong", "cases": []})


if __name__ == "__main__":
    unittest.main()
