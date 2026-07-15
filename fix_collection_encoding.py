"""
Fix collection JSON encoding issue.
Re-saves the collection with proper UTF-8 encoding.
"""

import json
import os

from atomic_json import write_json_atomically

def fix_collection_encoding():
    """Fix collection JSON encoding."""
    input_file = "data/collection.json"
    backup_file = "data/collection_backup_encoding.json"
    
    # Backup original file
    if os.path.exists(input_file):
        with open(input_file, 'rb') as f:
            content = f.read()
        
        with open(backup_file, 'wb') as f:
            f.write(content)
        
        print(f"Backup created: {backup_file}")
    
    # Try to read with different encodings
    data = None
    for encoding in ['utf-8', 'latin-1', 'cp1252']:
        try:
            with open(input_file, 'r', encoding=encoding) as f:
                data = json.load(f)
            print(f"Successfully read file with {encoding} encoding")
            break
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            print(f"Failed to read with {encoding}: {e}")
            continue
    
    if data is None:
        print("Failed to read collection file with any encoding")
        return False
    
    print(f"Total entries: {len(data)}")
    
    # Re-save with proper UTF-8 encoding
    try:
        write_json_atomically(input_file, data, indent=2, ensure_ascii=False)
        print(f"Successfully re-saved collection with UTF-8 encoding")
        return True
    except Exception as e:
        print(f"Error saving collection: {e}")
        return False

if __name__ == "__main__":
    success = fix_collection_encoding()
    exit(0 if success else 1)
