"""
Numista Export Importer
Imports coin collection data from Numista Excel exports.
"""

import pandas as pd
import os
from typing import List, Dict, Tuple
from datetime import datetime
from coin_collection import CoinItem, CoinCollection


class NumistaImporter:
    """Importer for Numista Excel exports."""
    
    def __init__(self, collection: CoinCollection):
        self.collection = collection
        self.imported_items = []
        self.duplicates = []
    
    def import_from_excel(self, file_path: str) -> Tuple[int, int]:
        """
        Import coins from Numista Excel export.
        
        Args:
            file_path: Path to Numista Excel export file
            
        Returns:
            Tuple of (imported_count, duplicate_count)
        """
        try:
            # Read Excel file
            df = pd.read_excel(file_path)
            
            # Clear previous import data
            self.imported_items = []
            self.duplicates = []
            
            # Preserve existing manual entries (non-Numista)
            manual_items = [item for item in self.collection.items if not item.from_numista]
            
            # Clear collection for fresh import
            self.collection.items = []
            
            # Process each row
            for index, row in df.iterrows():
                item = self.map_row_to_item(row)
                
                # Check for duplicates
                if self.is_duplicate(item):
                    self.duplicates.append(item)
                else:
                    self.imported_items.append(item)
            
            # Add imported items to collection
            for item in self.imported_items:
                self.collection.add_item(item)
            
            # Restore manual entries
            for item in manual_items:
                self.collection.add_item(item)
            
            return len(self.imported_items), len(self.duplicates)
            
        except Exception as e:
            print(f"Error importing Numista export: {str(e)}")
            raise
    
    def map_row_to_item(self, row: pd.Series) -> CoinItem:
        """Map Numista Excel row to CoinItem."""
        # Extract Numista N# from link
        numista_n = self.extract_numista_n(row.get('N# number (with link)', ''))
        
        # Format year (convert float to int if needed)
        year_value = row.get('Year', '')
        if pd.notna(year_value):
            if isinstance(year_value, float) and year_value.is_integer():
                year_value = str(int(year_value))
            else:
                year_value = str(year_value).strip()
        else:
            year_value = ''
        
        # Format denomination
        denomination = self.format_denomination(row.get('Face value', ''), row.get('Currency', ''))
        
        # Map fields with NaN handling
        item = CoinItem(
            id=self.generate_item_id(row),
            image_path="",  # Numista exports don't include images
            country=self.clean_value(row.get('Country', '')),
            denomination=denomination,
            year=year_value,
            grade=self.clean_value(row.get('Grade', '')),
            notes=self.clean_value(row.get('Comment', '')),
            date_added=datetime.now().isoformat(),
            auto_detected=False,
            detection_confidence=0.0,
            # Numista fields
            issuer=self.clean_value(row.get('Issuer', '')),
            currency=self.clean_value(row.get('Currency', '')),
            face_value=self.clean_value(row.get('Face value', '')),
            reference=self.clean_value(row.get('Reference', '')),
            numista_n=numista_n,
            title=self.clean_value(row.get('Title', '')),
            quantity=int(row.get('Quantity', 1)) if pd.notna(row.get('Quantity')) else 1,
            estimate_cad=float(row.get('Estimate (CAD)', 0)) if pd.notna(row.get('Estimate (CAD)')) else 0.0,
            comments=self.clean_value(row.get('Private comment', '')),
            from_numista=True
        )
        
        return item
    
    def clean_value(self, value) -> str:
        """Clean value - handle NaN and convert to string."""
        if pd.isna(value):
            return ''
        return str(value).strip()
    
    def format_denomination(self, face_value, currency) -> str:
        """Format denomination with currency symbol where possible."""
        face_value = self.clean_value(face_value)
        currency = self.clean_value(currency)
        
        if not face_value:
            return ''
        
        # Try to parse numeric value
        try:
            num_value = float(face_value)
            
            # Handle very small values (fractions of cents)
            if num_value < 0.001:
                # These are likely fractional values like 0.00104167 (1/960)
                # Return the original value for these edge cases
                return face_value
            
            if num_value >= 1:
                # Dollar values
                if 'Dollar' in currency or 'dollar' in currency or 'USD' in currency:
                    return f"${int(num_value)}"
                elif 'Pound' in currency or 'pound' in currency:
                    return f"£{int(num_value)}"
                elif 'Euro' in currency or 'euro' in currency:
                    return f"€{int(num_value)}"
                else:
                    return face_value
            else:
                # Cent values
                cents = int(round(num_value * 100))
                if cents == 0:
                    return face_value  # Don't format as "0 cents"
                elif 'Cent' in currency or 'cent' in currency or 'USD' in currency:
                    return f"{cents} cent" if cents == 1 else f"{cents} cents"
                elif 'Penny' in currency or 'penny' in currency:
                    return f"{cents} pence" if cents > 1 else "1 penny"
                else:
                    return f"{cents} cent" if cents == 1 else f"{cents} cents"
        except (ValueError, TypeError):
            return face_value
    
    def extract_numista_n(self, n_link: str) -> str:
        """Extract Numista N# from link."""
        if pd.isna(n_link) or not n_link:
            return ""
        
        # Numista N# is typically in format: N#123456
        # Try to extract the number
        if "N#" in str(n_link):
            return str(n_link).split("N#")[-1].strip()
        
        return str(n_link).strip()
    
    def generate_item_id(self, row: pd.Series) -> str:
        """Generate unique item ID from Numista data."""
        numista_n = self.extract_numista_n(row.get('N# number (with link)', ''))
        if numista_n:
            return f"numista_{numista_n}"
        
        # Fallback to other fields
        country = str(row.get('Country', '')).strip()
        year = str(row.get('Year', '')).strip()
        reference = str(row.get('Reference', '')).strip()
        
        if reference:
            return f"numista_{country}_{year}_{reference}"
        
        return f"numista_{country}_{year}_{datetime.now().strftime('%H%M%S')}"
    
    def is_duplicate(self, item: CoinItem) -> bool:
        """Check if item is a duplicate of existing collection."""
        # Check by Numista N#
        if item.numista_n:
            for existing_item in self.collection.items:
                if existing_item.numista_n == item.numista_n:
                    return True
        
        # Check by combination of country, year, reference
        for existing_item in self.collection.items:
            if (existing_item.country == item.country and
                existing_item.year == item.year and
                existing_item.reference == item.reference):
                return True
        
        return False
    
    def get_import_summary(self) -> Dict:
        """Get summary of import operation."""
        return {
            'imported': len(self.imported_items),
            'duplicates': len(self.duplicates),
            'total': len(self.imported_items) + len(self.duplicates)
        }
    
    def get_duplicate_items(self) -> List[CoinItem]:
        """Get list of duplicate items."""
        return self.duplicates


def test_numista_import():
    """Test Numista import functionality."""
    collection = CoinCollection("data/test_numista_import.json")
    
    importer = NumistaImporter(collection)
    
    try:
        imported, duplicates = importer.import_from_excel("data/numista_export.xlsx")
        
        print(f"Import Summary:")
        print(f"  Imported: {imported}")
        print(f"  Duplicates: {duplicates}")
        print(f"  Total processed: {imported + duplicates}")
        
        if duplicates > 0:
            print(f"\nDuplicate items:")
            for item in importer.get_duplicate_items():
                print(f"  {item.title} ({item.country} {item.year}) - N#: {item.numista_n}")
        
        return True
        
    except Exception as e:
        print(f"Import failed: {str(e)}")
        return False


if __name__ == "__main__":
    test_numista_import()
