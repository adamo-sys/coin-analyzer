"""Independent, deterministic review boundary for self-improvement candidates.

The reviewer consumes the frozen remediation package, the implementation role's
structured result, and independently supplied invariant evidence. It does not
mutate repository files, repair implementations, expand scope, manufacture
missing evidence, invoke models, merge, deploy, or promote changes.

Reviewer approval is evidence only; repository-owner authority and GitHub
Actions remain separate promotion gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Iterable, Tuple

from improvement_agent import ImprovementResult, ImprovementStatus, RemediationPackage


class ReviewRecommendation(str, Enum):
    """Deterministic recommendation emitted by the independent reviewer."""

    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True)
class InvariantEvidence:
    """Independent evidence for one invariant from the remediation package."""

    invariant: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class ReviewerReport:
    """Fail-closed review result; never grants merge or promotion authority."""

    recommendation: ReviewRecommendation
    findings: Tuple[str, ...]
    verified_invariants: Tuple[str, ...]

    @property
    def promotion_permitted(self) -> bool:
        """Whether review evidence permits promotion to proceed to later gates."""

        return self.recommendation is ReviewRecommendation.PASS


def _normalize_repository_path(value: str) -> str | None:
    normalized = str(value).strip().replace("\\", "/")
    if not normalized:
        return None

    posix_path = PurePosixPath(normalized)
    windows_path = PureWindowsPath(normalized)
    if (
        normalized == "."
        or normalized.startswith("./")
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or ".." in posix_path.parts
    ):
        return None
    return normalized


def review_candidate(
    package: RemediationPackage,
    result: ImprovementResult,
    invariant_evidence: Iterable[InvariantEvidence],
) -> ReviewerReport:
    """Independently evaluate candidate evidence against frozen package bounds.

    The review is deliberately fail-closed. Missing, malformed, contradictory,
    out-of-scope, stopped, failed, or unresolved evidence yields ``FAIL``.
    This function intentionally re-checks implementation scope and required gates
    rather than trusting the implementation role's own review conclusion.
    """

    findings: list[str] = []

    allowed = set(package.allowed_paths)
    normalized_changed: list[str] = []
    for raw_path in result.changed_files:
        normalized = _normalize_repository_path(raw_path)
        if normalized is None:
            findings.append(f"malformed changed file path: {raw_path}")
            continue
        normalized_changed.append(normalized)

    if len(set(normalized_changed)) != len(normalized_changed):
        findings.append("duplicate changed file paths after normalization")

    out_of_scope = sorted(set(normalized_changed) - allowed)
    if out_of_scope:
        findings.append("out-of-scope changed files: " + ", ".join(out_of_scope))

    validation_names = [str(item.name).strip() for item in result.validation]
    if any(not name for name in validation_names):
        findings.append("validation evidence names must be non-empty")
    if len(set(validation_names)) != len(validation_names):
        findings.append("duplicate or contradictory validation evidence names")

    evidence_by_name = {
        str(item.name).strip(): item
        for item in result.validation
        if str(item.name).strip()
    }
    for gate in package.required_gates:
        evidence = evidence_by_name.get(gate)
        if evidence is None:
            findings.append(f"missing required gate evidence: {gate}")
        elif not evidence.passed:
            findings.append(f"required gate failed: {gate}")

    if result.status is not ImprovementStatus.COMPLETED:
        if result.status is ImprovementStatus.STOPPED:
            findings.append("implementation stopped before successful completion")
        else:
            findings.append("unrecognized implementation status")

    if result.status is ImprovementStatus.COMPLETED and result.stopped_gate is not None:
        findings.append("completed result must not report stopped_gate")
    if result.status is ImprovementStatus.STOPPED and not result.stopped_gate:
        findings.append("stopped result must report stopped_gate")

    for issue in result.unresolved_issues:
        issue_text = str(issue).strip()
        if issue_text:
            findings.append(f"unresolved blocking issue: {issue_text}")
        else:
            findings.append("unresolved issue entries must be non-empty")

    supplied_invariants = tuple(invariant_evidence)
    names = [str(item.invariant).strip() for item in supplied_invariants]
    if any(not name for name in names):
        findings.append("invariant evidence names must be non-empty")
    if len(set(names)) != len(names):
        findings.append("duplicate or contradictory invariant evidence names")

    expected_invariants = set(package.invariants)
    supplied_names = {name for name in names if name}
    missing_invariants = sorted(expected_invariants - supplied_names)
    unexpected_invariants = sorted(supplied_names - expected_invariants)
    for invariant in missing_invariants:
        findings.append(f"missing invariant evidence: {invariant}")
    if unexpected_invariants:
        findings.append(
            "unexpected invariant evidence outside authorized review scope: "
            + ", ".join(unexpected_invariants)
        )

    evidence_by_invariant = {
        str(item.invariant).strip(): item
        for item in supplied_invariants
        if str(item.invariant).strip()
    }
    verified = []
    for invariant in package.invariants:
        evidence = evidence_by_invariant.get(invariant)
        if evidence is None:
            continue
        if not evidence.passed:
            findings.append(f"invariant failed: {invariant}")
        else:
            verified.append(invariant)

    findings_tuple = tuple(sorted(set(findings)))
    return ReviewerReport(
        recommendation=(
            ReviewRecommendation.PASS if not findings_tuple else ReviewRecommendation.FAIL
        ),
        findings=findings_tuple,
        verified_invariants=tuple(verified),
    )
