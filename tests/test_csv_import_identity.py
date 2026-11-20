"""Synthetic regression coverage for stable CSV-import record identities."""

import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coin_collection import CoinCollection, CoinItem


class CsvImportIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.storage = self.root / "collection.json"
        self.csv_path = self.root / "import.csv"
        self.collection = CoinCollection(str(self.storage))

    def write_csv(self, rows: list[list[str]]) -> None:
        with self.csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Country", "Denomination", "Year", "Quantity", "Notes"])
            writer.writerows(rows)

    def test_import_preserves_legacy_id_and_record_when_length_would_collide(self) -> None:
        legacy = CoinItem(
            id="csv_import_1_0", image_path="", country="Canada",
            denomination="1 cent", year="1967", grade="VF-20",
            notes="Collector-entered details", date_added="2026-01-01",
            reference="Synthetic reference", from_numista=True,
        )
        self.assertTrue(self.collection.add_item(legacy))
        before = json.loads(self.storage.read_text(encoding="utf-8"))[0]
        self.write_csv([["Canada", "5 cents", "1926", "1", "Imported details"]])

        self.assertEqual((1, 2, 1, 2), self.collection.import_from_csv(str(self.csv_path)))

        records = json.loads(self.storage.read_text(encoding="utf-8"))
        self.assertEqual(before, records[0])
        self.assertNotEqual("csv_import_1_0", records[1]["id"])
        self.assertEqual("Imported details", records[1]["notes"])
        self.collection.load_collection()
        self.assertTrue(self.collection.update_item(legacy.id, {"grade": "EF-40"}))
        self.assertEqual("", self.collection.last_save_error)
        self.assertEqual("", self.collection.items[1].grade)

    def test_import_delete_reimport_keeps_each_quantity_copy_independently_editable(self) -> None:
        self.write_csv([
            ["Canada", "1 cent", "1967", "2", "First row"],
            ["Canada", "5 cents", "1926", "2", "Second row"],
        ])
        self.assertEqual((4, 4, 1, 2), self.collection.import_from_csv(str(self.csv_path)))
        removed_id = self.collection.items[0].id
        self.assertTrue(self.collection.delete_item(removed_id))
        survivors = [item.to_dict() for item in self.collection.items]
        self.write_csv([["Canada", "25 cents", "1973", "2", "Later import"]])

        self.assertEqual((2, 5, 1, 3), self.collection.import_from_csv(str(self.csv_path)))

        self.collection.load_collection()
        ids = [item.id for item in self.collection.items]
        self.assertEqual(5, len(set(ids)))
        self.assertEqual(survivors, [item.to_dict() for item in self.collection.items[:3]])
        target_id = self.collection.items[-1].id
        self.assertTrue(self.collection.update_item(target_id, {"grade": "MS-60"}))
        self.assertEqual(["", "", "", "", "MS-60"], [item.grade for item in self.collection.items])
        self.assertTrue(self.collection.delete_item(target_id))
        self.assertEqual(4, len(self.collection.items))
        self.assertEqual(4, len(json.loads(self.storage.read_text(encoding="utf-8"))))

    def test_identity_allocation_failure_rolls_back_partial_import(self) -> None:
        self.write_csv([["Canada", "1 cent", "1967", "1", "Existing record"]])
        self.assertEqual(1, self.collection.import_from_csv(str(self.csv_path))[0])
        before = self.storage.read_bytes()
        original_items = list(self.collection.items)
        self.write_csv([["Canada", "5 cents", "1926", "2", "New records"]])

        with patch.object(
            self.collection, "generate_item_id",
            side_effect=["synthetic-new-id", RuntimeError("Identity allocation failed")],
        ):
            result = self.collection.import_from_csv(str(self.csv_path))

        self.assertEqual((0, 0, 0, 0), result)
        self.assertEqual(before, self.storage.read_bytes())
        self.assertEqual(original_items, self.collection.items)
        self.assertIn("Identity allocation failed", self.collection.last_save_error)


if __name__ == "__main__":
    unittest.main()
