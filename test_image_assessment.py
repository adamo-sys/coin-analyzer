import os
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from coin_collection import CoinItem, ItemPhoto, PhotoRole
from image_assessment import (
    DownstreamPermission,
    DownstreamUse,
    ImageAssessmentConfidence,
    ImageAssessmentEngine,
    ImageReadinessDecision,
)


def write_image(path, image):
    cv2.imwrite(path, image)
    return path


def valid_image(size=1000):
    tile = np.array([[80, 180], [180, 80]], dtype=np.uint8)
    gray = np.tile(tile, (size // 2, size // 2))
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def solid_image(value, size=1000):
    return np.full((size, size, 3), value, dtype=np.uint8)


def low_contrast_image(size=1000):
    gray = np.full((size, size), 120, dtype=np.uint8)
    gray[:, ::2] = 124
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def blurred_image(size=1000):
    return cv2.GaussianBlur(valid_image(size), (51, 51), 0)


def item_with_photos(photos):
    return CoinItem(
        id="item-1",
        image_path="",
        country="Canada",
        denomination="Cent",
        year="1920",
        grade="VF-20",
        notes="",
        date_added="2026-07-13",
        photos=photos,
    )


class ImageAssessmentTests(unittest.TestCase):
    def test_empty_photo_set(self):
        report = ImageAssessmentEngine().assess_photos([])

        self.assertEqual(0, report.overall_readiness_score)
        self.assertEqual(ImageReadinessDecision.NOT_READY, report.decision)
        self.assertEqual(DownstreamPermission.NO, report.downstream_permissions[DownstreamUse.BROAD_IDENTIFICATION.value])
        self.assertIn("No photos are attached for assessment.", report.blocking_issues)

    def test_one_valid_photo_is_limited(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            front = write_image(os.path.join(tmpdir, "front.jpg"), valid_image())

            report = ImageAssessmentEngine().assess_photos([ItemPhoto(front, role=PhotoRole.FRONT)])

            self.assertEqual(1, len(report.photo_assessments))
            self.assertEqual(ImageReadinessDecision.MAYBE, report.decision)
            self.assertEqual(DownstreamPermission.MAYBE, report.downstream_permissions[DownstreamUse.BROAD_IDENTIFICATION.value])
            self.assertEqual(DownstreamPermission.NO, report.downstream_permissions[DownstreamUse.GRADE_ESTIMATION.value])
            self.assertIn("No back or reverse photo is present.", report.blocking_issues)

    def test_obverse_and_reverse_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            front = write_image(os.path.join(tmpdir, "front.jpg"), valid_image())
            back = write_image(os.path.join(tmpdir, "back.jpg"), valid_image())

            report = ImageAssessmentEngine().assess_photos([
                ItemPhoto(front, role=PhotoRole.FRONT),
                ItemPhoto(back, role=PhotoRole.BACK),
            ])

            self.assertEqual(ImageReadinessDecision.READY, report.decision)
            self.assertTrue(report.required_roles_present["front"])
            self.assertTrue(report.required_roles_present["back"])
            self.assertEqual(DownstreamPermission.YES, report.downstream_permissions[DownstreamUse.BROAD_IDENTIFICATION.value])
            self.assertEqual(DownstreamPermission.YES, report.downstream_permissions[DownstreamUse.GRADE_ESTIMATION.value])

    def test_missing_reverse(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            front = write_image(os.path.join(tmpdir, "front.jpg"), valid_image())

            report = ImageAssessmentEngine().assess_photos([ItemPhoto(front, role=PhotoRole.FRONT)])

            self.assertIn("back", report.missing_roles)
            self.assertEqual(DownstreamPermission.NO, report.downstream_permissions[DownstreamUse.SUBMISSION_READINESS.value])

    def test_certified_item_missing_label_photo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            front = write_image(os.path.join(tmpdir, "front.jpg"), valid_image())
            back = write_image(os.path.join(tmpdir, "back.jpg"), valid_image())

            report = ImageAssessmentEngine().assess_photos([
                ItemPhoto(front, role=PhotoRole.FRONT),
                ItemPhoto(back, role=PhotoRole.BACK),
            ], certified_expected=True)

            self.assertIn("certification label", report.missing_roles)
            self.assertEqual(DownstreamPermission.NO, report.downstream_permissions[DownstreamUse.SUBMISSION_READINESS.value])

    def test_unsupported_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "front.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("not an image")

            assessment = ImageAssessmentEngine().assess_photo(ItemPhoto(path, role=PhotoRole.FRONT))

            self.assertEqual(ImageReadinessDecision.NOT_READY, assessment.decision)
            self.assertIn("Unsupported image format: .txt.", assessment.issues)

    def test_missing_file(self):
        assessment = ImageAssessmentEngine().assess_photo(ItemPhoto("missing.jpg", role=PhotoRole.FRONT))

        self.assertEqual(0, assessment.readiness_score)
        self.assertIn("Image file is missing.", assessment.blocking_issues)

    def test_inaccessible_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_image(os.path.join(tmpdir, "front.jpg"), valid_image())

            with patch("image_assessment.os.path.getsize", side_effect=PermissionError("denied")):
                assessment = ImageAssessmentEngine().assess_photo(ItemPhoto(path, role=PhotoRole.FRONT))

            self.assertEqual(0, assessment.readiness_score)
            self.assertIn("Image file is inaccessible.", assessment.blocking_issues)
            self.assertIn("denied", assessment.engine_errors[0])

    def test_zero_byte_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "empty.jpg")
            open(path, "wb").close()

            assessment = ImageAssessmentEngine().assess_photo(ItemPhoto(path, role=PhotoRole.FRONT))

            self.assertEqual(0, assessment.readiness_score)
            self.assertIn("Image file is zero bytes.", assessment.blocking_issues)

    def test_corrupted_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "corrupt.jpg")
            with open(path, "wb") as handle:
                handle.write(b"not a real jpg")

            assessment = ImageAssessmentEngine().assess_photo(ItemPhoto(path, role=PhotoRole.FRONT))

            self.assertEqual(0, assessment.readiness_score)
            self.assertIn("Image file could not be decoded.", assessment.blocking_issues)

    def test_low_resolution_image(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_image(os.path.join(tmpdir, "small.jpg"), valid_image(size=200))

            assessment = ImageAssessmentEngine().assess_photo(ItemPhoto(path, role=PhotoRole.FRONT))

            self.assertIn("Image resolution is extremely small.", assessment.issues)
            self.assertLess(assessment.readiness_score, 80)

    def test_underexposed_image(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_image(os.path.join(tmpdir, "dark.jpg"), solid_image(20))

            assessment = ImageAssessmentEngine().assess_photo(ItemPhoto(path, role=PhotoRole.FRONT))

            self.assertIn("Image appears underexposed.", assessment.issues)

    def test_overexposed_image(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_image(os.path.join(tmpdir, "bright.jpg"), solid_image(240))

            assessment = ImageAssessmentEngine().assess_photo(ItemPhoto(path, role=PhotoRole.FRONT))

            self.assertIn("Image appears overexposed.", assessment.issues)

    def test_low_contrast(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_image(os.path.join(tmpdir, "low_contrast.jpg"), low_contrast_image())

            assessment = ImageAssessmentEngine().assess_photo(ItemPhoto(path, role=PhotoRole.FRONT))

            self.assertIn("Image contrast is low.", assessment.issues)

    def test_blur_heuristic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_image(os.path.join(tmpdir, "blur.jpg"), blurred_image())

            assessment = ImageAssessmentEngine().assess_photo(ItemPhoto(path, role=PhotoRole.FRONT))

            self.assertTrue(any("blurred" in issue for issue in assessment.issues))

    def test_duplicate_references(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_image(os.path.join(tmpdir, "front.jpg"), valid_image())
            back = write_image(os.path.join(tmpdir, "back.jpg"), valid_image())

            report = ImageAssessmentEngine().assess_photos([
                ItemPhoto(path, role=PhotoRole.FRONT),
                ItemPhoto(path, role=PhotoRole.FRONT),
                ItemPhoto(back, role=PhotoRole.BACK),
            ])

            self.assertTrue(any("Duplicate photo references detected" in item for item in report.evidence))
            self.assertTrue(any("Duplicate photo reference" in issue for issue in report.photo_assessments[0].issues))

    def test_malformed_photo_role_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_image(os.path.join(tmpdir, "front.jpg"), valid_image())

            assessment = ImageAssessmentEngine().assess_photo({"path": path, "role": "mystery-side"})

            self.assertEqual(PhotoRole.OTHER.value, assessment.role)
            self.assertIn("Photo role is not recognized: mystery-side.", assessment.issues)

    def test_readiness_differs_by_downstream_task(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            front = write_image(os.path.join(tmpdir, "front.jpg"), valid_image())
            back = write_image(os.path.join(tmpdir, "back.jpg"), valid_image())

            report = ImageAssessmentEngine().assess_photos([
                ItemPhoto(front, role=PhotoRole.FRONT),
                ItemPhoto(back, role=PhotoRole.BACK),
            ])

            self.assertEqual(DownstreamPermission.YES, report.downstream_permissions[DownstreamUse.BROAD_IDENTIFICATION.value])
            self.assertEqual(DownstreamPermission.MAYBE, report.downstream_permissions[DownstreamUse.VARIETY_ATTRIBUTION.value])

    def test_multi_photo_aggregation_with_detail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            front = write_image(os.path.join(tmpdir, "front.jpg"), valid_image())
            back = write_image(os.path.join(tmpdir, "back.jpg"), valid_image())
            detail = write_image(os.path.join(tmpdir, "detail.jpg"), valid_image())

            report = ImageAssessmentEngine().assess_photos([
                ItemPhoto(front, role=PhotoRole.FRONT),
                ItemPhoto(back, role=PhotoRole.BACK),
                ItemPhoto(detail, role=PhotoRole.DETAIL),
            ])

            self.assertTrue(report.required_roles_present["detail"])
            self.assertEqual(DownstreamPermission.YES, report.downstream_permissions[DownstreamUse.VARIETY_ATTRIBUTION.value])

    def test_deterministic_score_and_evidence_order(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            front = write_image(os.path.join(tmpdir, "front.jpg"), valid_image())
            back = write_image(os.path.join(tmpdir, "back.jpg"), valid_image())
            engine = ImageAssessmentEngine()

            first = engine.assess_photos([ItemPhoto(front, role=PhotoRole.FRONT), ItemPhoto(back, role=PhotoRole.BACK)]).to_dict()
            second = engine.assess_photos([ItemPhoto(front, role=PhotoRole.FRONT), ItemPhoto(back, role=PhotoRole.BACK)]).to_dict()

            self.assertEqual(first, second)

    def test_graceful_partial_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            front = write_image(os.path.join(tmpdir, "front.jpg"), valid_image())
            missing = os.path.join(tmpdir, "missing.jpg")

            report = ImageAssessmentEngine().assess_photos([
                ItemPhoto(front, role=PhotoRole.FRONT),
                ItemPhoto(missing, role=PhotoRole.BACK),
            ])

            self.assertEqual(2, len(report.photo_assessments))
            self.assertEqual(0, report.photo_assessments[1].readiness_score)
            self.assertTrue(report.blocking_issues)

    def test_no_collection_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            front = write_image(os.path.join(tmpdir, "front.jpg"), valid_image())
            back = write_image(os.path.join(tmpdir, "back.jpg"), valid_image())
            item = item_with_photos([
                ItemPhoto(front, role=PhotoRole.FRONT, is_primary=True, display_order=0),
                ItemPhoto(back, role=PhotoRole.BACK, display_order=1),
            ])
            before = item.to_dict()

            ImageAssessmentEngine().assess_item(item)

            self.assertEqual(before, item.to_dict())

    def test_dto_serialization(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            front = write_image(os.path.join(tmpdir, "front.jpg"), valid_image())

            report_dict = ImageAssessmentEngine().assess_photos([ItemPhoto(front, role=PhotoRole.FRONT)]).to_dict()

            self.assertIn("photo_assessments", report_dict)
            self.assertIsInstance(report_dict["downstream_permissions"][DownstreamUse.OCR.value], str)
            self.assertIsInstance(report_dict["photo_assessments"][0]["decision"], str)

    def test_no_ocr_identification_or_grading_calls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            front = write_image(os.path.join(tmpdir, "front.jpg"), valid_image())
            back = write_image(os.path.join(tmpdir, "back.jpg"), valid_image())

            with patch("coin_recognition.CoinRecognizer.detect_coin", side_effect=AssertionError("should not call")):
                with patch("coin_grading.CoinGrader.estimate_grade", side_effect=AssertionError("should not call")):
                    report = ImageAssessmentEngine().assess_photos([
                        ItemPhoto(front, role=PhotoRole.FRONT),
                        ItemPhoto(back, role=PhotoRole.BACK),
                    ])

            self.assertEqual(ImageReadinessDecision.READY, report.decision)

    def test_confidence_reflects_limitations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            front = write_image(os.path.join(tmpdir, "front.jpg"), low_contrast_image())

            assessment = ImageAssessmentEngine().assess_photo(ItemPhoto(front, role=PhotoRole.FRONT))

            self.assertEqual(ImageAssessmentConfidence.MEDIUM, assessment.confidence)


if __name__ == "__main__":
    unittest.main()
