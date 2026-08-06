"""Pipeline selection seam for desktop capture-package import.

This module selects a processing pipeline based on explicit import mode.
It does not execute workflows, own persistence, instantiate review
controllers, or mutate collection state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .desktop_ocr_review_composition import (
    DesktopOCRReviewComposition,
    create_desktop_ocr_review_composition,
)
from .manifest import CapturePackageManifestParser
from .package import CapturePackageValidator
from .workflow_pipeline import ProcessingPipeline
from .workflow_stages import build_image_processing_pipeline

OCRPipelineFactory = Callable[..., ProcessingPipeline]


class ImportPipelineMode(str, Enum):
    """Explicit desktop import pipeline modes."""

    DEFAULT = "default"
    OCR_ENABLED = "ocr-enabled"


@dataclass(frozen=True, slots=True)
class DesktopImportPipelineSelection:
    """Immutable internal selection result for one desktop import mode.

    Not exported from ``capture_import``; internal callers may access
    ``pipeline`` and ``ocr_composition`` directly.
    """

    pipeline: ProcessingPipeline
    ocr_composition: DesktopOCRReviewComposition | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.pipeline, ProcessingPipeline):
            raise TypeError("pipeline must be a ProcessingPipeline.")
        if self.ocr_composition is not None and not isinstance(
            self.ocr_composition, DesktopOCRReviewComposition
        ):
            raise TypeError(
                "ocr_composition must be a DesktopOCRReviewComposition or None."
            )


def select_import_pipeline(
    *,
    mode: ImportPipelineMode | str = ImportPipelineMode.DEFAULT,
    validator: CapturePackageValidator | None = None,
    parser: CapturePackageManifestParser | None = None,
    runtime_factory: OCRPipelineFactory | None = None,
) -> DesktopImportPipelineSelection:
    """Return the selected desktop import pipeline for one explicit mode."""

    selected_mode = _coerce_mode(mode)
    if runtime_factory is not None and not callable(runtime_factory):
        raise TypeError("runtime_factory must be callable or None.")

    if selected_mode is ImportPipelineMode.DEFAULT:
        return DesktopImportPipelineSelection(
            pipeline=build_image_processing_pipeline(
                validator=validator,
                parser=parser,
            ),
            ocr_composition=None,
        )

    composition = create_desktop_ocr_review_composition(
        runtime_factory=runtime_factory,
        validator=validator,
        parser=parser,
    )
    return DesktopImportPipelineSelection(
        pipeline=composition.pipeline,
        ocr_composition=composition,
    )


def _coerce_mode(mode: ImportPipelineMode | str) -> ImportPipelineMode:
    if isinstance(mode, ImportPipelineMode):
        return mode
    if not isinstance(mode, str):
        raise TypeError("mode must be ImportPipelineMode or str.")
    try:
        return ImportPipelineMode(mode)
    except ValueError as error:
        raise ValueError(f"unsupported import pipeline mode: {mode!r}.") from error
