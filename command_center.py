from __future__ import annotations

from dataclasses import dataclass

from orchestrator import OrchestratorRun, OrchestratorState


@dataclass(frozen=True)
class CommandCenterStatus:
    run_id: str
    state: str
    result: str
    blocker: str | None
    next_authorized_action: str
    human_authorization_required: bool


def project_run_status(run: OrchestratorRun) -> CommandCenterStatus:
    if run.state is OrchestratorState.READY_FOR_HUMAN_REVIEW:
        return CommandCenterStatus(run.run_id, "NEEDS_AUTHORIZATION", "Machine-side pipeline complete; human review required.", None, "Human review; any governed follow-on action requires explicit authorization.", True)
    if run.state is OrchestratorState.STOPPED:
        return CommandCenterStatus(run.run_id, "STOPPED", "Orchestrator stopped.", run.terminal_reason or "Orchestrator stopped without a terminal reason.", "Human triage; no automatic resume.", False)
    return CommandCenterStatus(run.run_id, run.state.value.upper(), "Orchestrator run is not terminal.", None, "Observe the current bounded run; Command Center takes no action.", False)
