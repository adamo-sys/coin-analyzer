"""Bounded implementation contract for the Codex Improvement Agent.

This module does not invoke Codex, mutate repository files, merge changes, or
bypass repository gates. It converts one diagnostic finding plus explicit
caller-supplied scope into a deterministic remediation package, renders that
package as a bounded implementation task, and validates returned implementation
evidence fail-closed against the approved scope and required gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Iterable, Tuple

from diagnostic_agent import DiagnosticFinding


class ImprovementStatus(str, Enum):
    """Terminal status reported by the bounded implementation role."""

    COMPLETED = "completed"
    STOPPED = "stopped"


@dataclass(frozen=True)
class RemediationPackage:
    """Explicit, immutable handoff from diagnosis to bounded implementation."""

    dimension: str
    key: str
    failure_count: int
    observation_ids: Tuple[str, ...]
    hypothesis: str
    recommended_action: str
    objective: str
    allowed_paths: Tuple[str, ...]
    invariants: Tuple[str, ...]
    focused_tests: Tuple[str, ...]
    required_gates: Tuple[str, ...]


@dataclass(frozen=True)
class ValidationEvidence:
    """One reported validation command/gate and its outcome."""

    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class ImprovementResult:
    """Structured evidence returned by the bounded implementation role."""

    status: ImprovementStatus
    changed_files: Tuple[str, ...]
    validation: Tuple[ValidationEvidence, ...]
    risks: Tuple[str, ...] = ()
    unresolved_issues: Tuple[str, ...] = ()
    stopped_gate: str | None = None


@dataclass(frozen=True)
class ImprovementReview:
    """Fail-closed assessment of implementation evidence against its package."""

    acceptable: bool
    violations: Tuple[str, ...]


def _clean_nonempty(values: Iterable[str], *, field_name: str) -> Tuple[str, ...]:
    result = tuple(str(value).strip() for value in values)
    if not result or any(not value for value in result):
        raise ValueError(f"{field_name} must contain only non-empty values")
    if len(set(result)) != len(result):
        raise ValueError(f"{field_name} must not contain duplicates")
    return result


def _clean_paths(values: Iterable[str]) -> Tuple[str, ...]:
    raw = _clean_nonempty(values, field_name="allowed_paths")
    normalized = tuple(value.replace("\\", "/") for value in raw)

    if len(set(normalized)) != len(normalized):
        raise ValueError("allowed_paths must not contain duplicates")

    for value in normalized:
        posix_path = PurePosixPath(value)
        windows_path = PureWindowsPath(value)
        if (
            value == "."
            or value.startswith("./")
            or posix_path.is_absolute()
            or windows_path.is_absolute()
            or bool(windows_path.drive)
            or ".." in posix_path.parts
        ):
            raise ValueError("allowed_paths must be repository-relative paths without traversal")

    return tuple(sorted(normalized))


def build_remediation_package(
    finding: DiagnosticFinding,
    *,
    objective: str,
    allowed_paths: Iterable[str],
    invariants: Iterable[str],
    focused_tests: Iterable[str],
    required_gates: Iterable[str],
) -> RemediationPackage:
    """Create one deterministic remediation package from one diagnostic finding.

    Scope, invariants, tests, and gates must be supplied explicitly by the caller;
    the diagnostic finding is evidence, not authority to expand implementation
    scope.
    """

    objective = str(objective).strip()
    if not objective:
        raise ValueError("objective must be non-empty")

    return RemediationPackage(
        dimension=finding.dimension,
        key=finding.key,
        failure_count=finding.failure_count,
        observation_ids=tuple(finding.observation_ids),
        hypothesis=finding.hypothesis,
        recommended_action=finding.recommended_action,
        objective=objective,
        allowed_paths=_clean_paths(allowed_paths),
        invariants=_clean_nonempty(invariants, field_name="invariants"),
        focused_tests=_clean_nonempty(focused_tests, field_name="focused_tests"),
        required_gates=_clean_nonempty(required_gates, field_name="required_gates"),
    )


def render_codex_task(package: RemediationPackage) -> str:
    """Render a deterministic, bounded implementation task for Codex."""

    def bullets(values: Tuple[str, ...]) -> str:
        return "\n".join(f"- {value}" for value in values)

    return "\n".join(
        (
            "# Codex Improvement Task",
            "",
            "## Objective",
            package.objective,
            "",
            "## Diagnostic evidence",
            f"- dimension: {package.dimension}",
            f"- key: {package.key}",
            f"- failure_count: {package.failure_count}",
            f"- hypothesis: {package.hypothesis}",
            f"- recommended_action: {package.recommended_action}",
            "",
            "## Allowed paths",
            bullets(package.allowed_paths),
            "",
            "## Invariants",
            bullets(package.invariants),
            "",
            "## Focused tests",
            bullets(package.focused_tests),
            "",
            "## Required gates",
            bullets(package.required_gates),
            "",
            "## Stop conditions",
            "- Do not modify files outside Allowed paths.",
            "- Do not expand scope silently.",
            "- Stop when any required gate fails.",
            "- Report changed files, validation results, risks, unresolved issues, and the failed gate when stopped.",
            "- Do not merge or promote the change.",
        )
    )


def review_improvement_result(
    package: RemediationPackage,
    result: ImprovementResult,
) -> ImprovementReview:
    """Validate implementation evidence against scope and required gates.

    This assessment is deliberately fail-closed: missing required gate evidence,
    out-of-scope changes, inconsistent stop state, or any failed required gate
    makes the result unacceptable for promotion.
    """

    violations = []
    allowed = set(package.allowed_paths)
    changed = tuple(path.replace("\\", "/") for path in result.changed_files)

    out_of_scope = sorted(set(changed) - allowed)
    if out_of_scope:
        violations.append("out-of-scope changed files: " + ", ".join(out_of_scope))

    evidence_by_name = {item.name: item for item in result.validation}
    if len(evidence_by_name) != len(result.validation):
        violations.append("duplicate validation evidence names")

    for gate in package.required_gates:
        evidence = evidence_by_name.get(gate)
        if evidence is None:
            violations.append(f"missing required gate evidence: {gate}")
        elif not evidence.passed:
            violations.append(f"required gate failed: {gate}")

    if result.status is ImprovementStatus.COMPLETED and result.stopped_gate is not None:
        violations.append("completed result must not report stopped_gate")
    if result.status is ImprovementStatus.STOPPED and not result.stopped_gate:
        violations.append("stopped result must report stopped_gate")
    if result.status is ImprovementStatus.STOPPED:
        violations.append("implementation stopped before successful completion")

    return ImprovementReview(
        acceptable=not violations,
        violations=tuple(sorted(violations)),
    )
