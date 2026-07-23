"""Focused tests for Sprint 7 Unit 4: pipeline execution and cancellation."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from capture_import.events import EventType, ImportEventBus
from capture_import.workflow_execution import (
    ImportWorkflow,
    PipelineOutcome,
    assemble_prepared_import,
)
from capture_import.workflow_models import (
    ImportConfiguration,
    ImportRequest,
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

WORKSPACE = Path(tempfile.gettempdir())


def make_baseline_jpeg(size: tuple[int, int] = (8, 6)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, (50, 100, 150)).save(
        output, format="JPEG", progressive=False, exif=b""
    )
    return output.getvalue()


def make_request(collection_id: str = "collection-1") -> ImportRequest:
    return ImportRequest(
        source=Path(tempfile.gettempdir()),
        collection_id=collection_id,
        configuration=ImportConfiguration(),
    )


class RecordingStage:
    """Executes successfully, records invocation, returns fixed output."""

    def __init__(
        self,
        stage_id: str,
        *,
        artifact_key: str | None = None,
        metadata: dict | None = None,
        calls: list | None = None,
    ) -> None:
        self._stage_id = stage_id
        self._artifact_key = artifact_key
        self._metadata = dict(metadata) if metadata else {}
        self._calls = calls

    @property
    def stage_id(self) -> str:
        return self._stage_id

    def execute(self, stage_input: StageInput) -> StageResult:
        if self._calls is not None:
            self._calls.append(self._stage_id)
        artifacts = {}
        if self._artifact_key is not None:
            artifacts[self._artifact_key] = StageArtifact(
                relative_path=f"{self._artifact_key}.bin"
            )
        return StageResult(artifacts=artifacts, metadata=self._metadata)


class SpyStage:
    """Records the StageInput it receives for later assertions."""

    def __init__(self, stage_id: str, seen: list) -> None:
        self._stage_id = stage_id
        self._seen = seen

    @property
    def stage_id(self) -> str:
        return self._stage_id

    def execute(self, stage_input: StageInput) -> StageResult:
        self._seen.append(stage_input)
        return StageResult(artifacts={}, metadata={})


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


class BadReturnStage:
    """Returns an object that is not a StageResult."""

    def __init__(self, stage_id: str, value: object) -> None:
        self._stage_id = stage_id
        self._value = value

    @property
    def stage_id(self) -> str:
        return self._stage_id

    def execute(self, stage_input: StageInput):
        return self._value


class FlipCancellationStage:
    """Flips a cancellation flag during execution, then returns valid output."""

    def __init__(self, stage_id: str, flag: dict) -> None:
        self._stage_id = stage_id
        self._flag = flag

    @property
    def stage_id(self) -> str:
        return self._stage_id

    def execute(self, stage_input: StageInput) -> StageResult:
        self._flag["cancelled"] = True
        return StageResult(artifacts={}, metadata={})


class MutatingStage:
    """Attempts to mutate the input artifacts mapping (invisible-mutation probe)."""

    def __init__(self, stage_id: str) -> None:
        self._stage_id = stage_id

    @property
    def stage_id(self) -> str:
        return self._stage_id

    def execute(self, stage_input: StageInput) -> StageResult:
        stage_input.artifacts["injected"] = StageArtifact(relative_path="evil.bin")
        return StageResult(artifacts={}, metadata={})


class SequentialExecutionTests(unittest.TestCase):
    def test_stages_execute_exactly_once_in_declared_order(self) -> None:
        calls: list = []
        pipeline = ProcessingPipeline(
            stages=(
                RecordingStage("a", calls=calls),
                RecordingStage("b", calls=calls),
                RecordingStage("c", calls=calls),
            )
        )
        outcome = ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)
        self.assertEqual(calls, ["a", "b", "c"])
        self.assertIsInstance(outcome, PipelineOutcome)

    def test_artifacts_thread_forward_to_later_stages(self) -> None:
        seen: list = []
        pipeline = ProcessingPipeline(
            stages=(
                RecordingStage("a", artifact_key="art_a"),
                RecordingStage("b", artifact_key="art_b"),
                SpyStage("spy", seen),
            )
        )
        ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)
        self.assertEqual(len(seen), 1)
        forwarded = seen[0].artifacts
        self.assertEqual(set(forwarded), {"art_a", "art_b"})
        self.assertEqual(forwarded["art_a"].relative_path, "art_a.bin")

    def test_first_stage_receives_empty_artifacts(self) -> None:
        seen: list = []
        pipeline = ProcessingPipeline(
            stages=(SpyStage("spy", seen), RecordingStage("a", artifact_key="x"))
        )
        ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)
        self.assertEqual(seen[0].artifacts, {})

    def test_stage_receives_same_request_and_workspace(self) -> None:
        seen: list = []
        request = make_request()
        pipeline = ProcessingPipeline(stages=(SpyStage("spy", seen),))
        ImportWorkflow(pipeline).execute(request, WORKSPACE)
        self.assertIs(seen[0].request, request)
        self.assertEqual(seen[0].workspace, WORKSPACE)

    def test_stage_input_artifacts_are_snapshot_copies(self) -> None:
        seen: list = []
        pipeline = ProcessingPipeline(
            stages=(
                RecordingStage("a", artifact_key="legit"),
                MutatingStage("mutator"),
                SpyStage("spy", seen),
            )
        )
        outcome = ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)
        # The mutating stage's write into its own input copy is invisible:
        # it reaches neither the accumulator nor the following stage.
        self.assertEqual(set(seen[0].artifacts), {"legit"})
        self.assertEqual(set(outcome.artifacts), {"legit"})

    def test_outcome_merges_artifacts_and_metadata(self) -> None:
        pipeline = ProcessingPipeline(
            stages=(
                RecordingStage("a", artifact_key="art_a", metadata={"m_a": 1}),
                RecordingStage("b", artifact_key="art_b", metadata={"m_b": "two"}),
            )
        )
        outcome = ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)
        self.assertEqual(set(outcome.artifacts), {"art_a", "art_b"})
        self.assertEqual(outcome.metadata, {"m_a": 1, "m_b": "two"})

    def test_empty_pipeline_is_identity(self) -> None:
        pipeline = ProcessingPipeline(stages=())
        outcome = ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)
        self.assertEqual(outcome.artifacts, {})
        self.assertEqual(outcome.metadata, {})

    def test_outcome_is_frozen(self) -> None:
        outcome = ImportWorkflow(ProcessingPipeline(stages=())).execute(
            make_request(), WORKSPACE
        )
        with self.assertRaises(AttributeError):
            outcome.metadata = {}  # type: ignore[misc]

    def test_invalid_request_raises_value_error(self) -> None:
        pipeline = ProcessingPipeline(stages=(RecordingStage("a"),))
        with self.assertRaises(ValueError):
            ImportWorkflow(pipeline).execute(
                make_request(collection_id=""), WORKSPACE
            )

    def test_relative_workspace_raises_value_error(self) -> None:
        pipeline = ProcessingPipeline(stages=(RecordingStage("a"),))
        with self.assertRaisesRegex(ValueError, "workspace"):
            ImportWorkflow(pipeline).execute(make_request(), Path("relative/tmp"))

    def test_non_pipeline_constructor_argument_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            ImportWorkflow("not a pipeline")  # type: ignore[arg-type]


class CancellationTests(unittest.TestCase):
    def test_cancelled_before_first_stage(self) -> None:
        calls: list = []
        flag = {"cancelled": True}
        bus = ImportEventBus()
        pipeline = ProcessingPipeline(stages=(RecordingStage("a", calls=calls),))
        workflow = ImportWorkflow(
            pipeline, event_bus=bus, is_cancelled=lambda: flag["cancelled"]
        )
        with self.assertRaises(WorkflowCancelledError):
            workflow.execute(make_request(), WORKSPACE, import_id="imp-1")
        self.assertEqual(calls, [])  # stage never executed
        types = [e.event_type for e in bus.events]
        self.assertEqual(types, [EventType.PIPELINE_STARTED, EventType.PIPELINE_CANCELLED])
        cancelled = bus.events[-1]
        self.assertEqual(cancelled.context["stage_id"], "a")
        self.assertEqual(cancelled.context["stage_index"], 0)
        self.assertEqual(cancelled.context["reason"], "cancelled by caller")

    def test_cancelled_between_stages(self) -> None:
        calls: list = []
        flag = {"cancelled": False}
        bus = ImportEventBus()
        pipeline = ProcessingPipeline(
            stages=(
                FlipCancellationStage("flip", flag),
                RecordingStage("never", calls=calls),
            )
        )
        workflow = ImportWorkflow(
            pipeline, event_bus=bus, is_cancelled=lambda: flag["cancelled"]
        )
        with self.assertRaises(WorkflowCancelledError):
            workflow.execute(make_request(), WORKSPACE)
        self.assertEqual(calls, [])  # second stage never executed
        types = [e.event_type for e in bus.events]
        self.assertEqual(
            types,
            [
                EventType.PIPELINE_STARTED,
                EventType.STAGE_STARTED,
                EventType.STAGE_COMPLETED,
                EventType.PIPELINE_CANCELLED,
            ],
        )

    def test_cancelled_at_final_boundary_after_last_stage(self) -> None:
        # is_cancelled returns True only on the third check: pre-stage (1),
        # post-stage (2), then the pre-handoff boundary (3).
        state = {"checks": 0}

        def is_cancelled() -> bool:
            state["checks"] += 1
            return state["checks"] >= 3

        bus = ImportEventBus()
        pipeline = ProcessingPipeline(stages=(RecordingStage("only"),))
        workflow = ImportWorkflow(pipeline, event_bus=bus, is_cancelled=is_cancelled)
        with self.assertRaises(WorkflowCancelledError):
            workflow.execute(make_request(), WORKSPACE)
        types = [e.event_type for e in bus.events]
        self.assertEqual(
            types,
            [
                EventType.PIPELINE_STARTED,
                EventType.STAGE_STARTED,
                EventType.STAGE_COMPLETED,
                EventType.PIPELINE_CANCELLED,
            ],
        )
        self.assertNotIn(EventType.PIPELINE_COMPLETED, types)
        self.assertIsNone(bus.events[-1].context["stage_id"])

    def test_cancelled_empty_pipeline(self) -> None:
        bus = ImportEventBus()
        workflow = ImportWorkflow(
            ProcessingPipeline(stages=()),
            event_bus=bus,
            is_cancelled=lambda: True,
        )
        with self.assertRaises(WorkflowCancelledError):
            workflow.execute(make_request(), WORKSPACE)
        types = [e.event_type for e in bus.events]
        self.assertEqual(types, [EventType.PIPELINE_STARTED, EventType.PIPELINE_CANCELLED])

    def test_cancellation_is_raised_unwrapped(self) -> None:
        workflow = ImportWorkflow(
            ProcessingPipeline(stages=(RecordingStage("a"),)),
            is_cancelled=lambda: True,
        )
        with self.assertRaises(WorkflowCancelledError) as ctx:
            workflow.execute(make_request(), WORKSPACE)
        self.assertIs(type(ctx.exception), WorkflowCancelledError)
        self.assertIsNone(ctx.exception.__cause__)

    def test_cancellation_works_without_event_bus(self) -> None:
        workflow = ImportWorkflow(
            ProcessingPipeline(stages=(RecordingStage("a"),)),
            is_cancelled=lambda: True,
        )
        with self.assertRaises(WorkflowCancelledError):
            workflow.execute(make_request(), WORKSPACE)

    def test_stage_raised_cancellation_propagates_unwrapped(self) -> None:
        original = WorkflowCancelledError("stage abort")
        bus = ImportEventBus()
        pipeline = ProcessingPipeline(stages=(RaisingStage("canceller", original),))
        workflow = ImportWorkflow(pipeline, event_bus=bus)
        with self.assertRaises(WorkflowCancelledError) as ctx:
            workflow.execute(make_request(), WORKSPACE)
        # Original instance propagates unwrapped, with no chaining added.
        self.assertIs(ctx.exception, original)
        self.assertIs(type(ctx.exception), WorkflowCancelledError)
        self.assertIsNone(ctx.exception.__cause__)
        # Cancellation is not failure: exact sequence, with no STAGE_FAILED,
        # no STAGE_COMPLETED, and no PIPELINE_COMPLETED.
        types = [e.event_type for e in bus.events]
        self.assertEqual(
            types,
            [
                EventType.PIPELINE_STARTED,
                EventType.STAGE_STARTED,
                EventType.PIPELINE_CANCELLED,
            ],
        )
        self.assertNotIn(EventType.STAGE_FAILED, types)
        self.assertNotIn(EventType.STAGE_COMPLETED, types)
        self.assertNotIn(EventType.PIPELINE_COMPLETED, types)
        self.assertEqual(bus.events[-1].context["reason"], "cancelled by stage")


class StageFailureTests(unittest.TestCase):
    def test_base_exception_is_neither_swallowed_nor_wrapped(self) -> None:
        # KeyboardInterrupt is the representative BaseException: it must
        # propagate unchanged — never wrapped in StageExecutionError, and
        # with no failure or terminal pipeline events recorded.
        interrupt = KeyboardInterrupt()
        bus = ImportEventBus()
        pipeline = ProcessingPipeline(stages=(RaisingStage("halt", interrupt),))
        workflow = ImportWorkflow(pipeline, event_bus=bus)
        with self.assertRaises(KeyboardInterrupt) as ctx:
            workflow.execute(make_request(), WORKSPACE)
        self.assertIs(ctx.exception, interrupt)
        self.assertNotIsInstance(ctx.exception, StageExecutionError)
        types = [e.event_type for e in bus.events]
        self.assertEqual(
            types,
            [
                EventType.PIPELINE_STARTED,
                EventType.STAGE_STARTED,
            ],
        )
        self.assertNotIn(EventType.STAGE_FAILED, types)
        self.assertNotIn(EventType.PIPELINE_COMPLETED, types)
        self.assertNotIn(EventType.PIPELINE_CANCELLED, types)

    def test_ordinary_exception_wrapped_as_stage_execution_error(self) -> None:
        cause = ValueError("boom")
        pipeline = ProcessingPipeline(stages=(RaisingStage("bad", cause),))
        with self.assertRaises(StageExecutionError) as ctx:
            ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)
        exc = ctx.exception
        self.assertEqual(exc.stage_id, "bad")
        self.assertIs(exc.cause, cause)
        self.assertIn("bad", str(exc))

    def test_traceback_chaining_is_preserved(self) -> None:
        # Authorized Unit 4 contract: raise StageExecutionError(...) from exc.
        cause = ValueError("boom")
        pipeline = ProcessingPipeline(stages=(RaisingStage("bad", cause),))
        with self.assertRaises(StageExecutionError) as ctx:
            ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)
        exc = ctx.exception
        self.assertIs(exc.__cause__, cause)  # explicit raise-from chain
        self.assertTrue(exc.__suppress_context__)
        self.assertIsNotNone(cause.__traceback__)  # original traceback intact

    def test_first_failure_halts_execution(self) -> None:
        calls: list = []
        pipeline = ProcessingPipeline(
            stages=(
                RecordingStage("ok", calls=calls),
                RaisingStage("bad", RuntimeError("x")),
                RecordingStage("never", calls=calls),
            )
        )
        with self.assertRaises(StageExecutionError):
            ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)
        self.assertEqual(calls, ["ok"])

    def test_invalid_stage_result_raises_stage_contract_error(self) -> None:
        class InvalidResultStage:
            @property
            def stage_id(self) -> str:
                return "invalid"

            def execute(self, stage_input: StageInput) -> StageResult:
                return StageResult(
                    artifacts={"bad": StageArtifact(relative_path="../escape")},
                    metadata={},
                )

        pipeline = ProcessingPipeline(stages=(InvalidResultStage(),))
        with self.assertRaises(StageContractError) as ctx:
            ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)
        self.assertEqual(ctx.exception.stage_id, "invalid")

    def test_contract_error_from_validation_preserves_value_error_chain(self) -> None:
        class InvalidResultStage:
            @property
            def stage_id(self) -> str:
                return "invalid"

            def execute(self, stage_input: StageInput) -> StageResult:
                return StageResult(
                    artifacts={"bad": StageArtifact(relative_path="/absolute")},
                    metadata={},
                )

        pipeline = ProcessingPipeline(stages=(InvalidResultStage(),))
        with self.assertRaises(StageContractError) as ctx:
            ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)
        self.assertIsInstance(ctx.exception.__cause__, ValueError)

    def test_non_stage_result_return_raises_stage_contract_error(self) -> None:
        pipeline = ProcessingPipeline(stages=(BadReturnStage("none", None),))
        with self.assertRaises(StageContractError) as ctx:
            ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)
        self.assertEqual(ctx.exception.stage_id, "none")
        self.assertIn("expected StageResult", str(ctx.exception))

    def test_wrong_type_return_raises_stage_contract_error(self) -> None:
        pipeline = ProcessingPipeline(stages=(BadReturnStage("text", "oops"),))
        with self.assertRaises(StageContractError) as ctx:
            ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)
        self.assertIn("expected StageResult", str(ctx.exception))

    def test_duplicate_artifact_key_across_stages_raises(self) -> None:
        pipeline = ProcessingPipeline(
            stages=(
                RecordingStage("a", artifact_key="shared"),
                RecordingStage("b", artifact_key="shared"),
            )
        )
        with self.assertRaises(StageContractError) as ctx:
            ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)
        self.assertEqual(ctx.exception.stage_id, "b")
        self.assertIn("duplicate artifact key", str(ctx.exception))

    def test_duplicate_metadata_key_across_stages_raises(self) -> None:
        pipeline = ProcessingPipeline(
            stages=(
                RecordingStage("a", metadata={"shared": 1}),
                RecordingStage("b", metadata={"shared": 2}),
            )
        )
        with self.assertRaises(StageContractError) as ctx:
            ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)
        self.assertEqual(ctx.exception.stage_id, "b")
        self.assertIn("duplicate metadata key", str(ctx.exception))

    def test_stage_raised_contract_error_propagates_unwrapped(self) -> None:
        original = StageContractError("self", "self-detected violation")
        pipeline = ProcessingPipeline(stages=(RaisingStage("self", original),))
        with self.assertRaises(StageContractError) as ctx:
            ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)
        self.assertIs(ctx.exception, original)

    def test_failure_works_without_event_bus(self) -> None:
        pipeline = ProcessingPipeline(
            stages=(RaisingStage("bad", ValueError("boom")),)
        )
        with self.assertRaises(StageExecutionError):
            ImportWorkflow(pipeline).execute(make_request(), WORKSPACE)


class EventOrderingTests(unittest.TestCase):
    def test_happy_path_event_sequence_and_context(self) -> None:
        bus = ImportEventBus()
        pipeline = ProcessingPipeline(
            stages=(RecordingStage("a"), RecordingStage("b"))
        )
        ImportWorkflow(pipeline, event_bus=bus).execute(
            make_request(), WORKSPACE, import_id="imp-9"
        )
        types = [e.event_type for e in bus.events]
        self.assertEqual(
            types,
            [
                EventType.PIPELINE_STARTED,
                EventType.STAGE_STARTED,
                EventType.STAGE_COMPLETED,
                EventType.STAGE_STARTED,
                EventType.STAGE_COMPLETED,
                EventType.PIPELINE_COMPLETED,
            ],
        )
        started = bus.events[0]
        self.assertEqual(started.context["stage_ids"], ("a", "b"))
        self.assertEqual(started.context["stage_count"], 2)
        first_stage = bus.events[1]
        self.assertEqual(first_stage.context["stage_id"], "a")
        self.assertEqual(first_stage.context["stage_index"], 0)
        self.assertEqual(first_stage.context["stage_count"], 2)
        second_stage = bus.events[3]
        self.assertEqual(second_stage.context["stage_id"], "b")
        self.assertEqual(second_stage.context["stage_index"], 1)
        completed = bus.events[-1]
        self.assertEqual(completed.context["stage_count"], 2)
        for event in bus.events:
            self.assertEqual(event.import_id, "imp-9")

    def test_failure_event_sequence(self) -> None:
        bus = ImportEventBus()
        pipeline = ProcessingPipeline(
            stages=(
                RecordingStage("ok"),
                RaisingStage("bad", ValueError("boom")),
                RecordingStage("never"),
            )
        )
        with self.assertRaises(StageExecutionError):
            ImportWorkflow(pipeline, event_bus=bus).execute(make_request(), WORKSPACE)
        types = [e.event_type for e in bus.events]
        self.assertEqual(
            types,
            [
                EventType.PIPELINE_STARTED,
                EventType.STAGE_STARTED,
                EventType.STAGE_COMPLETED,
                EventType.STAGE_STARTED,
                EventType.STAGE_FAILED,
            ],
        )
        failed = bus.events[-1]
        self.assertEqual(failed.context["stage_id"], "bad")
        self.assertEqual(failed.context["stage_index"], 1)
        self.assertEqual(failed.context["error_type"], "ValueError")

    def test_contract_failure_records_stage_failed(self) -> None:
        bus = ImportEventBus()
        pipeline = ProcessingPipeline(stages=(BadReturnStage("none", None),))
        with self.assertRaises(StageContractError):
            ImportWorkflow(pipeline, event_bus=bus).execute(make_request(), WORKSPACE)
        self.assertEqual(bus.events[-1].event_type, EventType.STAGE_FAILED)
        self.assertEqual(bus.events[-1].context["error_type"], "StageContractError")

    def test_empty_pipeline_event_sequence(self) -> None:
        bus = ImportEventBus()
        ImportWorkflow(ProcessingPipeline(stages=()), event_bus=bus).execute(
            make_request(), WORKSPACE
        )
        types = [e.event_type for e in bus.events]
        self.assertEqual(
            types, [EventType.PIPELINE_STARTED, EventType.PIPELINE_COMPLETED]
        )

    def test_events_do_not_include_transaction_event_types(self) -> None:
        # Pipeline lifecycle must not emit transaction-owned events
        # (IMPORT_STARTED, IMPORT_COMPLETE, ...); no duplicate top-level events.
        bus = ImportEventBus()
        pipeline = ProcessingPipeline(stages=(RecordingStage("a"),))
        ImportWorkflow(pipeline, event_bus=bus).execute(make_request(), WORKSPACE)
        transaction_types = {
            EventType.IMPORT_STARTED,
            EventType.PACKAGE_VALIDATED,
            EventType.COLLECTION_CREATED,
            EventType.IMAGES_IMPORTED,
            EventType.COLLECTION_COMMITTED,
            EventType.IMPORT_COMPLETE,
        }
        for event in bus.events:
            self.assertNotIn(event.event_type, transaction_types)


class ProcessedArtifactAssemblyTests(unittest.TestCase):
    def test_multi_role_crop_stage_order_maps_then_sorts_descriptors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            payload = make_baseline_jpeg()
            records = []
            artifacts = {}
            stages = {}
            for role in ("edge", "front", "reverse"):
                normalized_key = f"source-{role}"
                cropped_key = f"output-{role}"
                normalized_path = f"source/{role}.jpg"
                cropped_path = f"result/{role}.jpg"
                (workspace / normalized_path).parent.mkdir(
                    parents=True, exist_ok=True
                )
                (workspace / cropped_path).parent.mkdir(
                    parents=True, exist_ok=True
                )
                (workspace / normalized_path).write_bytes(payload)
                (workspace / cropped_path).write_bytes(payload)
                artifacts[normalized_key] = StageArtifact(
                    normalized_path, "image/jpeg"
                )
                stages[normalized_key] = "image-normalization"
                records.append(
                    {
                        "coin_id": "coin-1",
                        "role": role,
                        "x": 0,
                        "y": 0,
                        "width": 8,
                        "height": 6,
                        "crop_confidence": 0.0,
                        "crop_applied": False,
                        "source_normalized_key": normalized_key,
                        "source_width": 8,
                        "source_height": 6,
                    }
                )
                artifacts[cropped_key] = StageArtifact(
                    cropped_path, "image/jpeg"
                )
                stages[cropped_key] = "crop-detection"
            # Real crop-stage output is lexical by role: edge/front/reverse.
            artifacts = {
                **{
                    key: value
                    for key, value in artifacts.items()
                    if stages[key] == "image-normalization"
                },
                **{
                    f"output-{role}": artifacts[f"output-{role}"]
                    for role in ("edge", "front", "reverse")
                },
            }
            prepared = assemble_prepared_import(
                make_request(),
                PipelineOutcome(
                    artifacts=artifacts,
                    metadata={"crop_records": records},
                ),
                workspace,
                stages,
            )
            self.assertEqual(
                [item.role for item in prepared.processed_artifacts.descriptors],
                ["front", "reverse", "edge"],
            )
            prepared.processed_artifacts.close()

    def test_exact_stage_routing_ignores_misleading_keys_and_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            payload = make_baseline_jpeg()
            normalized = workspace / "looks-cropped" / "selected.jpg"
            cropped = workspace / "looks-normalized" / "fallback.jpg"
            normalized.parent.mkdir(parents=True)
            cropped.parent.mkdir(parents=True)
            normalized.write_bytes(payload)
            cropped.write_bytes(payload)
            outcome = PipelineOutcome(
                artifacts={
                    "definitely-cropped-by-name": StageArtifact(
                        "looks-cropped/selected.jpg", "image/jpeg"
                    ),
                    "definitely-normalized-by-name": StageArtifact(
                        "looks-normalized/fallback.jpg", "image/jpeg"
                    ),
                },
                metadata={
                    "crop_records": [
                        {
                            "coin_id": "coin-1",
                            "role": "front",
                            "x": 0,
                            "y": 0,
                            "width": 8,
                            "height": 6,
                            "crop_confidence": 0.0,
                            "crop_applied": False,
                            "source_normalized_key": "definitely-cropped-by-name",
                            "source_width": 8,
                            "source_height": 6,
                        }
                    ]
                },
            )
            prepared = assemble_prepared_import(
                make_request(),
                outcome,
                workspace,
                {
                    "definitely-cropped-by-name": "image-normalization",
                    "definitely-normalized-by-name": "crop-detection",
                },
            )
            self.assertEqual(
                prepared.processed_artifacts.descriptors[0].artifact_key,
                "definitely-cropped-by-name",
            )
            self.assertEqual(
                prepared.processed_artifacts.descriptors[0].variant,
                "NORMALIZED",
            )
            prepared.processed_artifacts.close()

    def test_non_jpeg_typed_candidate_is_rejected_not_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            payload = make_baseline_jpeg()
            normalized = workspace / "normalized.jpg"
            cropped = workspace / "cropped.jpg"
            normalized.write_bytes(payload)
            cropped.write_bytes(payload)
            outcome = PipelineOutcome(
                artifacts={
                    "source": StageArtifact("normalized.jpg", "image/png"),
                    "candidate": StageArtifact("cropped.jpg", "image/jpeg"),
                },
                metadata={
                    "crop_records": [
                        {
                            "coin_id": "coin-1",
                            "role": "front",
                            "x": 0,
                            "y": 0,
                            "width": 8,
                            "height": 6,
                            "crop_confidence": 0.0,
                            "crop_applied": False,
                            "source_normalized_key": "source",
                            "source_width": 8,
                            "source_height": 6,
                        }
                    ]
                },
            )
            with self.assertRaises(StageContractError):
                assemble_prepared_import(
                    make_request(),
                    outcome,
                    workspace,
                    {
                        "source": "image-normalization",
                        "candidate": "crop-detection",
                    },
                )

    def test_exact_fallback_selects_normalized_with_single_use_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            payload = make_baseline_jpeg()
            normalized = workspace / "normalized/coin-1/front.jpg"
            cropped = workspace / "cropped/coin-1/front.jpg"
            normalized.parent.mkdir(parents=True)
            cropped.parent.mkdir(parents=True)
            normalized.write_bytes(payload)
            cropped.write_bytes(payload)
            outcome = PipelineOutcome(
                artifacts={
                    "normalized-coin-1-front": StageArtifact(
                        "normalized/coin-1/front.jpg", "image/jpeg"
                    ),
                    "cropped-coin-1-front": StageArtifact(
                        "cropped/coin-1/front.jpg", "image/jpeg"
                    ),
                },
                metadata={
                    "crop_records": [
                        {
                            "coin_id": "coin-1",
                            "role": "front",
                            "x": 0,
                            "y": 0,
                            "width": 8,
                            "height": 6,
                            "crop_confidence": 0.0,
                            "crop_applied": False,
                            "source_normalized_key": "normalized-coin-1-front",
                            "source_width": 8,
                            "source_height": 6,
                        }
                    ]
                },
            )
            prepared = assemble_prepared_import(
                make_request(),
                outcome,
                workspace,
                {
                    "normalized-coin-1-front": "image-normalization",
                    "cropped-coin-1-front": "crop-detection",
                },
            )
            self.assertIsNotNone(prepared.processed_artifacts)
            descriptor = prepared.processed_artifacts.descriptors[0]
            self.assertEqual(descriptor.variant, "NORMALIZED")
            self.assertEqual(descriptor.artifact_key, "normalized-coin-1-front")
            selected = next(
                item
                for item in prepared.files
                if item.artifact_key == "normalized-coin-1-front"
            )
            self.assertEqual(selected.durability_classification, "PROCESSED_SELECTED")
            self.assertIsNotNone(selected.sha256)
            prepared.processed_artifacts.close_if_unclaimed()

    def test_inconsistent_fallback_fails_and_closes_handles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            normalized = workspace / "normalized/coin-1/front.jpg"
            cropped = workspace / "cropped/coin-1/front.jpg"
            normalized.parent.mkdir(parents=True)
            cropped.parent.mkdir(parents=True)
            normalized.write_bytes(make_baseline_jpeg())
            cropped.write_bytes(make_baseline_jpeg((7, 5)))
            outcome = PipelineOutcome(
                artifacts={
                    "normalized-coin-1-front": StageArtifact(
                        "normalized/coin-1/front.jpg", "image/jpeg"
                    ),
                    "cropped-coin-1-front": StageArtifact(
                        "cropped/coin-1/front.jpg", "image/jpeg"
                    ),
                },
                metadata={
                    "crop_records": [
                        {
                            "coin_id": "coin-1",
                            "role": "front",
                            "x": 0,
                            "y": 0,
                            "width": 8,
                            "height": 6,
                            "crop_confidence": 0.0,
                            "crop_applied": False,
                            "source_normalized_key": "normalized-coin-1-front",
                            "source_width": 8,
                            "source_height": 6,
                        }
                    ]
                },
            )
            with self.assertRaises(StageContractError):
                assemble_prepared_import(
                    make_request(),
                    outcome,
                    workspace,
                    {
                        "normalized-coin-1-front": "image-normalization",
                        "cropped-coin-1-front": "crop-detection",
                    },
                )
            # No leaked handle prevents cleanup on Windows.
            normalized.unlink()
            cropped.unlink()


if __name__ == "__main__":
    unittest.main()
