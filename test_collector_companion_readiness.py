"""Tests for v2.9 Collector Companion Release Candidate readiness."""

import os
import tempfile
import unittest

from backup_manager import BackupManager
from coin_collection import CoinItem
from collection_snapshot import CollectionSnapshotManager
from collector_companion_readiness import (
    CollectorCompanionReadinessAuditor,
    CollectorCompanionReadinessReport,
    ExportConsistencyReport,
    ReportConsistencyReport,
    V3ReadinessChecklistItem,
    WorkflowAuditReport,
)
from legacy_portfolio_importer import LegacyWantListIntent
from market_awareness import MarketAwarenessEngine
from persistence_manager import AppState, PersistenceManager
from photo_vault import PhotoRecord
from smart_shopping_assistant import ShoppingCandidate


def make_item(item_id, country, denomination, year, grade):
    return CoinItem(
        id=item_id,
        image_path="",
        country=country,
        denomination=denomination,
        year=year,
        grade=grade,
        notes="",
        date_added="2026-06-19",
    )


def make_intent(target_coin):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id="readiness-want-1",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=150,
        why_wanted="Readiness test",
        status="Active",
        priority_score=85,
    )


class TestCollectorCompanionReadiness(unittest.TestCase):
    def setUp(self):
        self.items = [
            make_item("1", "Newfoundland", "20 cents", "1900", "F-12"),
            make_item("2", "Newfoundland", "20 cents", "1901", "VF-20"),
            make_item("3", "Canada", "10 cents", "1911", "EF-40"),
        ]
        self.want_list = [make_intent("Newfoundland 50 cents 1904")]
        self.shopping = [ShoppingCandidate("Newfoundland 50 cents 1904", asking_price=125, shipping=5)]
        self.photos = [
            PhotoRecord(
                file_path="coin_photos/collection/Newfoundland/1900-20c.jpg",
                photo_type="Collection Photo",
                linked_collection_item_id="1",
                linked_coin_name="Newfoundland 20 cents 1900",
            )
        ]

    def make_auditor(self, temp_dir, **overrides):
        persistence = PersistenceManager(state_dir=os.path.join(temp_dir, "state"))
        backup = BackupManager(
            backup_dir=os.path.join(temp_dir, "backups"),
            persistence_manager=persistence,
            collection_json_path=os.path.join(temp_dir, "collection.json"),
        )
        snapshot = CollectionSnapshotManager(os.path.join(temp_dir, "snapshots.json"))
        kwargs = {
            "collection_items": self.items,
            "want_list_intents": self.want_list,
            "photo_records": self.photos,
            "shopping_candidates": self.shopping,
            "market_awareness_engine": MarketAwarenessEngine(),
            "snapshot_manager": snapshot,
            "backup_manager": backup,
        }
        kwargs.update(overrides)
        return CollectorCompanionReadinessAuditor(**kwargs)

    def test_readiness_report_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report = self.make_auditor(temp_dir).generate_report()

            self.assertIsInstance(report, CollectorCompanionReadinessReport)
            self.assertEqual(report.status, "READY")
            self.assertTrue(report.checklist)
            self.assertIn("Collector Companion Readiness Report", report.format_markdown())

    def test_v3_checklist_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            checklist = self.make_auditor(temp_dir).v3_readiness_checklist()
            by_name = {item.name: item for item in checklist}

            self.assertIsInstance(checklist[0], V3ReadinessChecklistItem)
            self.assertTrue(by_name["Backup System"].ready)
            self.assertTrue(by_name["Collector Home Dashboard"].ready)
            self.assertTrue(by_name["OCR Workflow"].ready)

    def test_export_consistency_audit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report = self.make_auditor(temp_dir).audit_exports()

            self.assertIsInstance(report, ExportConsistencyReport)
            self.assertEqual(report.status, "READY")
            self.assertIn("Collector Home Dashboard", report.checked_reports)
            self.assertTrue(report.findings)

    def test_report_consistency_audit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report = self.make_auditor(temp_dir).audit_report_consistency()

            self.assertIsInstance(report, ReportConsistencyReport)
            self.assertEqual(report.status, "READY")
            self.assertTrue(any("Severity" in finding.area for finding in report.findings))

    def test_workflow_audit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report = self.make_auditor(temp_dir).audit_end_to_end_workflow()

            self.assertIsInstance(report, WorkflowAuditReport)
            self.assertEqual(report.status, "READY")
            self.assertTrue(report.friction_points)
            self.assertFalse(report.defects)

    def test_export_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report = self.make_auditor(temp_dir).generate_report()
            csv_path = os.path.join(temp_dir, "readiness.csv")
            md_path = os.path.join(temp_dir, "readiness.md")

            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("Checklist", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("V3.0 Readiness Checklist", handle.read())

    def test_persistence_compatibility(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PersistenceManager(state_dir=os.path.join(temp_dir, "state"))
            report = self.make_auditor(temp_dir).generate_report()
            state = manager.create_state(
                readiness_reports=[report.to_dict()],
                audit_summaries=[{"report": "Collector Companion Readiness", "status": report.status}],
            )

            saved = manager.save_state(state)
            loaded = manager.load_state()

            self.assertTrue(saved.success)
            self.assertEqual(len(loaded.state.readiness_reports), 1)
            self.assertEqual(loaded.state.audit_summaries[0]["status"], "READY")
            restored = CollectorCompanionReadinessReport.from_dict(loaded.state.readiness_reports[0])
            self.assertEqual(restored.status, "READY")

    def test_menu_grouping_source_contains_target_structure(self):
        with open("coin_collection_gui.py", "r", encoding="utf-8") as handle:
            source = handle.read()

        for label in [
            'label="Collector Home"',
            'label="Workflows"',
            'label="Reports"',
            'label="Tools"',
            'label="Help"',
        ]:
            self.assertIn(label, source)
        self.assertIn("Collector Companion Readiness", source)


if __name__ == "__main__":
    unittest.main()
