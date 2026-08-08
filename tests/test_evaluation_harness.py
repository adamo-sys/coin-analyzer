from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from capture_import.evaluation_harness import (
    BenchmarkManifestError,
    aggregate_latencies,
    load_manifest,
    render_summary,
    run_benchmark,
    score_results,
)


def _case(case_id: str = "case-1") -> dict[str, object]:
    return {
        "id": case_id,
        "obverse": "front.jpg",
        "reverse": "reverse.png",
        "expected": {
            "country": "Canada",
            "denomination": "25 cents",
            "year": "1967",
        },
        "identity_certain": True,
        "difficulty": ["clean"],
        "provenance": {
            "source_url": "https://example.invalid/source",
            "license": "CC0",
            "author": "Example",
        },
        "notes": "fixture",
    }


class EvaluationHarnessTests(unittest.TestCase):
    def _manifest(self, root: Path, case: dict[str, object] | None = None) -> Path:
        Image.new("RGB", (32, 32), "red").save(root / "front.jpg", "JPEG")
        Image.new("RGB", (32, 32), "blue").save(root / "reverse.png", "PNG")
        path = root / "manifest.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "coin-analyzer-ocr-benchmark",
                    "version": "test-v1",
                    "cases": [case or _case()],
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_manifest_accepts_relative_images_and_required_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = load_manifest(self._manifest(Path(temporary)))
        self.assertEqual(manifest.version, "test-v1")
        self.assertEqual(manifest.cases[0].case_id, "case-1")
        self.assertEqual(manifest.cases[0].difficulty, ("clean",))

    def test_manifest_rejects_absolute_image_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case = _case()
            case["obverse"] = str((root / "front.jpg").resolve())
            with self.assertRaisesRegex(BenchmarkManifestError, "relative|POSIX"):
                load_manifest(self._manifest(root, case))

    def test_scoring_keeps_unresolved_and_correction_separate(self) -> None:
        rows = [
            {
                "ocr_evaluated": True,
                "identity_certain": True,
                "field_scores": {"country": True, "denomination": True, "year": True},
                "unresolved": False,
                "correction_required": False,
                "infrastructure_failure": None,
                "latency_seconds": 1.0,
                "persistence_exercised": False,
            },
            {
                "ocr_evaluated": True,
                "identity_certain": True,
                "field_scores": {"country": True, "denomination": False, "year": False},
                "unresolved": True,
                "correction_required": True,
                "infrastructure_failure": None,
                "latency_seconds": 3.0,
                "persistence_exercised": False,
            },
        ]
        score = score_results(rows)
        self.assertEqual(score["country_accuracy"], 1.0)
        self.assertEqual(score["denomination_accuracy"], 0.5)
        self.assertEqual(score["full_identity_accuracy"], 0.5)
        self.assertEqual(score["unresolved_rate"], 0.5)
        self.assertEqual(score["correction_required_rate"], 0.5)

    def test_infrastructure_failure_is_not_scored_as_ocr_failure(self) -> None:
        score = score_results(
            [
                {
                    "ocr_evaluated": False,
                    "identity_certain": True,
                    "infrastructure_failure": {"type": "OSError"},
                    "persistence_exercised": False,
                }
            ]
        )
        self.assertEqual(score["evaluated_cases"], 0)
        self.assertEqual(score["infrastructure_failures"], 1)
        self.assertIsNone(score["country_accuracy"])
        self.assertEqual(score["failure_rate"], 1.0)

    def test_latency_uses_nearest_rank_p95(self) -> None:
        latency = aggregate_latencies([1, 2, 3, 4, 100])
        self.assertEqual(latency["mean_seconds"], 22.0)
        self.assertEqual(latency["median_seconds"], 3.0)
        self.assertEqual(latency["p95_seconds"], 100.0)

    def test_malformed_image_becomes_case_infrastructure_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = self._manifest(root)
            (root / "front.jpg").write_bytes(b"not-an-image")
            manifest = load_manifest(manifest_path)
            report = run_benchmark(manifest)
        self.assertEqual(report["summary"]["infrastructure_failures"], 1)
        self.assertFalse(report["cases"][0]["ocr_evaluated"])

    def test_missing_ocr_executable_is_infrastructure_not_accuracy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = load_manifest(self._manifest(Path(temporary)))
            evaluated = {
                "case_id": "case-1",
                "ocr_evaluated": True,
                "identity_certain": True,
                "field_scores": {"country": False, "denomination": False, "year": False},
                "unresolved": True,
                "correction_required": True,
                "infrastructure_failure": None,
                "latency_seconds": 1.0,
                "persistence_exercised": False,
                "difficulty": ["clean"],
            }
            with (
                patch(
                    "capture_import.evaluation_harness._runtime_configuration",
                    return_value={
                        "tesseract_available": False,
                        "tesseract_version": "unavailable: TesseractNotFoundError",
                    },
                ),
                patch(
                    "capture_import.evaluation_harness._run_case",
                    return_value=evaluated,
                ),
            ):
                report = run_benchmark(manifest)
        self.assertEqual(report["summary"]["evaluated_cases"], 0)
        self.assertEqual(report["summary"]["infrastructure_failures"], 1)
        self.assertIsNone(report["summary"]["country_accuracy"])

    def test_summary_rendering_is_deterministic(self) -> None:
        report = {
            "dataset_version": "v1",
            "summary": {
                "total_cases": 1,
                "evaluated_cases": 1,
                "infrastructure_failures": 0,
                "country_accuracy": 1.0,
                "denomination_accuracy": 0.0,
                "year_accuracy": 0.5,
                "full_identity_accuracy": 0.0,
                "unresolved_rate": 1.0,
                "correction_required_rate": 1.0,
                "failure_rate": 0.0,
                "persistence_success_rate": None,
                "latency": {
                    "mean_seconds": 1.0,
                    "median_seconds": 1.0,
                    "p95_seconds": 1.0,
                },
            },
        }
        self.assertEqual(render_summary(report), render_summary(report))
        self.assertIn("Full identity accuracy: 0.0%", render_summary(report))


if __name__ == "__main__":
    unittest.main()
