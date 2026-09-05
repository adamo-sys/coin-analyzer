from diagnostic_agent import DiagnosticFinding
from improvement_agent import ImprovementResult, ImprovementStatus, ValidationEvidence, build_remediation_package
from parallel_experiment import ExperimentState
from reviewer_agent import InvariantEvidence
from specialized_parallel_experiment import (
    SpecializedCandidateSpec,
    StrategyKind,
    execute_specialized_parallel_experiment,
)


class _Executor:
    def __init__(self, result):
        self.result = result
        self.calls = 0
        self.tasks = []
        self.packages = []

    def execute(self, task, package):
        self.calls += 1
        self.tasks.append(task)
        self.packages.append(package)
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


def _result(changed_files=("recognition/mintmark.py", "test_mintmark.py")):
    return ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=changed_files,
        validation=(
            ValidationEvidence("focused-tests", True),
            ValidationEvidence("pyright", True),
            ValidationEvidence("full-regression", True),
        ),
    )


def _spec(candidate_id, strategy, executor, summary=""):
    return SpecializedCandidateSpec(
        candidate_id=candidate_id,
        strategy=strategy,
        executor=executor,
        invariant_evidence=(InvariantEvidence("collection remains unchanged", True),),
        strategy_summary=summary,
    )


def test_accepts_exact_specialized_pair_and_preserves_metadata():
    a, b = _Executor(_result()), _Executor(_result())
    run = execute_specialized_parallel_experiment(
        "exp-11",
        _package(),
        (
            _spec("minimal", StrategyKind.MINIMAL_CHANGE, a, "smallest compliant change"),
            _spec("alternative", StrategyKind.ALTERNATIVE_DESIGN, b, "different bounded structure"),
        ),
    )
    assert run.experiment.state is ExperimentState.MULTIPLE_VIABLE_CANDIDATES
    assert tuple(item.strategy for item in run.strategy_metadata) == (
        StrategyKind.MINIMAL_CHANGE,
        StrategyKind.ALTERNATIVE_DESIGN,
    )
    assert run.strategy_metadata[0].strategy_summary == "smallest compliant change"
    assert a.calls == b.calls == 1


def test_duplicate_strategy_kinds_stop_before_execution():
    a, b = _Executor(_result()), _Executor(_result())
    run = execute_specialized_parallel_experiment(
        "exp-11",
        _package(),
        (
            _spec("a", StrategyKind.MINIMAL_CHANGE, a),
            _spec("b", StrategyKind.MINIMAL_CHANGE, b),
        ),
    )
    assert run.experiment.state is ExperimentState.STOPPED
    assert a.calls == b.calls == 0


def test_both_candidates_receive_same_frozen_package():
    package = _package()
    a, b = _Executor(_result()), _Executor(_result())
    execute_specialized_parallel_experiment(
        "exp-11",
        package,
        (
            _spec("a", StrategyKind.MINIMAL_CHANGE, a),
            _spec("b", StrategyKind.ALTERNATIVE_DESIGN, b),
        ),
    )
    assert a.packages == [package]
    assert b.packages == [package]


def test_strategy_instructions_are_distinct_but_do_not_mutate_package():
    package = _package()
    a, b = _Executor(_result()), _Executor(_result())
    execute_specialized_parallel_experiment(
        "exp-11",
        package,
        (
            _spec("a", StrategyKind.MINIMAL_CHANGE, a),
            _spec("b", StrategyKind.ALTERNATIVE_DESIGN, b),
        ),
    )
    assert "MINIMAL_CHANGE" in a.tasks[0]
    assert "ALTERNATIVE_DESIGN" in b.tasks[0]
    assert a.packages[0] == b.packages[0] == package
    assert package.allowed_paths == ("recognition/mintmark.py", "test_mintmark.py")
    assert package.required_gates == ("focused-tests", "pyright", "full-regression")


def test_each_candidate_executes_exactly_once():
    a, b = _Executor(_result()), _Executor(_result())
    execute_specialized_parallel_experiment(
        "exp-11",
        _package(),
        (
            _spec("a", StrategyKind.MINIMAL_CHANGE, a),
            _spec("b", StrategyKind.ALTERNATIVE_DESIGN, b),
        ),
    )
    assert a.calls == 1
    assert b.calls == 1


def test_strategy_metadata_does_not_auto_promote_tied_candidates():
    a, b = _Executor(_result()), _Executor(_result())
    run = execute_specialized_parallel_experiment(
        "exp-11",
        _package(),
        (
            _spec("a", StrategyKind.MINIMAL_CHANGE, a, "minimal"),
            _spec("b", StrategyKind.ALTERNATIVE_DESIGN, b, "alternative"),
        ),
    )
    assert run.experiment.preferred_candidate_id is None
    assert run.experiment.viable_candidate_ids == ("a", "b")
    assert run.experiment.human_review_required is True


def test_existing_deterministic_preference_is_preserved():
    a = _Executor(_result(changed_files=("recognition/mintmark.py",)))
    b = _Executor(_result())
    run = execute_specialized_parallel_experiment(
        "exp-11",
        _package(),
        (
            _spec("a", StrategyKind.MINIMAL_CHANGE, a),
            _spec("b", StrategyKind.ALTERNATIVE_DESIGN, b),
        ),
    )
    assert run.experiment.preferred_candidate_id == "a"
    assert run.experiment.viable_candidate_ids == ("a", "b")
    assert run.experiment.human_review_required is True
