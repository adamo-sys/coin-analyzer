"""
Coin Collection Manager
MVP app for managing coin collection with manual editing and optional automatic identification.
"""

import json
import csv
import os
from datetime import datetime
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
import cv2
import numpy as np

@dataclass
class CoinItem:
    """Data structure for a coin item in the collection."""
    id: str
    image_path: str
    country: str
    denomination: str
    year: str
    grade: str
    notes: str
    date_added: str
    auto_detected: bool = False
    detection_confidence: float = 0.0
    # Numista fields
    issuer: str = ""
    currency: str = ""
    face_value: str = ""
    reference: str = ""
    numista_n: str = ""
    title: str = ""
    quantity: int = 1
    estimate_cad: float = 0.0
    comments: str = ""
    from_numista: bool = False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CoinItem':
        """Create from dictionary."""
        return cls(**data)


class CoinCollection:
    """Manages local coin collection storage and operations."""
    
    def __init__(self, storage_path: str = "data/collection.json"):
        self.storage_path = storage_path
        self.items: List[CoinItem] = []
        self.ensure_storage_directory()
        self.load_collection()
    
    def ensure_storage_directory(self):
        """Ensure storage directory exists."""
        directory = os.path.dirname(self.storage_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
    
    def load_collection(self):
        """Load collection from JSON storage."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.items = [CoinItem.from_dict(item) for item in data]
                print(f"Loaded {len(self.items)} items from collection")
            except Exception as e:
                print(f"Error loading collection: {str(e)}")
                self.items = []
        else:
            self.items = []
            print("No existing collection found, starting fresh")
    
    def save_collection(self):
        """Save collection to JSON storage."""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump([item.to_dict() for item in self.items], f, indent=2, ensure_ascii=False)
            print(f"Saved {len(self.items)} items to collection")
        except Exception as e:
            print(f"Error saving collection: {str(e)}")
    
    def add_item(self, item: CoinItem) -> bool:
        """Add item to collection."""
        self.items.append(item)
        self.save_collection()
        return True
    
    def update_item(self, item_id: str, updates: Dict) -> bool:
        """Update item in collection."""
        for item in self.items:
            if item.id == item_id:
                for key, value in updates.items():
                    if hasattr(item, key):
                        setattr(item, key, value)
                self.save_collection()
                return True
        return False
    
    def delete_item(self, item_id: str) -> bool:
        """Delete item from collection."""
        self.items = [item for item in self.items if item.id != item_id]
        self.save_collection()
        return True
    
    def get_item(self, item_id: str) -> Optional[CoinItem]:
        """Get item by ID."""
        for item in self.items:
            if item.id == item_id:
                return item
        return None
    
    def get_all_items(self) -> List[CoinItem]:
        """Get all items in collection."""
        return self.items
    
    def search_items(self, query: str) -> List[CoinItem]:
        """
        Search collection items by multiple fields.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching items
        """
        if not query:
            return self.items
        
        query = query.lower().strip()
        results = []
        
        for item in self.items:
            # Search in multiple fields
            searchable_text = f"{item.id} {item.numista_n} {item.reference} {item.title} {item.country} {item.denomination} {item.year} {item.issuer}".lower()
            
            if query in searchable_text:
                results.append(item)
        
        return results
    
    def get_autocomplete_suggestions(self, field: str, query: str) -> List[str]:
        """
        Get autocomplete suggestions for a field from Numista dataset.
        
        Args:
            field: Field name (country, denomination, year, etc.)
            query: Partial query string
            
        Returns:
            List of unique matching values
        """
        if not query:
            return []
        
        query = query.lower().strip()
        values = set()
        
        for item in self.items:
            if item.from_numista:  # Only use Numista data for autocomplete
                value = ""
                if field == "country":
                    value = item.country
                elif field == "denomination":
                    value = item.denomination
                elif field == "year":
                    value = item.year
                elif field == "issuer":
                    value = item.issuer
                elif field == "currency":
                    value = item.currency
                
                if value and query in value.lower():
                    values.add(value)
        
        return sorted(list(values))[:20]  # Return top 20 matches
    
    def find_matching_coins(self, country: str, denomination: str, year: str) -> List[CoinItem]:
        """
        Find coins matching country, denomination, and year.
        
        Args:
            country: Country name
            denomination: Denomination
            year: Year
            
        Returns:
            List of matching coins
        """
        matches = []
        for item in self.items:
            if (item.country.lower() == country.lower() and
                item.denomination.lower() == denomination.lower() and
                item.year == year):
                matches.append(item)
        return matches
    
    def analyze_collection_gaps(self) -> Dict:
        """
        Analyze collection for gaps and patterns.
        
        Returns:
            Dictionary with gap analysis results
        """
        analysis = {
            'total_coins': len(self.items),
            'countries': {},
            'years': {},
            'denominations': {},
            'numista_coverage': 0
        }
        
        for item in self.items:
            # Country analysis
            if item.country:
                analysis['countries'][item.country] = analysis['countries'].get(item.country, 0) + 1
            
            # Year analysis
            if item.year:
                analysis['years'][item.year] = analysis['years'].get(item.year, 0) + 1
            
            # Denomination analysis
            if item.denomination:
                analysis['denominations'][item.denomination] = analysis['denominations'].get(item.denomination, 0) + 1
            
            # Numista coverage
            if item.from_numista:
                analysis['numista_coverage'] += 1
        
        analysis['numista_coverage'] = (analysis['numista_coverage'] / analysis['total_coins']) * 100
        
        return analysis
    
    def get_series_years(self, country: str, denomination: str) -> Set[str]:
        """Get all years for a country/denomination series."""
        years = set()
        for item in self.items:
            if item.country.lower() == country.lower() and item.denomination.lower() == denomination.lower():
                if item.year:
                    years.add(item.year)
        return years
    
    def get_country_denominations(self, country: str) -> Set[str]:
        """Get all denominations for a country."""
        denominations = set()
        for item in self.items:
            if item.country.lower() == country.lower():
                if item.denomination:
                    denominations.add(item.denomination)
        return denominations
    
    def export_to_csv(self, output_path: str = "data/collection_export.csv"):
        """Export collection to CSV."""
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['id', 'image_path', 'country', 'denomination', 'year', 
                            'grade', 'notes', 'date_added', 'auto_detected', 'detection_confidence',
                            'issuer', 'currency', 'face_value', 'reference', 'numista_n', 
                            'title', 'quantity', 'estimate_cad', 'comments', 'from_numista']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for item in self.items:
                    writer.writerow(item.to_dict())
            print(f"Exported {len(self.items)} items to {output_path}")
            return True
        except Exception as e:
            print(f"Error exporting to CSV: {str(e)}")
            return False
    
    def import_from_csv(self, input_path: str) -> bool:
        """Import collection from CSV."""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                imported = 0
                for row in reader:
                    try:
                        item = CoinItem.from_dict(row)
                        self.items.append(item)
                        imported += 1
                    except Exception as e:
                        print(f"Error importing row: {str(e)}")
                self.save_collection()
            print(f"Imported {imported} items from {input_path}")
            return True
        except Exception as e:
            print(f"Error importing from CSV: {str(e)}")
            return False
    
    def generate_item_id(self) -> str:
        """Generate unique item ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"coin_{timestamp}"
    
    def get_statistics(self) -> Dict:
        """Get collection statistics."""
        if not self.items:
            return {
                'total_items': 0,
                'countries': {},
                'denominations': {},
                'grades': {},
                'auto_detected': 0
            }
        
        countries = {}
        denominations = {}
        grades = {}
        auto_detected = sum(1 for item in self.items if item.auto_detected)
        
        for item in self.items:
            countries[item.country] = countries.get(item.country, 0) + 1
            denominations[item.denomination] = denominations.get(item.denomination, 0) + 1
            grades[item.grade] = grades.get(item.grade, 0) + 1
        
        return {
            'total_items': len(self.items),
            'countries': countries,
            'denominations': denominations,
            'grades': grades,
            'auto_detected': auto_detected
        }


class CoinCollectionApp:
    """Main application for coin collection management."""
    
    def __init__(self):
        self.collection = CoinCollection()
        self.current_image_path = None
        self.current_detection_result = None
    
    def upload_image(self, image_path: str) -> bool:
        """Upload and validate coin image."""
        if not os.path.exists(image_path):
            print(f"Image not found: {image_path}")
            return False
        
        # Validate image can be loaded
        img = cv2.imread(image_path)
        if img is None:
            print(f"Failed to load image: {image_path}")
            return False
        
        self.current_image_path = image_path
        print(f"Image uploaded: {image_path}")
        return True
    
    def run_denomination_detector(self) -> Dict:
        """Run denomination detector on current image."""
        if not self.current_image_path:
            return {'success': False, 'error': 'No image uploaded'}
        
        try:
            from coin_recognition import CoinRecognizer
            recognizer = CoinRecognizer()
            result = recognizer.detect_coin(self.current_image_path)
            
            if result['success']:
                self.current_detection_result = {
                    'success': True,
                    'country': result.get('country', 'Unknown'),
                    'denomination': result.get('denomination', 'Unknown'),
                    'year': result.get('year', 'Unknown'),
                    'confidence': result.get('denomination_confidence', 0.0),
                    'year_confidence': result.get('year_confidence', 0.0),
                    'method': 'coin_recognition'
                }
            else:
                self.current_detection_result = {
                    'success': False,
                    'error': result.get('error', 'Detection failed'),
                    'country': 'Unknown',
                    'denomination': 'Unknown',
                    'year': 'Unknown',
                    'confidence': 0.0,
                    'method': 'coin_recognition'
                }
            
            return self.current_detection_result
            
        except Exception as e:
            self.current_detection_result = {
                'success': False,
                'error': str(e),
                'country': 'Unknown',
                'denomination': 'Unknown',
                'year': 'Unknown',
                'confidence': 0.0,
                'method': 'coin_recognition'
            }
            return self.current_detection_result
    
    def add_to_collection(self, country: str, denomination: str, year: str, 
                         grade: str, notes: str, use_detection: bool = False) -> bool:
        """Add current coin to collection."""
        if not self.current_image_path:
            print("No image uploaded")
            return False
        
        item_id = self.collection.generate_item_id()
        
        if use_detection and self.current_detection_result:
            country = self.current_detection_result.get('country', country)
            denomination = self.current_detection_result.get('denomination', denomination)
            confidence = self.current_detection_result.get('confidence', 0.0)
            auto_detected = True
        else:
            confidence = 0.0
            auto_detected = False
        
        item = CoinItem(
            id=item_id,
            image_path=self.current_image_path,
            country=country,
            denomination=denomination,
            year=year,
            grade=grade,
            notes=notes,
            date_added=datetime.now().isoformat(),
            auto_detected=auto_detected,
            detection_confidence=confidence
        )
        
        self.collection.add_item(item)
        print(f"Added item {item_id} to collection")
        return True
    
    def view_collection(self) -> List[Dict]:
        """View all items in collection."""
        items = self.collection.get_all_items()
        return [item.to_dict() for item in items]
    
    def export_collection(self, output_path: str = None) -> bool:
        """Export collection to CSV."""
        if output_path is None:
            output_path = "data/collection_export.csv"
        return self.collection.export_to_csv(output_path)
    
    def get_statistics(self) -> Dict:
        """Get collection statistics."""
        return self.collection.get_statistics()


def main():
    """Main application entry point."""
    app = CoinCollectionApp()
    
    print("=" * 60)
    print("Coin Collection Manager - MVP")
    print("=" * 60)
    
    while True:
        print("\nOptions:")
        print("1. Upload coin image")
        print("2. Run denomination detector")
        print("3. Add to collection")
        print("4. View collection")
        print("5. Export to CSV")
        print("6. View statistics")
        print("7. Exit")
        
        try:
            choice = input("\nEnter choice (1-7): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break
        
        if choice == '1':
            image_path = input("Enter image path: ").strip()
            app.upload_image(image_path)
        
        elif choice == '2':
            result = app.run_denomination_detector()
            print(f"Detection result: {result}")
        
        elif choice == '3':
            if not app.current_image_path:
                print("Please upload an image first")
                continue
            
            country = input("Country: ").strip()
            denomination = input("Denomination: ").strip()
            year = input("Year: ").strip()
            grade = input("Grade: ").strip()
            notes = input("Notes: ").strip()
            
            use_detection = input("Use detection results? (y/n): ").strip().lower() == 'y'
            
            app.add_to_collection(country, denomination, year, grade, notes, use_detection)
        
        elif choice == '4':
            items = app.view_collection()
            print(f"\nCollection ({len(items)} items):")
            for item in items:
                print(f"  {item['id']}: {item['country']} {item['denomination']} {item['year']} - {item['grade']}")
        
        elif choice == '5':
            app.export_collection()
        
        elif choice == '6':
            stats = app.get_statistics()
            print(f"\nStatistics:")
            print(f"  Total items: {stats['total_items']}")
            print(f"  Auto-detected: {stats['auto_detected']}")
            print(f"  Countries: {stats['countries']}")
            print(f"  Denominations: {stats['denominations']}")
            print(f"  Grades: {stats['grades']}")
        
        elif choice == '7':
            print("Exiting...")
            break
        
        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()
