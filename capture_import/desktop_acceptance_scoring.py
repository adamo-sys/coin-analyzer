"""Provider-independent deterministic scoring for desktop acceptance results."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
import math
from typing import Mapping

from .desktop_acceptance_canonicalization import (
    DesktopAcceptanceCanonicalizationPolicy,
    canonicalize_complete_identity,
    complete_identities_equivalent,
    diagnostic_exact_identity_match,
)
from .desktop_acceptance_set import DesktopAcceptanceManifest

OBSERVED_ACTIONS = frozenset(
    {"identify", "abstain", "unavailable", "infrastructure_failure"}
)
_IDENTITY_FIELDS = frozenset({"country", "denomination", "year"})


class DesktopAcceptanceScoringError(ValueError):
    """Acceptance results are incomplete, ambiguous, or unsafe to score."""


@dataclass(frozen=True, slots=True)
class DesktopAcceptanceResult:
    case_id: str
    observed_action: str
    proposed_identity: Mapping[str, str] | None
    provider_source_score: float | None = None
    system_confidence: None = None

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id:
            raise DesktopAcceptanceScoringError("result.case_id must be non-empty text.")
        if self.observed_action not in OBSERVED_ACTIONS:
            raise DesktopAcceptanceScoringError("result.observed_action is unsupported.")
        if self.system_confidence is not None:
            raise DesktopAcceptanceScoringError("system confidence is unavailable in v1.")
        score = self.provider_source_score
        if (score is not None
                and (isinstance(score, bool) or not isinstance(score, (int, float))
                     or not math.isfinite(score))):
            raise DesktopAcceptanceScoringError(
                "provider source score must be finite or unavailable."
            )
        identity = self.proposed_identity
        if self.observed_action == "identify":
            if (not isinstance(identity, Mapping) or not identity
                    or set(identity) - _IDENTITY_FIELDS
                    or any(not isinstance(value, str) or not value.strip()
                           for value in identity.values())):
                raise DesktopAcceptanceScoringError(
                    "identify results require a non-empty identity field subset."
                )
            object.__setattr__(
                self, "proposed_identity",
                {field: identity[field].strip() for field in sorted(identity)},
            )
        elif identity is not None:
            raise DesktopAcceptanceScoringError(
                "non-identify public outcomes cannot carry a proposed identity."
            )


def score_desktop_acceptance_results(
    manifest: DesktopAcceptanceManifest,
    results: tuple[DesktopAcceptanceResult, ...],
    policy: DesktopAcceptanceCanonicalizationPolicy,
) -> dict[str, object]:
    """Score one public outcome per frozen case without executing a provider."""
    if not isinstance(results, tuple):
        raise DesktopAcceptanceScoringError("results must be an ordered tuple.")
    result_ids = tuple(result.case_id for result in results)
    manifest_ids = tuple(case.case_id for case in manifest.cases)
    if result_ids != tuple(sorted(result_ids)) or len(result_ids) != len(set(result_ids)):
        raise DesktopAcceptanceScoringError("result case IDs must be unique and sorted.")
    if result_ids != manifest_ids:
        raise DesktopAcceptanceScoringError(
            "results must contain exactly one outcome for every manifest case."
        )

    per_case = []
    action_rows = []
    identity_rows = []
    availability_rows = []
    infrastructure_cases = []
    for case, result in zip(manifest.cases, results):
        infrastructure = result.observed_action == "infrastructure_failure"
        unavailable = result.observed_action == "unavailable"
        if infrastructure:
            infrastructure_cases.append(case.case_id)
        action_correct = None if infrastructure else result.observed_action == case.expected_action
        identity_correct = None
        exact_diagnostic = None
        canonical_proposal = None
        if case.expected_action == "identify" and not infrastructure:
            identity_correct = (
                result.observed_action == "identify"
                and complete_identities_equivalent(
                    case.expected_identity, result.proposed_identity, policy
                )
            )
            exact_diagnostic = (
                result.observed_action == "identify"
                and diagnostic_exact_identity_match(
                    case.expected_identity, result.proposed_identity
                )
            )
            if result.observed_action == "identify":
                canonical = canonicalize_complete_identity(result.proposed_identity, policy)
                canonical_proposal = None if canonical is None else canonical.to_dict()
            identity_rows.append((case.specimen_id, bool(identity_correct)))
        if not infrastructure:
            action_rows.append((case.specimen_id, bool(action_correct)))
            availability_rows.append((case.specimen_id, not unavailable))
        per_case.append({
            "case_id": case.case_id,
            "specimen_id": case.specimen_id,
            "expected_action": case.expected_action,
            "observed_action": result.observed_action,
            "action_correct": action_correct,
            "complete_identity_correct": identity_correct,
            "exact_identity_diagnostic": exact_diagnostic,
            "canonical_proposed_identity": canonical_proposal,
            "provider_source_score": result.provider_source_score,
            "provider_source_score_semantics": "uncalibrated",
            "system_confidence": None,
        })

    return {
        "schema": "coin-analyzer-desktop-acceptance-score-report",
        "version": "1.0.0",
        "manifest_version": manifest.version,
        "canonicalization_policy": {
            "policy_id": policy.policy_id,
            "version": policy.version,
        },
        "primary_weighting": "specimen",
        "action_correctness": _metric(action_rows),
        "complete_identity_correctness": _metric(identity_rows),
        "provider_availability": _metric(availability_rows),
        "infrastructure_failures": {
            "count": len(infrastructure_cases),
            "case_ids": infrastructure_cases,
            "excluded_from_metric_denominators": True,
        },
        "per_case": per_case,
    }


def _metric(rows: list[tuple[str, bool]]) -> dict[str, object]:
    by_specimen: dict[str, list[bool]] = defaultdict(list)
    for specimen_id, correct in rows:
        by_specimen[specimen_id].append(correct)
    specimen_total = sum(
        (Fraction(sum(values), len(values)) for values in by_specimen.values()),
        start=Fraction(0),
    )
    specimen_rate = specimen_total / len(by_specimen) if by_specimen else Fraction(0)
    case_correct = sum(correct for _, correct in rows)
    case_total = len(rows)
    return {
        "specimen_weighted": {
            "numerator": specimen_rate.numerator,
            "denominator": specimen_rate.denominator,
            "rate": float(specimen_rate),
            "specimens": len(by_specimen),
        },
        "case_weighted_diagnostic": {
            "numerator": case_correct,
            "denominator": case_total,
            "rate": case_correct / case_total if case_total else 0.0,
        },
    }
