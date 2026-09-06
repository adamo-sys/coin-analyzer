"""Adapter from frozen desktop acceptance results to AI evaluation observations."""

from __future__ import annotations

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
    ObservedEvaluationResult,
)
from capture_import.desktop_acceptance_scoring import DesktopAcceptanceResult


def adapt_desktop_acceptance_result(
    result: DesktopAcceptanceResult,
    *,
    candidate_id: str | None = None,
    evidence_refs: tuple[str, ...] = (),
) -> ObservedEvaluationResult | None:
    """Adapt one already-produced desktop acceptance result.

    The adapter is pure and does not execute providers, canonicalize identities,
    interpret scores, manufacture candidate identities, or mutate state.

    ``candidate_id`` is required only for an ``identify`` result and must be
    explicitly supplied by the caller. ``unavailable`` and
    ``infrastructure_failure`` map to no observed AI-evaluation result because
    the frozen observation contract contains only candidate and abstention
    states.
    """

    if not isinstance(result, DesktopAcceptanceResult):
        raise TypeError("result must be a DesktopAcceptanceResult.")

    if not isinstance(evidence_refs, tuple):
        raise TypeError("evidence_refs must be a tuple.")

    if result.observed_action == "identify":
        if candidate_id is None:
            raise ValueError(
                "identify results require an explicit caller-supplied candidate_id."
            )

        observed = ObservedEvaluationResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=result.case_id,
            candidate_id=candidate_id,
            evidence_refs=evidence_refs,
        )
        observed.validate()
        return observed

    if candidate_id is not None:
        raise ValueError(
            "candidate_id must not be supplied for non-identify results."
        )

    if result.observed_action == "abstain":
        observed = ObservedEvaluationResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=result.case_id,
            abstained=True,
            evidence_refs=evidence_refs,
        )
        observed.validate()
        return observed

    if result.observed_action in {"unavailable", "infrastructure_failure"}:
        return None

    raise ValueError(
        f"Unsupported desktop acceptance action: {result.observed_action!r}."
    )
