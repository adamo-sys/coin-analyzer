"""GUI-facing acquisition validation, display, and disclosure tests."""

import inspect
import unittest
from decimal import Decimal
from unittest.mock import patch

from coin_collection import CoinItem
from coin_collection_gui import CoinCollectionGUI


def make_item(**overrides):
    values = {
        "id": "gui_acquisition",
        "image_path": "",
        "country": "Canada",
        "denomination": "5 cents",
        "year": "1926",
        "grade": "EF-40",
        "notes": "",
        "date_added": "2026-07-16T12:00:00",
    }
    values.update(overrides)
    return CoinItem(**values)


class AcquisitionGUITests(unittest.TestCase):
    def test_live_total_is_read_only_derived_text(self):
        values = {
            "purchase_price": "0.10",
            "shipping_cost": "0.20",
            "buyers_premium": "",
            "tax": "0",
            "purchase_currency": " cad ",
        }
        self.assertEqual("CAD 0.30", CoinCollectionGUI.acquisition_total_text(values))
        self.assertEqual("Not recorded", CoinCollectionGUI.acquisition_total_text({}))
        self.assertEqual("Invalid", CoinCollectionGUI.acquisition_total_text({"tax": "-1"}))

    def test_gui_parser_normalizes_values(self):
        parsed = CoinCollectionGUI.acquisition_values_from_text({
            "acquisition_date": "2026-07-01",
            "purchase_price": "10.500",
            "purchase_currency": " usd ",
            "purchase_source": "  Dealer  ",
            "shipping_cost": "",
            "buyers_premium": "2",
            "tax": "1.25",
        })
        self.assertEqual(Decimal("10.500"), parsed["purchase_price"])
        self.assertEqual("USD", parsed["purchase_currency"])
        self.assertEqual("Dealer", parsed["purchase_source"])
        self.assertIsNone(parsed["shipping_cost"])

    def test_gui_validation_delegates_to_backend_policy(self):
        sentinel = {"purchase_currency": "CAD"}
        with patch("coin_collection_gui.normalize_acquisition_values", return_value=sentinel) as normalize:
            result = CoinCollectionGUI.acquisition_values_from_text({"purchase_currency": " cad "})
        self.assertIs(sentinel, result)
        normalize.assert_called_once_with({"purchase_currency": " cad "})

    def test_view_details_omits_empty_acquisition_section(self):
        details = CoinCollectionGUI.item_details_text(make_item())
        self.assertNotIn("--- Acquisition Details ---", details)

    def test_view_details_shows_only_recorded_acquisition_values_and_total(self):
        details = CoinCollectionGUI.item_details_text(make_item(
            acquisition_date="2026-07-01",
            purchase_price="100.00",
            purchase_currency="CAD",
            shipping_cost=None,
            buyers_premium="20.5",
            tax="0",
        ))
        self.assertIn("--- Acquisition Details ---", details)
        self.assertIn("Acquisition Date: 2026-07-01", details)
        self.assertIn("Purchase Price: 100.00", details)
        self.assertNotIn("Shipping Cost:", details)
        self.assertIn("Tax: 0", details)
        self.assertIn("Total Cost: CAD 120.50", details)

    def test_main_form_disclosure_is_collapsed_by_default(self):
        source = inspect.getsource(CoinCollectionGUI.create_widgets)
        self.assertIn("acquisition_expanded = tk.BooleanVar(value=False)", source)
        self.assertIn("acquisition_frame.grid_remove()", source)
        self.assertIn('text="Acquisition Details ▸"', source)

    def test_edit_form_expands_existing_acquisition_records(self):
        source = inspect.getsource(CoinCollectionGUI.open_edit_item_window)
        self.assertIn("tk.BooleanVar(value=item.has_acquisition_details())", source)
        self.assertIn("acquisition_frame.grid_remove()", source)


if __name__ == "__main__":
    unittest.main()
