"""
Image Analyzer Module
This module handles computer vision analysis of coin images to extract country, denomination, and year.
Uses CV-first approach with OCR as supporting evidence only.
"""

import cv2
import re
from typing import Any, Dict, Optional
from coin_grading import CoinGrader
from coin_recognition import CoinRecognizer


class CoinAnalyzer:
    """Analyzes coin images using computer vision to extract information."""
    
    def __init__(self):
        """Initialize the coin analyzer."""
        # Initialize coin recognizer (CV-first approach)
        self.recognizer = CoinRecognizer()
        
        # Initialize coin grader
        self.grader = CoinGrader()
        
        # Common country names (for OCR support only)
        self.countries = [
            'canada', 'canadian', 'ca'
        ]
    
    def extract_country_from_ocr(self, text: str) -> Optional[str]:
        """
        Extract country from OCR text (supporting evidence only).
        
        Args:
            text: OCR extracted text
            
        Returns:
            Country as string or None if not found
        """
        text_lower = text.lower()
        
        for country in self.countries:
            if country.lower() in text_lower:
                return country.capitalize()
        
        return "Canada"  # Default to Canada for Canadian coin collector
    
    def extract_year_from_ocr(self, text: str) -> Optional[str]:
        """
        Extract year from OCR text (supporting evidence only).
        
        Args:
            text: OCR extracted text
            
        Returns:
            Year as string or None if not found
        """
        # Look for 4-digit years (1800-2099)
        year_pattern = r'\b(18[0-9]{2}|19[0-9]{2}|20[0-9]{2})\b'
        match = re.search(year_pattern, text)
        
        if match:
            return match.group(1)
        return None
    
    def extract_denomination_from_ocr(self, text: str) -> Optional[str]:
        """
        Extract denomination from OCR text (supporting evidence only).
        
        Args:
            text: OCR extracted text
            
        Returns:
            Denomination as string or None if not found
        """
        # Common Canadian coin denominations
        denominations = [
            '1 cent', '5 cent', '10 cent', '25 cent', '50 cent', '1 dollar', '2 dollar',
            'penny', 'nickel', 'dime', 'quarter', 'half dollar', 'loonie', 'toonie',
            '1¢', '5¢', '10¢', '25¢', '50¢', '$1', '$2'
        ]
        
        text_lower = text.lower()
        
        for denom in denominations:
            if denom.lower() in text_lower:
                return denom
        
        return None
    
    def analyze_coin(self, image_path: str) -> Dict[str, Any]:
        """
        Analyze a coin image using computer vision first, with OCR as supporting evidence.
        
        Args:
            image_path: Path to the coin image
            
        Returns:
            Dictionary with extracted information including grading and confidence scores
        """
        # Use computer vision to detect and identify the coin
        cv_result = self.recognizer.detect_coin(image_path)
        
        if cv_result['success']:
            # Get CV-based identification with confidence scores
            denomination = cv_result['denomination']
            denomination_confidence = cv_result['denomination_confidence']
            year = cv_result['year']
            year_confidence = cv_result['year_confidence']
            country = cv_result['country']
            country_confidence = cv_result['country_confidence']
            orientation = cv_result['orientation']
            ocr_text_preview = cv_result['ocr_text_preview']
            ocr_full_text = cv_result['ocr_full_text']
        else:
            # Fallback if CV detection failed
            denomination = 'unknown'
            denomination_confidence = 0.0
            year = 'Unknown'
            year_confidence = 0.0
            country = 'unknown'
            country_confidence = 0.0
            orientation = 'unknown'
            ocr_text_preview = 'CV detection failed'
            ocr_full_text = 'CV detection failed'
        
        # Estimate coin grade
        grade_info = self.grader.estimate_grade(image_path)
        
        return {
            'filename': image_path.split('\\')[-1],
            'country': country,
            'country_confidence': round(country_confidence * 100, 1),
            'denomination': denomination,
            'denomination_confidence': round(denomination_confidence * 100, 1),
            'year': year if year else 'Unknown',
            'year_confidence': round(year_confidence * 100, 1),
            'orientation': orientation,
            'ocr_text_preview': ocr_text_preview[:100],  # First 100 characters for display
            'ocr_full_text': ocr_full_text,
            'grade_range': grade_info['grade_range'],
            'grade_low': grade_info['grade_low'],
            'grade_high': grade_info['grade_high'],
            'confidence_score': grade_info['confidence_score'],
            'notes': grade_info['notes'],
            'wear_level': grade_info['wear_level'],
            'has_scratches': grade_info['has_scratches'],
            'has_corrosion': grade_info['has_corrosion'],
            'has_cleaning_marks': grade_info['has_cleaning_marks'],
            'has_damage': grade_info['has_damage'],
            'luster_present': grade_info['luster_present'],
            'image_quality_limitations': grade_info['image_quality_limitations']
        }
