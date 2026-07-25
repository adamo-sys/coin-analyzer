"""Focused Sprint 8 Unit 7E routing, ownership, and composition tests."""

from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from contextlib import chdir
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from coin_collection import CoinCollection

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
)
from capture_import.workflow_pipeline import WorkflowCancelledError
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
