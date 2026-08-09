import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from capture_import.evidence_fusion import fuse_identity_evidence
from capture_import.fusion_evaluation_runner import (
    FusionEvaluationError,
    analyze_safety,
    fusion_retention_results,
    load_archived_visual_report,
    score_evidence_rows,
)
from capture_import.visual_evaluation_harness import load_visual_manifest


class FusionEvaluationRunnerTests(unittest.TestCase):
    def test_frozen_archived_report_hash_and_configuration_are_accepted(self):
        manifest = load_visual_manifest("benchmarks/v2/manifest.json")
        report = load_archived_visual_report(
            "artifacts/benchmark-v2-terra-prospective-report.json",
            manifest,
        )
        self.assertTrue(report["experiment_passes"])

    def test_any_archived_report_byte_change_is_rejected(self):
        manifest = load_visual_manifest("benchmarks/v2/manifest.json")
        source = Path("artifacts/benchmark-v2-terra-prospective-report.json").read_bytes()
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            path.write_bytes(source + b" ")
            with self.assertRaisesRegex(FusionEvaluationError, "SHA-256"):
                load_archived_visual_report(path, manifest)

    def test_configuration_drift_is_rejected_after_hash_validation(self):
        source = self._source()
        source["provider"]["configuration"]["image_detail"] = "auto"
        self._assert_modified_rejected(source, "configuration fingerprint")

    def test_pass_metric_drift_is_rejected_after_hash_validation(self):
        source = self._source()
        source["canonical_metrics"]["country_accuracy"] = 0.80
        self._assert_modified_rejected(source, "PASS metrics")

    def test_archived_report_is_bound_to_frozen_case_inventory(self):
        source = self._source()
        source["cases"] = source["cases"][:-1]
        self._assert_modified_rejected(source, "inventory/order")

    @staticmethod
    def _source():
        return json.loads(
            Path("artifacts/benchmark-v2-terra-prospective-report.json").read_text(
                encoding="utf-8"
            )
        )

    def _assert_modified_rejected(self, source, message):
        manifest = load_visual_manifest("benchmarks/v2/manifest.json")
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            path.write_text(
                json.dumps(source, sort_keys=True), encoding="utf-8"
            )
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(FusionEvaluationError, message):
                load_archived_visual_report(
                    path,
                    manifest,
                    expected_sha256=expected,
                )

    def test_explicit_conflict_cannot_score_as_resolved(self):
        row = self._row(
            visual={"country": "Canada", "denomination": "5 cents", "year": "1964"},
            ocr=[self._ocr("year", "1965")],
            expected={"country": "Canada", "denomination": "5 cents", "year": "1964"},
        )
        metrics = score_evidence_rows([row], view="fused")
        self.assertEqual(metrics["year_accuracy"], 0.0)
        self.assertEqual(metrics["conflict_rate"], 1.0)
        self.assertIsNone(row["fused"]["fields"][2]["selected_comparable_value"])

    def test_safety_analysis_counts_challenge_without_silent_repair(self):
        row = self._row(
            visual={"country": "Canada", "denomination": "10 cents", "year": "1964"},
            ocr=[self._ocr("denomination", "5 cents")],
            expected={"country": "Canada", "denomination": "5 cents", "year": "1964"},
        )
        safety = analyze_safety([row])
        self.assertEqual(safety["visual_errors_safely_challenged_by_ocr_fields"], 1)
        self.assertEqual(safety["new_silent_incorrect_resolutions"], 0)

    def test_retention_requires_accuracy_safety_reliability_and_latency(self):
        metrics = {"country_accuracy": .75, "denomination_accuracy": .85, "year_accuracy": .65, "full_required_identity_accuracy": .5}
        safety = {"new_silent_incorrect_resolutions": 0, "unmarked_visual_ocr_disagreements": 0}
        result = fusion_retention_results(metrics, safety, {"mean_seconds": .001}, infrastructure_failures=0)
        self.assertTrue(all(result.values()))

    def test_wrong_ocr_only_value_is_a_new_silent_incorrect_resolution(self):
        row = self._row(
            visual={"country": "Canada", "denomination": "5 cents", "year": None},
            ocr=[self._ocr("year", "1965")],
            expected={"country": "Canada", "denomination": "5 cents", "year": "1964"},
        )
        self.assertEqual(
            analyze_safety([row])["new_silent_incorrect_resolutions"],
            1,
        )

    @staticmethod
    def _ocr(field, value):
        return {"field_name": field, "normalized_value": value, "provider_id": "legacy-ocr", "image_role": "front", "artifact_key": "crop-coin-front", "confidence_score": .8}

    def _row(self, *, visual, ocr, expected):
        candidate = {**visual, "rank": 1, "provider_id": "openai", "model_id": "gpt-5.6-terra", "confidence": .8}
        fused = fuse_identity_evidence(visual_candidates=[candidate], ocr_candidates=ocr)
        ocr_only = fuse_identity_evidence(visual_candidates=[], ocr_candidates=ocr)
        expected_keys = self._keys(expected)
        visual_keys = self._keys(visual)
        def scores(identity):
            fields = {item.field_name: item for item in identity.fields}
            values = {field: fields[field].selected_comparable_value == expected_keys[field] for field in expected_keys}
            values["full_required_identity"] = all(values.values())
            return values
        visual_scores = {field: visual_keys[field] == expected_keys[field] for field in expected_keys}
        visual_scores["full_required_identity"] = all(visual_scores.values())
        return {"case_id": "synthetic", "expected": expected, "visual": {"top_1": candidate}, "ocr": {"identity": ocr_only.to_dict()}, "fused": fused.to_dict(), "field_scores": {"visual": visual_scores, "ocr": scores(ocr_only), "fused": scores(fused)}, "infrastructure_failure": None}

    @staticmethod
    def _keys(identity):
        from capture_import.evidence_fusion import comparable_identity_value
        return {field: comparable_identity_value(field, identity.get(field), country_raw=identity.get("country"))[0] for field in ("country", "denomination", "year")}


if __name__ == "__main__":
    unittest.main()
