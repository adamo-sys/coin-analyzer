"""Tests for v2.4.2 collection integrity audit."""

import os
import tempfile
import unittest

from backup_manager import BackupManager
from coin_collection import CoinItem
from collection_integrity import CollectionIntegrityAudit, CollectionIntegrityReport
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord, PurchaseRecord
from persistence_manager import AppState, PersistenceManager
from photo_vault import PhotoRecord
from smart_shopping_assistant import ShoppingCandidate


def item(
    item_id="1",
    country="Newfoundland",
    denomination="20 cents",
    year="1900",
    grade="VF-20",
    notes="",
):
    return CoinItem(
        id=item_id,
        image_path="",
        country=country,
        denomination=denomination,
        year=year,
        grade=grade,
        notes=notes,
        date_added="2026-06-18",
    )


def make_safety_managers(temp_dir):
    state_dir = os.path.join(temp_dir, "collection_data", "app_state")
    backup_dir = os.path.join(temp_dir, "backups", "packages")
    collection_json_path = os.path.join(temp_dir, "data", "collection.json")
    os.makedirs(os.path.dirname(collection_json_path), exist_ok=True)
    with open(collection_json_path, "w", encoding="utf-8") as handle:
        handle.write('[{"id": "1"}]\n')
    persistence = PersistenceManager(state_dir=state_dir)
    persistence.save_state(AppState())
    backup = BackupManager(
        backup_dir=backup_dir,
        persistence_manager=persistence,
        collection_json_path=collection_json_path,
    )
    backup.create_backup_package()
    return persistence, backup


class TestCollectionIntegrityAudit(unittest.TestCase):
    def test_integrity_report_generates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_safety_managers(temp_dir)
            report = CollectionIntegrityAudit([item()], persistence_manager=persistence, backup_manager=backup).run()

            self.assertIsInstance(report, CollectionIntegrityReport)
            self.assertGreaterEqual(report.integrity_score.score, 80)
            self.assertIn("Integrity Score", report.format_markdown())

    def test_duplicate_ownership_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_safety_managers(temp_dir)
            report = CollectionIntegrityAudit(
                [item("1"), item("2")],
                persistence_manager=persistence,
                backup_manager=backup,
            ).run()

            self.assertTrue(any(finding.category == "Duplicate Ownership" for finding in report.findings))

    def test_missing_grade_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_safety_managers(temp_dir)
            report = CollectionIntegrityAudit([item(grade="")], persistence_manager=persistence, backup_manager=backup).run()

            self.assertTrue(any("Missing grade" in finding.message for finding in report.findings))

    def test_missing_date_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_safety_managers(temp_dir)
            report = CollectionIntegrityAudit([item(year="")], persistence_manager=persistence, backup_manager=backup).run()

            self.assertTrue(any("Missing date" in finding.message for finding in report.findings))

    def test_invalid_year_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_safety_managers(temp_dir)
            report = CollectionIntegrityAudit([item(year="19AB")], persistence_manager=persistence, backup_manager=backup).run()

            self.assertTrue(any("Invalid year" in finding.message for finding in report.findings))

    def test_invalid_country_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_safety_managers(temp_dir)
            report = CollectionIntegrityAudit([item(country="")], persistence_manager=persistence, backup_manager=backup).run()

            self.assertTrue(any("country" in finding.message.lower() for finding in report.findings))

    def test_orphan_photo_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_safety_managers(temp_dir)
            photo = PhotoRecord("missing.jpg", "Collection Photo", linked_collection_item_id="missing")

            report = CollectionIntegrityAudit(
                [item()],
                photo_records=[photo],
                persistence_manager=persistence,
                backup_manager=backup,
            ).run()

            self.assertEqual(report.photo_summary.orphan_photo_references, 1)
            self.assertEqual(report.photo_summary.missing_files, 1)

    def test_orphan_market_record_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_safety_managers(temp_dir)
            market = MarketAwarenessEngine(
                purchases=[PurchaseRecord("Canada 5 cents 1940", country="Canada", denomination="5 cents", year="1940")]
            )

            report = CollectionIntegrityAudit(
                [item()],
                market_awareness_engine=market,
                persistence_manager=persistence,
                backup_manager=backup,
            ).run()

            self.assertEqual(report.market_summary.orphan_market_records, 1)

    def test_duplicate_market_observation_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_safety_managers(temp_dir)
            observation = ObservedPriceRecord("Newfoundland 20 cents 1900", "Newfoundland", "20 cents", "1900", observed_price=20, source="test", date_observed="2026-06-18")
            market = MarketAwarenessEngine(observations=[observation, observation])

            report = CollectionIntegrityAudit(
                [item()],
                market_awareness_engine=market,
                persistence_manager=persistence,
                backup_manager=backup,
            ).run()

            self.assertEqual(report.market_summary.duplicate_observations, 1)

    def test_certification_issue_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_safety_managers(temp_dir)
            slabbed = item(notes="PCGS slabbed")
            certified = item("2")
            setattr(certified, "certification_number", "A")

            report = CollectionIntegrityAudit(
                [slabbed, certified],
                persistence_manager=persistence,
                backup_manager=backup,
            ).run()

            self.assertEqual(report.certification_summary.missing_certification_references, 1)
            self.assertEqual(report.certification_summary.malformed_certification_references, 1)

    def test_duplicate_certification_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_safety_managers(temp_dir)
            first = item("1")
            second = item("2", year="1901")
            setattr(first, "certification_number", "PCGS12345")
            setattr(second, "certification_number", "PCGS12345")

            report = CollectionIntegrityAudit(
                [first, second],
                persistence_manager=persistence,
                backup_manager=backup,
            ).run()

            self.assertEqual(report.certification_summary.duplicate_certification_ids, 1)

    def test_shopping_candidate_photo_reference_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_safety_managers(temp_dir)
            candidate = ShoppingCandidate("Newfoundland 20 cents 1904", photo_reference_ids=["missing-photo"])

            report = CollectionIntegrityAudit(
                [item()],
                shopping_candidates=[candidate],
                persistence_manager=persistence,
                backup_manager=backup,
            ).run()

            self.assertTrue(any(finding.category == "Shopping Candidates" for finding in report.findings))

    def test_backup_readiness_integration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence = PersistenceManager(state_dir=os.path.join(temp_dir, "collection_data", "app_state"))
            backup = BackupManager(
                backup_dir=os.path.join(temp_dir, "backups", "packages"),
                persistence_manager=persistence,
                collection_json_path=os.path.join(temp_dir, "missing", "collection.json"),
            )

            report = CollectionIntegrityAudit([item()], persistence_manager=persistence, backup_manager=backup).run()

            self.assertEqual(report.backup_status, "FAIL")
            self.assertTrue(any(finding.category == "Backups" for finding in report.findings))

    def test_export_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence, backup = make_safety_managers(temp_dir)
            report = CollectionIntegrityAudit([item()], persistence_manager=persistence, backup_manager=backup).run()
            md_path = os.path.join(temp_dir, "integrity.md")
            csv_path = os.path.join(temp_dir, "integrity.csv")

            self.assertTrue(report.export_markdown(md_path))
            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(os.path.exists(md_path))
            self.assertTrue(os.path.exists(csv_path))


if __name__ == "__main__":
    unittest.main()
