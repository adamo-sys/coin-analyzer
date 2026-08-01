"""Focused tests for explicit desktop OCR review composition."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import importlib
import inspect
import sys
import unittest
from unittest.mock import patch

from tests.frozen_dataclass_compat import (
    assert_frozen_slotted_assignment_rejected,
)

from capture_import.desktop_ocr_review_composition import (
    DesktopOCRReviewComposition,
    create_desktop_ocr_review_composition,
)
from capture_import.workflow_ocr_composition import (
    build_ocr_image_processing_pipeline,
)
from capture_import.workflow_ocr_review_controller import (
    OCRReviewSessionController,
)
from capture_import.workflow_stages import build_image_processing_pipeline


_DEFAULT_STAGE_IDS = (
    "package-validation",
    "manifest-preparation",
    "image-normalization",
    "image-quality-scoring",
    "crop-detection",
    "obverse-reverse-pairing",
    "image-duplicate-detection",
)


class FakeOCRProvider:
    provider_id = "desktop-composition-test"

    def __init__(self) -> None:
        self.calls = 0

    def analyze(self, **_kwargs):
        self.calls += 1
        raise AssertionError("focused composition must not execute OCR")


class DesktopOCRReviewCompositionTests(unittest.TestCase):
    def test_import_does_not_load_optional_legacy_runtime(self) -> None:
        module = importlib.import_module(
            "capture_import.desktop_ocr_review_composition"
        )
        with patch.dict(sys.modules):
            sys.modules.pop(
                "capture_import.workflow_ocr_runtime",
                None,
            )
            sys.modules.pop("legacy_ocr_workflow_provider", None)

            importlib.reload(module)

            self.assertNotIn(
                "capture_import.workflow_ocr_runtime",
                sys.modules,
            )
            self.assertNotIn(
                "legacy_ocr_workflow_provider",
                sys.modules,
            )

    def test_default_pipeline_remains_ocr_and_review_free(self) -> None:
        with patch.object(
            OCRReviewSessionController,
            "__init__",
            side_effect=AssertionError(
                "default composition must not create a review controller"
            ),
        ):
            pipeline = build_image_processing_pipeline()

        self.assertEqual(pipeline.stage_ids, _DEFAULT_STAGE_IDS)
        self.assertNotIn("ocr-metadata-extraction", pipeline.stage_ids)

    def test_default_desktop_import_works_without_optional_runtime(self) -> None:
        with patch.dict(
            sys.modules,
            {
                "capture_import.workflow_ocr_runtime": None,
                "legacy_ocr_workflow_provider": None,
                "pytesseract": None,
            },
        ):
            desktop = importlib.import_module("capture_import.ui")
            pipeline = desktop.build_image_processing_pipeline()

        self.assertEqual(pipeline.stage_ids, _DEFAULT_STAGE_IDS)

    def test_explicit_factory_builds_immutable_composition(self) -> None:
        composition = create_desktop_ocr_review_composition(
            raw_text_resolver=lambda *_args: "CANADA 1967"
        )

        self.assertIsInstance(composition, DesktopOCRReviewComposition)
        self.assertIsInstance(
            composition.review_controller,
            OCRReviewSessionController,
        )
        self.assertIn(
            "ocr-metadata-extraction",
            composition.pipeline.stage_ids,
        )
        with self.assertRaises(FrozenInstanceError):
            composition.pipeline = object()  # type: ignore[misc]
        with assert_frozen_slotted_assignment_rejected(self, composition):
            composition.extra = "no"  # type: ignore[attr-defined]

    def test_repeated_construction_returns_independent_controllers(self) -> None:
        first = create_desktop_ocr_review_composition(
            provider=FakeOCRProvider()
        )
        second = create_desktop_ocr_review_composition(
            provider=FakeOCRProvider()
        )

        self.assertIsNot(
            first.review_controller,
            second.review_controller,
        )
        self.assertIsNot(first.pipeline, second.pipeline)

    def test_injected_provider_uses_sprint_9_provider_composition(self) -> None:
        provider = FakeOCRProvider()

        composition = create_desktop_ocr_review_composition(
            provider=provider
        )

        ocr_stage = next(
            stage
            for stage in composition.pipeline.stages
            if stage.stage_id == "ocr-metadata-extraction"
        )
        self.assertIs(ocr_stage._provider, provider)
        self.assertEqual(provider.calls, 0)

    def test_injected_runtime_factory_is_honored(self) -> None:
        calls: list[dict[str, object]] = []
        provider = FakeOCRProvider()
        resolver = lambda *_args: "CANADA 1967"

        def runtime_factory(**kwargs):
            calls.append(kwargs)
            return build_ocr_image_processing_pipeline(
                provider=provider,
                validator=kwargs["validator"],
                parser=kwargs["parser"],
            )

        composition = create_desktop_ocr_review_composition(
            raw_text_resolver=resolver,
            runtime_factory=runtime_factory,
        )

        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0]["raw_text_resolver"], resolver)
        self.assertIsNone(calls[0]["validator"])
        self.assertIsNone(calls[0]["parser"])
        self.assertIn(
            "ocr-metadata-extraction",
            composition.pipeline.stage_ids,
        )

    def test_injected_controller_factory_is_honored(self) -> None:
        controller = OCRReviewSessionController()
        calls = 0

        def controller_factory() -> OCRReviewSessionController:
            nonlocal calls
            calls += 1
            return controller

        composition = create_desktop_ocr_review_composition(
            provider=FakeOCRProvider(),
            controller_factory=controller_factory,
        )

        self.assertEqual(calls, 1)
        self.assertIs(composition.review_controller, controller)

    def test_missing_optional_runtime_affects_only_opt_in_path(self) -> None:
        with patch.dict(
            sys.modules,
            {"capture_import.workflow_ocr_runtime": None},
        ):
            self.assertEqual(
                build_image_processing_pipeline().stage_ids,
                _DEFAULT_STAGE_IDS,
            )
            with self.assertRaises(ModuleNotFoundError):
                create_desktop_ocr_review_composition()

    def test_actionable_runtime_error_propagates(self) -> None:
        def unavailable_runtime(**_kwargs):
            raise RuntimeError("OCR runtime is not configured")

        with self.assertRaisesRegex(
            RuntimeError,
            "OCR runtime is not configured",
        ):
            create_desktop_ocr_review_composition(
                runtime_factory=unavailable_runtime
            )

    def test_invalid_or_ambiguous_dependencies_are_rejected(self) -> None:
        provider = FakeOCRProvider()

        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            create_desktop_ocr_review_composition(
                provider=provider,
                raw_text_resolver=lambda *_args: "",
            )
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            create_desktop_ocr_review_composition(
                provider=provider,
                runtime_factory=lambda **_kwargs: object(),
            )
        with self.assertRaisesRegex(TypeError, "runtime_factory"):
            create_desktop_ocr_review_composition(  # type: ignore[arg-type]
                runtime_factory=object()
            )
        with self.assertRaisesRegex(TypeError, "controller_factory"):
            create_desktop_ocr_review_composition(  # type: ignore[arg-type]
                provider=provider,
                controller_factory=object(),
            )

    def test_injected_dependencies_are_not_mutated(self) -> None:
        provider = FakeOCRProvider()
        before = dict(provider.__dict__)

        create_desktop_ocr_review_composition(provider=provider)

        self.assertEqual(provider.__dict__, before)

    def test_no_global_state_is_changed(self) -> None:
        default_before = build_image_processing_pipeline().stage_ids

        create_desktop_ocr_review_composition(
            provider=FakeOCRProvider()
        )

        self.assertEqual(
            build_image_processing_pipeline().stage_ids,
            default_before,
        )

    def test_architecture_import_boundary(self) -> None:
        module = importlib.import_module(
            "capture_import.desktop_ocr_review_composition"
        )
        source = inspect.getsource(module)
        tree = ast.parse(source)
        top_level_imports = {
            node.module
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module is not None
        }

        self.assertEqual(
            top_level_imports,
            {
                "__future__",
                "dataclasses",
                "typing",
                "capture_import.manifest",
                "capture_import.package",
                "capture_import.workflow_ocr_composition",
                "capture_import.workflow_ocr_review_controller",
                "capture_import.workflow_ocr_stage",
                "capture_import.workflow_pipeline",
            },
        )
        all_imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module is not None
        }
        prohibited_import_fragments = (
            "tkinter",
            "PyQt",
            "pathlib",
            "persistence",
            "collection",
            "confirmed_observation",
            "legacy_ocr_workflow_provider",
        )
        self.assertFalse(
            any(
                fragment in imported
                for imported in all_imports
                for fragment in prohibited_import_fragments
            )
        )
        prohibited_calls = {
            "open",
            "getenv",
            "putenv",
            "register",
        }
        self.assertFalse(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in prohibited_calls
                for node in ast.walk(tree)
            )
        )


if __name__ == "__main__":
    unittest.main()
