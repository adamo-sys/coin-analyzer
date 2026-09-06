import dataclasses
import unittest

from capture_import.workflow_ocr_models import OCRObservation
from multimodal_evidence_references import MultimodalEvidenceKind
from ocr_multimodal_role_adapter import (
    OCRMultimodalReferenceAdaptation,
    UnsupportedOCRImageRole,
    adapt_ocr_observation_image_reference,
)


class OCRMultimodalRoleAdapterTests(unittest.TestCase):
    def _observation(
        self,
        *,
        image_role: str = "reverse",
        raw_text: str = "CANADA",
    ) -> OCRObservation:
        return OCRObservation(
            source_coin_id="coin:synthetic:001",
            image_role=image_role,
            artifact_key="artifact-reverse-001",
            provider_id="synthetic-ocr",
            raw_text=raw_text,
            confidence_score=88.0,
        )

    def _adapt(
        self,
        source: OCRObservation | None = None,
        **kwargs: object,
    ) -> OCRMultimodalReferenceAdaptation:
        return adapt_ocr_observation_image_reference(
            source or self._observation(),
            reference_id=str(kwargs.get("reference_id", "ref:synthetic:reverse")),
            source_id=str(kwargs.get("source_id", "source:synthetic:reverse")),
            locator=str(
                kwargs.get(
                    "locator",
                    "synthetic/nonexistent/reverse-image.jpg",
                )
            ),
            source_fingerprint=kwargs.get(
                "source_fingerprint",
                "sha256:synthetic",
            ),  # type: ignore[arg-type]
        )

    def test_reverse_maps_only_to_image_reverse(self) -> None:
        source = self._observation(image_role="reverse")

        result = self._adapt(source)

        self.assertIs(result.source, source)
        self.assertEqual(result.source.image_role, "reverse")
        self.assertIs(
            result.reference.kind,
            MultimodalEvidenceKind.IMAGE_REVERSE,
        )
        result.validate()

    def test_front_fails_closed_without_obverse_inference(self) -> None:
        with self.assertRaisesRegex(
            UnsupportedOCRImageRole,
            "Unsupported OCR image role: 'front'",
        ):
            self._adapt(self._observation(image_role="front"))

    def test_edge_fails_closed_without_detail_inference(self) -> None:
        with self.assertRaisesRegex(
            UnsupportedOCRImageRole,
            "Unsupported OCR image role: 'edge'",
        ):
            self._adapt(self._observation(image_role="edge"))

    def test_invalid_source_record_fails_before_mapping(self) -> None:
        invalid = OCRObservation(
            source_coin_id="coin:synthetic:001",
            image_role="reverse",
            artifact_key="folder/not-an-artifact-key",
            provider_id="synthetic-ocr",
            raw_text="CANADA",
            confidence_score=88.0,
        )

        with self.assertRaisesRegex(
            ValueError,
            "artifact_key must be an identifier",
        ):
            self._adapt(invalid)

    def test_non_observation_source_fails_closed(self) -> None:
        with self.assertRaisesRegex(TypeError, "OCRObservation"):
            adapt_ocr_observation_image_reference(
                object(),  # type: ignore[arg-type]
                reference_id="ref:synthetic",
                source_id="source:synthetic",
                locator="synthetic/reverse.jpg",
            )

    def test_adaptation_is_frozen(self) -> None:
        result = self._adapt()

        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.source = self._observation()  # type: ignore[misc]

    def test_source_record_is_preserved_verbatim(self) -> None:
        source = self._observation(raw_text="  CANADA  ")

        result = self._adapt(source)

        self.assertIs(result.source, source)
        self.assertEqual(result.source.raw_text, "  CANADA  ")
        self.assertEqual(result.source.artifact_key, "artifact-reverse-001")
        self.assertEqual(result.source.provider_id, "synthetic-ocr")

    def test_caller_supplied_lineage_is_preserved(self) -> None:
        result = self._adapt(
            reference_id="ref:caller:001",
            source_id="source:caller:001",
            locator="opaque:artifact:reverse:001",
            source_fingerprint="sha256:caller-supplied",
        )

        self.assertEqual(result.reference.reference_id, "ref:caller:001")
        self.assertEqual(result.reference.source_id, "source:caller:001")
        self.assertEqual(result.reference.locator, "opaque:artifact:reverse:001")
        self.assertEqual(
            result.reference.source_fingerprint,
            "sha256:caller-supplied",
        )

    def test_invalid_reference_lineage_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "reference_id must not be empty"):
            self._adapt(reference_id="   ")

    def test_nonexistent_locator_requires_no_filesystem_access(self) -> None:
        result = self._adapt(
            locator="synthetic/path/that/does/not/exist/reverse.jpg"
        )

        self.assertEqual(
            result.reference.locator,
            "synthetic/path/that/does/not/exist/reverse.jpg",
        )
        result.validate()

    def test_result_rejects_semantically_inconsistent_reference(self) -> None:
        result = self._adapt()
        wrong_reference = dataclasses.replace(
            result.reference,
            kind=MultimodalEvidenceKind.IMAGE_DETAIL,
        )
        inconsistent = OCRMultimodalReferenceAdaptation(
            source=result.source,
            reference=wrong_reference,
        )

        with self.assertRaisesRegex(ValueError, "must map to IMAGE_REVERSE"):
            inconsistent.validate()


if __name__ == "__main__":
    unittest.main()
