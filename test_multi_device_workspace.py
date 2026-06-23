import csv
import os
import tempfile
import unittest

from coin_collection import CoinItem
from collector_cloud import CollectorCloud
from multi_device_workspace import (
    CAPABILITY_BACKUP_OPERATIONS,
    CAPABILITY_COLLECTION_ENTRY,
    CAPABILITY_OCR_IDENTIFICATION,
    CAPABILITY_PHOTO_CAPTURE,
    DEVICE_DESKTOP,
    DEVICE_LAPTOP,
    DEVICE_PHONE,
    DEVICE_TABLET,
    CollectorWorkspace,
    DeviceProfile,
    MultiDeviceWorkspaceEngine,
    WorkspaceActivity,
    WorkspaceHealthReport,
    WorkspaceSnapshot,
)
from sync_backup_engine import SyncBackupEngine


class TestMultiDeviceWorkspace(unittest.TestCase):
    def item(self, coin_id="1", grade="VF-20"):
        return CoinItem(coin_id, "", "Canada", "5 cents", "1945", grade, "", "2026-06-22")

    def second_item(self):
        return CoinItem("2", "", "Newfoundland", "50 cents", "1900", "F-12", "", "2026-06-22")

    def engine(self, items=None):
        return MultiDeviceWorkspaceEngine(
            collection_items=items if items is not None else [self.item()],
            want_list_intents=[],
            settings={"theme": "local", "watchlists": ["Newfoundland"]},
        )

    def test_device_creation_supports_all_workspace_device_types(self):
        engine = self.engine()
        desktop = engine.create_device_profile(DEVICE_DESKTOP, "Desk")
        laptop = engine.create_device_profile(DEVICE_LAPTOP, "Lap")
        phone = engine.create_device_profile(DEVICE_PHONE, "Phone")
        tablet = engine.create_device_profile(DEVICE_TABLET, "Tablet")

        self.assertEqual(desktop.device_type, DEVICE_DESKTOP)
        self.assertIn(CAPABILITY_BACKUP_OPERATIONS, desktop.capabilities)
        self.assertIn(CAPABILITY_COLLECTION_ENTRY, laptop.capabilities)
        self.assertIn(CAPABILITY_PHOTO_CAPTURE, phone.capabilities)
        self.assertIn(CAPABILITY_OCR_IDENTIFICATION, tablet.capabilities)

    def test_workspace_creation_tracks_devices_and_readiness(self):
        engine = self.engine()
        workspace = engine.default_workspace("Adam Workspace")

        self.assertIsInstance(workspace, CollectorWorkspace)
        self.assertEqual(len(workspace.registered_devices), 3)
        self.assertEqual(workspace.sync_readiness, "READY_FOR_SIMULATION")
        self.assertEqual(workspace.backup_readiness, "READY")
        self.assertIn("Synchronization executed: NO", workspace.format_markdown())

    def test_workspace_snapshot_tracks_collection_portfolio_workflow_watchlist_and_backup(self):
        engine = self.engine([self.item(), self.second_item()])
        workspace = engine.default_workspace()

        snapshot = engine.create_snapshot(workspace, "unit snapshot")

        self.assertIsInstance(snapshot, WorkspaceSnapshot)
        self.assertEqual(snapshot.collection_state["collection_items"], 2)
        self.assertEqual(snapshot.watchlist_state["watchlist_count"], 1)
        self.assertTrue(snapshot.cloud_snapshot_id)
        self.assertTrue(snapshot.backup_archive_id)
        self.assertEqual(len(workspace.workspace_snapshots), 1)
        self.assertIn("Synchronization executed: NO", snapshot.format_markdown())

    def test_snapshot_comparison_and_drift_analysis_detect_workspace_changes(self):
        engine = self.engine([self.item()])
        workspace = engine.default_workspace()
        first = engine.create_snapshot(workspace, "first")
        workspace.register_device(engine.create_device_profile(DEVICE_TABLET, "Tablet"))
        second = engine.create_snapshot(workspace, "second")

        diff = second.compare_to(first)
        drift = second.drift_analysis(first)

        self.assertTrue(diff["drift_detected"])
        self.assertTrue(diff["added_devices"])
        self.assertGreater(drift["drift_score"], 0)
        self.assertIn("Review changed workspace sections before future sync", drift["recommendations"])

    def test_capability_reporting_summarizes_device_coverage(self):
        engine = self.engine()
        devices = [
            engine.create_device_profile(DEVICE_DESKTOP, "Desktop"),
            engine.create_device_profile(DEVICE_PHONE, "Phone"),
            engine.create_device_profile(DEVICE_TABLET, "Tablet"),
        ]

        report = engine.capability_report(devices)

        self.assertEqual(report["device_count"], 3)
        self.assertGreaterEqual(report["capability_coverage"][CAPABILITY_PHOTO_CAPTURE], 2)
        self.assertGreaterEqual(report["capability_coverage"][CAPABILITY_BACKUP_OPERATIONS], 1)
        self.assertTrue(report["device_summaries"])

    def test_activity_tracking_and_summary(self):
        engine = self.engine()
        workspace = engine.default_workspace()
        phone = next(device for device in workspace.registered_devices if device.device_type == DEVICE_PHONE)

        activity = engine.record_activity(workspace, phone, "collection", "Reviewed a field entry", module="Mobile Collection Entry")
        summary = engine.activity_summary(workspace)

        self.assertIsInstance(activity, WorkspaceActivity)
        self.assertEqual(summary["activity_count"], 1)
        self.assertEqual(summary["devices_active"], 1)
        self.assertEqual(summary["activity_by_type"]["collection"], 1)
        self.assertIn("Mobile Collection Entry", activity.format_markdown())

    def test_health_reporting_tracks_coverage_readiness_and_recommendations(self):
        engine = self.engine([self.item(), self.second_item()])
        workspace = engine.default_workspace()
        workspace.register_device(engine.create_device_profile(DEVICE_TABLET, "Tablet"))
        engine.create_snapshot(workspace, "health")

        report = engine.health_report(workspace)

        self.assertIsInstance(report, WorkspaceHealthReport)
        self.assertGreaterEqual(report.device_coverage["coverage_score"], 100)
        self.assertEqual(report.sync_readiness["real_sync_enabled"], "NO")
        self.assertGreaterEqual(report.health_score, 0)
        self.assertIn("Real synchronization configured: NO", report.format_markdown())

    def test_export_generation_for_workspace_reports(self):
        engine = self.engine([self.item()])
        workspace = engine.default_workspace()
        snapshot = engine.create_snapshot(workspace, "export")
        activity = engine.record_activity(workspace, workspace.registered_devices[0], "backup", "Created backup plan")
        health = engine.health_report(workspace)
        device = workspace.registered_devices[0]

        with tempfile.TemporaryDirectory() as temp_dir:
            for name, report in [
                ("device", device),
                ("workspace", workspace),
                ("snapshot", snapshot),
                ("activity", activity),
                ("health", health),
            ]:
                md_path = os.path.join(temp_dir, f"{name}.md")
                csv_path = os.path.join(temp_dir, f"{name}.csv")
                self.assertTrue(report.export_markdown(md_path))
                self.assertTrue(report.export_csv(csv_path))
                self.assertTrue(os.path.getsize(md_path) > 0)
                with open(csv_path, newline="", encoding="utf-8") as handle:
                    rows = list(csv.reader(handle))
                self.assertGreaterEqual(len(rows), 1)

    def test_sync_backup_and_cloud_integration_reuses_existing_engines(self):
        cloud = CollectorCloud(collection_items=[self.item(), self.second_item()])
        sync_backup = SyncBackupEngine(collector_cloud=cloud)
        engine = MultiDeviceWorkspaceEngine(collector_cloud=cloud, sync_backup_engine=sync_backup)
        workspace = engine.default_workspace()

        snapshot = engine.create_snapshot(workspace, "integration")

        self.assertEqual(len(cloud.snapshot_history()), 1)
        self.assertEqual(len(sync_backup.archives), 1)
        self.assertEqual(snapshot.cloud_snapshot_id, cloud.snapshot_history()[0].snapshot_id)
        self.assertEqual(snapshot.backup_archive_id, sync_backup.archives[0].archive_id)
        self.assertEqual(sync_backup.archives[0].version, "v6.2")

    def test_multi_device_scenarios_generate_readiness_and_conflict_exposure(self):
        engine = self.engine([self.item()])
        first = engine.simulate_desktop_phone_laptop()
        second = engine.simulate_phone_tablet_desktop()

        self.assertEqual(first["device_path"], [DEVICE_DESKTOP, DEVICE_PHONE, DEVICE_LAPTOP])
        self.assertEqual(second["device_path"], [DEVICE_PHONE, DEVICE_TABLET, DEVICE_DESKTOP])
        self.assertIn("readiness_analysis", first)
        self.assertIn("conflict_exposure", second)
        self.assertEqual(first["conflict_exposure"]["automatic_resolution"], "NO")
        self.assertIn("Synchronization executed: NO", first["workspace_report"])


if __name__ == "__main__":
    unittest.main()
