"""
Unit tests for CSV import functionality.
"""

import csv
import os
import shutil
import tempfile
import unittest

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
        

if __name__ == '__main__':
    unittest.main()
