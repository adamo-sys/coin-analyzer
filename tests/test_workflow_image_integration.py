"""Focused Sprint 8 Unit 7E/7F routing, ownership, and composition tests."""

from __future__ import annotations

import json
import queue
import tempfile
import unittest
import zipfile
from contextlib import chdir
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from coin_collection import CoinCollection

from capture_import.desktop_import_pipeline_selection import ImportPipelineMode
from capture_import.decisions import ImportDecisionModel
from capture_import.enums import DuplicateDecision
from capture_import.errors import PackageChanged, RecoveryRequired
from capture_import.processed_snapshot import ProcessedSnapshotHandle
from capture_import.recovery import UnifiedPackageImportRecoveryService
from capture_import.schema3_runtime import Schema3PackageImportRecoveryService
from capture_import.snapshot import SnapshotHandle
from capture_import.workflow_adapter import commit_prepared_import
from capture_import.workflow_execution import ImportWorkflow
from capture_import.workflow_models import (
    ImportConfiguration,
    ImportRequest,
    PreparedArtifactSet,
    StageArtifact,
)
from capture_import.workflow_pipeline import (
    StageContractError,
    WorkflowCancelledError,
)
from capture_import.workflow_stages import (
    build_image_processing_pipeline,
    build_reference_pipeline,
)
from tests.capture_package_fixtures import package_bytes


class _CoordinatorSpy:
    def __init__(self, *, prepare_error=None, commit_error=None, claim=False):
        self.prepare_error = prepare_error
        self.commit_error = commit_error
        self.claim = claim
        self.prepare_calls = []
        self.commit_calls = []
        self.claimed = None
        self.staged = object()
        self.result = object()

    def prepare(self, source, **kwargs):
        self.prepare_calls.append((source, kwargs))
        if self.prepare_error is not None:
            raise self.prepare_error
        artifacts = kwargs.get("processed_artifacts")
        if self.claim and artifacts is not None:
            self.claimed = artifacts.claim()
        return self.staged

    def commit(self, staged, decisions):
        self.commit_calls.append((staged, decisions))
        if self.commit_error is not None:
            raise self.commit_error
        return self.result


class _RealCoordinatorSpy:
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.prepare_calls = []
        self.commit_calls = []

    def prepare(self, source, **kwargs):
        self.prepare_calls.append((source, kwargs))
        return self.coordinator.prepare(source, **kwargs)

    def commit(self, staged, decisions):
        self.commit_calls.append((staged, decisions))
        return self.coordinator.commit(staged, decisions)


class _CancelAt:
    def __init__(self, call_number: int) -> None:
        self.call_number = call_number
        self.calls = 0

    def __call__(self) -> bool:
        self.calls += 1
        return self.calls == self.call_number


class _ImmediateThread:
    instances = []

    def __init__(self, *, target, daemon):
        self.target = target
        self.daemon = daemon
        self.started = False
        self.__class__.instances.append(self)

    def start(self):
        self.started = True
        self.target()


class _WindowSpy:
    def __init__(self):
        self.after_calls = []

    def after(self, milliseconds, callback):
        self.after_calls.append((milliseconds, callback))


class _RecoverySpy:
    def __init__(self):
        self.calls = 0

    def reconcile_pending_imports(self):
        self.calls += 1


class _PreparedResult:
    def __init__(self):
        self.cancel_calls = 0

    def cancel(self):
        self.cancel_calls += 1


class _PreparationCoordinatorSpy:
    def __init__(self, *, fail_before_claim=False, fail_after_claim=False):
        self.fail_before_claim = fail_before_claim
        self.fail_after_claim = fail_after_claim
        self.prepare_calls = []
        self.claim_calls = 0
        self.artifacts = None
        self.result = _PreparedResult()

    def prepare(self, source, **kwargs):
        self.prepare_calls.append((source, kwargs))
        self.artifacts = kwargs["processed_artifacts"]
        if self.fail_before_claim:
            raise PackageChanged()
        claimed = self.artifacts.claim()
        self.claim_calls += 1
        claimed.close()
        if self.fail_after_claim:
            raise PackageChanged()
        return self.result


class WorkflowImageIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "test.ca-package"
        self.source.write_bytes(package_bytes())
        self.request = ImportRequest(
            source=self.source,
            collection_id="collection-1",
            configuration=ImportConfiguration(),
        )

    def workspace(self, name: str) -> Path:
        path = self.root / name
        path.mkdir()
        return path

    def test_pipeline_builders_have_distinct_fixed_orders(self) -> None:
        self.assertEqual(
            build_reference_pipeline().stage_ids,
            ("package-validation", "manifest-preparation"),
        )
        self.assertEqual(
            build_image_processing_pipeline().stage_ids,
            (
                "package-validation",
                "manifest-preparation",
                "image-normalization",
                "image-quality-scoring",
                "crop-detection",
                "obverse-reverse-pairing",
                "image-duplicate-detection",
            ),
        )

    def _run_with_spy(self, coordinator):
        decisions = self._empty_decisions()
        return ImportWorkflow(build_image_processing_pipeline()).execute(
            self.request,
            self.workspace("workspace"),
            transaction=lambda prepared: commit_prepared_import(
                prepared,
                decisions,
                coordinator=coordinator,
            ),
        )

    @staticmethod
    def _empty_decisions():
        from capture_import.preview import PreviewDecisionSet

        return PreviewDecisionSet(preview_fingerprint="ab" * 32, decisions=())

    def test_adapter_passes_exact_single_use_set_once(self) -> None:
        coordinator = _CoordinatorSpy(claim=True)
        result = self._run_with_spy(coordinator)
        self.assertIs(result, coordinator.result)
        self.assertEqual(len(coordinator.prepare_calls), 1)
        source, kwargs = coordinator.prepare_calls[0]
        artifacts = kwargs["processed_artifacts"]
        self.assertEqual(source, self.source)
        self.assertIsNotNone(coordinator.claimed)
        self.assertFalse(artifacts.is_active)
        self.assertEqual(len(coordinator.commit_calls), 1)
        coordinator.claimed.close()

    def test_rejection_before_claim_closes_workflow_owned_set(self) -> None:
        coordinator = _CoordinatorSpy(prepare_error=PackageChanged())
        with self.assertRaises(PackageChanged):
            self._run_with_spy(coordinator)
        artifacts = coordinator.prepare_calls[0][1]["processed_artifacts"]
        self.assertFalse(artifacts.is_active)

    def test_failure_after_claim_does_not_double_close_new_owner(self) -> None:
        coordinator = _CoordinatorSpy(
            claim=True,
            commit_error=RecoveryRequired(),
        )
        with self.assertRaises(RecoveryRequired):
            self._run_with_spy(coordinator)
        self.assertTrue(coordinator.claimed.is_active)
        coordinator.claimed.close()

    def test_pre_handoff_cancellation_closes_processed_artifacts(self) -> None:
        states = []
        original = PreparedArtifactSet.close_if_unclaimed

        def close_and_record(artifacts):
            states.append(artifacts.is_active)
            original(artifacts)
            states.append(artifacts.is_active)

        with patch.object(
            PreparedArtifactSet,
            "close_if_unclaimed",
            autospec=True,
            side_effect=close_and_record,
        ):
            with self.assertRaises(WorkflowCancelledError):
                ImportWorkflow(
                    build_image_processing_pipeline(),
                    is_cancelled=_CancelAt(16),
                ).execute(
                    self.request,
                    self.workspace("cancel-workspace"),
                    transaction=lambda _prepared: self.fail(
                        "transaction invoked after cancellation"
                    ),
                )
        self.assertEqual(states, [True, False])


class DesktopPreparationIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "test.ca-package"
        self.source.write_bytes(package_bytes())
        _ImmediateThread.instances = []

    def dialog(self, coordinator):
        from capture_import.ui import CapturePackageImportDialog

        dialog = CapturePackageImportDialog.__new__(CapturePackageImportDialog)
        dialog._source_path = str(self.source)
        dialog._collection = SimpleNamespace(
            storage_path=str(self.root / "collection.json")
        )
        dialog._recovery = _RecoverySpy()
        dialog._coordinator = coordinator
        dialog._closed = False
        dialog._request_id = object()
        dialog._queue = queue.Queue()
        dialog._workspace = None
        dialog.window = _WindowSpy()
        return dialog

    def start(self, dialog):
        workspace_root = self.root / "workspaces"
        with (
            patch(
                "capture_import.ui.WORKSPACE_ROOT",
                str(workspace_root),
            ),
            patch("capture_import.ui.threading.Thread", _ImmediateThread),
        ):
            dialog._start_prepare()
        return workspace_root

    def test_desktop_prepare_runs_pipeline_then_hands_off_once(self) -> None:
        coordinator = _PreparationCoordinatorSpy()
        dialog = self.dialog(coordinator)

        workspace_root = self.start(dialog)

        request, kind, payload = dialog._queue.get_nowait()
        self.assertIs(request, dialog._request_id)
        self.assertEqual(kind, "prepared")
        self.assertIs(payload, coordinator.result)
        self.assertEqual(dialog._recovery.calls, 1)
        self.assertEqual(len(coordinator.prepare_calls), 1)
        source, kwargs = coordinator.prepare_calls[0]
        self.assertEqual(source, str(self.source))
        self.assertIs(kwargs["processed_artifacts"], coordinator.artifacts)
        self.assertEqual(coordinator.claim_calls, 1)
        self.assertTrue(coordinator.artifacts.is_claimed)
        self.assertFalse(coordinator.artifacts.is_active)
        self.assertIsNotNone(dialog._workspace)
        self.assertTrue(dialog._workspace.is_closed)
        self.assertFalse(dialog._workspace.path.exists())
        self.assertTrue(workspace_root.exists())
        self.assertEqual(len(_ImmediateThread.instances), 1)
        self.assertTrue(_ImmediateThread.instances[0].daemon)
        self.assertTrue(_ImmediateThread.instances[0].started)
        self.assertEqual(dialog.window.after_calls[0][0], 50)

    def test_desktop_prepare_defaults_to_explicit_default_mode_selection(self) -> None:
        from capture_import.desktop_import_pipeline_selection import (
            select_import_pipeline as real_select_import_pipeline,
        )

        coordinator = _PreparationCoordinatorSpy()
        dialog = self.dialog(coordinator)

        with patch(
            "capture_import.ui.select_import_pipeline",
            wraps=real_select_import_pipeline,
        ) as selector:
            self.start(dialog)

        self.assertEqual(selector.call_count, 1)
        self.assertEqual(
            selector.call_args.kwargs["mode"],
            ImportPipelineMode.DEFAULT,
        )

    def test_desktop_prepare_can_request_ocr_enabled_mode_selection(self) -> None:
        coordinator = _PreparationCoordinatorSpy()
        dialog = self.dialog(coordinator)
        dialog._import_mode = ImportPipelineMode.OCR_ENABLED

        with patch(
            "capture_import.ui.select_import_pipeline",
            side_effect=(
                lambda **_kwargs: build_image_processing_pipeline()
            ),
        ) as selector:
            self.start(dialog)

        self.assertEqual(selector.call_count, 1)
        self.assertEqual(
            selector.call_args.kwargs["mode"],
            ImportPipelineMode.OCR_ENABLED,
        )

    def test_desktop_prepare_failure_before_claim_closes_once(self) -> None:
        coordinator = _PreparationCoordinatorSpy(fail_before_claim=True)
        dialog = self.dialog(coordinator)

        self.start(dialog)

        _request, kind, payload = dialog._queue.get_nowait()
        self.assertEqual(kind, "error")
        self.assertIsInstance(payload, PackageChanged)
        self.assertEqual(len(coordinator.prepare_calls), 1)
        self.assertEqual(coordinator.claim_calls, 0)
        self.assertFalse(coordinator.artifacts.is_claimed)
        self.assertFalse(coordinator.artifacts.is_active)
        self.assertTrue(dialog._workspace.is_closed)
        self.assertFalse(dialog._workspace.path.exists())

    def test_desktop_prepare_failure_after_claim_does_not_reclaim(self) -> None:
        coordinator = _PreparationCoordinatorSpy(fail_after_claim=True)
        dialog = self.dialog(coordinator)

        self.start(dialog)

        _request, kind, payload = dialog._queue.get_nowait()
        self.assertEqual(kind, "error")
        self.assertIsInstance(payload, PackageChanged)
        self.assertEqual(len(coordinator.prepare_calls), 1)
        self.assertEqual(coordinator.claim_calls, 1)
        self.assertTrue(coordinator.artifacts.is_claimed)
        self.assertFalse(coordinator.artifacts.is_active)
        self.assertTrue(dialog._workspace.is_closed)
        self.assertFalse(dialog._workspace.path.exists())

    def test_desktop_cancellation_stops_before_coordinator(self) -> None:
        coordinator = _PreparationCoordinatorSpy()
        dialog = self.dialog(coordinator)
        dialog._closed = True

        self.start(dialog)

        _request, kind, payload = dialog._queue.get_nowait()
        self.assertEqual(kind, "error")
        self.assertIsInstance(payload, WorkflowCancelledError)
        self.assertEqual(coordinator.prepare_calls, [])
        self.assertTrue(dialog._workspace.is_closed)
        self.assertFalse(dialog._workspace.path.exists())

    def test_desktop_post_pipeline_cancellation_stops_before_handoff(self) -> None:
        coordinator = _PreparationCoordinatorSpy()
        dialog = self.dialog(coordinator)
        execute = ImportWorkflow.execute

        def execute_then_cancel(workflow, *args, **kwargs):
            outcome = execute(workflow, *args, **kwargs)
            dialog._closed = True
            return outcome

        with patch.object(
            ImportWorkflow,
            "execute",
            autospec=True,
            side_effect=execute_then_cancel,
        ):
            self.start(dialog)

        self.assertTrue(dialog._queue.empty())
        self.assertEqual(coordinator.prepare_calls, [])
        self.assertTrue(dialog._workspace.is_closed)
        self.assertFalse(dialog._workspace.path.exists())

    def test_desktop_image_failure_has_no_raw_fallback(self) -> None:
        coordinator = _PreparationCoordinatorSpy()
        dialog = self.dialog(coordinator)
        self.source.write_bytes(b"not a capture package")

        self.start(dialog)

        _request, kind, payload = dialog._queue.get_nowait()
        self.assertEqual(kind, "error")
        self.assertIsInstance(payload, Exception)
        self.assertEqual(coordinator.prepare_calls, [])
        self.assertTrue(dialog._workspace.is_closed)
        self.assertFalse(dialog._workspace.path.exists())

    def test_fixed_pipeline_rejects_unknown_artifact_provenance(self) -> None:
        from capture_import.ui import _artifact_stages
        from capture_import.workflow_execution import PipelineOutcome

        outcome = PipelineOutcome(
            artifacts={"unknown": StageArtifact("unknown.bin")},
            metadata={},
        )

        with self.assertRaises(StageContractError):
            _artifact_stages(outcome)


class DefaultCompositionIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "test.ca-package"
        self.source.write_bytes(package_bytes())

    def _services(self):
        from capture_import.ui import build_default_import_services

        collection = CoinCollection(str(self.root / "collection.json"))
        return collection, build_default_import_services(collection)

    def _decisions(self, coordinator, *, selected: bool):
        prepared = coordinator.prepare(self.source)
        try:
            decisions = prepared.preview.decisions
            if not selected:
                for proposal in prepared.preview.proposals:
                    decisions = ImportDecisionModel.apply(
                        prepared.preview,
                        decisions,
                        proposal.source_coin_id,
                        DuplicateDecision.SKIP,
                    )
            return decisions
        finally:
            prepared.cancel()

    def _run_processed(self, coordinator, decisions, workspace_name):
        spy = _RealCoordinatorSpy(coordinator)
        workspace = self.root / workspace_name
        workspace.mkdir()
        result = ImportWorkflow(build_image_processing_pipeline()).execute(
            ImportRequest(
                source=self.source,
                collection_id="collection-1",
                configuration=ImportConfiguration(),
            ),
            workspace,
            transaction=lambda prepared: commit_prepared_import(
                prepared,
                decisions,
                coordinator=spy,
            ),
        )
        self.assertEqual(len(spy.prepare_calls), 1)
        self.assertEqual(len(spy.commit_calls), 1)
        return result, spy

    def test_default_composition_uses_one_lock_and_mandatory_runtime(self) -> None:
        with chdir(self.root):
            _collection, (recovery, coordinator) = self._services()
        self.assertIsInstance(recovery, UnifiedPackageImportRecoveryService)
        self.assertEqual(recovery._lock_path, coordinator._lock_path)
        transaction = coordinator._processed_transaction
        self.assertEqual(transaction._lock_path, coordinator._lock_path)
        self.assertIsInstance(
            transaction._schema3_runtime,
            Schema3PackageImportRecoveryService,
        )
        self.assertIs(
            transaction._schema3_runtime,
            recovery._schema3_runtime,
        )

    def test_zero_selection_is_no_journal_and_processed_then_raw_cleanup(self) -> None:
        with chdir(self.root):
            _collection, (_recovery, coordinator) = self._services()
            decisions = self._decisions(coordinator, selected=False)
            order = []
            processed_cleanup = ProcessedSnapshotHandle.cleanup
            raw_cleanup = SnapshotHandle.cleanup

            def cleanup_processed(handle):
                order.append("processed")
                return processed_cleanup(handle)

            def cleanup_raw(handle):
                order.append("raw")
                return raw_cleanup(handle)

            with (
                patch.object(
                    ProcessedSnapshotHandle,
                    "cleanup",
                    autospec=True,
                    side_effect=cleanup_processed,
                ),
                patch.object(
                    SnapshotHandle,
                    "cleanup",
                    autospec=True,
                    side_effect=cleanup_raw,
                ),
            ):
                result, _spy = self._run_processed(
                    coordinator,
                    decisions,
                    "zero-workspace",
                )

        self.assertIsNone(result.import_id)
        self.assertEqual(result.imported_count, 0)
        self.assertEqual(order, ["processed", "raw"])
        self.assertFalse((self.root / "collection.json").exists())
        self.assertFalse((self.root / "data/imports/journals").exists())
        self.assertFalse((self.root / "data/imports/processed-history").exists())
        self.assertFalse((self.root / "coin_photos/collection").exists())

    def test_processed_import_reaches_terminal_without_raw_fallback(self) -> None:
        with chdir(self.root):
            _collection, (recovery, coordinator) = self._services()
            decisions = self._decisions(coordinator, selected=True)
            self._run_processed(coordinator, decisions, "success-workspace")
            for _attempt in range(64):
                recovery.reconcile_pending_imports()
                journal_root = self.root / "data/imports/journals"
                if not journal_root.exists() or not tuple(journal_root.iterdir()):
                    break
            else:
                self.fail("Schema 3 recovery did not retire its journal chain.")

            history = self.root / "data/imports/processed-history"
            terminal_files = tuple(history.glob("*.json"))
            self.assertEqual(len(terminal_files), 1)
            terminal_bytes = terminal_files[0].read_bytes()
            collection_bytes = (self.root / "collection.json").read_bytes()
            collection_value = json.loads(collection_bytes)
            photos = collection_value[0]["photos"]
            provenance = [photo["capture_import_media"] for photo in photos]
            self.assertTrue(
                all(
                    value["source_kind"] == "PROCESSED_SNAPSHOT"
                    for value in provenance
                )
            )
            managed = tuple(
                path
                for path in (self.root / "coin_photos/collection").rglob("*.jpg")
            )
            self.assertEqual(len(managed), 2)
            with zipfile.ZipFile(self.source) as package:
                raw_media = {
                    package.read("images/front.png"),
                    package.read("images/reverse.jpg"),
                }
            self.assertTrue(
                all(path.read_bytes() not in raw_media for path in managed)
            )
            self.assertEqual(
                {sha256(path.read_bytes()).hexdigest() for path in managed},
                {value["artifact_sha256"] for value in provenance},
            )
            self.assertEqual(recovery.reconcile_pending_imports(), ())
            self.assertEqual(terminal_files[0].read_bytes(), terminal_bytes)
            self.assertEqual(
                (self.root / "collection.json").read_bytes(),
                collection_bytes,
            )


if __name__ == "__main__":
    unittest.main()
