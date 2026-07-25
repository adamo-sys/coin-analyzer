"""Focused tests for Sprint 9 Unit 1A OCR metadata contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
import unittest

from capture_import.workflow_ocr_models import (
    OCRConflict,
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRObservation,
    OCRReviewStatus,
)


def observation(**changes) -> OCRObservation:
    values = {
        "source_coin_id": "coin-1",
        "image_role": "front",
        "artifact_key": "cropped-coin-1-front",
        "provider_id": "test-provider",
        "raw_text": "CANADA 1967",
        "confidence_score": 82.0,
    }
    values.update(changes)
    return OCRObservation(**values)


def candidate(**changes) -> OCRFieldCandidate:
    values = {
        "source_coin_id": "coin-1",
        "image_role": "front",
        "artifact_key": "cropped-coin-1-front",
        "provider_id": "test-provider",
        "field_name": "year",
        "raw_text": "1967",
        "normalized_value": "1967",
        "confidence_score": 82.0,
        "evidence": ("four-digit year pattern",),
    }
    values.update(changes)
    return OCRFieldCandidate(**values)


def conflict(**changes) -> OCRConflict:
    values = {
        "source_coin_id": "coin-1",
        "field_name": "year",
        "candidate_values": ("1961", "1967"),
        "reason": "Front and reverse OCR candidates disagree.",
    }
    values.update(changes)
    return OCRConflict(**values)


class OCRObservationTests(unittest.TestCase):
    def test_valid_observation_is_immutable_and_json_safe(self) -> None:
        value = observation()
        value.validate()

        with self.assertRaises(FrozenInstanceError):
            value.raw_text = "changed"  # type: ignore[misc]

        json.dumps(value.to_dict(), allow_nan=False, sort_keys=True)

    def test_confidence_must_be_finite_and_bounded(self) -> None:
        for invalid in (-0.1, 100.1, float("inf"), float("nan"), True, "82"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    observation(confidence_score=invalid).validate()

    def test_artifact_key_cannot_be_a_path(self) -> None:
        for invalid in ("images/front.jpg", r"images\front.jpg"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    observation(artifact_key=invalid).validate()

    def test_role_is_closed(self) -> None:
        with self.assertRaises(ValueError):
            observation(image_role="obverse").validate()


class OCRFieldCandidateTests(unittest.TestCase):
    def test_candidate_is_review_only(self) -> None:
        value = candidate()
        value.validate()

        self.assertIs(
            value.review_status,
            OCRReviewStatus.REVIEW_REQUIRED,
        )

    def test_field_name_is_allowlisted(self) -> None:
        with self.assertRaises(ValueError):
            candidate(field_name="grade").validate()

    def test_evidence_must_be_sorted_unique_tuple(self) -> None:
        invalid_values = (
            ["one"],  # type: ignore[list-item]
            ("two", "one"),
            ("one", "one"),
        )
        for invalid in invalid_values:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    candidate(evidence=invalid).validate()  # type: ignore[arg-type]

    def test_candidate_cannot_be_marked_unavailable(self) -> None:
        with self.assertRaises(ValueError):
            candidate(
                review_status=OCRReviewStatus.UNAVAILABLE
            ).validate()


class OCRConflictTests(unittest.TestCase):
    def test_conflict_requires_two_distinct_sorted_values(self) -> None:
        conflict().validate()

        for invalid in (
            ("1967",),
            ("1967", "1961"),
            ("1967", "1967"),
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    conflict(candidate_values=invalid).validate()

    def test_conflict_status_is_fixed(self) -> None:
        with self.assertRaises(ValueError):
            conflict(
                review_status=OCRReviewStatus.REVIEW_REQUIRED
            ).validate()


class OCRMetadataReportTests(unittest.TestCase):
    def test_available_report_is_bounded_review_only_metadata(self) -> None:
        value = OCRMetadataReport(
            provider_available=True,
            observations=(observation(),),
            candidates=(candidate(),),
            conflicts=(),
        )
        value.validate()

        payload = value.to_dict()
        self.assertTrue(payload["manual_review_required"])
        self.assertEqual(payload["review_status"], "REVIEW_REQUIRED")
        json.dumps(payload, allow_nan=False, sort_keys=True)

    def test_conflicts_force_conflict_status(self) -> None:
        value = OCRMetadataReport(
            provider_available=True,
            observations=(observation(),),
            candidates=(
                candidate(),
                candidate(
                    image_role="reverse",
                    artifact_key="cropped-coin-1-reverse",
                    normalized_value="1961",
                    confidence_score=71.0,
                    evidence=("four-digit year pattern",),
                ),
            ),
            conflicts=(conflict(),),
            review_status=OCRReviewStatus.CONFLICT,
        )
        value.validate()
        self.assertEqual(value.to_dict()["review_status"], "CONFLICT")

    def test_provider_unavailable_is_not_a_failure(self) -> None:
        value = OCRMetadataReport(
            provider_available=False,
            review_status=OCRReviewStatus.UNAVAILABLE,
        )
        value.validate()

        payload = value.to_dict()
        self.assertEqual(payload["candidate_count"], 0)
        self.assertEqual(payload["review_status"], "UNAVAILABLE")

    def test_unavailable_provider_cannot_claim_results(self) -> None:
        with self.assertRaises(ValueError):
            OCRMetadataReport(
                provider_available=False,
                observations=(observation(),),
                review_status=OCRReviewStatus.UNAVAILABLE,
            ).validate()

    def test_report_requires_deterministic_candidate_order(self) -> None:
        later = candidate(
            field_name="year",
            normalized_value="1967",
        )
        earlier = candidate(
            field_name="country",
            raw_text="CANADA",
            normalized_value="Canada",
            confidence_score=91.0,
            evidence=("country keyword",),
        )

        valid = OCRMetadataReport(
            provider_available=True,
            candidates=(earlier, later),
        )
        valid.validate()

        with self.assertRaises(ValueError):
            replace(valid, candidates=(later, earlier)).validate()

    def test_report_collections_must_be_tuples(self) -> None:
        with self.assertRaises(ValueError):
            OCRMetadataReport(
                provider_available=True,
                observations=[observation()],  # type: ignore[arg-type]
            ).validate()


if __name__ == "__main__":
    unittest.main()