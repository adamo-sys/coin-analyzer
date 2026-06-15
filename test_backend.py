"""
Unit tests for the collection storage backend.

These tests use temporary files only. They must never read from or write to
data/collection.json.
"""

import csv
import json
import os
import tempfile
import unittest
from datetime import datetime

from coin_collection import CoinCollection, CoinItem


def make_coin_item(item_id="test_001", **overrides):
    """Create a valid CoinItem for tests."""
    values = {
        "id": item_id,
        "image_path": "test_coins/IMG_3460.jpeg",
        "country": "Canada",
        "denomination": "Quarter",
        "year": "2023",
        "grade": "VF-20",
        "notes": "Test coin",
        "date_added": datetime.now().isoformat(),
        "auto_detected": False,
        "detection_confidence": 0.0,
    }
    values.update(overrides)
    return CoinItem(**values)


class TestCoinCollectionBackend(unittest.TestCase):
    """Verify persistence, CRUD, and export behavior."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.collection_path = os.path.join(self.temp_dir.name, "collection.json")
        self.export_path = os.path.join(self.temp_dir.name, "collection_export.csv")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_data_persistence_saves_and_loads_json(self):
        collection = CoinCollection(self.collection_path)
        collection.add_item(make_coin_item(country="Canada"))

        reloaded = CoinCollection(self.collection_path)

        self.assertEqual(len(reloaded.items), 1)
        self.assertEqual(reloaded.items[0].country, "Canada")

    def test_json_loading_preserves_multiple_items(self):
        collection = CoinCollection(self.collection_path)
        collection.items = [
            make_coin_item(f"test_json_{i:03d}", year=str(2020 + i))
            for i in range(5)
        ]
        collection.save_collection()

        with open(self.collection_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        reloaded = CoinCollection(self.collection_path)

        self.assertEqual(len(data), 5)
        self.assertTrue(all("country" in item for item in data))
        self.assertEqual(len(reloaded.items), 5)

    def test_csv_export_writes_expected_rows(self):
        collection = CoinCollection(self.collection_path)
        collection.add_item(make_coin_item("test_csv", denomination="Quarter"))

        result = collection.export_to_csv(self.export_path)

        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.export_path))
        with open(self.export_path, "r", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["country"], "Canada")
        self.assertEqual(rows[0]["denomination"], "Quarter")

    def test_collection_operations_add_update_and_delete(self):
        collection = CoinCollection(self.collection_path)
        collection.add_item(make_coin_item("test_ops"))

        updated = collection.update_item(
            "test_ops",
            {"country": "United States", "year": "2024"},
        )
        deleted = collection.delete_item("test_ops")

        self.assertTrue(updated)
        self.assertTrue(deleted)
        self.assertEqual(collection.items, [])

    def test_image_path_is_preserved_after_reload(self):
        collection = CoinCollection(self.collection_path)
        image_path = "test_coins/IMG_3460.jpeg"
        collection.add_item(make_coin_item("test_image", image_path=image_path))

        reloaded = CoinCollection(self.collection_path)

        self.assertEqual(reloaded.items[0].image_path, image_path)

    def test_unicode_notes_survive_json_and_csv(self):
        special_notes = "Test with special chars: \u00e9, \u00f1, \u4e2d\u6587"
        collection = CoinCollection(self.collection_path)
        collection.add_item(make_coin_item("test_special", notes=special_notes))

        reloaded = CoinCollection(self.collection_path)
        reloaded.export_to_csv(self.export_path)

        with open(self.export_path, "r", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(reloaded.items[0].notes, special_notes)
        self.assertEqual(rows[0]["notes"], special_notes)


if __name__ == "__main__":
    unittest.main()
