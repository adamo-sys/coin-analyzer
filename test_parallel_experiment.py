from diagnostic_agent import DiagnosticFinding
from improvement_agent import ImprovementResult, ImprovementStatus, ValidationEvidence, build_remediation_package
from parallel_experiment import CandidateSpec, CandidateState, ExperimentState, execute_parallel_experiment
from reviewer_agent import InvariantEvidence


class _Executor:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def execute(self, task, package):
        self.calls += 1
        return self.result


class _Unavailable:
    def __init__(self):
        self.calls = 0

    def execute(self, task, package):
        self.calls += 1
        raise RuntimeError("candidate unavailable")


def _package():
    finding = DiagnosticFinding(
        dimension="field", key="mintmark", failure_count=2,
        observation_ids=("obs-1", "obs-2"), hypothesis="mintmark mismatch",
        recommended_action="bounded fix", relevant_paths=("recognition/mintmark.py",),
    )
    return build_remediation_package(
        finding,
        objective="Fix bounded mintmark regression.",
        allowed_paths=("recognition/mintmark.py", "test_mintmark.py"),
        invariants=("collection remains unchanged",),
        focused_tests=("pytest test_mintmark.py -q",),
        required_gates=("focused-tests", "pyright", "full-regression"),
    )


def _result(**overrides):
    values = dict(
        status=ImprovementStatus.COMPLETED,
        changed_files=("recognition/mintmark.py", "test_mintmark.py"),
        validation=(
            ValidationEvidence("focused-tests", True),
            ValidationEvidence("pyright", True),
            ValidationEvidence("full-regression", True),
        ),
    )
    values.update(overrides)
    return ImprovementResult(**values)


def _spec(candidate_id, executor, evidence=None):
    return CandidateSpec(
        candidate_id,
        executor,
        tuple(evidence if evidence is not None else (InvariantEvidence("collection remains unchanged", True),)),
    )


def test_two_valid_candidates_remain_multiple_when_tied():
    a, b = _Executor(_result()), _Executor(_result())
    run = execute_parallel_experiment("exp-1", _package(), (_spec("a", a), _spec("b", b)))
    assert run.state is ExperimentState.MULTIPLE_VIABLE_CANDIDATES
    assert run.viable_candidate_ids == ("a", "b")
    assert run.preferred_candidate_id is None
    assert run.human_review_required is True
    assert a.calls == b.calls == 1


def test_one_valid_one_rejected_produces_one_viable():
    a, b = _Executor(_result()), _Unavailable()
    run = execute_parallel_experiment("exp-1", _package(), (_spec("a", a), _spec("b", b)))
    assert run.state is ExperimentState.ONE_VIABLE_CANDIDATE
    assert run.viable_candidate_ids == ("a",)
    assert run.preferred_candidate_id == "a"
    assert b.calls == 1


def test_two_rejected_produce_no_viable_candidates():
    bad = _result(validation=(ValidationEvidence("focused-tests", False), ValidationEvidence("pyright", True), ValidationEvidence("full-regression", True)))
    a, b = _Executor(bad), _Executor(bad)
    run = execute_parallel_experiment("exp-1", _package(), (_spec("a", a), _spec("b", b)))
    assert run.state is ExperimentState.NO_VIABLE_CANDIDATES
    assert run.human_review_required is False
    assert all(item.state is CandidateState.REJECTED for item in run.candidates)


def test_duplicate_candidate_ids_stop_before_execution():
    a, b = _Executor(_result()), _Executor(_result())
    run = execute_parallel_experiment("exp-1", _package(), (_spec("same", a), _spec("same", b)))
    assert run.state is ExperimentState.STOPPED
    assert a.calls == b.calls == 0


def test_empty_experiment_id_stops_before_execution():
    a, b = _Executor(_result()), _Executor(_result())
    run = execute_parallel_experiment(" ", _package(), (_spec("a", a), _spec("b", b)))
    assert run.state is ExperimentState.STOPPED
    assert a.calls == b.calls == 0


def test_failed_invariant_rejects_only_affected_candidate():
    a, b = _Executor(_result()), _Executor(_result())
    failed = (InvariantEvidence("collection remains unchanged", False),)
    run = execute_parallel_experiment("exp-1", _package(), (_spec("a", a, failed), _spec("b", b)))
    assert run.state is ExperimentState.ONE_VIABLE_CANDIDATE
    assert run.viable_candidate_ids == ("b",)
    assert a.calls == b.calls == 1


def test_out_of_scope_change_rejects_only_affected_candidate():
    a = _Executor(_result(changed_files=("outside.py",)))
    b = _Executor(_result())
    run = execute_parallel_experiment("exp-1", _package(), (_spec("a", a), _spec("b", b)))
    assert run.state is ExperimentState.ONE_VIABLE_CANDIDATE
    assert run.viable_candidate_ids == ("b",)


def test_unresolved_issue_rejects_only_affected_candidate():
    a = _Executor(_result(unresolved_issues=("manual investigation",)))
    b = _Executor(_result())
    run = execute_parallel_experiment("exp-1", _package(), (_spec("a", a), _spec("b", b)))
    assert run.state is ExperimentState.ONE_VIABLE_CANDIDATE
    assert run.viable_candidate_ids == ("b",)


def test_deterministic_comparison_prefers_fewer_changed_files():
    a = _Executor(_result(changed_files=("recognition/mintmark.py",)))
    b = _Executor(_result())
    run = execute_parallel_experiment("exp-1", _package(), (_spec("a", a), _spec("b", b)))
    assert run.state is ExperimentState.MULTIPLE_VIABLE_CANDIDATES
    assert run.preferred_candidate_id == "a"


def test_identical_structured_evidence_produces_same_aggregate_decision():
    first = execute_parallel_experiment("exp-1", _package(), (_spec("a", _Executor(_result())), _spec("b", _Executor(_result()))))
    second = execute_parallel_experiment("exp-1", _package(), (_spec("a", _Executor(_result())), _spec("b", _Executor(_result()))))
    assert first.state == second.state
    assert first.viable_candidate_ids == second.viable_candidate_ids
    assert first.preferred_candidate_id == second.preferred_candidate_id


def test_candidate_failure_is_single_shot_without_replacement():
    a, b = _Unavailable(), _Executor(_result())
    run = execute_parallel_experiment("exp-1", _package(), (_spec("a", a), _spec("b", b)))
    assert run.state is ExperimentState.ONE_VIABLE_CANDIDATE
    assert a.calls == 1
    assert b.calls == 1
    assert tuple(item.candidate_id for item in run.candidates) == ("a", "b")
