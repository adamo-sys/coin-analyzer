"""Focused tests for Sprint 9 Unit 1C OCR metadata extraction stage."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from capture_import.workflow_models import (
    ImportConfiguration,
    ImportRequest,
    StageArtifact,
    StageInput,
)
from capture_import.workflow_ocr_models import (
    OCRFieldCandidate,
    OCRMetadataReport,
    OCRObservation,
)
from capture_import.workflow_ocr_stage import (
    OCR_METADATA_STAGE_ID,
    OCRMetadataExtractionStage,
    _parse_artifact_key,
)
from capture_import.workflow_pipeline import (
    ProcessingPipeline,
    StageContractError,
    StageExecutionError,
)
from inference_telemetry import current_scan_id


def _jpeg() -> bytes:
    output = BytesIO()
    Image.new("RGB", (20, 20), (120, 120, 120)).save(
        output,
        format="JPEG",
        progressive=False,
    )
    return output.getvalue()


def _input(
    workspace: Path,
    artifacts: dict[str, StageArtifact],
) -> StageInput:
    return StageInput(
        request=ImportRequest(
            source=workspace / "source.ca-package",
            collection_id="collection-1",
            configuration=ImportConfiguration(),
        ),
        workspace=workspace,
        artifacts=artifacts,
    )


class FakeProvider:
    provider_id = "fake-ocr"

    def __init__(self) -> None:
        self.calls = []
        self.scan_ids = []

    def analyze(
        self,
        *,
        source_coin_id,
        image_role,
        artifact_key,
        image_bytes,
    ):
        self.scan_ids.append(current_scan_id())
        self.calls.append(
            (
                source_coin_id,
                image_role,
                artifact_key,
                image_bytes,
            )
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
            evidence=("four-digit year pattern",),
        )

        return OCRMetadataReport(
            provider_available=True,
            observations=(observation,),
            candidates=(candidate,),
        )


class OCRArtifactParsingTests(unittest.TestCase):
    def test_supported_keys_parse(self) -> None:
        self.assertEqual(
            _parse_artifact_key("cropped-coin-1-front"),
            ("cropped", "coin-1", "front"),
        )
        self.assertEqual(
            _parse_artifact_key("normalized-coin-1-reverse"),
            ("normalized", "coin-1", "reverse"),
        )

    def test_invalid_keys_are_ignored(self) -> None:
        for value in (
            "prepared-manifest",
            "cropped-coin-1-obverse",
            "cropped-../front",
            "normalized-",
        ):
            with self.subTest(value=value):
                self.assertIsNone(_parse_artifact_key(value))


class OCRMetadataExtractionStageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)

    def _write(self, relative_path: str) -> StageArtifact:
        path = self.workspace / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_jpeg())
        return StageArtifact(relative_path, "image/jpeg")

    def test_cropped_artifact_is_preferred(self) -> None:
        provider = FakeProvider()
        stage_input = _input(
            self.workspace,
            {
                "normalized-coin-1-front": self._write(
                    "normalized/coin-1/front.jpg"
                ),
                "cropped-coin-1-front": self._write(
                    "cropped/coin-1/front.jpg"
                ),
            },
        )

        result = OCRMetadataExtractionStage(
            provider=provider
        ).execute(stage_input)

        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(
            provider.calls[0][2],
            "cropped-coin-1-front",
        )
        self.assertEqual(
            result.metadata["ocr_processed_image_count"],
            1,
        )
        self.assertEqual(
            result.metadata["ocr_reports"][0]["selected_variant"],
            "cropped",
        )

    def test_normalized_artifact_is_valid_fallback(self) -> None:
        provider = FakeProvider()
        stage_input = _input(
            self.workspace,
            {
                "normalized-coin-1-front": self._write(
                    "normalized/coin-1/front.jpg"
                ),
            },
        )

        result = OCRMetadataExtractionStage(
            provider=provider
        ).execute(stage_input)

        self.assertEqual(
            provider.calls[0][2],
            "normalized-coin-1-front",
        )
        self.assertEqual(
            result.metadata["ocr_reports"][0]["selected_variant"],
            "normalized",
        )

    def test_provider_absence_is_advisory_not_failure(self) -> None:
        stage_input = _input(
            self.workspace,
            {
                "cropped-coin-1-front": self._write(
                    "cropped/coin-1/front.jpg"
                ),
            },
        )

        result = OCRMetadataExtractionStage().execute(stage_input)

        self.assertFalse(
            result.metadata["ocr_provider_available"]
        )
        self.assertEqual(
            result.metadata["ocr_processed_image_count"],
            0,
        )
        self.assertEqual(result.metadata["ocr_reports"], [])
        self.assertTrue(result.metadata["ocr_review_required"])

    def test_multiple_artifacts_use_deterministic_order(self) -> None:
        provider = FakeProvider()
        stage_input = _input(
            self.workspace,
            {
                "cropped-coin-b-front": self._write(
                    "cropped/coin-b/front.jpg"
                ),
                "cropped-coin-a-reverse": self._write(
                    "cropped/coin-a/reverse.jpg"
                ),
                "cropped-coin-a-front": self._write(
                    "cropped/coin-a/front.jpg"
                ),
            },
        )

        OCRMetadataExtractionStage(
            provider=provider
        ).execute(stage_input)

        self.assertEqual(
            [
                (call[0], call[1])
                for call in provider.calls
            ],
            [
                ("coin-a", "front"),
                ("coin-a", "reverse"),
                ("coin-b", "front"),
            ],
        )

    def test_all_provider_calls_in_one_scan_share_one_scan_id(self) -> None:
        provider = FakeProvider()
        stage_input = _input(
            self.workspace,
            {
                "cropped-coin-1-front": self._write("cropped/coin-1/front.jpg"),
                "cropped-coin-1-reverse": self._write(
                    "cropped/coin-1/reverse.jpg"
                ),
            },
        )

        OCRMetadataExtractionStage(provider=provider).execute(stage_input)

        self.assertEqual(len(provider.scan_ids), 2)
        self.assertEqual(len(set(provider.scan_ids)), 1)
        self.assertNotEqual(provider.scan_ids[0], "unscoped")
        self.assertEqual(current_scan_id(), "unscoped")

    def test_independent_scan_workspaces_use_different_scan_ids(self) -> None:
        provider = FakeProvider()
        stage = OCRMetadataExtractionStage(provider=provider)
        for name in ("workflow-scan-one", "workflow-scan-two"):
            workspace = self.workspace / name
            workspace.mkdir()
            artifact_path = workspace / "cropped/coin-1/front.jpg"
            artifact_path.parent.mkdir(parents=True)
            artifact_path.write_bytes(_jpeg())
            stage.execute(
                _input(
                    workspace,
                    {
                        "cropped-coin-1-front": StageArtifact(
                            "cropped/coin-1/front.jpg",
                            "image/jpeg",
                        )
                    },
                )
            )

        self.assertEqual(provider.scan_ids, ["scan-one", "scan-two"])
        self.assertEqual(current_scan_id(), "unscoped")

    def test_missing_artifacts_raise_contract_error(self) -> None:
        stage_input = _input(
            self.workspace,
            {
                "prepared-manifest": StageArtifact(
                    "prepared-manifest.json",
                    "application/json",
                )
            },
        )

        with self.assertRaises(StageContractError):
            OCRMetadataExtractionStage().execute(stage_input)

    def test_missing_selected_file_raises_contract_error(self) -> None:
        stage_input = _input(
            self.workspace,
            {
                "cropped-coin-1-front": StageArtifact(
                    "cropped/coin-1/front.jpg",
                    "image/jpeg",
                )
            },
        )

        with self.assertRaises(StageContractError):
            OCRMetadataExtractionStage(
                provider=FakeProvider()
            ).execute(stage_input)

    def test_provider_failure_is_execution_error(self) -> None:
        class BrokenProvider:
            provider_id = "broken"

            def analyze(self, **kwargs):
                raise RuntimeError("OCR failed")

        stage_input = _input(
            self.workspace,
            {
                "cropped-coin-1-front": self._write(
                    "cropped/coin-1/front.jpg"
                ),
            },
        )

        with self.assertRaises(StageExecutionError) as context:
            OCRMetadataExtractionStage(
                provider=BrokenProvider()
            ).execute(stage_input)

        self.assertEqual(
            context.exception.stage_id,
            OCR_METADATA_STAGE_ID,
        )

    def test_invalid_provider_report_raises_contract_error(self) -> None:
        class InvalidProvider:
            provider_id = "invalid"

            def analyze(self, **kwargs):
                return object()

        stage_input = _input(
            self.workspace,
            {
                "cropped-coin-1-front": self._write(
                    "cropped/coin-1/front.jpg"
                ),
            },
        )

        with self.assertRaises(StageContractError):
            OCRMetadataExtractionStage(
                provider=InvalidProvider()
            ).execute(stage_input)

    def test_stage_conforms_to_pipeline_protocol(self) -> None:
        stage = OCRMetadataExtractionStage()
        pipeline = ProcessingPipeline(stages=(stage,))

        self.assertEqual(
            pipeline.stage_ids,
            (OCR_METADATA_STAGE_ID,),
        )


if __name__ == "__main__":
    unittest.main()
