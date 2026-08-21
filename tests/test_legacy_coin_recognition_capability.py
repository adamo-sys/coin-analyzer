import ast
from pathlib import Path
import unittest

from legacy_coin_recognition_capability import (
    LegacyCoinRecognitionCapability,
    to_legacy_detector_result,
)


class FakeRecognizer:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def detect_coin(self, image_reference):
        self.calls.append(image_reference)
        return self.output


class LegacyCoinRecognitionCapabilityTests(unittest.TestCase):
    def execute(self, output):
        recognizer = FakeRecognizer(output)
        result = LegacyCoinRecognitionCapability(lambda: recognizer).execute("fixture.jpg")
        self.assertEqual(["fixture.jpg"], recognizer.calls)
        return result

    def test_detector_output_maps_without_fabricated_confidence_or_raw_ocr(self):
        result = self.execute(
            {
                "success": True,
                "country": "Canada",
                "denomination": "25 cents",
                "year": "1907",
                "denomination_confidence": 72,
                "year_confidence": 61,
                "country_confidence": 150,
                "orientation": "reverse",
                "year_candidates": [{"year": "1907"}],
                "ocr_full_text": "private raw OCR",
            }
        )

        self.assertTrue(result.success)
        self.assertIsNone(result.confidence)
        self.assertEqual(72, result.source_metadata["denomination_confidence"])
        self.assertEqual(150, result.source_metadata["country_confidence"])
        self.assertNotIn("ocr_full_text", result.source_metadata)
        self.assertNotIn("private raw OCR", " ".join(result.evidence))

    def test_success_compatibility_dictionary_is_exact(self):
        result = self.execute(
            {
                "success": True,
                "country": "Canada",
                "denomination": "dime",
                "year": None,
                "denomination_confidence": 0.4,
                "year_confidence": 0.0,
            }
        )

        self.assertEqual(
            {
                "success": True,
                "country": "Canada",
                "denomination": "dime",
                "year": None,
                "confidence": 0.4,
                "year_confidence": 0.0,
                "method": "coin_recognition",
            },
            to_legacy_detector_result(result),
        )

    def test_failure_uses_historical_get_default_semantics(self):
        for output, expected in (
            ({"success": False}, "Detection failed"),
            ({"success": False, "error": None}, None),
            ({"success": False, "error": "No coin"}, "No coin"),
        ):
            with self.subTest(output=output):
                result = self.execute(output)
                legacy = to_legacy_detector_result(result)
                self.assertEqual(expected, legacy["error"])
                self.assertEqual(
                    {
                        "success",
                        "error",
                        "country",
                        "denomination",
                        "year",
                        "confidence",
                        "method",
                    },
                    set(legacy),
                )

    def test_missing_scores_remain_absent_in_generic_metadata_but_zero_in_legacy(self):
        result = self.execute(
            {"success": True, "country": "Canada", "denomination": "5 cents", "year": None}
        )

        self.assertNotIn("denomination_confidence", result.source_metadata)
        self.assertNotIn("year_confidence", result.source_metadata)
        self.assertEqual(0.0, to_legacy_detector_result(result)["confidence"])
        self.assertEqual(0.0, to_legacy_detector_result(result)["year_confidence"])
        self.assertTrue(result.warnings)

    def test_exception_and_invalid_output_are_bounded(self):
        class Failing:
            def detect_coin(self, _image):
                raise RuntimeError("optional OCR unavailable")

        failed = LegacyCoinRecognitionCapability(lambda: Failing()).execute("fixture.jpg")
        invalid = self.execute(None)

        self.assertEqual("RuntimeError", failed.failure_category)
        self.assertEqual("optional OCR unavailable", to_legacy_detector_result(failed)["error"])
        self.assertEqual("TypeError", invalid.failure_category)
        self.assertEqual(
            "'NoneType' object is not subscriptable",
            to_legacy_detector_result(invalid)["error"],
        )

    def test_adapter_import_boundary_keeps_detector_import_lazy(self):
        tree = ast.parse(Path("legacy_coin_recognition_capability.py").read_text(encoding="utf-8"))
        top_level = set()
        all_imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                all_imports.update(alias.name for alias in node.names)
                if node in tree.body:
                    top_level.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                all_imports.add(node.module or "")
                if node in tree.body:
                    top_level.add(node.module or "")
        self.assertNotIn("coin_recognition", top_level)
        self.assertLessEqual(
            all_imports,
            {"__future__", "typing", "legacy_recognition_orchestration", "coin_recognition"},
        )


if __name__ == "__main__":
    unittest.main()
