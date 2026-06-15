"""
Restore manual entries from backup.
"""

import json
import shutil
from coin_collection import CoinCollection

def restore_manual_entries():
    """Restore manual entries from backup and merge with current collection."""
    # Load current collection
    current_collection = CoinCollection('data/collection.json')
    
    # Load backup
    backup_file = 'data/collection_backup_before_reimport.json'
    if not os.path.exists(backup_file):
        print(f"Backup file not found: {backup_file}")
        return False
    
    with open(backup_file, 'r', encoding='utf-8') as f:
        backup_data = json.load(f)
    
    # Extract manual entries from backup
    manual_entries = [item for item in backup_data if not item.get('from_numista', False)]
    
    print(f"Found {len(manual_entries)} manual entries in backup")
    
    # Add manual entries to current collection
    for item_data in manual_entries:
        # Check if already exists
        existing = current_collection.get_item(item_data['id'])
        if not existing:
            from coin_collection import CoinItem
            item = CoinItem.from_dict(item_data)
            current_collection.add_item(item)
            print(f"Restored: {item.country} {item.denomination} {item.year}")
    
    print(f"Total coins after restore: {len(current_collection.items)}")
    return True

if __name__ == "__main__":
    import os
    success = restore_manual_entries()
    exit(0 if success else 1)
