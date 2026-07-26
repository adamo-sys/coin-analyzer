"""Explicit opt-in composition for desktop advisory OCR review.

Importing this module does not import the optional legacy OCR runtime, alter
the default desktop pipeline, register services, or execute OCR.  The legacy
runtime is imported only when the explicit factory is called without an
injected hardened OCR provider or runtime factory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from capture_import.manifest import CapturePackageManifestParser
from capture_import.package import CapturePackageValidator
from capture_import.workflow_ocr_composition import (
    build_ocr_image_processing_pipeline,
)
from capture_import.workflow_ocr_review_controller import (
    OCRReviewSessionController,
)
from capture_import.workflow_ocr_stage import OCRMetadataProvider
from capture_import.workflow_pipeline import ProcessingPipeline


RawTextResolver = Callable[[str, str, str, bytes], str | None]
OCRPipelineFactory = Callable[..., ProcessingPipeline]
OCRReviewControllerFactory = Callable[[], OCRReviewSessionController]


@dataclass(frozen=True, slots=True)
class DesktopOCRReviewComposition:
    """Immutable opt-in desktop services for advisory OCR review."""

    pipeline: ProcessingPipeline
    review_controller: OCRReviewSessionController

    def __post_init__(self) -> None:
        if not isinstance(self.pipeline, ProcessingPipeline):
            raise TypeError("pipeline must be a ProcessingPipeline.")
        if "ocr-metadata-extraction" not in self.pipeline.stage_ids:
            raise ValueError(
                "pipeline must contain the advisory OCR metadata stage."
            )
        if not isinstance(
            self.review_controller,
            OCRReviewSessionController,
        ):
            raise TypeError(
                "review_controller must be an "
                "OCRReviewSessionController."
            )


def create_desktop_ocr_review_composition(
    *,
    provider: OCRMetadataProvider | None = None,
    raw_text_resolver: RawTextResolver | None = None,
    validator: CapturePackageValidator | None = None,
    parser: CapturePackageManifestParser | None = None,
    runtime_factory: OCRPipelineFactory | None = None,
    controller_factory: OCRReviewControllerFactory = (
        OCRReviewSessionController
    ),
) -> DesktopOCRReviewComposition:
    """Build the deliberately requested OCR pipeline and review controller.

    An injected hardened ``provider`` uses Sprint 9's provider-based pipeline
    composition directly.  Otherwise the existing Sprint 9 legacy runtime
    factory is loaded lazily and receives the optional deterministic raw-text
    resolver.

    Construction performs no pipeline execution, review execution,
    persistence, collection mutation, or desktop registration.
    """

    if not callable(controller_factory):
        raise TypeError("controller_factory must be callable.")
    if runtime_factory is not None and not callable(runtime_factory):
        raise TypeError("runtime_factory must be callable or None.")
    if provider is not None and raw_text_resolver is not None:
        raise ValueError(
            "provider and raw_text_resolver are mutually exclusive."
        )
    if provider is not None and runtime_factory is not None:
        raise ValueError(
            "provider and runtime_factory are mutually exclusive."
        )

    if provider is not None:
        pipeline = build_ocr_image_processing_pipeline(
            provider=provider,
            validator=validator,
            parser=parser,
        )
    else:
        if runtime_factory is None:
            from capture_import.workflow_ocr_runtime import (
                build_legacy_ocr_pipeline,
            )

            selected_runtime_factory = build_legacy_ocr_pipeline
        else:
            selected_runtime_factory = runtime_factory

        pipeline = selected_runtime_factory(
            raw_text_resolver=raw_text_resolver,
            validator=validator,
            parser=parser,
        )

    return DesktopOCRReviewComposition(
        pipeline=pipeline,
        review_controller=controller_factory(),
    )
