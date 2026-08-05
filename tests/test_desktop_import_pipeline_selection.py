"""Focused tests for desktop import pipeline selection seam."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from capture_import.desktop_import_pipeline_selection import (
    ImportPipelineMode,
    select_import_pipeline,
)
from capture_import.workflow_ocr_composition import (
    build_ocr_image_processing_pipeline,
)
from capture_import.workflow_stages import build_image_processing_pipeline


class _FakeOCRProvider:
    provider_id = "selection-test-provider"

    def analyze(self, **_kwargs):
        raise AssertionError("pipeline selection must not execute OCR")


class DesktopImportPipelineSelectionTests(unittest.TestCase):
    def test_default_mode_is_stage_equivalent_to_existing_default_builder(
        self,
    ) -> None:
        selected = select_import_pipeline(mode=ImportPipelineMode.DEFAULT)
        expected = build_image_processing_pipeline()
        self.assertEqual(selected.stage_ids, expected.stage_ids)
        self.assertEqual(
            tuple(type(stage) for stage in selected.stages),
            tuple(type(stage) for stage in expected.stages),
        )

    def test_default_mode_does_not_require_optional_ocr_runtime(self) -> None:
        with patch.dict(
            sys.modules,
            {
                "capture_import.workflow_ocr_runtime": None,
                "legacy_ocr_workflow_provider": None,
            },
        ):
            selected = select_import_pipeline(mode=ImportPipelineMode.DEFAULT)
        self.assertNotIn("ocr-metadata-extraction", selected.stage_ids)

    def test_ocr_enabled_mode_honors_injected_runtime_factory(self) -> None:
        calls: list[dict[str, object]] = []

        def runtime_factory(**kwargs):
            calls.append(kwargs)
            return build_ocr_image_processing_pipeline(
                provider=_FakeOCRProvider(),
                validator=kwargs["validator"],
                parser=kwargs["parser"],
            )

        selected = select_import_pipeline(
            mode=ImportPipelineMode.OCR_ENABLED,
            runtime_factory=runtime_factory,
        )
        self.assertEqual(len(calls), 1)
        self.assertIn("ocr-metadata-extraction", selected.stage_ids)

    def test_ocr_enabled_mode_without_runtime_factory_propagates_missing_runtime(
        self,
    ) -> None:
        with patch.dict(
            sys.modules,
            {"capture_import.workflow_ocr_runtime": None},
        ):
            with self.assertRaises(ModuleNotFoundError):
                select_import_pipeline(mode=ImportPipelineMode.OCR_ENABLED)

    def test_unsupported_mode_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported import pipeline mode"):
            select_import_pipeline(mode="unsupported-mode")

    def test_non_callable_runtime_factory_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "runtime_factory"):
            select_import_pipeline(
                mode=ImportPipelineMode.OCR_ENABLED,
                runtime_factory=object(),  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
