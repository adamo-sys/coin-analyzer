"""
Re-import Numista data with proper formatting.
"""

import os
import shutil
from coin_collection import CoinCollection
from numista_importer import NumistaImporter

def reimport_numista_formatted():
    """Re-import Numista data with proper formatting."""
    # Backup existing collection
    if os.path.exists("data/collection.json"):
        shutil.copy("data/collection.json", "data/collection_backup_before_reimport.json")
        print("Backup created: data/collection_backup_before_reimport.json")
    
    # Create fresh collection
    os.makedirs("data", exist_ok=True)
    collection = CoinCollection("data/collection.json")
    collection.items = []  # Clear existing items
    
    # Import Numista data
    importer = NumistaImporter(collection)
    
    try:
        imported, duplicates = importer.import_from_excel("data/numista_export.xlsx")
        
        print(f"Import Summary:")
        print(f"  Imported: {imported} items")
        print(f"  Duplicates: {duplicates} items")
        print(f"  Total: {imported + duplicates} items")
        
        # Show some sample formatted data
        print(f"\n=== Sample Formatted Data ===")
        for item in collection.items[:5]:
            print(f"  {item.country} {item.denomination} {item.year} - {item.title}")
        
        return True
        
    except Exception as e:
        print(f"Import failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = reimport_numista_formatted()
    exit(0 if success else 1)
