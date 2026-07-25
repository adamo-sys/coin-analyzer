"""Runtime factory for the explicit legacy OCR workflow.

This module centralizes construction of the legacy OCR provider and the
opt-in OCR processing pipeline. Importing it does not enable OCR anywhere;
callers must explicitly invoke :func:`build_legacy_ocr_pipeline`.

The default desktop image-processing composition remains unchanged.
"""

from __future__ import annotations

from .manifest import CapturePackageManifestParser
from .package import CapturePackageValidator
from .workflow_pipeline import ProcessingPipeline
from .workflow_ocr_composition import build_ocr_image_processing_pipeline

from legacy_ocr_workflow_provider import (
    LegacyOCRWorkflowProvider,
    RawTextResolver,
)


def build_legacy_ocr_pipeline(
    *,
    raw_text_resolver: RawTextResolver | None = None,
    validator: CapturePackageValidator | None = None,
    parser: CapturePackageManifestParser | None = None,
) -> ProcessingPipeline:
    """Build the opt-in image pipeline backed by legacy OCR.

    ``raw_text_resolver`` is an optional deterministic seam for tests,
    offline imports, and future external OCR adapters. When omitted, the
    legacy provider retains its existing optional local OCR behavior.

    This factory performs no workflow execution, persistence, collection
    mutation, or desktop registration.
    """

    provider = LegacyOCRWorkflowProvider(
        raw_text_resolver=raw_text_resolver,
    )

    return build_ocr_image_processing_pipeline(
        provider=provider,
        validator=validator,
        parser=parser,
    )