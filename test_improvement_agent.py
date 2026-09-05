from __future__ import annotations

import pytest

from diagnostic_agent import DiagnosticFinding
from improvement_agent import (
    ImprovementResult,
    ImprovementStatus,
    ValidationEvidence,
    build_remediation_package,
    render_codex_task,
    review_improvement_result,
)


def _finding() -> DiagnosticFinding:
    return DiagnosticFinding(
        dimension="field",
        key="mintmark",
        failure_count=3,
        observation_ids=("obs-1", "obs-2", "obs-3"),
        hypothesis="mintmark hypothesis",
        recommended_action="inspect mintmark path",
        relevant_paths=("capture_import/mintmark.py",),
    )


def _package():
    return build_remediation_package(
        _finding(),
        objective="Fix the bounded mintmark failure without changing unrelated behavior.",
        allowed_paths=("test_mintmark.py", "capture_import/mintmark.py"),
        invariants=("confirmed observations remain immutable", "no collection mutation"),
        focused_tests=("pytest test_mintmark.py -q",),
        required_gates=("focused-tests", "pyright", "full-regression"),
    )


def test_package_preserves_diagnostic_evidence_and_normalizes_scope() -> None:
    package = _package()

    assert package.dimension == "field"
    assert package.key == "mintmark"
    assert package.failure_count == 3
    assert package.observation_ids == ("obs-1", "obs-2", "obs-3")
    assert package.hypothesis == "mintmark hypothesis"
    assert package.recommended_action == "inspect mintmark path"
    assert package.allowed_paths == (
        "capture_import/mintmark.py",
        "test_mintmark.py",
    )


def test_package_requires_explicit_nonempty_bounds() -> None:
    kwargs = dict(
        finding=_finding(),
        objective="fix",
        allowed_paths=("a.py",),
        invariants=("preserve contract",),
        focused_tests=("pytest test_a.py -q",),
        required_gates=("tests",),
    )

    for field_name in ("allowed_paths", "invariants", "focused_tests", "required_gates"):
        bad = dict(kwargs)
        bad[field_name] = ()
        with pytest.raises(ValueError):
            build_remediation_package(**bad)

    bad = dict(kwargs)
    bad["objective"] = "   "
    with pytest.raises(ValueError):
        build_remediation_package(**bad)


def test_package_rejects_duplicate_bounds_and_path_traversal() -> None:
    with pytest.raises(ValueError, match="must not contain duplicates"):
        build_remediation_package(
            _finding(),
            objective="fix",
            allowed_paths=("a.py", "a.py"),
            invariants=("preserve contract",),
            focused_tests=("pytest test_a.py -q",),
            required_gates=("tests",),
        )

    with pytest.raises(ValueError, match="repository-relative"):
        build_remediation_package(
            _finding(),
            objective="fix",
            allowed_paths=("../a.py",),
            invariants=("preserve contract",),
            focused_tests=("pytest test_a.py -q",),
            required_gates=("tests",),
        )


def test_render_codex_task_contains_scope_invariants_gates_and_stop_conditions() -> None:
    task = render_codex_task(_package())

    assert "# Codex Improvement Task" in task
    assert "capture_import/mintmark.py" in task
    assert "confirmed observations remain immutable" in task
    assert "pytest test_mintmark.py -q" in task
    assert "full-regression" in task
    assert "Do not modify files outside Allowed paths." in task
    assert "Stop when any required gate fails." in task
    assert "Do not merge or promote the change." in task


def test_completed_in_scope_result_with_all_required_gates_is_acceptable() -> None:
    review = review_improvement_result(
        _package(),
        ImprovementResult(
            status=ImprovementStatus.COMPLETED,
            changed_files=("capture_import/mintmark.py", "test_mintmark.py"),
            validation=(
                ValidationEvidence("focused-tests", True),
                ValidationEvidence("pyright", True),
                ValidationEvidence("full-regression", True),
            ),
            risks=("catalog edge cases remain externally governed",),
        ),
    )

    assert review.acceptable is True
    assert review.violations == ()


def test_out_of_scope_change_fails_closed() -> None:
    review = review_improvement_result(
        _package(),
        ImprovementResult(
            status=ImprovementStatus.COMPLETED,
            changed_files=("capture_import/mintmark.py", "unrelated.py"),
            validation=(
                ValidationEvidence("focused-tests", True),
                ValidationEvidence("pyright", True),
                ValidationEvidence("full-regression", True),
            ),
        ),
    )

    assert review.acceptable is False
    assert "out-of-scope changed files: unrelated.py" in review.violations


def test_missing_or_failed_required_gate_fails_closed() -> None:
    review = review_improvement_result(
        _package(),
        ImprovementResult(
            status=ImprovementStatus.COMPLETED,
            changed_files=("capture_import/mintmark.py",),
            validation=(
                ValidationEvidence("focused-tests", True),
                ValidationEvidence("pyright", False, "type error"),
            ),
        ),
    )

    assert review.acceptable is False
    assert "required gate failed: pyright" in review.violations
    assert "missing required gate evidence: full-regression" in review.violations


def test_duplicate_validation_names_fail_closed() -> None:
    review = review_improvement_result(
        _package(),
        ImprovementResult(
            status=ImprovementStatus.COMPLETED,
            changed_files=("capture_import/mintmark.py",),
            validation=(
                ValidationEvidence("focused-tests", True),
                ValidationEvidence("pyright", True),
                ValidationEvidence("pyright", True),
                ValidationEvidence("full-regression", True),
            ),
        ),
    )

    assert review.acceptable is False
    assert "duplicate validation evidence names" in review.violations


def test_stopped_result_is_never_acceptable_even_with_passing_prior_evidence() -> None:
    review = review_improvement_result(
        _package(),
        ImprovementResult(
            status=ImprovementStatus.STOPPED,
            changed_files=("capture_import/mintmark.py",),
            validation=(
                ValidationEvidence("focused-tests", True),
                ValidationEvidence("pyright", True),
                ValidationEvidence("full-regression", True),
            ),
            stopped_gate="manual-review",
            unresolved_issues=("scope ambiguity",),
        ),
    )

    assert review.acceptable is False
    assert "implementation stopped before successful completion" in review.violations


def test_completed_result_cannot_report_stopped_gate() -> None:
    review = review_improvement_result(
        _package(),
        ImprovementResult(
            status=ImprovementStatus.COMPLETED,
            changed_files=("capture_import/mintmark.py",),
            validation=(
                ValidationEvidence("focused-tests", True),
                ValidationEvidence("pyright", True),
                ValidationEvidence("full-regression", True),
            ),
            stopped_gate="pyright",
        ),
    )

    assert review.acceptable is False
    assert "completed result must not report stopped_gate" in review.violations
