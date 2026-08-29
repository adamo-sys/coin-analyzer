"""Deterministic desktop acceptance review records, packets, and reporting.

This module validates human-originated review records, generates blinded
reviewer packets, and derives advisory progress reports.  It does not mutate
authoring state, apply reconciliation results, or authorize recognition,
photography, or benchmark execution.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Mapping, Sequence, TypeAlias
from urllib.parse import unquote, urlsplit

from capture_import.desktop_acceptance_authoring import (
    DESKTOP_ACCEPTANCE_V1_CASE_COUNT,
    validate_authoring_plan,
)


REVIEW_EXECUTION_SCHEMA = "coin-analyzer-desktop-acceptance-review-execution"
REVIEW_EXECUTION_VERSION = "1.0.0"
REVIEW_PACKET_SCHEMA = "coin-analyzer-desktop-acceptance-review-packet"
REVIEW_PACKET_VERSION = "1.0.0"
REVIEW_PROGRESS_SCHEMA = "coin-analyzer-desktop-acceptance-review-progress"
REVIEW_PROGRESS_VERSION = "1.0.0"
REVIEW_RECONCILIATION_SCHEMA = "coin-analyzer-desktop-acceptance-review-reconciliation"
REVIEW_RECONCILIATION_VERSION = "1.0.0"
EVIDENCE_RESOLUTION_SCHEMA = "coin-analyzer-desktop-acceptance-evidence-resolution"
EVIDENCE_RESOLUTION_VERSION = "1.0.0"
EVIDENCE_ATTESTATION_ROOTS = (
    "benchmarks/real-world-desktop-v1/evidence/",
    "benchmarks/real-world-desktop-v1/reviews/",
)
REVIEW_STATES = frozenset({"unresolved", "complete"})
ELIGIBILITY_STATES = frozenset({"unresolved", "approved", "rejected"})
EXPECTED_ACTIONS = frozenset({"identify", "abstain"})
ELIGIBILITY_FIELDS = ("privacy", "licensing", "provider_authorization")
GROUND_TRUTH_TRACK = "ground_truth"
ACTION_TRACK = "expected_action"
IDENTITY_FIELDS = ("country", "denomination", "year")
GROUND_TRUTH_INSTRUCTIONS = (
    "Determine country or jurisdiction, denomination, and year from the permitted evidence.",
    "Record the decision independently without seeking candidate or peer decisions.",
)
ACTION_INSTRUCTIONS = (
    "Determine whether the resolved identity is within the frozen v1 domain.",
    "Base the decision only on the supplied domain and canonicalization references.",
)
GROUND_TRUTH_PROGRESS_STATES = (
    "unassigned",
    "awaiting_submissions",
    "disagreement_awaiting_adjudication",
    "unresolved",
    "complete",
)
ACTION_PROGRESS_STATES = (
    "blocked_by_ground_truth",
    *GROUND_TRUTH_PROGRESS_STATES,
)

_CASE_ID = re.compile(r"^case-[0-9]{3}$")
_SPECIMEN_ID = re.compile(r"^specimen-[0-9]{3}$")
_SAFE_REVIEWER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:")
_OBVIOUS_CREDENTIAL = re.compile(
    r"(?:^|[.:_-])(?:password|passwd|secret|api[_-]?key|credential|bearer)(?:$|[=:._-])",
    re.IGNORECASE,
)


class DesktopAcceptanceReviewError(ValueError):
    """A review execution record is unreadable, malformed, or inconsistent."""


@dataclass(frozen=True, slots=True)
class IdentityDecision:
    country: str
    denomination: str
    year: str

    def as_dict(self) -> dict[str, str]:
        return {
            "country": self.country,
            "denomination": self.denomination,
            "year": self.year,
        }


ReviewDecision: TypeAlias = IdentityDecision | str


@dataclass(frozen=True, slots=True)
class ReviewSubmission:
    reviewer_id: str
    decision: ReviewDecision
    evidence_references: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "reviewer_id": self.reviewer_id,
            "decision": _decision_as_json(self.decision),
            "evidence_references": list(self.evidence_references),
        }


@dataclass(frozen=True, slots=True)
class ReviewAdjudication:
    reviewer_id: str
    decision: ReviewDecision
    evidence_references: tuple[str, ...]
    rationale: str

    def as_dict(self) -> dict[str, object]:
        return {
            "reviewer_id": self.reviewer_id,
            "decision": _decision_as_json(self.decision),
            "evidence_references": list(self.evidence_references),
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class ReviewTrack:
    state: str
    submissions: tuple[ReviewSubmission, ...]
    adjudication: ReviewAdjudication | None

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "submissions": [submission.as_dict() for submission in self.submissions],
            "adjudication": None if self.adjudication is None else self.adjudication.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    state: str
    evidence_references: tuple[str, ...]

    @property
    def approved(self) -> bool:
        return self.state == "approved"

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "evidence_references": list(self.evidence_references),
        }


@dataclass(frozen=True, slots=True)
class ProviderEligibility:
    privacy: EligibilityDecision
    licensing: EligibilityDecision
    provider_authorization: EligibilityDecision

    @property
    def approved(self) -> bool:
        return all(getattr(self, field).approved for field in ELIGIBILITY_FIELDS)

    def as_dict(self) -> dict[str, object]:
        return {field: getattr(self, field).as_dict() for field in ELIGIBILITY_FIELDS}


@dataclass(frozen=True, slots=True)
class ReviewCaseRecord:
    case_id: str
    specimen_id: str
    ground_truth_review: ReviewTrack
    action_review: ReviewTrack
    provider_eligibility: ProviderEligibility

    def as_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "specimen_id": self.specimen_id,
            "ground_truth_review": self.ground_truth_review.as_dict(),
            "action_review": self.action_review.as_dict(),
            "provider_eligibility": self.provider_eligibility.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class ReviewExecutionRecord:
    schema: str
    version: str
    cases: tuple[ReviewCaseRecord, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "version": self.version,
            "cases": [case.as_dict() for case in self.cases],
        }


@dataclass(frozen=True, slots=True)
class GroundTruthReviewerPacket:
    schema: str
    version: str
    track: str
    case_id: str
    specimen_id: str
    reviewer_id: str
    evidence_references: tuple[str, ...]
    identity_fields: tuple[str, ...]
    instructions: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "version": self.version,
            "track": self.track,
            "case_id": self.case_id,
            "specimen_id": self.specimen_id,
            "reviewer_id": self.reviewer_id,
            "evidence_references": list(self.evidence_references),
            "identity_fields": list(self.identity_fields),
            "instructions": list(self.instructions),
        }


@dataclass(frozen=True, slots=True)
class ActionReviewerPacket:
    schema: str
    version: str
    track: str
    case_id: str
    specimen_id: str
    reviewer_id: str
    resolved_identity: IdentityDecision
    domain_references: tuple[str, ...]
    instructions: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "version": self.version,
            "track": self.track,
            "case_id": self.case_id,
            "specimen_id": self.specimen_id,
            "reviewer_id": self.reviewer_id,
            "resolved_identity": self.resolved_identity.as_dict(),
            "domain_references": list(self.domain_references),
            "instructions": list(self.instructions),
        }


ReviewerPacket: TypeAlias = GroundTruthReviewerPacket | ActionReviewerPacket


@dataclass(frozen=True, slots=True)
class EvidenceResolutionEntry:
    evidence_reference: str
    resolution_record: str

    def _as_dict(self) -> dict[str, str]:
        return {
            "evidence_reference": self.evidence_reference,
            "resolution_record": self.resolution_record,
        }


@dataclass(frozen=True, slots=True)
class EvidenceResolutionCatalog:
    schema: str
    version: str
    entries: tuple[EvidenceResolutionEntry, ...]
    digest: str

    def _payload_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "version": self.version,
            "entries": [entry._as_dict() for entry in self.entries],
        }

    def _as_dict(self) -> dict[str, object]:
        return {**self._payload_dict(), "digest": self.digest}


@dataclass(frozen=True, slots=True)
class EvidenceResolutionDiagnostics:
    ground_truth: tuple[str, ...]
    expected_action: tuple[str, ...]
    provenance: tuple[str, ...]
    privacy: tuple[str, ...]
    licensing: tuple[str, ...]
    provider_authorization: tuple[str, ...]

    def _as_dict(self) -> dict[str, list[str]]:
        return {
            "ground_truth": list(self.ground_truth),
            "expected_action": list(self.expected_action),
            "provenance": list(self.provenance),
            "privacy": list(self.privacy),
            "licensing": list(self.licensing),
            "provider_authorization": list(self.provider_authorization),
        }


@dataclass(frozen=True, slots=True)
class CaseReviewProgress:
    case_id: str
    specimen_id: str
    ground_truth_status: str
    action_status: str
    privacy_state: str
    licensing_state: str
    provider_authorization_state: str
    provenance_ready: bool
    review_provenance_ready: bool
    blockers: tuple[str, ...]
    unresolved_evidence: EvidenceResolutionDiagnostics

    def _as_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "specimen_id": self.specimen_id,
            "ground_truth_status": self.ground_truth_status,
            "action_status": self.action_status,
            "adjudication_needed": {
                "ground_truth": (
                    self.ground_truth_status == "disagreement_awaiting_adjudication"
                ),
                "expected_action": (
                    self.action_status == "disagreement_awaiting_adjudication"
                ),
            },
            "provider_eligibility": {
                "privacy": self.privacy_state,
                "licensing": self.licensing_state,
                "provider_authorization": self.provider_authorization_state,
            },
            "provenance_ready": self.provenance_ready,
            "review_provenance_ready": self.review_provenance_ready,
            "blockers": list(self.blockers),
            "unresolved_evidence": self.unresolved_evidence._as_dict(),
        }


@dataclass(frozen=True, slots=True)
class ReviewProgressReport:
    schema: str
    version: str
    evidence_catalog_digest: str
    aggregate_blockers: tuple[str, ...]
    cases: tuple[CaseReviewProgress, ...]

    @property
    def review_provenance_ready(self) -> bool:
        return (
            not self.aggregate_blockers
            and bool(self.cases)
            and all(case.review_provenance_ready for case in self.cases)
        )

    def _as_dict(self) -> dict[str, object]:
        ground_truth_counts = {state: 0 for state in GROUND_TRUTH_PROGRESS_STATES}
        action_counts = {state: 0 for state in ACTION_PROGRESS_STATES}
        eligibility_counts = {
            field: {state: 0 for state in sorted(ELIGIBILITY_STATES)}
            for field in ELIGIBILITY_FIELDS
        }
        ground_truth_adjudications = 0
        action_adjudications = 0
        for case in self.cases:
            ground_truth_counts[case.ground_truth_status] += 1
            action_counts[case.action_status] += 1
            eligibility_counts["privacy"][case.privacy_state] += 1
            eligibility_counts["licensing"][case.licensing_state] += 1
            eligibility_counts["provider_authorization"][case.provider_authorization_state] += 1
            if case.ground_truth_status == "disagreement_awaiting_adjudication":
                ground_truth_adjudications += 1
            if case.action_status == "disagreement_awaiting_adjudication":
                action_adjudications += 1
        return {
            "schema": self.schema,
            "version": self.version,
            "evidence_catalog_digest": self.evidence_catalog_digest,
            "aggregate_blockers": list(self.aggregate_blockers),
            "total_cases": len(self.cases),
            "ground_truth_status_counts": ground_truth_counts,
            "expected_action_status_counts": action_counts,
            "adjudication_needed_counts": {
                "ground_truth": ground_truth_adjudications,
                "expected_action": action_adjudications,
            },
            "provider_eligibility_state_counts": eligibility_counts,
            "review_provenance_ready": self.review_provenance_ready,
            "cases": [case._as_dict() for case in self.cases],
        }


@dataclass(frozen=True, slots=True)
class CaseReviewReconciliation:
    case_id: str
    specimen_id: str
    candidate_identity: IdentityDecision | None
    resolved_identity: IdentityDecision | None
    identity_status: str
    candidate_expected_action: str | None
    resolved_expected_action: str | None
    expected_action_status: str
    ground_truth_evidence_references: tuple[str, ...]
    expected_action_evidence_references: tuple[str, ...]
    provenance_evidence_references: tuple[str, ...]
    privacy_state: str
    privacy_evidence_references: tuple[str, ...]
    licensing_state: str
    licensing_evidence_references: tuple[str, ...]
    provider_authorization_state: str
    provider_authorization_evidence_references: tuple[str, ...]
    review_provenance_reconciled: bool
    blockers: tuple[str, ...]
    unresolved_evidence: EvidenceResolutionDiagnostics

    def _as_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "specimen_id": self.specimen_id,
            "candidate_identity": (
                None if self.candidate_identity is None else self.candidate_identity.as_dict()
            ),
            "resolved_identity": (
                None if self.resolved_identity is None else self.resolved_identity.as_dict()
            ),
            "identity_reconciliation_status": self.identity_status,
            "candidate_expected_action": self.candidate_expected_action,
            "resolved_expected_action": self.resolved_expected_action,
            "expected_action_reconciliation_status": self.expected_action_status,
            "evidence_links": {
                "ground_truth": list(self.ground_truth_evidence_references),
                "expected_action": list(self.expected_action_evidence_references),
                "provenance": list(self.provenance_evidence_references),
                "provider_eligibility": {
                    "privacy": {
                        "state": self.privacy_state,
                        "evidence_references": list(self.privacy_evidence_references),
                    },
                    "licensing": {
                        "state": self.licensing_state,
                        "evidence_references": list(self.licensing_evidence_references),
                    },
                    "provider_authorization": {
                        "state": self.provider_authorization_state,
                        "evidence_references": list(
                            self.provider_authorization_evidence_references
                        ),
                    },
                },
            },
            "review_provenance_reconciled": self.review_provenance_reconciled,
            "blockers": list(self.blockers),
            "unresolved_evidence": self.unresolved_evidence._as_dict(),
        }


@dataclass(frozen=True, slots=True)
class ReviewReconciliationHandoff:
    schema: str
    version: str
    evidence_catalog_digest: str
    unit4_review_provenance_ready: bool
    aggregate_blockers: tuple[str, ...]
    cases: tuple[CaseReviewReconciliation, ...]

    @property
    def review_provenance_reconciled(self) -> bool:
        return (
            self.unit4_review_provenance_ready
            and not self.aggregate_blockers
            and bool(self.cases)
            and all(
                case.review_provenance_reconciled
                and case.identity_status == "matched"
                and case.expected_action_status == "matched"
                for case in self.cases
            )
        )

    @property
    def blockers(self) -> tuple[str, ...]:
        case_blockers = tuple(
            f"{case.case_id}:{blocker}"
            for case in self.cases
            for blocker in case.blockers
        )
        return self.aggregate_blockers + case_blockers

    def _as_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "version": self.version,
            "scope": "review_provenance_reconciliation_only",
            "evidence_catalog_digest": self.evidence_catalog_digest,
            "unit4_review_provenance_ready": self.unit4_review_provenance_ready,
            "aggregate_blockers": list(self.aggregate_blockers),
            "review_provenance_reconciled": self.review_provenance_reconciled,
            "authoring_mutation_applied": False,
            "freeze_preparation_authorized": False,
            "benchmark_execution_approved": False,
            "blockers": list(self.blockers),
            "cases": [case._as_dict() for case in self.cases],
        }


def load_review_execution_record(
    path: str | Path, authoring_state: Mapping[str, object]
) -> ReviewExecutionRecord:
    """Load and strictly validate a UTF-8 JSON review execution record."""
    record_path = Path(path)
    try:
        payload = json.loads(
            record_path.read_text(encoding="utf-8"),
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except DesktopAcceptanceReviewError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DesktopAcceptanceReviewError(
            f"cannot read review execution record: {error}"
        ) from error
    return validate_review_execution_record(payload, authoring_state)


def validate_review_execution_record(
    payload: object, authoring_state: Mapping[str, object]
) -> ReviewExecutionRecord:
    """Return an immutable, deterministically ordered record or fail closed."""
    authoring_roster = _authoring_roster(authoring_state)
    root = _require_mapping(payload, "review execution record")
    _require_exact_keys(root, {"schema", "version", "cases"}, "review execution record")
    if root["schema"] != REVIEW_EXECUTION_SCHEMA or root["version"] != REVIEW_EXECUTION_VERSION:
        raise DesktopAcceptanceReviewError("unsupported review execution schema/version")

    raw_cases = root["cases"]
    if not isinstance(raw_cases, list):
        raise DesktopAcceptanceReviewError("cases must be an array")

    cases: list[ReviewCaseRecord] = []
    seen_case_ids: set[str] = set()
    for index, raw_case in enumerate(raw_cases):
        case = _validate_case(raw_case, f"cases[{index}]", authoring_roster)
        if case.case_id in seen_case_ids:
            raise DesktopAcceptanceReviewError(f"duplicate case record: {case.case_id}")
        seen_case_ids.add(case.case_id)
        cases.append(case)

    expected = set(authoring_roster)
    missing = sorted(expected - seen_case_ids)
    unsupported = sorted(seen_case_ids - expected)
    if missing or unsupported:
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unsupported:
            details.append("unsupported " + ", ".join(unsupported))
        raise DesktopAcceptanceReviewError("case roster mismatch: " + "; ".join(details))

    return ReviewExecutionRecord(
        schema=REVIEW_EXECUTION_SCHEMA,
        version=REVIEW_EXECUTION_VERSION,
        cases=tuple(sorted(cases, key=lambda case: case.case_id)),
    )


def normalized_review_execution_json(
    record: ReviewExecutionRecord, authoring_state: Mapping[str, object]
) -> str:
    """Serialize a validated record in one deterministic JSON representation."""
    if not isinstance(record, ReviewExecutionRecord):
        raise TypeError("record must be a ReviewExecutionRecord")
    validated = validate_review_execution_record(record.as_dict(), authoring_state)
    return json.dumps(
        validated.as_dict(),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n"


def generate_ground_truth_packet(
    authoring_state: Mapping[str, object],
    case_id: str,
    reviewer_id: str,
    evidence_references: Sequence[str],
) -> GroundTruthReviewerPacket:
    """Generate one deterministic packet without exposing roster answers."""
    authoring_case = _authoring_case(authoring_state, case_id)
    payload = {
        "schema": REVIEW_PACKET_SCHEMA,
        "version": REVIEW_PACKET_VERSION,
        "track": GROUND_TRUTH_TRACK,
        "case_id": case_id,
        "specimen_id": authoring_case["specimen_id"],
        "reviewer_id": reviewer_id,
        "evidence_references": _copy_supplied_references(evidence_references),
        "identity_fields": list(IDENTITY_FIELDS),
        "instructions": list(GROUND_TRUTH_INSTRUCTIONS),
    }
    packet = validate_reviewer_packet(payload, authoring_state)
    assert isinstance(packet, GroundTruthReviewerPacket)
    return packet


def generate_action_packet(
    authoring_state: Mapping[str, object],
    execution_record: ReviewExecutionRecord,
    case_id: str,
    reviewer_id: str,
    domain_references: Sequence[str],
) -> ActionReviewerPacket:
    """Generate an action packet only from independently resolved ground truth."""
    validated_execution = _revalidate_execution_record(execution_record, authoring_state)
    execution_case = _execution_case(validated_execution, case_id)
    resolved_identity = _resolved_ground_truth(execution_case.ground_truth_review, case_id)
    payload = {
        "schema": REVIEW_PACKET_SCHEMA,
        "version": REVIEW_PACKET_VERSION,
        "track": ACTION_TRACK,
        "case_id": case_id,
        "specimen_id": execution_case.specimen_id,
        "reviewer_id": reviewer_id,
        "resolved_identity": resolved_identity.as_dict(),
        "domain_references": _copy_supplied_references(domain_references),
        "instructions": list(ACTION_INSTRUCTIONS),
    }
    packet = validate_reviewer_packet(payload, authoring_state, validated_execution)
    assert isinstance(packet, ActionReviewerPacket)
    return packet


def validate_reviewer_packet(
    payload: object,
    authoring_state: Mapping[str, object],
    execution_record: ReviewExecutionRecord | None = None,
) -> ReviewerPacket:
    """Strictly validate a reviewer-facing packet and its blinding boundary."""
    raw = _require_mapping(payload, "reviewer packet")
    if raw.get("schema") != REVIEW_PACKET_SCHEMA or raw.get("version") != REVIEW_PACKET_VERSION:
        raise DesktopAcceptanceReviewError("unsupported review packet schema/version")
    track = raw.get("track")
    if track == GROUND_TRUTH_TRACK:
        return _validate_ground_truth_packet(raw, authoring_state)
    if track == ACTION_TRACK:
        if execution_record is None:
            raise DesktopAcceptanceReviewError(
                "action packet validation requires a validated execution record"
            )
        validated_execution = _revalidate_execution_record(execution_record, authoring_state)
        return _validate_action_packet(raw, authoring_state, validated_execution)
    raise DesktopAcceptanceReviewError("reviewer packet track is unsupported")


def normalized_reviewer_packet_json(
    packet: ReviewerPacket,
    authoring_state: Mapping[str, object],
    execution_record: ReviewExecutionRecord | None = None,
) -> str:
    """Revalidate and serialize one packet in deterministic machine form."""
    if not isinstance(packet, (GroundTruthReviewerPacket, ActionReviewerPacket)):
        raise TypeError("packet must be a reviewer packet")
    validated = validate_reviewer_packet(packet.as_dict(), authoring_state, execution_record)
    return _normalized_json(validated.as_dict())


def validate_evidence_resolution_catalog(
    payload: object, repository_root: str | Path
) -> EvidenceResolutionCatalog:
    """Validate an explicit local evidence-resolution catalog without dereferencing evidence."""
    root = _require_mapping(payload, "evidence-resolution catalog")
    _require_exact_keys(
        root, {"schema", "version", "entries"}, "evidence-resolution catalog"
    )
    if (
        root["schema"] != EVIDENCE_RESOLUTION_SCHEMA
        or root["version"] != EVIDENCE_RESOLUTION_VERSION
    ):
        raise DesktopAcceptanceReviewError(
            "unsupported evidence-resolution catalog schema/version"
        )
    raw_entries = root["entries"]
    if not isinstance(raw_entries, list):
        raise DesktopAcceptanceReviewError(
            "evidence-resolution catalog entries must be an array"
        )
    validated_root = _validated_repository_root(repository_root)
    entries: list[EvidenceResolutionEntry] = []
    seen: set[str] = set()
    for index, value in enumerate(raw_entries):
        label = f"evidence-resolution catalog entries[{index}]"
        raw_entry = _require_mapping(value, label)
        _require_exact_keys(
            raw_entry, {"evidence_reference", "resolution_record"}, label
        )
        evidence_reference = _validate_evidence_reference(
            raw_entry["evidence_reference"], f"{label}.evidence_reference"
        )
        if evidence_reference in seen:
            raise DesktopAcceptanceReviewError(
                f"duplicate evidence-resolution reference: {evidence_reference}"
            )
        seen.add(evidence_reference)
        resolution_record = _validate_resolution_record(
            raw_entry["resolution_record"], validated_root, label
        )
        entries.append(EvidenceResolutionEntry(evidence_reference, resolution_record))
    entries.sort(key=lambda entry: (entry.evidence_reference, entry.resolution_record))
    canonical_payload = {
        "schema": EVIDENCE_RESOLUTION_SCHEMA,
        "version": EVIDENCE_RESOLUTION_VERSION,
        "entries": [entry._as_dict() for entry in entries],
    }
    digest = hashlib.sha256(_canonical_json(canonical_payload).encode("utf-8")).hexdigest()
    return EvidenceResolutionCatalog(
        EVIDENCE_RESOLUTION_SCHEMA,
        EVIDENCE_RESOLUTION_VERSION,
        tuple(entries),
        digest,
    )


def normalized_evidence_resolution_catalog_json(
    catalog: EvidenceResolutionCatalog, repository_root: str | Path
) -> str:
    """Revalidate and serialize a catalog with its canonical payload digest."""
    validated = _revalidate_evidence_resolution_catalog(catalog, repository_root)
    return _normalized_json(validated._as_dict())


def build_review_progress_report(
    authoring_state: Mapping[str, object],
    execution_record: ReviewExecutionRecord,
    evidence_catalog: EvidenceResolutionCatalog,
    repository_root: str | Path,
) -> ReviewProgressReport:
    """Derive immutable review/provenance progress without changing source state."""
    validated_authoring = validate_authoring_plan(authoring_state)
    validated_execution = _revalidate_execution_record(
        execution_record, validated_authoring
    )
    validated_catalog = _revalidate_evidence_resolution_catalog(
        evidence_catalog, repository_root
    )
    resolved_references = {
        entry.evidence_reference for entry in validated_catalog.entries
    }
    authoring_cases = _authoring_cases_for_reporting(validated_authoring)
    cases = tuple(
        _derive_case_progress(
            authoring_cases[case.case_id], case, resolved_references
        )
        for case in validated_execution.cases
    )
    aggregate_blockers = ()
    if len(cases) != DESKTOP_ACCEPTANCE_V1_CASE_COUNT:
        aggregate_blockers = (
            "corpus_case_count_mismatch:"
            f"expected={DESKTOP_ACCEPTANCE_V1_CASE_COUNT}:actual={len(cases)}",
        )
    return ReviewProgressReport(
        REVIEW_PROGRESS_SCHEMA,
        REVIEW_PROGRESS_VERSION,
        validated_catalog.digest,
        aggregate_blockers,
        cases,
    )


def normalized_review_progress_json(
    report: ReviewProgressReport,
    authoring_state: Mapping[str, object],
    execution_record: ReviewExecutionRecord,
    evidence_catalog: EvidenceResolutionCatalog,
    repository_root: str | Path,
) -> str:
    """Revalidate and serialize one progress report deterministically."""
    return _normalized_json(
        validated_review_progress_dict(
            report,
            authoring_state,
            execution_record,
            evidence_catalog,
            repository_root,
        )
    )


def validated_review_progress_dict(
    report: ReviewProgressReport,
    authoring_state: Mapping[str, object],
    execution_record: ReviewExecutionRecord,
    evidence_catalog: EvidenceResolutionCatalog,
    repository_root: str | Path,
) -> dict[str, object]:
    """Return a machine-readable report only after source-state revalidation."""
    validated = _revalidate_progress_report(
        report,
        authoring_state,
        execution_record,
        evidence_catalog,
        repository_root,
    )
    return validated._as_dict()


def render_review_progress_report(
    report: ReviewProgressReport,
    authoring_state: Mapping[str, object],
    execution_record: ReviewExecutionRecord,
    evidence_catalog: EvidenceResolutionCatalog,
    repository_root: str | Path,
) -> str:
    """Render the same validated progress state as concise deterministic text."""
    data = validated_review_progress_dict(
        report,
        authoring_state,
        execution_record,
        evidence_catalog,
        repository_root,
    )
    ready_text = "yes" if data["review_provenance_ready"] else "no"
    lines = [
        "Desktop acceptance review/provenance progress",
        f"Overall ready: {ready_text}",
        f"Total cases: {data['total_cases']}",
        f"Evidence catalog digest: {data['evidence_catalog_digest']}",
        "Aggregate blockers: "
        + (",".join(data["aggregate_blockers"]) or "none"),
        "Ground truth: "
        + _format_counts(data["ground_truth_status_counts"], GROUND_TRUTH_PROGRESS_STATES),
        "Expected action: "
        + _format_counts(data["expected_action_status_counts"], ACTION_PROGRESS_STATES),
    ]
    adjudications = data["adjudication_needed_counts"]
    assert isinstance(adjudications, Mapping)
    lines.append(
        "Adjudication needed: "
        f"ground_truth={adjudications['ground_truth']}, "
        f"expected_action={adjudications['expected_action']}"
    )
    eligibility_counts = data["provider_eligibility_state_counts"]
    assert isinstance(eligibility_counts, Mapping)
    for field in ELIGIBILITY_FIELDS:
        counts = eligibility_counts[field]
        assert isinstance(counts, Mapping)
        lines.append(
            f"Eligibility {field}: "
            + _format_counts(counts, tuple(sorted(ELIGIBILITY_STATES)))
        )
    lines.append("Cases:")
    raw_cases = data["cases"]
    assert isinstance(raw_cases, list)
    for case in raw_cases:
        assert isinstance(case, Mapping)
        blockers = case["blockers"]
        assert isinstance(blockers, list)
        blocker_text = ",".join(blockers) if blockers else "none"
        readiness = "ready" if case["review_provenance_ready"] else "blocked"
        lines.append(
            f"- {case['case_id']} {case['specimen_id']}: {readiness}; "
            f"gt={case['ground_truth_status']}; action={case['action_status']}; "
            f"blockers={blocker_text}"
        )
    return "\n".join(lines) + "\n"


def build_review_reconciliation_handoff(
    authoring_state: Mapping[str, object],
    execution_record: ReviewExecutionRecord,
    evidence_catalog: EvidenceResolutionCatalog,
    repository_root: str | Path,
) -> ReviewReconciliationHandoff:
    """Derive reconciliation diagnostics without applying authoring mutations."""
    progress = build_review_progress_report(
        authoring_state, execution_record, evidence_catalog, repository_root
    )
    validated_authoring = validate_authoring_plan(authoring_state)
    validated_execution = _revalidate_execution_record(
        execution_record, validated_authoring
    )
    authoring_cases = _authoring_cases_for_reporting(validated_authoring)
    progress_cases = {case.case_id: case for case in progress.cases}
    cases = tuple(
        _derive_case_reconciliation(
            authoring_cases[execution_case.case_id],
            execution_case,
            progress_cases[execution_case.case_id],
        )
        for execution_case in validated_execution.cases
    )
    return ReviewReconciliationHandoff(
        REVIEW_RECONCILIATION_SCHEMA,
        REVIEW_RECONCILIATION_VERSION,
        progress.evidence_catalog_digest,
        progress.review_provenance_ready,
        progress.aggregate_blockers,
        cases,
    )


def validated_review_reconciliation_dict(
    handoff: ReviewReconciliationHandoff,
    authoring_state: Mapping[str, object],
    execution_record: ReviewExecutionRecord,
    evidence_catalog: EvidenceResolutionCatalog,
    repository_root: str | Path,
) -> dict[str, object]:
    """Return a reconciliation artifact only after full source revalidation."""
    validated = _revalidate_reconciliation_handoff(
        handoff,
        authoring_state,
        execution_record,
        evidence_catalog,
        repository_root,
    )
    return validated._as_dict()


def normalized_review_reconciliation_json(
    handoff: ReviewReconciliationHandoff,
    authoring_state: Mapping[str, object],
    execution_record: ReviewExecutionRecord,
    evidence_catalog: EvidenceResolutionCatalog,
    repository_root: str | Path,
) -> str:
    """Serialize one revalidated reconciliation artifact deterministically."""
    return _normalized_json(
        validated_review_reconciliation_dict(
            handoff,
            authoring_state,
            execution_record,
            evidence_catalog,
            repository_root,
        )
    )


def _validate_ground_truth_packet(
    raw: Mapping[str, object], authoring_state: Mapping[str, object]
) -> GroundTruthReviewerPacket:
    label = "ground-truth packet"
    _require_exact_keys(
        raw,
        {
            "schema",
            "version",
            "track",
            "case_id",
            "specimen_id",
            "reviewer_id",
            "evidence_references",
            "identity_fields",
            "instructions",
        },
        label,
    )
    case_id, specimen_id, reviewer_id = _validate_packet_header(
        raw, authoring_state, label
    )
    evidence = _validate_evidence_references(
        raw["evidence_references"], f"{label}.evidence_references", required=True
    )
    identity_fields = _require_exact_string_list(
        raw["identity_fields"], IDENTITY_FIELDS, f"{label}.identity_fields"
    )
    instructions = _require_exact_string_list(
        raw["instructions"], GROUND_TRUTH_INSTRUCTIONS, f"{label}.instructions"
    )
    packet = GroundTruthReviewerPacket(
        REVIEW_PACKET_SCHEMA,
        REVIEW_PACKET_VERSION,
        GROUND_TRUTH_TRACK,
        case_id,
        specimen_id,
        reviewer_id,
        evidence,
        identity_fields,
        instructions,
    )
    return packet


def _validate_action_packet(
    raw: Mapping[str, object],
    authoring_state: Mapping[str, object],
    execution_record: ReviewExecutionRecord,
) -> ActionReviewerPacket:
    label = "action packet"
    _require_exact_keys(
        raw,
        {
            "schema",
            "version",
            "track",
            "case_id",
            "specimen_id",
            "reviewer_id",
            "resolved_identity",
            "domain_references",
            "instructions",
        },
        label,
    )
    case_id, specimen_id, reviewer_id = _validate_packet_header(
        raw, authoring_state, label
    )
    execution_case = _execution_case(execution_record, case_id)
    expected_identity = _resolved_ground_truth(execution_case.ground_truth_review, case_id)
    supplied_identity = _validate_decision(
        raw["resolved_identity"], "identity", f"{label}.resolved_identity"
    )
    assert isinstance(supplied_identity, IdentityDecision)
    if supplied_identity != expected_identity:
        raise DesktopAcceptanceReviewError(
            f"{label}.resolved_identity does not match completed ground truth"
        )
    domain_references = _validate_evidence_references(
        raw["domain_references"], f"{label}.domain_references", required=True
    )
    instructions = _require_exact_string_list(
        raw["instructions"], ACTION_INSTRUCTIONS, f"{label}.instructions"
    )
    packet = ActionReviewerPacket(
        REVIEW_PACKET_SCHEMA,
        REVIEW_PACKET_VERSION,
        ACTION_TRACK,
        case_id,
        specimen_id,
        reviewer_id,
        supplied_identity,
        domain_references,
        instructions,
    )
    return packet


def _validate_packet_header(
    raw: Mapping[str, object], authoring_state: Mapping[str, object], label: str
) -> tuple[str, str, str]:
    case_id = _require_matching_text(raw["case_id"], _CASE_ID, f"{label}.case_id")
    authoring_case = _authoring_case(authoring_state, case_id)
    specimen_id = _require_matching_text(
        raw["specimen_id"], _SPECIMEN_ID, f"{label}.specimen_id"
    )
    if specimen_id != authoring_case["specimen_id"]:
        raise DesktopAcceptanceReviewError(f"{label}.specimen_id does not match authoring state")
    reviewer_id = _validate_reviewer_id(raw["reviewer_id"], f"{label}.reviewer_id")
    return case_id, specimen_id, reviewer_id


def _authoring_case(
    authoring_state: Mapping[str, object], case_id: str
) -> Mapping[str, object]:
    _authoring_roster(authoring_state)
    raw_cases = authoring_state["cases"]
    assert isinstance(raw_cases, list)
    for raw_case in raw_cases:
        assert isinstance(raw_case, Mapping)
        if raw_case["case_id"] == case_id:
            return raw_case
    raise DesktopAcceptanceReviewError(f"case is not present in authoring state: {case_id}")


def _execution_case(record: ReviewExecutionRecord, case_id: str) -> ReviewCaseRecord:
    for case in record.cases:
        if case.case_id == case_id:
            return case
    raise DesktopAcceptanceReviewError(f"case is not present in execution record: {case_id}")


def _resolved_ground_truth(track: ReviewTrack, case_id: str) -> IdentityDecision:
    if track.state != "complete":
        raise DesktopAcceptanceReviewError(
            f"{case_id}.ground_truth_review must be complete before action packet generation"
        )
    if track.adjudication is not None:
        decision = track.adjudication.decision
    else:
        decision = track.submissions[0].decision
    if not isinstance(decision, IdentityDecision):
        raise DesktopAcceptanceReviewError(f"{case_id}.ground_truth_review has invalid identity")
    return decision


def _revalidate_execution_record(
    record: ReviewExecutionRecord, authoring_state: Mapping[str, object]
) -> ReviewExecutionRecord:
    if not isinstance(record, ReviewExecutionRecord):
        raise DesktopAcceptanceReviewError("execution record must be validated and immutable")
    return validate_review_execution_record(record.as_dict(), authoring_state)


def _copy_supplied_references(value: Sequence[str]) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise DesktopAcceptanceReviewError("evidence references must be a supplied sequence")
    return list(value)


def _require_exact_string_list(
    value: object, expected: tuple[str, ...], label: str
) -> tuple[str, ...]:
    if not isinstance(value, list) or tuple(value) != expected:
        raise DesktopAcceptanceReviewError(f"{label} does not match the packet contract")
    return expected


def _authoring_cases_for_reporting(
    authoring_state: Mapping[str, object],
) -> dict[str, Mapping[str, object]]:
    roster = _authoring_roster(authoring_state)
    raw_cases = authoring_state["cases"]
    assert isinstance(raw_cases, list)
    cases: dict[str, Mapping[str, object]] = {}
    for index, value in enumerate(raw_cases):
        case = _require_mapping(value, f"authoring state cases[{index}]")
        case_id = case.get("case_id")
        assert isinstance(case_id, str) and case_id in roster
        if "candidate_identity" not in case or "expected_action" not in case:
            raise DesktopAcceptanceReviewError(
                f"authoring state {case_id} lacks candidate review values"
            )
        provenance = _require_mapping(
            case.get("provenance"), f"authoring state {case_id}.provenance"
        )
        _require_exact_keys(
            provenance,
            {"ownership_or_source", "evidence_reference", "notes"},
            f"authoring state {case_id}.provenance",
        )
        for field in ("ownership_or_source", "evidence_reference", "notes"):
            if not isinstance(provenance[field], str):
                raise DesktopAcceptanceReviewError(
                    f"authoring state {case_id}.provenance.{field} must be text"
                )
        cases[case_id] = case
    return cases


def _derive_case_progress(
    authoring_case: Mapping[str, object],
    execution_case: ReviewCaseRecord,
    resolved_references: set[str],
) -> CaseReviewProgress:
    ground_truth_status = _track_progress_status(execution_case.ground_truth_review)
    if execution_case.ground_truth_review.state != "complete":
        action_status = "blocked_by_ground_truth"
    else:
        action_status = _track_progress_status(execution_case.action_review)

    blockers: list[str] = []
    if ground_truth_status != "complete":
        blockers.append(f"ground_truth_{ground_truth_status}")
    elif _resolved_track_decision(execution_case.ground_truth_review) != _candidate_identity(
        authoring_case
    ):
        blockers.append("ground_truth_reconciliation_mismatch")

    if action_status != "complete":
        blockers.append(f"action_{action_status}")
    elif _resolved_track_decision(execution_case.action_review) != authoring_case.get(
        "expected_action"
    ):
        blockers.append("action_reconciliation_mismatch")

    provenance = _require_mapping(
        authoring_case.get("provenance"),
        f"authoring state {execution_case.case_id}.provenance",
    )
    ownership_ready = _nonempty_authoring_text(provenance["ownership_or_source"])
    evidence_ready = _nonempty_authoring_text(provenance["evidence_reference"])
    if not ownership_ready:
        blockers.append("provenance_ownership_or_source_unresolved")
    if not evidence_ready:
        blockers.append("provenance_evidence_unresolved")
    provenance_ready = ownership_ready and evidence_ready

    eligibility_states: dict[str, str] = {}
    for field in ELIGIBILITY_FIELDS:
        state = getattr(execution_case.provider_eligibility, field).state
        eligibility_states[field] = state
        if state != "approved":
            blockers.append(f"{field}_{state}")

    ground_truth_evidence = (
        _track_evidence_references(execution_case.ground_truth_review)
        if ground_truth_status == "complete"
        else ()
    )
    action_evidence = (
        _track_evidence_references(execution_case.action_review)
        if action_status == "complete"
        else ()
    )
    provenance_evidence = (
        (provenance["evidence_reference"],) if evidence_ready else ()
    )
    unresolved_by_category = {
        "ground_truth": _unresolved_references(
            ground_truth_evidence, resolved_references
        ),
        "expected_action": _unresolved_references(
            action_evidence, resolved_references
        ),
        "provenance": _unresolved_references(
            provenance_evidence, resolved_references
        ),
    }
    for field in ELIGIBILITY_FIELDS:
        decision = getattr(execution_case.provider_eligibility, field)
        references = decision.evidence_references if decision.state == "approved" else ()
        unresolved_by_category[field] = _unresolved_references(
            references, resolved_references
        )
    for category in (
        "ground_truth",
        "expected_action",
        "provenance",
        "privacy",
        "licensing",
        "provider_authorization",
    ):
        if unresolved_by_category[category]:
            blockers.append(f"{category}_evidence_unresolved")

    unresolved_evidence = EvidenceResolutionDiagnostics(
        ground_truth=unresolved_by_category["ground_truth"],
        expected_action=unresolved_by_category["expected_action"],
        provenance=unresolved_by_category["provenance"],
        privacy=unresolved_by_category["privacy"],
        licensing=unresolved_by_category["licensing"],
        provider_authorization=unresolved_by_category["provider_authorization"],
    )

    return CaseReviewProgress(
        case_id=execution_case.case_id,
        specimen_id=execution_case.specimen_id,
        ground_truth_status=ground_truth_status,
        action_status=action_status,
        privacy_state=eligibility_states["privacy"],
        licensing_state=eligibility_states["licensing"],
        provider_authorization_state=eligibility_states["provider_authorization"],
        provenance_ready=provenance_ready,
        review_provenance_ready=not blockers,
        blockers=tuple(blockers),
        unresolved_evidence=unresolved_evidence,
    )


def _unresolved_references(
    references: Sequence[str], resolved_references: set[str]
) -> tuple[str, ...]:
    return tuple(sorted(set(references) - resolved_references))


def _track_progress_status(track: ReviewTrack) -> str:
    if track.state == "complete":
        return "complete"
    if not track.submissions:
        return "unassigned"
    if len(track.submissions) == 1:
        return "awaiting_submissions"
    if (
        track.submissions[0].decision != track.submissions[1].decision
        and track.adjudication is None
    ):
        return "disagreement_awaiting_adjudication"
    return "unresolved"


def _resolved_track_decision(track: ReviewTrack) -> ReviewDecision:
    if track.state != "complete":
        raise DesktopAcceptanceReviewError("cannot resolve an incomplete review track")
    if track.adjudication is not None:
        return track.adjudication.decision
    return track.submissions[0].decision


def _candidate_identity(authoring_case: Mapping[str, object]) -> IdentityDecision | None:
    identity = authoring_case.get("candidate_identity")
    if not isinstance(identity, Mapping) or set(identity) != set(IDENTITY_FIELDS):
        return None
    values = tuple(identity.get(field) for field in IDENTITY_FIELDS)
    if not all(_nonempty_authoring_text(value) for value in values):
        return None
    country, denomination, year = values
    assert isinstance(country, str) and isinstance(denomination, str) and isinstance(year, str)
    return IdentityDecision(country, denomination, year)


def _nonempty_authoring_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _revalidate_progress_report(
    report: ReviewProgressReport,
    authoring_state: Mapping[str, object],
    execution_record: ReviewExecutionRecord,
    evidence_catalog: EvidenceResolutionCatalog,
    repository_root: str | Path,
) -> ReviewProgressReport:
    if not isinstance(report, ReviewProgressReport):
        raise TypeError("report must be a ReviewProgressReport")
    expected = build_review_progress_report(
        authoring_state, execution_record, evidence_catalog, repository_root
    )
    if report != expected:
        raise DesktopAcceptanceReviewError(
            "review progress report does not match supplied authoring/execution state"
        )
    return expected


def _derive_case_reconciliation(
    authoring_case: Mapping[str, object],
    execution_case: ReviewCaseRecord,
    progress_case: CaseReviewProgress,
) -> CaseReviewReconciliation:
    candidate_identity = _candidate_identity(authoring_case)
    if progress_case.ground_truth_status == "complete":
        resolved_identity = _resolved_track_decision(
            execution_case.ground_truth_review
        )
        assert isinstance(resolved_identity, IdentityDecision)
        identity_status = (
            "matched" if resolved_identity == candidate_identity else "mismatched"
        )
    else:
        resolved_identity = None
        identity_status = "blocked"

    candidate_action_value = authoring_case.get("expected_action")
    candidate_action = (
        candidate_action_value
        if isinstance(candidate_action_value, str)
        and candidate_action_value in EXPECTED_ACTIONS
        else None
    )
    if progress_case.action_status == "complete":
        resolved_action = _resolved_track_decision(execution_case.action_review)
        assert isinstance(resolved_action, str)
        action_status = "matched" if resolved_action == candidate_action else "mismatched"
    else:
        resolved_action = None
        action_status = "blocked"

    provenance = _require_mapping(
        authoring_case.get("provenance"),
        f"authoring state {execution_case.case_id}.provenance",
    )
    provenance_reference = provenance["evidence_reference"]
    provenance_references = (
        (provenance_reference,)
        if _nonempty_authoring_text(provenance_reference)
        else ()
    )
    eligibility = execution_case.provider_eligibility
    return CaseReviewReconciliation(
        case_id=execution_case.case_id,
        specimen_id=execution_case.specimen_id,
        candidate_identity=candidate_identity,
        resolved_identity=resolved_identity,
        identity_status=identity_status,
        candidate_expected_action=candidate_action,
        resolved_expected_action=resolved_action,
        expected_action_status=action_status,
        ground_truth_evidence_references=_track_evidence_references(
            execution_case.ground_truth_review
        ),
        expected_action_evidence_references=_track_evidence_references(
            execution_case.action_review
        ),
        provenance_evidence_references=provenance_references,
        privacy_state=eligibility.privacy.state,
        privacy_evidence_references=eligibility.privacy.evidence_references,
        licensing_state=eligibility.licensing.state,
        licensing_evidence_references=eligibility.licensing.evidence_references,
        provider_authorization_state=eligibility.provider_authorization.state,
        provider_authorization_evidence_references=(
            eligibility.provider_authorization.evidence_references
        ),
        review_provenance_reconciled=progress_case.review_provenance_ready,
        blockers=progress_case.blockers,
        unresolved_evidence=progress_case.unresolved_evidence,
    )


def _track_evidence_references(track: ReviewTrack) -> tuple[str, ...]:
    references = {
        reference
        for submission in track.submissions
        for reference in submission.evidence_references
    }
    if track.adjudication is not None:
        references.update(track.adjudication.evidence_references)
    return tuple(sorted(references))


def _revalidate_reconciliation_handoff(
    handoff: ReviewReconciliationHandoff,
    authoring_state: Mapping[str, object],
    execution_record: ReviewExecutionRecord,
    evidence_catalog: EvidenceResolutionCatalog,
    repository_root: str | Path,
) -> ReviewReconciliationHandoff:
    if not isinstance(handoff, ReviewReconciliationHandoff):
        raise TypeError("handoff must be a ReviewReconciliationHandoff")
    expected = build_review_reconciliation_handoff(
        authoring_state, execution_record, evidence_catalog, repository_root
    )
    if handoff != expected:
        raise DesktopAcceptanceReviewError(
            "review reconciliation handoff does not match supplied authoring/execution state"
        )
    return expected


def _format_counts(counts: object, states: tuple[str, ...]) -> str:
    mapping = _require_mapping(counts, "progress counts")
    return ", ".join(f"{state}={mapping[state]}" for state in states)


def _revalidate_evidence_resolution_catalog(
    catalog: EvidenceResolutionCatalog, repository_root: str | Path
) -> EvidenceResolutionCatalog:
    if not isinstance(catalog, EvidenceResolutionCatalog):
        raise TypeError("evidence_catalog must be an EvidenceResolutionCatalog")
    expected = validate_evidence_resolution_catalog(
        catalog._payload_dict(), repository_root
    )
    if catalog != expected:
        raise DesktopAcceptanceReviewError(
            "evidence-resolution catalog does not match its validated canonical form"
        )
    return expected


def _validated_repository_root(repository_root: str | Path) -> Path:
    try:
        root = Path(repository_root).resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise DesktopAcceptanceReviewError(
            f"evidence repository root is unavailable: {error}"
        ) from error
    if not root.is_dir():
        raise DesktopAcceptanceReviewError("evidence repository root must be a directory")
    return root


def _validate_resolution_record(
    value: object, repository_root: Path, label: str
) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise DesktopAcceptanceReviewError(
            f"{label}.resolution_record must be normalized non-empty text"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise DesktopAcceptanceReviewError(
            f"{label}.resolution_record contains control characters"
        )
    if (
        "\\" in value
        or "@" in value
        or "://" in value
        or _OBVIOUS_CREDENTIAL.search(value)
    ):
        raise DesktopAcceptanceReviewError(
            f"{label}.resolution_record must be a sanitized repository-relative path"
        )
    if value.startswith("/") or _WINDOWS_DRIVE_PATH.match(value):
        raise DesktopAcceptanceReviewError(
            f"{label}.resolution_record must be repository-relative"
        )
    lexical_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in lexical_parts):
        raise DesktopAcceptanceReviewError(
            f"{label}.resolution_record contains an unsafe path segment"
        )
    invalid_windows_characters = frozenset('<>:"|?*')
    reserved_windows_names = frozenset(
        {"CON", "PRN", "AUX", "NUL"}
        | {f"COM{number}" for number in range(1, 10)}
        | {f"LPT{number}" for number in range(1, 10)}
    )
    if any(
        part.endswith((".", " "))
        or any(character in invalid_windows_characters for character in part)
        or part.split(".", 1)[0].upper() in reserved_windows_names
        for part in lexical_parts
    ):
        raise DesktopAcceptanceReviewError(
            f"{label}.resolution_record contains a non-canonical Windows path segment"
        )
    path = PurePosixPath(value)
    if not any(value.startswith(root) for root in EVIDENCE_ATTESTATION_ROOTS):
        raise DesktopAcceptanceReviewError(
            f"{label}.resolution_record is outside permitted attestation roots"
        )
    current = repository_root
    try:
        for part in path.parts:
            exact_matches = [entry for entry in current.iterdir() if entry.name == part]
            if len(exact_matches) != 1:
                raise DesktopAcceptanceReviewError(
                    f"{label}.resolution_record does not use exact on-disk spelling"
                )
            current = exact_matches[0]
            is_junction = getattr(current, "is_junction", lambda: False)
            if current.is_symlink() or is_junction():
                raise DesktopAcceptanceReviewError(
                    f"{label}.resolution_record may not traverse links or reparse points"
                )
        resolved = current.resolve(strict=True)
        resolved.relative_to(repository_root)
    except DesktopAcceptanceReviewError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise DesktopAcceptanceReviewError(
            f"{label}.resolution_record does not resolve to a repository file"
        ) from error
    if not resolved.is_file():
        raise DesktopAcceptanceReviewError(
            f"{label}.resolution_record must resolve to a regular file"
        )
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _normalized_json(value: object) -> str:
    return _canonical_json(value) + "\n"


def _authoring_roster(authoring_state: object) -> dict[str, str]:
    raw = _require_mapping(authoring_state, "authoring state")
    raw_cases = raw.get("cases")
    if not isinstance(raw_cases, list):
        raise DesktopAcceptanceReviewError("authoring state cases must be an array")
    roster: dict[str, str] = {}
    for index, value in enumerate(raw_cases):
        case = _require_mapping(value, f"authoring state cases[{index}]")
        if "case_id" not in case or "specimen_id" not in case:
            raise DesktopAcceptanceReviewError(
                f"authoring state cases[{index}] requires case_id and specimen_id"
            )
        case_id = _require_matching_text(
            case["case_id"], _CASE_ID, f"authoring state cases[{index}].case_id"
        )
        specimen_id = _require_matching_text(
            case["specimen_id"],
            _SPECIMEN_ID,
            f"authoring state cases[{index}].specimen_id",
        )
        if case_id in roster:
            raise DesktopAcceptanceReviewError(f"duplicate authoring case: {case_id}")
        roster[case_id] = specimen_id
    return roster


def _validate_case(
    value: object, label: str, authoring_roster: Mapping[str, str]
) -> ReviewCaseRecord:
    raw = _require_mapping(value, label)
    _require_exact_keys(
        raw,
        {"case_id", "specimen_id", "ground_truth_review", "action_review", "provider_eligibility"},
        label,
    )
    case_id = _require_matching_text(raw["case_id"], _CASE_ID, f"{label}.case_id")
    specimen_id = _require_matching_text(raw["specimen_id"], _SPECIMEN_ID, f"{label}.specimen_id")
    expected_specimen = authoring_roster.get(case_id)
    if expected_specimen is not None and specimen_id != expected_specimen:
        raise DesktopAcceptanceReviewError(
            f"{case_id}.specimen_id must be {expected_specimen}; found {specimen_id}"
        )

    ground_truth = _validate_track(raw["ground_truth_review"], "identity", f"{case_id}.ground_truth_review")
    action = _validate_track(raw["action_review"], "action", f"{case_id}.action_review")
    if action.submissions and ground_truth.state != "complete":
        raise DesktopAcceptanceReviewError(
            f"{case_id}.action_review cannot contain submissions before ground truth is complete"
        )

    eligibility = _validate_provider_eligibility(
        raw["provider_eligibility"], f"{case_id}.provider_eligibility"
    )
    return ReviewCaseRecord(case_id, specimen_id, ground_truth, action, eligibility)


def _validate_track(value: object, kind: str, label: str) -> ReviewTrack:
    raw = _require_mapping(value, label)
    _require_exact_keys(raw, {"state", "submissions", "adjudication"}, label)
    state = raw["state"]
    if not isinstance(state, str) or state not in REVIEW_STATES:
        raise DesktopAcceptanceReviewError(f"{label}.state is unsupported")
    raw_submissions = raw["submissions"]
    if not isinstance(raw_submissions, list):
        raise DesktopAcceptanceReviewError(f"{label}.submissions must be an array")
    if len(raw_submissions) > 2:
        raise DesktopAcceptanceReviewError(f"{label} cannot contain more than two submissions")

    submissions = [
        _validate_submission(item, kind, f"{label}.submissions[{index}]")
        for index, item in enumerate(raw_submissions)
    ]
    reviewer_ids = [submission.reviewer_id for submission in submissions]
    if len(reviewer_ids) != len(set(reviewer_ids)):
        raise DesktopAcceptanceReviewError(f"{label} requires distinct reviewer IDs")

    adjudication = _validate_optional_adjudication(raw["adjudication"], kind, f"{label}.adjudication")
    if adjudication is not None:
        if len(submissions) != 2 or submissions[0].decision == submissions[1].decision:
            raise DesktopAcceptanceReviewError(
                f"{label}.adjudication is allowed only for two disagreeing submissions"
            )
        if adjudication.reviewer_id in reviewer_ids:
            raise DesktopAcceptanceReviewError(f"{label}.adjudicator must be a distinct reviewer")

    if state == "complete":
        if len(submissions) != 2:
            raise DesktopAcceptanceReviewError(
                f"{label}.complete state requires exactly two submissions"
            )
        disagree = submissions[0].decision != submissions[1].decision
        if disagree and adjudication is None:
            raise DesktopAcceptanceReviewError(
                f"{label}.complete disagreement requires adjudication"
            )

    return ReviewTrack(
        state=state,
        submissions=tuple(sorted(submissions, key=lambda submission: submission.reviewer_id)),
        adjudication=adjudication,
    )


def _validate_submission(value: object, kind: str, label: str) -> ReviewSubmission:
    raw = _require_mapping(value, label)
    _require_exact_keys(raw, {"reviewer_id", "decision", "evidence_references"}, label)
    return ReviewSubmission(
        reviewer_id=_validate_reviewer_id(raw["reviewer_id"], f"{label}.reviewer_id"),
        decision=_validate_decision(raw["decision"], kind, f"{label}.decision"),
        evidence_references=_validate_evidence_references(
            raw["evidence_references"], f"{label}.evidence_references", required=True
        ),
    )


def _validate_optional_adjudication(
    value: object, kind: str, label: str
) -> ReviewAdjudication | None:
    if value is None:
        return None
    raw = _require_mapping(value, label)
    _require_exact_keys(
        raw, {"reviewer_id", "decision", "evidence_references", "rationale"}, label
    )
    return ReviewAdjudication(
        reviewer_id=_validate_reviewer_id(raw["reviewer_id"], f"{label}.reviewer_id"),
        decision=_validate_decision(raw["decision"], kind, f"{label}.decision"),
        evidence_references=_validate_evidence_references(
            raw["evidence_references"], f"{label}.evidence_references", required=True
        ),
        rationale=_require_clean_text(raw["rationale"], f"{label}.rationale"),
    )


def _validate_decision(value: object, kind: str, label: str) -> ReviewDecision:
    if kind == "action":
        if not isinstance(value, str) or value not in EXPECTED_ACTIONS:
            raise DesktopAcceptanceReviewError(f"{label} must be identify or abstain")
        return value

    raw = _require_mapping(value, label)
    _require_exact_keys(raw, {"country", "denomination", "year"}, label)
    return IdentityDecision(
        country=_require_clean_text(raw["country"], f"{label}.country"),
        denomination=_require_clean_text(raw["denomination"], f"{label}.denomination"),
        year=_require_clean_text(raw["year"], f"{label}.year"),
    )


def _validate_provider_eligibility(value: object, label: str) -> ProviderEligibility:
    raw = _require_mapping(value, label)
    _require_exact_keys(raw, set(ELIGIBILITY_FIELDS), label)
    decisions = {
        field: _validate_eligibility_decision(raw[field], f"{label}.{field}")
        for field in ELIGIBILITY_FIELDS
    }
    return ProviderEligibility(**decisions)


def _validate_eligibility_decision(value: object, label: str) -> EligibilityDecision:
    raw = _require_mapping(value, label)
    _require_exact_keys(raw, {"state", "evidence_references"}, label)
    state = raw["state"]
    if not isinstance(state, str) or state not in ELIGIBILITY_STATES:
        raise DesktopAcceptanceReviewError(f"{label}.state is unsupported")
    evidence = _validate_evidence_references(
        raw["evidence_references"],
        f"{label}.evidence_references",
        required=state == "approved",
    )
    return EligibilityDecision(state=state, evidence_references=evidence)


def _validate_evidence_references(value: object, label: str, *, required: bool) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise DesktopAcceptanceReviewError(f"{label} must be an array")
    references: list[str] = []
    for index, item in enumerate(value):
        references.append(_validate_evidence_reference(item, f"{label}[{index}]"))
    if len(references) != len(set(references)):
        raise DesktopAcceptanceReviewError(f"{label} contains duplicate references")
    if required and not references:
        raise DesktopAcceptanceReviewError(f"{label} requires supporting evidence")
    return tuple(sorted(references))


def _validate_reviewer_id(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise DesktopAcceptanceReviewError(f"{label} must be an opaque sanitized reviewer ID")
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value):
        raise DesktopAcceptanceReviewError(f"{label} must be an opaque sanitized reviewer ID")
    if not _SAFE_REVIEWER_ID.fullmatch(value):
        raise DesktopAcceptanceReviewError(f"{label} must be an opaque sanitized reviewer ID")
    if (
        "@" in value
        or "/" in value
        or "\\" in value
        or ".." in value
        or "://" in value
        or _WINDOWS_DRIVE_PATH.match(value)
        or _OBVIOUS_CREDENTIAL.search(value)
    ):
        raise DesktopAcceptanceReviewError(f"{label} must be an opaque sanitized reviewer ID")
    return value


def _validate_evidence_reference(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise DesktopAcceptanceReviewError(f"{label} is not a safe durable reference")
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value):
        raise DesktopAcceptanceReviewError(f"{label} is not a safe durable reference")
    lower_value = value.lower()
    if "\\" in value or "@" in value or _OBVIOUS_CREDENTIAL.search(value):
        raise DesktopAcceptanceReviewError(f"{label} is not a safe durable reference")
    if (
        value.startswith(("/", "~", "./", "../", "$", "%"))
        or _WINDOWS_DRIVE_PATH.match(value)
        or re.search(r"(?:^|:)[A-Za-z]:/", value)
        or lower_value.startswith(("file:", "private:"))
    ):
        raise DesktopAcceptanceReviewError(f"{label} is not a safe durable reference")

    parsed = urlsplit(value)
    if parsed.scheme and "://" in value:
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise DesktopAcceptanceReviewError(f"{label} is not a safe durable reference")
        path_to_check = unquote(parsed.path)
    else:
        if value.startswith("//") or "://" in value:
            raise DesktopAcceptanceReviewError(f"{label} is not a safe durable reference")
        path_to_check = unquote(value.split("#", 1)[0].split("?", 1)[0])

    if any(segment == ".." for segment in path_to_check.split("/")):
        raise DesktopAcceptanceReviewError(f"{label} is not a safe durable reference")
    return value


def _require_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DesktopAcceptanceReviewError(f"{label} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise DesktopAcceptanceReviewError(f"{label} contains a non-string key")
    return value


def _require_exact_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unsupported " + ", ".join(extra))
        raise DesktopAcceptanceReviewError(f"{label} has invalid fields: " + "; ".join(details))


def _require_clean_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise DesktopAcceptanceReviewError(f"{label} must be non-empty normalized text")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise DesktopAcceptanceReviewError(f"{label} contains control characters")
    return value


def _require_matching_text(value: object, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise DesktopAcceptanceReviewError(f"{label} has invalid format")
    return value


def _decision_as_json(decision: ReviewDecision) -> object:
    return decision.as_dict() if isinstance(decision, IdentityDecision) else decision


def _object_without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DesktopAcceptanceReviewError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_non_json_constant(value: str) -> object:
    raise DesktopAcceptanceReviewError(f"unsupported JSON constant: {value}")
