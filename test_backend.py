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

from coin_collection import CoinCollection, CoinItem, ItemPhoto, PhotoRole


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

    def test_legacy_image_path_only_record_loads_and_synthesizes_photo(self):
        image_path = "coin_photos/collection/Canada/1920_front.jpg"
        legacy = make_coin_item("legacy_image", image_path=image_path).to_dict()
        legacy.pop("photos")
        with open(self.collection_path, "w", encoding="utf-8") as handle:
            json.dump([legacy], handle)

        collection = CoinCollection(self.collection_path)

        self.assertEqual(collection.items[0].image_path, image_path)
        photos = collection.items[0].normalized_photos()
        self.assertEqual(len(photos), 1)
        self.assertEqual(photos[0].path, image_path)
        self.assertTrue(photos[0].is_primary)

    def test_new_photos_only_record_loads_and_sets_primary_image_alias(self):
        record = make_coin_item("photos_only", image_path="").to_dict()
        record["image_path"] = ""
        record["photos"] = [
            {"path": "front.jpg", "role": "FRONT", "is_primary": True, "display_order": 0},
            {"path": "back.jpg", "role": "BACK", "display_order": 1},
        ]
        with open(self.collection_path, "w", encoding="utf-8") as handle:
            json.dump([record], handle)

        collection = CoinCollection(self.collection_path)

        self.assertEqual(collection.items[0].primary_image_path, "front.jpg")
        self.assertEqual(collection.items[0].to_dict()["image_path"], "front.jpg")

    def test_consistent_image_path_and_photos_round_trip_deterministically(self):
        item = make_coin_item(
            "consistent",
            image_path="front.jpg",
            photos=[
                ItemPhoto("back.jpg", PhotoRole.BACK, False, "", 1),
                ItemPhoto("front.jpg", PhotoRole.FRONT, True, "", 0),
            ],
        )
        collection = CoinCollection(self.collection_path)
        collection.add_item(item)

        reloaded = CoinCollection(self.collection_path)
        serialized = reloaded.items[0].to_dict()

        self.assertEqual(serialized["image_path"], "front.jpg")
        self.assertEqual([p["path"] for p in serialized["photos"]], ["front.jpg", "back.jpg"])
        self.assertEqual(sum(1 for p in serialized["photos"] if p["is_primary"]), 1)

    def test_conflicting_image_path_and_photos_prefer_primary_photo(self):
        item = make_coin_item(
            "conflict",
            image_path="legacy.jpg",
            photos=[ItemPhoto("primary.jpg", PhotoRole.FRONT, True, "", 0)],
        )

        self.assertEqual(item.primary_image_path, "primary.jpg")
        self.assertEqual(item.to_dict()["image_path"], "primary.jpg")

    def test_no_primary_photo_normalizes_first_photo(self):
        item = make_coin_item(
            "no_primary",
            image_path="",
            photos=[
                ItemPhoto("b.jpg", PhotoRole.BACK, False, "", 5),
                ItemPhoto("a.jpg", PhotoRole.FRONT, False, "", 1),
            ],
        )

        photos = item.normalized_photos()

        self.assertEqual(photos[0].path, "a.jpg")
        self.assertTrue(photos[0].is_primary)
        self.assertEqual(sum(1 for p in photos if p.is_primary), 1)

    def test_multiple_primary_photos_normalize_deterministically(self):
        item = make_coin_item(
            "multi_primary",
            image_path="",
            photos=[
                ItemPhoto("second.jpg", PhotoRole.BACK, True, "", 1),
                ItemPhoto("first.jpg", PhotoRole.FRONT, True, "", 0),
            ],
        )

        photos = item.normalized_photos()

        self.assertEqual(photos[0].path, "first.jpg")
        self.assertTrue(photos[0].is_primary)
        self.assertFalse(photos[1].is_primary)

    def test_malformed_photo_entries_do_not_prevent_collection_loading(self):
        record = make_coin_item("malformed", image_path="legacy.jpg").to_dict()
        record["photos"] = [
            {"path": ""},
            "string-photo.jpg",
            123,
            {"file_path": "file-path-photo.jpg", "role": "OBVERSE"},
        ]
        with open(self.collection_path, "w", encoding="utf-8") as handle:
            json.dump([record], handle)

        collection = CoinCollection(self.collection_path)
        photos = collection.items[0].normalized_photos()
        paths = [photo.path for photo in photos]

        self.assertEqual(paths, ["string-photo.jpg", "file-path-photo.jpg"])
        self.assertEqual(photos[1].role, PhotoRole.FRONT)

    def test_unknown_json_keys_do_not_break_collection_loading(self):
        record = make_coin_item("unknown_keys").to_dict()
        record["unexpected"] = "ignored"
        with open(self.collection_path, "w", encoding="utf-8") as handle:
            json.dump([record], handle)

        collection = CoinCollection(self.collection_path)

        self.assertEqual(len(collection.items), 1)
        self.assertEqual(collection.items[0].id, "unknown_keys")

    def test_photo_migration_preview_and_apply_are_idempotent(self):
        collection = CoinCollection(self.collection_path)
        collection.items = [
            make_coin_item("legacy", image_path="legacy.jpg"),
            make_coin_item("blank", image_path=""),
        ]

        preview = collection.preview_photo_migration()
        first_apply = collection.apply_photo_migration()
        second_apply = collection.apply_photo_migration()

        self.assertEqual(preview.legacy_image_path_items, 1)
        self.assertEqual(first_apply.migrated_items, 1)
        self.assertEqual(second_apply.migrated_items, 0)
        self.assertEqual(collection.items[0].photos[0].path, "legacy.jpg")

    def test_csv_export_preserves_shape_and_primary_image_path(self):
        collection = CoinCollection(self.collection_path)
        collection.add_item(make_coin_item(
            "csv_photo",
            image_path="legacy.jpg",
            photos=[ItemPhoto("primary.jpg", PhotoRole.FRONT, True, "", 0)],
        ))

        self.assertTrue(collection.export_to_csv(self.export_path))
        with open(self.export_path, "r", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(rows[0]["image_path"], "primary.jpg")
        self.assertNotIn("photos", rows[0])


if __name__ == "__main__":
    unittest.main()
