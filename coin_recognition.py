"""
Coin Recognition Module
This module uses computer vision techniques to identify Canadian coins.
Uses pattern matching and image classification instead of OCR-first approach.
"""

import cv2
import numpy as np
from typing import Dict, Tuple, Optional, List
import re
import os
import platform
from datetime import datetime


class CoinRecognizer:
    """Identifies Canadian coins using computer vision techniques."""
    
    def __init__(self):
        """Initialize the coin recognizer."""
        # Configure Tesseract path for Windows
        self.configure_tesseract()
        
        # Canadian coin specifications (approximate diameters in pixels for reference)
        # These are relative sizes - actual detection will use proportional analysis
        self.coin_specs = {
            'penny': {'diameter_ratio': 0.85, 'color': 'copper'},
            'nickel': {'diameter_ratio': 0.90, 'color': 'silver'},
            'dime': {'diameter_ratio': 0.70, 'color': 'silver'},
            'quarter': {'diameter_ratio': 1.00, 'color': 'silver'},
            '50_cent': {'diameter_ratio': 1.15, 'color': 'silver'},
            'dollar': {'diameter_ratio': 1.10, 'color': 'gold'}
        }
        
        # Common year patterns for digit recognition
        self.year_patterns = {
            '0': [cv2.imread('templates/0.png', 0)] if False else [],
            '1': [],
            '2': [],
            '3': [],
            '4': [],
            '5': [],
            '6': [],
            '7': [],
            '8': [],
            '9': []
        }
    
    def configure_tesseract(self):
        """
        Configure Tesseract OCR path for Windows.
        Automatically detects Tesseract installation at common Windows paths.
        """
        if platform.system() == 'Windows':
            # Common Windows Tesseract installation paths
            tesseract_paths = [
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                r'C:\Tesseract-OCR\tesseract.exe'
            ]
            
            for path in tesseract_paths:
                if os.path.exists(path):
                    try:
                        import pytesseract
                        pytesseract.pytesseract.tesseract_cmd = path
                        print(f"Tesseract configured at: {path}")
                        return
                    except ImportError:
                        print("pytesseract not available, OCR support disabled")
                        return
            
            print("Tesseract not found at common Windows paths. OCR may not work.")
        else:
            # On non-Windows systems, assume Tesseract is in PATH
            print("Non-Windows system detected. Assuming Tesseract is in PATH.")
    
    def detect_coin(self, image_path: str) -> Dict:
        """
        Detect and analyze a coin from an image.
        
        Args:
            image_path: Path to the coin image
            
        Returns:
            Dictionary with coin detection results including confidence scores
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return {'success': False, 'error': 'Could not read image'}
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Detect coin using circle detection
            coin_info = self.detect_coin_circle(gray, img)
            
            if not coin_info['success']:
                return {'success': False, 'error': 'Could not detect coin'}
            
            # Segment the coin from the background
            coin_segment = self.segment_coin(gray, coin_info)
            
            # Identify denomination with confidence
            denomination_result = self.identify_denomination(coin_segment, coin_info)
            
            # Identify obverse vs reverse
            orientation = self.identify_orientation(coin_segment)
            
            # Detect year with confidence and OCR variants using cropped date region
            year_result = self.detect_year(coin_segment, orientation, image_path, coin_info)
            
            # Detect country with confidence (no default to Canada)
            country_result = self.detect_country(image_path, year_result['all_ocr_text'])
            
            return {
                'success': True,
                'denomination': denomination_result['denomination'],
                'denomination_confidence': denomination_result['confidence'],
                'year': year_result['year'],
                'year_confidence': year_result['confidence'],
                'year_candidates': year_result['candidates'],
                'country': country_result['country'],
                'country_confidence': country_result['confidence'],
                'orientation': orientation,
                'ocr_text_preview': year_result['all_ocr_text'][:500],  # First 500 chars for preview
                'ocr_full_text': year_result['all_ocr_text'],
                'coin_info': coin_info
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def detect_coin_circle(self, gray: np.ndarray, original: np.ndarray) -> Dict:
        """
        Detect coin using Hough Circle Transform.
        
        Args:
            gray: Grayscale image
            original: Original color image
            
        Returns:
            Dictionary with circle detection results
        """
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)
        
        # Detect circles using Hough Circle Transform
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=100,
            param1=50,
            param2=30,
            minRadius=50,
            maxRadius=300
        )
        
        if circles is None:
            return {'success': False}
        
        circles = np.round(circles[0, :]).astype("int")
        
        # Take the largest circle (assuming it's the coin)
        if len(circles) > 0:
            # Sort by radius (descending)
            circles = sorted(circles, key=lambda x: x[2], reverse=True)
            x, y, radius = circles[0]
            
            return {
                'success': True,
                'center': (x, y),
                'radius': radius,
                'diameter': radius * 2
            }
        
        return {'success': False}
    
    def segment_coin(self, gray: np.ndarray, coin_info: Dict) -> np.ndarray:
        """
        Segment the coin from the background.
        
        Args:
            gray: Grayscale image
            coin_info: Coin detection information
            
        Returns:
            Segmented coin image
        """
        x, y = coin_info['center']
        radius = coin_info['radius']
        
        # Create circular mask
        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.circle(mask, (x, y), radius, 255, -1)
        
        # Apply mask to get coin region
        coin_segment = cv2.bitwise_and(gray, gray, mask=mask)
        
        # Crop to bounding box of the coin
        x1 = max(0, x - radius)
        y1 = max(0, y - radius)
        x2 = min(gray.shape[1], x + radius)
        y2 = min(gray.shape[0], y + radius)
        
        coin_crop = coin_segment[y1:y2, x1:x2]
        
        return coin_crop
    
    def identify_denomination(self, coin_segment: np.ndarray, coin_info: Dict) -> Dict:
        """
        Identify coin denomination using size and color analysis with confidence scoring.
        
        Args:
            coin_segment: Segmented coin image
            coin_info: Coin detection information
            
        Returns:
            Dictionary with denomination and confidence score
        """
        # Analyze color
        color = self.analyze_color(coin_segment)
        
        # Analyze size relative to image
        radius = coin_info['radius']
        image_diagonal = np.sqrt(coin_segment.shape[0]**2 + coin_segment.shape[1]**2)
        size_ratio = radius / (image_diagonal / 2)
        
        # Match against specifications with confidence scoring
        candidates = []
        
        for denom, spec in self.coin_specs.items():
            # Score based on size similarity
            size_score = 1 - abs(size_ratio - spec['diameter_ratio'] * 0.5)
            
            # Score based on color match
            color_score = 1 if color == spec['color'] else 0.5
            
            # Combined score
            total_score = (size_score * 0.7) + (color_score * 0.3)
            
            candidates.append({
                'denomination': denom,
                'confidence': total_score
            })
        
        # Sort by confidence
        candidates.sort(key=lambda x: x['confidence'], reverse=True)
        
        best_candidate = candidates[0]
        
        # Return unknown if confidence is too low
        if best_candidate['confidence'] < 0.5:
            return {
                'denomination': 'unknown',
                'confidence': best_candidate['confidence'],
                'candidates': candidates
            }
        
        return {
            'denomination': best_candidate['denomination'],
            'confidence': best_candidate['confidence'],
            'candidates': candidates
        }
    
    def analyze_color(self, coin_segment: np.ndarray) -> str:
        """
        Analyze coin color to determine metal type.
        
        Args:
            coin_segment: Segmented coin image
            
        Returns:
            Color string ('copper', 'silver', 'gold')
        """
        # Convert to color if needed (this would need the original color image)
        # For now, use grayscale analysis
        mean_intensity = np.mean(coin_segment)
        
        # Simple heuristic based on intensity
        # Copper coins (pennies) tend to be darker
        # Silver coins are brighter
        # Gold coins (dollar) have intermediate values
        
        if mean_intensity < 100:
            return 'copper'
        elif mean_intensity > 150:
            return 'silver'
        else:
            return 'gold'
    
    def identify_orientation(self, coin_segment: np.ndarray) -> str:
        """
        Identify if the coin shows obverse (heads) or reverse (tails).
        
        Args:
            coin_segment: Segmented coin image
            
        Returns:
            Orientation string ('obverse', 'reverse', 'unknown')
        """
        # This would typically use template matching or feature detection
        # For Canadian coins:
        # Obverse: Portrait of the monarch
        # Reverse: Varies by denomination (caribou for quarter, loon for dollar, etc.)
        
        # Simple heuristic: look for portrait-like features
        # Use edge density and symmetry analysis
        
        # Calculate edge density
        edges = cv2.Canny(coin_segment, 50, 150)
        edge_density = np.sum(edges) / (edges.shape[0] * edges.shape[1])
        
        # Obverse (portrait) typically has more complex features
        if edge_density > 0.15:
            return 'obverse'
        else:
            return 'reverse'
    
    def detect_year(self, coin_segment: np.ndarray, orientation: str, image_path: str, coin_info: Dict) -> Dict:
        """
        Detect year from coin using text region detection and OCR.
        
        Args:
            coin_segment: Segmented coin image
            orientation: Coin orientation (obverse/reverse)
            image_path: Path to original image for OCR variants
            coin_info: Coin detection information (center, radius)
            
        Returns:
            Dictionary with year detection results including confidence and candidates
        """
        current_year = datetime.now().year
        year_pattern = r'\b(18[5-9][0-9]|19[0-9]{2}|20[0-9]{2})\b'
        
        # Detect text regions in the coin image
        text_regions = self.detect_text_regions(image_path, coin_info)
        
        if not text_regions:
            return {
                'year': None,
                'confidence': 0.0,
                'candidates': [],
                'all_ocr_text': 'No text regions detected'
            }
        
        # Extract years from each text region with confidence scoring
        year_candidates = []
        all_ocr_text = []
        
        for i, region in enumerate(text_regions):
            try:
                import pytesseract
                # Try different OCR configurations
                configs = [
                    '--psm 7 --oem 3',  # Treat as single text line
                    '--psm 6 --oem 3',  # Assume uniform block of text
                ]
                
                for config in configs:
                    text = pytesseract.image_to_string(region, config=config)
                    all_ocr_text.append(f"region_{i} ({config}): {text[:100]}")
                    
                    # Find all year matches
                    matches = re.findall(year_pattern, text)
                    
                    for match in matches:
                        year = int(match)
                        # Validate year is in reasonable range
                        if 1850 <= year <= current_year:
                            # Calculate confidence
                            confidence = self.calculate_year_confidence(f"region_{i}", text, match)
                            year_candidates.append({
                                'year': match,
                                'confidence': confidence,
                                'source': f"region_{i} ({config})"
                            })
            except Exception as e:
                all_ocr_text.append(f"region_{i}: OCR Error - {str(e)}")
        
        # Sort candidates by confidence (descending)
        year_candidates.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Select best year if confidence is high enough
        best_year = None
        year_confidence = 0.0
        
        if year_candidates and year_candidates[0]['confidence'] > 0.3:
            best_year = year_candidates[0]['year']
            year_confidence = year_candidates[0]['confidence']
        
        return {
            'year': best_year,
            'confidence': year_confidence,
            'candidates': year_candidates,
            'all_ocr_text': '\n'.join(all_ocr_text)
        }
    
    def detect_text_regions(self, image_path: str, coin_info: Dict) -> List[np.ndarray]:
        """
        Detect potential text regions in the coin image using contour analysis.
        
        Args:
            image_path: Path to original image
            coin_info: Coin detection information (center, radius)
            
        Returns:
            List of detected text regions
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return []
            
            x, y = coin_info['center']
            radius = coin_info['radius']
            
            # Crop to coin region
            x1 = max(0, x - radius - 20)
            y1 = max(0, y - radius - 20)
            x2 = min(img.shape[1], x + radius + 20)
            y2 = min(img.shape[0], y + radius + 20)
            coin_region = img[y1:y2, x1:x2]
            
            # Convert to grayscale
            gray = cv2.cvtColor(coin_region, cv2.COLOR_BGR2GRAY)
            
            # Apply adaptive threshold to get binary image
            binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                         cv2.THRESH_BINARY_INV, 11, 2)
            
            # Find contours
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            text_regions = []
            
            for contour in contours:
                # Get bounding rectangle
                rect = cv2.boundingRect(contour)
                rx, ry, rw, rh = rect
                
                # Filter contours by size and aspect ratio (text-like regions)
                aspect_ratio = rw / rh if rh > 0 else 0
                area = rw * rh
                
                # Text regions typically have:
                # - Aspect ratio between 0.5 and 5
                # - Area between 100 and 50000 pixels
                # - Height between 10 and 100 pixels
                if 0.5 < aspect_ratio < 5 and 100 < area < 50000 and 10 < rh < 100:
                    # Extract the region
                    region = gray[ry:ry+rh, rx:rx+rw]
                    
                    # Upscale for better OCR
                    if rw > 0 and rh > 0:
                        upscaled = cv2.resize(region, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
                        text_regions.append(upscaled)
            
            # Also add the lower portion of the coin as a fallback
            crop_height = int(radius * 0.6)
            crop_width = int(radius * 0.8)
            crop_center_y = y + int(radius * 0.2)
            cx1 = max(0, x - crop_width // 2)
            cy1 = max(0, crop_center_y - crop_height // 2)
            cx2 = min(img.shape[1], x + crop_width // 2)
            cy2 = min(img.shape[0], crop_center_y + crop_height // 2)
            date_crop = img[cy1:cy2, cx1:cx2]
            date_crop_gray = cv2.cvtColor(date_crop, cv2.COLOR_BGR2GRAY)
            date_crop_upscaled = cv2.resize(date_crop_gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            text_regions.append(date_crop_upscaled)
            
            return text_regions
            
        except Exception as e:
            print(f"Error detecting text regions: {str(e)}")
            return []
    
    def crop_date_region(self, image_path: str, coin_info: Dict) -> Optional[np.ndarray]:
        """
        Crop the lower portion of the coin where dates usually appear.
        Try multiple crop regions and return the best one.
        
        Args:
            image_path: Path to original image
            coin_info: Coin detection information (center, radius)
            
        Returns:
            Cropped date region or None if detection failed
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return None
            
            x, y = coin_info['center']
            radius = coin_info['radius']
            
            # Try multiple crop regions to find the best one
            crop_regions = []
            
            # Region 1: Lower portion (traditional date location)
            crop_height = int(radius * 0.7)
            crop_width = int(radius * 0.8)
            crop_center_y = y + int(radius * 0.2)
            x1 = max(0, x - crop_width // 2)
            y1 = max(0, crop_center_y - crop_height // 2)
            x2 = min(img.shape[1], x + crop_width // 2)
            y2 = min(img.shape[0], crop_center_y + crop_height // 2)
            crop_regions.append(img[y1:y2, x1:x2])
            
            # Region 2: Bottom edge (dates often at very bottom)
            crop_height = int(radius * 0.5)
            crop_width = int(radius * 0.9)
            crop_center_y = y + int(radius * 0.4)
            x1 = max(0, x - crop_width // 2)
            y1 = max(0, crop_center_y - crop_height // 2)
            x2 = min(img.shape[1], x + crop_width // 2)
            y2 = min(img.shape[0], crop_center_y + crop_height // 2)
            crop_regions.append(img[y1:y2, x1:x2])
            
            # Region 3: Center-lower (alternative date location)
            crop_height = int(radius * 0.6)
            crop_width = int(radius * 0.7)
            crop_center_y = y + int(radius * 0.1)
            x1 = max(0, x - crop_width // 2)
            y1 = max(0, crop_center_y - crop_height // 2)
            x2 = min(img.shape[1], x + crop_width // 2)
            y2 = min(img.shape[0], crop_center_y + crop_height // 2)
            crop_regions.append(img[y1:y2, x1:x2])
            
            # Use the largest region (most likely to contain date)
            best_crop = max(crop_regions, key=lambda x: x.shape[0] * x.shape[1])
            
            # Save the cropped date image to debug folder
            filename = os.path.basename(image_path)
            debug_path = os.path.join('debug_outputs', 'date_crops', f'crop_{filename}')
            cv2.imwrite(debug_path, best_crop)
            
            return best_crop
            
        except Exception as e:
            print(f"Error cropping date region: {str(e)}")
            return None
    
    def generate_date_crop_variants(self, date_crop: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Generate multiple preprocessing versions of the date crop for OCR.
        
        Args:
            date_crop: Cropped date region image
            
        Returns:
            Dictionary of preprocessed image variants
        """
        variants = {}
        
        # Convert to grayscale first
        gray = cv2.cvtColor(date_crop, cv2.COLOR_BGR2GRAY)
        
        # 1. Original grayscale
        variants['original'] = gray
        
        # 2. Upscaled for better OCR (2x)
        upscaled = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        variants['upscaled'] = upscaled
        
        # 3. Sharpened
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(gray, -1, kernel)
        variants['sharpened'] = sharpened
        
        # 4. Thresholded (binary) with Otsu
        _, thresholded = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants['thresholded'] = thresholded
        
        # 5. Inverted (for light text on dark background)
        inverted = cv2.bitwise_not(gray)
        variants['inverted'] = inverted
        
        # 6. High contrast using CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        high_contrast = clahe.apply(gray)
        variants['high_contrast'] = high_contrast
        
        # 7. Adaptive threshold (better for uneven lighting)
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                         cv2.THRESH_BINARY, 11, 2)
        variants['adaptive_threshold'] = adaptive
        
        # 8. Denoised
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        variants['denoised'] = denoised
        
        # 9. Morphological operations to clean up text
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        morph = cv2.morphologyEx(thresholded, cv2.MORPH_CLOSE, kernel)
        variants['morphological'] = morph
        
        return variants
    
    def generate_ocr_variants(self, image_path: str) -> Dict[str, np.ndarray]:
        """
        Generate multiple image variants for OCR processing.
        
        Args:
            image_path: Path to original image
            
        Returns:
            Dictionary of image variants
        """
        img = cv2.imread(image_path)
        if img is None:
            return {}
        
        variants = {}
        
        # 1. Original
        variants['original'] = img
        
        # 2. Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        variants['grayscale'] = gray
        
        # 3. Adaptive threshold
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                         cv2.THRESH_BINARY, 11, 2)
        variants['adaptive_threshold'] = adaptive
        
        # 4. Inverted
        inverted = cv2.bitwise_not(gray)
        variants['inverted'] = inverted
        
        # 5. Sharpened
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(gray, -1, kernel)
        variants['sharpened'] = sharpened
        
        return variants
    
    def calculate_year_confidence(self, variant_name: str, text: str, year_match: str) -> float:
        """
        Calculate confidence score for a year detection.
        
        Args:
            variant_name: Name of the OCR variant used
            text: Full OCR text
            year_match: The matched year string
            
        Returns:
            Confidence score between 0 and 1
        """
        base_confidence = 0.5
        
        # Boost confidence for certain variants
        variant_boosts = {
            'adaptive_threshold': 0.2,
            'grayscale': 0.1,
            'sharpened': 0.15,
            'inverted': 0.05,
            'original': 0.0
        }
        
        confidence = base_confidence + variant_boosts.get(variant_name, 0.0)
        
        # Boost if year appears multiple times
        year_count = text.count(year_match)
        if year_count > 1:
            confidence += 0.1
        
        # Boost if year is surrounded by digits (more likely to be actual year)
        year_index = text.find(year_match)
        if year_index > 0:
            prev_char = text[year_index - 1]
            next_char = text[year_index + len(year_match)] if year_index + len(year_match) < len(text) else ' '
            if prev_char.isdigit() or next_char.isdigit():
                confidence += 0.05
        
        # Cap at 1.0
        return min(confidence, 1.0)
    
    def detect_country(self, image_path: str, ocr_text: str) -> Dict:
        """
        Detect country from OCR text with confidence scoring.
        Does NOT default to Canada - returns "Unknown" if confidence is low.
        
        Args:
            image_path: Path to the coin image
            ocr_text: OCR text from multiple variants
            
        Returns:
            Dictionary with country and confidence score
        """
        # Common country names and their variations
        country_patterns = {
            'canada': ['canada', 'canadian', 'ca', 'can'],
            'united states': ['usa', 'united states', 'america', 'us', 'united states of america'],
            'united kingdom': ['uk', 'united kingdom', 'great britain', 'britain', 'england'],
            'australia': ['australia', 'australian', 'aus'],
            'france': ['france', 'french', 'fr'],
            'germany': ['germany', 'german', 'deutschland', 'de'],
            'japan': ['japan', 'japanese', 'jp'],
            'china': ['china', 'chinese', 'cn'],
            'mexico': ['mexico', 'mexican', 'mx'],
            'spain': ['spain', 'spanish', 'es']
        }
        
        text_lower = ocr_text.lower()
        
        # Score each country based on matches
        country_scores = {}
        for country, patterns in country_patterns.items():
            score = 0
            for pattern in patterns:
                if pattern in text_lower:
                    # Exact match gets higher score
                    if pattern == text_lower:
                        score += 1.0
                    # Partial match gets lower score
                    else:
                        score += 0.5
            country_scores[country] = score
        
        # Find best match
        best_country = 'unknown'
        best_score = 0.0
        
        for country, score in country_scores.items():
            if score > best_score:
                best_score = score
                best_country = country
        
        # Return unknown if confidence is too low
        if best_score < 0.5:
            return {
                'country': 'unknown',
                'confidence': best_score
            }
        
        return {
            'country': best_country.capitalize(),
            'confidence': best_score
        }
    
    def extract_ocr_support(self, image_path: str) -> str:
        """
        Extract OCR text as supporting evidence only.
        
        Args:
            image_path: Path to the coin image
            
        Returns:
            Extracted text string
        """
        try:
            import pytesseract
            text = pytesseract.image_to_string(image_path, config='--psm 6')
            return text.strip()
        except Exception as e:
            return f"OCR Error: {str(e)}"
