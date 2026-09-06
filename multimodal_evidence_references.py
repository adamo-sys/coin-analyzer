"""Immutable contracts for typed multimodal evidence references.

Issue #93 Slice C1 adds deterministic, read-only references that can describe
multimodal evidence lineage without reading files, running OCR, persisting data,
calling models, mutating collection state, or authorizing evidence promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION = "1"

_MAX_ID_CHARS = 16_384
_MAX_SOURCE_ID_CHARS = 16_384
_MAX_FINGERPRINT_CHARS = 4_096
_MAX_LOCATOR_CHARS = 16_384


class MultimodalEvidenceKind(str, Enum):
    IMAGE_OBVERSE = "IMAGE_OBVERSE"
    IMAGE_REVERSE = "IMAGE_REVERSE"
    IMAGE_DETAIL = "IMAGE_DETAIL"
    OCR_TEXT = "OCR_TEXT"
    CAPTURE_PACKAGE = "CAPTURE_PACKAGE"
    STRUCTURED_METADATA = "STRUCTURED_METADATA"


def _text(value: object, name: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value.strip():
        raise ValueError(f"{name} must not be empty.")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds maximum length {maximum}.")
    return value


@dataclass(frozen=True, slots=True)
class MultimodalEvidenceReference:
    """One typed, deterministic pointer to multimodal evidence lineage."""

    schema_version: str
    reference_id: str
    kind: MultimodalEvidenceKind
    source_id: str
    locator: str
    source_fingerprint: str | None = None

    @property
    def identity(self) -> tuple[str, str, str, str, str | None]:
        """Return a deterministic immutable identity tuple for this reference."""

        return (
            self.reference_id,
            self.kind.value,
            self.source_id,
            self.locator,
            self.source_fingerprint,
        )

    def validate(self) -> None:
        if self.schema_version != CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported multimodal reference schema version: "
                f"{self.schema_version!r}."
            )
        _text(self.reference_id, "reference_id", maximum=_MAX_ID_CHARS)
        if not isinstance(self.kind, MultimodalEvidenceKind):
            raise TypeError("kind must be a MultimodalEvidenceKind.")
        _text(self.source_id, "source_id", maximum=_MAX_SOURCE_ID_CHARS)
        _text(self.locator, "locator", maximum=_MAX_LOCATOR_CHARS)
        if self.source_fingerprint is not None:
            _text(
                self.source_fingerprint,
                "source_fingerprint",
                maximum=_MAX_FINGERPRINT_CHARS,
            )
