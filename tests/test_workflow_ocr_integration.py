"""Sprint 9 Unit 1E opt-in OCR pipeline integration tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from capture_import.workflow_execution import ImportWorkflow
from capture_import.workflow_models import ImportConfiguration, ImportRequest
from capture_import.workflow_ocr_models import (
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRObservation,
    OCRReviewStatus,
)
from capture_import.workflow_ocr_composition import (
    build_ocr_image_processing_pipeline,
)
from capture_import.workflow_stages import (
    build_image_processing_pipeline,
)
from tests.capture_package_fixtures import package_bytes


class _FakeOCRProvider:
    provider_id = "integration-fake-ocr"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def analyze(
        self,
        *,
        source_coin_id: str,
        image_role: str,
        artifact_key: str,
        image_bytes: bytes,
    ) -> OCRMetadataReport:
        self.calls.append(
            {
                "source_coin_id": source_coin_id,
                "image_role": image_role,
                "artifact_key": artifact_key,
                "image_bytes": image_bytes,
            }
        )

        observation = OCRObservation(
            source_coin_id=source_coin_id,
            image_role=image_role,
            artifact_key=artifact_key,
            provider_id=self.provider_id,
            raw_text="CANADA 1967",
            confidence_score=80.0,
        )
        candidate = OCRFieldCandidate(
            source_coin_id=source_coin_id,
            image_role=image_role,
            artifact_key=artifact_key,
            provider_id=self.provider_id,
            field_name="year",
            raw_text="1967",
            normalized_value="1967",
            confidence_score=80.0,
            evidence=("integration fixture",),
            review_status=OCRReviewStatus.REVIEW_REQUIRED,
        )

        report = OCRMetadataReport(
            provider_available=True,
            observations=(observation,),
            candidates=(candidate,),
            review_status=OCRReviewStatus.REVIEW_REQUIRED,
        )
        report.validate()
        return report


class OptInOCRPipelineCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)

        self.root = Path(self.temporary.name)
        self.source = self.root / "fixture.ca-package"
        self.source.write_bytes(package_bytes())

        self.request = ImportRequest(
            source=self.source,
            collection_id="collection-1",
            configuration=ImportConfiguration(),
        )

    def _workspace(self, name: str) -> Path:
        workspace = self.root / name
        workspace.mkdir()
        return workspace

    def test_default_image_pipeline_remains_ocr_free(self) -> None:
        self.assertEqual(
            build_image_processing_pipeline().stage_ids,
            (
                "package-validation",
                "manifest-preparation",
                "image-normalization",
                "image-quality-scoring",
                "crop-detection",
                "obverse-reverse-pairing",
                "image-duplicate-detection",
            ),
        )
        self.assertNotIn(
            "ocr-metadata-extraction",
            build_image_processing_pipeline().stage_ids,
        )

    def test_opt_in_pipeline_has_fixed_ocr_stage_order(self) -> None:
        pipeline = build_ocr_image_processing_pipeline(
            provider=_FakeOCRProvider()
        )

        self.assertEqual(
            pipeline.stage_ids,
            (
                "package-validation",
                "manifest-preparation",
                "image-normalization",
                "image-quality-scoring",
                "crop-detection",
                "ocr-metadata-extraction",
                "obverse-reverse-pairing",
                "image-duplicate-detection",
            ),
        )

    def test_opt_in_pipeline_requires_explicit_provider(self) -> None:
        with self.assertRaisesRegex(ValueError, "provider"):
            build_ocr_image_processing_pipeline(
                provider=None,  # type: ignore[arg-type]
            )

    def test_end_to_end_pipeline_emits_advisory_ocr_metadata(self) -> None:
        provider = _FakeOCRProvider()

        outcome = ImportWorkflow(
            build_ocr_image_processing_pipeline(provider=provider)
        ).execute(
            self.request,
            self._workspace("ocr-workspace"),
        )

        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(
            [
                (
                    call["source_coin_id"],
                    call["image_role"],
                    call["artifact_key"],
                )
                for call in provider.calls
            ],
            [
                ("coin-1", "front", "cropped-coin-1-front"),
                ("coin-1", "reverse", "cropped-coin-1-reverse"),
            ],
        )

        self.assertTrue(outcome.metadata["ocr_provider_available"])
        self.assertEqual(
            outcome.metadata["ocr_provider_id"],
            "integration-fake-ocr",
        )
        self.assertEqual(
            outcome.metadata["ocr_processed_image_count"],
            2,
        )
        self.assertTrue(outcome.metadata["ocr_review_required"])

        reports = outcome.metadata["ocr_reports"]
        self.assertEqual(len(reports), 2)
        self.assertTrue(
            all(report["selected_variant"] == "cropped" for report in reports)
        )
        self.assertTrue(
            all(
                report["review_status"] == "REVIEW_REQUIRED"
                for report in reports
            )
        )
        self.assertTrue(
            all(
                report["candidates"][0]["field_name"] == "year"
                for report in reports
            )
        )

    def test_ocr_metadata_does_not_change_processed_artifact_inventory(self) -> None:
        provider = _FakeOCRProvider()

        outcome = ImportWorkflow(
            build_ocr_image_processing_pipeline(provider=provider)
        ).execute(
            self.request,
            self._workspace("inventory-workspace"),
        )

        self.assertEqual(
            {
                key
                for key in outcome.artifacts
                if key.startswith("normalized-")
            },
            {
                "normalized-coin-1-front",
                "normalized-coin-1-reverse",
            },
        )
        self.assertEqual(
            {
                key
                for key in outcome.artifacts
                if key.startswith("cropped-")
            },
            {
                "cropped-coin-1-front",
                "cropped-coin-1-reverse",
            },
        )
        self.assertFalse(
            any(key.startswith("ocr-") for key in outcome.artifacts)
        )


if __name__ == "__main__":
    unittest.main()