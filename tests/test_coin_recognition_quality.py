"""Focused contracts for the legacy detector's evidence-based suggestions."""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from coin_recognition import CoinRecognizer


class TestCoinRecognitionQuality(unittest.TestCase):
    def setUp(self):
        with patch.object(CoinRecognizer, "configure_tesseract"):
            self.recognizer = CoinRecognizer()

    def test_explicit_one_cent_text_beats_indefensible_size_guess(self):
        coin = np.full((400, 400), 125, dtype=np.uint8)

        result = self.recognizer.identify_denomination(
            coin,
            {"radius": 200},
            ocr_text="ONE CENT\n1859",
        )

        self.assertEqual("penny", result["denomination"])
        self.assertEqual(1.0, result["confidence"])
        self.assertEqual("ocr_text", result["source"])

    def test_missing_text_abstains_instead_of_guessing_from_crop_size(self):
        coin = np.full((400, 400), 125, dtype=np.uint8)

        result = self.recognizer.identify_denomination(
            coin,
            {"radius": 200},
            ocr_text="",
        )

        self.assertEqual("unknown", result["denomination"])
        self.assertEqual(0.0, result["confidence"])
        self.assertEqual("unavailable", result["source"])

    def test_one_with_spurious_trailing_s_requires_cent_token(self):
        accepted = self.recognizer.identify_denomination(
            np.zeros((20, 20), dtype=np.uint8),
            {"radius": 10},
            ocr_text="ONES CENT",
        )
        rejected = self.recognizer.identify_denomination(
            np.zeros((20, 20), dtype=np.uint8),
            {"radius": 10},
            ocr_text="ONES",
        )

        self.assertEqual("penny", accepted["denomination"])
        self.assertEqual("unknown", rejected["denomination"])

    def test_conflicting_denomination_text_abstains(self):
        result = self.recognizer.identify_denomination(
            np.zeros((20, 20), dtype=np.uint8),
            {"radius": 10},
            ocr_text="ONE CENT ONE DOLLAR",
        )

        self.assertEqual("unknown", result["denomination"])
        self.assertEqual("conflicting_ocr_text", result["source"])

    def test_year_parser_accepts_digits_split_by_ocr_spacing(self):
        self.assertEqual(
            ["1859"],
            self.recognizer.extract_years_from_text("ONE CENT 18 59"),
        )

    def test_year_detection_ocr_includes_whole_coin_variants(self):
        coin = np.zeros((80, 80), dtype=np.uint8)
        fake_pytesseract = SimpleNamespace(
            image_to_string=Mock(return_value="ONE CENT 18 59"),
        )
        with (
            patch.object(self.recognizer, "crop_date_region", return_value=None),
            patch.object(self.recognizer, "build_embossed_text_jobs", return_value=[]),
            patch.dict(sys.modules, {"pytesseract": fake_pytesseract}),
        ):
            result = self.recognizer.detect_year(
                coin,
                "reverse",
                "synthetic.jpg",
                {"center": (40, 40), "radius": 35},
            )

        self.assertEqual("1859", result["year"])
        self.assertIn("ONE CENT", result["all_ocr_text"])

    def test_embossed_text_jobs_combine_separate_denomination_lines(self):
        jobs = [
            ("upper", np.zeros((20, 40), dtype=np.uint8), "upper-config"),
            ("lower", np.zeros((20, 40), dtype=np.uint8), "lower-config"),
            ("date", np.zeros((20, 40), dtype=np.uint8), "date-config"),
        ]
        fake_pytesseract = SimpleNamespace(
            image_to_string=Mock(side_effect=["ONE", "CENT", "1859"]),
        )
        with (
            patch.object(self.recognizer, "crop_date_region", return_value=None),
            patch.object(self.recognizer, "build_embossed_text_jobs", return_value=jobs),
            patch.dict(sys.modules, {"pytesseract": fake_pytesseract}),
        ):
            result = self.recognizer.detect_year(
                np.empty((0, 0), dtype=np.uint8),
                "reverse",
                "synthetic.jpg",
                {"center": (40, 40), "radius": 35},
            )

        denomination = self.recognizer.identify_denomination(
            np.empty((0, 0), dtype=np.uint8),
            {"radius": 35},
            ocr_text=result["recognized_text"],
        )
        self.assertEqual("1859", result["year"])
        self.assertEqual("penny", denomination["denomination"])

    def detect_fixture_dates(self, readings):
        """Supply deterministic OCR text without accessing photos or an engine."""
        jobs = [
            (f"fixture_{index}", np.zeros((20, 40), dtype=np.uint8), "fixture-config")
            for index in range(len(readings))
        ]
        fake_ocr = SimpleNamespace(image_to_string=Mock(side_effect=readings))
        with (
            patch.object(self.recognizer, "crop_date_region", return_value=None),
            patch.object(self.recognizer, "build_embossed_text_jobs", return_value=jobs),
            patch.dict(sys.modules, {"pytesseract": fake_ocr}),
        ):
            return self.recognizer.detect_year(
                np.empty((0, 0), dtype=np.uint8), "reverse", "synthetic.jpg",
                {"center": (20, 20), "radius": 15},
            )

    def test_conflicting_dates_abstain_even_with_repeated_majority(self):
        for readings in (
            ["1959", "1959", "1969"],
            ["1969", "1959", "1959"],
            ["1959 1959 1959", "1969"],
            ["1959", "1969"],
            ["1959 1969"],
            ["1959 19 69"],
            ["19 59 1969"],
            ["19 59 19 69"],
        ):
            with self.subTest(readings=readings):
                result = self.detect_fixture_dates(readings)
                self.assertIsNone(result["year"])
                self.assertEqual(0.0, result["confidence"])
                self.assertEqual({"1959", "1969"}, {c["year"] for c in result["candidates"]})
                self.assertTrue(all(c["source"] for c in result["candidates"]))

    def test_date_parser_does_not_complete_partial_or_ambiguous_digits(self):
        for text in ("19\n59", "19\r\n59", "19\v59", "19", "195", "19?9", "19S9", "", "unreadable"):
            with self.subTest(text=text):
                self.assertEqual([], self.recognizer.extract_years_from_text(text))

    def test_clear_dates_and_horizontal_spacing_remain_supported(self):
        for text in ("CANADA ONE CENT 1959", "CANADA ONE CENT 19 59", "1 9 5 9", "19\t59"):
            with self.subTest(text=text):
                result = self.detect_fixture_dates([text, text])
                self.assertEqual("1959", result["year"])
                self.assertGreater(result["confidence"], 0.0)

    def test_missing_partial_and_unreadable_dates_abstain(self):
        for readings in (["", ""], ["195", "19?9"], ["19\n59", "19S9"], [RuntimeError("OCR timeout")]):
            with self.subTest(readings=readings):
                result = self.detect_fixture_dates(readings)
                self.assertIsNone(result["year"])
                self.assertEqual([], result["candidates"])
                self.assertEqual(0.0, result["confidence"])

    def test_uncertain_date_cannot_complete_canadian_identity(self):
        from coin_collection_gui import CoinCollectionGUI
        from legacy_coin_recognition_capability import LegacyCoinRecognitionCapability, to_legacy_detector_result

        image = np.zeros((40, 40, 3), dtype=np.uint8)
        readings = ["CANADA ONE CENT 1959", "1959", "1969"]
        fake_ocr = SimpleNamespace(image_to_string=Mock(side_effect=readings))
        with (
            patch("coin_recognition.cv2.imread", return_value=image),
            patch.object(self.recognizer, "detect_coin_circle", return_value={
                "success": True, "center": (20, 20), "radius": 15, "diameter": 30,
            }),
            patch.object(self.recognizer, "crop_date_region", return_value=None),
            patch.object(self.recognizer, "build_embossed_text_jobs", return_value=[]),
            patch.dict(sys.modules, {"pytesseract": fake_ocr}),
        ):
            capability = LegacyCoinRecognitionCapability(lambda: self.recognizer)
            result = to_legacy_detector_result(capability.execute("synthetic.jpg"))

        self.assertTrue(result["success"])
        self.assertEqual("Canada", result["country"])
        self.assertEqual("penny", result["denomination"])
        self.assertIsNone(result["year"])
        self.assertEqual(0.0, result["year_confidence"])
        self.assertTrue(CoinCollectionGUI.recognition_result_needs_paired_review(result))

    def test_embossed_text_jobs_are_bounded(self):
        image = np.zeros((3200, 3000), dtype=np.uint8)
        with patch("coin_recognition.cv2.imread", return_value=image):
            jobs = self.recognizer.build_embossed_text_jobs(
                "synthetic.jpg",
                {"center": (1500, 1600), "radius": 1500},
            )

        self.assertEqual(3, len(jobs))
        self.assertTrue(all(max(region.shape) <= 1800 for _, region, _ in jobs))

    def test_country_matching_requires_whole_words(self):
        self.assertEqual(
            "unknown",
            self.recognizer.detect_country("unused", "adaptive threshold result")["country"],
        )
        self.assertEqual(
            "Canada",
            self.recognizer.detect_country("unused", "VICTORIA REGINA CANADA")["country"],
        )

    def test_detect_coin_uses_ocr_text_for_denomination(self):
        image = np.zeros((20, 20, 3), dtype=np.uint8)
        year_result = {
            "year": "1859",
            "confidence": 0.6,
            "candidates": [{"year": "1859", "confidence": 0.6, "source": "date"}],
            "all_ocr_text": "ONE CENT 1859",
        }
        with (
            patch("coin_recognition.cv2.imread", return_value=image),
            patch.object(
                self.recognizer,
                "detect_coin_circle",
                return_value={"success": True, "center": (10, 10), "radius": 8, "diameter": 16},
            ),
            patch.object(self.recognizer, "segment_coin", return_value=np.zeros((16, 16), dtype=np.uint8)),
            patch.object(self.recognizer, "identify_orientation", return_value="reverse"),
            patch.object(self.recognizer, "detect_year", return_value=year_result),
        ):
            result = self.recognizer.detect_coin("synthetic.jpg")

        self.assertTrue(result["success"])
        self.assertEqual("penny", result["denomination"])
        self.assertEqual("1859", result["year"])

    def test_circle_detection_scales_coordinates_back_from_large_photo(self):
        gray = np.zeros((2000, 1500), dtype=np.uint8)
        original = np.zeros((2000, 1500, 3), dtype=np.uint8)
        observed_shapes = []

        def fake_hough(image, *_args, **_kwargs):
            observed_shapes.append(image.shape)
            return np.array([[[375.0, 500.0, 300.0]]], dtype=np.float32)

        with patch("coin_recognition.cv2.HoughCircles", side_effect=fake_hough):
            result = self.recognizer.detect_coin_circle(gray, original)

        self.assertEqual((1000, 750), observed_shapes[0])
        self.assertEqual((750, 1000), result["center"])
        self.assertEqual(600, result["radius"])

    def test_circle_detection_rejects_larger_mostly_off_frame_candidate(self):
        gray = np.zeros((1000, 1000), dtype=np.uint8)
        original = np.zeros((1000, 1000, 3), dtype=np.uint8)
        candidates = np.array(
            [[[950.0, 500.0, 490.0], [500.0, 500.0, 450.0]]],
            dtype=np.float32,
        )

        with patch("coin_recognition.cv2.HoughCircles", return_value=candidates):
            result = self.recognizer.detect_coin_circle(gray, original)

        self.assertEqual((500, 500), result["center"])
        self.assertEqual(450, result["radius"])

    def test_ocr_resize_caps_large_coin_crop(self):
        resized = self.recognizer.resize_for_ocr(np.zeros((1600, 1200), dtype=np.uint8))

        self.assertEqual((1000, 750), resized.shape)


if __name__ == "__main__":
    unittest.main()
