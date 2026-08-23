from __future__ import annotations

import json
import hashlib
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from capture_import.visual_evaluation_harness import (
    VisualBenchmarkManifestError,
    audit_visual_manifest,
    load_visual_manifest,
    score_visual_results,
)


def _image(role: str, path: str) -> dict[str, object]:
    return {
        "role": role,
        "path": path,
        "source_asset_path": "source.jpg",
        "source_page": "https://commons.wikimedia.org/wiki/File:Example.jpg",
        "source_file_url": "https://upload.wikimedia.org/example.jpg",
        "author": "Example Author",
        "license": "CC0-1.0",
        "retrieved_at": "2026-08-08",
        "source_sha256": "a" * 64,
        "transformation": "960px thumbnail; no other transformation",
    }


def _case(case_id: str = "case-1") -> dict[str, object]:
    return {
        "id": case_id,
        "underlying_identity": "canada-25-cents-1967-centennial",
        "obverse": _image("obverse", "obverse.jpg"),
        "reverse": _image("reverse", "reverse.jpg"),
        "expected": {
            "country": "Canada",
            "denomination": "25 cents",
            "year": "1967",
            "type_design": "Centennial bobcat",
        },
        "identity_certain": True,
        "era": "modern",
        "difficulty": ["clean", "studio"],
        "previously_used": False,
        "notes": "fixture",
    }


class VisualEvaluationHarnessTests(unittest.TestCase):
    def _manifest(self, root: Path, case: dict[str, object] | None = None) -> Path:
        Image.new("RGB", (20, 20), "red").save(root / "obverse.jpg")
        Image.new("RGB", (20, 20), "blue").save(root / "reverse.jpg")
        Image.new("RGB", (20, 20), "green").save(root / "source.jpg")
        prepared_case = case or _case()
        source_digest = hashlib.sha256((root / "source.jpg").read_bytes()).hexdigest()
        prepared_case["obverse"]["source_sha256"] = source_digest
        prepared_case["reverse"]["source_sha256"] = source_digest
        path = root / "manifest.json"
        path.write_text(json.dumps({"schema": "coin-analyzer-visual-benchmark", "version": "test-v2", "cases": [prepared_case]}), encoding="utf-8")
        return path

    def test_manifest_accepts_paired_images_and_complete_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = load_visual_manifest(self._manifest(Path(temporary)))
        self.assertEqual(manifest.version, "test-v2")
        self.assertEqual(manifest.cases[0].obverse.role, "obverse")
        self.assertEqual(manifest.cases[0].reverse.role, "reverse")

    def test_manifest_rejects_non_allowlisted_license(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = _case()
            case["obverse"]["license"] = "All rights reserved"
            with self.assertRaisesRegex(VisualBenchmarkManifestError, "allowlisted"):
                load_visual_manifest(self._manifest(Path(temporary), case))

    def test_manifest_rejects_incomplete_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = _case()
            del case["reverse"]["author"]
            with self.assertRaisesRegex(VisualBenchmarkManifestError, "author"):
                load_visual_manifest(self._manifest(Path(temporary), case))

    def test_manifest_rejects_source_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self._manifest(Path(temporary))
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["cases"][0]["obverse"]["source_sha256"] = "0" * 64
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(VisualBenchmarkManifestError, "does not match"):
                load_visual_manifest(path)

    def test_manifest_rejects_role_mismatch_and_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case = _case()
            case["obverse"]["role"] = "reverse"
            with self.assertRaisesRegex(VisualBenchmarkManifestError, "obverse"):
                load_visual_manifest(self._manifest(root, case))
            case = _case()
            case["obverse"]["path"] = str((root / "obverse.jpg").resolve())
            with self.assertRaisesRegex(VisualBenchmarkManifestError, "relative|POSIX"):
                load_visual_manifest(self._manifest(root, case))

    def test_scoring_separates_prediction_abstention_and_infrastructure(self) -> None:
        rows = [
            {"outcome": "PREDICTED", "identity_certain": True, "expected": _case()["expected"], "predictions": [_case()["expected"]], "latency_seconds": 1.0, "estimated_cost_usd": 0.02},
            {"outcome": "ABSTAINED", "identity_certain": True, "expected": _case()["expected"], "latency_seconds": 2.0, "estimated_cost_usd": 0.01},
            {"outcome": "INFRASTRUCTURE_FAILURE", "identity_certain": True, "latency_seconds": 0.1},
        ]
        score = score_visual_results(rows)
        self.assertEqual(score["country_accuracy"], 0.5)
        self.assertEqual(score["top_k_identity_recall"], 0.5)
        self.assertEqual(score["abstention_rate"], 1 / 3)
        self.assertEqual(score["infrastructure_failure_rate"], 1 / 3)
        self.assertAlmostEqual(score["estimated_cost_usd"]["total"], 0.03)

    def test_top_k_preserves_composite_identity(self) -> None:
        expected = _case()["expected"]
        wrong = dict(expected, denomination="5 cents")
        score = score_visual_results([{"outcome": "PREDICTED", "identity_certain": True, "expected": expected, "predictions": [wrong, expected]}], top_k=2)
        self.assertEqual(score["full_required_identity_accuracy"], 0.0)
        self.assertEqual(score["top_k_identity_recall"], 1.0)

    def test_safety_metrics_separate_coverage_accuracy_and_high_score_errors(self) -> None:
        expected = _case()["expected"]
        rows = [
            {
                "case_id": "correct-full",
                "outcome": "PREDICTED",
                "identity_certain": True,
                "expected": expected,
                "predictions": [dict(expected)],
                "ranked_candidates": [{**expected, "source_score": 0.95}],
            },
            {
                "case_id": "partial-high-score",
                "outcome": "PREDICTED",
                "identity_certain": True,
                "expected": expected,
                "predictions": [{"country": "Canada"}],
                "ranked_candidates": [{"country": "Canada", "source_score": 0.99}],
            },
            {
                "case_id": "abstained",
                "outcome": "ABSTAINED",
                "identity_certain": True,
                "expected": expected,
                "predictions": [],
                "ranked_candidates": [],
            },
        ]

        metrics = score_visual_results(rows)

        self.assertEqual(metrics["field_coverage"]["country"], 2 / 3)
        self.assertEqual(metrics["field_coverage"]["full_required_identity"], 1 / 3)
        self.assertEqual(metrics["selective_accuracy"]["country"], 1.0)
        self.assertEqual(metrics["selective_accuracy"]["full_required_identity"], 1.0)
        safety = metrics["source_score_safety"]
        self.assertEqual(safety["high_score_predictions"], 2)
        self.assertEqual(safety["high_score_incomplete"], 1)
        self.assertEqual(safety["high_score_incomplete_case_ids"], ["partial-high-score"])
        self.assertEqual(safety["high_score_incorrect"], 0)
        self.assertEqual(safety["high_score_unsafe"], 1)
        self.assertEqual(safety["semantics"], "uncalibrated_provider_source_score")

    def test_safety_case_ids_are_deterministic_and_invalid_scores_are_reported(self) -> None:
        expected = _case()["expected"]
        rows = [
            {
                "case_id": case_id,
                "outcome": "PREDICTED",
                "identity_certain": True,
                "expected": expected,
                "predictions": [{"country": "Canada"}],
                "ranked_candidates": [
                    {"country": "Canada", "source_score": source_score}
                ],
            }
            for case_id, source_score in (
                ("z-case", 1.0),
                ("a-case", 0.9),
                ("ignored-nan", float("nan")),
                ("ignored-range", 1.01),
            )
        ]

        safety = score_visual_results(rows)["source_score_safety"]

        self.assertEqual(safety["scored_predictions"], 2)
        self.assertEqual(safety["missing_source_scores"], 0)
        self.assertEqual(safety["invalid_source_scores"], 2)
        self.assertEqual(
            safety["invalid_source_score_case_ids"],
            ["ignored-nan", "ignored-range"],
        )
        self.assertEqual(safety["high_score_predictions"], 2)
        self.assertEqual(
            safety["high_score_incomplete_case_ids"], ["a-case", "z-case"]
        )

    def test_source_score_bins_have_deterministic_boundaries(self) -> None:
        expected = _case()["expected"]
        rows = [
            {
                "case_id": f"boundary-{index}",
                "outcome": "PREDICTED",
                "identity_certain": True,
                "expected": expected,
                "predictions": [expected],
                "ranked_candidates": [{**expected, "source_score": score}],
            }
            for index, score in enumerate((0.0, 0.699, 0.7, 0.899, 0.9, 1.0))
        ]

        bins = score_visual_results(rows)["source_score_safety"][
            "calibration_diagnostic_only"
        ]["bins"]

        self.assertEqual([item["count"] for item in bins], [2, 2, 2])

    def test_missing_source_score_is_distinct_from_invalid_score(self) -> None:
        expected = _case()["expected"]
        safety = score_visual_results(
            [
                {
                    "case_id": "missing-score",
                    "outcome": "PREDICTED",
                    "identity_certain": True,
                    "expected": expected,
                    "predictions": [expected],
                    "ranked_candidates": [expected],
                }
            ]
        )["source_score_safety"]

        self.assertEqual(safety["missing_source_scores"], 1)
        self.assertEqual(safety["invalid_source_scores"], 0)

    def test_scored_prediction_requires_auditable_case_id(self) -> None:
        expected = _case()["expected"]
        with self.assertRaisesRegex(ValueError, "non-empty case_id"):
            score_visual_results(
                [
                    {
                        "outcome": "PREDICTED",
                        "identity_certain": True,
                        "expected": expected,
                        "predictions": [expected],
                        "ranked_candidates": [
                            {**expected, "source_score": 0.9}
                        ],
                    }
                ]
            )

    def test_safety_metrics_have_explicit_empty_population_values(self) -> None:
        metrics = score_visual_results(
            [
                {
                    "case_id": "abstained",
                    "outcome": "ABSTAINED",
                    "identity_certain": True,
                    "expected": _case()["expected"],
                    "predictions": [],
                    "ranked_candidates": [],
                }
            ]
        )

        safety = metrics["source_score_safety"]
        self.assertEqual(safety["scored_predictions"], 0)
        self.assertEqual(safety["missing_source_scores"], 0)
        self.assertEqual(safety["invalid_source_scores"], 0)
        self.assertIsNone(safety["high_score_unsafe_rate"])
        self.assertIsNone(
            safety["calibration_diagnostic_only"]["weighted_absolute_gap"]
        )
        self.assertIsNone(metrics["selective_accuracy"]["country"])

    def test_audit_reports_image_duplicates_and_concentration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = load_visual_manifest(self._manifest(Path(temporary)))
            audit = audit_visual_manifest(manifest)
        self.assertEqual(audit["cases"], 1)
        self.assertEqual(audit["unique_identities"], 1)
        self.assertEqual(audit["largest_country_share"], 1.0)
        self.assertFalse(audit["duplicate_image_hashes"])
        self.assertEqual(len(audit["near_duplicate_candidates"]), 1)
        self.assertFalse(audit["repeated_source_pages_across_cases"])

    def test_benchmark_v2_candidate_is_complete_and_auditable(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = load_visual_manifest(root / "benchmarks" / "v2" / "manifest.json")
        audit = audit_visual_manifest(manifest)
        self.assertEqual(audit["cases"], 20)
        self.assertEqual(audit["unique_identities"], 20)
        self.assertFalse(audit["duplicate_image_hashes"])
        self.assertFalse(audit["repeated_source_pages_across_cases"])


if __name__ == "__main__":
    unittest.main()
