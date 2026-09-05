from diagnostic_agent import DiagnosticFinding
from improvement_agent import ImprovementResult, ImprovementStatus, ValidationEvidence
from orchestrator import OrchestratorRequest, OrchestratorState, execute_orchestrator_run
from reviewer_agent import InvariantEvidence


class _Executor:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def execute(self, task, package):
        self.calls += 1
        return self.result


class _UnavailableExecutor:
    def __init__(self):
        self.calls = 0

    def execute(self, task, package):
        self.calls += 1
        raise RuntimeError("Codex unavailable")


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


def _request(**overrides):
    values = {
        "run_id": "run-001",
        "finding": _finding(),
        "objective": "Fix the bounded mintmark regression.",
        "allowed_paths": ("recognition/mintmark.py", "test_mintmark.py"),
        "invariants": ("collection remains unchanged",),
        "focused_tests": ("pytest test_mintmark.py -q",),
        "required_gates": ("focused-tests", "pyright", "full-regression"),
    }
    values.update(overrides)
    return OrchestratorRequest(**values)


def _success_result(**overrides):
    values = {
        "status": ImprovementStatus.COMPLETED,
        "changed_files": ("recognition/mintmark.py", "test_mintmark.py"),
        "validation": (
            ValidationEvidence("focused-tests", True),
            ValidationEvidence("pyright", True),
            ValidationEvidence("full-regression", True),
        ),
    }
    values.update(overrides)
    return ImprovementResult(**values)


def _invariants(*, passed=True):
    return (InvariantEvidence("collection remains unchanged", passed),)


def test_valid_run_reaches_human_review_with_ordered_transitions():
    executor = _Executor(_success_result())
    run = execute_orchestrator_run(_request(), executor, _invariants())

    assert executor.calls == 1
    assert run.state is OrchestratorState.READY_FOR_HUMAN_REVIEW
    assert run.ready_for_human_review
    assert run.human_review_required is True
    assert run.terminal_reason is None
    assert [item.to_state for item in run.transitions] == [
        OrchestratorState.DIAGNOSED,
        OrchestratorState.PACKAGE_FROZEN,
        OrchestratorState.IMPLEMENTATION_COMPLETE,
        OrchestratorState.REVIEW_COMPLETE,
        OrchestratorState.READY_FOR_HUMAN_REVIEW,
    ]


def test_empty_run_id_stops_before_execution():
    executor = _Executor(_success_result())
    run = execute_orchestrator_run(_request(run_id=" "), executor, _invariants())

    assert run.state is OrchestratorState.STOPPED
    assert executor.calls == 0
    assert run.transitions[-1].from_state is OrchestratorState.PENDING


def test_invalid_package_stops_before_execution():
    executor = _Executor(_success_result())
    run = execute_orchestrator_run(_request(allowed_paths=("../escape.py",)), executor, _invariants())

    assert run.state is OrchestratorState.STOPPED
    assert executor.calls == 0
    assert run.transitions[-1].from_state is OrchestratorState.DIAGNOSED


def test_executor_exception_stops_without_retry():
    executor = _UnavailableExecutor()
    run = execute_orchestrator_run(_request(), executor, _invariants())

    assert run.state is OrchestratorState.STOPPED
    assert executor.calls == 1
    assert "Codex unavailable" in run.terminal_reason


def test_malformed_executor_result_stops():
    executor = _Executor(object())
    run = execute_orchestrator_run(_request(), executor, _invariants())

    assert run.state is OrchestratorState.STOPPED
    assert executor.calls == 1
    assert "malformed result" in run.terminal_reason


def test_out_of_scope_change_stops_before_review_complete():
    executor = _Executor(
        _success_result(changed_files=("recognition/mintmark.py", "outside.py"))
    )
    run = execute_orchestrator_run(_request(), executor, _invariants())

    assert run.state is OrchestratorState.STOPPED
    assert OrchestratorState.IMPLEMENTATION_COMPLETE not in [
        item.to_state for item in run.transitions
    ]


def test_missing_required_gate_stops():
    executor = _Executor(
        _success_result(
            validation=(
                ValidationEvidence("focused-tests", True),
                ValidationEvidence("pyright", True),
            )
        )
    )
    run = execute_orchestrator_run(_request(), executor, _invariants())

    assert run.state is OrchestratorState.STOPPED
    assert "missing required gate evidence" in run.terminal_reason


def test_failed_required_gate_stops():
    executor = _Executor(
        _success_result(
            validation=(
                ValidationEvidence("focused-tests", True),
                ValidationEvidence("pyright", False),
                ValidationEvidence("full-regression", True),
            )
        )
    )
    run = execute_orchestrator_run(_request(), executor, _invariants())

    assert run.state is OrchestratorState.STOPPED
    assert "required gate failed" in run.terminal_reason


def test_stopped_implementation_cannot_advance():
    executor = _Executor(
        _success_result(status=ImprovementStatus.STOPPED, stopped_gate="focused-tests")
    )
    run = execute_orchestrator_run(_request(), executor, _invariants())

    assert run.state is OrchestratorState.STOPPED
    assert OrchestratorState.IMPLEMENTATION_COMPLETE not in [
        item.to_state for item in run.transitions
    ]


def test_unresolved_issue_is_rejected_by_independent_reviewer():
    executor = _Executor(_success_result(unresolved_issues=("needs manual investigation",)))
    run = execute_orchestrator_run(_request(), executor, _invariants())

    assert run.state is OrchestratorState.STOPPED
    assert OrchestratorState.IMPLEMENTATION_COMPLETE in [
        item.to_state for item in run.transitions
    ]
    assert OrchestratorState.REVIEW_COMPLETE not in [
        item.to_state for item in run.transitions
    ]


def test_missing_or_failed_invariant_evidence_stops():
    executor = _Executor(_success_result())
    missing = execute_orchestrator_run(_request(), executor, ())
    failed = execute_orchestrator_run(_request(run_id="run-002"), executor, _invariants(passed=False))

    assert missing.state is OrchestratorState.STOPPED
    assert failed.state is OrchestratorState.STOPPED
    assert "missing invariant evidence" in missing.terminal_reason
    assert "invariant failed" in failed.terminal_reason


def test_scope_broadening_through_invariant_evidence_stops():
    executor = _Executor(_success_result())
    evidence = (
        InvariantEvidence("collection remains unchanged", True),
        InvariantEvidence("new unauthorized invariant", True),
    )
    run = execute_orchestrator_run(_request(), executor, evidence)

    assert run.state is OrchestratorState.STOPPED
    assert "outside authorized review scope" in run.terminal_reason


def test_duplicate_validation_evidence_stops():
    executor = _Executor(
        _success_result(
            validation=(
                ValidationEvidence("focused-tests", True),
                ValidationEvidence("focused-tests", True),
                ValidationEvidence("pyright", True),
                ValidationEvidence("full-regression", True),
            )
        )
    )
    run = execute_orchestrator_run(_request(), executor, _invariants())

    assert run.state is OrchestratorState.STOPPED
    assert "duplicate validation evidence names" in run.terminal_reason
