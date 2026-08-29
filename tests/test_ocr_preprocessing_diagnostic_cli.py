"""Focused tests for the benchmark-only OCR preprocessing diagnostic."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from capture_import.evaluation_harness import BenchmarkCase, BenchmarkManifest
from capture_import.ocr_preprocessing_diagnostic_cli import OCRVariant, run_matrix


class OCRPreprocessingDiagnosticTests(unittest.TestCase):
    def test_matrix_scores_expected_tokens_without_feeding_them_to_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            front = root / "front.png"
            reverse = root / "reverse.png"
            front.write_bytes(b"not-an-image-needed-by-fake")
            reverse.write_bytes(b"not-an-image-needed-by-fake")
            case = BenchmarkCase(
                case_id="coin-1",
                obverse=front,
                reverse=reverse,
                expected={"country": "Canada", "denomination": "10 cents", "year": "1937"},
                identity_certain=True,
                difficulty=("clean",),
                provenance={},
                notes="",
            )
            manifest = BenchmarkManifest(version="v-test", root=root, cases=(case,))
            seen: list[tuple[Path, str]] = []

            def fake_ocr(path: Path, variant: OCRVariant) -> str:
                seen.append((path, variant.name))
                return "CANADA 10 CENTS" if path == front else "1937"

            report = run_matrix(
                manifest,
                variants=(OCRVariant("fixture", 11, "original"),),
                ocr=fake_ocr,
            )

            self.assertEqual(seen, [(front, "fixture"), (reverse, "fixture")])
            row = report["variants"][0]
            self.assertEqual(row["summary"]["required_tokens_recovered"], 3)
            self.assertEqual(row["summary"]["structured_suggestions"], 3)
            case_row = row["cases"][0]
            self.assertEqual(
                case_row["expected_token_presence_diagnostic_only"],
                {"country": True, "denomination": True, "year": True},
            )
            self.assertEqual(case_row["suggestions"]["countries"], ["Canada"])
            self.assertEqual(case_row["suggestions"]["denominations"], ["10 CENTS"])
            self.assertEqual(case_row["suggestions"]["years"], ["1937"])

    def test_matrix_preserves_variant_separation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            front = root / "front.png"
            reverse = root / "reverse.png"
            front.write_bytes(b"x")
            reverse.write_bytes(b"x")
            case = BenchmarkCase(
                case_id="coin-1",
                obverse=front,
                reverse=reverse,
                expected={"country": "Canada", "denomination": "10 cents", "year": "1937"},
                identity_certain=True,
                difficulty=("clean",),
                provenance={},
                notes="",
            )
            manifest = BenchmarkManifest(version="v-test", root=root, cases=(case,))

            def fake_ocr(_path: Path, variant: OCRVariant) -> str:
                return "1937" if variant.psm == 6 else "noise"

            report = run_matrix(
                manifest,
                variants=(
                    OCRVariant("psm6", 6, "original"),
                    OCRVariant("psm11", 11, "original"),
                ),
                ocr=fake_ocr,
            )

            self.assertEqual(report["variants"][0]["summary"]["required_tokens_recovered"], 1)
            self.assertEqual(report["variants"][1]["summary"]["required_tokens_recovered"], 0)
            self.assertIn("never provided to OCR", report["warning"])


if __name__ == "__main__":
    unittest.main()
