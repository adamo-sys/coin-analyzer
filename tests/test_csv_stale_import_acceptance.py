"""Acceptance coverage for CSV imports when collection storage changes elsewhere."""

from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from coin_collection import CoinCollection
from coin_collection_gui import CoinCollectionGUI


class CsvStaleImportAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.collection_path = self.root / "collection.json"
        self.csv_path = self.root / "import.csv"

        self._write_collection(
            [
                {
                    "id": "seed",
                    "image_path": "",
                    "country": "Canada",
                    "denomination": "1 cent",
                    "year": "1967",
                    "grade": "VF-20",
                    "notes": "seed",
                    "date_added": "2026-09-07",
                }
            ]
        )
        with self.csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                ["Country", "Denomination", "Year", "Grade", "Quantity", "Notes"]
            )
            writer.writerow(["Canada", "5 cents", "1926", "EF-40", "1", "Near 6"])

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_collection(self, records: list[dict[str, str]]) -> None:
        self.collection_path.write_text(
            json.dumps(records, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _replace_storage_elsewhere(self) -> bytes:
        records = json.loads(self.collection_path.read_text(encoding="utf-8"))
        records.append(
            {
                "id": "external",
                "image_path": "",
                "country": "Canada",
                "denomination": "25 cents",
                "year": "1973",
                "grade": "EF-40",
                "notes": "competing window",
                "date_added": "2026-09-07",
            }
        )
        self._write_collection(records)
        return self.collection_path.read_bytes()

    def test_stale_csv_import_preserves_external_bytes_and_rolls_back_memory(self) -> None:
        collection = CoinCollection(str(self.collection_path))
        original_ids = [item.id for item in collection.items]
        external_bytes = self._replace_storage_elsewhere()

        result = collection.import_from_csv(str(self.csv_path))

        self.assertEqual((0, 0, 0, 0), result)
        self.assertEqual(external_bytes, self.collection_path.read_bytes())
        self.assertEqual(original_ids, [item.id for item in collection.items])
        self.assertIn("changed outside this window", collection.last_save_error)
        self.assertIn("Reload", collection.last_save_error)

    def test_explicit_reload_allows_csv_retry_after_stale_rejection(self) -> None:
        collection = CoinCollection(str(self.collection_path))
        external_bytes = self._replace_storage_elsewhere()

        first_result = collection.import_from_csv(str(self.csv_path))
        self.assertEqual((0, 0, 0, 0), first_result)
        self.assertEqual(external_bytes, self.collection_path.read_bytes())

        collection.load_collection()
        retry_result = collection.import_from_csv(str(self.csv_path))

        self.assertEqual(1, retry_result[0])
        self.assertEqual("", collection.last_save_error)
        self.assertEqual(3, len(collection.items))
        persisted = json.loads(self.collection_path.read_text(encoding="utf-8"))
        self.assertEqual(3, len(persisted))
        self.assertTrue(
            any(
                record.get("country") == "Canada"
                and record.get("denomination") == "5 cents"
                and record.get("year") == "1926"
                for record in persisted
            )
        )

    def test_gui_reports_stale_csv_import_as_failure_not_success(self) -> None:
        collection = CoinCollection(str(self.collection_path))
        external_bytes = self._replace_storage_elsewhere()

        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = object()
        gui.app = SimpleNamespace(
            collection=collection,
            import_from_csv=collection.import_from_csv,
        )
        gui.refresh_collection_list = Mock()

        with (
            patch(
                "coin_collection_gui.filedialog.askopenfilename",
                return_value=str(self.csv_path),
            ),
            patch("coin_collection_gui.messagebox.showerror") as showerror,
            patch("coin_collection_gui.messagebox.showinfo") as showinfo,
        ):
            gui.import_collection_csv()

        self.assertEqual(external_bytes, self.collection_path.read_bytes())
        showinfo.assert_not_called()
        showerror.assert_called_once()
        title, message = showerror.call_args.args[:2]
        self.assertEqual("Collection Import Failed", title)
        self.assertIn("not saved", message)
        self.assertIn("Reload", message)
        gui.refresh_collection_list.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
