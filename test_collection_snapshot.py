"""Tests for v2.4.3 collection snapshot system."""

import os
import tempfile
import unittest
import zipfile

from backup_manager import BackupManager
from coin_collection import CoinItem
from collection_snapshot import CollectionSnapshot, CollectionSnapshotManager
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord
from persistence_manager import AppState, PersistenceManager
from photo_vault import PhotoRecord
from smart_shopping_assistant import ShoppingCandidate


def item(item_id, year="1900", grade="VF-20"):
    return CoinItem(
        id=item_id,
        image_path="",
        country="Newfoundland",
        denomination="20 cents",
        year=year,
        grade=grade,
        notes="",
        date_added="2026-06-18",
    )


class TestCollectionSnapshotSystem(unittest.TestCase):
    def test_snapshot_creation(self):
        manager = CollectionSnapshotManager()
        snapshot = manager.create_snapshot([item("1")])

        self.assertEqual(snapshot.collection_size, 1)
        self.assertGreaterEqual(snapshot.quality_score, 0)
        self.assertGreaterEqual(snapshot.integrity_score, 0)

    def test_snapshot_persistence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CollectionSnapshotManager(os.path.join(temp_dir, "snapshots.json"))
            snapshot = CollectionSnapshot("2026-06-18 10:00:00", collection_size=5, quality_score=70)

            manager.save_snapshot(snapshot)
            loaded = manager.load_snapshots()

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].collection_size, 5)

    def test_snapshot_comparison(self):
        manager = CollectionSnapshotManager()
        previous = CollectionSnapshot("2026-06-18 10:00:00", collection_size=5, quality_score=70, integrity_score=80, photo_coverage=10)
        current = CollectionSnapshot("2026-06-18 11:00:00", collection_size=7, quality_score=74, integrity_score=83, photo_coverage=25)

        report = manager.compare_snapshots(current, previous, previous)

        self.assertEqual(report.growth_summary.growth_since_last_snapshot, 2)
        self.assertEqual(report.quality_delta, 4)
        self.assertEqual(report.integrity_delta, 3)
        self.assertEqual(report.photo_coverage_delta, 15)

    def test_growth_since_first_snapshot(self):
        manager = CollectionSnapshotManager()
        first = CollectionSnapshot("first", collection_size=2)
        previous = CollectionSnapshot("previous", collection_size=4)
        current = CollectionSnapshot("current", collection_size=9)

        report = manager.compare_snapshots(current, previous, first)

        self.assertEqual(report.growth_summary.growth_since_last_snapshot, 5)
        self.assertEqual(report.growth_summary.growth_since_first_snapshot, 7)

    def test_series_delta_and_new_completion(self):
        manager = CollectionSnapshotManager()
        previous = CollectionSnapshot("previous", series_completion_metrics={"Newfoundland 20 Cents": 80.0})
        current = CollectionSnapshot("current", series_completion_metrics={"Newfoundland 20 Cents": 100.0})

        report = manager.compare_snapshots(current, previous, previous)

        self.assertEqual(len(report.series_progress), 1)
        self.assertEqual(report.series_progress[0].completion_delta, 20.0)
        self.assertTrue(report.series_progress[0].newly_completed)

    def test_photo_delta_from_created_snapshots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            photo_path = os.path.join(temp_dir, "coin.jpg")
            with open(photo_path, "wb") as handle:
                handle.write(b"photo")
            manager = CollectionSnapshotManager(os.path.join(temp_dir, "snapshots.json"))
            previous = manager.create_snapshot([item("1")], photo_records=[])
            current = manager.create_snapshot(
                [item("1")],
                photo_records=[PhotoRecord(photo_path, "Collection Photo", linked_collection_item_id="1")],
            )

            report = manager.compare_snapshots(current, previous, previous)

            self.assertGreater(report.photo_coverage_delta, 0)

    def test_market_and_shopping_counts(self):
        manager = CollectionSnapshotManager()
        market = MarketAwarenessEngine(
            observations=[ObservedPriceRecord("Newfoundland 20 cents 1900", "Newfoundland", "20 cents", "1900")]
        )
        snapshot = manager.create_snapshot(
            [item("1")],
            market_awareness_engine=market,
            shopping_candidates=[ShoppingCandidate("Newfoundland 20 cents 1904")],
        )

        self.assertEqual(snapshot.market_record_count, 1)
        self.assertEqual(snapshot.shopping_candidate_count, 1)

    def test_export_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CollectionSnapshotManager(os.path.join(temp_dir, "snapshots.json"))
            report = manager.compare_snapshots(
                CollectionSnapshot("current", collection_size=2, quality_score=80),
                CollectionSnapshot("previous", collection_size=1, quality_score=75),
            )
            md_path = os.path.join(temp_dir, "snapshot.md")
            csv_path = os.path.join(temp_dir, "snapshot.csv")

            self.assertTrue(report.export_markdown(md_path))
            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(os.path.exists(md_path))
            self.assertTrue(os.path.exists(csv_path))

    def test_snapshot_backup_eligible(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = os.path.join(temp_dir, "collection_data", "app_state")
            snapshot_path = os.path.join(state_dir, "collection_snapshots.json")
            collection_json = os.path.join(temp_dir, "data", "collection.json")
            os.makedirs(os.path.dirname(collection_json), exist_ok=True)
            with open(collection_json, "w", encoding="utf-8") as handle:
                handle.write('[{"id": "1"}]\n')
            persistence = PersistenceManager(state_dir=state_dir)
            persistence.save_state(AppState())
            manager = CollectionSnapshotManager(snapshot_path)
            manager.save_snapshot(CollectionSnapshot("current", collection_size=1))
            backup = BackupManager(
                backup_dir=os.path.join(temp_dir, "backups", "packages"),
                persistence_manager=persistence,
                collection_json_path=collection_json,
            )

            result = backup.create_backup_package()

            self.assertTrue(result.success)
            with zipfile.ZipFile(result.package_path, "r") as archive:
                self.assertIn("collection_data/app_state/collection_snapshots.json", archive.namelist())


if __name__ == "__main__":
    unittest.main()
