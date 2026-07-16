"""
Controlled Year OCR Experiment
Tests multiple preprocessing variants and crop zones for year detection.
Does not modify main detection pipeline.
"""

import cv2
import numpy as np
import re
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEST_FOLDER = os.path.join(PROJECT_ROOT, "test_coins")
DEFAULT_DEBUG_FOLDER = os.path.join(PROJECT_ROOT, "debug_outputs", "year_ocr_crops")


def load_pytesseract():
    """Load the optional OCR dependency with an actionable error when unavailable."""
    try:
        import pytesseract
    except ImportError as error:
        raise RuntimeError(
            "Year OCR experiments require the optional 'pytesseract' package and a "
            "separately installed Tesseract executable."
        ) from error
    return pytesseract


class YearOCRExperiment:
    """Controlled experiment for year OCR detection."""
    
    def __init__(self):
        self.current_year = datetime.now().year
        self.year_pattern = r'\b(18[5-9][0-9]|19[0-9]{2}|20[0-9]{2})\b'
        
        # Preprocessing variants to test
        self.preprocessing_variants = [
            'grayscale',
            'grayscale_resize3x',
            'grayscale_contrast',
            'inverted_grayscale',
            'original'  # Add original color image as baseline
        ]
        
        # Crop zones to test
        self.crop_zones = [
            'bottom_25',
            'bottom_center',
            'lower_left',
            'lower_right',
            'full_coin'
        ]
        
        # Tesseract PSM modes to test
        self.psm_modes = ['7', '8', '10', '13']
    
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
    
    def apply_preprocessing(self, image: np.ndarray, variant: str) -> np.ndarray:
        """Apply preprocessing variant to image."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        if variant == 'grayscale':
            return gray
        elif variant == 'grayscale_resize3x':
            return cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        elif variant == 'grayscale_contrast':
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            return clahe.apply(gray)
        elif variant == 'inverted_grayscale':
            return cv2.bitwise_not(gray)
        else:
            return gray
    
    def crop_zone(self, image: np.ndarray, coin_info: Dict, zone: str) -> np.ndarray:
        """Crop image to specified zone."""
        x, y = coin_info['center']
        radius = coin_info['radius']
        
        if zone == 'full_coin':
            x1 = max(0, x - radius)
            y1 = max(0, y - radius)
            x2 = min(image.shape[1], x + radius)
            y2 = min(image.shape[0], y + radius)
            return image[y1:y2, x1:x2]
        
        elif zone == 'bottom_25':
            # Bottom 25% of coin
            crop_height = int(radius * 0.5)
            crop_width = int(radius * 0.8)
            crop_center_y = y + int(radius * 0.4)
            x1 = max(0, x - crop_width // 2)
            y1 = max(0, crop_center_y - crop_height // 2)
            x2 = min(image.shape[1], x + crop_width // 2)
            y2 = min(image.shape[0], crop_center_y + crop_height // 2)
            return image[y1:y2, x1:x2]
        
        elif zone == 'bottom_center':
            # Bottom center area
            crop_height = int(radius * 0.4)
            crop_width = int(radius * 0.6)
            crop_center_y = y + int(radius * 0.3)
            x1 = max(0, x - crop_width // 2)
            y1 = max(0, crop_center_y - crop_height // 2)
            x2 = min(image.shape[1], x + crop_width // 2)
            y2 = min(image.shape[0], crop_center_y + crop_height // 2)
            return image[y1:y2, x1:x2]
        
        elif zone == 'lower_left':
            # Lower left quadrant
            crop_height = int(radius * 0.4)
            crop_width = int(radius * 0.4)
            crop_center_x = x - int(radius * 0.3)
            crop_center_y = y + int(radius * 0.3)
            x1 = max(0, crop_center_x - crop_width // 2)
            y1 = max(0, crop_center_y - crop_height // 2)
            x2 = min(image.shape[1], crop_center_x + crop_width // 2)
            y2 = min(image.shape[0], crop_center_y + crop_height // 2)
            return image[y1:y2, x1:x2]
        
        elif zone == 'lower_right':
            # Lower right quadrant
            crop_height = int(radius * 0.4)
            crop_width = int(radius * 0.4)
            crop_center_x = x + int(radius * 0.3)
            crop_center_y = y + int(radius * 0.3)
            x1 = max(0, crop_center_x - crop_width // 2)
            y1 = max(0, crop_center_y - crop_height // 2)
            x2 = min(image.shape[1], crop_center_x + crop_width // 2)
            y2 = min(image.shape[0], crop_center_y + crop_height // 2)
            return image[y1:y2, x1:x2]
        
        else:
            return image
    
    def extract_years_from_ocr(self, text: str) -> List[str]:
        """Extract years from OCR text."""
        matches = re.findall(self.year_pattern, text)
        return matches
    
    def run_ocr(self, image: np.ndarray, psm_mode: str, use_whitelist: bool = True) -> Tuple[str, str]:
        """Run OCR with digit-only configuration."""
        try:
            pytesseract = load_pytesseract()
            if use_whitelist:
                config = f'--psm {psm_mode} --oem 3 -c tessedit_char_whitelist=0123456789'
            else:
                config = f'--psm {psm_mode} --oem 3'
            text = pytesseract.image_to_string(image, config=config)
            return text, ""
        except Exception as e:
            return "", str(e)
    
    def test_image(self, image_path: str, expected_year: str) -> List[Dict]:
        """Test all variants on a single image."""
        results = []
        
        # Detect coin circle
        coin_info = self.detect_coin_circle(image_path)
        if coin_info is None:
            print(f"Failed to detect coin in {image_path}")
            return results
        
        # Load image
        img = cv2.imread(image_path)
        if img is None:
            print(f"Failed to load {image_path}")
            return results
        
        # Save debug crops for visual inspection
        debug_folder = DEFAULT_DEBUG_FOLDER
        os.makedirs(debug_folder, exist_ok=True)
        
        filename = os.path.basename(image_path)
        
        # Test all combinations
        for preprocessing in self.preprocessing_variants:
            for zone in self.crop_zones:
                # Crop and preprocess
                cropped = self.crop_zone(img, coin_info, zone)
                
                # Save debug crop for first preprocessing variant
                if preprocessing == 'grayscale':
                    crop_debug_path = os.path.join(debug_folder, f"{filename}_{zone}.jpg")
                    cv2.imwrite(crop_debug_path, cropped)
                
                preprocessed = self.apply_preprocessing(cropped, preprocessing)
                
                # Test all PSM modes with and without whitelist
                for psm in self.psm_modes:
                    for use_whitelist in [True, False]:
                        text, error = self.run_ocr(preprocessed, psm, use_whitelist)
                        
                        # Extract years
                        years = self.extract_years_from_ocr(text)
                        
                        # Calculate confidence
                        confidence = 0.0
                        detected_year = "Unknown"
                        if years:
                            # Use first match as detected year
                            detected_year = years[0]
                            # Simple confidence: if expected year matches, high confidence
                            if detected_year == expected_year:
                                confidence = 1.0
                            elif expected_year in years:
                                confidence = 0.8
                            else:
                                confidence = 0.3
                        
                        result = {
                            'filename': filename,
                            'expected_year': expected_year,
                            'detected_year': detected_year,
                            'crop_zone': zone,
                            'preprocessing': preprocessing,
                            'psm_mode': psm,
                            'use_whitelist': use_whitelist,
                            'confidence': confidence,
                            'ocr_text': text[:100],  # First 100 chars
                            'error': error
                        }
                        results.append(result)
        
        return results
    
    def run_experiment(self, test_folder: str, expected_years: Dict[str, str]) -> List[Dict]:
        """Run experiment on all test images."""
        all_results = []
        
        for filename, expected_year in expected_years.items():
            image_path = os.path.join(test_folder, filename)
            print(f"Testing {filename}...")
            results = self.test_image(image_path, expected_year)
            all_results.extend(results)
        
        return all_results
    
    def print_results_table(self, results: List[Dict]):
        """Print results in table format."""
        print("\n" + "=" * 140)
        print("YEAR OCR EXPERIMENT RESULTS")
        print("=" * 140)
        print(f"{'Filename':<20} {'Expected':<10} {'Detected':<10} {'Zone':<15} {'Preproc':<20} {'PSM':<5} {'WL':<5} {'Conf':<6} {'OCR Text':<40}")
        print("-" * 140)
        
        for result in results:
            wl = 'Y' if result['use_whitelist'] else 'N'
            print(f"{result['filename']:<20} {result['expected_year']:<10} {result['detected_year']:<10} "
                  f"{result['crop_zone']:<15} {result['preprocessing']:<20} {result['psm_mode']:<5} "
                  f"{wl:<5} {result['confidence']:<6.2f} {result['ocr_text']:<40}")
        
        print("=" * 140)
        
        # Summary statistics
        correct = sum(1 for r in results if r['detected_year'] == r['expected_year'])
        total = len(results)
        accuracy = (correct / total * 100) if total > 0 else 0
        
        print(f"\nTotal tests: {total}")
        print(f"Correct detections: {correct}")
        print(f"Accuracy: {accuracy:.2f}%")
        
        # Best performing combinations
        print("\nTop 10 performing combinations:")
        sorted_results = sorted(results, key=lambda x: x['confidence'], reverse=True)
        for i, result in enumerate(sorted_results[:10]):
            wl = 'Y' if result['use_whitelist'] else 'N'
            print(f"{i+1}. {result['preprocessing']} + {result['crop_zone']} + PSM {result['psm_mode']} (WL:{wl}) "
                  f"- Confidence: {result['confidence']:.2f} - Detected: {result['detected_year']}")
        
        # Show some sample OCR output for debugging
        print("\nSample OCR output (first 5 non-empty results):")
        count = 0
        for result in results:
            if result['ocr_text'].strip() and count < 5:
                print(f"\n{result['filename']} - {result['preprocessing']} - {result['crop_zone']} - PSM {result['psm_mode']}:")
                print(f"  OCR: {result['ocr_text']}")
                count += 1


def main():
    """Run the year OCR experiment."""
    experiment = YearOCRExperiment()
    
    # Test folder
    test_folder = DEFAULT_TEST_FOLDER
    
    # Expected years for test images (you'll need to fill these in manually)
    expected_years = {
        'IMG_3460.jpeg': '1967',  # Example - replace with actual expected years
        'IMG_3461.jpeg': '1968',
        'IMG_3462.jpeg': '1969',
        'IMG_3463.jpeg': '1970',
        'IMG_3464.jpeg': '1971',
        'IMG_3465.jpeg': '1972',
        'IMG_3466.jpeg': '1973',
        'IMG_3467.jpeg': '1974',
        'IMG_3468.jpeg': '1975',
        'IMG_3469.jpeg': '1976',
    }
    
    print("Starting Year OCR Experiment...")
    print(f"Test folder: {test_folder}")
    print(f"Images to test: {len(expected_years)}")
    
    results = experiment.run_experiment(test_folder, expected_years)
    experiment.print_results_table(results)


if __name__ == "__main__":
    main()
