import csv
import os
import tempfile
import unittest

from coin_collection import CoinItem
from collector_cloud import CollectorCloud
from collector_workflow_integration import CollectorWorkflowIntegrationEngine
from sync_backup_engine import (
    BackupArchive,
    BackupHistory,
    RECOMMEND_REVIEW,
    RestorePlan,
    RollbackPlan,
    SyncBackupEngine,
    SyncConflictReport,
    SyncSimulation,
)


class TestSyncBackupEngine(unittest.TestCase):
    def item(self, coin_id="1", grade="VF-20"):
        return CoinItem(coin_id, "", "Canada", "5 cents", "1945", grade, "", "2026-06-22")

    def second_item(self):
        return CoinItem("2", "", "Newfoundland", "50 cents", "1900", "F-12", "", "2026-06-22")

    def engine(self, items=None, workflow_reports=None):
        return SyncBackupEngine(
            collection_items=items if items is not None else [self.item()],
            workflow_completion_reports=workflow_reports,
            settings={"theme": "local"},
        )

    def test_backup_generation_tracks_scope_checksum_and_snapshot(self):
        engine = self.engine([self.item(), self.second_item()])

        archive = engine.create_backup_archive()

        self.assertIsInstance(archive, BackupArchive)
        self.assertEqual(archive.version, "v6.1")
        self.assertIn("collection", archive.backup_scope)
        self.assertEqual(archive.record_count, archive.source_snapshot.record_count)
        self.assertTrue(archive.checksum)
        self.assertIn("Automatic restore performed: NO", archive.format_markdown())

    def test_restore_planning_reports_affected_records_and_validation(self):
        archive = self.engine([self.item("1", "VF-20")]).create_backup_archive()
        current = CollectorCloud(collection_items=[self.item("1", "G-4"), self.second_item()]).create_snapshot("current")

        plan = self.engine().plan_restore(archive, current)

        self.assertIsInstance(plan, RestorePlan)
        self.assertIn("collection", plan.affected_modules)
        self.assertIn("collection:1", plan.affected_records)
        self.assertTrue(any("Archive checksum" in item for item in plan.validation_results))
        self.assertIn("Restore executed: NO", plan.format_markdown())

    def test_snapshot_history_tracks_timeline_and_deltas(self):
        engine = self.engine([self.item("1")])
        archive_a = engine.create_backup_archive()
        archive_b = self.engine([self.item("1"), self.second_item()]).create_backup_archive()

        history = engine.backup_history([archive_a, archive_b])

        self.assertIsInstance(history, BackupHistory)
        self.assertEqual(len(history.timeline), 2)
        self.assertTrue(history.snapshot_comparisons)
        self.assertEqual(history.collection_delta["collection_items"], 1)
        self.assertIn("Backup History", history.format_markdown())

    def test_sync_simulation_generates_plan_conflicts_and_merge_preview(self):
        device_a = CollectorCloud(collection_items=[self.item("1", "VF-20"), self.second_item()]).create_snapshot("device-a")
        device_b = CollectorCloud(collection_items=[self.item("1", "G-4")]).create_snapshot("device-b")

        simulation = self.engine().simulate_sync(device_a, device_b)

        self.assertIsInstance(simulation, SyncSimulation)
        self.assertGreaterEqual(simulation.sync_plan.proposed_change_count, 2)
        self.assertEqual(simulation.conflict_report.conflict_count, 1)
        self.assertTrue(simulation.merge_preview)
        self.assertIn("Synchronization executed: NO", simulation.format_markdown())

    def test_conflict_detection_reports_collection_snapshot_and_recommendation(self):
        source = CollectorCloud(collection_items=[self.item("1", "VF-20")]).create_snapshot("source")
        destination = CollectorCloud(collection_items=[self.item("1", "G-4")]).create_snapshot("destination")

        report = self.engine().create_conflict_report(source, destination)

        self.assertIsInstance(report, SyncConflictReport)
        self.assertIn("collection:1", report.collection_mismatches)
        self.assertTrue(report.snapshot_divergence)
        self.assertIn(RECOMMEND_REVIEW, report.recommendations)
        self.assertIn("Automatic conflict resolution: NO", report.format_markdown())

    def test_rollback_planning_covers_backup_restore_and_sync_context(self):
        engine = self.engine([self.item("1", "VF-20")])
        archive = engine.create_backup_archive()
        current = CollectorCloud(collection_items=[self.item("1", "G-4")]).create_snapshot("current")
        restore = engine.plan_restore(archive, current)
        simulation = engine.simulate_sync(archive.source_snapshot, current)

        rollback = engine.plan_rollback("sync", archive=archive, restore_plan=restore, sync_simulation=simulation)

        self.assertIsInstance(rollback, RollbackPlan)
        self.assertIn(archive.archive_id, rollback.rollback_targets)
        self.assertIn(restore.plan_id, rollback.rollback_targets)
        self.assertIn(simulation.simulation_id, rollback.rollback_targets)
        self.assertIn("Rollback executed: NO", rollback.format_markdown())

    def test_export_generation_for_all_sync_backup_reports(self):
        engine = self.engine([self.item("1", "VF-20"), self.second_item()])
        archive = engine.create_backup_archive()
        current = CollectorCloud(collection_items=[self.item("1", "G-4")]).create_snapshot("current")
        restore = engine.plan_restore(archive, current)
        history = engine.backup_history([archive])
        simulation = engine.simulate_sync(archive.source_snapshot, current)
        conflict_report = simulation.conflict_report
        rollback = engine.plan_rollback("sync", archive=archive, restore_plan=restore, sync_simulation=simulation)

        with tempfile.TemporaryDirectory() as temp_dir:
            for name, report in [
                ("archive", archive),
                ("restore", restore),
                ("history", history),
                ("simulation", simulation),
                ("conflicts", conflict_report),
                ("rollback", rollback),
            ]:
                md_path = os.path.join(temp_dir, f"{name}.md")
                csv_path = os.path.join(temp_dir, f"{name}.csv")
                self.assertTrue(report.export_markdown(md_path))
                self.assertTrue(report.export_csv(csv_path))
                self.assertTrue(os.path.getsize(md_path) > 0)
                with open(csv_path, newline="", encoding="utf-8") as handle:
                    rows = list(csv.reader(handle))
                self.assertGreaterEqual(len(rows), 1)

    def test_cloud_integration_reuses_collector_cloud_snapshots(self):
        cloud = CollectorCloud(collection_items=[self.item(), self.second_item()])
        snapshot = cloud.create_snapshot("cloud")
        engine = SyncBackupEngine(collector_cloud=cloud)

        archive = engine.create_backup_archive(source_snapshot=snapshot)

        self.assertEqual(archive.source_snapshot.snapshot_id, snapshot.snapshot_id)
        self.assertEqual(archive.metadata["collection_records"], 2)
        self.assertEqual(engine.archives[0], archive)

    def test_workflow_integration_includes_workflow_scope_and_deltas(self):
        workflow_report = CollectorWorkflowIntegrationEngine(collection_items=[self.item()]).run_workflow(
            raw_text="Canada 1945 5 cents George VI"
        )
        engine = self.engine([self.item()], workflow_reports=[workflow_report])

        archive = engine.create_backup_archive()

        self.assertIn("workflow", archive.backup_scope)
        self.assertGreaterEqual(archive.source_snapshot.workflow_metrics["workflow_reports"], 1)
        self.assertGreaterEqual(archive.source_snapshot.module_counts()["workflow"], 1)


if __name__ == "__main__":
    unittest.main()
