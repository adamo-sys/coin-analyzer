"""Pipeline selection seam for desktop capture-package import.

This module selects a processing pipeline based on explicit import mode.
It does not execute workflows, own persistence, instantiate review
controllers, or mutate collection state.
"""

from __future__ import annotations

from enum import Enum
from typing import Callable

from .manifest import CapturePackageManifestParser
from .package import CapturePackageValidator
from .workflow_pipeline import ProcessingPipeline
from .workflow_stages import build_image_processing_pipeline

OCRPipelineFactory = Callable[..., ProcessingPipeline]


class ImportPipelineMode(str, Enum):
    """Explicit desktop import pipeline modes."""

    DEFAULT = "default"
    OCR_ENABLED = "ocr-enabled"


def select_import_pipeline(
    *,
    mode: ImportPipelineMode | str = ImportPipelineMode.DEFAULT,
    validator: CapturePackageValidator | None = None,
    parser: CapturePackageManifestParser | None = None,
    runtime_factory: OCRPipelineFactory | None = None,
) -> ProcessingPipeline:
    """Return the selected desktop import pipeline for one explicit mode."""

    selected_mode = _coerce_mode(mode)
    if runtime_factory is not None and not callable(runtime_factory):
        raise TypeError("runtime_factory must be callable or None.")

    if selected_mode is ImportPipelineMode.DEFAULT:
        return build_image_processing_pipeline(
            validator=validator,
            parser=parser,
        )

    selected_factory = runtime_factory
    if selected_factory is None:
        from .workflow_ocr_runtime import build_legacy_ocr_pipeline

        selected_factory = build_legacy_ocr_pipeline

    return selected_factory(
        validator=validator,
        parser=parser,
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
