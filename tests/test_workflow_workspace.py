"""Focused tests for Sprint 7 Unit 5: workflow workspace lifecycle."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from capture_import.workflow_models import (
    ImportConfiguration,
    ImportRequest,
    StageInput,
    StageResult,
)
from capture_import.workflow_execution import ImportWorkflow
from capture_import.workflow_pipeline import (
    ImportWorkflowError,
    ProcessingPipeline,
    StageExecutionError,
    WorkflowCancelledError,
)
from capture_import.workflow_workspace import (
    WorkflowWorkspace,
    WorkspaceCleanupError,
    WorkspaceClosedError,
    WorkspaceCreationError,
    WorkspacePathError,
)


def make_request() -> ImportRequest:
    return ImportRequest(
        source=Path(tempfile.gettempdir()),
        collection_id="collection-1",
        configuration=ImportConfiguration(),
    )


class WritingStage:
    """Writes one file into the workspace it receives."""

    def __init__(self, stage_id: str, relative_name: str, payload: bytes = b"x") -> None:
        self._stage_id = stage_id
        self._relative_name = relative_name
        self._payload = payload

    @property
    def stage_id(self) -> str:
        return self._stage_id

    def execute(self, stage_input: StageInput) -> StageResult:
        target = stage_input.workspace / self._relative_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self._payload)
        return StageResult(artifacts={}, metadata={})


class RaisingStage:
    def __init__(self, stage_id: str, exc: Exception) -> None:
        self._stage_id = stage_id
        self._exc = exc

    @property
    def stage_id(self) -> str:
        return self._stage_id

    def execute(self, stage_input: StageInput) -> StageResult:
        raise self._exc


class FlipCancellationStage:
    def __init__(self, stage_id: str, flag: dict) -> None:
        self._stage_id = stage_id
        self._flag = flag

    @property
    def stage_id(self) -> str:
        return self._stage_id

    def execute(self, stage_input: StageInput) -> StageResult:
        self._flag["cancelled"] = True
        return StageResult(artifacts={}, metadata={})


class WorkspaceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "trusted-root"
        # Note: root deliberately does not exist yet; creation is verified.

    def make_workspace(self, **kwargs) -> WorkflowWorkspace:
        self.root.mkdir(parents=True, exist_ok=True)
        return WorkflowWorkspace(self.root, **kwargs)


class CreationTests(WorkspaceTestCase):
    def test_workspace_is_created_beneath_trusted_root(self) -> None:
        workspace = self.make_workspace()
        self.assertTrue(workspace.path.is_dir())
        self.assertEqual(workspace.path.parent, self.root)
        self.assertEqual(workspace.path.name, f"workflow-{workspace.workspace_id}")
        workspace.close()

    def test_missing_root_is_created_plain_verified(self) -> None:
        # Root does not exist; creation must establish it.
        workspace = WorkflowWorkspace(self.root)
        self.assertTrue(self.root.is_dir())
        self.assertTrue(workspace.path.is_dir())
        workspace.close()

    def test_unique_workspace_identities(self) -> None:
        first = self.make_workspace()
        second = self.make_workspace()
        self.assertNotEqual(first.workspace_id, second.workspace_id)
        self.assertNotEqual(first.path, second.path)
        first.close()
        second.close()

    def test_relative_root_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute"):
            WorkflowWorkspace(Path("relative/root"))

    def test_invalid_max_entries_is_rejected(self) -> None:
        for bad in (0, -1, True, "many"):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "max_entries"):
                    WorkflowWorkspace(self.root, max_entries=bad)  # type: ignore[arg-type]

    def test_malformed_token_is_rejected(self) -> None:
        with self.assertRaises(WorkspaceCreationError):
            WorkflowWorkspace(self.root, token_factory=lambda: "not-a-token")

    def test_token_collision_preserves_existing_directory(self) -> None:
        self.root.mkdir(parents=True)
        token = "a" * 16
        preexisting = self.root / f"workflow-{token}"
        preexisting.mkdir()
        marker = preexisting / "keep.txt"
        marker.write_text("precious", encoding="utf-8")
        with self.assertRaises(WorkspaceCreationError) as ctx:
            WorkflowWorkspace(self.root, token_factory=lambda: token)
        self.assertIsInstance(ctx.exception.__cause__, FileExistsError)
        # Ownership discipline: the pre-existing directory is not touched.
        self.assertEqual(marker.read_text(encoding="utf-8"), "precious")

    def test_partial_creation_failure_cleans_owned_directory(self) -> None:
        # Identity capture fails after mkdir; the just-created directory must
        # be removed and the creation error chained from the OSError.
        with mock.patch(
            "capture_import.workflow_workspace.path_object_identity",
            side_effect=[(1, 1), OSError("identity boom")],
        ):
            with self.assertRaises(WorkspaceCreationError) as ctx:
                WorkflowWorkspace(self.root, token_factory=lambda: "b" * 16)
        self.assertIsInstance(ctx.exception.__cause__, OSError)
        self.assertFalse((self.root / f"workflow-{'b' * 16}").exists())


class AllocationTests(WorkspaceTestCase):
    def test_allocate_returns_contained_path_and_creates_parents(self) -> None:
        with self.make_workspace() as workspace:
            candidate = workspace.allocate_path("stage/output/result.bin")
            self.assertTrue(str(candidate).startswith(str(workspace.path) + os.sep))
            self.assertTrue(candidate.parent.is_dir())
            self.assertFalse(candidate.exists())  # allocation does not create the file

    def test_absolute_paths_are_rejected(self) -> None:
        with self.make_workspace() as workspace:
            for name in ("/etc/passwd", "C:/escape.bin", "C:\\escape.bin"):
                with self.subTest(name=name):
                    with self.assertRaises(WorkspacePathError):
                        workspace.allocate_path(name)

    def test_parent_traversal_is_rejected(self) -> None:
        with self.make_workspace() as workspace:
            for name in ("../escape", "a/../../b", ".."):
                with self.subTest(name=name):
                    with self.assertRaises(WorkspacePathError):
                        workspace.allocate_path(name)

    def test_empty_and_malformed_names_are_rejected(self) -> None:
        with self.make_workspace() as workspace:
            for name in ("", ".", "a//b", "a/", "a\\b", "a/./b", "name.", "name "):
                with self.subTest(name=name):
                    with self.assertRaises(WorkspacePathError):
                        workspace.allocate_path(name)

    def test_windows_reserved_names_are_rejected(self) -> None:
        with self.make_workspace() as workspace:
            with self.assertRaises(WorkspacePathError):
                workspace.allocate_path("CON.bin")

    def test_path_error_chains_value_error(self) -> None:
        with self.make_workspace() as workspace:
            with self.assertRaises(WorkspacePathError) as ctx:
                workspace.allocate_path("../escape")
            self.assertIsInstance(ctx.exception.__cause__, ValueError)

    def test_duplicate_allocation_collides(self) -> None:
        with self.make_workspace() as workspace:
            workspace.allocate_path("out.bin")
            with self.assertRaisesRegex(WorkspacePathError, "collides"):
                workspace.allocate_path("out.bin")

    def test_case_fold_alias_collision_matches_platform(self) -> None:
        with self.make_workspace() as workspace:
            workspace.allocate_path("Out.bin")
            if os.path.normcase("Out.bin") == os.path.normcase("out.bin"):
                # Windows-style case-fold: the alias must not collide silently.
                with self.assertRaisesRegex(WorkspacePathError, "collides"):
                    workspace.allocate_path("out.bin")
            else:
                # POSIX: distinct names, both allocatable.
                workspace.allocate_path("out.bin")

    def test_distinct_names_do_not_collide(self) -> None:
        with self.make_workspace() as workspace:
            workspace.allocate_path("a.bin")
            workspace.allocate_path("b.bin")
            workspace.allocate_path("a/b.bin")  # same basename, different directory

    def test_allocation_through_planted_link_is_rejected(self) -> None:
        with self.make_workspace() as workspace:
            outside = Path(self._tmp.name) / "outside"
            outside.mkdir()
            link = workspace.path / "linkdir"
            try:
                os.symlink(outside, link, target_is_directory=True)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"symlink creation unavailable on this platform: {error}")
            try:
                with self.assertRaises(WorkspacePathError):
                    workspace.allocate_path("linkdir/escape.bin")
            finally:
                link.unlink()


class CleanupTests(WorkspaceTestCase):
    def test_empty_workspace_cleanup(self) -> None:
        workspace = self.make_workspace()
        path = workspace.path
        workspace.close()
        self.assertFalse(path.exists())
        self.assertTrue(workspace.is_closed)

    def test_cleanup_after_files_and_nested_directories(self) -> None:
        with self.make_workspace() as workspace:
            deep = workspace.allocate_path("a/b/c.bin")
            deep.write_bytes(b"deep")
            shallow = workspace.allocate_path("a/d.bin")
            shallow.write_bytes(b"shallow")
            top = workspace.allocate_path("top.bin")
            top.write_bytes(b"top")
            path = workspace.path
        self.assertFalse(path.exists())

    def test_cleanup_removes_read_only_files(self) -> None:
        with self.make_workspace() as workspace:
            target = workspace.allocate_path("locked.bin")
            target.write_bytes(b"ro")
            target.chmod(stat.S_IREAD)
            path = workspace.path
        self.assertFalse(path.exists())

    def test_cleanup_alias_cleanup_method(self) -> None:
        workspace = self.make_workspace()
        path = workspace.path
        workspace.cleanup()
        self.assertFalse(path.exists())

    def test_repeated_cleanup_is_idempotent(self) -> None:
        workspace = self.make_workspace()
        workspace.close()
        workspace.close()
        workspace.cleanup()
        self.assertTrue(workspace.is_closed)

    def test_cleanup_on_success_via_context_manager(self) -> None:
        with self.make_workspace() as workspace:
            path = workspace.path
            workspace.allocate_path("done.bin").write_bytes(b"ok")
        self.assertFalse(path.exists())

    def test_cleanup_on_ordinary_exception(self) -> None:
        with self.assertRaises(RuntimeError):
            with self.make_workspace() as workspace:
                path = workspace.path
                workspace.allocate_path("partial.bin").write_bytes(b"x")
                raise RuntimeError("body failure")
        self.assertFalse(path.exists())

    def test_root_is_never_deleted(self) -> None:
        sentinel = self.root / "sentinel.txt"
        self.root.mkdir(parents=True)
        sentinel.write_text("keep", encoding="utf-8")
        with self.make_workspace() as workspace:
            workspace.allocate_path("work.bin").write_bytes(b"x")
        self.assertTrue(self.root.is_dir())
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_caller_configuration_is_not_mutated(self) -> None:
        self.root.mkdir(parents=True)
        root_before = self.root
        workspace = WorkflowWorkspace(root_before)
        workspace.close()
        self.assertEqual(self.root, root_before)
        self.assertTrue(self.root.is_dir())

    def test_source_files_outside_workspace_remain_immutable(self) -> None:
        source_dir = Path(self._tmp.name) / "source"
        source_dir.mkdir()
        source = source_dir / "package.bin"
        source.write_bytes(b"source-material")
        with self.make_workspace() as workspace:
            workspace.allocate_path("copy.bin").write_bytes(b"derived")
        self.assertEqual(source.read_bytes(), b"source-material")


class CleanupFailureTests(WorkspaceTestCase):
    def test_close_failure_raises_cleanup_error_chained(self) -> None:
        workspace = self.make_workspace(max_entries=1)
        first = workspace.allocate_path("one.bin")
        first.write_bytes(b"1")
        second = workspace.allocate_path("two.bin")
        second.write_bytes(b"2")
        with self.assertRaises(WorkspaceCleanupError) as ctx:
            workspace.close()
        self.assertIsInstance(ctx.exception.__cause__, OSError)
        self.assertIn("bound", str(ctx.exception.__cause__))
        self.assertFalse(workspace.is_closed)

    def test_close_failure_leaves_instance_open_for_retry(self) -> None:
        workspace = self.make_workspace(max_entries=1)
        workspace.allocate_path("one.bin").write_bytes(b"1")
        extra = workspace.allocate_path("two.bin")
        extra.write_bytes(b"2")
        with self.assertRaises(WorkspaceCleanupError):
            workspace.close()
        survivors = list(workspace.path.iterdir())
        self.assertEqual(len(survivors), 1)
        survivors[0].unlink()  # caller removes whichever entry exceeded the bound
        workspace.close()
        self.assertTrue(workspace.is_closed)
        self.assertFalse(workspace.path.exists())

    def test_exit_without_primary_exception_propagates_cleanup_error(self) -> None:
        workspace = self.make_workspace(max_entries=1)
        with self.assertRaises(WorkspaceCleanupError):
            with workspace:
                workspace.allocate_path("one.bin").write_bytes(b"1")
                workspace.allocate_path("two.bin").write_bytes(b"2")

    def test_exit_with_primary_exception_preserves_it_and_attaches_cleanup(self) -> None:
        workspace = self.make_workspace(max_entries=1)
        with self.assertRaises(ValueError) as ctx:
            with workspace:
                workspace.allocate_path("one.bin").write_bytes(b"1")
                workspace.allocate_path("two.bin").write_bytes(b"2")
                raise ValueError("primary failure")
        self.assertEqual(str(ctx.exception), "primary failure")
        notes = getattr(ctx.exception, "__notes__", [])
        self.assertTrue(
            any("cleanup" in note for note in notes),
            f"cleanup failure must be attached as a note, got {notes!r}",
        )

    def test_cleanup_refuses_link_inside_workspace(self) -> None:
        workspace = self.make_workspace()
        outside = Path(self._tmp.name) / "outside"
        outside.mkdir()
        precious = outside / "precious.txt"
        precious.write_text("untouched", encoding="utf-8")
        try:
            os.symlink(outside, workspace.path / "escape-link", target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"symlink creation unavailable on this platform: {error}")
        with self.assertRaises(WorkspaceCleanupError):
            workspace.close()
        # Fail-closed: the link is not traversed and the target is untouched.
        self.assertEqual(precious.read_text(encoding="utf-8"), "untouched")
        self.assertTrue(workspace.path.exists())


class OwnershipTests(WorkspaceTestCase):
    def test_cleanup_rejects_substituted_directory_identity(self) -> None:
        workspace = self.make_workspace()
        original = workspace.path
        impostor = self.root / "impostor"
        impostor.mkdir()
        original.rmdir()  # remove the genuine owned directory (it is empty)
        impostor.rename(original)
        with self.assertRaises(WorkspaceCleanupError):
            workspace.close()
        # The impostor directory must NOT be deleted by this instance.
        self.assertTrue(original.exists())
        self.assertFalse(workspace.is_closed)

    def test_cleanup_rejects_missing_owned_directory(self) -> None:
        workspace = self.make_workspace()
        shutil.rmtree(workspace.path)
        with self.assertRaises(WorkspaceCleanupError):
            workspace.close()
        self.assertFalse(workspace.is_closed)

    def test_workspace_errors_belong_to_workflow_hierarchy(self) -> None:
        for error in (
            WorkspaceCreationError("x"),
            WorkspacePathError("x"),
            WorkspaceCleanupError("x"),
            WorkspaceClosedError("x"),
        ):
            with self.subTest(error=type(error).__name__):
                self.assertIsInstance(error, ImportWorkflowError)


class ClosedStateTests(WorkspaceTestCase):
    def test_allocate_after_close_raises(self) -> None:
        workspace = self.make_workspace()
        workspace.close()
        with self.assertRaises(WorkspaceClosedError):
            workspace.allocate_path("late.bin")

    def test_enter_after_close_raises(self) -> None:
        workspace = self.make_workspace()
        workspace.close()
        with self.assertRaises(WorkspaceClosedError):
            with workspace:
                pass

    def test_nested_entry_is_rejected(self) -> None:
        with self.make_workspace() as workspace:
            with self.assertRaises(WorkspaceClosedError):
                workspace.__enter__()

    def test_path_remains_inspectable_after_close(self) -> None:
        workspace = self.make_workspace()
        path = workspace.path
        workspace.close()
        self.assertEqual(workspace.path, path)
        self.assertTrue(workspace.is_closed)


class WorkflowIntegrationTests(WorkspaceTestCase):
    def test_cleanup_on_workflow_success(self) -> None:
        with self.make_workspace() as workspace:
            pipeline = ProcessingPipeline(
                stages=(WritingStage("writer", "out/result.bin"),)
            )
            outcome = ImportWorkflow(pipeline).execute(make_request(), workspace.path)
            self.assertTrue((workspace.path / "out" / "result.bin").exists())
            self.assertEqual(outcome.metadata, {})
            path = workspace.path
        self.assertFalse(path.exists())

    def test_cleanup_on_stage_failure(self) -> None:
        with self.assertRaises(StageExecutionError):
            with self.make_workspace() as workspace:
                path = workspace.path
                pipeline = ProcessingPipeline(
                    stages=(
                        WritingStage("writer", "partial.bin"),
                        RaisingStage("bad", ValueError("boom")),
                    )
                )
                ImportWorkflow(pipeline).execute(make_request(), workspace.path)
        self.assertFalse(path.exists())

    def test_cleanup_on_workflow_cancellation(self) -> None:
        flag = {"cancelled": False}
        with self.assertRaises(WorkflowCancelledError):
            with self.make_workspace() as workspace:
                path = workspace.path
                pipeline = ProcessingPipeline(
                    stages=(
                        WritingStage("writer", "partial.bin"),
                        FlipCancellationStage("flip", flag),
                    )
                )
                workflow = ImportWorkflow(
                    pipeline, is_cancelled=lambda: flag["cancelled"]
                )
                workflow.execute(make_request(), workspace.path)
        self.assertFalse(path.exists())

    def test_stage_writes_stay_contained_in_workspace(self) -> None:
        with self.make_workspace() as workspace:
            pipeline = ProcessingPipeline(
                stages=(WritingStage("writer", "nested/deep.bin", b"payload"),)
            )
            ImportWorkflow(pipeline).execute(make_request(), workspace.path)
            written = workspace.path / "nested" / "deep.bin"
            self.assertEqual(written.read_bytes(), b"payload")
            self.assertTrue(
                str(written).startswith(str(workspace.path) + os.sep)
            )


class TildeHardeningTests(WorkspaceTestCase):
    """Windows 8.3 namespace hardening: '~' is rejected in every component."""

    def test_short_name_alias_basename_is_rejected(self) -> None:
        with self.make_workspace() as workspace:
            with self.assertRaisesRegex(WorkspacePathError, "8.3"):
                workspace.allocate_path("LONGFI~1.BIN")

    def test_tilde_in_parent_component_is_rejected(self) -> None:
        with self.make_workspace() as workspace:
            with self.assertRaisesRegex(WorkspacePathError, "8.3"):
                workspace.allocate_path("parent~1/output.bin")

    def test_tilde_rejection_creates_no_parent_path(self) -> None:
        with self.make_workspace() as workspace:
            with self.assertRaises(WorkspacePathError):
                workspace.allocate_path("bad~1/sub/file.bin")
            # Rejection happened before any state mutation or directory creation.
            self.assertEqual(list(workspace.path.iterdir()), [])

    def test_normal_filename_remains_accepted(self) -> None:
        with self.make_workspace() as workspace:
            candidate = workspace.allocate_path("normal-file_name.bin")
            self.assertTrue(str(candidate).startswith(str(workspace.path) + os.sep))

    def test_demonstrated_short_name_collision_is_prevented(self) -> None:
        with self.make_workspace() as workspace:
            long_name = workspace.allocate_path("longfilenameoutput.bin")
            long_name.write_bytes(b"A")
            with self.assertRaises(WorkspacePathError):
                workspace.allocate_path("LONGFI~1.BIN")
            # The original entry was not overwritten through an alias.
            self.assertEqual(long_name.read_bytes(), b"A")


class BoundedEnumerationTests(WorkspaceTestCase):
    def test_exactly_max_entries_succeeds(self) -> None:
        workspace = self.make_workspace(max_entries=3)
        for index in range(3):
            workspace.allocate_path(f"file{index}.bin").write_bytes(b"x")
        workspace.close()
        self.assertTrue(workspace.is_closed)
        self.assertFalse(workspace.path.exists())

    def test_max_entries_plus_one_fails_closed(self) -> None:
        workspace = self.make_workspace(max_entries=3)
        for index in range(4):
            workspace.allocate_path(f"file{index}.bin").write_bytes(b"x")
        with self.assertRaises(WorkspaceCleanupError) as ctx:
            workspace.close()
        self.assertIn("bound", str(ctx.exception.__cause__))
        # The excessive tree is not reported as cleaned.
        self.assertFalse(workspace.is_closed)
        self.assertTrue(workspace.path.exists())

    def test_retry_after_reducing_below_bound(self) -> None:
        workspace = self.make_workspace(max_entries=3)
        paths = []
        for index in range(4):
            path = workspace.allocate_path(f"file{index}.bin")
            path.write_bytes(b"x")
            paths.append(path)
        with self.assertRaises(WorkspaceCleanupError):
            workspace.close()
        for path in paths:
            if path.exists():
                path.unlink()  # caller reduces the tree below the bound
        workspace.close()
        self.assertTrue(workspace.is_closed)
        self.assertFalse(workspace.path.exists())

    def test_enumeration_does_not_eagerly_consume_unbounded_iterator(self) -> None:
        workspace = self.make_workspace(max_entries=3)
        for index in range(10):
            workspace.allocate_path(f"file{index}.bin").write_bytes(b"x")
        real_iterdir = Path.iterdir
        pulled = {"count": 0}

        def counting_iterdir(self: Path):
            for entry in real_iterdir(self):
                pulled["count"] += 1
                yield entry

        with mock.patch.object(Path, "iterdir", counting_iterdir):
            with self.assertRaises(WorkspaceCleanupError):
                workspace.close()
        # Bounded enumeration pulls at most the remaining budget plus one
        # sentinel; unbounded materialization would have pulled all ten.
        self.assertLessEqual(pulled["count"], 4)


def _make_junction(test_case: unittest.TestCase, link: Path, target: Path) -> None:
    """Create a real Windows directory junction, or skip with a concrete reason."""

    if os.name != "nt":
        test_case.skipTest("directory junctions are a Windows-only mechanism")
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not link.exists():
        test_case.skipTest(
            f"junction creation failed (rc={result.returncode}): "
            f"{result.stdout.strip()} {result.stderr.strip()}"
        )


def _remove_junction(link: Path) -> None:
    """Remove only the junction itself (non-recursive, target-safe)."""

    try:
        os.rmdir(link)
    except OSError:
        pass


class JunctionTests(WorkspaceTestCase):
    """Real directory-junction coverage (no elevated privilege required)."""

    def test_allocation_through_junction_is_rejected(self) -> None:
        with self.make_workspace() as workspace:
            outside = Path(self._tmp.name) / "junction-target"
            outside.mkdir()
            sentinel = outside / "sentinel.txt"
            sentinel.write_text("external", encoding="utf-8")
            junction = workspace.path / "junction"
            _make_junction(self, junction, outside)
            self.addCleanup(_remove_junction, junction)
            with self.assertRaises(WorkspacePathError):
                workspace.allocate_path("junction/escape.bin")
            # Allocation did not traverse into the external target.
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "external")
            self.assertFalse((outside / "escape.bin").exists())
            # Remove the junction itself so __exit__ cleanup can proceed.
            _remove_junction(junction)

    def test_cleanup_refuses_junction_and_preserves_target(self) -> None:
        workspace = self.make_workspace()
        outside = Path(self._tmp.name) / "junction-target"
        outside.mkdir()
        sentinel = outside / "sentinel.txt"
        sentinel.write_text("external", encoding="utf-8")
        junction = workspace.path / "junction"
        _make_junction(self, junction, outside)
        self.addCleanup(_remove_junction, junction)
        with self.assertRaises(WorkspaceCleanupError):
            workspace.close()
        # Fail-closed: no recursion through the junction; target intact;
        # the owned workspace remains for inspection/retry.
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "external")
        self.assertTrue(workspace.path.exists())
        self.assertFalse(workspace.is_closed)
        # Retry after the caller removes the junction itself succeeds.
        _remove_junction(junction)
        workspace.close()
        self.assertTrue(workspace.is_closed)

    def test_workspace_substituted_by_junction_is_rejected(self) -> None:
        workspace = self.make_workspace()
        owned = workspace.path
        outside = Path(self._tmp.name) / "junction-target"
        outside.mkdir()
        sentinel = outside / "sentinel.txt"
        sentinel.write_text("external", encoding="utf-8")
        owned.rmdir()  # genuine owned directory is empty at this point
        _make_junction(self, owned, outside)
        self.addCleanup(_remove_junction, owned)
        with self.assertRaises(WorkspaceCleanupError):
            workspace.close()
        # Ownership verification rejected the substitution; the external
        # target was not deleted or modified.
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "external")
        self.assertTrue(outside.is_dir())
        self.assertFalse(workspace.is_closed)


if __name__ == "__main__":
    unittest.main()
