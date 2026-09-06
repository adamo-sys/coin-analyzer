"""Immutable, read-only contracts for bounded retrieval evidence.

These contracts define the Issue #93 Slice A trust boundary. They carry
retrieval requests, evidence, provenance, ranked results, and explicit
validation outcomes. They do not search, persist, mutate collection state,
call models, or authorize promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


CURRENT_RETRIEVAL_SCHEMA_VERSION = "1"

_MAX_ID_CHARS = 16_384
_MAX_TEXT_CHARS = 65_536
_MAX_SOURCE_TYPE_CHARS = 128
_MAX_FINGERPRINT_CHARS = 4_096
_MAX_REFERENCE_CHARS = 4_096
_MAX_REFERENCES = 64
_MAX_METADATA_ITEMS = 128
_MAX_METADATA_KEY_CHARS = 256
_MAX_METADATA_VALUE_CHARS = 4_096
_MAX_SOURCE_TYPES = 64
_MAX_RESULTS = 100
_MAX_CANDIDATES = 100_000
_MAX_REASON_CODES = 32
_MAX_REASON_CODE_CHARS = 128
_MAX_RATIONALE_CHARS = 4_096


class RetrievalValidationDecision(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


def _text(value: object, name: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value.strip():
        raise ValueError(f"{name} must not be empty.")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds maximum length {maximum}.")
    return value


def _sorted_unique_strings(values: object, name: str, *, maximum_items: int, maximum_chars: int) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be a tuple.")
    if len(values) > maximum_items:
        raise ValueError(f"{name} contains too many items.")
    for index, value in enumerate(values):
        _text(value, f"{name}[{index}]", maximum=maximum_chars)
    if values != tuple(sorted(values)):
        raise ValueError(f"{name} must be in deterministic sorted order.")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must not contain duplicates.")
    return values


def _metadata(values: object, name: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be a tuple.")
    if len(values) > _MAX_METADATA_ITEMS:
        raise ValueError(f"{name} contains too many items.")
    keys: list[str] = []
    for index, item in enumerate(values):
        if not isinstance(item, tuple) or len(item) != 2:
            raise TypeError(f"{name}[{index}] must be a two-item tuple.")
        key, value = item
        _text(key, f"{name}[{index}].key", maximum=_MAX_METADATA_KEY_CHARS)
        _text(value, f"{name}[{index}].value", maximum=_MAX_METADATA_VALUE_CHARS)
        keys.append(key)
    if keys != sorted(keys):
        raise ValueError(f"{name} must be in deterministic key order.")
    if len(set(keys)) != len(keys):
        raise ValueError(f"{name} must not contain duplicate keys.")
    return values


@dataclass(frozen=True, slots=True)
class RetrievalProvenance:
    source_type: str
    source_id: str
    source_fingerprint: str | None = None
    evidence_refs: tuple[str, ...] = ()

    @property
    def identity(self) -> tuple[str, str]:
        return (self.source_type, self.source_id)

    def validate(self) -> None:
        _text(self.source_type, "source_type", maximum=_MAX_SOURCE_TYPE_CHARS)
        _text(self.source_id, "source_id", maximum=_MAX_ID_CHARS)
        if self.source_fingerprint is not None:
            _text(self.source_fingerprint, "source_fingerprint", maximum=_MAX_FINGERPRINT_CHARS)
        _sorted_unique_strings(self.evidence_refs, "evidence_refs", maximum_items=_MAX_REFERENCES, maximum_chars=_MAX_REFERENCE_CHARS)


@dataclass(frozen=True, slots=True)
class RetrievableEvidenceItem:
    schema_version: str
    item_id: str
    text: str
    provenance: RetrievalProvenance
    metadata: tuple[tuple[str, str], ...] = ()

    def validate(self) -> None:
        if self.schema_version != CURRENT_RETRIEVAL_SCHEMA_VERSION:
            raise ValueError(f"Unsupported retrieval schema version: {self.schema_version!r}.")
        _text(self.item_id, "item_id", maximum=_MAX_ID_CHARS)
        _text(self.text, "text", maximum=_MAX_TEXT_CHARS)
        if not isinstance(self.provenance, RetrievalProvenance):
            raise TypeError("provenance must be a RetrievalProvenance.")
        self.provenance.validate()
        _metadata(self.metadata, "metadata")


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    query_text: str
    max_results: int = 10
    source_types: tuple[str, ...] = ()
    metadata_filters: tuple[tuple[str, str], ...] = ()

    def validate(self) -> None:
        _text(self.query_text, "query_text", maximum=_MAX_TEXT_CHARS)
        if isinstance(self.max_results, bool) or not isinstance(self.max_results, int):
            raise TypeError("max_results must be an integer.")
        if self.max_results < 1 or self.max_results > _MAX_RESULTS:
            raise ValueError(f"max_results must be between 1 and {_MAX_RESULTS}.")
        _sorted_unique_strings(self.source_types, "source_types", maximum_items=_MAX_SOURCE_TYPES, maximum_chars=_MAX_SOURCE_TYPE_CHARS)
        _metadata(self.metadata_filters, "metadata_filters")


@dataclass(frozen=True, slots=True)
class RetrievalContext:
    query: RetrievalQuery
    candidate_item_ids: tuple[str, ...] = ()

    def validate(self) -> None:
        if not isinstance(self.query, RetrievalQuery):
            raise TypeError("query must be a RetrievalQuery.")
        self.query.validate()
        _sorted_unique_strings(self.candidate_item_ids, "candidate_item_ids", maximum_items=_MAX_CANDIDATES, maximum_chars=_MAX_ID_CHARS)


@dataclass(frozen=True, slots=True)
class RankedRetrievalResult:
    item: RetrievableEvidenceItem
    rank: int
    rationale: str | None = None

    def validate(self) -> None:
        if not isinstance(self.item, RetrievableEvidenceItem):
            raise TypeError("item must be a RetrievableEvidenceItem.")
        self.item.validate()
        if isinstance(self.rank, bool) or not isinstance(self.rank, int):
            raise TypeError("rank must be an integer.")
        if self.rank < 1:
            raise ValueError("rank must be a positive integer.")
        if self.rationale is not None:
            _text(self.rationale, "rationale", maximum=_MAX_RATIONALE_CHARS)


@dataclass(frozen=True, slots=True)
class RetrievalValidationOutcome:
    item_id: str
    decision: RetrievalValidationDecision
    reason_codes: tuple[str, ...] = ()

    def validate(self) -> None:
        _text(self.item_id, "item_id", maximum=_MAX_ID_CHARS)
        if not isinstance(self.decision, RetrievalValidationDecision):
            raise TypeError("decision must be a RetrievalValidationDecision.")
        _sorted_unique_strings(self.reason_codes, "reason_codes", maximum_items=_MAX_REASON_CODES, maximum_chars=_MAX_REASON_CODE_CHARS)
        if self.decision is RetrievalValidationDecision.REJECT and not self.reason_codes:
            raise ValueError("REJECT validation outcomes require a reason code.")
