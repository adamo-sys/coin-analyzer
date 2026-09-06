"""Pure capture-package fingerprint adapter for Issue #93 Slice C.

This module converts canonical facts from an already-validated capture package
into one typed multimodal reference. It performs no filesystem access,
extraction, persistence, indexing, model calls, collection mutation, or evidence
promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from capture_import.package import ValidatedCapturePackage
from multimodal_evidence_references import (
    CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
    MultimodalEvidenceKind,
    MultimodalEvidenceReference,
)


_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class CapturePackageReferenceAdaptation:
    """One validated capture package bound to its canonical fingerprint reference."""

    source: ValidatedCapturePackage
    reference: MultimodalEvidenceReference

    def validate(self) -> None:
        if not isinstance(self.source, ValidatedCapturePackage):
            raise TypeError("source must be a ValidatedCapturePackage.")
        _validate_source_identity(self.source)

        if not isinstance(self.reference, MultimodalEvidenceReference):
            raise TypeError("reference must be a MultimodalEvidenceReference.")
        self.reference.validate()

        if self.reference.kind is not MultimodalEvidenceKind.CAPTURE_PACKAGE:
            raise ValueError("capture-package sources must map to CAPTURE_PACKAGE references.")
        if self.reference.locator != self.source.package_basename:
            raise ValueError("capture-package locator must preserve package_basename exactly.")
        if self.reference.source_fingerprint != self.source.package_sha256:
            raise ValueError("capture-package reference must preserve package_sha256 exactly.")


def _validate_source_identity(source: ValidatedCapturePackage) -> None:
    """Validate only the canonical identity facts consumed by this adapter."""

    basename = source.package_basename
    if not isinstance(basename, str) or not basename:
        raise ValueError("package_basename must be a non-empty string.")
    if "/" in basename or "\\" in basename or basename in {".", ".."}:
        raise ValueError("package_basename must remain a filename basename.")

    digest = source.package_sha256
    if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
        raise ValueError("package_sha256 must be a lowercase SHA-256 digest.")

    length = source.package_byte_length
    if isinstance(length, bool) or not isinstance(length, int) or length < 1:
        raise ValueError("package_byte_length must be a positive integer.")


def adapt_capture_package_reference(
    source: ValidatedCapturePackage,
    *,
    reference_id: str,
    source_id: str,
) -> CapturePackageReferenceAdaptation:
    """Create one deterministic CAPTURE_PACKAGE reference without I/O.

    The validated package basename is preserved as the locator and the canonical
    package SHA-256 is preserved as the source fingerprint. Callers supply only
    the retrieval-layer reference and source identifiers; they cannot substitute
    a different package fingerprint or locator.
    """

    if not isinstance(source, ValidatedCapturePackage):
        raise TypeError("source must be a ValidatedCapturePackage.")
    _validate_source_identity(source)

    reference = MultimodalEvidenceReference(
        schema_version=CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
        reference_id=reference_id,
        kind=MultimodalEvidenceKind.CAPTURE_PACKAGE,
        source_id=source_id,
        locator=source.package_basename,
        source_fingerprint=source.package_sha256,
    )
    reference.validate()

    result = CapturePackageReferenceAdaptation(source=source, reference=reference)
    result.validate()
    return result
