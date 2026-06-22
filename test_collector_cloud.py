import csv
import os
import tempfile
import unittest

from coin_collection import CoinItem
from collector_cloud import (
    CONFLICT_COLLECTION,
    CloudBackupPackage,
    CloudCollectionSnapshot,
    CloudReadinessReport,
    CloudSyncPlan,
    CollectorCloud,
)
from collector_workflow_integration import CollectorWorkflowIntegrationEngine
from mobile_collector_companion import MobileCollectorCompanion


class TestCollectorCloud(unittest.TestCase):
    def item(self, coin_id="1", grade="VF-20"):
        return CoinItem(coin_id, "", "Canada", "5 cents", "1945", grade, "", "2026-06-22")

    def second_item(self):
        return CoinItem("2", "", "Newfoundland", "50 cents", "1900", "F-12", "", "2026-06-22")

    def test_snapshot_creation_tracks_records_and_metrics(self):
        cloud = CollectorCloud(collection_items=[self.item(), self.second_item()])

        snapshot = cloud.create_snapshot("unit test")

        self.assertIsInstance(snapshot, CloudCollectionSnapshot)
        self.assertEqual(snapshot.collection_metrics["collection_items"], 2)
        self.assertGreaterEqual(snapshot.portfolio_metrics["health_score"], 0)
        self.assertEqual(snapshot.module_counts()["collection"], 2)
        self.assertIn("Cloud upload performed: NO", snapshot.format_markdown())
        self.assertEqual(len(cloud.snapshot_history()), 1)

    def test_snapshot_comparison_detects_added_changed_and_removed_records(self):
        source = CollectorCloud(collection_items=[self.item("1"), self.second_item()]).create_snapshot("source")
        destination = CollectorCloud(collection_items=[self.item("1", "F-12")]).create_snapshot("destination")

        diff = source.compare_to(destination)

        self.assertIn("collection:2", diff["added_record_ids"])
        self.assertIn("collection:1", diff["changed_record_ids"])
        self.assertEqual(diff["removed_record_ids"], [])

    def test_sync_planning_generates_review_only_changes(self):
        source = CollectorCloud(collection_items=[self.item("1"), self.second_item()]).create_snapshot("source")
        destination = CollectorCloud(collection_items=[self.item("1", "F-12")]).create_snapshot("destination")

        plan = CollectorCloud().create_sync_plan(source, destination)

        self.assertIsInstance(plan, CloudSyncPlan)
        self.assertGreaterEqual(plan.proposed_change_count, 2)
        self.assertEqual(plan.conflict_count, 1)
        self.assertIn("Synchronization executed: NO", plan.format_markdown())

    def test_conflict_generation_classifies_collection_conflicts(self):
        source = CollectorCloud(collection_items=[self.item("1", "VF-20")]).create_snapshot("source")
        destination = CollectorCloud(collection_items=[self.item("1", "G-4")]).create_snapshot("destination")

        plan = CollectorCloud().create_sync_plan(source, destination)

        self.assertEqual(plan.conflicts[0].conflict_type, CONFLICT_COLLECTION)
        self.assertEqual(plan.conflicts[0].review_required, True)
        self.assertIn("choose manually", plan.conflicts[0].recommendation)

    def test_backup_package_generation_validation_and_restore_preview(self):
        cloud = CollectorCloud(collection_items=[self.item()])
        snapshot = cloud.create_snapshot("backup")

        package = cloud.create_backup_package(snapshot)

        self.assertIsInstance(package, CloudBackupPackage)
        self.assertIn("Snapshot hash matches", "; ".join(cloud.validate_backup_package(package)))
        self.assertIn("manual confirmation", "; ".join(cloud.restore_package_preview(package)))
        self.assertIn("Restore executed: NO", package.format_markdown())

    def test_readiness_reporting_lists_syncable_and_non_syncable_modules(self):
        cloud = CollectorCloud(collection_items=[self.item()])
        cloud.create_snapshot("readiness")

        report = cloud.cloud_readiness_report()

        self.assertIsInstance(report, CloudReadinessReport)
        self.assertTrue(any("Collection records" in item for item in report.syncable_modules))
        self.assertTrue(any("Raw photo files" in item for item in report.non_syncable_modules))
        self.assertTrue(any("Snapshot records" in item for item in report.conflict_exposure))
        self.assertIn("Cloud services configured: NO", report.format_markdown())

    def test_workflow_and_mobile_companion_integration(self):
        workflow_report = CollectorWorkflowIntegrationEngine(collection_items=[self.item()]).run_workflow(
            raw_text="Canada 1945 5 cents George VI"
        )
        cloud = CollectorCloud(
            collection_items=[self.item()],
            workflow_completion_reports=[workflow_report],
            mobile_entry_reports=[workflow_report.session.entry_report],
        )
        snapshot = cloud.create_snapshot("workflow")
        readiness = cloud.cloud_readiness_report([snapshot])

        companion_report = MobileCollectorCompanion(collection_items=[self.item()]).generate_report(
            workflow_completion_report=workflow_report,
            cloud_readiness_report=readiness,
        )

        self.assertEqual(snapshot.workflow_metrics["workflow_reports"], 1)
        self.assertGreaterEqual(snapshot.module_counts()["workflow"], 1)
        self.assertIn("Collector Cloud Foundation", companion_report.format_markdown())

    def test_export_generation_for_all_cloud_reports(self):
        source = CollectorCloud(collection_items=[self.item("1"), self.second_item()]).create_snapshot("source")
        destination = CollectorCloud(collection_items=[self.item("1", "F-12")]).create_snapshot("destination")
        cloud = CollectorCloud(collection_items=[self.item("1"), self.second_item()])
        plan = cloud.create_sync_plan(source, destination)
        package = cloud.create_backup_package(source)
        readiness = cloud.cloud_readiness_report([source])

        with tempfile.TemporaryDirectory() as temp_dir:
            reports = [
                ("snapshot", source),
                ("plan", plan),
                ("package", package),
                ("readiness", readiness),
            ]
            for name, report in reports:
                md_path = os.path.join(temp_dir, f"{name}.md")
                csv_path = os.path.join(temp_dir, f"{name}.csv")
                self.assertTrue(report.export_markdown(md_path))
                self.assertTrue(report.export_csv(csv_path))
                self.assertTrue(os.path.getsize(md_path) > 0)
                with open(csv_path, newline="", encoding="utf-8") as handle:
                    rows = list(csv.reader(handle))
                self.assertGreaterEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
