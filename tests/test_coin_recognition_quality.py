"""Focused contracts for the legacy detector's evidence-based suggestions."""

import unittest
from unittest.mock import patch

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
        with (
            patch.object(self.recognizer, "crop_date_region", return_value=None),
            patch.object(self.recognizer, "build_embossed_text_jobs", return_value=[]),
            patch("pytesseract.image_to_string", return_value="ONE CENT 18 59"),
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
        with (
            patch.object(self.recognizer, "crop_date_region", return_value=None),
            patch.object(self.recognizer, "build_embossed_text_jobs", return_value=jobs),
            patch("pytesseract.image_to_string", side_effect=["ONE", "CENT", "1859"]),
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
