"""Bounded orchestration for the grounded recognition pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .candidate_verification_summary import (
    VerificationSummary,
    summarize_candidate_verification,
)
from .catalogue_retrieval import (
    CatalogueRetrievalContractError,
    CatalogueRetrievalResult,
    CatalogueRetriever,
    request_from_numeral_envelope,
)
from .grounded_visual_observation import GroundedVisualObservation
from .numeral_evidence_envelope import (
    NumeralEvidenceEnvelope,
    build_numeral_evidence_envelope,
)
from .recognition_decision_gate import RecognitionGateResult, decide_identity
from .two_side_candidate_verification import (
    CandidateVerificationReport,
    verify_retrieved_candidates,
)


@dataclass(frozen=True, slots=True)
class GroundedRecognitionPipelineResult:
    """Auditable outputs from evidence extraction through final decision."""

    evidence: NumeralEvidenceEnvelope
    retrieval: CatalogueRetrievalResult | None
    verification: CandidateVerificationReport | None
    summary: VerificationSummary | None
    decision: RecognitionGateResult


def run_grounded_recognition_pipeline(
    observations: Iterable[GroundedVisualObservation],
    retriever: CatalogueRetriever,
    *,
    retrieval_limit: int = 10,
) -> GroundedRecognitionPipelineResult:
    """Run deterministic recognition stages and fail closed to ABSTAIN."""

    sides = tuple(observations)
    envelope = build_numeral_evidence_envelope(sides)

    try:
        request = request_from_numeral_envelope(
            envelope,
            limit=retrieval_limit,
        )
    except CatalogueRetrievalContractError as exc:
        return GroundedRecognitionPipelineResult(
            evidence=envelope,
            retrieval=None,
            verification=None,
            summary=None,
            decision=_abstain(
                str(exc),
                tuple(side.role for side in sides),
            ),
        )

    retrieval = retriever.retrieve(request)
    if not isinstance(retrieval, CatalogueRetrievalResult):
        raise TypeError("retriever must return CatalogueRetrievalResult.")

    verification = verify_retrieved_candidates(retrieval, sides)
    summary = summarize_candidate_verification(verification)
    decision = decide_identity(verification, summary)

    return GroundedRecognitionPipelineResult(
        evidence=envelope,
        retrieval=retrieval,
        verification=verification,
        summary=summary,
        decision=decision,
    )


def _abstain(reason: str, roles: tuple[str, ...]) -> RecognitionGateResult:
    from .recognition_decision_gate import RecognitionDecision

    return RecognitionGateResult(
        decision=RecognitionDecision.ABSTAIN,
        candidate_id=None,
        reason=reason,
        observation_roles=roles,
    )
