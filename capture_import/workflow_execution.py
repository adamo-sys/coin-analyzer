"""Sequential execution engine for the import workflow pipeline.

This module implements Sprint 7 Unit 4: deterministic, single-threaded
execution of a :class:`ProcessingPipeline` with cooperative cancellation
and pipeline lifecycle events.

Failure contract (frozen for Sprint 7):

- Stage returns an invalid ``StageResult`` (or a non-``StageResult``)
  → :class:`StageContractError`.
- Stage raises an ordinary exception
  → ``raise StageExecutionError(stage_id, exc) from exc``.
- Stage raises a workflow-typed exception (``ImportWorkflowError``
  subclass) → propagated unwrapped; ``WorkflowCancelledError`` additionally
  records ``PIPELINE_CANCELLED``.
- Cancellation requested by the caller → :class:`WorkflowCancelledError`
  raised unwrapped at cooperative boundaries.

Cancellation is checked before each stage, after each stage, and once
more after the final stage (the future pre-handoff boundary defined in
``docs/architecture/IMPORT_WORKFLOW.md``).  A terminal pipeline event is
emitted on every path: ``PIPELINE_COMPLETED``, ``PIPELINE_CANCELLED``, or
``STAGE_FAILED``.

Merge policy: artifact and metadata keys must be unique across stages.
A later stage re-emitting a key produced by an earlier stage is a wiring
error and fails fast with :class:`StageContractError`, consistent with
the duplicate ``stage_id`` construction policy and ADR-007 fail-fast.

Deliberately excluded (later units):

- Workspace creation, containment, and cleanup (Unit 5).  The caller
  supplies an absolute workspace path; this engine never creates or
  deletes it.
- ``PreparedImport`` assembly and transaction handoff (Unit 6).  This
  engine never invokes ``TransactionService``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from .events import ImportEventBus
from .workflow_models import (
    ImportRequest,
    JsonValue,
    StageArtifact,
    StageInput,
    StageResult,
)
from .workflow_pipeline import (
    ImportWorkflowError,
    ProcessingPipeline,
    ProcessingStage,
    StageContractError,
    StageExecutionError,
    WorkflowCancelledError,
)

_CANCELLED_BY_CALLER = "cancelled by caller"
_CANCELLED_BY_STAGE = "cancelled by stage"


@dataclass(frozen=True, slots=True)
class PipelineOutcome:
    """Accumulated result of one successful pipeline execution.

    ``artifacts`` is the union of every stage's produced artifacts;
    ``metadata`` is the union of every stage's metadata.  Both mappings
    are snapshots taken at completion.  Assembly of a ``PreparedImport``
    from an outcome plus workspace files is deferred to the transaction
    integration unit.
    """

    artifacts: Mapping[str, StageArtifact]
    metadata: Mapping[str, JsonValue]


class ImportWorkflow:
    """Run a ``ProcessingPipeline`` sequentially with cancellation and events.

    One workflow instance may execute its immutable pipeline any number of
    times; execution state is local to each ``execute`` call.  Threading
    is out of scope for Sprint 7 (ADR-007).
    """

    def __init__(
        self,
        pipeline: ProcessingPipeline,
        *,
        event_bus: ImportEventBus | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        if not isinstance(pipeline, ProcessingPipeline):
            raise TypeError(
                "pipeline must be a ProcessingPipeline, not "
                f"{type(pipeline).__name__}."
            )
        self._pipeline = pipeline
        self._event_bus = event_bus
        self._is_cancelled = is_cancelled

    # -- Public execution ---------------------------------------------------

    def execute(
        self,
        request: ImportRequest,
        workspace: Path,
        *,
        import_id: str | None = None,
    ) -> PipelineOutcome:
        """Run every stage exactly once in declared order.

        Args:
            request: Immutable import request (validated up front).
            workspace: Absolute path stages may write into.  Owned by the
                caller in Unit 4; no cleanup is performed here.
            import_id: Optional correlation id propagated to events.

        Returns:
            PipelineOutcome with merged artifacts and metadata.

        Raises:
            ValueError: If ``request`` or ``workspace`` is malformed.
            StageContractError: If a stage violates its result contract.
            StageExecutionError: If a stage raises an ordinary exception.
            WorkflowCancelledError: If cancellation is requested at a
                cooperative boundary.
        """
        request.validate()
        if not isinstance(workspace, Path) or not workspace.is_absolute():
            raise ValueError("workspace must be an absolute pathlib.Path.")

        stages = self._pipeline.stages
        stage_count = len(stages)
        if self._event_bus is not None:
            self._event_bus.record_pipeline_started(
                import_id=import_id,
                stage_ids=self._pipeline.stage_ids,
            )

        artifacts: dict[str, StageArtifact] = {}
        metadata: dict[str, JsonValue] = {}

        for index, stage in enumerate(stages):
            stage_id = stage.stage_id
            self._raise_if_cancelled(import_id, stage_id, index)
            self._record_stage_started(import_id, stage_id, index, stage_count)

            stage_input = StageInput(
                request=request,
                workspace=workspace,
                artifacts=dict(artifacts),
            )
            result = self._execute_stage(stage, stage_input, import_id, index)
            self._apply_result(result, stage_id, import_id, index, artifacts, metadata)

            self._record_stage_completed(import_id, stage_id, index)
            self._raise_if_cancelled(import_id, stage_id, index)

        # Final boundary: the future pre-handoff check before a
        # PreparedImport would be given to TransactionService (Unit 6).
        self._raise_if_cancelled(import_id, None, None)

        if self._event_bus is not None:
            self._event_bus.record_pipeline_completed(
                import_id=import_id,
                stage_count=stage_count,
            )
        return PipelineOutcome(artifacts=dict(artifacts), metadata=dict(metadata))

    # -- Stage execution and result contract ---------------------------------

    def _execute_stage(
        self,
        stage: ProcessingStage,
        stage_input: StageInput,
        import_id: str | None,
        index: int,
    ) -> StageResult:
        """Invoke one stage, mapping exceptions onto the failure contract."""
        stage_id = stage.stage_id
        try:
            return stage.execute(stage_input)
        except WorkflowCancelledError:
            # Cooperative cancellation signalled by the stage itself:
            # unwrapped, but still a terminal pipeline event.
            if self._event_bus is not None:
                self._event_bus.record_pipeline_cancelled(
                    import_id=import_id,
                    stage_id=stage_id,
                    stage_index=index,
                    reason=_CANCELLED_BY_STAGE,
                )
            raise
        except ImportWorkflowError as exc:
            # Already workflow-typed (e.g. StageContractError): never rewrap.
            self._record_stage_failed(import_id, stage_id, index, type(exc).__name__)
            raise
        except Exception as exc:
            self._record_stage_failed(import_id, stage_id, index, type(exc).__name__)
            raise StageExecutionError(stage_id, exc) from exc

    def _apply_result(
        self,
        result: StageResult,
        stage_id: str,
        import_id: str | None,
        index: int,
        artifacts: dict[str, StageArtifact],
        metadata: dict[str, JsonValue],
    ) -> None:
        """Validate a stage result and merge it into the accumulators.

        Raises:
            StageContractError: On non-``StageResult`` returns, model
                validation failures, or duplicate artifact/metadata keys.
        """
        if not isinstance(result, StageResult):
            self._record_stage_failed(import_id, stage_id, index, "StageContractError")
            raise StageContractError(
                stage_id,
                f"execute returned {type(result).__name__}, expected StageResult.",
            )
        try:
            self._pipeline.validate_stage_result(result, stage_id)
        except StageContractError as exc:
            self._record_stage_failed(import_id, stage_id, index, type(exc).__name__)
            raise  # Preserves the original ValueError chain.
        for key in result.artifacts:
            if key in artifacts:
                self._record_stage_failed(
                    import_id, stage_id, index, "StageContractError"
                )
                raise StageContractError(
                    stage_id,
                    f"duplicate artifact key {key!r}: already produced by an "
                    "earlier stage.",
                )
        for key in result.metadata:
            if key in metadata:
                self._record_stage_failed(
                    import_id, stage_id, index, "StageContractError"
                )
                raise StageContractError(
                    stage_id,
                    f"duplicate metadata key {key!r}: already produced by an "
                    "earlier stage.",
                )
        artifacts.update(result.artifacts)
        metadata.update(result.metadata)

    # -- Cancellation ---------------------------------------------------------

    def _raise_if_cancelled(
        self,
        import_id: str | None,
        stage_id: str | None,
        stage_index: int | None,
    ) -> None:
        """Raise WorkflowCancelledError (unwrapped) at a safe boundary.

        Cancellation is cooperative and checked only at stage boundaries
        in this layer.  Once a future transaction handoff occurs, Sprint 6
        semantics remain authoritative for the durable commit boundary.
        """
        if self._is_cancelled is not None and self._is_cancelled():
            if self._event_bus is not None:
                self._event_bus.record_pipeline_cancelled(
                    import_id=import_id,
                    stage_id=stage_id,
                    stage_index=stage_index,
                    reason=_CANCELLED_BY_CALLER,
                )
            raise WorkflowCancelledError("workflow cancelled by caller")

    # -- Event helpers ---------------------------------------------------------

    def _record_stage_started(
        self,
        import_id: str | None,
        stage_id: str,
        index: int,
        stage_count: int,
    ) -> None:
        if self._event_bus is not None:
            self._event_bus.record_stage_started(
                import_id=import_id,
                stage_id=stage_id,
                stage_index=index,
                stage_count=stage_count,
            )

    def _record_stage_completed(
        self,
        import_id: str | None,
        stage_id: str,
        index: int,
    ) -> None:
        if self._event_bus is not None:
            self._event_bus.record_stage_completed(
                import_id=import_id,
                stage_id=stage_id,
                stage_index=index,
            )

    def _record_stage_failed(
        self,
        import_id: str | None,
        stage_id: str,
        index: int,
        error_type: str,
    ) -> None:
        if self._event_bus is not None:
            self._event_bus.record_stage_failed(
                import_id=import_id,
                stage_id=stage_id,
                stage_index=index,
                error_type=error_type,
            )
