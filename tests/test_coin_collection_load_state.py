"""Fail-closed tests for the authoritative collection load-state boundary."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from coin_collection import CollectionLoadState, CoinCollection, CoinItem
from collection_management.collection_mutation_repository import (
    ConditionalCollectionFieldChange,
    ConditionalCollectionRepositoryError,
)


def item(item_id: str, *, country: str = "Canada") -> CoinItem:
    return CoinItem(
        id=item_id,
        image_path="",
        country=country,
        denomination="Cent",
        year="2000",
        grade="",
        notes="",
        date_added="2026-08-30T00:00:00",
        auto_detected=False,
        detection_confidence=0.0,
    )


class CollectionLoadStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "collection.json"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_json(self, payload: object) -> bytes:
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        return self.path.read_bytes()

    def assert_invalid_source_is_unchanged(self, source: bytes) -> CoinCollection:
        collection = CoinCollection(str(self.path))
        self.assertEqual(
            CollectionLoadState.INVALID_OR_UNSUPPORTED,
            collection.load_state,
        )
        self.assertTrue(collection.load_error)
        self.assertEqual([], collection.items)
        self.assertEqual(source, self.path.read_bytes())
        return collection

    def assert_mutations_are_blocked(
        self, collection: CoinCollection, source: bytes
    ) -> None:
        collection.items = [item("existing")]

        self.assertFalse(collection.add_item(item("new")))
        self.assertFalse(collection.update_item("existing", {"country": "France"}))
        self.assertFalse(collection.delete_item("existing"))
        self.assertFalse(collection.save_collection())

        self.assertEqual(["existing"], [entry.id for entry in collection.items])
        self.assertEqual("Canada", collection.items[0].country)
        self.assertIn("INVALID_OR_UNSUPPORTED", collection.last_save_error)
        self.assertEqual(source, self.path.read_bytes())

    def test_missing_collection_allows_first_save_and_becomes_valid(self) -> None:
        collection = CoinCollection(str(self.path))

        self.assertEqual(CollectionLoadState.MISSING, collection.load_state)
        self.assertEqual("", collection.load_error)
        self.assertFalse(self.path.exists())

        self.assertTrue(collection.add_item(item("first")))
        self.assertEqual(CollectionLoadState.VALID, collection.load_state)
        self.assertEqual(["first"], [entry.id for entry in collection.items])
        self.assertTrue(self.path.is_file())

    def test_valid_collection_loads_and_allows_mutation(self) -> None:
        self.write_json([item("existing").to_dict()])

        collection = CoinCollection(str(self.path))

        self.assertEqual(CollectionLoadState.VALID, collection.load_state)
        self.assertEqual("", collection.load_error)
        self.assertTrue(collection.update_item("existing", {"country": "France"}))
        self.assertEqual("France", CoinCollection(str(self.path)).items[0].country)

    def test_malformed_json_fails_closed_and_blocks_mutations(self) -> None:
        source = b'{"id":'
        self.path.write_bytes(source)

        collection = self.assert_invalid_source_is_unchanged(source)
        self.assert_mutations_are_blocked(collection, source)

    def test_non_array_root_fails_closed(self) -> None:
        source = self.write_json({"items": []})

        collection = self.assert_invalid_source_is_unchanged(source)

        self.assertIn("root must be an array", collection.load_error)
        self.assertFalse(collection.save_collection())
        self.assertEqual(source, self.path.read_bytes())

    def test_structurally_invalid_record_fails_closed(self) -> None:
        source = self.write_json([42])

        collection = self.assert_invalid_source_is_unchanged(source)

        self.assertIn("record 0 must be an object", collection.load_error)
        self.assertFalse(collection.add_item(item("replacement")))
        self.assertEqual(source, self.path.read_bytes())

    def test_duplicate_item_ids_fail_closed(self) -> None:
        source = self.write_json(
            [item("duplicate").to_dict(), item("duplicate").to_dict()]
        )

        collection = self.assert_invalid_source_is_unchanged(source)

        self.assertIn("duplicate item id", collection.load_error)
        self.assertFalse(collection.delete_item("duplicate"))
        self.assertEqual(source, self.path.read_bytes())

    def test_other_authoritative_write_paths_cannot_bypass_invalid_state(self) -> None:
        source = b"{not-json"
        self.path.write_bytes(source)
        collection = self.assert_invalid_source_is_unchanged(source)

        self.assertFalse(
            collection.replace_items_for_import(
                [item("replacement")],
                expected_baseline=object(),
                import_lock=object(),
            )
        )
        self.assertIn("INVALID_OR_UNSUPPORTED", collection.last_save_error)
        with self.assertRaises(ConditionalCollectionRepositoryError):
            collection.mutate_fields_conditionally(
                "existing",
                (
                    ConditionalCollectionFieldChange(
                        "country", "Canada", "France"
                    ),
                ),
            )
        self.assertIn("INVALID_OR_UNSUPPORTED", collection.last_save_error)
        self.assertEqual(source, self.path.read_bytes())


if __name__ == "__main__":
    unittest.main()
