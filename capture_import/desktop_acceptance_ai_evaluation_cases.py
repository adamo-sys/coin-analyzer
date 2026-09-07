"""Adapter from the frozen desktop acceptance manifest to AI evaluation cases."""

from __future__ import annotations

from collections.abc import Mapping

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
    EvaluationCase,
)
from capture_import.desktop_acceptance_set import (
    DesktopAcceptanceCase,
    DesktopAcceptanceManifest,
)


def adapt_desktop_acceptance_manifest_cases(
    manifest: DesktopAcceptanceManifest,
    *,
    candidate_ids_by_case: Mapping[str, str],
) -> tuple[EvaluationCase, ...]:
    """Adapt authoritative frozen manifest cases without manufacturing identity."""

    if not isinstance(manifest, DesktopAcceptanceManifest):
        raise TypeError("manifest must be a DesktopAcceptanceManifest.")

    if not isinstance(candidate_ids_by_case, Mapping):
        raise TypeError("candidate_ids_by_case must be a mapping.")

    for key, value in candidate_ids_by_case.items():
        if not isinstance(key, str):
            raise TypeError("candidate_ids_by_case keys must be strings.")
        if not isinstance(value, str):
            raise TypeError("candidate_ids_by_case values must be strings.")

    manifest_cases = manifest.cases

    if not isinstance(manifest_cases, tuple):
        raise TypeError("manifest.cases must be a tuple.")

    for case in manifest_cases:
        if not isinstance(case, DesktopAcceptanceCase):
            raise TypeError(
                "manifest.cases must contain DesktopAcceptanceCase values."
            )

    case_ids = tuple(case.case_id for case in manifest_cases)

    if case_ids != tuple(sorted(case_ids)):
        raise ValueError("desktop acceptance manifest case IDs must be sorted.")

    if len(case_ids) != len(set(case_ids)):
        raise ValueError("desktop acceptance manifest case IDs must be unique.")

    identify_case_ids: set[str] = set()

    for case in manifest_cases:
        if case.expected_action == "identify":
            identify_case_ids.add(case.case_id)
        elif case.expected_action != "abstain":
            raise ValueError(
                "desktop acceptance manifest contains unsupported "
                f"expected_action {case.expected_action!r} "
                f"for case {case.case_id!r}."
            )

    supplied_candidate_ids = set(candidate_ids_by_case)

    if supplied_candidate_ids != identify_case_ids:
        missing = tuple(sorted(identify_case_ids - supplied_candidate_ids))
        extra = tuple(sorted(supplied_candidate_ids - identify_case_ids))
        raise ValueError(
            "candidate_ids_by_case must contain exactly the manifest identify "
            f"case IDs; missing={missing!r}, extra={extra!r}."
        )

    evaluation_cases: list[EvaluationCase] = []

    for case in manifest_cases:
        if case.expected_action == "abstain":
            evaluation_case = EvaluationCase(
                schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
                case_id=case.case_id,
                require_abstention=True,
            )
        else:
            evaluation_case = EvaluationCase(
                schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
                case_id=case.case_id,
                allowed_candidate_ids=(
                    candidate_ids_by_case[case.case_id],
                ),
            )

        evaluation_case.validate()
        evaluation_cases.append(evaluation_case)

    return tuple(evaluation_cases)
