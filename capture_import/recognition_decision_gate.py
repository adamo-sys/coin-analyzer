"""Final deterministic IDENTIFY/ABSTAIN gate for grounded recognition."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .candidate_verification_summary import (
    VerificationDisposition,
    VerificationSummary,
)
from .two_side_candidate_verification import CandidateVerificationReport


class RecognitionDecision(str, Enum):
    IDENTIFY = "identify"
    ABSTAIN = "abstain"


@dataclass(frozen=True, slots=True)
class RecognitionGateResult:
    """Final deterministic recognition decision with explicit evidence provenance."""

    decision: RecognitionDecision
    candidate_id: str | None
    reason: str
    observation_roles: tuple[str, ...]


def decide_identity(
    report: CandidateVerificationReport,
    summary: VerificationSummary,
) -> RecognitionGateResult:
    """Identify only one uniquely verified candidate with two-side support."""

    if not isinstance(report, CandidateVerificationReport):
        raise TypeError("report must be CandidateVerificationReport.")
    if not isinstance(summary, VerificationSummary):
        raise TypeError("summary must be VerificationSummary.")

    if report.observation_roles != summary.observation_roles:
        raise ValueError("report and summary observation roles must agree.")

    if (
        summary.disposition is not VerificationDisposition.UNIQUE_VERIFIED
        or not summary.ready_for_final_gate
        or len(summary.verified_candidate_ids) != 1
    ):
        return RecognitionGateResult(
            decision=RecognitionDecision.ABSTAIN,
            candidate_id=None,
            reason=summary.disposition.value,
            observation_roles=summary.observation_roles,
        )

    candidate_id = summary.verified_candidate_ids[0]
    matches = tuple(
        row
        for row in report.rows
        if row.candidate.candidate_id == candidate_id and row.verified
    )
    if len(matches) != 1:
        return RecognitionGateResult(
            decision=RecognitionDecision.ABSTAIN,
            candidate_id=None,
            reason="verification_summary_mismatch",
            observation_roles=summary.observation_roles,
        )

    row = matches[0]
    if set(row.supporting_roles) != {"obverse", "reverse"}:
        return RecognitionGateResult(
            decision=RecognitionDecision.ABSTAIN,
            candidate_id=None,
            reason="two_side_support_required",
            observation_roles=summary.observation_roles,
        )

    strong_fields = {"year", "denomination"} & set(row.matched_fields)
    if not strong_fields or row.conflicting_fields:
        return RecognitionGateResult(
            decision=RecognitionDecision.ABSTAIN,
            candidate_id=None,
            reason="insufficient_consistent_evidence",
            observation_roles=summary.observation_roles,
        )

    return RecognitionGateResult(
        decision=RecognitionDecision.IDENTIFY,
        candidate_id=candidate_id,
        reason="unique_verified_candidate_with_two_side_support",
        observation_roles=summary.observation_roles,
    )
