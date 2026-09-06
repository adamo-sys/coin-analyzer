"""Fail-closed OCR image-role adapter for Issue #93 Slice C.

This module preserves the validated OCR source record verbatim and maps only
explicitly authorized image-role semantics into typed multimodal references.
It performs no filesystem access, OCR execution, persistence, indexing, model
calls, collection mutation, or evidence promotion.
"""

from __future__ import annotations

from dataclasses import dataclass

from capture_import.workflow_ocr_models import OCRObservation
from multimodal_evidence_references import (
    CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
    MultimodalEvidenceKind,
    MultimodalEvidenceReference,
)


class UnsupportedOCRImageRole(ValueError):
    """Raised when an OCR image role has no explicitly authorized mapping."""


@dataclass(frozen=True, slots=True)
class OCRMultimodalReferenceAdaptation:
    """One validated OCR source record bound to one typed image reference."""

    source: OCRObservation
    reference: MultimodalEvidenceReference

    def validate(self) -> None:
        if not isinstance(self.source, OCRObservation):
            raise TypeError("source must be an OCRObservation.")
        self.source.validate()

        if not isinstance(self.reference, MultimodalEvidenceReference):
            raise TypeError("reference must be a MultimodalEvidenceReference.")
        self.reference.validate()

        if self.source.image_role != "reverse":
            raise UnsupportedOCRImageRole(
                f"Unsupported OCR image role: {self.source.image_role!r}."
            )
        if self.reference.kind is not MultimodalEvidenceKind.IMAGE_REVERSE:
            raise ValueError(
                "reverse OCR sources must map to IMAGE_REVERSE references."
            )


def adapt_ocr_observation_image_reference(
    source: OCRObservation,
    *,
    reference_id: str,
    source_id: str,
    locator: str,
    source_fingerprint: str | None = None,
) -> OCRMultimodalReferenceAdaptation:
    """Map only an explicitly authorized OCR image role to a typed reference.

    Under the approved Option B role policy, only ``reverse`` is authorized.
    ``front`` and ``edge`` fail closed instead of being coerced to obverse or
    detail semantics. Caller-supplied lineage identifiers and locators are
    preserved without normalization or I/O.
    """

    if not isinstance(source, OCRObservation):
        raise TypeError("source must be an OCRObservation.")
    source.validate()

    if source.image_role != "reverse":
        raise UnsupportedOCRImageRole(
            f"Unsupported OCR image role: {source.image_role!r}."
        )

    reference = MultimodalEvidenceReference(
        schema_version=CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
        reference_id=reference_id,
        kind=MultimodalEvidenceKind.IMAGE_REVERSE,
        source_id=source_id,
        locator=locator,
        source_fingerprint=source_fingerprint,
    )
    reference.validate()

    result = OCRMultimodalReferenceAdaptation(
        source=source,
        reference=reference,
    )
    result.validate()
    return result
