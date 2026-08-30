"""
Unit tests for CSV import functionality.
"""

import csv
import json
import os
import shutil
import tempfile
import unittest
from decimal import Decimal

from coin_collection import CoinCollection


FIXTURE_CSV = os.path.join(
    os.path.dirname(__file__),
    "test_data",
    "sample_import.csv",
)


class TestCSVImport(unittest.TestCase):
    """Test CSV import functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = self.temp_dir.name
        self.test_csv = os.path.join(self.test_dir, "test_collection.csv")
        self.collection_path = os.path.join(self.test_dir, "collection.json")
        shutil.copy(FIXTURE_CSV, self.test_csv)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    def test_csv_import_basic(self):
        """Test basic CSV import."""
        collection = CoinCollection(self.collection_path)
        
        # Import from CSV
        imported_count, total_coins, total_countries, total_unique_dates = collection.import_from_csv(self.test_csv)
        
        # Verify import
        self.assertEqual(imported_count, 4)  # 1 + 2 + 1 = 4 coins
        self.assertEqual(total_coins, 4)
        self.assertEqual(total_countries, 2)  # Canada and Newfoundland
        self.assertEqual(total_unique_dates, 3)  # 1967, 1968, 1909
        self.assertTrue(all(item.image_path == "" for item in collection.items))
        self.assertTrue(all(item.photos == [] for item in collection.items))
        self.assertTrue(all(item.purchase_currency is None for item in collection.items))
        self.assertTrue(all(item.total_cost is None for item in collection.items))
    
    def test_csv_import_with_missing_fields(self):
        """Test CSV import with missing required fields."""
        # Create a CSV with missing fields
        test_csv_missing = os.path.join(self.test_dir, "test_missing.csv")
        with open(test_csv_missing, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Country', 'Denomination', 'Year', 'Grade', 'Quantity', 'Notes'])
            writer.writerow(['Canada', '1 cent', '', 'VF-20', '1', 'Missing year'])  # Missing year
            writer.writerow(['', '1 cent', '1967', 'VF-20', '1', 'Missing country'])  # Missing country
            writer.writerow(['Canada', '', '1967', 'VF-20', '1', 'Missing denomination'])  # Missing denomination
            writer.writerow(['Canada', '1 cent', '1969', 'VF-20', '1', 'Valid'])  # Valid
        
        collection = CoinCollection(self.collection_path)
        imported_count, total_coins, total_countries, total_unique_dates = collection.import_from_csv(test_csv_missing)
        
        # Only the valid row should be imported
        self.assertEqual(imported_count, 1)
        self.assertEqual(total_coins, 1)
        

    def test_csv_import_with_quantity(self):
        """Test CSV import with quantity > 1."""
        test_csv_qty = os.path.join(self.test_dir, "test_quantity.csv")
        with open(test_csv_qty, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Country', 'Denomination', 'Year', 'Grade', 'Quantity', 'Notes'])
            writer.writerow(['Canada', '1 cent', '1967', 'VF-20', '5', 'Five coins'])
        
        collection = CoinCollection(self.collection_path)
        imported_count, total_coins, total_countries, total_unique_dates = collection.import_from_csv(test_csv_qty)
        
        # Should create 5 separate items
        self.assertEqual(imported_count, 5)
        self.assertEqual(total_coins, 5)
        

    def test_csv_import_empty_file(self):
        """Test CSV import with empty file."""
        test_csv_empty = os.path.join(self.test_dir, "test_empty.csv")
        with open(test_csv_empty, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Country', 'Denomination', 'Year', 'Grade', 'Quantity', 'Notes'])
        
        collection = CoinCollection(self.collection_path)
        imported_count, total_coins, total_countries, total_unique_dates = collection.import_from_csv(test_csv_empty)
        
        # No items should be imported
        self.assertEqual(imported_count, 0)
        self.assertEqual(total_coins, 0)
        

    def test_csv_import_invalid_quantity(self):
        """Test CSV import with invalid quantity."""
        test_csv_invalid_qty = os.path.join(self.test_dir, "test_invalid_qty.csv")
        with open(test_csv_invalid_qty, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Country', 'Denomination', 'Year', 'Grade', 'Quantity', 'Notes'])
            writer.writerow(['Canada', '1 cent', '1967', 'VF-20', 'invalid', 'Invalid quantity'])
        
        collection = CoinCollection(self.collection_path)
        imported_count, total_coins, total_countries, total_unique_dates = collection.import_from_csv(test_csv_invalid_qty)
        
        # Should default to 1 item
        self.assertEqual(imported_count, 1)
        self.assertEqual(total_coins, 1)

    def test_csv_import_with_acquisition_columns_recalculates_total(self):
        acquisition_csv = os.path.join(self.test_dir, "with_acquisition.csv")
        with open(acquisition_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Country', 'Denomination', 'Year', 'Grade', 'Quantity', 'Notes',
                'Acquisition_Date', 'Purchase_Price', 'Purchase_Currency',
                'Purchase_Source', 'Shipping_Cost', 'Buyers_Premium', 'Tax', 'Total_Cost',
            ])
            writer.writerow([
                'Canada', '5 cents', '1926', 'EF-40', '1', 'Near 6',
                '2026-07-01', '100.1200', ' usd ', 'Auction', '12.345', '20.00', '3.4',
                'not authoritative',
            ])

        collection = CoinCollection(self.collection_path)
        imported_count, _, _, _ = collection.import_from_csv(acquisition_csv)
        item = collection.items[0]

        self.assertEqual(1, imported_count)
        self.assertEqual('2026-07-01', item.acquisition_date)
        self.assertEqual(Decimal('100.1200'), item.purchase_price)
        self.assertEqual('USD', item.purchase_currency)
        self.assertEqual(Decimal('135.8650'), item.total_cost)
        with open(self.collection_path, 'r', encoding='utf-8') as handle:
            self.assertNotIn('total_cost', json.load(handle)["items"][0])

    def test_csv_import_accepts_blank_acquisition_values(self):
        blank_csv = os.path.join(self.test_dir, "blank_acquisition.csv")
        with open(blank_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Country', 'Denomination', 'Year', 'Grade', 'Quantity',
                'Acquisition_Date', 'Purchase_Price', 'Purchase_Currency',
                'Purchase_Source', 'Shipping_Cost', 'Buyers_Premium', 'Tax',
            ])
            writer.writerow(['Canada', '1 cent', '1967', 'VF-20', '1', '', '', '', '', '', '', ''])

        collection = CoinCollection(self.collection_path)
        imported_count, _, _, _ = collection.import_from_csv(blank_csv)

        self.assertEqual(1, imported_count)
        self.assertIsNone(collection.items[0].total_cost)
        self.assertIsNone(collection.items[0].purchase_currency)

    def test_csv_import_rejects_rows_with_invalid_acquisition_money(self):
        invalid_csv = os.path.join(self.test_dir, "invalid_acquisition.csv")
        with open(invalid_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Country', 'Denomination', 'Year', 'Purchase_Price'])
            writer.writerow(['Canada', '1 cent', '1967', '-1'])
            writer.writerow(['Canada', '1 cent', '1968', 'NaN'])

        collection = CoinCollection(self.collection_path)
        imported_count, total_coins, _, _ = collection.import_from_csv(invalid_csv)

        self.assertEqual(0, imported_count)
        self.assertEqual(0, total_coins)
        self.assertEqual([], collection.items)
        

if __name__ == '__main__':
    unittest.main()
