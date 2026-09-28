"""Generic, advisory, side-aware field proposals for coin observations.

This module is deliberately below ``RecognitionGateResult`` and imports no
phone, reviewed-draft, persistence, or approval code.  A supported field is
only a review suggestion; it is never a whole-identity or save decision.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum

from .date_numeral_extraction import DateNumeralExtraction
from .denomination_mark_extraction import DenominationMarkExtraction

_FIELD_NAMES = ("country", "denomination", "year", "monarch", "reverse_design", "variety")
_IMAGE_ROLES = {"OBVERSE", "REVERSE"}
_MAX_EVIDENCE = 8
_MAX_CANDIDATES = 25
_MAX_TEXT = 255
_EXACT_YEAR = re.compile(r"^\d{4}$")


class FieldProposalStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICTING = "CONFLICTING"
    ABSTAIN = "ABSTAIN"


class ProposalScope(str, Enum):
    DIRECT_OBSERVATION = "DIRECT_OBSERVATION"
    CANDIDATE_METADATA = "CANDIDATE_METADATA"
    CROSS_SIDE_AGREEMENT = "CROSS_SIDE_AGREEMENT"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """Bounded provenance for one field-level observation or metadata trail."""

    source: str
    image_role: str | None
    artifact_id: str
    observed_value: str
    producer_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("source", "artifact_id", "observed_value"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > _MAX_TEXT:
                raise ValueError(f"{name} must be bounded non-empty text.")
        if self.image_role is not None and self.image_role not in _IMAGE_ROLES:
            raise ValueError("image_role must be OBVERSE, REVERSE, or None for non-image metadata.")
        if self.producer_id is not None and (
            not isinstance(self.producer_id, str) or not self.producer_id.strip() or len(self.producer_id) > _MAX_TEXT
        ):
            raise ValueError("producer_id must be bounded non-empty text when present.")

    def to_dict(self) -> dict[str, str | None]:
        return {
            "source": self.source,
            "image_role": self.image_role,
            "artifact_id": self.artifact_id,
            "observed_value": self.observed_value,
            "producer_id": self.producer_id,
        }


@dataclass(frozen=True, slots=True)
class FieldProposal:
    field_name: str
    status: FieldProposalStatus
    proposed_value: str | None
    normalized_value: str | None
    evidence: tuple[EvidenceReference, ...]
    reasons: tuple[str, ...]
    scope: ProposalScope
    candidate_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.field_name not in _FIELD_NAMES:
            raise ValueError("field_name is not supported by the coin proposal contract.")
        if not isinstance(self.status, FieldProposalStatus) or not isinstance(self.scope, ProposalScope):
            raise TypeError("status and scope must be proposal enums.")
        if self.status is FieldProposalStatus.SUPPORTED:
            if not self.proposed_value or not self.normalized_value:
                raise ValueError("supported proposals require proposed and normalized values.")
        elif self.proposed_value is not None or self.normalized_value is not None:
            raise ValueError("non-supported proposals cannot select a value.")
        if not isinstance(self.evidence, tuple) or len(self.evidence) > _MAX_EVIDENCE or any(not isinstance(item, EvidenceReference) for item in self.evidence):
            raise ValueError("evidence must be a bounded tuple of EvidenceReference values.")
        if not isinstance(self.reasons, tuple) or not self.reasons or any(not _stable_reason(item) for item in self.reasons):
            raise ValueError("reasons must be stable non-empty reason codes.")
        if not isinstance(self.candidate_ids, tuple) or len(self.candidate_ids) > _MAX_CANDIDATES or any(not _bounded_id(item) for item in self.candidate_ids):
            raise ValueError("candidate_ids must be bounded opaque identifiers.")
        if self.field_name == "year" and self.status is FieldProposalStatus.SUPPORTED:
            if self.scope is not ProposalScope.DIRECT_OBSERVATION or not _EXACT_YEAR.fullmatch(self.proposed_value or ""):
                raise ValueError("a supported year requires direct exact observed evidence.")
            if not any(item.observed_value == self.proposed_value and item.image_role is not None for item in self.evidence):
                raise ValueError("a supported year requires retained side-aware direct evidence.")

    @classmethod
    def supported(
        cls, field_name: str, proposed_value: str, normalized_value: str,
        evidence: Sequence[EvidenceReference], *, scope: ProposalScope,
        reasons: tuple[str, ...] = ("direct_field_evidence",), candidate_ids: tuple[str, ...] = (),
    ) -> FieldProposal:
        return cls(field_name, FieldProposalStatus.SUPPORTED, proposed_value, normalized_value, tuple(evidence), reasons, scope, candidate_ids)

    @classmethod
    def unresolved(
        cls, field_name: str, status: FieldProposalStatus, evidence: Sequence[EvidenceReference] = (),
        *, reasons: tuple[str, ...], scope: ProposalScope = ProposalScope.DIRECT_OBSERVATION,
        candidate_ids: tuple[str, ...] = (),
    ) -> FieldProposal:
        if status is FieldProposalStatus.SUPPORTED:
            raise ValueError("use supported for selected proposals.")
        return cls(field_name, status, None, None, tuple(evidence), reasons, scope, candidate_ids)

    def to_dict(self) -> dict[str, object]:
        return {
            "field_name": self.field_name, "status": self.status.value,
            "proposed_value": self.proposed_value, "normalized_value": self.normalized_value,
            "evidence": [item.to_dict() for item in self.evidence], "reasons": list(self.reasons),
            "scope": self.scope.value, "candidate_ids": list(self.candidate_ids),
        }


@dataclass(frozen=True, slots=True)
class CoinFieldProposalSet:
    """Immutable advisory projection; intentionally has no approval or save surface."""

    schema_version: int
    source_coin_id: str
    fields: tuple[FieldProposal, ...]
    producer_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != 1 or not _bounded_id(self.source_coin_id):
            raise ValueError("proposal set schema version or source coin ID is invalid.")
        if not isinstance(self.fields, tuple) or tuple(item.field_name for item in self.fields) != _FIELD_NAMES:
            raise ValueError("proposal fields must be the complete canonical ordered field set.")
        if any(not isinstance(item, FieldProposal) for item in self.fields):
            raise TypeError("fields must contain FieldProposal values.")
        if not isinstance(self.producer_ids, tuple) or any(not _bounded_id(item) for item in self.producer_ids):
            raise ValueError("producer_ids must be bounded identifiers.")

    def field(self, field_name: str) -> FieldProposal:
        return next(item for item in self.fields if item.field_name == field_name)

    def to_dict(self) -> dict[str, object]:
        return {"schema_version": self.schema_version, "source_coin_id": self.source_coin_id, "producer_ids": list(self.producer_ids), "fields": [item.to_dict() for item in self.fields]}


def project_coin_field_proposals(
    *, source_coin_id: str, date: DateNumeralExtraction, denomination: DenominationMarkExtraction,
    direct_evidence: Iterable[tuple[str, str, str, str, str, str]] = (),
    candidate_metadata: Iterable[tuple[str, str, str]] = (), producer_ids: tuple[str, ...] = (),
) -> CoinFieldProposalSet:
    """Project conservative literal/direct evidence into independent advisory fields.

    Candidate metadata can retain/reject year compatibility, but cannot generate a
    year.  It is deliberately not a recognizer and does not invoke a final gate.
    """
    if not isinstance(date, DateNumeralExtraction) or not isinstance(denomination, DenominationMarkExtraction):
        raise TypeError("date and denomination must be existing conservative extraction artifacts.")
    direct = _direct_by_field(direct_evidence)
    metadata = _metadata_by_field(candidate_metadata)
    fields = (
        _direct_field("country", direct["country"]),
        _denomination_field(denomination),
        _year_field(date, metadata["year"]),
        _direct_field("monarch", direct["monarch"]),
        _direct_field("reverse_design", direct["reverse_design"]),
        FieldProposal.unresolved("variety", FieldProposalStatus.ABSTAIN, reasons=("variety_disabled",)),
    )
    return CoinFieldProposalSet(1, source_coin_id, fields, producer_ids)


def _denomination_field(extraction: DenominationMarkExtraction) -> FieldProposal:
    evidence = tuple(EvidenceReference("DIRECT_DENOMINATION_MARK", item.role.upper(), item.source_field, item.value) for item in extraction.candidates)
    if extraction.conflict:
        return FieldProposal.unresolved("denomination", FieldProposalStatus.CONFLICTING, evidence, reasons=("direct_denomination_conflict",))
    if extraction.resolved_value is None:
        return FieldProposal.unresolved("denomination", FieldProposalStatus.ABSTAIN, evidence, reasons=("no_defensible_denomination_evidence",))
    return FieldProposal.supported("denomination", extraction.resolved_value, _normalize(extraction.resolved_value), evidence, scope=ProposalScope.DIRECT_OBSERVATION, reasons=("explicit_denomination_mark",))


def _year_field(extraction: DateNumeralExtraction, metadata: tuple[tuple[str, str], ...]) -> FieldProposal:
    evidence = tuple(EvidenceReference("DIRECT_DATE_NUMERAL", item.role.upper(), item.source_field, item.value) for item in extraction.candidates)
    ids = tuple(item[0] for item in metadata)
    if extraction.conflict:
        return FieldProposal.unresolved("year", FieldProposalStatus.CONFLICTING, evidence, reasons=("direct_year_conflict",), candidate_ids=ids)
    if extraction.resolved_value is None:
        return FieldProposal.unresolved("year", FieldProposalStatus.ABSTAIN, evidence, reasons=("no_exact_direct_year",), candidate_ids=ids)
    exact_metadata = tuple(value for _, value in metadata if _EXACT_YEAR.fullmatch(value))
    if exact_metadata and any(value != extraction.resolved_value for value in exact_metadata):
        trails = evidence + tuple(EvidenceReference("CANDIDATE_METADATA", None, candidate_id, value) for candidate_id, value in metadata if _EXACT_YEAR.fullmatch(value))
        return FieldProposal.unresolved("year", FieldProposalStatus.CONFLICTING, trails, reasons=("direct_year_metadata_conflict",), scope=ProposalScope.CANDIDATE_METADATA, candidate_ids=ids)
    return FieldProposal.supported("year", extraction.resolved_value, extraction.resolved_value, evidence, scope=ProposalScope.DIRECT_OBSERVATION, reasons=("exact_direct_year",), candidate_ids=ids)


def _direct_field(field_name: str, rows: tuple[tuple[str, str, EvidenceReference], ...]) -> FieldProposal:
    if not rows:
        return FieldProposal.unresolved(field_name, FieldProposalStatus.ABSTAIN, reasons=("no_defensible_direct_evidence",))
    values = {normalized for _, normalized, _ in rows}
    evidence = tuple(item[2] for item in rows)
    if len(values) > 1:
        roles = {item.image_role for item in evidence}
        if len(roles) == 1:
            return FieldProposal.unresolved(field_name, FieldProposalStatus.AMBIGUOUS, evidence, reasons=("multiple_compatible_direct_values",))
        return FieldProposal.unresolved(field_name, FieldProposalStatus.CONFLICTING, evidence, reasons=("direct_field_conflict",))
    value, normalized, _ = rows[0]
    return FieldProposal.supported(field_name, value, normalized, evidence, scope=ProposalScope.DIRECT_OBSERVATION, reasons=(("one_side_supported",) if len({item.image_role for item in evidence}) == 1 else ("direct_field_agreement",)))


def _direct_by_field(rows: Iterable[tuple[str, str, str, str, str, str]]) -> dict[str, tuple[tuple[str, str, EvidenceReference], ...]]:
    result: dict[str, list[tuple[str, str, EvidenceReference]]] = {field: [] for field in _FIELD_NAMES}
    for field, value, normalized, role, source, artifact_id in rows:
        if field not in _FIELD_NAMES or field in {"year", "denomination", "variety"}:
            raise ValueError("direct evidence for year, denomination, and variety must use their dedicated safety paths.")
        result[field].append((value, normalized, EvidenceReference(source, role.upper(), artifact_id, value)))
    return {field: tuple(items) for field, items in result.items()}


def _metadata_by_field(rows: Iterable[tuple[str, str, str]]) -> dict[str, tuple[tuple[str, str], ...]]:
    result: dict[str, list[tuple[str, str]]] = {field: [] for field in _FIELD_NAMES}
    for candidate_id, field, value in rows:
        if field not in _FIELD_NAMES or not _bounded_id(candidate_id) or not isinstance(value, str) or not value.strip() or len(value) > _MAX_TEXT:
            raise ValueError("candidate metadata must be bounded and use a supported field.")
        result[field].append((candidate_id, value))
    return {field: tuple(items) for field, items in result.items()}


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _bounded_id(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= _MAX_TEXT


def _stable_reason(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[a-z0-9_]{1,64}", value))
