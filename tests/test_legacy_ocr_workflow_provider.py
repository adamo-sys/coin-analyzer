"""Focused tests for Sprint 9 Unit 1D legacy OCR provider bridge."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from capture_import.workflow_ocr_models import (
    OCRMetadataReport,
    OCRReviewStatus,
)
from capture_import.workflow_pipeline import StageContractError
from legacy_ocr_workflow_provider import LegacyOCRWorkflowProvider
from ocr_experiment import OCRExperiment
from ocr_validation import OCRValidationEngine
from ocr_workflow_adapter import OCRWorkflowAdapter


def _jpeg() -> bytes:
    output = BytesIO()
    Image.new("RGB", (24, 24), (100, 100, 100)).save(
        output,
        format="JPEG",
        progressive=False,
    )
    return output.getvalue()


class _ExperimentSpy(OCRExperiment):
    def __init__(self) -> None:
        super().__init__()
        self.calls = []

    def run(
        self,
        image_path="",
        raw_text=None,
        engine="pytesseract",
    ):
        self.calls.append(
            {
                "image_path": image_path,
                "raw_text": raw_text,
                "engine": engine,
            }
        )
        return super().run(
            image_path=image_path,
            raw_text=raw_text,
            engine=engine,
        )


class _ValidationSpy(OCRValidationEngine):
    def __init__(self) -> None:
        super().__init__()
        self.calls = []

    def validate(
        self,
        ocr_result=None,
        suggestion_report=None,
    ):
        self.calls.append(
            {
                "ocr_result": ocr_result,
                "suggestion_report": suggestion_report,
            }
        )
        return super().validate(
            ocr_result=ocr_result,
            suggestion_report=suggestion_report,
        )


class _AdapterSpy(OCRWorkflowAdapter):
    def __init__(self) -> None:
        self.calls = []

    def adapt(self, **kwargs):
        self.calls.append(kwargs)
        return super().adapt(**kwargs)


class LegacyOCRWorkflowProviderTests(unittest.TestCase):
    def test_provider_id_is_stable(self) -> None:
        provider = LegacyOCRWorkflowProvider()
        self.assertEqual(provider.provider_id, "legacy-ocr")

    def test_local_runtime_uses_one_fixed_sparse_text_psm(self) -> None:
        with patch(
            "pytesseract.image_to_string",
            return_value="CANADA\n1967\f25 CENTS\n",
        ) as image_to_string:
            report = LegacyOCRWorkflowProvider().analyze(
                source_coin_id="coin-1",
                image_role="front",
                artifact_key="cropped-coin-1-front",
                image_bytes=_jpeg(),
            )

        image_to_string.assert_called_once()
        ocr_input = image_to_string.call_args.args[0]
        self.assertEqual(ocr_input.size, (24, 24))
        self.assertEqual(ocr_input.mode, "RGB")
        self.assertEqual(
            image_to_string.call_args.kwargs,
            {"config": "--psm 11"},
        )
        self.assertTrue(report.provider_available)
        self.assertEqual(
            report.observations[0].raw_text,
            "CANADA 1967 25 CENTS",
        )
        self.assertIn(
            ("year", "1967"),
            {
                (candidate.field_name, candidate.normalized_value)
                for candidate in report.candidates
            },
        )

    def test_raw_text_path_avoids_local_ocr_runtime(self) -> None:
        experiment = _ExperimentSpy()
        validation = _ValidationSpy()
        adapter = _AdapterSpy()

        provider = LegacyOCRWorkflowProvider(
            experiment=experiment,
            validation_engine=validation,
            adapter=adapter,
            raw_text_resolver=lambda *_args: (
                "CANADA 1967 25 CENTS ICCS ABC123"
            ),
        )

        report = provider.analyze(
            source_coin_id="coin-1",
            image_role="front",
            artifact_key="cropped-coin-1-front",
            image_bytes=_jpeg(),
        )

        self.assertIsInstance(report, OCRMetadataReport)
        self.assertTrue(report.provider_available)
        self.assertIs(
            report.review_status,
            OCRReviewStatus.REVIEW_REQUIRED,
        )

        self.assertEqual(len(experiment.calls), 1)
        self.assertEqual(
            experiment.calls[0]["raw_text"],
            "CANADA 1967 25 CENTS ICCS ABC123",
        )
        self.assertEqual(
            experiment.calls[0]["image_path"],
            "",
        )
        self.assertEqual(
            experiment.calls[0]["engine"],
            "legacy-ocr",
        )

        self.assertEqual(len(validation.calls), 1)
        self.assertIsNotNone(
            validation.calls[0]["suggestion_report"]
        )

        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(
            adapter.calls[0]["source_coin_id"],
            "coin-1",
        )
        self.assertEqual(
            adapter.calls[0]["image_role"],
            "front",
        )
        self.assertEqual(
            adapter.calls[0]["artifact_key"],
            "cropped-coin-1-front",
        )

    def test_raw_text_candidates_are_review_only(self) -> None:
        provider = LegacyOCRWorkflowProvider(
            raw_text_resolver=lambda *_args: (
                "CANADA 1967 25 CENTS"
            )
        )

        report = provider.analyze(
            source_coin_id="coin-1",
            image_role="front",
            artifact_key="cropped-coin-1-front",
            image_bytes=_jpeg(),
        )

        fields = {
            (candidate.field_name, candidate.normalized_value)
            for candidate in report.candidates
        }

        self.assertIn(("year", "1967"), fields)
        self.assertIn(("country", "Canada"), fields)
        self.assertTrue(
            all(
                candidate.review_status
                is OCRReviewStatus.REVIEW_REQUIRED
                for candidate in report.candidates
            )
        )

    def test_multiple_years_remain_unresolved_conflict(self) -> None:
        provider = LegacyOCRWorkflowProvider(
            raw_text_resolver=lambda *_args: (
                "CANADA 1961 1967 25 CENTS"
            )
        )

        report = provider.analyze(
            source_coin_id="coin-1",
            image_role="front",
            artifact_key="cropped-coin-1-front",
            image_bytes=_jpeg(),
        )

        self.assertIs(report.review_status, OCRReviewStatus.CONFLICT)
        self.assertEqual(len(report.conflicts), 1)
        self.assertEqual(
            report.conflicts[0].field_name,
            "year",
        )
        self.assertEqual(
            report.conflicts[0].candidate_values,
            ("1961", "1967"),
        )

    def test_resolver_receives_exact_identity_and_bytes(self) -> None:
        calls = []
        payload = _jpeg()

        def resolver(
            source_coin_id,
            image_role,
            artifact_key,
            image_bytes,
        ):
            calls.append(
                (
                    source_coin_id,
                    image_role,
                    artifact_key,
                    image_bytes,
                )
            )
            return "CANADA 1967"

        provider = LegacyOCRWorkflowProvider(
            raw_text_resolver=resolver
        )

        provider.analyze(
            source_coin_id="coin-9",
            image_role="reverse",
            artifact_key="normalized-coin-9-reverse",
            image_bytes=payload,
        )

        self.assertEqual(
            calls,
            [
                (
                    "coin-9",
                    "reverse",
                    "normalized-coin-9-reverse",
                    payload,
                )
            ],
        )

    def test_none_resolver_uses_temporary_image_and_cleans_it(self) -> None:
        experiment = _ExperimentSpy()

        provider = LegacyOCRWorkflowProvider(
            experiment=experiment,
            raw_text_resolver=lambda *_args: None,
        )

        provider.analyze(
            source_coin_id="coin-1",
            image_role="front",
            artifact_key="cropped-coin-1-front",
            image_bytes=_jpeg(),
        )

        self.assertEqual(len(experiment.calls), 1)
        temporary_name = experiment.calls[0]["image_path"]
        self.assertTrue(temporary_name)
        self.assertEqual(
            experiment.calls[0]["raw_text"],
            None,
        )
        self.assertEqual(
            experiment.calls[0]["engine"],
            "legacy-ocr",
        )
        self.assertFalse(Path(temporary_name).exists())

    def test_default_provider_is_safe_without_tesseract(self) -> None:
        provider = LegacyOCRWorkflowProvider(
            raw_text_resolver=lambda *_args: ""
        )

        report = provider.analyze(
            source_coin_id="coin-1",
            image_role="front",
            artifact_key="cropped-coin-1-front",
            image_bytes=_jpeg(),
        )

        self.assertTrue(report.provider_available)
        self.assertEqual(report.candidates, ())
        self.assertIs(
            report.review_status,
            OCRReviewStatus.REVIEW_REQUIRED,
        )

    def test_invalid_jpeg_is_rejected(self) -> None:
        provider = LegacyOCRWorkflowProvider(
            raw_text_resolver=lambda *_args: "CANADA 1967"
        )

        with self.assertRaises(StageContractError):
            provider.analyze(
                source_coin_id="coin-1",
                image_role="front",
                artifact_key="cropped-coin-1-front",
                image_bytes=b"not-a-jpeg",
            )

    def test_empty_image_bytes_are_rejected(self) -> None:
        provider = LegacyOCRWorkflowProvider(
            raw_text_resolver=lambda *_args: "CANADA 1967"
        )

        with self.assertRaises(StageContractError):
            provider.analyze(
                source_coin_id="coin-1",
                image_role="front",
                artifact_key="cropped-coin-1-front",
                image_bytes=b"",
            )

    def test_non_string_resolver_result_is_rejected(self) -> None:
        provider = LegacyOCRWorkflowProvider(
            raw_text_resolver=lambda *_args: 123
        )

        with self.assertRaises(StageContractError):
            provider.analyze(
                source_coin_id="coin-1",
                image_role="front",
                artifact_key="cropped-coin-1-front",
                image_bytes=_jpeg(),
            )

    def test_output_is_deterministic(self) -> None:
        provider = LegacyOCRWorkflowProvider(
            raw_text_resolver=lambda *_args: (
                "CANADA 1967 25 CENTS"
            )
        )

        first = provider.analyze(
            source_coin_id="coin-1",
            image_role="front",
            artifact_key="cropped-coin-1-front",
            image_bytes=_jpeg(),
        )
        second = provider.analyze(
            source_coin_id="coin-1",
            image_role="front",
            artifact_key="cropped-coin-1-front",
            image_bytes=_jpeg(),
        )

        self.assertEqual(first, second)
        self.assertEqual(first.to_dict(), second.to_dict())


if __name__ == "__main__":
    unittest.main()
