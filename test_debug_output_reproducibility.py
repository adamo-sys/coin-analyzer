"""Regression tests for repository-relative OCR experiment outputs."""

import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import coin_recognition
import extract_date_regions
import label_years
import template_matching_year
import year_ocr_experiment


class DebugOutputReproducibilityTests(unittest.TestCase):
    def test_experiment_defaults_are_repository_relative(self):
        project_root = os.path.dirname(os.path.abspath(__file__))

        self.assertEqual(project_root, extract_date_regions.PROJECT_ROOT)
        self.assertEqual(project_root, label_years.PROJECT_ROOT)
        self.assertEqual(project_root, template_matching_year.PROJECT_ROOT)
        self.assertEqual(project_root, year_ocr_experiment.PROJECT_ROOT)
        self.assertEqual(project_root, coin_recognition.PROJECT_ROOT)
        self.assertEqual(
            os.path.join(project_root, "test_coins"),
            extract_date_regions.DEFAULT_INPUT_FOLDER,
        )
        self.assertEqual(
            os.path.join(project_root, "test_coins"),
            template_matching_year.DEFAULT_TEST_FOLDER,
        )
        self.assertEqual(
            os.path.join(project_root, "test_coins"),
            year_ocr_experiment.DEFAULT_TEST_FOLDER,
        )

    def test_date_region_processing_is_sorted_and_creates_output_directory(self):
        extractor = extract_date_regions.DateRegionExtractor()
        with tempfile.TemporaryDirectory() as temp_dir:
            input_folder = os.path.join(temp_dir, "inputs")
            output_folder = os.path.join(temp_dir, "nested", "outputs")
            os.makedirs(input_folder)
            for filename in ("z.PNG", "A.jpeg", "middle.jpg", "ignore.txt"):
                open(os.path.join(input_folder, filename), "wb").close()

            processed = []

            def record(image_path, _output_folder):
                processed.append(os.path.basename(image_path))
                return []

            with patch.object(extractor, "extract_date_regions", side_effect=record):
                extractor.process_folder(input_folder, output_folder)

            self.assertTrue(os.path.isdir(output_folder))
            self.assertEqual(["A.jpeg", "middle.jpg", "z.PNG"], processed)

    def test_debug_writers_create_their_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            detector_output = os.path.join(temp_dir, "template", "debug")
            detector = template_matching_year.TemplateMatchingYearDetector(detector_output)
            self.assertFalse(os.path.exists(detector.debug_folder))
            template_image = np.zeros((10, 10, 3), dtype=np.uint8)
            template_result = {"debug_info": {}}
            with patch.object(template_matching_year.cv2, "imwrite", return_value=True) as write:
                detector.save_debug_images(
                    "fixture.jpeg",
                    template_image,
                    template_image,
                    [],
                    template_result,
                )
            self.assertTrue(os.path.isdir(detector.debug_folder))
            self.assertEqual(2, write.call_count)

            recognizer_output = os.path.join(temp_dir, "recognition")
            fake_image = np.zeros((40, 40, 3), dtype=np.uint8)
            with (
                patch.object(coin_recognition, "DEBUG_OUTPUT_ROOT", recognizer_output),
                patch.object(coin_recognition.cv2, "imread", return_value=fake_image),
                patch.object(coin_recognition.cv2, "imwrite", return_value=True) as write,
                patch.object(coin_recognition.CoinRecognizer, "configure_tesseract"),
            ):
                recognizer = coin_recognition.CoinRecognizer()
                crop = recognizer.crop_date_region("fixture.jpeg", {"center": (20, 20), "radius": 15})

            self.assertIsNotNone(crop)
            self.assertTrue(os.path.isdir(os.path.join(recognizer_output, "date_crops")))
            write.assert_called_once()

    def test_label_paths_resolve_from_repository_not_current_directory(self):
        expected = os.path.join(label_years.PROJECT_ROOT, "test_coins", "IMG_3460.jpeg")
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "year_labels.csv")
            resolved = label_years.resolve_label_image_path(
                csv_path,
                {"image_path": "test_coins/IMG_3460.jpeg", "crop_path": ""},
            )

        self.assertEqual(os.path.normpath(expected), resolved)

    def test_missing_optional_ocr_dependency_returns_actionable_error(self):
        experiment = year_ocr_experiment.YearOCRExperiment()
        with patch.object(
            year_ocr_experiment,
            "load_pytesseract",
            side_effect=RuntimeError("optional pytesseract and Tesseract are required"),
        ):
            text, error = experiment.run_ocr(np.zeros((2, 2), dtype=np.uint8), "7")

        self.assertEqual("", text)
        self.assertIn("pytesseract", error)
        self.assertIn("Tesseract", error)

    def test_all_ten_source_coin_fixtures_exist(self):
        fixture_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_coins")
        expected = {f"IMG_{number}.jpeg" for number in range(3460, 3470)}
        actual = {
            name
            for name in os.listdir(fixture_folder)
            if name.lower().endswith((".jpg", ".jpeg", ".png"))
        }

        self.assertEqual(expected, actual)

    def test_debug_outputs_are_ignored_and_absent_from_tracked_assets(self):
        project_root = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(project_root, ".gitignore"), "r", encoding="utf-8") as handle:
            ignore_rules = {line.strip() for line in handle if line.strip()}

        tracked = subprocess.run(
            ["git", "ls-files", "--", "debug_outputs"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("/debug_outputs/", ignore_rules)
        self.assertEqual("", tracked.stdout.strip())


if __name__ == "__main__":
    unittest.main()
