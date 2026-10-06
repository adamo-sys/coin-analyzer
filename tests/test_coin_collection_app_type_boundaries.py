"""Detector consumer and export contracts using synthetic temporary records."""

import csv
import json
import os
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from coin_collection import CoinCollection, CoinCollectionApp


class CoinCollectionAppTypeBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.path = self.directory / "collection.json"
        self.app = CoinCollectionApp(CoinCollection(str(self.path)))

    def add_with_detector(self, payload, *, use_detection=True):
        self.app.current_detection_result = payload
        self.assertTrue(self.app.add_to_collection(
            "Caller country", "Caller denomination", "2024", "VF", "Synthetic note",
            use_detection=use_detection,
        ))
        item = self.app.collection.get_item(self.app.last_added_item_id)
        self.assertIsNotNone(item)
        rows = json.loads(self.path.read_text(encoding="utf-8"))
        row = next(row for row in rows if row["id"] == item.id)
        reloaded = CoinCollection(str(self.path)).get_item(item.id)
        self.assertIsNotNone(reloaded)
        self.assertEqual((item.country, item.denomination, item.detection_confidence),
                         (reloaded.country, reloaded.denomination,
                          reloaded.detection_confidence))
        return item, row

    def assert_confidence(self, item, row, expected):
        self.assertIs(type(item.detection_confidence), float)
        self.assertEqual(item.detection_confidence, expected)
        self.assertIs(type(row["detection_confidence"]), float)
        self.assertEqual(row["detection_confidence"], expected)

    def test_detector_strings_override_caller_values_verbatim(self):
        for country, denomination in (("Canada", "Quarter"), (" Canada ", "")):
            with self.subTest(country=country, denomination=denomination):
                item, row = self.add_with_detector({
                    "country": country, "denomination": denomination, "confidence": 72.5,
                })
                self.assertEqual((item.country, item.denomination), (country, denomination))
                self.assertEqual((row["country"], row["denomination"]),
                                 (country, denomination))
                self.assertTrue(item.auto_detected)

    def test_non_string_country_retains_caller_country(self):
        for value in (None, 42, True, {}, [], object()):
            with self.subTest(value=value):
                item, row = self.add_with_detector({"country": value, "denomination": "Cent"})
                self.assertEqual((item.country, item.denomination), ("Caller country", "Cent"))
                self.assertEqual(row["country"], "Caller country")

    def test_non_string_denomination_retains_caller_denomination(self):
        for value in (None, 42, True, {}, [], object()):
            with self.subTest(value=value):
                item, row = self.add_with_detector({"country": "Canada", "denomination": value})
                self.assertEqual((item.country, item.denomination),
                                 ("Canada", "Caller denomination"))
                self.assertEqual(row["denomination"], "Caller denomination")

    def test_numeric_confidence_is_persisted_as_float_without_rescaling(self):
        for value, expected in ((72, 72.0), (0.625, 0.625), (0, 0.0), (-2.5, -2.5)):
            with self.subTest(value=value):
                item, row = self.add_with_detector({"confidence": value})
                self.assert_confidence(item, row, expected)

    def test_real_numeric_confidence_is_normalized_to_float(self):
        item, row = self.add_with_detector({"confidence": Fraction(3, 4)})
        self.assert_confidence(item, row, 0.75)

    def test_malformed_confidence_falls_back_to_zero(self):
        for value in (None, "72", "bad", {}, [], object(), 2 + 3j):
            with self.subTest(value=value):
                item, row = self.add_with_detector({"confidence": value})
                self.assert_confidence(item, row, 0.0)

    def test_boolean_confidence_falls_back_to_zero(self):
        for value in (True, False):
            with self.subTest(value=value):
                item, row = self.add_with_detector({"confidence": value})
                self.assert_confidence(item, row, 0.0)

    def test_unrepresentable_numeric_confidence_falls_back_to_zero(self):
        item, row = self.add_with_detector({"confidence": 10 ** 400})
        self.assert_confidence(item, row, 0.0)

    def test_missing_detector_fields_retain_caller_values_and_zero_confidence(self):
        item, row = self.add_with_detector({"success": True})
        self.assertEqual((item.country, item.denomination),
                         ("Caller country", "Caller denomination"))
        self.assert_confidence(item, row, 0.0)
        self.assertTrue(item.auto_detected)

    def test_detection_disabled_ignores_detector_fields(self):
        item, row = self.add_with_detector({
            "country": "Canada", "denomination": "Quarter", "confidence": 72,
        }, use_detection=False)
        self.assertEqual((item.country, item.denomination),
                         ("Caller country", "Caller denomination"))
        self.assert_confidence(item, row, 0.0)
        self.assertFalse(item.auto_detected)

    def test_empty_detector_result_preserves_manual_add_behavior(self):
        for payload in (None, {}):
            with self.subTest(payload=payload):
                item, row = self.add_with_detector(payload)
                self.assertEqual((item.country, item.denomination),
                                 ("Caller country", "Caller denomination"))
                self.assert_confidence(item, row, 0.0)
                self.assertFalse(item.auto_detected)

    def test_export_default_and_none_use_historical_relative_path(self):
        self.add_with_detector(None, use_detection=False)
        (self.directory / "data").mkdir()
        previous_directory = os.getcwd()
        try:
            os.chdir(self.directory)
            for explicit_none in (False, True):
                with self.subTest(explicit_none=explicit_none):
                    result = (self.app.export_collection(None) if explicit_none
                              else self.app.export_collection())
                    self.assertTrue(result)
                    output = self.directory / "data" / "collection_export.csv"
                    with output.open(encoding="utf-8", newline="") as handle:
                        rows = list(csv.DictReader(handle))
                    self.assertEqual([row["country"] for row in rows], ["Caller country"])
                    output.unlink()
        finally:
            os.chdir(previous_directory)

    def test_export_explicit_path_is_preserved(self):
        self.add_with_detector(None, use_detection=False)
        output = self.directory / "chosen.csv"
        self.assertTrue(self.app.export_collection(str(output)))
        with output.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([row["denomination"] for row in rows], ["Caller denomination"])
        self.assertFalse((self.directory / "data" / "collection_export.csv").exists())


if __name__ == "__main__":
    unittest.main()
