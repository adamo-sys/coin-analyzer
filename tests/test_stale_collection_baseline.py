"""Deterministic stale ordinary-save and Numista replacement protection tests."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from coin_collection import CoinCollection, CoinItem, CollectionLoadState
from numista_importer import NumistaImporter


def item(item_id: str, *, country: str = "Canada") -> CoinItem:
    return CoinItem(
        id=item_id,
        image_path="",
        country=country,
        denomination="25 cents",
        year="1967",
        grade="VF-20",
        notes="",
        date_added="2026-09-07T00:00:00",
    )


class StaleOrdinaryCollectionSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "collection.json"

    def seeded_pair(self):
        first = CoinCollection(str(self.path))
        self.assertTrue(first.add_item(item("seed")))
        second = CoinCollection(str(self.path))
        return first, second

    def test_existing_unchanged_save_and_repeated_own_save_succeed(self):
        first, _ = self.seeded_pair()
        self.assertTrue(first.save_collection())
        self.assertTrue(first.add_item(item("second")))
        self.assertTrue(first.save_collection())
        self.assertEqual([row["id"] for row in json.loads(self.path.read_text("utf-8"))], ["seed", "second"])

    def test_missing_first_run_first_save_succeeds(self):
        collection = CoinCollection(str(self.path))
        self.assertEqual(collection.load_state, CollectionLoadState.MISSING)
        self.assertTrue(collection.add_item(item("first")))
        self.assertTrue(self.path.is_file())

    def test_stale_add_edit_and_delete_fail_without_changing_newer_bytes(self):
        for operation in ("add", "edit", "delete"):
            with self.subTest(operation=operation):
                first, stale = self.seeded_pair()
                self.assertTrue(first.add_item(item("newer")))
                newer_bytes = self.path.read_bytes()

                if operation == "add":
                    result = stale.add_item(item("stale-add"))
                elif operation == "edit":
                    result = stale.update_item("seed", {"country": "United States"})
                else:
                    result = stale.delete_item("seed")

                self.assertFalse(result)
                self.assertEqual(self.path.read_bytes(), newer_bytes)
                self.assertIn("changed outside this window", stale.last_save_error)
                self.assertIn("Reload", stale.last_save_error)

                # Restore the fixture for the next subtest.
                self.path.unlink(missing_ok=True)

    def test_disappeared_existing_storage_is_rejected(self):
        collection, _ = self.seeded_pair()
        self.path.unlink()
        self.assertFalse(collection.add_item(item("blocked")))
        self.assertFalse(self.path.exists())
        self.assertIn("Reload", collection.last_save_error)

    def test_storage_appearing_after_missing_load_is_rejected(self):
        collection = CoinCollection(str(self.path))
        external_bytes = b'[{"id":"external"}]'
        self.path.write_bytes(external_bytes)
        self.assertFalse(collection.add_item(item("blocked")))
        self.assertEqual(self.path.read_bytes(), external_bytes)
        self.assertIn("Reload", collection.last_save_error)

    def test_failed_stale_save_does_not_advance_baseline_and_reload_recovers(self):
        first, stale = self.seeded_pair()
        self.assertTrue(first.add_item(item("newer")))
        newer_bytes = self.path.read_bytes()

        self.assertFalse(stale.add_item(item("blocked-one")))
        self.assertFalse(stale.add_item(item("blocked-two")))
        self.assertEqual(self.path.read_bytes(), newer_bytes)

        stale.load_collection()
        self.assertEqual(stale.load_state, CollectionLoadState.LOADED)
        self.assertTrue(stale.add_item(item("after-reload")))
        ids = [row["id"] for row in json.loads(self.path.read_text("utf-8"))]
        self.assertEqual(ids, ["seed", "newer", "after-reload"])


class NumistaReplacementProtectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "collection.json"
        self.collection = CoinCollection(str(self.path))
        self.manual = item("manual")
        self.assertTrue(self.collection.add_item(self.manual))

    def frame(self):
        return pd.DataFrame(
            [
                {
                    "N# number (with link)": "N#123",
                    "Country": "Canada",
                    "Face value": "0.25",
                    "Currency": "Dollar",
                    "Year": 1967,
                    "Grade": "VF-20",
                    "Quantity": 1,
                }
            ]
        )

    def test_numista_publishes_complete_replacement_with_one_save(self):
        importer = NumistaImporter(self.collection)
        real_save = self.collection.save_collection
        calls = []

        def counted_save():
            calls.append(tuple(current.id for current in self.collection.items))
            return real_save()

        with patch("numista_importer.pd.read_excel", return_value=self.frame()), patch.object(
            self.collection, "save_collection", side_effect=counted_save
        ):
            imported, duplicates = importer.import_from_excel("synthetic.xlsx")

        self.assertEqual((imported, duplicates), (1, 0))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], ("numista_123", "manual"))

    def test_numista_save_failure_restores_memory_and_preserves_storage(self):
        importer = NumistaImporter(self.collection)
        original_bytes = self.path.read_bytes()
        original_items = list(self.collection.items)

        def fail_save():
            self.collection.last_save_error = "synthetic save failure"
            return False

        with patch("numista_importer.pd.read_excel", return_value=self.frame()), patch.object(
            self.collection, "save_collection", side_effect=fail_save
        ):
            with self.assertRaises(OSError):
                importer.import_from_excel("synthetic.xlsx")

        self.assertEqual(self.collection.items, original_items)
        self.assertEqual(self.path.read_bytes(), original_bytes)


if __name__ == "__main__":
    unittest.main()
