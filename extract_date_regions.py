"""
Extract date regions from coin images for CNN training.
Saves sample crops to debug folder for visual inspection.
"""

import cv2
import numpy as np
import os
from typing import Dict, List, Optional

class DateRegionExtractor:
    """Extract date regions from coin images."""
    
    def __init__(self):
        self.crop_zones = [
            'bottom_25',
            'bottom_center', 
            'lower_left',
            'lower_right',
            'full_coin'
        ]
    
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
    
    def extract_date_regions(self, image_path: str, output_folder: str) -> List[str]:
        """Extract date regions from a single image."""
        # Detect coin
        coin_info = self.detect_coin_circle(image_path)
        if coin_info is None:
            print(f"Failed to detect coin in {image_path}")
            return []
        
        # Load image
        img = cv2.imread(image_path)
        if img is None:
            print(f"Failed to load {image_path}")
            return []
        
        # Extract regions
        extracted_files = []
        filename = os.path.basename(image_path)
        name_without_ext = os.path.splitext(filename)[0]
        
        for zone in self.crop_zones:
            cropped = self.crop_zone(img, coin_info, zone)
            
            # Save cropped region
            output_filename = f"{name_without_ext}_{zone}.jpg"
            output_path = os.path.join(output_folder, output_filename)
            cv2.imwrite(output_path, cropped)
            extracted_files.append(output_path)
        
        return extracted_files
    
    def process_folder(self, input_folder: str, output_folder: str, max_images: int = 100):
        """Process all images in a folder and extract date regions."""
        os.makedirs(output_folder, exist_ok=True)
        
        # Get all image files
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        image_files = [
            f for f in os.listdir(input_folder)
            if any(f.lower().endswith(ext) for ext in image_extensions)
        ]
        
        # Limit to max_images
        image_files = image_files[:max_images]
        
        print(f"Processing {len(image_files)} images from {input_folder}")
        print(f"Output folder: {output_folder}")
        
        total_extracted = 0
        for i, filename in enumerate(image_files, 1):
            image_path = os.path.join(input_folder, filename)
            print(f"[{i}/{len(image_files)}] Processing {filename}...")
            
            extracted = self.extract_date_regions(image_path, output_folder)
            total_extracted += len(extracted)
        
        print(f"\nTotal date regions extracted: {total_extracted}")
        print(f"Output saved to: {output_folder}")


def main():
    """Extract date regions from test images."""
    extractor = DateRegionExtractor()
    
    # Input folder
    input_folder = r"C:\Users\<username>\CascadeProjects\coin-analyzer\test_coins"
    
    # Output folder for debug crops
    output_folder = r"C:\Users\<username>\CascadeProjects\coin-analyzer\debug_outputs\date_regions_sample"
    
    # Process all images (will be limited to 10 since that's all we have)
    extractor.process_folder(input_folder, output_folder, max_images=100)
    
    print("\nDate region extraction complete.")
    print("Please visually inspect the extracted regions in the debug folder to verify:")
    print("1. The date is visible in the crops")
    print("2. The crop zones are targeting the correct areas")
    print("3. The image quality is sufficient for CNN training")


if __name__ == "__main__":
    main()
