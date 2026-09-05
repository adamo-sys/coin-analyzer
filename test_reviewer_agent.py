from __future__ import annotations

from diagnostic_agent import DiagnosticFinding
from improvement_agent import (
    ImprovementResult,
    ImprovementStatus,
    ValidationEvidence,
    build_remediation_package,
)
from reviewer_agent import (
    InvariantEvidence,
    ReviewRecommendation,
    review_candidate,
)


def _package():
    finding = DiagnosticFinding(
        dimension="field",
        key="mintmark",
        failure_count=3,
        observation_ids=("obs-1", "obs-2", "obs-3"),
        hypothesis="mintmark hypothesis",
        recommended_action="inspect mintmark path",
        relevant_paths=("capture_import/mintmark.py",),
    )
    return build_remediation_package(
        finding,
        objective="Fix the bounded mintmark failure without changing unrelated behavior.",
        allowed_paths=("capture_import/mintmark.py", "test_mintmark.py"),
        invariants=("confirmed observations remain immutable", "no collection mutation"),
        focused_tests=("pytest test_mintmark.py -q",),
        required_gates=("focused-tests", "pyright", "full-regression"),
    )


def _valid_result() -> ImprovementResult:
    return ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=("capture_import/mintmark.py", "test_mintmark.py"),
        validation=(
            ValidationEvidence("focused-tests", True),
            ValidationEvidence("pyright", True),
            ValidationEvidence("full-regression", True),
        ),
        risks=("catalog edge cases remain externally governed",),
    )


def _invariants() -> tuple[InvariantEvidence, ...]:
    return (
        InvariantEvidence("confirmed observations remain immutable", True, "reviewed diff"),
        InvariantEvidence("no collection mutation", True, "reviewed persistence boundary"),
    )


def test_valid_independent_evidence_permits_promotion_recommendation() -> None:
    report = review_candidate(_package(), _valid_result(), _invariants())

    assert report.recommendation is ReviewRecommendation.PASS
    assert report.promotion_permitted is True
    assert report.findings == ()
    assert report.verified_invariants == (
        "confirmed observations remain immutable",
        "no collection mutation",
    )


def test_out_of_scope_change_rejects_candidate() -> None:
    result = ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=("capture_import/mintmark.py", "unrelated.py"),
        validation=_valid_result().validation,
    )

    report = review_candidate(_package(), result, _invariants())

    assert report.recommendation is ReviewRecommendation.FAIL
    assert "out-of-scope changed files: unrelated.py" in report.findings


def test_missing_and_failed_required_validation_reject_candidate() -> None:
    result = ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=("capture_import/mintmark.py",),
        validation=(
            ValidationEvidence("focused-tests", True),
            ValidationEvidence("pyright", False, "type error"),
        ),
    )

    report = review_candidate(_package(), result, _invariants())

    assert "required gate failed: pyright" in report.findings
    assert "missing required gate evidence: full-regression" in report.findings
    assert report.promotion_permitted is False


def test_duplicate_or_contradictory_validation_evidence_rejects_candidate() -> None:
    result = ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=("capture_import/mintmark.py",),
        validation=(
            ValidationEvidence("focused-tests", True),
            ValidationEvidence("pyright", True),
            ValidationEvidence("pyright", False, "contradiction"),
            ValidationEvidence("full-regression", True),
        ),
    )

    report = review_candidate(_package(), result, _invariants())

    assert "duplicate or contradictory validation evidence names" in report.findings
    assert report.promotion_permitted is False


def test_stopped_implementation_rejects_candidate() -> None:
    result = ImprovementResult(
        status=ImprovementStatus.STOPPED,
        changed_files=("capture_import/mintmark.py",),
        validation=_valid_result().validation,
        stopped_gate="manual-review",
    )

    report = review_candidate(_package(), result, _invariants())

    assert "implementation stopped before successful completion" in report.findings
    assert report.promotion_permitted is False


def test_unresolved_issue_is_blocking() -> None:
    result = ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=("capture_import/mintmark.py",),
        validation=_valid_result().validation,
        unresolved_issues=("scope ambiguity",),
    )

    report = review_candidate(_package(), result, _invariants())

    assert "unresolved blocking issue: scope ambiguity" in report.findings
    assert report.promotion_permitted is False


def test_missing_or_failed_invariant_evidence_fails_closed() -> None:
    report = review_candidate(
        _package(),
        _valid_result(),
        (InvariantEvidence("confirmed observations remain immutable", False),),
    )

    assert "invariant failed: confirmed observations remain immutable" in report.findings
    assert "missing invariant evidence: no collection mutation" in report.findings
    assert report.promotion_permitted is False


def test_duplicate_invariant_evidence_fails_closed() -> None:
    report = review_candidate(
        _package(),
        _valid_result(),
        (
            InvariantEvidence("confirmed observations remain immutable", True),
            InvariantEvidence("confirmed observations remain immutable", False),
            InvariantEvidence("no collection mutation", True),
        ),
    )

    assert "duplicate or contradictory invariant evidence names" in report.findings
    assert report.promotion_permitted is False


def test_reviewer_rejects_attempt_to_broaden_invariant_scope() -> None:
    report = review_candidate(
        _package(),
        _valid_result(),
        _invariants() + (InvariantEvidence("new reviewer-created invariant", True),),
    )

    assert (
        "unexpected invariant evidence outside authorized review scope: new reviewer-created invariant"
        in report.findings
    )
    assert report.promotion_permitted is False


def test_malformed_and_duplicate_changed_paths_fail_closed() -> None:
    malformed = ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=("../escape.py",),
        validation=_valid_result().validation,
    )
    duplicate = ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=("capture_import/mintmark.py", "capture_import\\mintmark.py"),
        validation=_valid_result().validation,
    )

    malformed_report = review_candidate(_package(), malformed, _invariants())
    duplicate_report = review_candidate(_package(), duplicate, _invariants())

    assert "malformed changed file path: ../escape.py" in malformed_report.findings
    assert "duplicate changed file paths after normalization" in duplicate_report.findings
    assert malformed_report.promotion_permitted is False
    assert duplicate_report.promotion_permitted is False


def test_empty_validation_or_unresolved_issue_entries_fail_closed() -> None:
    result = ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=("capture_import/mintmark.py",),
        validation=(
            ValidationEvidence("focused-tests", True),
            ValidationEvidence("pyright", True),
            ValidationEvidence("full-regression", True),
            ValidationEvidence("   ", True),
        ),
        unresolved_issues=("   ",),
    )

    report = review_candidate(_package(), result, _invariants())

    assert "validation evidence names must be non-empty" in report.findings
    assert "unresolved issue entries must be non-empty" in report.findings
    assert report.promotion_permitted is False
