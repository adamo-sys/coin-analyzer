"""
Template matching based year detection for coins.
Experimental local implementation using full_coin images with manual date regions.
"""

import cv2
import numpy as np
import os
import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEST_FOLDER = os.path.join(PROJECT_ROOT, "test_coins")
DEFAULT_DEBUG_FOLDER = os.path.join(PROJECT_ROOT, "debug_outputs", "template_matching")


class TemplateMatchingYearDetector:
    """Template matching based year detection (experimental)."""
    
    def __init__(self, debug_folder: str = None):
        self.current_year = datetime.now().year
        self.year_pattern = r'\b(18[5-9][0-9]|19[0-9]{2}|20[0-9]{2})\b'
        self.debug_folder = os.path.abspath(debug_folder or DEFAULT_DEBUG_FOLDER)
        
        # Manual date regions for full_coin images (relative coordinates 0-1)
        # Format: (x_center, y_center, width, height) as fractions of image dimensions
        self.date_regions = {
            'default': (0.5, 0.75, 0.4, 0.25),  # Center bottom
            'bottom_center': (0.5, 0.8, 0.3, 0.2),
            'bottom_left': (0.3, 0.8, 0.25, 0.2),
            'bottom_right': (0.7, 0.8, 0.25, 0.2)
        }
        
        # Digit templates (will be created from sample images)
        self.digit_templates = {}
        
    def detect_coin_circle(self, image_path: str) -> Optional[Dict]:
        """Detect coin circle using Hough Circle Transform."""
        try:
            img = cv2.imread(image_path)
            if img is None:
                return None
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (9, 9), 2)
            
            circles = cv2.HoughCircles(
                gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=100,
                param1=50, param2=30, minRadius=50, maxRadius=300
            )
            
            if circles is not None:
                circles = np.round(circles[0, :]).astype("int")
                x, y, radius = circles[0]
                return {'center': (x, y), 'radius': radius}
            
            return None
        except Exception as e:
            print(f"Error detecting coin circle: {str(e)}")
            return None
    
    def extract_date_region(self, image: np.ndarray, region_name: str = 'default') -> np.ndarray:
        """Extract date region from full coin image."""
        if region_name not in self.date_regions:
            region_name = 'default'
        
        x_center, y_center, width, height = self.date_regions[region_name]
        
        h, w = image.shape[:2]
        
        # Convert relative coordinates to absolute
        x1 = int(max(0, (x_center - width/2) * w))
        y1 = int(max(0, (y_center - height/2) * h))
        x2 = int(min(w, (x_center + width/2) * w))
        y2 = int(min(h, (y_center + height/2) * h))
        
        return image[y1:y2, x1:x2]
    
    def preprocess_for_digits(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for digit detection."""
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Apply thresholding
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Invert if needed (digits should be dark on light background)
        if np.mean(binary[:10, :10]) > 127:  # Check top-left corner
            binary = 255 - binary
        
        # Apply morphological operations
        kernel = np.ones((2, 2), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        return binary
    
    def detect_digit_contours(self, image: np.ndarray) -> List[Dict]:
        """Detect potential digit contours in image."""
        # Preprocess
        processed = self.preprocess_for_digits(image)
        
        # Find contours
        contours, _ = cv2.findContours(processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        digit_candidates = []
        
        for contour in contours:
            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter by aspect ratio and size
            aspect_ratio = w / h if h > 0 else 0
            area = w * h
            
            # Typical digit characteristics
            if (0.2 < aspect_ratio < 0.8 and  # Digits are taller than wide
                50 < area < 5000 and  # Reasonable size
                h > 10 and w > 5):  # Minimum dimensions
                
                digit_candidates.append({
                    'contour': contour,
                    'bbox': (x, y, w, h),
                    'aspect_ratio': aspect_ratio,
                    'area': area
                })
        
        # Sort by x position (left to right)
        digit_candidates.sort(key=lambda d: d['bbox'][0])
        
        return digit_candidates
    
    def extract_year_from_contours(self, digit_candidates: List[Dict], image: np.ndarray) -> Tuple[str, float]:
        """Extract year from detected digit contours."""
        if len(digit_candidates) < 4:
            return "unknown", 0.0
        
        # Try to form 4-digit year from contours
        years = []
        
        # Try different combinations of 4 contours
        for i in range(len(digit_candidates) - 3):
            # Get 4 consecutive contours
            four_digits = digit_candidates[i:i+4]
            
            # Extract digit images
            digit_images = []
            for digit in four_digits:
                x, y, w, h = digit['bbox']
                digit_img = image[y:y+h, x:x+w]
                digit_images.append(digit_img)
            
            # Try to recognize digits (simplified approach)
            year_str = self.recognize_digits_simple(digit_images)
            
            if year_str and self.is_valid_year(year_str):
                years.append((year_str, 0.5))  # Base confidence
        
        if not years:
            return "unknown", 0.0
        
        # Return the most likely year
        return years[0]
    
    def recognize_digits_simple(self, digit_images: List[np.ndarray]) -> Optional[str]:
        """Simple digit recognition using template matching (placeholder)."""
        # This is a simplified approach
        # In a real implementation, you would use trained digit templates
        # For now, return None to indicate this needs proper implementation
        return None
    
    def is_valid_year(self, year_str: str) -> bool:
        """Check if year string is valid."""
        if not year_str or len(year_str) != 4:
            return False
        
        try:
            year = int(year_str)
            return 1850 <= year <= self.current_year
        except ValueError:
            return False
    
    def detect_year(self, image_path: str, save_debug: bool = True) -> Dict:
        """
        Detect year from coin image using template matching.
        
        Args:
            image_path: Path to coin image
            save_debug: Whether to save debug images
            
        Returns:
            Dictionary with detection results
        """
        result = {
            'success': False,
            'year': 'unknown',
            'confidence': 0.0,
            'method': 'template_matching',
            'debug_info': {},
            'error': None
        }
        
        try:
            # Load image
            img = cv2.imread(image_path)
            if img is None:
                result['error'] = f"Failed to load image: {image_path}"
                return result
            
            # Detect coin circle
            coin_info = self.detect_coin_circle(image_path)
            if not coin_info:
                result['error'] = "Failed to detect coin circle"
                return result
            
            # Extract date region
            date_region = self.extract_date_region(img, 'default')
            
            # Detect digit contours
            digit_candidates = self.detect_digit_contours(date_region)
            
            result['debug_info']['num_candidates'] = len(digit_candidates)
            result['debug_info']['date_region_shape'] = date_region.shape
            
            # Extract year
            year, confidence = self.extract_year_from_contours(digit_candidates, date_region)
            result['year'] = year
            result['confidence'] = confidence
            
            if year != 'unknown':
                result['success'] = True
            
            # Save debug images
            if save_debug:
                self.save_debug_images(image_path, img, date_region, digit_candidates, result)
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def save_debug_images(self, image_path: str, full_image: np.ndarray, 
                         date_region: np.ndarray, digit_candidates: List[Dict], 
                         result: Dict):
        """Save debug images for analysis."""
        os.makedirs(self.debug_folder, exist_ok=True)
        filename = os.path.basename(image_path)
        name_without_ext = os.path.splitext(filename)[0]
        
        # Save date region
        region_path = os.path.join(self.debug_folder, f"{name_without_ext}_date_region.jpg")
        cv2.imwrite(region_path, date_region)
        
        # Save date region with detected contours
        contour_img = date_region.copy()
        if len(contour_img.shape) == 2:
            contour_img = cv2.cvtColor(contour_img, cv2.COLOR_GRAY2BGR)
        
        for digit in digit_candidates:
            x, y, w, h = digit['bbox']
            cv2.rectangle(contour_img, (x, y), (x+w, y+h), (0, 255, 0), 2)
        
        contour_path = os.path.join(self.debug_folder, f"{name_without_ext}_contours.jpg")
        cv2.imwrite(contour_path, contour_img)
        
        result['debug_info']['debug_images'] = {
            'date_region': region_path,
            'contours': contour_path
        }


def test_template_matching():
    """Test template matching year detection on test images."""
    detector = TemplateMatchingYearDetector()
    
    test_folder = DEFAULT_TEST_FOLDER
    
    print("=" * 60)
    print("Template Matching Year Detection - Experimental Test")
    print("=" * 60)
    
    results = []
    
    for filename in sorted(os.listdir(test_folder), key=str.casefold):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            image_path = os.path.join(test_folder, filename)
            print(f"\nTesting: {filename}")
            
            result = detector.detect_year(image_path, save_debug=True)
            results.append(result)
            
            print(f"  Success: {result['success']}")
            print(f"  Year: {result['year']}")
            print(f"  Confidence: {result['confidence']}")
            if result['error']:
                print(f"  Error: {result['error']}")
            print(f"  Candidates: {result['debug_info'].get('num_candidates', 0)}")
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    successful = sum(1 for r in results if r['success'])
    print(f"Total images: {len(results)}")
    print(f"Successful detections: {successful}")
    print(f"Success rate: {successful/len(results)*100:.1f}%")
    print(f"\nNote: This is experimental template matching.")
    print(f"Do not claim production accuracy.")
    print(f"Debug images saved to: {detector.debug_folder}")


if __name__ == "__main__":
    test_template_matching()
