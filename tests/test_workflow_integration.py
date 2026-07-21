"""Focused tests for Sprint 7 Unit 6: transaction integration.

Proves the workflow's single durable handoff: exactly one delegate
invocation per execute call, PreparedImport as the only boundary object,
unwrapped delegate exceptions, cancellation/assembly boundaries, event
ordering (pipeline family before transaction family), and workspace
cleanup on every exit path.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from capture_import.errors import RecoveryRequired, RollbackFailed
from capture_import.events import EventType, ImportEventBus
from capture_import.workflow_execution import (
    ImportWorkflow,
    PipelineOutcome,
    assemble_prepared_import,
)
from capture_import.workflow_models import (
    ImportConfiguration,
    ImportRequest,
    PreparedImport,
    StageArtifact,
    StageInput,
    StageResult,
)
from capture_import.workflow_pipeline import (
    ProcessingPipeline,
    StageContractError,
    StageExecutionError,
    WorkflowCancelledError,
)
from capture_import.workflow_workspace import WorkflowWorkspace


def make_request(collection_id: str = "collection-1") -> ImportRequest:
    return ImportRequest(
        source=Path(tempfile.gettempdir()),
        collection_id=collection_id,
        configuration=ImportConfiguration(),
    )


class ArtifactWritingStage:
    """Writes real bytes into the workspace and declares the artifact.

    ``write=False`` declares the artifact without creating the file, for
    assembly failure tests.
    """

    def __init__(
        self,
        stage_id: str,
        key: str | None = None,
        content: bytes = b"",
        metadata: dict | None = None,
        write: bool = True,
    ) -> None:
        self._stage_id = stage_id
        self._key = key
        self._content = content
        self._metadata = dict(metadata) if metadata else {}
        self._write = write

    @property
    def stage_id(self) -> str:
        return self._stage_id

    def execute(self, stage_input: StageInput) -> StageResult:
        artifacts = {}
        if self._key is not None:
            relative = f"{self._key}.bin"
            if self._write:
                (stage_input.workspace / relative).write_bytes(self._content)
            artifacts[self._key] = StageArtifact(relative_path=relative)
        return StageResult(artifacts=artifacts, metadata=self._metadata)


class RaisingStage:
    """Raises the given exception from execute."""

    def __init__(self, stage_id: str, exc: Exception) -> None:
        self._stage_id = stage_id
        self._exc = exc

    @property
    def stage_id(self) -> str:
        return self._stage_id

    def execute(self, stage_input: StageInput) -> StageResult:
        raise self._exc


class TransactionSpy:
    """Stands in for the durable handoff delegate.

    Records every invocation.  Optionally simulates the transaction
    layer's own event family on a shared bus and/or raises an error
    after IMPORT_STARTED (the real TransactionService failure shape).
    """

    def __init__(
        self,
        *,
        error: BaseException | None = None,
        bus: ImportEventBus | None = None,
        import_id: str = "import-1",
        result: object = None,
    ) -> None:
        self.calls: list[PreparedImport] = []
        self._error = error
        self._bus = bus
        self._import_id = import_id
        self.result = result if result is not None else object()

    def __call__(self, prepared: PreparedImport) -> object:
        self.calls.append(prepared)
        if self._bus is not None:
            self._bus.record_started(
                import_id=self._import_id,
                package_basename="package.zip",
                proposed_count=len(prepared.files),
            )
        if self._error is not None:
            raise self._error
        if self._bus is not None:
            self._bus.record_complete(
                import_id=self._import_id,
                status="COMMITTED",
                imported_count=len(prepared.files),
                skipped_count=0,
                image_count=0,
            )
        return self.result


class CancelAfter:
    """Cancellation probe: returns False until the ``n``-th call fires True."""

    def __init__(self, n: int) -> None:
        self._n = n
        self.calls = 0

    def __call__(self) -> bool:
        self.calls += 1
        return self.calls >= self._n


class WorkspaceTestCase(unittest.TestCase):
    """Provides a real temporary directory as the execution workspace."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workspace = Path(self._tmp.name)


class HandoffSemanticsTests(WorkspaceTestCase):
    """The delegate is invoked exactly once and owns its own failure modes."""

    def test_successful_handoff_invokes_delegate_exactly_once(self) -> None:
        spy = TransactionSpy()
        pipeline = ProcessingPipeline(
            stages=(
                ArtifactWritingStage("stage-a", "alpha", b"12345"),
                ArtifactWritingStage("stage-b", "beta", b"hello world!"),
            )
        )
        result = ImportWorkflow(pipeline).execute(
            make_request(), self.workspace, transaction=spy
        )
        self.assertEqual(len(spy.calls), 1)
        self.assertIs(result, spy.result)

    def test_delegate_receives_validated_prepared_import(self) -> None:
        request = make_request()
        spy = TransactionSpy()
        pipeline = ProcessingPipeline(
            stages=(ArtifactWritingStage("stage-a", "alpha", b"12345"),)
        )
        ImportWorkflow(pipeline).execute(request, self.workspace, transaction=spy)
        prepared = spy.calls[0]
        self.assertIsInstance(prepared, PreparedImport)
        prepared.validate()  # Must not raise: the boundary object is valid.
        self.assertIs(prepared.request, request)

    def test_delegate_value_error_propagates_unwrapped(self) -> None:
        error = ValueError("transaction rejected")
        spy = TransactionSpy(error=error)
        pipeline = ProcessingPipeline(stages=(ArtifactWritingStage("stage-a"),))
        with self.assertRaises(ValueError) as ctx:
            ImportWorkflow(pipeline).execute(
                make_request(), self.workspace, transaction=spy
            )
        self.assertIs(ctx.exception, error)
        # Exactly-once holds even when the delegate fails.
        self.assertEqual(len(spy.calls), 1)

    def test_delegate_recovery_required_propagates_unwrapped(self) -> None:
        error = RecoveryRequired("journal left mid-transaction")
        spy = TransactionSpy(error=error)
        pipeline = ProcessingPipeline(stages=(ArtifactWritingStage("stage-a"),))
        with self.assertRaises(RecoveryRequired) as ctx:
            ImportWorkflow(pipeline).execute(
                make_request(), self.workspace, transaction=spy
            )
        self.assertIs(ctx.exception, error)
        self.assertEqual(len(spy.calls), 1)

    def test_delegate_rollback_failed_propagates_unwrapped(self) -> None:
        error = RollbackFailed("snapshot restore incomplete")
        spy = TransactionSpy(error=error)
        pipeline = ProcessingPipeline(stages=(ArtifactWritingStage("stage-a"),))
        with self.assertRaises(RollbackFailed) as ctx:
            ImportWorkflow(pipeline).execute(
                make_request(), self.workspace, transaction=spy
            )
        self.assertIs(ctx.exception, error)
        self.assertEqual(len(spy.calls), 1)

    def test_non_callable_transaction_rejected_before_any_event(self) -> None:
        bus = ImportEventBus()
        pipeline = ProcessingPipeline(stages=(ArtifactWritingStage("stage-a"),))
        with self.assertRaises(TypeError):
            ImportWorkflow(pipeline, event_bus=bus).execute(
                make_request(), self.workspace, transaction=object()
            )
        self.assertEqual(len(bus), 0)

    def test_transaction_none_returns_pipeline_outcome(self) -> None:
        pipeline = ProcessingPipeline(
            stages=(ArtifactWritingStage("stage-a", "alpha", b"12345"),)
        )
        outcome = ImportWorkflow(pipeline).execute(make_request(), self.workspace)
        self.assertIsInstance(outcome, PipelineOutcome)
        self.assertEqual(
            outcome.artifacts["alpha"], StageArtifact(relative_path="alpha.bin")
        )

    def test_repeated_execute_on_one_instance_hands_off_once_per_run(self) -> None:
        spy = TransactionSpy()
        pipeline = ProcessingPipeline(
            stages=(ArtifactWritingStage("stage-a", "alpha", b"12345"),)
        )
        workflow = ImportWorkflow(pipeline)
        first = workflow.execute(make_request("run-1"), self.workspace, transaction=spy)
        second = workflow.execute(make_request("run-2"), self.workspace, transaction=spy)
        # Exactly one handoff per run; no cross-run state accumulates.
        self.assertEqual(len(spy.calls), 2)
        self.assertIs(first, spy.result)
        self.assertIs(second, spy.result)
        self.assertIsNot(spy.calls[0], spy.calls[1])
        for prepared in spy.calls:
            self.assertEqual(
                [(f.relative_path, f.expected_size) for f in prepared.files],
                [("alpha.bin", 5)],
            )
        self.assertEqual(spy.calls[0].request.collection_id, "run-1")
        self.assertEqual(spy.calls[1].request.collection_id, "run-2")


class PreparedImportAssemblyTests(WorkspaceTestCase):
    """Assembly verifies workspace files and builds the boundary object."""

    def test_files_carry_verified_sizes_in_execution_order(self) -> None:
        spy = TransactionSpy()
        pipeline = ProcessingPipeline(
            stages=(
                ArtifactWritingStage("stage-b", "beta", b"hello world!"),
                ArtifactWritingStage("stage-a", "alpha", b"12345"),
            )
        )
        ImportWorkflow(pipeline).execute(make_request(), self.workspace, transaction=spy)
        prepared = spy.calls[0]
        self.assertEqual(
            [(f.relative_path, f.expected_size) for f in prepared.files],
            [("beta.bin", 12), ("alpha.bin", 5)],
        )

    def test_sha256_left_none_for_the_snapshot_path(self) -> None:
        spy = TransactionSpy()
        pipeline = ProcessingPipeline(
            stages=(ArtifactWritingStage("stage-a", "alpha", b"12345"),)
        )
        ImportWorkflow(pipeline).execute(make_request(), self.workspace, transaction=spy)
        self.assertTrue(all(f.sha256 is None for f in spy.calls[0].files))

    def test_metadata_merged_into_prepared_import(self) -> None:
        spy = TransactionSpy()
        pipeline = ProcessingPipeline(
            stages=(
                ArtifactWritingStage("stage-a", metadata={"count": 2}),
                ArtifactWritingStage("stage-b", metadata={"tags": ["x", "y"]}),
            )
        )
        ImportWorkflow(pipeline).execute(make_request(), self.workspace, transaction=spy)
        self.assertEqual(
            dict(spy.calls[0].metadata), {"count": 2, "tags": ["x", "y"]}
        )

    def test_empty_artifact_pipeline_hands_off_empty_files(self) -> None:
        spy = TransactionSpy()
        pipeline = ProcessingPipeline(stages=(ArtifactWritingStage("stage-a"),))
        ImportWorkflow(pipeline).execute(make_request(), self.workspace, transaction=spy)
        self.assertEqual(len(spy.calls), 1)
        self.assertEqual(spy.calls[0].files, ())

    def test_missing_artifact_fails_closed_at_assembly(self) -> None:
        bus = ImportEventBus()
        spy = TransactionSpy()
        pipeline = ProcessingPipeline(
            stages=(ArtifactWritingStage("stage-a", "ghost", b"x", write=False),)
        )
        with self.assertRaises(StageContractError) as ctx:
            ImportWorkflow(pipeline, event_bus=bus).execute(
                make_request(), self.workspace, transaction=spy
            )
        self.assertEqual(ctx.exception.stage_id, "stage-a")
        self.assertIsInstance(ctx.exception.__cause__, OSError)
        self.assertEqual(spy.calls, [])
        # The stage itself completed; assembly failed afterwards, so no
        # pipeline-terminal event is emitted at all.
        self.assertEqual(len(bus.by_type(EventType.STAGE_COMPLETED)), 1)
        self.assertEqual(bus.by_type(EventType.STAGE_FAILED), ())
        self.assertEqual(bus.by_type(EventType.PIPELINE_COMPLETED), ())
        self.assertEqual(bus.by_type(EventType.PIPELINE_CANCELLED), ())
        # Deliberate contract pin (IMPORT_WORKFLOW.md, "Prepared-import
        # assembly failure"): the exact bus contents are PIPELINE_STARTED
        # plus the stage lifecycle — no terminal pipeline event and no
        # transaction-family event whatsoever.
        self.assertEqual(
            [event.event_type for event in bus.events],
            [
                EventType.PIPELINE_STARTED,
                EventType.STAGE_STARTED,
                EventType.STAGE_COMPLETED,
            ],
        )

    def test_artifact_pointing_at_directory_fails_closed(self) -> None:
        (self.workspace / "tree.bin").mkdir()
        spy = TransactionSpy()
        pipeline = ProcessingPipeline(
            stages=(ArtifactWritingStage("stage-a", "tree", write=False),)
        )
        with self.assertRaises(StageContractError) as ctx:
            ImportWorkflow(pipeline).execute(
                make_request(), self.workspace, transaction=spy
            )
        self.assertEqual(ctx.exception.stage_id, "stage-a")
        self.assertIsInstance(ctx.exception.__cause__, OSError)
        self.assertEqual(spy.calls, [])

    @unittest.skipUnless(hasattr(os, "symlink"), "platform lacks symlink support")
    def test_artifact_symlink_escape_fails_closed(self) -> None:
        external = Path(self._tmp.name) / "external.bin"
        external.write_bytes(b"secret")
        link = self.workspace / "linked.bin"
        try:
            os.symlink(external, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        spy = TransactionSpy()
        pipeline = ProcessingPipeline(
            stages=(ArtifactWritingStage("stage-a", "linked", write=False),)
        )
        with self.assertRaises(StageContractError):
            ImportWorkflow(pipeline).execute(
                make_request(), self.workspace, transaction=spy
            )
        self.assertEqual(spy.calls, [])
        self.assertEqual(external.read_bytes(), b"secret")

    def test_assembly_attributes_unknown_stage_when_mapping_incomplete(self) -> None:
        outcome = PipelineOutcome(
            artifacts={"key": StageArtifact(relative_path="nope.bin")}, metadata={}
        )
        with self.assertRaises(StageContractError) as ctx:
            assemble_prepared_import(make_request(), outcome, self.workspace, {})
        self.assertEqual(ctx.exception.stage_id, "<unknown>")


class CancellationBoundaryTests(WorkspaceTestCase):
    """Cancellation before the handoff commits nothing, ever."""

    def test_cancellation_at_pre_stage_boundary_commits_nothing(self) -> None:
        bus = ImportEventBus()
        spy = TransactionSpy()
        # With one stage + transaction: pre-stage is the 1st check.
        cancel = CancelAfter(1)
        pipeline = ProcessingPipeline(
            stages=(ArtifactWritingStage("stage-a", "alpha", b"12345"),)
        )
        with self.assertRaises(WorkflowCancelledError):
            ImportWorkflow(pipeline, event_bus=bus, is_cancelled=cancel).execute(
                make_request(), self.workspace, transaction=spy
            )
        self.assertEqual(spy.calls, [])
        self.assertEqual(bus.by_type(EventType.STAGE_STARTED), ())
        self.assertEqual(len(bus.by_type(EventType.PIPELINE_CANCELLED)), 1)
        self.assertEqual(bus.by_type(EventType.PIPELINE_COMPLETED), ())

    def test_cancellation_at_post_stage_boundary_commits_nothing(self) -> None:
        bus = ImportEventBus()
        spy = TransactionSpy()
        # With one stage + transaction: post-stage is the 2nd check.
        cancel = CancelAfter(2)
        pipeline = ProcessingPipeline(
            stages=(ArtifactWritingStage("stage-a", "alpha", b"12345"),)
        )
        with self.assertRaises(WorkflowCancelledError):
            ImportWorkflow(pipeline, event_bus=bus, is_cancelled=cancel).execute(
                make_request(), self.workspace, transaction=spy
            )
        self.assertEqual(spy.calls, [])
        self.assertEqual(len(bus.by_type(EventType.STAGE_COMPLETED)), 1)
        self.assertEqual(len(bus.by_type(EventType.PIPELINE_CANCELLED)), 1)
        self.assertEqual(bus.by_type(EventType.PIPELINE_COMPLETED), ())

    def test_cancellation_at_pre_assembly_boundary_commits_nothing(self) -> None:
        bus = ImportEventBus()
        spy = TransactionSpy()
        # With one stage: pre-stage(1), post-stage(2), pre-assembly(3).
        cancel = CancelAfter(3)
        pipeline = ProcessingPipeline(
            stages=(ArtifactWritingStage("stage-a", "alpha", b"12345"),)
        )
        with self.assertRaises(WorkflowCancelledError):
            ImportWorkflow(pipeline, event_bus=bus, is_cancelled=cancel).execute(
                make_request(), self.workspace, transaction=spy
            )
        self.assertEqual(spy.calls, [])
        self.assertEqual(len(bus.by_type(EventType.PIPELINE_CANCELLED)), 1)
        self.assertEqual(bus.by_type(EventType.PIPELINE_COMPLETED), ())

    def test_cancellation_at_pre_handoff_boundary_commits_nothing(self) -> None:
        bus = ImportEventBus()
        spy = TransactionSpy()
        # With one stage + transaction: pre-handoff is the 4th check.
        cancel = CancelAfter(4)
        pipeline = ProcessingPipeline(
            stages=(ArtifactWritingStage("stage-a", "alpha", b"12345"),)
        )
        with self.assertRaises(WorkflowCancelledError):
            ImportWorkflow(pipeline, event_bus=bus, is_cancelled=cancel).execute(
                make_request(), self.workspace, transaction=spy
            )
        self.assertEqual(spy.calls, [])
        self.assertEqual(len(bus.by_type(EventType.PIPELINE_CANCELLED)), 1)
        self.assertEqual(bus.by_type(EventType.PIPELINE_COMPLETED), ())

    def test_failed_stage_commits_zero_times(self) -> None:
        bus = ImportEventBus()
        spy = TransactionSpy()
        pipeline = ProcessingPipeline(
            stages=(RaisingStage("stage-a", ValueError("boom")),)
        )
        with self.assertRaises(StageExecutionError):
            ImportWorkflow(pipeline, event_bus=bus).execute(
                make_request(), self.workspace, transaction=spy
            )
        self.assertEqual(spy.calls, [])
        self.assertEqual(len(bus.by_type(EventType.STAGE_FAILED)), 1)
        self.assertEqual(bus.by_type(EventType.PIPELINE_COMPLETED), ())
        self.assertEqual(bus.by_type(EventType.PIPELINE_CANCELLED), ())

    def test_stage_raised_cancellation_commits_zero_times(self) -> None:
        bus = ImportEventBus()
        spy = TransactionSpy()
        pipeline = ProcessingPipeline(
            stages=(RaisingStage("stage-a", WorkflowCancelledError("stop")),)
        )
        with self.assertRaises(WorkflowCancelledError) as ctx:
            ImportWorkflow(pipeline, event_bus=bus).execute(
                make_request(), self.workspace, transaction=spy
            )
        self.assertIsNone(ctx.exception.__cause__)
        self.assertEqual(spy.calls, [])
        self.assertEqual(len(bus.by_type(EventType.PIPELINE_CANCELLED)), 1)
        self.assertEqual(bus.by_type(EventType.PIPELINE_COMPLETED), ())

    def test_stage_raised_contract_error_commits_zero_times(self) -> None:
        bus = ImportEventBus()
        spy = TransactionSpy()
        error = StageContractError("stage-a", "self-reported violation")
        pipeline = ProcessingPipeline(stages=(RaisingStage("stage-a", error),))
        with self.assertRaises(StageContractError) as ctx:
            ImportWorkflow(pipeline, event_bus=bus).execute(
                make_request(), self.workspace, transaction=spy
            )
        # Workflow-typed: propagated unwrapped, never rewrapped.
        self.assertIs(ctx.exception, error)
        self.assertEqual(spy.calls, [])
        self.assertEqual(len(bus.by_type(EventType.STAGE_FAILED)), 1)
        self.assertEqual(bus.by_type(EventType.PIPELINE_COMPLETED), ())
        self.assertEqual(bus.by_type(EventType.PIPELINE_CANCELLED), ())


class EventOrderingTests(WorkspaceTestCase):
    """The integrated stream is pipeline-family first, transaction second."""

    def test_integrated_stream_orders_pipeline_family_first(self) -> None:
        bus = ImportEventBus()
        spy = TransactionSpy(bus=bus)
        pipeline = ProcessingPipeline(
            stages=(ArtifactWritingStage("stage-a", "alpha", b"12345"),)
        )
        ImportWorkflow(pipeline, event_bus=bus).execute(
            make_request(), self.workspace, transaction=spy
        )
        self.assertEqual(
            [event.event_type for event in bus.events],
            [
                EventType.PIPELINE_STARTED,
                EventType.STAGE_STARTED,
                EventType.STAGE_COMPLETED,
                EventType.PIPELINE_COMPLETED,
                EventType.IMPORT_STARTED,
                EventType.IMPORT_COMPLETE,
            ],
        )
        self.assertEqual(len(bus.by_type(EventType.PIPELINE_COMPLETED)), 1)
        self.assertEqual(len(bus.by_type(EventType.IMPORT_STARTED)), 1)

    def test_delegate_failure_stream_ends_at_import_started(self) -> None:
        bus = ImportEventBus()
        spy = TransactionSpy(bus=bus, error=ValueError("commit failed"))
        pipeline = ProcessingPipeline(
            stages=(ArtifactWritingStage("stage-a", "alpha", b"12345"),)
        )
        with self.assertRaises(ValueError):
            ImportWorkflow(pipeline, event_bus=bus).execute(
                make_request(), self.workspace, transaction=spy
            )
        self.assertEqual(
            [event.event_type for event in bus.events],
            [
                EventType.PIPELINE_STARTED,
                EventType.STAGE_STARTED,
                EventType.STAGE_COMPLETED,
                EventType.PIPELINE_COMPLETED,
                EventType.IMPORT_STARTED,
            ],
        )
        self.assertEqual(bus.by_type(EventType.IMPORT_COMPLETE), ())


class WorkspaceCleanupIntegrationTests(unittest.TestCase):
    """Unit 5 cleanup guarantees hold across every Unit 6 exit path."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _run(self, workspace_path: Path, spy: TransactionSpy, **kwargs) -> None:
        pipeline = ProcessingPipeline(
            stages=(ArtifactWritingStage("stage-a", "alpha", b"data"),)
        )
        ImportWorkflow(pipeline, **kwargs).execute(
            make_request(), workspace_path, transaction=spy
        )

    def test_workspace_cleaned_after_successful_handoff(self) -> None:
        spy = TransactionSpy()
        with WorkflowWorkspace(self.root) as workspace:
            self._run(workspace.path, spy)
        self.assertTrue(workspace.is_closed)
        self.assertFalse(workspace.path.exists())
        self.assertEqual(len(spy.calls), 1)

    def test_workspace_cleaned_after_delegate_failure(self) -> None:
        spy = TransactionSpy(error=ValueError("commit failed"))
        with self.assertRaises(ValueError):
            with WorkflowWorkspace(self.root) as workspace:
                self._run(workspace.path, spy)
        self.assertFalse(workspace.path.exists())
        self.assertEqual(len(spy.calls), 1)

    def test_workspace_cleaned_after_cancellation(self) -> None:
        spy = TransactionSpy()
        # Pre-handoff boundary: the 4th cancellation check with one stage.
        cancel = CancelAfter(4)
        with self.assertRaises(WorkflowCancelledError):
            with WorkflowWorkspace(self.root) as workspace:
                self._run(workspace.path, spy, is_cancelled=cancel)
        self.assertFalse(workspace.path.exists())
        self.assertEqual(spy.calls, [])


if __name__ == "__main__":
    unittest.main()
