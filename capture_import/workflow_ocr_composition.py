"""Explicit opt-in OCR processing-pipeline composition.

This module is separate from ``workflow_stages`` so the established
reference-stage durability boundary and runtime-import allowlist remain
unchanged.

Nothing in this module enables OCR in the default desktop workflow.
"""

from __future__ import annotations

from .manifest import CapturePackageManifestParser
from .package import CapturePackageValidator
from .workflow_crop_detection import CropDetectionStage
from .workflow_image_duplicates import ImageDuplicateDetectionStage
from .workflow_image_normalization import ImageNormalizationStage
from .workflow_image_quality import ImageQualityScoringStage
from .workflow_obverse_reverse_pairing import ObverseReversePairingStage
from .workflow_ocr_stage import (
    OCRMetadataExtractionStage,
    OCRMetadataProvider,
)
from .workflow_pipeline import ProcessingPipeline
from .workflow_stages import (
    ManifestPreparationStage,
    PackageValidationStage,
)


def build_ocr_image_processing_pipeline(
    *,
    provider: OCRMetadataProvider,
    validator: CapturePackageValidator | None = None,
    parser: CapturePackageManifestParser | None = None,
) -> ProcessingPipeline:
    """Build the explicit opt-in image pipeline with advisory OCR.

    OCR runs after crop detection so cropped artifacts are preferred while
    normalized-image fallback remains available.
    """

    if provider is None:
        raise ValueError("provider is required for the opt-in OCR pipeline.")

    return ProcessingPipeline(
        stages=(
            PackageValidationStage(validator=validator),
            ManifestPreparationStage(parser=parser),
            ImageNormalizationStage(),
            ImageQualityScoringStage(),
            CropDetectionStage(),
            OCRMetadataExtractionStage(provider=provider),
            ObverseReversePairingStage(),
            ImageDuplicateDetectionStage(),
        )
    )