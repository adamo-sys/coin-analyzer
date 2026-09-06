from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from capture_import.workflow_ocr_models import OCRObservation
from multimodal_evidence_references import (
    CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
    MultimodalEvidenceKind,
    MultimodalEvidenceReference,
)
from ocr_text_reference_adapter import (
    EmptyOCRText,
    OCRTextReferenceAdaptation,
    adapt_ocr_observation_text_reference,
)


def observation(**changes: object) -> OCRObservation:
    values: dict[str, object] = {
        "source_coin_id": "coin-001",
        "image_role": "front",
        "artifact_key": "coin-001-front",
        "provider_id": "synthetic-provider",
        "raw_text": "CANADA 1967 25 CENTS",
        "confidence_score": 87.5,
    }
    values.update(changes)
    return OCRObservation(**values)  # type: ignore[arg-type]


class OCRTextReferenceAdapterTests(unittest.TestCase):
    def test_maps_non_empty_text_to_ocr_text_reference(self) -> None:
        source = observation()

        result = adapt_ocr_observation_text_reference(
            source,
            reference_id="ocr-text:coin-001-front",
            source_id="workflow:synthetic-001",
            locator="artifact:coin-001-front",
            source_fingerprint="sha256:synthetic",
        )

        self.assertIs(result.source, source)
        self.assertEqual(result.reference.kind, MultimodalEvidenceKind.OCR_TEXT)
        self.assertEqual(
            result.reference.schema_version,
            CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
        )
        self.assertEqual(result.reference.reference_id, "ocr-text:coin-001-front")
        self.assertEqual(result.reference.source_id, "workflow:synthetic-001")
        self.assertEqual(result.reference.locator, "artifact:coin-001-front")
        self.assertEqual(result.reference.source_fingerprint, "sha256:synthetic")

    def test_preserves_original_role_without_translation(self) -> None:
        for role in ("front", "reverse", "edge"):
            with self.subTest(role=role):
                source = observation(image_role=role)
                result = adapt_ocr_observation_text_reference(
                    source,
                    reference_id=f"ocr-text:{role}",
                    source_id="workflow:synthetic-001",
                    locator=f"artifact:{role}",
                )
                self.assertEqual(result.source.image_role, role)
                self.assertEqual(result.reference.kind, MultimodalEvidenceKind.OCR_TEXT)

    def test_rejects_empty_text_fail_closed(self) -> None:
        source = observation(raw_text="")
        source.validate()

        with self.assertRaises(EmptyOCRText):
            adapt_ocr_observation_text_reference(
                source,
                reference_id="ocr-text:empty",
                source_id="workflow:synthetic-001",
                locator="artifact:empty",
            )

    def test_rejects_invalid_source_record(self) -> None:
        source = observation(artifact_key="not/a/key")

        with self.assertRaises(ValueError):
            adapt_ocr_observation_text_reference(
                source,
                reference_id="ocr-text:bad",
                source_id="workflow:synthetic-001",
                locator="artifact:bad",
            )

    def test_rejects_wrong_source_type(self) -> None:
        with self.assertRaises(TypeError):
            adapt_ocr_observation_text_reference(  # type: ignore[arg-type]
                object(),
                reference_id="ocr-text:bad-type",
                source_id="workflow:synthetic-001",
                locator="artifact:bad-type",
            )

    def test_rejects_invalid_lineage_values(self) -> None:
        with self.assertRaises(ValueError):
            adapt_ocr_observation_text_reference(
                observation(),
                reference_id="",
                source_id="workflow:synthetic-001",
                locator="artifact:coin-001-front",
            )

    def test_accepts_nonexistent_synthetic_locator_without_io(self) -> None:
        locator = "synthetic://does-not-exist/coin-001-front.txt"
        result = adapt_ocr_observation_text_reference(
            observation(),
            reference_id="ocr-text:synthetic-locator",
            source_id="workflow:synthetic-001",
            locator=locator,
        )
        self.assertEqual(result.reference.locator, locator)

    def test_result_is_immutable(self) -> None:
        result = adapt_ocr_observation_text_reference(
            observation(),
            reference_id="ocr-text:immutable",
            source_id="workflow:synthetic-001",
            locator="artifact:immutable",
        )

        with self.assertRaises(FrozenInstanceError):
            result.source = observation()  # type: ignore[misc]

    def test_manual_inconsistent_result_fails_validation(self) -> None:
        source = observation()
        reference = MultimodalEvidenceReference(
            schema_version=CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
            reference_id="image:wrong-kind",
            kind=MultimodalEvidenceKind.IMAGE_REVERSE,
            source_id="workflow:synthetic-001",
            locator="artifact:coin-001-front",
        )
        result = OCRTextReferenceAdaptation(source=source, reference=reference)

        with self.assertRaises(ValueError):
            result.validate()

    def test_manual_empty_text_result_fails_validation(self) -> None:
        source = observation(raw_text="")
        reference = MultimodalEvidenceReference(
            schema_version=CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
            reference_id="ocr-text:empty",
            kind=MultimodalEvidenceKind.OCR_TEXT,
            source_id="workflow:synthetic-001",
            locator="artifact:empty",
        )
        result = OCRTextReferenceAdaptation(source=source, reference=reference)

        with self.assertRaises(EmptyOCRText):
            result.validate()


if __name__ == "__main__":
    unittest.main()
