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
from unittest.mock import patch
from uuid import UUID

from coin_collection import CoinCollection, CoinCollectionApp, CoinItem, ItemPhoto, PhotoRole


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

    def test_default_collection_path_is_created_on_first_save(self):
        original_working_directory = os.getcwd()
        try:
            os.chdir(self.temp_dir.name)
            default_collection_path = os.path.join("data", "collection.json")

            app = CoinCollectionApp()

            self.assertEqual([], app.collection.items)
            self.assertFalse(os.path.exists(default_collection_path))
            self.assertTrue(app.collection.save_collection())
            self.assertTrue(os.path.isfile(default_collection_path))
            with open(default_collection_path, "r", encoding="utf-8") as handle:
                self.assertEqual(
                    {"schema_version": 1, "items": []}, json.load(handle)
                )
        finally:
            os.chdir(original_working_directory)

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

        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(len(data["items"]), 5)
        self.assertTrue(all("country" in item for item in data["items"]))
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

    def test_atomic_save_replaces_existing_collection(self):
        with open(self.collection_path, "w", encoding="utf-8") as handle:
            handle.write('[{"id": "old"}]')
        collection = CoinCollection(self.collection_path)
        collection.items = [make_coin_item("replacement", notes="Montreal - \u00e9dition")]

        self.assertTrue(collection.save_collection())

        with open(self.collection_path, "r", encoding="utf-8") as handle:
            saved = json.load(handle)
        self.assertEqual(1, saved["schema_version"])
        self.assertEqual("replacement", saved["items"][0]["id"])
        self.assertEqual("Montreal - \u00e9dition", saved["items"][0]["notes"])
        self.assertEqual([], [name for name in os.listdir(self.temp_dir.name) if name.endswith(".tmp")])

    def test_serialization_failure_preserves_existing_collection(self):
        original = b'[{"id":"original"}]'
        with open(self.collection_path, "wb") as handle:
            handle.write(original)
        collection = CoinCollection(self.collection_path)
        collection.items = [make_coin_item("bad", notes=object())]

        self.assertFalse(collection.save_collection())

        with open(self.collection_path, "rb") as handle:
            self.assertEqual(original, handle.read())
        self.assertEqual([], [name for name in os.listdir(self.temp_dir.name) if name.endswith(".tmp")])

    @patch("atomic_json.json.dump", side_effect=OSError("simulated disk write failure"))
    def test_write_failure_preserves_existing_collection_and_cleans_temp_file(self, _dump):
        original = b'[{"id":"original"}]'
        with open(self.collection_path, "wb") as handle:
            handle.write(original)
        collection = CoinCollection(self.collection_path)
        collection.items = [make_coin_item("replacement")]

        self.assertFalse(collection.save_collection())

        with open(self.collection_path, "rb") as handle:
            self.assertEqual(original, handle.read())
        self.assertEqual([], [name for name in os.listdir(self.temp_dir.name) if name.endswith(".tmp")])

    @patch("atomic_json.os.replace", side_effect=OSError("simulated replacement failure"))
    def test_replace_failure_preserves_existing_collection_and_cleans_temp_file(self, _replace):
        original = b'[{"id":"original"}]'
        with open(self.collection_path, "wb") as handle:
            handle.write(original)
        collection = CoinCollection(self.collection_path)
        collection.items = [make_coin_item("replacement")]

        self.assertFalse(collection.save_collection())

        with open(self.collection_path, "rb") as handle:
            self.assertEqual(original, handle.read())
        self.assertEqual([], [name for name in os.listdir(self.temp_dir.name) if name.endswith(".tmp")])

    def test_failed_mutations_restore_in_memory_collection(self):
        collection = CoinCollection(self.collection_path)
        original = make_coin_item("original", country="Canada")
        self.assertTrue(collection.add_item(original))

        with patch("atomic_json.os.replace", side_effect=OSError("simulated replacement failure")):
            self.assertFalse(collection.add_item(make_coin_item("new")))
            self.assertFalse(collection.update_item("original", {"country": "United States"}))
            self.assertFalse(collection.delete_item("original"))

        self.assertEqual(["original"], [item.id for item in collection.items])
        self.assertEqual("Canada", collection.get_item("original").country)

    def test_injected_collection_path_remains_isolated(self):
        collection = CoinCollection(self.collection_path)
        app = CoinCollectionApp(collection=collection)
        source_path = os.path.join(self.temp_dir.name, "temporary-front.jpg")
        with open(source_path, "wb") as handle:
            handle.write(b"source photo")
        app.current_image_path = source_path

        self.assertTrue(app.add_to_collection("Canada", "Cent", "1920", "VF-20", "isolated"))
        self.assertTrue(os.path.exists(self.collection_path))

    def test_generate_item_id_is_unique_across_rapid_calls(self):
        collection = CoinCollection(self.collection_path)

        generated = [collection.generate_item_id() for _ in range(1_000)]

        self.assertEqual(len(generated), len(set(generated)))
        for item_id in generated:
            self.assertRegex(item_id, r"^coin_[0-9a-f]{32}$")

    @patch("coin_collection.uuid4")
    def test_generate_item_id_retries_an_existing_collection_id(self, mock_uuid4):
        collision = UUID("00000000-0000-4000-8000-000000000001")
        replacement = UUID("00000000-0000-4000-8000-000000000002")
        collection = CoinCollection(self.collection_path)
        collection.items = [make_coin_item(f"coin_{collision.hex}")]
        mock_uuid4.side_effect = [collision, replacement]

        self.assertEqual(f"coin_{replacement.hex}", collection.generate_item_id())
        self.assertEqual(2, mock_uuid4.call_count)

    @patch("coin_collection.uuid4")
    def test_generate_item_id_fails_closed_after_repeated_collisions(self, mock_uuid4):
        collision = UUID("00000000-0000-4000-8000-000000000001")
        collection = CoinCollection(self.collection_path)
        collection.items = [make_coin_item(f"coin_{collision.hex}")]
        mock_uuid4.return_value = collision

        with self.assertRaisesRegex(RuntimeError, "Unable to generate a unique coin item ID"):
            collection.generate_item_id()

        self.assertEqual(10, mock_uuid4.call_count)

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
