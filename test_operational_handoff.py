from __future__ import annotations

from dataclasses import dataclass

from diagnostic_agent import DiagnosticFinding
from improvement_agent import (
    ImprovementResult,
    ImprovementStatus,
    ValidationEvidence,
    build_remediation_package,
)
from operational_handoff import HandoffStatus, execute_operational_handoff
from reviewer_agent import InvariantEvidence, ReviewRecommendation


def _package():
    finding = DiagnosticFinding(
        dimension="field",
        key="mintmark",
        failure_count=2,
        observation_ids=("obs-1", "obs-2"),
        hypothesis="bounded mintmark hypothesis",
        recommended_action="inspect mintmark path",
        relevant_paths=("capture_import/mintmark.py",),
    )
    return build_remediation_package(
        finding,
        objective="Fix the bounded mintmark failure.",
        allowed_paths=("capture_import/mintmark.py", "test_mintmark.py"),
        invariants=("no collection mutation", "confirmed observations remain immutable"),
        focused_tests=("pytest test_mintmark.py -q",),
        required_gates=("focused-tests", "pyright", "full-regression"),
    )


def _invariants(*, passed: bool = True):
    return (
        InvariantEvidence("no collection mutation", passed, "checked independently"),
        InvariantEvidence(
            "confirmed observations remain immutable",
            passed,
            "checked independently",
        ),
    )


def _passing_result(*, changed_files=("capture_import/mintmark.py",)):
    return ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=tuple(changed_files),
        validation=(
            ValidationEvidence("focused-tests", True),
            ValidationEvidence("pyright", True),
            ValidationEvidence("full-regression", True),
        ),
    )


@dataclass
class _Executor:
    result: object
    calls: int = 0
    last_task: str | None = None

    def execute(self, task, package):
        self.calls += 1
        self.last_task = task
        return self.result


class _UnavailableExecutor:
    def __init__(self):
        self.calls = 0

    def execute(self, task, package):
        self.calls += 1
        raise RuntimeError("Codex unavailable")


def test_valid_single_shot_execution_reaches_human_review_boundary() -> None:
    executor = _Executor(_passing_result())

    report = execute_operational_handoff(_package(), executor, _invariants())

    assert executor.calls == 1
    assert report.status is HandoffStatus.READY_FOR_HUMAN_REVIEW
    assert report.ready_for_human_review is True
    assert report.execution_error is None
    assert report.implementation_review.acceptable is True
    assert report.reviewer_report.recommendation is ReviewRecommendation.PASS
    assert "Do not merge or promote the change." in report.task
    assert executor.last_task == report.task


def test_codex_unavailable_stops_without_retry() -> None:
    executor = _UnavailableExecutor()

    report = execute_operational_handoff(_package(), executor, _invariants())

    assert executor.calls == 1
    assert report.status is HandoffStatus.STOPPED
    assert report.ready_for_human_review is False
    assert report.execution_error == "RuntimeError: Codex unavailable"
    assert report.implementation_result.status is ImprovementStatus.STOPPED
    assert report.implementation_result.stopped_gate == "codex-execution"
    assert report.implementation_review.acceptable is False
    assert report.reviewer_report.recommendation is ReviewRecommendation.FAIL


def test_malformed_executor_result_stops_fail_closed() -> None:
    executor = _Executor({"status": "completed"})

    report = execute_operational_handoff(_package(), executor, _invariants())

    assert executor.calls == 1
    assert report.status is HandoffStatus.STOPPED
    assert report.execution_error == "executor returned malformed result"
    assert report.implementation_result.status is ImprovementStatus.STOPPED


def test_out_of_scope_change_stops_even_with_passing_gates() -> None:
    executor = _Executor(_passing_result(changed_files=("capture_import/mintmark.py", "oops.py")))

    report = execute_operational_handoff(_package(), executor, _invariants())

    assert report.status is HandoffStatus.STOPPED
    assert report.implementation_review.acceptable is False
    assert "out-of-scope changed files: oops.py" in report.implementation_review.violations
    assert report.reviewer_report.recommendation is ReviewRecommendation.FAIL


def test_failed_required_gate_stops() -> None:
    result = ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=("capture_import/mintmark.py",),
        validation=(
            ValidationEvidence("focused-tests", True),
            ValidationEvidence("pyright", False, "type error"),
            ValidationEvidence("full-regression", True),
        ),
    )

    report = execute_operational_handoff(_package(), _Executor(result), _invariants())

    assert report.status is HandoffStatus.STOPPED
    assert "required gate failed: pyright" in report.implementation_review.violations
    assert report.reviewer_report.recommendation is ReviewRecommendation.FAIL


def test_missing_required_gate_stops() -> None:
    result = ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=("capture_import/mintmark.py",),
        validation=(ValidationEvidence("focused-tests", True), ValidationEvidence("pyright", True)),
    )

    report = execute_operational_handoff(_package(), _Executor(result), _invariants())

    assert report.status is HandoffStatus.STOPPED
    assert "missing required gate evidence: full-regression" in report.implementation_review.violations


def test_stopped_implementation_remains_stopped() -> None:
    result = ImprovementResult(
        status=ImprovementStatus.STOPPED,
        changed_files=("capture_import/mintmark.py",),
        validation=(ValidationEvidence("focused-tests", True),),
        unresolved_issues=("implementation could not prove safety",),
        stopped_gate="pyright",
    )

    report = execute_operational_handoff(_package(), _Executor(result), _invariants())

    assert report.status is HandoffStatus.STOPPED
    assert report.implementation_result.status is ImprovementStatus.STOPPED
    assert "implementation stopped before successful completion" in report.implementation_review.violations
    assert report.reviewer_report.recommendation is ReviewRecommendation.FAIL


def test_unresolved_blocking_issue_is_rejected_by_independent_reviewer() -> None:
    result = ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=("capture_import/mintmark.py",),
        validation=(
            ValidationEvidence("focused-tests", True),
            ValidationEvidence("pyright", True),
            ValidationEvidence("full-regression", True),
        ),
        unresolved_issues=("manual uncertainty remains",),
    )

    report = execute_operational_handoff(_package(), _Executor(result), _invariants())

    assert report.status is HandoffStatus.STOPPED
    assert report.implementation_review.acceptable is True
    assert report.reviewer_report.recommendation is ReviewRecommendation.FAIL
    assert "unresolved blocking issue: manual uncertainty remains" in report.reviewer_report.findings


def test_failed_invariant_evidence_stops() -> None:
    report = execute_operational_handoff(
        _package(),
        _Executor(_passing_result()),
        _invariants(passed=False),
    )

    assert report.status is HandoffStatus.STOPPED
    assert report.reviewer_report.recommendation is ReviewRecommendation.FAIL
    assert any(item.startswith("invariant failed:") for item in report.reviewer_report.findings)


def test_missing_invariant_evidence_stops() -> None:
    report = execute_operational_handoff(
        _package(),
        _Executor(_passing_result()),
        (InvariantEvidence("no collection mutation", True),),
    )

    assert report.status is HandoffStatus.STOPPED
    assert report.reviewer_report.recommendation is ReviewRecommendation.FAIL
    assert "missing invariant evidence: confirmed observations remain immutable" in report.reviewer_report.findings


def test_scope_broadening_through_reviewer_evidence_stops() -> None:
    evidence = _invariants() + (InvariantEvidence("new broader invariant", True),)

    report = execute_operational_handoff(_package(), _Executor(_passing_result()), evidence)

    assert report.status is HandoffStatus.STOPPED
    assert report.reviewer_report.recommendation is ReviewRecommendation.FAIL
    assert any(
        item.startswith("unexpected invariant evidence outside authorized review scope:")
        for item in report.reviewer_report.findings
    )


def test_duplicate_validation_evidence_stops() -> None:
    result = ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=("capture_import/mintmark.py",),
        validation=(
            ValidationEvidence("focused-tests", True),
            ValidationEvidence("pyright", True),
            ValidationEvidence("pyright", False),
            ValidationEvidence("full-regression", True),
        ),
    )

    report = execute_operational_handoff(_package(), _Executor(result), _invariants())

    assert report.status is HandoffStatus.STOPPED
    assert "duplicate validation evidence names" in report.implementation_review.violations
    assert report.reviewer_report.recommendation is ReviewRecommendation.FAIL
