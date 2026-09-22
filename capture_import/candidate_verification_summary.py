"""Deterministic summary of candidate verification outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .two_side_candidate_verification import CandidateVerificationReport


class VerificationDisposition(str, Enum):
    """Shape of verification output before final identify/abstain gating."""

    EVIDENCE_CONFLICT = "evidence_conflict"
    NO_CANDIDATES = "no_candidates"
    NONE_VERIFIED = "none_verified"
    UNIQUE_VERIFIED = "unique_verified"
    AMBIGUOUS_VERIFIED = "ambiguous_verified"


@dataclass(frozen=True, slots=True)
class VerificationSummary:
    """Verification-set diagnostics; never a final identity decision."""

    disposition: VerificationDisposition
    candidate_count: int
    verified_count: int
    verified_candidate_ids: tuple[str, ...]
    rejected_candidate_ids: tuple[str, ...]
    observation_roles: tuple[str, ...]
    ready_for_final_gate: bool


def summarize_candidate_verification(
    report: CandidateVerificationReport,
) -> VerificationSummary:
    """Summarize verification deterministically without accepting an identity."""

    if not isinstance(report, CandidateVerificationReport):
        raise TypeError("report must be CandidateVerificationReport.")

    rows = report.rows
    verified_ids = tuple(
        row.candidate.candidate_id for row in rows if row.verified
    )
    rejected_ids = tuple(
        row.candidate.candidate_id for row in rows if not row.verified
    )

    if report.has_evidence_conflict:
        disposition = VerificationDisposition.EVIDENCE_CONFLICT
    elif not rows:
        disposition = VerificationDisposition.NO_CANDIDATES
    elif not verified_ids:
        disposition = VerificationDisposition.NONE_VERIFIED
    elif len(verified_ids) == 1:
        disposition = VerificationDisposition.UNIQUE_VERIFIED
    else:
        disposition = VerificationDisposition.AMBIGUOUS_VERIFIED

    return VerificationSummary(
        disposition=disposition,
        candidate_count=len(rows),
        verified_count=len(verified_ids),
        verified_candidate_ids=verified_ids,
        rejected_candidate_ids=rejected_ids,
        observation_roles=report.observation_roles,
        ready_for_final_gate=(
            disposition is VerificationDisposition.UNIQUE_VERIFIED
        ),
    )
