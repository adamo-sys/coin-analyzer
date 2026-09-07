"""End-to-end deterministic composition for frozen desktop AI evaluation."""

from __future__ import annotations

from collections.abc import Mapping

from capture_import.desktop_acceptance_ai_evaluation_batch import (
    DesktopAcceptanceAIEvaluationBatchReport,
    evaluate_desktop_acceptance_batch,
)
from capture_import.desktop_acceptance_ai_evaluation_cases import (
    adapt_desktop_acceptance_manifest_cases,
)
from capture_import.desktop_acceptance_scoring import DesktopAcceptanceResult
from capture_import.desktop_acceptance_set import DesktopAcceptanceManifest


def evaluate_desktop_acceptance_manifest_results(
    manifest: DesktopAcceptanceManifest,
    results: tuple[DesktopAcceptanceResult, ...],
    *,
    authoritative_candidate_ids_by_case: Mapping[str, str],
    observed_candidate_ids_by_case: Mapping[str, str],
    evidence_refs_by_case: Mapping[str, tuple[str, ...]] | None = None,
) -> DesktopAcceptanceAIEvaluationBatchReport:
    """Compose existing manifest adaptation and frozen batch evaluation."""

    if not isinstance(manifest, DesktopAcceptanceManifest):
        raise TypeError("manifest must be a DesktopAcceptanceManifest.")

    if not isinstance(results, tuple):
        raise TypeError("results must be a tuple.")

    if not isinstance(authoritative_candidate_ids_by_case, Mapping):
        raise TypeError(
            "authoritative_candidate_ids_by_case must be a mapping."
        )

    if not isinstance(observed_candidate_ids_by_case, Mapping):
        raise TypeError(
            "observed_candidate_ids_by_case must be a mapping."
        )

    if (
        evidence_refs_by_case is not None
        and not isinstance(evidence_refs_by_case, Mapping)
    ):
        raise TypeError("evidence_refs_by_case must be a mapping or None.")

    evaluation_cases = adapt_desktop_acceptance_manifest_cases(
        manifest,
        candidate_ids_by_case=authoritative_candidate_ids_by_case,
    )

    return evaluate_desktop_acceptance_batch(
        evaluation_cases,
        results,
        candidate_ids_by_case=observed_candidate_ids_by_case,
        evidence_refs_by_case=evidence_refs_by_case,
    )
