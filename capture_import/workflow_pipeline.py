"""Deterministic processing pipeline for import workflow stages.

This module defines the internal stage protocol and pipeline construction
rules.  It deliberately contains no execution, workspace, transaction, or
event logic — those belong in later implementation units.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .workflow_models import StageInput, StageResult


class ImportWorkflowError(Exception):
    """Base for all import workflow processing failures."""


class PipelineConfigurationError(ImportWorkflowError):
    """Pipeline was constructed with invalid stage configuration."""


class StageContractError(ImportWorkflowError):
    """A stage violated its input/output contract."""

    def __init__(self, stage_id: str, message: str) -> None:
        self.stage_id = stage_id
        super().__init__(f"Stage '{stage_id}' contract error: {message}")


class StageExecutionError(ImportWorkflowError):
    """A stage raised an exception during execution."""

    def __init__(self, stage_id: str, cause: Exception) -> None:
        self.stage_id = stage_id
        self.cause = cause
        super().__init__(f"Stage '{stage_id}' failed: {cause}")


class WorkflowCancelledError(ImportWorkflowError):
    """The workflow was cancelled at a safe boundary."""


@runtime_checkable
class ProcessingStage(Protocol):
    """Internal processing component — not a public plugin API.

    Implementations must provide a stable ``stage_id`` and an ``execute``
    method that returns a validated ``StageResult``.
    """

    @property
    def stage_id(self) -> str:
        """Unique stable identifier within one pipeline."""
        ...

    def execute(self, stage_input: StageInput) -> StageResult:
        """Transform stage input to stage output without mutating shared state."""
        ...


@dataclass(frozen=True, slots=True)
class ProcessingPipeline:
    """Immutable, explicitly ordered collection of processing stages.

    Construction validates:
    - stages is an immutable tuple;
    - every stage has a non-empty string ``stage_id``;
    - every stage has a callable ``execute`` method;
    - ``stage_id`` values are unique;
    - empty tuple is accepted (identity pipeline).
    """

    stages: tuple[ProcessingStage, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.stages, tuple):
            raise PipelineConfigurationError(
                "stages must be an immutable tuple, not "
                f"{type(self.stages).__name__}."
            )
        seen: set[str] = set()
        for stage in self.stages:
            if not hasattr(stage, "stage_id"):
                raise PipelineConfigurationError(
                    f"Stage {type(stage).__name__} missing required "
                    f"'stage_id' attribute."
                )
            stage_id = stage.stage_id
            if not isinstance(stage_id, str) or not stage_id:
                raise PipelineConfigurationError(
                    f"Stage {type(stage).__name__} has invalid stage_id: "
                    f"{stage_id!r}."
                )
            if stage_id in seen:
                raise PipelineConfigurationError(
                    f"Duplicate stage_id: {stage_id!r}."
                )
            if not hasattr(stage, "execute") or not callable(stage.execute):
                raise PipelineConfigurationError(
                    f"Stage {type(stage).__name__} missing required "
                    f"'execute' method."
                )
            seen.add(stage_id)

    @property
    def stage_ids(self) -> tuple[str, ...]:
        """Ordered stage identifiers."""
        return tuple(stage.stage_id for stage in self.stages)

    def validate_stage_result(
        self, result: StageResult, stage_id: str
    ) -> None:
        """Validate a ``StageResult`` and attribute failure to ``stage_id``.

        Raises:
            StageContractError: If the result fails model validation.
        """
        try:
            result.validate()
        except ValueError as exc:
            raise StageContractError(
                stage_id, f"invalid StageResult: {exc}"
            ) from exc
