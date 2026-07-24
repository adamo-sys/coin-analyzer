"""Unit 7C coordinator ownership and processed-artifact handoff tests."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from capture_import.coordinator import PackageImportCoordinator, PreparedPackageImport
from capture_import.lock import PackageImportLock
from capture_import.package import ValidatedCapturePackage
from capture_import.processed_snapshot import (
    ProcessedArtifactSnapshotService,
    ProcessedSnapshotHandle,
)
from capture_import.snapshot import CapturePackageSnapshotService, SnapshotHandle
from capture_import.transaction import PackageImportTransactionService
from capture_import.workflow_models import PreparedArtifactSet


class Unit7COwnershipTransferTests(unittest.TestCase):
    """Unit 7C: coordinator ownership and processed-artifact handoff."""

    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp())
        source_digest = patch.object(
            PackageImportCoordinator, "_source_digest", return_value="0" * 64
        )
        source_digest.start()
        self.addCleanup(source_digest.stop)

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.temp, ignore_errors=True)

    @staticmethod
    def _journals() -> Mock:
        journals = Mock()
        journals.list_entries.return_value = ()
        return journals

    def _prepare_context(
        self,
        processed_service: Mock | None,
    ) -> tuple[
        PackageImportCoordinator,
        Mock,
        Mock,
        Mock,
        Mock,
        Mock,
    ]:
        snapshot_service = Mock(spec=CapturePackageSnapshotService)
        snapshot = Mock(spec=SnapshotHandle)
        snapshot_service.create_snapshot.return_value = snapshot
        journals = Mock()
        journals.list_entries.return_value = ()
        transaction = Mock(spec=PackageImportTransactionService)
        transaction._lock_path = self.temp / "authoritative-global.lock"
        package = Mock(spec=ValidatedCapturePackage)
        preview = Mock()
        coordinator = PackageImportCoordinator(
            collection_path=self.temp,
            snapshots=snapshot_service,
            journals=journals,
            transaction=transaction,
            processed_snapshots=processed_service,
        )
        coordinator._validator = Mock()
        coordinator._validator.validate_snapshot.return_value = package
        coordinator._preview_builder = Mock()
        coordinator._preview_builder.build.return_value = preview
        return coordinator, snapshot_service, snapshot, transaction, package, preview

    def test_coordinator_accepts_processed_snapshots_service(self) -> None:
        """Coordinator constructor accepts optional processed_snapshots service."""
        snapshot_service = Mock(spec=CapturePackageSnapshotService)
        processed_service = Mock(spec=ProcessedArtifactSnapshotService)

        coordinator = PackageImportCoordinator(
            collection_path=self.temp,
            snapshots=snapshot_service,
            journals=self._journals(),
            transaction=Mock(),
            processed_snapshots=processed_service,
        )

        self.assertEqual(coordinator._processed_snapshots, processed_service)

    def test_coordinator_without_processed_snapshots_service(self) -> None:
        """Coordinator constructor works without processed_snapshots service."""
        snapshot_service = Mock(spec=CapturePackageSnapshotService)

        coordinator = PackageImportCoordinator(
            collection_path=self.temp,
            snapshots=snapshot_service,
            journals=self._journals(),
            transaction=Mock(),
            processed_snapshots=None,
        )

        self.assertIsNone(coordinator._processed_snapshots)

    @patch("capture_import.coordinator.capture_collection_baseline")
    def test_prepare_without_processed_artifacts_calls_seal_only_original(
        self, mock_baseline
    ):
        """prepare() without processed_artifacts only seals original snapshot."""
        snapshot_service = Mock(spec=CapturePackageSnapshotService)
        mock_snapshot = Mock(spec=SnapshotHandle)
        snapshot_service.create_snapshot.return_value = mock_snapshot

        mock_package = Mock(spec=ValidatedCapturePackage)
        mock_validator = Mock()
        mock_validator.validate_snapshot.return_value = mock_package

        mock_preview = Mock()
        mock_preview_builder = Mock()
        mock_preview_builder.build.return_value = mock_preview

        coordinator = PackageImportCoordinator(
            collection_path=self.temp,
            snapshots=snapshot_service,
            journals=self._journals(),
            transaction=Mock(),
            processed_snapshots=None,
        )
        coordinator._validator = mock_validator
        coordinator._preview_builder = mock_preview_builder
        mock_baseline.return_value = Mock()

        prepared = coordinator.prepare(self.temp / "test.ca-package")

        self.assertIsNone(prepared.processed_snapshot)
        self.assertIsInstance(prepared, PreparedPackageImport)

    @patch("capture_import.coordinator.capture_collection_baseline")
    def test_prepare_with_processed_artifacts_calls_seal_on_processed_service(
        self, mock_baseline
    ):
        """prepare() with processed_artifacts calls processed service seal."""
        snapshot_service = Mock(spec=CapturePackageSnapshotService)
        mock_snapshot = Mock(spec=SnapshotHandle)
        snapshot_service.create_snapshot.return_value = mock_snapshot

        processed_service = Mock(spec=ProcessedArtifactSnapshotService)
        mock_processed = Mock(spec=ProcessedSnapshotHandle)
        processed_service.seal.return_value = mock_processed

        mock_package = Mock(spec=ValidatedCapturePackage)
        mock_validator = Mock()
        mock_validator.validate_snapshot.return_value = mock_package

        mock_preview = Mock()
        mock_preview_builder = Mock()
        mock_preview_builder.build.return_value = mock_preview

        mock_artifacts = Mock(spec=PreparedArtifactSet)
        mock_artifacts.verify = Mock()
        transaction = Mock()
        transaction._lock_path = self.temp / "authoritative-global.lock"

        coordinator = PackageImportCoordinator(
            collection_path=self.temp,
            snapshots=snapshot_service,
            journals=self._journals(),
            transaction=transaction,
            processed_snapshots=processed_service,
        )
        coordinator._validator = mock_validator
        coordinator._preview_builder = mock_preview_builder
        mock_baseline.return_value = Mock()

        prepared = coordinator.prepare(
            self.temp / "test.ca-package", processed_artifacts=mock_artifacts
        )

        self.assertEqual(prepared.processed_snapshot, mock_processed)
        processed_service.seal.assert_called_once()

    @patch("capture_import.coordinator.capture_collection_baseline")
    def test_prepare_with_processed_artifacts_but_no_service_raises(
        self, mock_baseline
    ):
        """Providing processed artifacts without configured service raises."""
        snapshot_service = Mock(spec=CapturePackageSnapshotService)
        mock_snapshot = Mock(spec=SnapshotHandle)
        snapshot_service.create_snapshot.return_value = mock_snapshot

        mock_package = Mock(spec=ValidatedCapturePackage)
        mock_validator = Mock()
        mock_validator.validate_snapshot.return_value = mock_package

        mock_preview = Mock()
        mock_preview_builder = Mock()
        mock_preview_builder.build.return_value = mock_preview

        coordinator = PackageImportCoordinator(
            collection_path=self.temp,
            snapshots=snapshot_service,
            journals=self._journals(),
            transaction=Mock(),
            processed_snapshots=None,
        )
        coordinator._validator = mock_validator
        coordinator._preview_builder = mock_preview_builder
        mock_baseline.return_value = Mock()

        mock_artifacts = Mock(spec=PreparedArtifactSet)

        with self.assertRaises(ValueError) as caught:
            coordinator.prepare(
                self.temp / "test.ca-package", processed_artifacts=mock_artifacts
            )

        self.assertIn("processed_snapshots service not configured", str(caught.exception))
        mock_snapshot.cleanup.assert_called_once()
        coordinator._transaction.execute.assert_not_called()

    def test_cancel_cleans_both_snapshots_when_processed_present(self) -> None:
        """Cancellation cleans processed snapshot then original snapshot."""
        mock_snapshot = Mock(spec=SnapshotHandle)
        mock_processed = Mock(spec=ProcessedSnapshotHandle)
        cleanup_order = []
        mock_processed.cleanup.side_effect = lambda: cleanup_order.append("processed")
        mock_snapshot.cleanup.side_effect = lambda: cleanup_order.append("raw")

        prepared = PreparedPackageImport(
            snapshot=mock_snapshot,
            package=Mock(spec=ValidatedCapturePackage),
            preview=Mock(),
            processed_snapshot=mock_processed,
        )

        prepared.cancel()

        mock_processed.cleanup.assert_called_once()
        mock_snapshot.cleanup.assert_called_once()
        self.assertEqual(cleanup_order, ["processed", "raw"])
        self.assertTrue(prepared.closed)

    def test_cancel_with_no_processed_snapshot_cleans_only_original(self) -> None:
        """Cancellation with no processed snapshot cleans only original."""
        mock_snapshot = Mock(spec=SnapshotHandle)

        prepared = PreparedPackageImport(
            snapshot=mock_snapshot,
            package=Mock(spec=ValidatedCapturePackage),
            preview=Mock(),
            processed_snapshot=None,
        )

        prepared.cancel()

        mock_snapshot.cleanup.assert_called_once()
        self.assertTrue(prepared.closed)

    def test_cancel_is_idempotent(self) -> None:
        """Multiple cancel calls are safe."""
        mock_snapshot = Mock(spec=SnapshotHandle)
        mock_processed = Mock(spec=ProcessedSnapshotHandle)

        prepared = PreparedPackageImport(
            snapshot=mock_snapshot,
            package=Mock(spec=ValidatedCapturePackage),
            preview=Mock(),
            processed_snapshot=mock_processed,
        )

        prepared.cancel()
        prepared.cancel()
        prepared.cancel()

        # Each cleanup should only be called once
        mock_processed.cleanup.assert_called_once()
        mock_snapshot.cleanup.assert_called_once()

    @patch("capture_import.coordinator.capture_collection_baseline")
    def test_prepare_failure_cleans_partial_processed_state(
        self, mock_baseline
    ):
        """Failure during prepare cleans any partial processed snapshot state."""
        snapshot_service = Mock(spec=CapturePackageSnapshotService)
        mock_snapshot = Mock(spec=SnapshotHandle)
        snapshot_service.create_snapshot.return_value = mock_snapshot

        processed_service = Mock(spec=ProcessedArtifactSnapshotService)
        mock_processed = Mock(spec=ProcessedSnapshotHandle)
        processed_service.seal.side_effect = RuntimeError("test failure")

        mock_package = Mock(spec=ValidatedCapturePackage)
        mock_validator = Mock()
        mock_validator.validate_snapshot.return_value = mock_package

        mock_preview = Mock()
        mock_preview_builder = Mock()
        mock_preview_builder.build.return_value = mock_preview

        mock_artifacts = Mock(spec=PreparedArtifactSet)
        mock_artifacts.verify = Mock()
        transaction = Mock()
        transaction._lock_path = self.temp / "authoritative-global.lock"

        coordinator = PackageImportCoordinator(
            collection_path=self.temp,
            snapshots=snapshot_service,
            journals=self._journals(),
            transaction=transaction,
            processed_snapshots=processed_service,
        )
        coordinator._validator = mock_validator
        coordinator._preview_builder = mock_preview_builder
        mock_baseline.return_value = Mock()

        with self.assertRaises(RuntimeError):
            coordinator.prepare(
                self.temp / "test.ca-package", processed_artifacts=mock_artifacts
            )

        # Verify original snapshot was cleaned despite processed failure
        mock_snapshot.cleanup.assert_called_once()

    @patch("capture_import.coordinator.PackageImportLock.acquire")
    @patch("capture_import.coordinator.capture_collection_baseline")
    def test_prepare_uses_authoritative_lock_and_transfers_exact_artifacts_once(
        self, mock_baseline, mock_acquire
    ) -> None:
        """Sealing uses the transaction lock and the exact artifact handoff."""
        processed_service = Mock(spec=ProcessedArtifactSnapshotService)
        processed_snapshot = Mock(spec=ProcessedSnapshotHandle)
        processed_service.seal.return_value = processed_snapshot
        (
            coordinator,
            _snapshot_service,
            _snapshot,
            _transaction,
            package,
            _preview,
        ) = self._prepare_context(processed_service)
        artifacts = Mock(spec=PreparedArtifactSet)
        import_lock = Mock(spec=PackageImportLock)
        events = []
        processed_service.seal.side_effect = (
            lambda *args, **kwargs: events.append("seal") or processed_snapshot
        )
        import_lock.release.side_effect = lambda: events.append("release")
        mock_acquire.return_value = import_lock
        mock_baseline.return_value = Mock()

        prepared = coordinator.prepare(
            self.temp / "test.ca-package", processed_artifacts=artifacts
        )

        self.assertIs(prepared.processed_snapshot, processed_snapshot)
        mock_acquire.assert_called_once_with(coordinator._transaction._lock_path)
        processed_service.seal.assert_called_once_with(
            artifacts, package, import_lock=import_lock
        )
        import_lock.release.assert_called_once_with()
        self.assertEqual(events, ["seal", "release"])

    @patch("capture_import.coordinator.PackageImportLock.acquire")
    @patch("capture_import.coordinator.capture_collection_baseline")
    def test_prepare_releases_lock_and_raw_snapshot_after_sealing_failure(
        self, mock_baseline, mock_acquire
    ) -> None:
        """A sealing failure releases the lock and cleans the owned raw snapshot."""
        processed_service = Mock(spec=ProcessedArtifactSnapshotService)
        processed_service.seal.side_effect = RuntimeError("sealing failed")
        (
            coordinator,
            _snapshot_service,
            snapshot,
            transaction,
            _package,
            _preview,
        ) = self._prepare_context(processed_service)
        import_lock = Mock(spec=PackageImportLock)
        mock_acquire.return_value = import_lock
        mock_baseline.return_value = Mock()

        with self.assertRaisesRegex(RuntimeError, "sealing failed"):
            coordinator.prepare(
                self.temp / "test.ca-package",
                processed_artifacts=Mock(spec=PreparedArtifactSet),
            )

        import_lock.release.assert_called_once_with()
        snapshot.cleanup.assert_called_once_with()
        transaction.execute.assert_not_called()

    @patch("capture_import.coordinator.PackageImportLock.acquire")
    @patch("capture_import.coordinator.capture_collection_baseline")
    def test_prepare_lock_acquisition_failure_cleans_raw_without_sealing(
        self, mock_baseline, mock_acquire
    ) -> None:
        """Failure to acquire the global lock leaves no coordinator snapshot."""
        processed_service = Mock(spec=ProcessedArtifactSnapshotService)
        (
            coordinator,
            _snapshot_service,
            snapshot,
            transaction,
            _package,
            _preview,
        ) = self._prepare_context(processed_service)
        mock_acquire.side_effect = RuntimeError("lock unavailable")
        mock_baseline.return_value = Mock()

        with self.assertRaisesRegex(RuntimeError, "lock unavailable"):
            coordinator.prepare(
                self.temp / "test.ca-package",
                processed_artifacts=Mock(spec=PreparedArtifactSet),
            )

        processed_service.seal.assert_not_called()
        snapshot.cleanup.assert_called_once_with()
        transaction.execute.assert_not_called()

    @patch("capture_import.coordinator.PackageImportLock.acquire")
    @patch("capture_import.coordinator.capture_collection_baseline")
    def test_prepare_propagates_duplicate_ownership_transfer_rejection(
        self, mock_baseline, mock_acquire
    ) -> None:
        """Reusing an already-transferred artifact set fails preparation."""
        processed_service = Mock(spec=ProcessedArtifactSnapshotService)
        first_processed = Mock(spec=ProcessedSnapshotHandle)
        processed_service.seal.side_effect = [
            first_processed,
            RuntimeError("prepared artifacts were already claimed"),
        ]
        (
            coordinator,
            snapshot_service,
            first_snapshot,
            transaction,
            _package,
            _preview,
        ) = self._prepare_context(processed_service)
        second_snapshot = Mock(spec=SnapshotHandle)
        snapshot_service.create_snapshot.side_effect = [
            first_snapshot,
            second_snapshot,
        ]
        mock_acquire.side_effect = [
            Mock(spec=PackageImportLock),
            Mock(spec=PackageImportLock),
        ]
        mock_baseline.return_value = Mock()
        artifacts = Mock(spec=PreparedArtifactSet)

        first = coordinator.prepare(
            self.temp / "test.ca-package", processed_artifacts=artifacts
        )
        with self.assertRaisesRegex(RuntimeError, "already claimed"):
            coordinator.prepare(
                self.temp / "test.ca-package", processed_artifacts=artifacts
            )

        self.assertIs(first.processed_snapshot, first_processed)
        self.assertEqual(processed_service.seal.call_count, 2)
        second_snapshot.cleanup.assert_called_once_with()
        transaction.execute.assert_not_called()

    @patch("capture_import.coordinator.PackageImportLock.acquire")
    @patch("capture_import.coordinator.capture_collection_baseline")
    def test_prepare_propagates_package_artifact_linkage_mismatch(
        self, mock_baseline, mock_acquire
    ) -> None:
        """A package/artifact mapping rejection aborts before transaction use."""
        processed_service = Mock(spec=ProcessedArtifactSnapshotService)
        processed_service.seal.side_effect = ValueError(
            "Prepared artifacts do not map one-to-one to package media."
        )
        (
            coordinator,
            _snapshot_service,
            snapshot,
            transaction,
            _package,
            _preview,
        ) = self._prepare_context(processed_service)
        import_lock = Mock(spec=PackageImportLock)
        mock_acquire.return_value = import_lock
        mock_baseline.return_value = Mock()

        with self.assertRaisesRegex(ValueError, "one-to-one"):
            coordinator.prepare(
                self.temp / "test.ca-package",
                processed_artifacts=Mock(spec=PreparedArtifactSet),
            )

        import_lock.release.assert_called_once_with()
        snapshot.cleanup.assert_called_once_with()
        transaction.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
