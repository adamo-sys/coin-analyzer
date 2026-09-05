from dataclasses import replace

import pytest
from hypothesis import given, strategies as st

from diagnostic_agent import DiagnosticFinding
from improvement_agent import (
    ImprovementResult,
    ImprovementStatus,
    ValidationEvidence,
    build_remediation_package,
)
from reviewer_agent import InvariantEvidence, ReviewRecommendation, review_candidate


def _finding() -> DiagnosticFinding:
    return DiagnosticFinding(
        dimension="field",
        key="mintmark",
        failure_count=2,
        observation_ids=("obs-1", "obs-2"),
        hypothesis="mintmark mismatch",
        recommended_action="bounded fix",
        relevant_paths=("recognition/mintmark.py",),
    )


def _package(*, allowed_paths=("recognition/mintmark.py", "test_mintmark.py")):
    return build_remediation_package(
        _finding(),
        objective="Fix bounded mintmark regression.",
        allowed_paths=allowed_paths,
        invariants=("collection remains unchanged", "scope remains bounded"),
        focused_tests=("pytest test_mintmark.py -q",),
        required_gates=("focused-tests", "pyright", "full-regression"),
    )


def _valid_result() -> ImprovementResult:
    return ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=("recognition/mintmark.py",),
        validation=(
            ValidationEvidence("focused-tests", True),
            ValidationEvidence("pyright", True),
            ValidationEvidence("full-regression", True),
        ),
    )


_SAFE_COMPONENT = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"),
        whitelist_characters="_-",
    ),
    min_size=1,
    max_size=16,
).filter(lambda value: value not in {".", ".."})


@given(st.lists(_SAFE_COMPONENT, min_size=1, max_size=5, unique=True))
def test_allowed_paths_are_deterministically_normalized_and_sorted(parts):
    raw = [f"dir\\{part}.py" for part in parts]
    package = _package(allowed_paths=raw)
    assert package.allowed_paths == tuple(sorted(f"dir/{part}.py" for part in parts))


@given(_SAFE_COMPONENT)
def test_duplicate_paths_after_separator_normalization_fail_closed(part):
    with pytest.raises(ValueError, match="allowed_paths must not contain duplicates"):
        _package(allowed_paths=(f"dir/{part}.py", f"dir\\{part}.py"))


@given(
    prefix=st.lists(_SAFE_COMPONENT, min_size=0, max_size=3),
    suffix=st.lists(_SAFE_COMPONENT, min_size=0, max_size=3),
)
def test_any_parent_traversal_in_allowed_path_is_rejected(prefix, suffix):
    segments = [*prefix, "..", *suffix, "file.py"]
    candidate = "/".join(segments)
    with pytest.raises(ValueError, match="repository-relative paths without traversal"):
        _package(allowed_paths=(candidate,))


@given(st.permutations(("focused-tests", "pyright", "full-regression")))
def test_reviewer_decision_is_invariant_to_validation_evidence_order(order):
    package = _package()
    evidence = {
        "focused-tests": ValidationEvidence("focused-tests", True),
        "pyright": ValidationEvidence("pyright", True),
        "full-regression": ValidationEvidence("full-regression", True),
    }
    result = replace(_valid_result(), validation=tuple(evidence[name] for name in order))
    invariants = (
        InvariantEvidence("collection remains unchanged", True),
        InvariantEvidence("scope remains bounded", True),
    )
    report = review_candidate(package, result, invariants)
    assert report.recommendation is ReviewRecommendation.PASS
    assert report.findings == ()


@given(st.permutations(("collection remains unchanged", "scope remains bounded")))
def test_reviewer_decision_is_invariant_to_invariant_evidence_order(order):
    package = _package()
    evidence = {name: InvariantEvidence(name, True) for name in order}
    report = review_candidate(package, _valid_result(), tuple(evidence[name] for name in order))
    assert report.recommendation is ReviewRecommendation.PASS
    assert report.findings == ()
    assert report.verified_invariants == package.invariants


@given(_SAFE_COMPONENT)
def test_parent_traversal_changed_file_always_fails_independent_review(part):
    package = _package()
    result = replace(_valid_result(), changed_files=(f"recognition/{part}/../mintmark.py",))
    report = review_candidate(
        package,
        result,
        (
            InvariantEvidence("collection remains unchanged", True),
            InvariantEvidence("scope remains bounded", True),
        ),
    )
    assert report.recommendation is ReviewRecommendation.FAIL
    assert any("malformed changed file path" in finding for finding in report.findings)


@given(_SAFE_COMPONENT)
def test_failed_required_gate_cannot_be_hidden_by_extra_passing_evidence(extra_name):
    package = _package()
    assume_name = extra_name if extra_name not in package.required_gates else f"extra-{extra_name}"
    result = replace(
        _valid_result(),
        validation=(
            ValidationEvidence("focused-tests", True),
            ValidationEvidence("pyright", False),
            ValidationEvidence("full-regression", True),
            ValidationEvidence(assume_name, True),
        ),
    )
    report = review_candidate(
        package,
        result,
        (
            InvariantEvidence("collection remains unchanged", True),
            InvariantEvidence("scope remains bounded", True),
        ),
    )
    assert report.recommendation is ReviewRecommendation.FAIL
    assert "required gate failed: pyright" in report.findings
