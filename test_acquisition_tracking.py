"""Focused tests for collection-item acquisition tracking."""

import csv
import json
import os
import tempfile
import unittest
from decimal import Decimal

from coin_collection import CoinCollection, CoinItem


def make_item(item_id="acquisition_item", **overrides):
    values = {
        "id": item_id,
        "image_path": "coin.jpg",
        "country": "Canada",
        "denomination": "5 cents",
        "year": "1926",
        "grade": "EF-40",
        "notes": "",
        "date_added": "2026-07-16T12:00:00",
    }
    values.update(overrides)
    return CoinItem(**values)


class AcquisitionTrackingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.collection_path = os.path.join(self.temp_dir.name, "collection.json")
        self.csv_path = os.path.join(self.temp_dir.name, "collection.csv")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_old_record_loads_without_acquisition_fields_or_file_modification(self):
        record = make_item().to_dict()
        for key in (
            "acquisition_date",
            "purchase_price",
            "purchase_currency",
            "purchase_source",
            "shipping_cost",
            "buyers_premium",
            "tax",
        ):
            record.pop(key, None)
        original = json.dumps([record], indent=2).encode("utf-8")
        with open(self.collection_path, "wb") as handle:
            handle.write(original)

        collection = CoinCollection(self.collection_path)

        with open(self.collection_path, "rb") as handle:
            self.assertEqual(original, handle.read())
        self.assertIsNone(collection.items[0].purchase_currency)
        self.assertIsNone(collection.items[0].total_cost)

    def test_all_acquisition_fields_save_and_reload_exactly(self):
        item = make_item(
            acquisition_date="2026-07-01",
            purchase_price="100.1200",
            purchase_currency=" usd ",
            purchase_source="  Heritage Auction  ",
            shipping_cost="12.345",
            buyers_premium="20.00",
            tax="3.4",
        )
        collection = CoinCollection(self.collection_path)
        self.assertTrue(collection.add_item(item))

        with open(self.collection_path, "r", encoding="utf-8") as handle:
            stored = json.load(handle)[0]
        reloaded = CoinCollection(self.collection_path).items[0]

        self.assertEqual("100.1200", stored["purchase_price"])
        self.assertEqual("12.345", stored["shipping_cost"])
        self.assertNotIn("total_cost", stored)
        self.assertEqual("USD", reloaded.purchase_currency)
        self.assertEqual("Heritage Auction", reloaded.purchase_source)
        self.assertEqual(Decimal("135.8650"), reloaded.total_cost)

    def test_acquisition_date_requires_strict_real_iso_date(self):
        self.assertEqual("2024-02-29", make_item(acquisition_date="2024-02-29").acquisition_date)
        for invalid in ("2024-2-29", "02/29/2024", "2023-02-29", "2024-13-01"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    make_item(acquisition_date=invalid)

    def test_total_cost_distinguishes_blank_from_explicit_zero(self):
        self.assertIsNone(make_item().total_cost)
        self.assertEqual(Decimal("0"), make_item(purchase_price="0").total_cost)
        self.assertEqual(
            Decimal("13.375"),
            make_item(purchase_price="10.125", shipping_cost=None, buyers_premium="2", tax="1.25").total_cost,
        )

    def test_invalid_negative_boolean_and_non_finite_money_is_rejected(self):
        for invalid in (True, False, "not-money", "NaN", "Infinity", "-0.01"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    make_item(purchase_price=invalid)

    def test_currency_defaults_normalizes_and_validates(self):
        self.assertEqual("CAD", make_item().purchase_currency)
        self.assertEqual("GBP", make_item(purchase_currency=" gbp ").purchase_currency)
        self.assertIsNone(make_item(purchase_currency="").purchase_currency)
        for invalid in ("CA", "US12", "EURO", True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    make_item(purchase_currency=invalid)

    def test_editing_existing_record_updates_acquisition_fields_and_rejects_invalid(self):
        collection = CoinCollection(self.collection_path)
        collection.add_item(make_item("edit_me", purchase_currency=None))

        self.assertTrue(collection.update_item("edit_me", {
            "acquisition_date": "2026-06-30",
            "purchase_price": "40.00",
            "purchase_currency": "cad",
            "shipping_cost": "5.50",
        }))
        self.assertEqual(Decimal("45.50"), CoinCollection(self.collection_path).items[0].total_cost)

        self.assertFalse(collection.update_item("edit_me", {"country": "Mutated", "tax": "-1"}))
        self.assertIsNone(collection.get_item("edit_me").tax)
        self.assertEqual("Canada", collection.get_item("edit_me").country)

    def test_csv_export_includes_exact_components_and_derived_total(self):
        collection = CoinCollection(self.collection_path)
        collection.items = [
            make_item("priced", purchase_price="0.10", shipping_cost="0.20", tax="0"),
            make_item("unpriced", purchase_currency=None),
        ]

        self.assertTrue(collection.export_to_csv(self.csv_path))
        with open(self.csv_path, "r", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual("0.10", rows[0]["purchase_price"])
        self.assertEqual("0.30", rows[0]["total_cost"])
        self.assertEqual("0", rows[0]["tax"])
        self.assertEqual("", rows[1]["total_cost"])
        self.assertEqual("", rows[1]["purchase_currency"])


if __name__ == "__main__":
    unittest.main()
