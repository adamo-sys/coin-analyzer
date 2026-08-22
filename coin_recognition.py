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


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEBUG_OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "debug_outputs")


class CoinRecognizer:
    """Identifies Canadian coins using computer vision techniques."""
    
    def __init__(self):
        """Initialize the coin recognizer."""
        # Configure Tesseract path for Windows
        self.configure_tesseract()
        
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
            
            # Identify obverse vs reverse
            orientation = self.identify_orientation(coin_segment)
            
            # Detect year with confidence and OCR variants using cropped date region
            year_result = self.detect_year(coin_segment, orientation, image_path, coin_info)

            # Denomination suggestions require explicit textual evidence. A coin's
            # apparent diameter in a single unscaled photo is not a physical size.
            recognition_text = year_result.get(
                'recognized_text',
                year_result['all_ocr_text'],
            )
            denomination_result = self.identify_denomination(
                coin_segment,
                coin_info,
                ocr_text=recognition_text,
            )
            
            # Detect country with confidence (no default to Canada)
            country_result = self.detect_country(image_path, recognition_text)
            
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
        height, width = gray.shape[:2]
        longest_side = max(height, width)
        detection_scale = min(1.0, 1000.0 / longest_side)
        detection_gray = gray
        if detection_scale < 1.0:
            detection_gray = cv2.resize(
                gray,
                (max(1, int(width * detection_scale)), max(1, int(height * detection_scale))),
                interpolation=cv2.INTER_AREA,
            )

        # Run Hough detection at a bounded resolution, but express allowed coin
        # radii relative to the image instead of using a phone-photo-hostile
        # fixed 300-pixel ceiling.
        blurred = cv2.GaussianBlur(detection_gray, (9, 9), 2)
        minimum_dimension = min(detection_gray.shape[:2])
        
        # Detect circles using Hough Circle Transform
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=max(50, int(minimum_dimension * 0.25)),
            param1=50,
            param2=30,
            minRadius=max(30, int(minimum_dimension * 0.10)),
            maxRadius=max(50, int(minimum_dimension * 0.49)),
        )
        
        if circles is None:
            return {'success': False}
        
        circles = np.round(circles[0, :]).astype("int")

        if len(circles) > 0:
            detection_height, detection_width = detection_gray.shape[:2]

            def circle_rank(circle: np.ndarray) -> tuple:
                """Prefer large circles that are substantially inside the photo."""

                candidate_x, candidate_y, candidate_radius = circle
                diameter = max(1, candidate_radius * 2)
                visible_width = max(
                    0,
                    min(detection_width, candidate_x + candidate_radius)
                    - max(0, candidate_x - candidate_radius),
                )
                visible_height = max(
                    0,
                    min(detection_height, candidate_y + candidate_radius)
                    - max(0, candidate_y - candidate_radius),
                )
                visible_fraction = min(
                    visible_width / diameter,
                    visible_height / diameter,
                )
                center_distance = np.hypot(
                    (candidate_x - detection_width / 2) / detection_width,
                    (candidate_y - detection_height / 2) / detection_height,
                )
                return (
                    visible_fraction >= 0.85,
                    candidate_radius * visible_fraction,
                    -center_distance,
                    candidate_radius,
                )

            x, y, radius = max(circles, key=circle_rank)
            if detection_scale < 1.0:
                x = int(round(x / detection_scale))
                y = int(round(y / detection_scale))
                radius = int(round(radius / detection_scale))
            
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
    
    def identify_denomination(
        self,
        coin_segment: np.ndarray,
        coin_info: Dict,
        ocr_text: str = "",
    ) -> Dict:
        """
        Identify denomination only from explicit OCR text.
        
        Args:
            coin_segment: Segmented coin image
            coin_info: Coin detection information
            ocr_text: Bounded OCR evidence collected from the same image
            
        Returns:
            Dictionary with denomination and confidence score
        """
        normalized = re.sub(r"[^a-z0-9]+", " ", str(ocr_text).casefold()).strip()
        patterns = (
            # Raised rim/detail can make Tesseract append a false trailing S to
            # ONE; require the following CENT token before accepting it.
            (r"\bones?\s+cent\b|\b1\s+cent\b", "penny"),
            (r"\bfive\s+cents?\b|\b5\s+cents?\b", "nickel"),
            (r"\bten\s+cents?\b|\b10\s+cents?\b", "dime"),
            (r"\btwenty\s*five\s+cents?\b|\b25\s+cents?\b", "quarter"),
            (r"\bfifty\s+cents?\b|\b50\s+cents?\b", "50_cent"),
            (r"\bone\s+dollar\b|\b1\s+dollar\b", "dollar"),
        )
        candidates = [
            {
                "denomination": denomination,
                # Binary exact-phrase evidence, not a calibrated probability.
                "confidence": 1.0,
                "source": "ocr_text",
            }
            for pattern, denomination in patterns
            if re.search(pattern, normalized)
        ]
        if not candidates:
            return {
                "denomination": "unknown",
                "confidence": 0.0,
                "candidates": [],
                "source": "unavailable",
            }
        if len(candidates) > 1:
            return {
                "denomination": "unknown",
                "confidence": 0.0,
                "candidates": candidates,
                "source": "conflicting_ocr_text",
            }
        return {**candidates[0], "candidates": candidates}
    
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
        # Keep the OCR workload bounded. Whole-face and targeted date crops are
        # more useful than running Tesseract once per individual letter contour.
        text_config = "--psm 6 --oem 3"
        sparse_text_config = "--psm 11 --oem 3"
        digits_config = "--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789"
        ocr_jobs = []
        if coin_segment is not None and coin_segment.size:
            upscaled_coin = self.resize_for_ocr(coin_segment)
            _, thresholded_coin = cv2.threshold(
                upscaled_coin,
                0,
                255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU,
            )
            high_contrast_coin = cv2.createCLAHE(
                clipLimit=3.0,
                tileGridSize=(8, 8),
            ).apply(upscaled_coin)
            ocr_jobs.extend((
                ("coin_upscaled", upscaled_coin, text_config),
                ("coin_thresholded", thresholded_coin, sparse_text_config),
                ("coin_high_contrast", high_contrast_coin, text_config),
            ))
        date_crop = self.crop_date_region(image_path, coin_info)
        if date_crop is not None and date_crop.size:
            ocr_jobs.extend(
                (f"date_{name}", variant, digits_config)
                for name, variant in self.generate_date_crop_variants(date_crop).items()
                if name in {"upscaled", "high_contrast"}
            )
        ocr_jobs.extend(self.build_embossed_text_jobs(image_path, coin_info))

        year_candidates = []
        all_ocr_text = []
        recognized_text = []
        try:
            import pytesseract
        except Exception as error:
            return {
                "year": None,
                "confidence": 0.0,
                "candidates": [],
                "all_ocr_text": f"OCR unavailable: {error.__class__.__name__}",
                "recognized_text": "",
            }

        for source_name, region, config in ocr_jobs:
            try:
                text = pytesseract.image_to_string(region, config=config, timeout=2)
            except Exception as error:
                all_ocr_text.append(f"{source_name}: OCR Error - {error.__class__.__name__}")
                continue
            all_ocr_text.append(f"{source_name} ({config}): {text[:100]}")
            if text.strip():
                recognized_text.append(text.strip())
            for match in self.extract_years_from_text(text):
                year_candidates.append({
                    "year": match,
                    "confidence": self.calculate_year_confidence(source_name, text, match),
                    "source": f"{source_name} ({config})",
                })

        year_candidates.sort(key=lambda item: (-item['confidence'], item['year'], item['source']))

        # Select only an unambiguous plurality. Conflicting OCR variants must
        # not become an arbitrary year suggestion because of iteration order.
        best_year = None
        year_confidence = 0.0
        counts = {}
        for candidate in year_candidates:
            counts[candidate['year']] = counts.get(candidate['year'], 0) + 1
        if counts:
            ordered_counts = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            top_year, top_count = ordered_counts[0]
            tied = len(ordered_counts) > 1 and ordered_counts[1][1] == top_count
            if not tied:
                best_year = top_year
                best_source_score = max(
                    item['confidence']
                    for item in year_candidates
                    if item['year'] == top_year
                )
                year_confidence = min(best_source_score + (0.1 if top_count > 1 else 0.0), 1.0)
        
        return {
            'year': best_year,
            'confidence': year_confidence,
            'candidates': year_candidates,
            'all_ocr_text': '\n'.join(all_ocr_text),
            'recognized_text': '\n'.join(recognized_text),
        }

    def build_embossed_text_jobs(self, image_path: str, coin_info: Dict) -> List[tuple]:
        """Build three bounded OCR jobs for upright, embossed coin text."""

        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if image is None or not image.size:
            return []

        center_x, center_y = coin_info.get("center", (0, 0))
        radius = int(coin_info.get("radius", 0))
        if radius <= 0:
            return []
        image_height, image_width = image.shape[:2]
        image = image[
            max(0, center_y - radius):min(image_height, center_y + radius),
            max(0, center_x - radius):min(image_width, center_x + radius),
        ]
        if not image.size:
            return []
        height, width = image.shape[:2]
        region_specs = (
            (
                "embossed_denomination_upper",
                (0.075, 0.325, 0.20, 0.95),
                "--psm 13 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            ),
            (
                "embossed_denomination_lower",
                (0.28, 0.565, 0.16, 0.98),
                "--psm 13 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            ),
            (
                "embossed_date",
                (0.55, 0.75, 0.29, 0.90),
                "--psm 13 --oem 3 -c tessedit_char_whitelist=0123456789",
            ),
        )

        jobs = []
        for source_name, (top, bottom, left, right), config in region_specs:
            region = image[
                int(height * top):int(height * bottom),
                int(width * left):int(width * right),
            ]
            if not region.size:
                continue
            longest_side = max(region.shape[:2])
            scale = min(2.0, 1800.0 / longest_side)
            if scale != 1.0:
                interpolation = cv2.INTER_CUBIC if scale > 1.0 else cv2.INTER_AREA
                region = cv2.resize(
                    region,
                    (
                        max(1, int(region.shape[1] * scale)),
                        max(1, int(region.shape[0] * scale)),
                    ),
                    interpolation=interpolation,
                )
            enhanced = cv2.createCLAHE(
                clipLimit=3.0,
                tileGridSize=(8, 8),
            ).apply(region)
            embossed_gradient = cv2.morphologyEx(
                enhanced,
                cv2.MORPH_GRADIENT,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)),
            )
            jobs.append((source_name, embossed_gradient, config))
        return jobs

    @staticmethod
    def extract_years_from_text(text: str) -> List[str]:
        """Return plausible four-digit years without repairing ambiguous glyphs."""

        current_year = datetime.now().year
        # Tesseract sometimes inserts spaces between otherwise clear digits.
        digit_joined = re.sub(r"(?<=\d)\s+(?=\d)", "", str(text))
        matches = re.findall(r"(?<!\d)(18[5-9][0-9]|19[0-9]{2}|20[0-9]{2})(?!\d)", digit_joined)
        return [year for year in matches if 1850 <= int(year) <= current_year]

    @staticmethod
    def resize_for_ocr(image: np.ndarray, maximum_dimension: int = 1000) -> np.ndarray:
        """Bound OCR input size while preserving smaller source detail."""

        height, width = image.shape[:2]
        longest_side = max(height, width)
        if longest_side <= maximum_dimension:
            return image.copy()
        scale = maximum_dimension / longest_side
        return cv2.resize(
            image,
            (max(1, int(width * scale)), max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    
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

            filename = os.path.basename(image_path)
            debug_path = os.path.join(DEBUG_OUTPUT_ROOT, "date_crops", f"crop_{filename}")
            os.makedirs(os.path.dirname(debug_path), exist_ok=True)
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
            'canada': ['canada', 'canadian'],
            'united states': ['usa', 'united states', 'america', 'united states of america'],
            'united kingdom': ['united kingdom', 'great britain', 'britain', 'england'],
            'australia': ['australia', 'australian'],
            'france': ['france', 'french'],
            'germany': ['germany', 'german', 'deutschland'],
            'japan': ['japan', 'japanese'],
            'china': ['china', 'chinese'],
            'mexico': ['mexico', 'mexican'],
            'spain': ['spain', 'spanish']
        }
        
        text_lower = ocr_text.lower()
        
        # Score each country based on matches
        country_scores = {}
        for country, patterns in country_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(rf"\b{re.escape(pattern)}\b", text_lower):
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
