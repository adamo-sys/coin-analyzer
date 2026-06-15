"""
Automated backend tests for coin collection functionality.
Tests data persistence, JSON loading, CSV export, and collection operations.
"""

import os
import json
import csv
import shutil
from coin_collection import CoinCollection, CoinItem
from datetime import datetime

def setup_test_environment():
    """Setup test environment with clean state."""
    # Backup existing collection if it exists
    if os.path.exists("data/collection.json"):
        shutil.copy("data/collection.json", "data/collection_backup.json")
    
    # Create test collection
    test_collection = CoinCollection("data/test_collection.json")
    test_collection.items = []
    test_collection.save_collection()
    
    return test_collection

def teardown_test_environment():
    """Restore original collection."""
    if os.path.exists("data/collection_backup.json"):
        shutil.copy("data/collection_backup.json", "data/collection.json")
        os.remove("data/collection_backup.json")
    
    # Clean up test files
    if os.path.exists("data/test_collection.json"):
        os.remove("data/test_collection.json")
    if os.path.exists("data/test_export.csv"):
        os.remove("data/test_export.csv")

def test_data_persistence():
    """Test 1: Data persistence - JSON save and load."""
    print("\n=== Test 1: Data Persistence ===")
    
    collection = CoinCollection("data/test_collection.json")
    
    # Add test item
    item = CoinItem(
        id="test_001",
        image_path="test_coins/IMG_3460.jpeg",
        country="Canada",
        denomination="Quarter",
        year="2023",
        grade="VF-20",
        notes="Test coin for persistence",
        date_added=datetime.now().isoformat(),
        auto_detected=False,
        detection_confidence=0.0
    )
    
    collection.add_item(item)
    
    # Verify item was saved
    assert len(collection.items) == 1, "Item not added to collection"
    assert collection.items[0].country == "Canada", "Country not saved correctly"
    
    # Reload collection
    collection2 = CoinCollection("data/test_collection.json")
    assert len(collection2.items) == 1, "Item not persisted"
    assert collection2.items[0].country == "Canada", "Country not persisted correctly"
    
    print("[PASS] Data persistence test PASSED")
    return True

def test_json_loading():
    """Test 2: JSON collection loading."""
    print("\n=== Test 2: JSON Collection Loading ===")
    
    collection = CoinCollection("data/test_collection.json")
    collection.items = []  # Clear existing items
    
    # Add multiple items
    for i in range(5):
        item = CoinItem(
            id=f"test_json_{i:03d}",
            image_path=f"test_coins/IMG_{3460+i}.jpeg",
            country="Canada",
            denomination="Quarter",
            year=str(2020 + i),
            grade="VF-20",
            notes=f"Test coin {i}",
            date_added=datetime.now().isoformat(),
            auto_detected=False,
            detection_confidence=0.0
        )
        collection.add_item(item)
    
    # Verify JSON file exists and is valid
    assert os.path.exists("data/test_collection.json"), "JSON file not created"
    
    with open("data/test_collection.json", 'r') as f:
        data = json.load(f)
    
    assert len(data) == 5, "Incorrect number of items in JSON"
    assert all('country' in item for item in data), "Missing country field in JSON"
    
    # Reload and verify
    collection2 = CoinCollection("data/test_collection.json")
    assert len(collection2.items) == 5, "Items not loaded correctly from JSON"
    
    print("[PASS] JSON loading test PASSED")
    return True

def test_csv_export():
    """Test 3: CSV export functionality."""
    print("\n=== Test 3: CSV Export ===")
    
    collection = CoinCollection("data/test_collection.json")
    collection.items = []  # Clear existing items
    
    # Add test item
    item = CoinItem(
        id="test_csv",
        image_path="test_coins/IMG_3460.jpeg",
        country="Canada",
        denomination="Quarter",
        year="2023",
        grade="VF-20",
        notes="Test for CSV export",
        date_added=datetime.now().isoformat(),
        auto_detected=False,
        detection_confidence=0.0
    )
    collection.add_item(item)
    
    # Export to CSV
    result = collection.export_to_csv("data/test_export.csv")
    assert result == True, "CSV export failed"
    
    # Verify CSV file exists
    assert os.path.exists("data/test_export.csv"), "CSV file not created"
    
    # Verify CSV content
    with open("data/test_export.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    assert len(rows) == 1, "Incorrect number of rows in CSV"
    assert rows[0]['country'] == "Canada", "Country not in CSV"
    assert rows[0]['denomination'] == "Quarter", "Denomination not in CSV"
    
    print("[PASS] CSV export test PASSED")
    return True

def test_collection_operations():
    """Test 4: Collection operations (add, edit, delete)."""
    print("\n=== Test 4: Collection Operations ===")
    
    collection = CoinCollection("data/test_collection.json")
    collection.items = []  # Clear existing items
    
    # Add item
    item = CoinItem(
        id="test_ops",
        image_path="test_coins/IMG_3460.jpeg",
        country="Canada",
        denomination="Quarter",
        year="2023",
        grade="VF-20",
        notes="Test for operations",
        date_added=datetime.now().isoformat(),
        auto_detected=False,
        detection_confidence=0.0
    )
    collection.add_item(item)
    assert len(collection.items) == 1, "Add operation failed"
    
    # Edit item
    collection.update_item("test_ops", {"country": "United States", "year": "2024"})
    assert collection.items[0].country == "United States", "Edit operation failed"
    assert collection.items[0].year == "2024", "Year edit failed"
    
    # Delete item
    collection.delete_item("test_ops")
    assert len(collection.items) == 0, "Delete operation failed"
    
    print("[PASS] Collection operations test PASSED")
    return True

def test_image_path_handling():
    """Test 5: Image path handling."""
    print("\n=== Test 5: Image Path Handling ===")
    
    collection = CoinCollection("data/test_collection.json")
    collection.items = []  # Clear existing items
    
    # Add item with image path
    item = CoinItem(
        id="test_image",
        image_path="test_coins/IMG_3460.jpeg",
        country="Canada",
        denomination="Quarter",
        year="2023",
        grade="VF-20",
        notes="Test image path",
        date_added=datetime.now().isoformat(),
        auto_detected=False,
        detection_confidence=0.0
    )
    collection.add_item(item)
    
    # Verify image path is preserved
    assert collection.items[0].image_path == "test_coins/IMG_3460.jpeg", "Image path not preserved"
    
    # Reload and verify
    collection2 = CoinCollection("data/test_collection.json")
    assert collection2.items[0].image_path == "test_coins/IMG_3460.jpeg", "Image path not persisted"
    
    print("[PASS] Image path handling test PASSED")
    return True

def test_special_characters():
    """Test 6: Special characters in notes."""
    print("\n=== Test 6: Special Characters ===")
    
    collection = CoinCollection("data/test_collection.json")
    collection.items = []  # Clear existing items
    
    # Add item with special characters
    special_notes = "Test with special chars: é, ñ, Chinese, emoji"
    item = CoinItem(
        id="test_special",
        image_path="test_coins/IMG_3460.jpeg",
        country="Canada",
        denomination="Quarter",
        year="2023",
        grade="VF-20",
        notes=special_notes,
        date_added=datetime.now().isoformat(),
        auto_detected=False,
        detection_confidence=0.0
    )
    collection.add_item(item)
    
    # Reload and verify special characters are preserved
    collection2 = CoinCollection("data/test_collection.json")
    assert collection2.items[0].notes == special_notes, "Special characters not preserved"
    
    # Export to CSV and verify
    collection2.export_to_csv("data/test_export.csv")
    with open("data/test_export.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    assert rows[0]['notes'] == special_notes, "Special characters not in CSV"
    
    print("[PASS] Special characters test PASSED")
    return True

def run_all_tests():
    """Run all automated backend tests."""
    print("=" * 60)
    print("Coin Collection Backend Tests")
    print("=" * 60)
    
    try:
        setup_test_environment()
        
        results = []
        results.append(("Data Persistence", test_data_persistence()))
        results.append(("JSON Loading", test_json_loading()))
        results.append(("CSV Export", test_csv_export()))
        results.append(("Collection Operations", test_collection_operations()))
        results.append(("Image Path Handling", test_image_path_handling()))
        results.append(("Special Characters", test_special_characters()))
        
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "[PASS]" if result else "[FAIL]"
            print(f"{test_name}: {status}")
        
        print(f"\nTotal: {passed}/{total} tests passed")
        
        if passed == total:
            print("\nAll backend tests PASSED")
        else:
            print(f"\n{total - passed} test(s) FAILED")
        
        return passed == total
        
    except Exception as e:
        print(f"\n[FAIL] Test execution failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        teardown_test_environment()

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
