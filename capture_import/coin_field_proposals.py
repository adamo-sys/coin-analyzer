"""Generic, advisory, side-aware field proposals for coin observations.

This module is deliberately below ``RecognitionGateResult`` and imports no
phone, reviewed-draft, persistence, or approval code.  A supported field is
only a review suggestion; it is never a whole-identity or save decision.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import Enum

from .canonical_identity import canonicalize_denomination, canonicalize_jurisdiction
from .date_numeral_extraction import DateNumeralExtraction, extract_date_numerals
from .denomination_mark_extraction import (
    DenominationMarkExtraction,
    extract_denomination_marks,
)
from .grounded_visual_observation import GroundedVisualObservation
from .two_side_candidate_verification import UniqueVerifiedCandidateDenominationSupport

_FIELD_NAMES = ("country", "denomination", "year", "monarch", "reverse_design", "variety")
_IMAGE_ROLES = {"OBVERSE", "REVERSE"}
_MAX_EVIDENCE = 8
_MAX_CANDIDATES = 25
_MAX_PRODUCERS = 8
_MAX_TEXT = 255
_EXACT_YEAR = re.compile(r"^\d{4}$")
_YEAR_RANGE = re.compile(r"^(\d{4})-(\d{4})$")
_SUPPORT_CONSTRUCTION = ContextVar("field_proposal_support_construction", default=False)


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
    _validated: bool = dataclass_field(default=False, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.field_name not in _FIELD_NAMES:
            raise ValueError("field_name is not supported by the coin proposal contract.")
        if not isinstance(self.status, FieldProposalStatus) or not isinstance(self.scope, ProposalScope):
            raise TypeError("status and scope must be proposal enums.")
        if self.status is FieldProposalStatus.SUPPORTED:
            if not _SUPPORT_CONSTRUCTION.get():
                raise ValueError("SUPPORTED is produced only by field-aware validation.")
            if not self.proposed_value or not self.normalized_value:
                raise ValueError("supported proposals require proposed and normalized values.")
            if not isinstance(self.proposed_value, str) or not isinstance(self.normalized_value, str) or len(self.proposed_value) > _MAX_TEXT or len(self.normalized_value) > _MAX_TEXT:
                raise ValueError("supported values must be bounded text.")
        elif self.proposed_value is not None or self.normalized_value is not None:
            raise ValueError("non-supported proposals cannot select a value.")
        if not isinstance(self.evidence, tuple) or len(self.evidence) > _MAX_EVIDENCE or any(not isinstance(item, EvidenceReference) for item in self.evidence):
            raise ValueError("evidence must be a bounded tuple of EvidenceReference values.")
        if not isinstance(self.reasons, tuple) or not self.reasons or any(not _stable_reason(item) for item in self.reasons):
            raise ValueError("reasons must be stable non-empty reason codes.")
        if not isinstance(self.candidate_ids, tuple) or len(self.candidate_ids) > _MAX_CANDIDATES or any(not _bounded_id(item) for item in self.candidate_ids):
            raise ValueError("candidate_ids must be bounded opaque identifiers.")
        if self.status is FieldProposalStatus.SUPPORTED and not self.evidence:
            raise ValueError("supported proposals require retained provenance evidence.")
        if self.field_name in {"monarch", "reverse_design"} and self.status is FieldProposalStatus.SUPPORTED:
            required_role = "OBVERSE" if self.field_name == "monarch" else "REVERSE"
            if not self.candidate_ids or not any(item.image_role == required_role and _normalize(item.observed_value) == self.normalized_value for item in self.evidence) or not any(item.source == "CANDIDATE_METADATA" and item.artifact_id in self.candidate_ids and _normalize(item.observed_value) == self.normalized_value for item in self.evidence):
                raise ValueError("supported semantic proposals require role-correct direct evidence and candidate provenance.")
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
        raise ValueError("SUPPORTED proposals are created only by the field-aware projector.")

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
        if not isinstance(self.producer_ids, tuple) or len(self.producer_ids) > _MAX_PRODUCERS or any(not _bounded_id(item) for item in self.producer_ids):
            raise ValueError("producer_ids must be bounded identifiers.")

    def field(self, field_name: str) -> FieldProposal:
        return next(item for item in self.fields if item.field_name == field_name)

    def to_dict(self) -> dict[str, object]:
        return {"schema_version": self.schema_version, "source_coin_id": self.source_coin_id, "producer_ids": list(self.producer_ids), "fields": [item.to_dict() for item in self.fields]}


def project_coin_field_proposals(
    *, source_coin_id: str, date: DateNumeralExtraction, denomination: DenominationMarkExtraction,
    direct_evidence: Iterable[tuple[str, str, str, str, str, str]] = (),
    candidate_metadata: Iterable[tuple[str, str, str]] = (), candidate_support: UniqueVerifiedCandidateDenominationSupport | None = None,
    observations: Iterable[GroundedVisualObservation] | None = None, producer_ids: tuple[str, ...] = (),
) -> CoinFieldProposalSet:
    """Project conservative literal/direct evidence into independent advisory fields.

    Candidate metadata can retain/reject year compatibility, but cannot generate a
    year.  It is deliberately not a recognizer and does not invoke a final gate.
    """
    if not isinstance(date, DateNumeralExtraction) or not isinstance(denomination, DenominationMarkExtraction):
        raise TypeError("date and denomination must be existing conservative extraction artifacts.")
    direct = _direct_by_field(direct_evidence)
    metadata = _metadata_by_field(candidate_metadata)
    if metadata["country"]:
        raise ValueError("candidate country metadata is not accepted by this packet's direct-issuer contract.")
    country = _direct_field("country", direct["country"])
    fields = (
        country,
        _denomination_field(denomination, country, candidate_support, source_coin_id, date, observations),
        _year_field(date, metadata["year"]),
        _semantic_field("monarch", direct["monarch"], metadata["monarch"]),
        _semantic_field("reverse_design", direct["reverse_design"], metadata["reverse_design"]),
        FieldProposal.unresolved("variety", FieldProposalStatus.ABSTAIN, reasons=("variety_disabled",)),
    )
    return CoinFieldProposalSet(1, source_coin_id, fields, producer_ids)


def _denomination_field(extraction: DenominationMarkExtraction, country: FieldProposal, support: UniqueVerifiedCandidateDenominationSupport | None, source_coin_id: str, date: DateNumeralExtraction, observations: Iterable[GroundedVisualObservation] | None) -> FieldProposal:
    evidence = tuple(EvidenceReference("DIRECT_DENOMINATION_MARK", item.role.upper(), item.source_field, item.value) for item in extraction.candidates)
    if extraction.conflict:
        return FieldProposal.unresolved("denomination", FieldProposalStatus.CONFLICTING, evidence, reasons=("direct_denomination_conflict",))
    if extraction.resolved_value is None:
        return FieldProposal.unresolved("denomination", FieldProposalStatus.ABSTAIN, evidence, reasons=("no_defensible_denomination_evidence",))
    canonical = canonicalize_jurisdiction(country.proposed_value)
    if country.status is FieldProposalStatus.SUPPORTED and canonical.is_mapped:
        canonical_denomination = canonicalize_denomination(
            extraction.resolved_value,
            jurisdiction_id=canonical.canonical_value.canonical_id,
        )
        if not canonical_denomination.is_mapped:
            return FieldProposal.unresolved(
                "denomination",
                FieldProposalStatus.ABSTAIN,
                evidence,
                reasons=("explicit_denomination_not_mapped_to_canonical_issuer",),
            )
        return _supported("denomination", extraction.resolved_value, _normalize(extraction.resolved_value), evidence, scope=ProposalScope.CROSS_SIDE_AGREEMENT, reasons=("explicit_denomination_with_canonical_issuer",))
    if not isinstance(support, UniqueVerifiedCandidateDenominationSupport):
        return FieldProposal.unresolved("denomination", FieldProposalStatus.ABSTAIN, evidence, reasons=("unique_verified_candidate_required",))
    if not _candidate_support_matches_current_observations(support, source_coin_id, date, extraction, observations):
        return FieldProposal.unresolved("denomination", FieldProposalStatus.CONFLICTING, evidence, reasons=("candidate_support_context_mismatch",), candidate_ids=(support.candidate_id,))
    if _normalize(support.denomination) != _normalize(extraction.resolved_value):
        return FieldProposal.unresolved("denomination", FieldProposalStatus.CONFLICTING, evidence, reasons=("direct_candidate_denomination_conflict",), candidate_ids=(support.candidate_id,))
    return _supported("denomination", extraction.resolved_value, _normalize(extraction.resolved_value), evidence + (EvidenceReference("CANDIDATE_VERIFICATION", None, support.candidate_id, support.denomination),), scope=ProposalScope.CROSS_SIDE_AGREEMENT, reasons=("explicit_denomination_with_unique_verified_candidate",), candidate_ids=(support.candidate_id,))


def _candidate_support_matches_current_observations(support: UniqueVerifiedCandidateDenominationSupport, source_coin_id: str, date: DateNumeralExtraction, denomination: DenominationMarkExtraction, observations: Iterable[GroundedVisualObservation] | None) -> bool:
    if observations is None or support.validation_context_id != source_coin_id:
        return False
    sides = tuple(observations)
    return (
        support.observations == sides
        and date == extract_date_numerals(sides)
        and denomination == extract_denomination_marks(sides)
    )

def _semantic_field(field_name: str, rows: tuple[tuple[str, str, EvidenceReference], ...], metadata: tuple[tuple[str, str], ...]) -> FieldProposal:
    required_role = "OBVERSE" if field_name == "monarch" else "REVERSE"
    valid = tuple(row for row in rows if row[2].image_role == required_role)
    if not valid:
        return FieldProposal.unresolved(field_name, FieldProposalStatus.ABSTAIN, tuple(row[2] for row in rows), reasons=("missing_role_correct_direct_evidence",))
    direct = _direct_field(field_name, valid)
    if direct.status is not FieldProposalStatus.SUPPORTED:
        return direct
    matches = tuple(candidate_id for candidate_id, value in metadata if _normalize(value) == direct.normalized_value)
    conflicting = tuple(candidate_id for candidate_id, value in metadata if _normalize(value) != direct.normalized_value)
    if conflicting:
        trails = direct.evidence + tuple(EvidenceReference("CANDIDATE_METADATA", None, item, "conflicting_metadata") for item in conflicting)
        return FieldProposal.unresolved(field_name, FieldProposalStatus.CONFLICTING, trails, reasons=("direct_metadata_conflict",), scope=ProposalScope.CANDIDATE_METADATA, candidate_ids=matches + conflicting)
    if len(matches) != 1:
        return FieldProposal.unresolved(field_name, FieldProposalStatus.ABSTAIN, direct.evidence, reasons=("unique_candidate_metadata_required",), candidate_ids=matches)
    return _supported(field_name, direct.proposed_value or "", direct.normalized_value or "", direct.evidence + (EvidenceReference("CANDIDATE_METADATA", None, matches[0], direct.proposed_value or ""),), scope=ProposalScope.CROSS_SIDE_AGREEMENT, reasons=("role_correct_direct_and_candidate_metadata",), candidate_ids=matches)


def _year_field(extraction: DateNumeralExtraction, metadata: tuple[tuple[str, str], ...]) -> FieldProposal:
    evidence = tuple(EvidenceReference("DIRECT_DATE_NUMERAL", item.role.upper(), item.source_field, item.value) for item in extraction.candidates)
    ids = tuple(item[0] for item in metadata)
    if extraction.conflict:
        return FieldProposal.unresolved("year", FieldProposalStatus.CONFLICTING, evidence, reasons=("direct_year_conflict",), candidate_ids=ids)
    if extraction.resolved_value is None:
        return FieldProposal.unresolved("year", FieldProposalStatus.ABSTAIN, evidence, reasons=("no_exact_direct_year",), candidate_ids=ids)
    constrained_metadata = tuple((candidate_id, value) for candidate_id, value in metadata if _is_year_constraint(value))
    if any(not _year_constraint_matches(value, extraction.resolved_value) for _, value in constrained_metadata):
        trails = evidence + tuple(EvidenceReference("CANDIDATE_METADATA", None, candidate_id, value) for candidate_id, value in constrained_metadata)
        return FieldProposal.unresolved("year", FieldProposalStatus.CONFLICTING, trails, reasons=("direct_year_metadata_conflict",), scope=ProposalScope.CANDIDATE_METADATA, candidate_ids=ids)
    return _supported("year", extraction.resolved_value, extraction.resolved_value, evidence, scope=ProposalScope.DIRECT_OBSERVATION, reasons=("exact_direct_year",), candidate_ids=ids)


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
    value, _, _ = rows[0]
    return _supported(field_name, value, _normalize(value), evidence, scope=ProposalScope.DIRECT_OBSERVATION, reasons=(("one_side_supported",) if len({item.image_role for item in evidence}) == 1 else ("direct_field_agreement",)))


def _supported(field_name: str, proposed_value: str, normalized_value: str, evidence: Sequence[EvidenceReference], *, scope: ProposalScope, reasons: tuple[str, ...], candidate_ids: tuple[str, ...] = ()) -> FieldProposal:
    if not any(_normalize(item.observed_value) == normalized_value for item in evidence if item.image_role is not None):
        raise ValueError("supported proposal value must correspond to direct evidence.")
    if field_name in {"monarch", "reverse_design"} and not any(item.source == "CANDIDATE_METADATA" and _normalize(item.observed_value) == normalized_value for item in evidence):
        raise ValueError("semantic supported proposal requires matching candidate metadata evidence.")
    token = _SUPPORT_CONSTRUCTION.set(True)
    try:
        return FieldProposal(field_name, FieldProposalStatus.SUPPORTED, proposed_value, normalized_value, tuple(evidence), reasons, scope, candidate_ids)
    finally:
        _SUPPORT_CONSTRUCTION.reset(token)


def _direct_by_field(rows: Iterable[tuple[str, str, str, str, str, str]]) -> dict[str, tuple[tuple[str, str, EvidenceReference], ...]]:
    result: dict[str, list[tuple[str, str, EvidenceReference]]] = {field: [] for field in _FIELD_NAMES}
    for field, value, _caller_normalized, role, source, artifact_id in rows:
        if field not in _FIELD_NAMES or field in {"year", "denomination", "variety"}:
            raise ValueError("direct evidence for year, denomination, and variety must use their dedicated safety paths.")
        evidence = EvidenceReference(source, role.upper(), artifact_id, value)
        result[field].append((value, _normalize(evidence.observed_value), evidence))
    return {field: tuple(items) for field, items in result.items()}


def _metadata_by_field(rows: Iterable[tuple[str, str, str]]) -> dict[str, tuple[tuple[str, str], ...]]:
    result: dict[str, list[tuple[str, str]]] = {field: [] for field in _FIELD_NAMES}
    for candidate_id, field, value in rows:
        if field not in _FIELD_NAMES or not _bounded_id(candidate_id) or not isinstance(value, str) or not value.strip() or len(value) > _MAX_TEXT:
            raise ValueError("candidate metadata must be bounded and use a supported field.")
        result[field].append((candidate_id, value))
    return {field: tuple(items) for field, items in result.items()}


def _is_year_constraint(value: str) -> bool:
    return _EXACT_YEAR.fullmatch(value) is not None or _YEAR_RANGE.fullmatch(value) is not None


def _year_constraint_matches(value: str, direct_year: str) -> bool:
    if _EXACT_YEAR.fullmatch(value):
        return value == direct_year
    match = _YEAR_RANGE.fullmatch(value)
    if match is None:
        return True
    start, end = match.groups()
    return start <= direct_year <= end

def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _bounded_id(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= _MAX_TEXT


def _stable_reason(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[a-z0-9_]{1,64}", value))
