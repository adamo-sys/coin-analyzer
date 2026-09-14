from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum

from orchestrator import OrchestratorRun, OrchestratorState


@dataclass(frozen=True)
class CommandCenterStatus:
    run_id: str
    state: str
    result: str
    blocker: str | None
    next_authorized_action: str
    human_authorization_required: bool


@dataclass(frozen=True)
class RepositoryStatus:
    branch: str
    head: str
    upstream: str | None
    clean: bool
    on_default_branch: bool
    state: str
    next_authorized_action: str


class CommandCenterAuthority(str, Enum):
    OBSERVATION_ONLY = "observation_only"


@dataclass(frozen=True)
class CommandCenterSnapshot:
    """Observed component state is never a grant of execution authority."""

    repository: RepositoryStatus
    run: CommandCenterStatus
    execution_authority: CommandCenterAuthority = field(
        default=CommandCenterAuthority.OBSERVATION_ONLY, init=False
    )

    @property
    def human_review_pending(self) -> bool:
        """A review request does not authorize execution or automatic resume."""
        return self.run.human_authorization_required


def project_command_center_snapshot(
    repository: RepositoryStatus, run: CommandCenterStatus
) -> CommandCenterSnapshot:
    """Combine supplied observations without collecting state or taking action."""
    return CommandCenterSnapshot(repository=repository, run=run)


def project_operator_status(snapshot: CommandCenterSnapshot) -> str:
    """Render supplied observations as state, result, and next authorized action.

    Precedence: repository STOPPED, run STOPPED, repository DIRTY, then run
    status (including NEEDS_AUTHORIZATION). The winning component supplies the
    action verbatim. Both states and pending review remain visible regardless
    of precedence. This is display selection, never a lifecycle transition or
    authorization to perform the displayed action.
    """
    repository, run = snapshot.repository, snapshot.run
    if repository.state == "STOPPED":
        state, action = repository.state, repository.next_authorized_action
    elif run.state == "STOPPED":
        state, action = run.state, run.next_authorized_action
    elif repository.state == "DIRTY":
        state, action = repository.state, repository.next_authorized_action
    else:
        state, action = run.state, run.next_authorized_action

    results = [run.result]
    if repository.state == "STOPPED":
        results.append(
            f"Repository STOPPED (branch={repository.branch!r}, "
            f"on_default_branch={repository.on_default_branch})."
        )
    elif repository.state == "DIRTY":
        results.append("Repository has tracked changes.")
    if run.blocker:
        results.append(f"Blocker: {run.blocker}")
    pending = "yes" if snapshot.human_review_pending else "no"
    return (
        f"STATE: {state} | repository={repository.state} | run={run.state} | "
        f"authority={snapshot.execution_authority.value} | "
        f"human_review_pending={pending}\n"
        f"RESULT: {' '.join(results)}\n"
        f"NEXT ACTION: {action}"
    )


def project_run_status(run: OrchestratorRun) -> CommandCenterStatus:
    if run.state is OrchestratorState.READY_FOR_HUMAN_REVIEW:
        return CommandCenterStatus(run.run_id, "NEEDS_AUTHORIZATION", "Machine-side pipeline complete; human review required.", None, "Human review; any governed follow-on action requires explicit authorization.", True)
    if run.state is OrchestratorState.STOPPED:
        return CommandCenterStatus(run.run_id, "STOPPED", "Orchestrator stopped.", run.terminal_reason or "Orchestrator stopped without a terminal reason.", "Human triage; no automatic resume.", False)
    return CommandCenterStatus(run.run_id, run.state.value.upper(), "Orchestrator run is not terminal.", None, "Observe the current bounded run; Command Center takes no action.", False)


def project_repository_status(branch, head, upstream, clean, default_branch='main'):
    on_default = branch == default_branch
    state = 'STOPPED' if on_default or not branch else ('DIRTY' if not clean else 'READY')
    action = 'Restore an authorized named non-default branch before further work.' if not branch else ('Move implementation work to an authorized non-default branch.' if on_default else ('Review tracked changes before further work.' if not clean else 'Repository state permits bounded work; authorization rules still apply.'))
    return RepositoryStatus(branch, head, upstream, clean, on_default, state, action)


def _git(*args):
    return subprocess.run(['git', *args], check=True, capture_output=True, text=True).stdout.strip()


def collect_repository_status(default_branch='main'):
    branch = _git('branch', '--show-current')
    head = _git('rev-parse', 'HEAD')
    tracked = _git('status', '--short', '--untracked-files=no')
    upstream = _git_optional('rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}')
    return project_repository_status(branch, head, upstream, not bool(tracked), default_branch)


def _git_optional(*args):
    try:
        return _git(*args)
    except subprocess.CalledProcessError:
        return None
