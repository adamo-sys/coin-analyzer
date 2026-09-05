from diagnostic_agent import DiagnosticFinding
from improvement_agent import ImprovementResult, ImprovementStatus, ValidationEvidence, build_remediation_package
from parallel_experiment import CandidateSpec, ExperimentState, execute_parallel_experiment
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


class _MutatingExecutor(_Executor):
    def __init__(self, result, external_evidence):
        super().__init__(result)
        self.external_evidence = external_evidence

    def execute(self, task, package):
        self.calls += 1
        self.external_evidence.clear()
        return self.result


def _package():
    finding = DiagnosticFinding(
        dimension="field",
        key="mintmark",
        failure_count=2,
        observation_ids=("obs-1", "obs-2"),
        hypothesis="mintmark mismatch",
        recommended_action="bounded fix",
        relevant_paths=("recognition/mintmark.py",),
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


def _good_evidence():
    return (InvariantEvidence("collection remains unchanged", True),)


def _spec(candidate_id, executor, evidence=None):
    return CandidateSpec(candidate_id, executor, evidence if evidence is not None else _good_evidence())


def _decision_signature(run):
    return (
        run.state,
        run.viable_candidate_ids,
        run.preferred_candidate_id,
        run.human_review_required,
        tuple((item.candidate_id, item.state, item.terminal_reason) for item in run.candidates),
    )


def test_identical_inputs_produce_identical_decision_artifacts():
    first = execute_parallel_experiment(
        "exp-1",
        _package(),
        (_spec("a", _Executor(_result())), _spec("b", _Executor(_result()))),
    )
    second = execute_parallel_experiment(
        "exp-1",
        _package(),
        (_spec("a", _Executor(_result())), _spec("b", _Executor(_result()))),
    )

    assert _decision_signature(first) == _decision_signature(second)


def test_experiment_id_changes_trace_identity_not_decision():
    first = execute_parallel_experiment(
        "exp-1",
        _package(),
        (_spec("a", _Executor(_result())), _spec("b", _Executor(_result()))),
    )
    second = execute_parallel_experiment(
        "exp-2",
        _package(),
        (_spec("a", _Executor(_result())), _spec("b", _Executor(_result()))),
    )

    assert first.experiment_id != second.experiment_id
    assert _decision_signature(first) == _decision_signature(second)


def test_each_candidate_executes_once_even_when_one_fails():
    failed = _Unavailable()
    good = _Executor(_result())

    run = execute_parallel_experiment(
        "exp-1", _package(), (_spec("a", failed), _spec("b", good))
    )

    assert failed.calls == 1
    assert good.calls == 1
    assert run.state is ExperimentState.ONE_VIABLE_CANDIDATE
    assert run.viable_candidate_ids == ("b",)


def test_candidate_failure_does_not_trigger_replacement_or_extra_execution():
    first = _Unavailable()
    second = _Executor(_result())

    run = execute_parallel_experiment(
        "exp-1", _package(), (_spec("a", first), _spec("b", second))
    )

    assert first.calls == 1
    assert second.calls == 1
    assert tuple(item.candidate_id for item in run.candidates) == ("a", "b")


def test_invariant_evidence_is_snapshotted_before_first_candidate_runs():
    second_evidence = [InvariantEvidence("collection remains unchanged", True)]
    first = _MutatingExecutor(_result(), second_evidence)
    second = _Executor(_result())

    run = execute_parallel_experiment(
        "exp-1",
        _package(),
        (_spec("a", first), _spec("b", second, second_evidence)),
    )

    assert second_evidence == []
    assert run.state is ExperimentState.MULTIPLE_VIABLE_CANDIDATES
    assert run.viable_candidate_ids == ("a", "b")


def test_failed_gate_is_candidate_local():
    bad = _Executor(
        _result(
            validation=(
                ValidationEvidence("focused-tests", True),
                ValidationEvidence("pyright", False),
                ValidationEvidence("full-regression", True),
            )
        )
    )
    good = _Executor(_result())

    run = execute_parallel_experiment(
        "exp-1", _package(), (_spec("a", bad), _spec("b", good))
    )

    assert run.state is ExperimentState.ONE_VIABLE_CANDIDATE
    assert run.viable_candidate_ids == ("b",)


def test_out_of_scope_change_is_candidate_local():
    bad = _Executor(_result(changed_files=("outside.py",)))
    good = _Executor(_result())

    run = execute_parallel_experiment(
        "exp-1", _package(), (_spec("a", bad), _spec("b", good))
    )

    assert run.state is ExperimentState.ONE_VIABLE_CANDIDATE
    assert run.viable_candidate_ids == ("b",)


def test_zero_viable_candidates_never_require_human_promotion_review():
    bad = _Unavailable()
    worse = _Unavailable()

    run = execute_parallel_experiment(
        "exp-1", _package(), (_spec("a", bad), _spec("b", worse))
    )

    assert run.state is ExperimentState.NO_VIABLE_CANDIDATES
    assert run.viable_candidate_ids == ()
    assert run.preferred_candidate_id is None
    assert run.human_review_required is False


def test_tied_viable_candidates_remain_for_human_selection():
    run = execute_parallel_experiment(
        "exp-1",
        _package(),
        (_spec("a", _Executor(_result())), _spec("b", _Executor(_result()))),
    )

    assert run.state is ExperimentState.MULTIPLE_VIABLE_CANDIDATES
    assert run.preferred_candidate_id is None
    assert run.human_review_required is True


def test_preference_is_evidence_only_and_does_not_reduce_viable_set():
    narrow = _Executor(_result(changed_files=("recognition/mintmark.py",)))
    broad = _Executor(_result())

    run = execute_parallel_experiment(
        "exp-1", _package(), (_spec("a", narrow), _spec("b", broad))
    )

    assert run.state is ExperimentState.MULTIPLE_VIABLE_CANDIDATES
    assert run.viable_candidate_ids == ("a", "b")
    assert run.preferred_candidate_id == "a"
    assert run.human_review_required is True
