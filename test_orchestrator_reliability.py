from diagnostic_agent import DiagnosticFinding
from improvement_agent import ImprovementResult, ImprovementStatus, ValidationEvidence
from orchestrator import OrchestratorRequest, OrchestratorState, execute_orchestrator_run
from reviewer_agent import InvariantEvidence


class _RecordingExecutor:
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


def _finding():
    return DiagnosticFinding(
        dimension="field",
        key="mintmark",
        failure_count=3,
        observation_ids=("obs-1", "obs-2", "obs-3"),
        hypothesis="mintmark mismatch",
        recommended_action="add bounded mintmark regression coverage",
        relevant_paths=("recognition/mintmark.py",),
    )


def _request(run_id="run-reliability-001"):
    return OrchestratorRequest(
        run_id=run_id,
        finding=_finding(),
        objective="Fix the bounded mintmark regression.",
        allowed_paths=("recognition/mintmark.py", "test_mintmark.py"),
        invariants=("collection remains unchanged",),
        focused_tests=("pytest test_mintmark.py -q",),
        required_gates=("focused-tests", "pyright", "full-regression"),
    )


def _success_result():
    return ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=("recognition/mintmark.py", "test_mintmark.py"),
        validation=(
            ValidationEvidence("focused-tests", True, "11 passed"),
            ValidationEvidence("pyright", True, "0 errors"),
            ValidationEvidence("full-regression", True, "green"),
        ),
    )


def _invariants():
    return (InvariantEvidence("collection remains unchanged", True, "verified"),)


def test_identical_structured_inputs_produce_identical_run_artifacts():
    first_executor = _RecordingExecutor(_success_result())
    second_executor = _RecordingExecutor(_success_result())

    first = execute_orchestrator_run(_request(), first_executor, _invariants())
    second = execute_orchestrator_run(_request(), second_executor, _invariants())

    assert first == second
    assert first.state is OrchestratorState.READY_FOR_HUMAN_REVIEW
    assert first_executor.calls == second_executor.calls == 1
    assert first_executor.tasks == second_executor.tasks
    assert first_executor.packages == second_executor.packages


def test_successful_runs_never_cross_the_human_promotion_boundary():
    executor = _RecordingExecutor(_success_result())
    run = execute_orchestrator_run(_request(), executor, _invariants())

    assert run.state is OrchestratorState.READY_FOR_HUMAN_REVIEW
    assert run.human_review_required is True
    assert run.ready_for_human_review is True
    assert run.terminal_reason is None
    assert run.transitions[-1].to_state is OrchestratorState.READY_FOR_HUMAN_REVIEW


def test_run_id_changes_trace_identity_without_changing_pipeline_decision():
    first = execute_orchestrator_run(
        _request("run-reliability-a"),
        _RecordingExecutor(_success_result()),
        _invariants(),
    )
    second = execute_orchestrator_run(
        _request("run-reliability-b"),
        _RecordingExecutor(_success_result()),
        _invariants(),
    )

    assert first.run_id != second.run_id
    assert first.state is second.state is OrchestratorState.READY_FOR_HUMAN_REVIEW
    assert first.transitions == second.transitions
    assert first.remediation_package == second.remediation_package
    assert first.implementation_result == second.implementation_result
    assert first.reviewer_report == second.reviewer_report


def test_failed_invariant_run_is_deterministically_terminal_and_single_shot():
    executor = _RecordingExecutor(_success_result())
    evidence = (InvariantEvidence("collection remains unchanged", False, "mutation detected"),)

    run = execute_orchestrator_run(_request(), executor, evidence)

    assert executor.calls == 1
    assert run.state is OrchestratorState.STOPPED
    assert run.human_review_required is False
    assert run.ready_for_human_review is False
    assert "invariant failed" in run.terminal_reason
    assert run.transitions[-1].to_state is OrchestratorState.STOPPED
    assert OrchestratorState.REVIEW_COMPLETE not in [item.to_state for item in run.transitions]
    assert OrchestratorState.READY_FOR_HUMAN_REVIEW not in [
        item.to_state for item in run.transitions
    ]


def test_failed_gate_run_is_deterministically_terminal_and_single_shot():
    failed = ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=("recognition/mintmark.py",),
        validation=(
            ValidationEvidence("focused-tests", True),
            ValidationEvidence("pyright", False, "type error"),
            ValidationEvidence("full-regression", True),
        ),
    )
    executor = _RecordingExecutor(failed)

    run = execute_orchestrator_run(_request(), executor, _invariants())

    assert executor.calls == 1
    assert run.state is OrchestratorState.STOPPED
    assert "required gate failed: pyright" in run.terminal_reason
    assert run.transitions[-1].from_state is OrchestratorState.PACKAGE_FROZEN
    assert run.transitions[-1].to_state is OrchestratorState.STOPPED


def test_out_of_scope_change_never_reaches_implementation_complete_state():
    result = ImprovementResult(
        status=ImprovementStatus.COMPLETED,
        changed_files=("recognition/mintmark.py", "unauthorized.py"),
        validation=(
            ValidationEvidence("focused-tests", True),
            ValidationEvidence("pyright", True),
            ValidationEvidence("full-regression", True),
        ),
    )
    executor = _RecordingExecutor(result)

    run = execute_orchestrator_run(_request(), executor, _invariants())

    states = [item.to_state for item in run.transitions]
    assert executor.calls == 1
    assert run.state is OrchestratorState.STOPPED
    assert OrchestratorState.IMPLEMENTATION_COMPLETE not in states
    assert OrchestratorState.REVIEW_COMPLETE not in states
    assert OrchestratorState.READY_FOR_HUMAN_REVIEW not in states


def test_transition_history_is_forward_only_for_successful_run():
    run = execute_orchestrator_run(
        _request(),
        _RecordingExecutor(_success_result()),
        _invariants(),
    )

    order = {
        OrchestratorState.PENDING: 0,
        OrchestratorState.DIAGNOSED: 1,
        OrchestratorState.PACKAGE_FROZEN: 2,
        OrchestratorState.IMPLEMENTATION_COMPLETE: 3,
        OrchestratorState.REVIEW_COMPLETE: 4,
        OrchestratorState.READY_FOR_HUMAN_REVIEW: 5,
    }
    for transition in run.transitions:
        assert order[transition.to_state] > order[transition.from_state]


def test_repeated_independent_runs_remain_single_shot():
    first_executor = _RecordingExecutor(_success_result())
    second_executor = _RecordingExecutor(_success_result())

    first = execute_orchestrator_run(_request("run-1"), first_executor, _invariants())
    second = execute_orchestrator_run(_request("run-2"), second_executor, _invariants())

    assert first.state is OrchestratorState.READY_FOR_HUMAN_REVIEW
    assert second.state is OrchestratorState.READY_FOR_HUMAN_REVIEW
    assert first_executor.calls == 1
    assert second_executor.calls == 1
