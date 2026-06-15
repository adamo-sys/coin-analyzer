"""
CSV Exporter Module
This module handles exporting coin analysis results to CSV format.
"""

import csv
from typing import List, Dict
from urllib.parse import quote


class CSVExporter:
    """Exports coin analysis results to CSV format."""
    
    def __init__(self):
        """Initialize the CSV exporter."""
        self.base_numista_url = "https://en.numista.com/search/"
    
    def create_numista_url(self, country: str, denomination: str, year: str) -> str:
        """
        Create a Numista search URL based on coin information.
        
        Args:
            country: Country name
            denomination: Coin denomination
            year: Coin year
            
        Returns:
            Numista search URL
        """
        # Build search query
        search_parts = []
        
        if country and country != 'Unknown':
            search_parts.append(country)
        
        if denomination and denomination != 'Unknown':
            search_parts.append(denomination)
        
        if year and year != 'Unknown':
            search_parts.append(year)
        
        search_query = ' '.join(search_parts)
        encoded_query = quote(search_query)
        
        return f"{self.base_numista_url}?q={encoded_query}"
    
    def export_to_csv(self, results: List[Dict[str, str]], output_path: str) -> None:
        """
        Export analysis results to CSV file.
        
        Args:
            results: List of dictionaries containing coin information
            output_path: Path where CSV file will be saved
        """
        if not results:
            print("No results to export")
            return
        
        # Define CSV columns
        fieldnames = [
            'filename', 'country', 'country_confidence', 'denomination', 'denomination_confidence',
            'year', 'year_confidence', 'orientation', 'ocr_text_preview',
            'grade_range', 'grade_low', 'grade_high', 'confidence_score',
            'status', 'notes', 'wear_level', 'has_scratches', 'has_corrosion', 
            'has_cleaning_marks', 'has_damage', 'luster_present', 'image_quality_limitations',
            'numista_url', 'raw_text'
        ]
        
        # Add Numista URLs to results
        for result in results:
            result['numista_url'] = self.create_numista_url(
                result['country'],
                result['denomination'],
                result['year']
            )
        
        # Write to CSV
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header
                writer.writeheader()
                
                # Write data rows
                writer.writerows(results)
            
            print(f"Successfully exported {len(results)} coins to {output_path}")
        except Exception as e:
            print(f"Error exporting to CSV: {e}")
