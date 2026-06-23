import csv
import os
import tempfile
import unittest

from coin_collection import CoinItem
from collector_cloud import CollectorCloud
from device_linking import (
    ACTION_KEEP_PRIMARY,
    ACTION_MERGE,
    ACTION_REVIEW_REQUIRED,
    CONFLICT_COLLECTION,
    CONFLICT_SETTINGS,
    CONFLICT_SNAPSHOT,
    CONFLICT_WATCHLIST,
    LINK_LINKED,
    RELATIONSHIP_BACKUP,
    RELATIONSHIP_MOBILE,
    RELATIONSHIP_PRIMARY,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    ConflictResolutionEngine,
    ConflictResolutionReport,
    DeviceLinkReadinessReport,
    DeviceLinkReport,
    DeviceLinkingEngine,
    DeviceRelationship,
    LinkedDevice,
    WorkspaceLinkMap,
)
from multi_device_workspace import (
    DEVICE_DESKTOP,
    DEVICE_LAPTOP,
    DEVICE_PHONE,
    DEVICE_TABLET,
    MultiDeviceWorkspaceEngine,
    WorkspaceSnapshot,
)
from sync_backup_engine import SyncBackupEngine


class TestDeviceLinking(unittest.TestCase):
    def item(self, coin_id="1", grade="VF-20"):
        return CoinItem(coin_id, "", "Canada", "5 cents", "1945", grade, "", "2026-06-22")

    def second_item(self):
        return CoinItem("2", "", "Newfoundland", "50 cents", "1900", "F-12", "", "2026-06-22")

    def workspace_engine(self, items=None):
        return MultiDeviceWorkspaceEngine(
            collection_items=items if items is not None else [self.item()],
            settings={"theme": "local"},
        )

    def engine(self, items=None):
        return DeviceLinkingEngine(
            collection_items=items if items is not None else [self.item()],
            settings={"theme": "local"},
        )

    def test_device_linking_creates_linked_devices_from_profiles(self):
        workspace_engine = self.workspace_engine()
        profile = workspace_engine.create_device_profile(DEVICE_PHONE, "Show Phone")
        device = self.engine().create_linked_device(profile, RELATIONSHIP_MOBILE)

        self.assertIsInstance(device, LinkedDevice)
        self.assertEqual(device.device_id, profile.device_id)
        self.assertEqual(device.relationship_role, RELATIONSHIP_MOBILE)
        self.assertEqual(device.sync_readiness, "READY_FOR_REVIEW")
        self.assertIn("Automatic sync enabled: NO", device.format_markdown())

    def test_relationship_mapping_tracks_overlap_and_readiness(self):
        workspace_engine = self.workspace_engine()
        primary = self.engine().create_linked_device(workspace_engine.create_device_profile(DEVICE_DESKTOP, "Desktop"), RELATIONSHIP_PRIMARY)
        secondary = self.engine().create_linked_device(workspace_engine.create_device_profile(DEVICE_LAPTOP, "Laptop"), RELATIONSHIP_BACKUP)

        relationship = self.engine().link_devices(primary, secondary, RELATIONSHIP_BACKUP, LINK_LINKED)

        self.assertIsInstance(relationship, DeviceRelationship)
        self.assertIn("Collection Entry", relationship.capability_overlap)
        self.assertEqual(relationship.sync_readiness, "READY_FOR_REVIEW")
        self.assertEqual(relationship.link_status, LINK_LINKED)

    def test_workspace_link_report_maps_primary_mobile_tablet_and_backup_roles(self):
        workspace_engine = self.workspace_engine()
        workspace = workspace_engine.create_workspace("Link Map Workspace", [
            workspace_engine.create_device_profile(DEVICE_DESKTOP, "Desktop"),
            workspace_engine.create_device_profile(DEVICE_PHONE, "Phone"),
            workspace_engine.create_device_profile(DEVICE_TABLET, "Tablet"),
            workspace_engine.create_device_profile(DEVICE_LAPTOP, "Laptop"),
        ])

        report = self.engine().link_workspace(workspace)

        self.assertIsInstance(report, DeviceLinkReport)
        self.assertEqual(len(report.linked_devices), 4)
        self.assertEqual(len(report.relationships), 3)
        self.assertTrue(any(device.relationship_role == RELATIONSHIP_PRIMARY for device in report.linked_devices))
        self.assertTrue(any(device.relationship_role == RELATIONSHIP_MOBILE for device in report.linked_devices))
        self.assertIn("Synchronization executed: NO", report.format_markdown())

    def test_conflict_detection_finds_collection_watchlist_settings_and_snapshot_conflicts(self):
        primary = WorkspaceSnapshot(
            snapshot_id="primary",
            workspace_id="w",
            collection_state={"collection_items": 3, "content_hash": "aaa"},
            watchlist_state={"want_list_intents": 1},
            metadata={"settings_hash": "primary-settings"},
        )
        secondary = WorkspaceSnapshot(
            snapshot_id="secondary",
            workspace_id="w",
            collection_state={"collection_items": 1, "content_hash": "bbb"},
            watchlist_state={"want_list_intents": 2},
            metadata={"settings_hash": "secondary-settings"},
        )

        report = ConflictResolutionEngine().analyze_snapshots(primary, secondary)
        types = {case.conflict_type for case in report.conflicts}

        self.assertIn(CONFLICT_COLLECTION, types)
        self.assertIn(CONFLICT_WATCHLIST, types)
        self.assertIn(CONFLICT_SETTINGS, types)
        self.assertIn(CONFLICT_SNAPSHOT, types)
        self.assertGreaterEqual(report.conflict_count, 4)

    def test_conflict_classification_sets_high_collection_risk(self):
        engine = ConflictResolutionEngine()

        severity = engine.classify_conflict(
            CONFLICT_COLLECTION,
            {"collection_items": 5, "content_hash": "aaa"},
            {"collection_items": 1, "content_hash": "bbb"},
        )

        self.assertEqual(severity, SEVERITY_HIGH)

    def test_recommendations_are_review_only_and_actionable(self):
        primary = WorkspaceSnapshot(
            snapshot_id="primary",
            workspace_id="w",
            collection_state={"collection_items": 3, "content_hash": "aaa"},
        )
        secondary = WorkspaceSnapshot(
            snapshot_id="secondary",
            workspace_id="w",
            collection_state={"collection_items": 1, "content_hash": "bbb"},
        )

        report = ConflictResolutionEngine().analyze_snapshots(primary, secondary)
        actions = {recommendation.action for recommendation in report.recommendations}

        self.assertIn(ACTION_REVIEW_REQUIRED, actions)
        self.assertTrue(all(recommendation.review_required for recommendation in report.recommendations))
        self.assertIn("Automatic resolution applied: NO", report.format_markdown())

    def test_recommendations_cover_merge_and_keep_primary_cases(self):
        primary = WorkspaceSnapshot(
            snapshot_id="primary",
            workspace_id="w",
            watchlist_state={"want_list_intents": 1},
            metadata={"settings_hash": "primary-settings"},
        )
        secondary = WorkspaceSnapshot(
            snapshot_id="secondary",
            workspace_id="w",
            watchlist_state={"want_list_intents": 2},
            metadata={"settings_hash": "secondary-settings"},
        )

        report = ConflictResolutionEngine().analyze_snapshots(primary, secondary)
        actions = {recommendation.action for recommendation in report.recommendations}

        self.assertIn(ACTION_MERGE, actions)
        self.assertIn(ACTION_KEEP_PRIMARY, actions)

    def test_workspace_link_map_tracks_overlap_exposure_and_readiness(self):
        workspace_engine = self.workspace_engine([self.item(), self.second_item()])
        workspace = workspace_engine.default_workspace("Map Workspace")
        first = workspace_engine.create_snapshot(workspace, "primary")
        workspace.register_device(workspace_engine.create_device_profile(DEVICE_TABLET, "Tablet"))
        second = workspace_engine.create_snapshot(workspace, "secondary")
        conflict_report = ConflictResolutionEngine().analyze_snapshots(second, first)

        engine = self.engine()
        link_report = engine.link_workspace(workspace)
        link_map = engine.create_link_map(workspace, link_report, conflict_report)

        self.assertIsInstance(link_map, WorkspaceLinkMap)
        self.assertGreaterEqual(link_map.conflict_exposure["conflict_count"], 1)
        self.assertTrue(link_map.capability_overlap)
        self.assertIn("Real sync configured: NO", link_map.format_markdown())

    def test_readiness_report_uses_workspace_health_backup_and_conflict_counts(self):
        workspace_engine = self.workspace_engine([self.item()])
        workspace = workspace_engine.default_workspace("Readiness Workspace")
        workspace_engine.create_snapshot(workspace, "readiness")
        engine = DeviceLinkingEngine(workspace_engine=workspace_engine)
        conflict_report = engine.analyze_workspace_conflicts(workspace)
        link_map = engine.create_link_map(workspace, conflict_report=conflict_report)

        readiness = engine.readiness_report(workspace, link_map, conflict_report)

        self.assertIsInstance(readiness, DeviceLinkReadinessReport)
        self.assertEqual(readiness.backup_coverage, "READY")
        self.assertGreaterEqual(readiness.linked_devices, 1)
        self.assertIn("Automatic conflict resolution: NO", readiness.format_markdown())

    def test_export_generation_for_device_linking_reports(self):
        workspace_engine = self.workspace_engine([self.item(), self.second_item()])
        workspace = workspace_engine.default_workspace("Export Workspace")
        workspace_engine.create_snapshot(workspace, "primary")
        workspace.register_device(workspace_engine.create_device_profile(DEVICE_TABLET, "Tablet"))
        workspace_engine.create_snapshot(workspace, "secondary")
        engine = DeviceLinkingEngine(workspace_engine=workspace_engine)
        link_report = engine.link_workspace(workspace)
        conflict_report = engine.analyze_workspace_conflicts(workspace)
        link_map = engine.create_link_map(workspace, link_report, conflict_report)
        readiness = engine.readiness_report(workspace, link_map, conflict_report)

        with tempfile.TemporaryDirectory() as temp_dir:
            for name, report in [
                ("link_report", link_report),
                ("link_map", link_map),
                ("conflicts", conflict_report),
                ("readiness", readiness),
            ]:
                md_path = os.path.join(temp_dir, f"{name}.md")
                csv_path = os.path.join(temp_dir, f"{name}.csv")
                self.assertTrue(report.export_markdown(md_path))
                self.assertTrue(report.export_csv(csv_path))
                self.assertTrue(os.path.getsize(md_path) > 0)
                with open(csv_path, newline="", encoding="utf-8") as handle:
                    rows = list(csv.reader(handle))
                self.assertGreaterEqual(len(rows), 1)

    def test_workspace_and_sync_integration_reuses_existing_engines(self):
        cloud = CollectorCloud(collection_items=[self.item(), self.second_item()])
        sync_backup = SyncBackupEngine(collector_cloud=cloud)
        workspace_engine = MultiDeviceWorkspaceEngine(collector_cloud=cloud, sync_backup_engine=sync_backup)
        workspace = workspace_engine.default_workspace("Integrated Workspace")
        workspace_engine.create_snapshot(workspace, "primary")
        workspace.register_device(workspace_engine.create_device_profile(DEVICE_TABLET, "Tablet"))
        workspace_engine.create_snapshot(workspace, "secondary")
        engine = DeviceLinkingEngine(
            collector_cloud=cloud,
            sync_backup_engine=sync_backup,
            workspace_engine=workspace_engine,
        )

        conflict_report = engine.analyze_workspace_conflicts(workspace)
        readiness = engine.readiness_report(workspace, conflict_report=conflict_report)

        self.assertIsInstance(conflict_report, ConflictResolutionReport)
        self.assertGreaterEqual(len(cloud.snapshot_history()), 2)
        self.assertGreaterEqual(len(sync_backup.archives), 2)
        self.assertGreaterEqual(readiness.readiness_score, 0)


if __name__ == "__main__":
    unittest.main()
