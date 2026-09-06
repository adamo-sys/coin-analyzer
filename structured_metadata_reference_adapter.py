"""Pure structured-metadata reference adapter for Issue #93 Slice C.

This module composes the existing capture-package reference boundary with one
validated structured coin record from the package manifest. It performs no
filesystem access, extraction, persistence, indexing, model calls, collection
mutation, or evidence promotion.
"""

from __future__ import annotations

from dataclasses import dataclass

from capture_import.models import PackageCoin
from capture_package_reference_adapter import CapturePackageReferenceAdaptation
from multimodal_evidence_references import (
    CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
    MultimodalEvidenceKind,
    MultimodalEvidenceReference,
)


class StructuredMetadataRecordNotFound(ValueError):
    """Raised when a requested source coin is absent from the validated package."""


@dataclass(frozen=True, slots=True)
class StructuredMetadataReferenceAdaptation:
    """One validated package coin bound to a structured-metadata reference."""

    package: CapturePackageReferenceAdaptation
    source: PackageCoin
    reference: MultimodalEvidenceReference

    def validate(self) -> None:
        if not isinstance(self.package, CapturePackageReferenceAdaptation):
            raise TypeError("package must be a CapturePackageReferenceAdaptation.")
        self.package.validate()
        self.package.source.manifest.validate()

        if not isinstance(self.source, PackageCoin):
            raise TypeError("source must be a PackageCoin.")
        self.source.validate()

        matching = tuple(
            coin for coin in self.package.source.manifest.coins if coin.id == self.source.id
        )
        if len(matching) != 1 or matching[0] != self.source:
            raise ValueError("source must be the exact package coin identified by its id.")

        if not isinstance(self.reference, MultimodalEvidenceReference):
            raise TypeError("reference must be a MultimodalEvidenceReference.")
        self.reference.validate()

        if self.reference.kind is not MultimodalEvidenceKind.STRUCTURED_METADATA:
            raise ValueError(
                "package coin sources must map to STRUCTURED_METADATA references."
            )
        if self.reference.source_id != self.package.reference.source_id:
            raise ValueError("structured metadata must preserve package source_id.")
        if self.reference.locator != self.source.id:
            raise ValueError("structured metadata locator must preserve coin.id exactly.")
        if self.reference.source_fingerprint != self.package.source.package_sha256:
            raise ValueError(
                "structured metadata must preserve the package SHA-256 fingerprint."
            )


def adapt_structured_metadata_reference(
    package: CapturePackageReferenceAdaptation,
    *,
    source_coin_id: str,
    reference_id: str,
) -> StructuredMetadataReferenceAdaptation:
    """Create one deterministic STRUCTURED_METADATA reference without I/O.

    The package's retrieval source identifier and canonical SHA-256 fingerprint
    are inherited unchanged. The validated package coin ID is preserved as the
    locator. Unsupported or missing source records fail closed.
    """

    if not isinstance(package, CapturePackageReferenceAdaptation):
        raise TypeError("package must be a CapturePackageReferenceAdaptation.")
    package.validate()
    package.source.manifest.validate()

    if not isinstance(source_coin_id, str) or not source_coin_id:
        raise ValueError("source_coin_id must be a non-empty string.")

    matches = tuple(
        coin for coin in package.source.manifest.coins if coin.id == source_coin_id
    )
    if len(matches) != 1:
        raise StructuredMetadataRecordNotFound(
            f"No unique structured metadata record for source coin {source_coin_id!r}."
        )
    source = matches[0]

    reference = MultimodalEvidenceReference(
        schema_version=CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
        reference_id=reference_id,
        kind=MultimodalEvidenceKind.STRUCTURED_METADATA,
        source_id=package.reference.source_id,
        locator=source.id,
        source_fingerprint=package.source.package_sha256,
    )
    reference.validate()

    result = StructuredMetadataReferenceAdaptation(
        package=package,
        source=source,
        reference=reference,
    )
    result.validate()
    return result
