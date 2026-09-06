"""Pure OCR-text adapter for Issue #93 Slice C.

This module binds an already-validated OCR observation containing non-empty text
into one typed OCR_TEXT multimodal evidence reference. It preserves the source
observation verbatim and performs no filesystem access, OCR execution,
persistence, indexing, model calls, collection mutation, or evidence promotion.
"""

from __future__ import annotations

from dataclasses import dataclass

from capture_import.workflow_ocr_models import OCRObservation
from multimodal_evidence_references import (
    CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
    MultimodalEvidenceKind,
    MultimodalEvidenceReference,
)


class EmptyOCRText(ValueError):
    """Raised when a validated OCR observation contains no retrievable text."""


@dataclass(frozen=True, slots=True)
class OCRTextReferenceAdaptation:
    """One validated OCR observation bound to one typed OCR-text reference."""

    source: OCRObservation
    reference: MultimodalEvidenceReference

    def validate(self) -> None:
        if not isinstance(self.source, OCRObservation):
            raise TypeError("source must be an OCRObservation.")
        self.source.validate()

        if not self.source.raw_text:
            raise EmptyOCRText("OCR observations without text cannot map to OCR_TEXT.")

        if not isinstance(self.reference, MultimodalEvidenceReference):
            raise TypeError("reference must be a MultimodalEvidenceReference.")
        self.reference.validate()

        if self.reference.kind is not MultimodalEvidenceKind.OCR_TEXT:
            raise ValueError("OCR text sources must map to OCR_TEXT references.")


def adapt_ocr_observation_text_reference(
    source: OCRObservation,
    *,
    reference_id: str,
    source_id: str,
    locator: str,
    source_fingerprint: str | None = None,
) -> OCRTextReferenceAdaptation:
    """Bind non-empty validated OCR text to one typed multimodal reference.

    The caller supplies lineage identifiers, locator, and optional fingerprint;
    this adapter preserves them without normalization or I/O. Image-role
    semantics are deliberately not translated because OCR text can remain
    traceable to its original ``front``, ``reverse``, or ``edge`` source record
    without manufacturing an image classification.
    """

    if not isinstance(source, OCRObservation):
        raise TypeError("source must be an OCRObservation.")
    source.validate()

    if not source.raw_text:
        raise EmptyOCRText("OCR observations without text cannot map to OCR_TEXT.")

    reference = MultimodalEvidenceReference(
        schema_version=CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
        reference_id=reference_id,
        kind=MultimodalEvidenceKind.OCR_TEXT,
        source_id=source_id,
        locator=locator,
        source_fingerprint=source_fingerprint,
    )
    reference.validate()

    result = OCRTextReferenceAdaptation(source=source, reference=reference)
    result.validate()
    return result
