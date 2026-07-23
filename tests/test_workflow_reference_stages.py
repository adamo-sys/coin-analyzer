"""Focused tests for Sprint 7 Unit 7: reference processing stages.

Covers the two reference stages (package validation, manifest
preparation), deterministic pipeline registration, the application-layer
adapter to the existing coordinator seam, and the owner-mandated critical
proof: reference stages stay ephemeral and durability remains reachable
exclusively through the Unit 6 transaction delegate, exactly once.
"""

from __future__ import annotations

import ast
import json
import os
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from unittest import mock

from capture_import import workflow_stages
from capture_import.errors import (
    CaptureImportError,
    InvalidManifest,
    PackageChanged,
    PackageNotZip,
    RecoveryRequired,
)
from capture_import.events import EventType, ImportEventBus
from capture_import.manifest import CapturePackageManifestParser
from capture_import.preview import PreviewDecisionSet
from capture_import.workflow_adapter import commit_prepared_import
from capture_import.workflow_execution import ImportWorkflow
from capture_import.workflow_models import (
    ImportConfiguration,
    ImportRequest,
    PreparedFile,
    PreparedImport,
    StageArtifact,
    StageInput,
    StageResult,
)
from capture_import.workflow_pipeline import (
    PipelineConfigurationError,
    ProcessingPipeline,
    StageContractError,
    StageExecutionError,
    WorkflowCancelledError,
)
from capture_import.workflow_stages import (
    MANIFEST_PREPARATION_STAGE_ID,
    PACKAGE_VALIDATION_STAGE_ID,
    PREPARED_MANIFEST_ARTIFACT,
    PREPARED_MANIFEST_NAME,
    ManifestPreparationStage,
    PackageValidationStage,
    build_reference_pipeline,
)
from tests.capture_package_fixtures import manifest_dict, package_bytes

SOURCE_NAME = "fixture.ca-package"


def make_request(source: Path, collection_id: str = "collection-1") -> ImportRequest:
    return ImportRequest(
        source=source,
        collection_id=collection_id,
        configuration=ImportConfiguration(),
    )


class DelegateSpy:
    """Records Unit 6 transaction-delegate invocations."""

    def __init__(self) -> None:
        self.calls: list[PreparedImport] = []
        self.result = object()

    def __call__(self, prepared: PreparedImport) -> object:
        self.calls.append(prepared)
        return self.result


class CancelAfter:
    """Cancellation probe: returns False until the ``n``-th call fires True."""

    def __init__(self, n: int) -> None:
        self._n = n
        self.calls = 0

    def __call__(self) -> bool:
        self.calls += 1
        return self.calls >= self._n


class PassThroughStage:
    """Trivial stub proving the framework design (per the sprint plan)."""

    def __init__(self, stage_id: str, seen: list) -> None:
        self._stage_id = stage_id
        self._seen = seen

    @property
    def stage_id(self) -> str:
        return self._stage_id

    def execute(self, stage_input: StageInput) -> StageResult:
        self._seen.append(stage_input)
        return StageResult(artifacts={}, metadata={})


class PackageTestCase(unittest.TestCase):
    """Provides a temp workspace and valid/invalid package sources."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        self.source_dir = root / "source"
        self.source_dir.mkdir()

    def write_source(
        self, payload: bytes | None = None, name: str = SOURCE_NAME
    ) -> Path:
        source = self.source_dir / name
        source.write_bytes(payload if payload is not None else package_bytes())
        return source


class PackageValidationStageTests(PackageTestCase):
    """The validation stage adapts the real validator, race-aware."""

    def test_valid_source_publishes_normalized_manifest_artifact(self) -> None:
        payload = package_bytes()
        source = self.write_source(payload)
        result = PackageValidationStage().execute(
            StageInput(request=make_request(source), workspace=self.workspace, artifacts={})
        )
        self.assertEqual(
            dict(result.artifacts),
            {
                PREPARED_MANIFEST_ARTIFACT: StageArtifact(
                    relative_path=PREPARED_MANIFEST_NAME,
                    content_type="application/json",
                )
            },
        )
        self.assertEqual(
            dict(result.metadata),
            {
                "package_basename": SOURCE_NAME,
                "package_sha256": sha256(payload).hexdigest(),
                "package_byte_length": len(payload),
            },
        )
        artifact = self.workspace / PREPARED_MANIFEST_NAME
        self.assertTrue(artifact.is_file())
        manifest = CapturePackageManifestParser().parse(artifact.read_bytes())
        self.assertEqual(manifest.schema, "coin-analyzer.capture-package")
        self.assertEqual(len(manifest.coins), 1)

    def test_normalized_manifest_serialization_policy(self) -> None:
        source = self.write_source()
        PackageValidationStage().execute(
            StageInput(request=make_request(source), workspace=self.workspace, artifacts={})
        )
        payload = (self.workspace / PREPARED_MANIFEST_NAME).read_bytes()
        text = payload.decode("utf-8", errors="strict")
        self.assertFalse(text.startswith("\ufeff"))
        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))
        document = json.loads(text)
        self.assertEqual(list(document.keys()), sorted(document.keys()))
        # Fixed-point: re-serializing under the documented policy reproduces
        # the exact bytes (sorted keys, compact separators, UTF-8, one LF).
        self.assertEqual(
            text,
            json.dumps(
                document,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n",
        )

    def test_invalid_package_surfaces_capture_error(self) -> None:
        source = self.write_source(b"this is not a zip archive")
        with self.assertRaises(PackageNotZip):
            PackageValidationStage().execute(
                StageInput(
                    request=make_request(source), workspace=self.workspace, artifacts={}
                )
            )
        self.assertFalse((self.workspace / PREPARED_MANIFEST_NAME).exists())

    def test_missing_source_fails_closed(self) -> None:
        with self.assertRaises(FileNotFoundError):
            PackageValidationStage().execute(
                StageInput(
                    request=make_request(self.source_dir / "absent.ca-package"),
                    workspace=self.workspace,
                    artifacts={},
                )
            )

    def test_source_directory_rejected(self) -> None:
        with self.assertRaises(OSError):
            PackageValidationStage().execute(
                StageInput(
                    request=make_request(self.source_dir),
                    workspace=self.workspace,
                    artifacts={},
                )
            )

    @unittest.skipUnless(hasattr(os, "symlink"), "platform lacks symlink support")
    def test_symlink_source_rejected(self) -> None:
        target = self.write_source()
        link = self.source_dir / "linked.ca-package"
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        with self.assertRaises(OSError):
            PackageValidationStage().execute(
                StageInput(
                    request=make_request(link), workspace=self.workspace, artifacts={}
                )
            )
        self.assertFalse((self.workspace / PREPARED_MANIFEST_NAME).exists())

    def test_source_replacement_between_passes_fails_closed(self) -> None:
        source = self.write_source()
        # First call binds the open handle; second simulates a detected
        # replacement before the validator pass.
        with mock.patch.object(
            workflow_stages, "handle_matches_path", side_effect=[True, False]
        ):
            with self.assertRaises(PackageChanged):
                PackageValidationStage().execute(
                    StageInput(
                        request=make_request(source),
                        workspace=self.workspace,
                        artifacts={},
                    )
                )
        self.assertFalse((self.workspace / PREPARED_MANIFEST_NAME).exists())

    def test_source_is_never_written(self) -> None:
        payload = package_bytes()
        source = self.write_source(payload)
        before = sorted(self.source_dir.iterdir())
        PackageValidationStage().execute(
            StageInput(request=make_request(source), workspace=self.workspace, artifacts={})
        )
        self.assertEqual(source.read_bytes(), payload)
        self.assertEqual(sorted(self.source_dir.iterdir()), before)


class ManifestPreparationStageTests(PackageTestCase):
    """The manifest stage reparses through the existing parser only."""

    def _stage_input(self) -> StageInput:
        return StageInput(
            request=make_request(self.write_source()),
            workspace=self.workspace,
            artifacts={
                PREPARED_MANIFEST_ARTIFACT: StageArtifact(
                    relative_path=PREPARED_MANIFEST_NAME,
                    content_type="application/json",
                )
            },
        )

    def test_consumes_artifact_and_emits_metadata(self) -> None:
        (self.workspace / PREPARED_MANIFEST_NAME).write_bytes(
            json.dumps(manifest_dict(), separators=(",", ":")).encode("utf-8")
        )
        result = ManifestPreparationStage().execute(self._stage_input())
        self.assertEqual(dict(result.artifacts), {})
        self.assertEqual(
            dict(result.metadata),
            {
                "manifest_schema": "coin-analyzer.capture-package",
                "manifest_package_version": "1.0",
                "manifest_coin_count": 1,
            },
        )

    def test_missing_upstream_artifact_is_contract_error(self) -> None:
        stage_input = StageInput(
            request=make_request(self.write_source()),
            workspace=self.workspace,
            artifacts={},
        )
        with self.assertRaises(StageContractError) as ctx:
            ManifestPreparationStage().execute(stage_input)
        self.assertEqual(ctx.exception.stage_id, MANIFEST_PREPARATION_STAGE_ID)

    def test_unreadable_declared_artifact_is_contract_error(self) -> None:
        with self.assertRaises(StageContractError) as ctx:
            ManifestPreparationStage().execute(self._stage_input())
        self.assertEqual(ctx.exception.stage_id, MANIFEST_PREPARATION_STAGE_ID)
        self.assertIsInstance(ctx.exception.__cause__, OSError)

    def test_corrupt_artifact_surfaces_parser_error(self) -> None:
        (self.workspace / PREPARED_MANIFEST_NAME).write_bytes(b"not json")
        with self.assertRaises(InvalidManifest):
            ManifestPreparationStage().execute(self._stage_input())


class ReferencePipelineEngineTests(PackageTestCase):
    """End-to-end: reference pipeline under the Unit 4/6 engine."""

    def test_factory_order_is_explicit_and_deterministic(self) -> None:
        self.assertEqual(
            build_reference_pipeline().stage_ids,
            (PACKAGE_VALIDATION_STAGE_ID, MANIFEST_PREPARATION_STAGE_ID),
        )

    def test_duplicate_stage_ids_rejected_at_construction(self) -> None:
        with self.assertRaises(PipelineConfigurationError):
            ProcessingPipeline(
                stages=(PackageValidationStage(), PackageValidationStage())
            )

    def test_trivial_stages_prove_the_design(self) -> None:
        seen: list = []
        pipeline = ProcessingPipeline(
            stages=(PassThroughStage("stub-a", seen), PassThroughStage("stub-b", seen))
        )
        spy = DelegateSpy()
        ImportWorkflow(pipeline).execute(
            make_request(self.write_source()), self.workspace, transaction=spy
        )
        self.assertEqual([item.request.source.name for item in seen], [SOURCE_NAME] * 2)
        self.assertEqual(len(spy.calls), 1)
        self.assertEqual(spy.calls[0].files, ())

    def test_full_pipeline_hands_off_exactly_once(self) -> None:
        source = self.write_source()
        spy = DelegateSpy()
        result = ImportWorkflow(build_reference_pipeline()).execute(
            make_request(source), self.workspace, transaction=spy
        )
        self.assertIs(result, spy.result)
        self.assertEqual(len(spy.calls), 1)
        prepared = spy.calls[0]
        self.assertEqual(
            [(f.relative_path, f.sha256) for f in prepared.files],
            [(PREPARED_MANIFEST_NAME, None)],
        )
        expected_size = (self.workspace / PREPARED_MANIFEST_NAME).stat().st_size
        self.assertEqual(prepared.files[0].expected_size, expected_size)
        self.assertEqual(
            dict(prepared.metadata),
            {
                "package_basename": SOURCE_NAME,
                "package_sha256": sha256(source.read_bytes()).hexdigest(),
                "package_byte_length": source.stat().st_size,
                "manifest_schema": "coin-analyzer.capture-package",
                "manifest_package_version": "1.0",
                "manifest_coin_count": 1,
            },
        )

    def test_full_pipeline_event_order(self) -> None:
        bus = ImportEventBus()
        ImportWorkflow(build_reference_pipeline(), event_bus=bus).execute(
            make_request(self.write_source()), self.workspace, transaction=DelegateSpy()
        )
        self.assertEqual(
            [event.event_type for event in bus.events],
            [
                EventType.PIPELINE_STARTED,
                EventType.STAGE_STARTED,
                EventType.STAGE_COMPLETED,
                EventType.STAGE_STARTED,
                EventType.STAGE_COMPLETED,
                EventType.PIPELINE_COMPLETED,
            ],
        )

    def test_stage_failure_commits_nothing(self) -> None:
        bus = ImportEventBus()
        spy = DelegateSpy()
        with self.assertRaises(StageExecutionError) as ctx:
            ImportWorkflow(build_reference_pipeline(), event_bus=bus).execute(
                make_request(self.write_source(b"definitely not a zip")),
                self.workspace,
                transaction=spy,
            )
        self.assertEqual(ctx.exception.stage_id, PACKAGE_VALIDATION_STAGE_ID)
        self.assertIsInstance(ctx.exception.__cause__, CaptureImportError)
        self.assertEqual(spy.calls, [])
        self.assertEqual(len(bus.by_type(EventType.STAGE_FAILED)), 1)
        self.assertEqual(bus.by_type(EventType.PIPELINE_COMPLETED), ())
        self.assertEqual(bus.by_type(EventType.PIPELINE_CANCELLED), ())

    def test_cancellation_between_stages_commits_nothing(self) -> None:
        bus = ImportEventBus()
        spy = DelegateSpy()
        # Two stages + transaction: pre-stage-2 is the 3rd check.
        cancel = CancelAfter(3)
        with self.assertRaises(WorkflowCancelledError):
            ImportWorkflow(
                build_reference_pipeline(), event_bus=bus, is_cancelled=cancel
            ).execute(
                make_request(self.write_source()), self.workspace, transaction=spy
            )
        self.assertEqual(spy.calls, [])
        self.assertEqual(len(bus.by_type(EventType.PIPELINE_CANCELLED)), 1)
        self.assertEqual(bus.by_type(EventType.PIPELINE_COMPLETED), ())

    def test_cancellation_pre_handoff_commits_nothing(self) -> None:
        bus = ImportEventBus()
        spy = DelegateSpy()
        # Two stages + transaction: pre-handoff is the 6th check.
        cancel = CancelAfter(6)
        with self.assertRaises(WorkflowCancelledError):
            ImportWorkflow(
                build_reference_pipeline(), event_bus=bus, is_cancelled=cancel
            ).execute(
                make_request(self.write_source()), self.workspace, transaction=spy
            )
        self.assertEqual(spy.calls, [])
        self.assertEqual(len(bus.by_type(EventType.PIPELINE_CANCELLED)), 1)
        self.assertEqual(bus.by_type(EventType.PIPELINE_COMPLETED), ())


class _StagedSentinel:
    pass


class FakeCoordinator:
    """Records prepare/commit invocations; no durable side effects."""

    def __init__(self, *, prepare_error: Exception | None = None) -> None:
        self.prepare_calls: list = []
        self.commit_calls: list = []
        self.staged = _StagedSentinel()
        self.result = object()
        self._prepare_error = prepare_error

    def prepare(self, source):
        self.prepare_calls.append(source)
        if self._prepare_error is not None:
            raise self._prepare_error
        return self.staged

    def commit(self, staged, decisions):
        self.commit_calls.append((staged, decisions))
        return self.result


class WorkflowAdapterTests(PackageTestCase):
    """The adapter is a stateless one-way translation onto the seam."""

    def _prepared(self, source: Path) -> PreparedImport:
        return PreparedImport(
            request=make_request(source),
            files=(PreparedFile(relative_path=PREPARED_MANIFEST_NAME, expected_size=10),),
            metadata={"manifest_coin_count": 1},
        )

    def _decisions(self) -> PreviewDecisionSet:
        return PreviewDecisionSet(preview_fingerprint="ab" * 32, decisions=())

    def test_adapter_drives_existing_seam(self) -> None:
        coordinator = FakeCoordinator()
        prepared = self._prepared(self.write_source())
        decisions = self._decisions()
        result = commit_prepared_import(prepared, decisions, coordinator=coordinator)
        self.assertIs(result, coordinator.result)
        self.assertEqual(coordinator.prepare_calls, [prepared.request.source])
        self.assertEqual(coordinator.commit_calls, [(coordinator.staged, decisions)])

    def test_adapter_rejects_wrong_types(self) -> None:
        coordinator = FakeCoordinator()
        with self.assertRaises(TypeError):
            commit_prepared_import(object(), self._decisions(), coordinator=coordinator)
        with self.assertRaises(TypeError):
            commit_prepared_import(
                self._prepared(self.write_source()), object(), coordinator=coordinator
            )
        self.assertEqual(coordinator.prepare_calls, [])

    def test_adapter_rejects_invalid_prepared_import(self) -> None:
        invalid = PreparedImport(
            request=make_request(self.write_source()),
            files=["not-a-prepared-file"],
            metadata={},
        )
        with self.assertRaises(ValueError):
            commit_prepared_import(invalid, self._decisions(), coordinator=FakeCoordinator())

    def test_adapter_propagates_prepare_error_unwrapped(self) -> None:
        error = PackageChanged("digest mismatch")
        coordinator = FakeCoordinator(prepare_error=error)
        with self.assertRaises(PackageChanged) as ctx:
            commit_prepared_import(
                self._prepared(self.write_source()),
                self._decisions(),
                coordinator=coordinator,
            )
        self.assertIs(ctx.exception, error)
        self.assertEqual(coordinator.commit_calls, [])

    def test_adapter_propagates_commit_error_unwrapped(self) -> None:
        error = RecoveryRequired("journal interrupted")

        class CommitFailingCoordinator(FakeCoordinator):
            def commit(self, staged, decisions):
                raise error

        with self.assertRaises(RecoveryRequired) as ctx:
            commit_prepared_import(
                self._prepared(self.write_source()),
                self._decisions(),
                coordinator=CommitFailingCoordinator(),
            )
        self.assertIs(ctx.exception, error)

    def test_adapter_does_not_inspect_artifact_contents(self) -> None:
        # The declared file does not exist anywhere; translation must not care.
        coordinator = FakeCoordinator()
        result = commit_prepared_import(
            self._prepared(self.write_source()), self._decisions(), coordinator=coordinator
        )
        self.assertIs(result, coordinator.result)

    def test_adapter_is_stateless_across_calls(self) -> None:
        coordinator = FakeCoordinator()
        prepared = self._prepared(self.write_source())
        commit_prepared_import(prepared, self._decisions(), coordinator=coordinator)
        commit_prepared_import(prepared, self._decisions(), coordinator=coordinator)
        self.assertEqual(len(coordinator.prepare_calls), 2)
        self.assertEqual(len(coordinator.commit_calls), 2)


def _resolve_imports(tree: ast.AST, package: tuple[str, ...]) -> set[str]:
    """Resolve every import in an AST to absolute dotted names.

    Walks the whole tree — including imports nested in functions, classes,
    and try blocks — excluding only ``if TYPE_CHECKING:`` bodies (their
    imports are annotation-only, never executed at runtime).  Fails closed
    with ``ValueError`` on any import form it cannot resolve.
    """
    names: set[str] = set()

    def resolve_from(node: ast.ImportFrom) -> tuple[str, ...]:
        if node.level == 0:
            if node.module is None:
                raise ValueError("unresolvable import form: ImportFrom without module")
            return (node.module,)
        remaining = len(package) - (node.level - 1)
        if remaining < 1:
            raise ValueError(f"relative import escapes package: level {node.level}")
        base = package[:remaining]
        if node.module is not None:
            return (".".join([*base, node.module]),)
        resolved = []
        for alias in node.names:
            if alias.name == "*":
                raise ValueError("unresolvable import form: 'from . import *'")
            resolved.append(".".join([*base, alias.name]))
        return tuple(resolved)

    def visit(node: ast.AST) -> None:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
            return
        if isinstance(node, ast.ImportFrom):
            names.update(resolve_from(node))
            return
        if isinstance(node, ast.If):
            test = node.test
            if (
                isinstance(test, ast.Name)
                and test.id == "TYPE_CHECKING"
                or isinstance(test, ast.Attribute)
                and test.attr == "TYPE_CHECKING"
            ):
                for statement in node.orelse:
                    visit(statement)
                return
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return names


def _runtime_import_modules(module: object) -> set[str]:
    """Absolute runtime imports of a module (TYPE_CHECKING excluded)."""
    package = tuple((module.__package__ or "").split("."))
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    return _resolve_imports(tree, package)


class DurabilityBoundaryAuditTests(unittest.TestCase):
    """Allowlist-based structural proof (hardened per Unit 7 review M1).

    Durability stays reachable exclusively through the Unit 6 delegate:
    each workflow module's runtime import surface must match its explicit
    allowlist exactly — any new import fails the audit until reviewed.
    """

    def _assert_runtime_imports(
        self, module: object, *, stdlib: set[str], package: set[str]
    ) -> None:
        resolved = _runtime_import_modules(module)
        unexpected = set()
        for name in resolved:
            if name.startswith("capture_import"):
                if name not in package:
                    unexpected.add(name)
            elif name.split(".", 1)[0] not in stdlib:
                unexpected.add(name)
        self.assertEqual(
            unexpected, set(), f"non-allowlisted imports in {module.__name__}"
        )
        drift = {name for name in package if name not in resolved}
        self.assertEqual(
            drift, set(), f"allowlisted imports missing from {module.__name__}"
        )

    def test_stage_module_imports_match_allowlist(self) -> None:
        self._assert_runtime_imports(
            workflow_stages,
            stdlib={"__future__", "json", "os", "hashlib", "pathlib", "typing"},
            package={
                "capture_import._filesystem",
                "capture_import.errors",
                "capture_import.manifest",
                "capture_import.package",
                "capture_import.workflow_models",
                "capture_import.workflow_pipeline",
            },
        )

    def test_adapter_module_imports_match_allowlist(self) -> None:
        from capture_import import workflow_adapter

        self._assert_runtime_imports(
            workflow_adapter,
            stdlib={"__future__", "typing"},
            package={
                "capture_import.coordinator",
                "capture_import.preview",
                "capture_import.workflow_models",
            },
        )

    def test_engine_module_imports_match_allowlist(self) -> None:
        from capture_import import workflow_execution

        self._assert_runtime_imports(
            workflow_execution,
            stdlib={
                "PIL",
                "__future__",
                "dataclasses",
                "hashlib",
                "io",
                "os",
                "pathlib",
                "typing",
            },
            package={
                "capture_import._filesystem",
                "capture_import.events",
                "capture_import.image_validation",
                "capture_import.limits",
                "capture_import.workflow_models",
                "capture_import.workflow_pipeline",
            },
        )

    def test_type_checking_imports_are_excluded(self) -> None:
        # Annotation-only imports must not count as runtime surface:
        # workflow_stages → capture_import.models, workflow_adapter →
        # capture_import.transaction live under TYPE_CHECKING exclusively.
        from capture_import import workflow_adapter

        self.assertNotIn(
            "capture_import.models", _runtime_import_modules(workflow_stages)
        )
        self.assertNotIn(
            "capture_import.transaction", _runtime_import_modules(workflow_adapter)
        )

    def test_audit_traverses_nested_imports(self) -> None:
        tree = ast.parse("def f():\n    from . import coordinator\n")
        self.assertEqual(
            _resolve_imports(tree, ("capture_import",)),
            {"capture_import.coordinator"},
        )
        tree = ast.parse(
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    from . import transaction\n"
        )
        self.assertEqual(_resolve_imports(tree, ("capture_import",)), {"typing"})

    def test_audit_includes_non_type_checking_if_bodies(self) -> None:
        # A guard regression that skipped every `ast.If` body would let a
        # durability import hide behind a runtime condition.
        tree = ast.parse("if flag:\n    from . import journal\n")
        self.assertEqual(
            _resolve_imports(tree, ("capture_import",)),
            {"capture_import.journal"},
        )

    def test_audit_traverses_type_checking_orelse(self) -> None:
        tree = ast.parse(
            "if TYPE_CHECKING:\n"
            "    pass\n"
            "else:\n"
            "    from . import journal\n"
        )
        self.assertEqual(
            _resolve_imports(tree, ("capture_import",)),
            {"capture_import.journal"},
        )

    def test_audit_excludes_attribute_type_checking_form(self) -> None:
        tree = ast.parse(
            "import typing\n"
            "if typing.TYPE_CHECKING:\n"
            "    from . import transaction\n"
        )
        self.assertEqual(_resolve_imports(tree, ("capture_import",)), {"typing"})

    def test_audit_fails_closed_on_unrecognized_forms(self) -> None:
        with self.assertRaises(ValueError):
            _resolve_imports(ast.parse("from . import *\n"), ("capture_import",))
        with self.assertRaises(ValueError):
            _resolve_imports(ast.parse("from ..sibling import x\n"), ("capture_import",))
        # ImportFrom with neither module nor level (not parseable source).
        node = ast.ImportFrom(module=None, names=[ast.alias(name="x")], level=0)
        with self.assertRaises(ValueError):
            _resolve_imports(ast.Module(body=[node], type_ignores=[]), ("capture_import",))
        # Escape from a deeper package must raise, not mis-resolve.
        with self.assertRaises(ValueError):
            _resolve_imports(ast.parse("from ....x import y\n"), ("a", "b"))


if __name__ == "__main__":
    unittest.main()
