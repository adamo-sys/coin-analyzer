"""Focused tests for Sprint 7 workflow pipeline construction and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
import unittest

from capture_import.workflow_models import (
    ImportConfiguration,
    ImportRequest,
    StageArtifact,
    StageInput,
    StageResult,
)
from capture_import.workflow_pipeline import (
    ImportWorkflowError,
    PipelineConfigurationError,
    ProcessingPipeline,
    ProcessingStage,
    StageContractError,
    StageExecutionError,
    WorkflowCancelledError,
)


def make_request() -> ImportRequest:
    return ImportRequest(
        source=Path(tempfile.gettempdir()),
        collection_id="collection-1",
        configuration=ImportConfiguration(),
    )


def make_stage_input() -> StageInput:
    return StageInput(
        request=make_request(),
        workspace=Path(tempfile.gettempdir()),
        artifacts={},
    )


@dataclass(frozen=True, slots=True)
class FakeStage:
    """Lightweight fake implementing ProcessingStage."""

    _stage_id: str

    @property
    def stage_id(self) -> str:
        return self._stage_id

    def execute(self, stage_input: StageInput) -> StageResult:
        return StageResult(artifacts={}, metadata={"fake": True})


@dataclass(frozen=True, slots=True)
class FakeTransformStage:
    """Fake that returns a deterministic transform result."""

    _stage_id: str
    key: str
    value: str

    @property
    def stage_id(self) -> str:
        return self._stage_id

    def execute(self, stage_input: StageInput) -> StageResult:
        return StageResult(
            artifacts={},
            metadata={self.key: self.value},
        )


class ValidConstructionTests(unittest.TestCase):
    def test_empty_pipeline_is_accepted(self) -> None:
        pipeline = ProcessingPipeline(stages=())
        self.assertEqual(pipeline.stages, ())
        self.assertEqual(pipeline.stage_ids, ())

    def test_single_stage_pipeline(self) -> None:
        stage = FakeStage("validation")
        pipeline = ProcessingPipeline(stages=(stage,))
        self.assertEqual(pipeline.stage_ids, ("validation",))

    def test_multi_stage_pipeline_preserves_order(self) -> None:
        a = FakeStage("stage_a")
        b = FakeStage("stage_b")
        c = FakeStage("stage_c")
        pipeline = ProcessingPipeline(stages=(a, b, c))
        self.assertEqual(pipeline.stage_ids, ("stage_a", "stage_b", "stage_c"))

    def test_pipeline_is_frozen(self) -> None:
        pipeline = ProcessingPipeline(stages=(FakeStage("s"),))
        with self.assertRaises(AttributeError):
            pipeline.stages = ()  # type: ignore[misc]


class DuplicateIdTests(unittest.TestCase):
    def test_duplicate_stage_id_raises(self) -> None:
        with self.assertRaisesRegex(PipelineConfigurationError, "Duplicate"):
            ProcessingPipeline(stages=(FakeStage("same"), FakeStage("same")))

    def test_duplicate_id_in_three_stage_pipeline(self) -> None:
        with self.assertRaisesRegex(PipelineConfigurationError, "Duplicate"):
            ProcessingPipeline(
                stages=(FakeStage("a"), FakeStage("b"), FakeStage("a"))
            )


class MalformedStageTests(unittest.TestCase):
    def test_empty_stage_id_raises(self) -> None:
        with self.assertRaisesRegex(PipelineConfigurationError, "invalid stage_id"):
            ProcessingPipeline(stages=(FakeStage(""),))

    def test_non_string_stage_id_raises(self) -> None:
        class BadStage:
            @property
            def stage_id(self):
                return 123

            def execute(self, stage_input):
                return None

        with self.assertRaisesRegex(PipelineConfigurationError, "invalid stage_id"):
            ProcessingPipeline(stages=(BadStage(),))  # type: ignore[list-item]

    def test_missing_stage_id_attribute_raises(self) -> None:
        class NoId:
            def execute(self, stage_input):
                return None

        with self.assertRaisesRegex(PipelineConfigurationError, "missing required"):
            ProcessingPipeline(stages=(NoId(),))  # type: ignore[list-item]

    def test_missing_execute_method_raises(self) -> None:
        class NoExecute:
            @property
            def stage_id(self):
                return "noop"

        with self.assertRaisesRegex(PipelineConfigurationError, "missing required"):
            ProcessingPipeline(stages=(NoExecute(),))  # type: ignore[list-item]

    def test_non_callable_execute_raises(self) -> None:
        class BadExecute:
            @property
            def stage_id(self):
                return "noop"

            execute = "not callable"

        with self.assertRaisesRegex(PipelineConfigurationError, "missing required"):
            ProcessingPipeline(stages=(BadExecute(),))  # type: ignore[list-item]


class CollectionMutationTests(unittest.TestCase):
    def test_list_rejected_for_stages(self) -> None:
        with self.assertRaisesRegex(PipelineConfigurationError, "immutable tuple"):
            ProcessingPipeline(stages=[FakeStage("a")])  # type: ignore[arg-type]


class ResultValidationTests(unittest.TestCase):
    def test_valid_result_passes(self) -> None:
        pipeline = ProcessingPipeline(stages=(FakeStage("s"),))
        result = StageResult(artifacts={}, metadata={"key": "value"})
        pipeline.validate_stage_result(result, "s")  # Should not raise

    def test_nested_invalid_artifact_raises_stage_contract(self) -> None:
        pipeline = ProcessingPipeline(stages=(FakeStage("s"),))
        result = StageResult(
            artifacts={"bad": StageArtifact(relative_path="../escape")},
            metadata={},
        )
        with self.assertRaises(StageContractError) as ctx:
            pipeline.validate_stage_result(result, "s")
        self.assertEqual(ctx.exception.stage_id, "s")
        self.assertIn("invalid StageResult", str(ctx.exception))

    def test_result_validation_preserves_original_cause(self) -> None:
        pipeline = ProcessingPipeline(stages=(FakeStage("s"),))
        result = StageResult(
            artifacts={"bad": StageArtifact(relative_path="/absolute")},
            metadata={},
        )
        with self.assertRaises(StageContractError) as ctx:
            pipeline.validate_stage_result(result, "s")
        self.assertIsInstance(ctx.exception.__cause__, ValueError)


class ErrorHierarchyTests(unittest.TestCase):
    def test_all_errors_inherit_from_import_workflow(self) -> None:
        errors = [
            PipelineConfigurationError("msg"),
            StageContractError("sid", "msg"),
            StageExecutionError("sid", ValueError("boom")),
            WorkflowCancelledError(),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                self.assertIsInstance(error, ImportWorkflowError)

    def test_stage_contract_error_includes_stage_id(self) -> None:
        error = StageContractError("my_stage", "something failed")
        self.assertEqual(error.stage_id, "my_stage")
        self.assertIn("my_stage", str(error))

    def test_stage_execution_error_includes_stage_id_and_cause(self) -> None:
        cause = ValueError("original")
        error = StageExecutionError("my_stage", cause)
        self.assertEqual(error.stage_id, "my_stage")
        self.assertIs(error.cause, cause)
        self.assertIn("my_stage", str(error))


class DeterministicEqualityTests(unittest.TestCase):
    def test_same_stages_equal(self) -> None:
        a = ProcessingPipeline(stages=(FakeStage("a"), FakeStage("b")))
        b = ProcessingPipeline(stages=(FakeStage("a"), FakeStage("b")))
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_different_order_not_equal(self) -> None:
        a = ProcessingPipeline(stages=(FakeStage("a"), FakeStage("b")))
        b = ProcessingPipeline(stages=(FakeStage("b"), FakeStage("a")))
        self.assertNotEqual(a, b)


class ProtocolConformanceTests(unittest.TestCase):
    def test_fake_stage_satisfies_protocol(self) -> None:
        stage: ProcessingStage = FakeStage("test")
        self.assertEqual(stage.stage_id, "test")
        result = stage.execute(make_stage_input())
        self.assertIsInstance(result, StageResult)

    def test_transform_stage_satisfies_protocol(self) -> None:
        stage: ProcessingStage = FakeTransformStage("transform", "k", "v")
        result = stage.execute(make_stage_input())
        self.assertEqual(result.metadata["k"], "v")


if __name__ == "__main__":
    unittest.main()
