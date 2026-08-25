"""Focused tests for the read-only OCR benchmark diagnostic CLI."""

from __future__ import annotations

import unittest

from capture_import.ocr_benchmark_diagnostic_cli import diagnose_report


class OCRBenchmarkDiagnosticCLITests(unittest.TestCase):
    def test_classifies_signal_present_candidate_missing_without_feeding_expected(self) -> None:
        report = {
            "schema": "coin-analyzer-ocr-evaluation-report",
            "dataset_version": "v1",
            "cases": [
                {
                    "case_id": "case-1",
                    "ocr_evaluated": True,
                    "identity_certain": True,
                    "difficulty": ["clean"],
                    "expected": {
                        "country": "United States",
                        "denomination": "1 cent",
                        "year": "2013",
                    },
                    "raw_observations": [
                        {
                            "image_role": "front",
                            "confidence_score": 7.0,
                            "raw_text": "LIBERTY 2013",
                        }
                    ],
                    "raw_candidates": [],
                    "raw_conflicts": [],
                    "unresolved_fields": ["country", "denomination", "year"],
                }
            ],
        }

        result = diagnose_report(report)
        row = result["cases"][0]
        self.assertEqual(row["bottleneck"], "signal_present_candidate_missing")
        self.assertEqual(
            row["expected_token_presence_diagnostic_only"],
            {"country": False, "denomination": False, "year": True},
        )
        self.assertEqual(row["candidate_count"], 0)
        self.assertIn("must never feed recognition", result["warning"])

    def test_classifies_ocr_signal_missing_when_text_exists_but_expected_tokens_do_not(self) -> None:
        report = {
            "schema": "coin-analyzer-ocr-evaluation-report",
            "cases": [
                {
                    "case_id": "case-2",
                    "ocr_evaluated": True,
                    "identity_certain": True,
                    "expected": {
                        "country": "Canada",
                        "denomination": "50 cents",
                        "year": "1908",
                    },
                    "raw_observations": [{"raw_text": "garbled symbols only"}],
                    "raw_candidates": [],
                    "raw_conflicts": [],
                    "unresolved_fields": ["country", "denomination", "year"],
                }
            ],
        }

        row = diagnose_report(report)["cases"][0]
        self.assertEqual(row["bottleneck"], "ocr_signal_missing")

    def test_counts_candidates_by_required_field(self) -> None:
        report = {
            "schema": "coin-analyzer-ocr-evaluation-report",
            "cases": [
                {
                    "case_id": "case-3",
                    "ocr_evaluated": True,
                    "identity_certain": True,
                    "expected": {
                        "country": "United States",
                        "denomination": "1 cent",
                        "year": "2013",
                    },
                    "raw_observations": [{"raw_text": "LIBERTY 2013"}],
                    "raw_candidates": [
                        {"field_name": "year", "normalized_value": "2013"},
                        {"field_name": "year", "normalized_value": "2018"},
                    ],
                    "raw_conflicts": [],
                    "unresolved_fields": ["country", "denomination", "year"],
                }
            ],
        }

        row = diagnose_report(report)["cases"][0]
        self.assertEqual(
            row["candidate_counts_by_field"],
            {"country": 0, "denomination": 0, "year": 2},
        )
        self.assertEqual(row["bottleneck"], "partial_signal_or_candidate_gap")

    def test_conflict_takes_priority(self) -> None:
        report = {
            "schema": "coin-analyzer-ocr-evaluation-report",
            "cases": [
                {
                    "case_id": "case-4",
                    "ocr_evaluated": True,
                    "expected": {"country": "India", "denomination": "1 rupee", "year": "1918"},
                    "raw_observations": [{"raw_text": "INDIA ONE RUPEE 1918"}],
                    "raw_candidates": [{"field_name": "year", "normalized_value": "1918"}],
                    "raw_conflicts": [{"field_name": "year"}],
                }
            ],
        }

        row = diagnose_report(report)["cases"][0]
        self.assertEqual(row["bottleneck"], "candidate_conflict")

    def test_skips_unevaluated_rows_and_rejects_wrong_schema(self) -> None:
        report = {
            "schema": "coin-analyzer-ocr-evaluation-report",
            "cases": [{"case_id": "not-run", "ocr_evaluated": False}],
        }
        self.assertEqual(diagnose_report(report)["case_count"], 0)
        with self.assertRaises(ValueError):
            diagnose_report({"schema": "wrong", "cases": []})


if __name__ == "__main__":
    unittest.main()
