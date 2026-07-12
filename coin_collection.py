"""
Coin Collection Manager
MVP app for managing coin collection with manual editing and optional automatic identification.
"""

import json
import csv
import os
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
import cv2
import numpy as np


class PhotoRole(str, Enum):
    """Structured role for photos attached to a collection item."""

    FRONT = "FRONT"
    BACK = "BACK"
    HOLDER_FRONT = "HOLDER_FRONT"
    HOLDER_BACK = "HOLDER_BACK"
    EDGE = "EDGE"
    DETAIL = "DETAIL"
    CERT_LABEL = "CERT_LABEL"
    OTHER = "OTHER"

    @classmethod
    def normalize(cls, value: Any) -> "PhotoRole":
        if isinstance(value, cls):
            return value
        text = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
        aliases = {
            "OBVERSE": cls.FRONT,
            "REVERSE": cls.BACK,
            "FRONT_PHOTO": cls.FRONT,
            "BACK_PHOTO": cls.BACK,
            "LABEL": cls.CERT_LABEL,
            "CERTIFICATION_LABEL": cls.CERT_LABEL,
            "CERT": cls.CERT_LABEL,
        }
        if text in aliases:
            return aliases[text]
        try:
            return cls(text)
        except ValueError:
            return cls.OTHER


@dataclass
class ItemPhoto:
    """Photo metadata owned by a collection item; files are never moved."""

    path: str
    role: PhotoRole = PhotoRole.OTHER
    is_primary: bool = False
    notes: str = ""
    display_order: int = 0

    def __post_init__(self) -> None:
        self.path = str(self.path or "").strip()
        self.role = PhotoRole.normalize(self.role)
        self.is_primary = bool(self.is_primary)
        self.notes = str(self.notes or "").strip()
        try:
            self.display_order = int(self.display_order)
        except (TypeError, ValueError):
            self.display_order = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "role": self.role.value,
            "is_primary": self.is_primary,
            "notes": self.notes,
            "display_order": self.display_order,
        }

    @classmethod
    def from_dict(cls, data: Any, fallback_order: int = 0) -> Optional["ItemPhoto"]:
        if isinstance(data, str):
            path = data.strip()
            return cls(path=path, display_order=fallback_order) if path else None
        if not isinstance(data, dict):
            return None
        path = str(data.get("path") or data.get("file_path") or "").strip()
        if not path:
            return None
        return cls(
            path=path,
            role=data.get("role") or data.get("photo_role") or data.get("photo_type") or PhotoRole.OTHER,
            is_primary=bool(data.get("is_primary", False)),
            notes=str(data.get("notes") or ""),
            display_order=data.get("display_order", fallback_order),
        )


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
    photos: List[ItemPhoto] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.image_path = str(self.image_path or "").strip()
        self.photos = self._coerce_photos(self.photos)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        self.sync_image_path_from_primary()
        return {
            "id": self.id,
            "image_path": self.image_path,
            "country": self.country,
            "denomination": self.denomination,
            "year": self.year,
            "grade": self.grade,
            "notes": self.notes,
            "date_added": self.date_added,
            "auto_detected": self.auto_detected,
            "detection_confidence": self.detection_confidence,
            "issuer": self.issuer,
            "currency": self.currency,
            "face_value": self.face_value,
            "reference": self.reference,
            "numista_n": self.numista_n,
            "title": self.title,
            "quantity": self.quantity,
            "estimate_cad": self.estimate_cad,
            "comments": self.comments,
            "from_numista": self.from_numista,
            "photos": [photo.to_dict() for photo in self.normalized_photos()],
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CoinItem':
        """Create from dictionary."""
        if not isinstance(data, dict):
            data = {}
        known = {
            "id": str(data.get("id") or ""),
            "image_path": str(data.get("image_path") or ""),
            "country": str(data.get("country") or ""),
            "denomination": str(data.get("denomination") or ""),
            "year": str(data.get("year") or ""),
            "grade": str(data.get("grade") or ""),
            "notes": str(data.get("notes") or ""),
            "date_added": str(data.get("date_added") or ""),
            "auto_detected": bool(data.get("auto_detected", False)),
            "detection_confidence": cls._float_or_default(data.get("detection_confidence"), 0.0),
            "issuer": str(data.get("issuer") or ""),
            "currency": str(data.get("currency") or ""),
            "face_value": str(data.get("face_value") or ""),
            "reference": str(data.get("reference") or ""),
            "numista_n": str(data.get("numista_n") or ""),
            "title": str(data.get("title") or ""),
            "quantity": cls._int_or_default(data.get("quantity"), 1),
            "estimate_cad": cls._float_or_default(data.get("estimate_cad"), 0.0),
            "comments": str(data.get("comments") or ""),
            "from_numista": bool(data.get("from_numista", False)),
            "photos": cls._coerce_photos(data.get("photos", [])),
        }
        return cls(**known)

    def normalized_photos(self) -> List[ItemPhoto]:
        """Return deterministic photos, synthesizing legacy image_path if needed."""
        photos = self._coerce_photos(self.photos)
        if not photos and self.image_path:
            photos = [ItemPhoto(self.image_path, PhotoRole.OTHER, True, "", 0)]
        photos = [photo for photo in photos if photo.path]
        photos.sort(key=lambda photo: photo.display_order)
        for index, photo in enumerate(photos):
            photo.display_order = index
        primary_index = self._effective_primary_index(photos)
        for index, photo in enumerate(photos):
            photo.is_primary = index == primary_index
        return photos

    def primary_photo(self) -> Optional[ItemPhoto]:
        photos = self.normalized_photos()
        return next((photo for photo in photos if photo.is_primary), photos[0] if photos else None)

    @property
    def primary_image_path(self) -> str:
        primary = self.primary_photo()
        return primary.path if primary else self.image_path

    def sync_image_path_from_primary(self) -> None:
        primary = self.primary_photo()
        if primary:
            self.image_path = primary.path
            self.photos = self.normalized_photos()

    @staticmethod
    def _coerce_photos(value: Any) -> List[ItemPhoto]:
        if not value:
            return []
        if not isinstance(value, list):
            value = [value]
        photos = []
        for index, row in enumerate(value):
            photo = row if isinstance(row, ItemPhoto) else ItemPhoto.from_dict(row, index)
            if photo and photo.path:
                photos.append(photo)
        return photos

    @staticmethod
    def _effective_primary_index(photos: List[ItemPhoto]) -> Optional[int]:
        if not photos:
            return None
        for index, photo in enumerate(photos):
            if photo.is_primary:
                return index
        return 0

    @staticmethod
    def _int_or_default(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _float_or_default(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default


@dataclass
class PhotoMigrationResult:
    """Preview/apply result for explicit legacy photo migration."""

    total_items: int = 0
    legacy_image_path_items: int = 0
    structured_photo_items: int = 0
    blank_photo_items: int = 0
    migrated_items: int = 0
    duplicate_photo_paths: int = 0
    multiple_primary_items: int = 0
    no_primary_items: int = 0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_items": self.total_items,
            "legacy_image_path_items": self.legacy_image_path_items,
            "structured_photo_items": self.structured_photo_items,
            "blank_photo_items": self.blank_photo_items,
            "migrated_items": self.migrated_items,
            "duplicate_photo_paths": self.duplicate_photo_paths,
            "multiple_primary_items": self.multiple_primary_items,
            "no_primary_items": self.no_primary_items,
            "warnings": list(self.warnings),
        }


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

    def preview_photo_migration(self) -> PhotoMigrationResult:
        """Preview legacy image_path-to-photos normalization without writing."""
        return self._build_photo_migration_result(apply=False)

    def apply_photo_migration(self) -> PhotoMigrationResult:
        """Explicitly normalize item-owned photos and save when changes occur."""
        result = self._build_photo_migration_result(apply=True)
        if result.migrated_items:
            self.save_collection()
        return result

    def _build_photo_migration_result(self, apply: bool) -> PhotoMigrationResult:
        result = PhotoMigrationResult(total_items=len(self.items))
        seen_paths = set()
        for item in self.items:
            raw_photos = CoinItem._coerce_photos(getattr(item, "photos", []))
            primary_count = sum(1 for photo in raw_photos if photo.is_primary)
            if raw_photos:
                result.structured_photo_items += 1
                if primary_count > 1:
                    result.multiple_primary_items += 1
                    result.warnings.append(f"{item.id}: multiple primary photos normalized deterministically")
                elif primary_count == 0:
                    result.no_primary_items += 1
                    result.warnings.append(f"{item.id}: no primary photo; first photo becomes primary")
            elif item.image_path:
                result.legacy_image_path_items += 1
            else:
                result.blank_photo_items += 1

            for photo in item.normalized_photos():
                normalized_path = os.path.normcase(os.path.normpath(photo.path))
                if normalized_path in seen_paths:
                    result.duplicate_photo_paths += 1
                    result.warnings.append(f"{item.id}: duplicate photo path detected: {photo.path}")
                else:
                    seen_paths.add(normalized_path)

            before = [photo.to_dict() for photo in raw_photos]
            before_image_path = item.image_path
            normalized = item.normalized_photos()
            after = [photo.to_dict() for photo in normalized]
            after_image_path = normalized[0].path if normalized else item.image_path
            if before != after or before_image_path != after_image_path:
                result.migrated_items += 1
                if apply:
                    item.photos = normalized
                    item.image_path = after_image_path
        return result
    
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
    
    def get_field_suggestions(
        self,
        field: str,
        query: str = "",
        country: str = "",
        denomination: str = "",
        limit: int = 50,
    ) -> List[str]:
        """
        Get editable-entry suggestions from current collection data.

        Suggestions are advisory only. They do not validate or restrict manual
        values typed by the collector.
        """
        field = (field or "").strip().lower()
        query = (query or "").strip().lower()
        country_filter = (country or "").strip().lower()
        denomination_filter = (denomination or "").strip().lower()
        values_by_key = {}

        for item in self.items:
            if country_filter and (item.country or "").strip().lower() != country_filter:
                continue
            if denomination_filter and (item.denomination or "").strip().lower() != denomination_filter:
                continue

            value = ""
            if field == "country":
                value = item.country
            elif field == "denomination":
                value = item.denomination
            elif field == "year":
                value = item.year
            elif field == "grade":
                value = item.grade
            elif field == "issuer":
                value = item.issuer
            elif field == "currency":
                value = item.currency

            value = str(value or "").strip()
            if not value:
                continue
            if query and query not in value.lower():
                continue
            values_by_key.setdefault(value.lower(), value)

        suggestions = list(values_by_key.values())
        if field == "year":
            suggestions.sort(key=self._year_sort_key)
        else:
            suggestions.sort(key=lambda value: value.lower())
        return suggestions[:limit]

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
        return self.get_field_suggestions(field, query=query, limit=20)

    @staticmethod
    def _year_sort_key(value: str):
        text = str(value or "").strip()
        if text.isdigit():
            return (0, int(text), text)
        return (1, text.lower(), text)
    
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
    
    def import_from_csv(self, csv_path: str) -> tuple:
        """
        Import collection items from CSV file.
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            Tuple of (imported_count, total_coins, total_countries, total_unique_dates)
        """
        imported_count = 0
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Convert all keys to lowercase for case-insensitive matching
                    row_lower = {k.lower(): v for k, v in row.items()}
                    
                    # Parse required fields (case-insensitive)
                    country = row_lower.get('country', '').strip()
                    denomination = row_lower.get('denomination', '').strip()
                    year = row_lower.get('year', '').strip()
                    grade = row_lower.get('grade', '').strip()
                    quantity = row_lower.get('quantity', '1').strip()
                    notes = row_lower.get('notes', '').strip()
                    
                    # Validate required fields
                    if not country or not denomination or not year:
                        print(f"Skipping row with missing required fields: {row}")
                        continue
                    
                    # Parse quantity
                    try:
                        quantity = int(quantity) if quantity else 1
                    except ValueError:
                        quantity = 1
                    
                    # Create items (one per quantity)
                    for i in range(quantity):
                        # Generate unique ID
                        item_id = f"csv_import_{len(self.items)}_{i}"
                        
                        # Create CoinItem
                        item = CoinItem(
                            id=item_id,
                            image_path="",  # No image for CSV import
                            country=country,
                            denomination=denomination,
                            year=year,
                            grade=grade,
                            notes=notes,
                            date_added=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            auto_detected=False,
                            quantity=1  # Each item has quantity 1, we create multiple items
                        )
                        
                        self.items.append(item)
                        imported_count += 1
            
            # Save collection
            self.save_collection()
            
            # Calculate statistics
            total_coins = len(self.items)
            total_countries = len(set(item.country for item in self.items))
            total_unique_dates = len(set(f"{item.country}_{item.denomination}_{item.year}" for item in self.items))
            
            return imported_count, total_coins, total_countries, total_unique_dates
            
        except Exception as e:
            print(f"Error importing CSV: {str(e)}")
            return 0, 0, 0, 0
    
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
                    row = item.to_dict()
                    writer.writerow({field: row.get(field, "") for field in fieldnames})
            print(f"Exported {len(self.items)} items to {output_path}")
            return True
        except Exception as e:
            print(f"Error exporting to CSV: {str(e)}")
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
                         grade: str, notes: str, use_detection: bool = False,
                         photos: Optional[List[ItemPhoto]] = None) -> bool:
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
        
        structured_photos = CoinItem._coerce_photos(photos or [])
        if structured_photos:
            structured_photos = CoinItem(
                id="",
                image_path=self.current_image_path,
                country="",
                denomination="",
                year="",
                grade="",
                notes="",
                date_added="",
                photos=structured_photos,
            ).normalized_photos()
            primary_photo = next((photo for photo in structured_photos if photo.is_primary), structured_photos[0])
            self.current_image_path = primary_photo.path

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
            detection_confidence=confidence,
            photos=structured_photos,
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
