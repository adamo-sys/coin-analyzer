"""
Coin Grading Module
This module analyzes coin images to estimate grade using Canadian/Sheldon-style grading.
Provides conservative grade ranges with confidence scores and detailed notes.
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple


class CoinGrader:
    """Analyzes coin images to estimate grade and condition."""
    
    def __init__(self):
        """Initialize the coin grader."""
        # Canadian/Sheldon grade definitions
        self.grade_ranges = {
            'Poor (P-1)': (1, 1),
            'Fair (FR-2)': (2, 2),
            'Good (G-4)': (4, 6),
            'Very Good (VG-8)': (8, 10),
            'Fine (F-12)': (12, 15),
            'Very Fine (VF-20)': (20, 35),
            'Extremely Fine (EF-40)': (40, 45),
            'About Uncirculated (AU-50)': (50, 58),
            'Uncirculated (MS-60)': (60, 70)
        }
        
        # Grade descriptions
        self.grade_descriptions = {
            'Poor (P-1)': 'Barely identifiable, heavily worn',
            'Fair (FR-2)': 'Outline visible but details worn smooth',
            'Good (G-4)': 'Major details visible but worn',
            'Very Good (VG-8)': 'Some details visible, moderate wear',
            'Fine (F-12)': 'Moderate to considerable wear, details clear',
            'Very Fine (VF-20)': 'Light to moderate wear, sharp details',
            'Extremely Fine (EF-40)': 'Slight wear, nearly full detail',
            'About Uncirculated (AU-50)': 'Trace wear, nearly full luster',
            'Uncirculated (MS-60)': 'No wear, full luster, may have marks'
        }
    
    def analyze_image_quality(self, image_path: str) -> Dict[str, float]:
        """
        Analyze overall image quality metrics.
        
        Args:
            image_path: Path to the coin image
            
        Returns:
            Dictionary with quality metrics
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return {'sharpness': 0, 'contrast': 0, 'brightness': 0}
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Calculate sharpness using Laplacian variance
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            sharpness = np.var(laplacian)
            
            # Calculate contrast (standard deviation)
            contrast = np.std(gray)
            
            # Calculate brightness (mean)
            brightness = np.mean(gray)
            
            return {
                'sharpness': sharpness,
                'contrast': contrast,
                'brightness': brightness
            }
        except Exception as e:
            print(f"Error analyzing image quality: {e}")
            return {'sharpness': 0, 'contrast': 0, 'brightness': 0}
    
    def detect_surface_issues(self, image_path: str) -> Dict[str, any]:
        """
        Detect surface issues like scratches, corrosion, cleaning marks, and damage.
        
        Args:
            image_path: Path to the coin image
            
        Returns:
            Dictionary with detected issues and severity
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return {'scratches': 0, 'corrosion': 0, 'cleaning_marks': 0, 'damage': 0}
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Detect scratches using edge detection
            edges = cv2.Canny(gray, 50, 150)
            scratch_density = np.sum(edges) / (edges.shape[0] * edges.shape[1])
            
            # Detect corrosion (dark spots, discoloration)
            _, binary = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
            corrosion_area = np.sum(binary) / (binary.shape[0] * binary.shape[1])
            
            # Detect cleaning marks (unnatural patterns, uniform brightness)
            uniform_regions = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            cleaning_score = np.std(gray) / 255.0  # Lower std may indicate cleaning
            
            # Detect damage (dents, bends, edge damage) using contour analysis
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            damage_score = 0
            if contours:
                # Look for irregular contours that might indicate damage
                contour_areas = [cv2.contourArea(c) for c in contours]
                if contour_areas:
                    area_variance = np.var(contour_areas)
                    damage_score = min(area_variance / 10000, 1.0)
            
            return {
                'scratches': min(scratch_density / 100, 1.0),
                'corrosion': min(corrosion_area / 1000, 1.0),
                'cleaning_marks': min(1.0 - cleaning_score, 1.0),
                'damage': damage_score
            }
        except Exception as e:
            print(f"Error detecting surface issues: {e}")
            return {'scratches': 0, 'corrosion': 0, 'cleaning_marks': 0, 'damage': 0}
    
    def assess_luster(self, image_path: str) -> Dict[str, float]:
        """
        Assess coin luster and mint luster presence.
        
        Args:
            image_path: Path to the coin image
            
        Returns:
            Dictionary with luster metrics
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return {'luster_score': 0, 'surface_quality': 0}
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Calculate local contrast variations (indicates luster)
            kernel = np.ones((5, 5), np.float32) / 25
            local_mean = cv2.filter2D(gray, -1, kernel)
            local_contrast = np.abs(gray - local_mean)
            luster_score = np.mean(local_contrast) / 255.0
            
            # Surface smoothness (inverse of noise)
            noise = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            surface_quality = 1.0 - (np.abs(gray.astype(float) - noise.astype(float)).mean() / 255.0)
            
            return {
                'luster_score': luster_score,
                'surface_quality': surface_quality
            }
        except Exception as e:
            print(f"Error assessing luster: {e}")
            return {'luster_score': 0, 'surface_quality': 0}
    
    def estimate_wear_level(self, image_path: str, quality: Dict, surface: Dict, luster: Dict) -> float:
        """
        Estimate overall wear level from 0 (no wear) to 1 (heavily worn).
        
        Args:
            image_path: Path to the coin image
            quality: Image quality metrics
            surface: Surface issue metrics
            luster: Luster metrics
            
        Returns:
            Wear level between 0 and 1
        """
        # Base wear estimate from luster (less luster = more wear)
        wear_from_luster = 1.0 - luster['luster_score']
        
        # Adjust for surface quality
        wear_from_surface = 1.0 - luster['surface_quality']
        
        # Adjust for scratches (indicates wear/handling)
        wear_from_scratches = surface['scratches'] * 0.6
        
        # Adjust for corrosion (indicates age/wear)
        wear_from_corrosion = surface['corrosion'] * 0.4
        
        # Adjust for damage (significantly affects grade)
        wear_from_damage = surface['damage'] * 0.5
        
        # Adjust for image quality (poor images may underestimate wear)
        quality_factor = min(quality['sharpness'] / 500, 1.0)
        
        # Combine factors with weights (more conservative weighting)
        total_wear = (
            wear_from_luster * 0.35 +
            wear_from_surface * 0.25 +
            wear_from_scratches * 0.2 +
            wear_from_corrosion * 0.1 +
            wear_from_damage * 0.1
        )
        
        # Adjust for image quality confidence
        total_wear = total_wear * (0.5 + 0.5 * quality_factor)
        
        return min(max(total_wear, 0), 1)
    
    def calculate_confidence_score(self, quality: Dict, surface: Dict, luster: Dict) -> float:
        """
        Calculate confidence score for the grade estimate.
        
        Args:
            quality: Image quality metrics
            surface: Surface issue metrics
            luster: Luster metrics
            
        Returns:
            Confidence score between 0 and 1
        """
        # High sharpness increases confidence
        sharpness_confidence = min(quality['sharpness'] / 1000, 1.0)
        
        # Good contrast increases confidence
        contrast_confidence = min(quality['contrast'] / 100, 1.0)
        
        # High surface issues decrease confidence (more conservative with damage)
        surface_confidence = 1.0 - (surface['scratches'] * 0.25 + surface['corrosion'] * 0.25 + surface['cleaning_marks'] * 0.25 + surface['damage'] * 0.25)
        
        # Good luster assessment increases confidence
        luster_confidence = luster['luster_score']
        
        # Combine factors
        confidence = (
            sharpness_confidence * 0.3 +
            contrast_confidence * 0.2 +
            surface_confidence * 0.3 +
            luster_confidence * 0.2
        )
        
        return min(max(confidence, 0.1), 0.95)  # Never 100% confident, minimum 10%
    
    def generate_notes(self, wear_level: float, surface: Dict, luster: Dict, quality: Dict) -> List[str]:
        """
        Generate detailed notes about the coin's condition.
        
        Args:
            wear_level: Estimated wear level (0-1)
            surface: Surface issue metrics
            luster: Luster metrics
            quality: Image quality metrics
            
        Returns:
            List of notes describing condition
        """
        notes = []
        
        # Wear notes
        if wear_level < 0.1:
            notes.append("Appears uncirculated with no visible wear")
        elif wear_level < 0.3:
            notes.append("Light wear visible, likely handled sparingly")
        elif wear_level < 0.5:
            notes.append("Moderate wear consistent with circulation")
        elif wear_level < 0.7:
            notes.append("Considerable wear, details partially worn")
        else:
            notes.append("Heavy wear, major details worn smooth")
        
        # Scratch notes
        if surface['scratches'] > 0.7:
            notes.append("Numerous scratches visible, significantly affects appearance")
        elif surface['scratches'] > 0.4:
            notes.append("Moderate scratching present")
        elif surface['scratches'] > 0.2:
            notes.append("Minor scratches visible under close inspection")
        
        # Corrosion notes
        if surface['corrosion'] > 0.5:
            notes.append("Significant corrosion or environmental damage present")
        elif surface['corrosion'] > 0.2:
            notes.append("Some corrosion or toning visible")
        
        # Cleaning notes
        if surface['cleaning_marks'] > 0.6:
            notes.append("Possible cleaning marks detected - may have been cleaned")
        elif surface['cleaning_marks'] > 0.3:
            notes.append("Surface may have been lightly cleaned")
        
        # Damage notes
        if surface['damage'] > 0.6:
            notes.append("Significant damage detected - dents, bends, or edge damage present")
        elif surface['damage'] > 0.3:
            notes.append("Some damage visible - may affect grade")
        
        # Luster notes
        if luster['luster_score'] > 0.6:
            notes.append("Good luster present, original mint shine visible")
        elif luster['luster_score'] > 0.3:
            notes.append("Some luster remains")
        else:
            notes.append("Little to no luster visible")
        
        # Image quality notes
        if quality['sharpness'] < 100:
            notes.append("Photo quality limitations may affect accuracy")
        elif quality['contrast'] < 30:
            notes.append("Low contrast image may obscure details")
        
        return notes if notes else ["Condition assessment based on image analysis"]
    
    def estimate_grade(self, image_path: str) -> Dict[str, any]:
        """
        Estimate coin grade with confidence and notes.
        
        Args:
            image_path: Path to the coin image
            
        Returns:
            Dictionary with grade information
        """
        # Analyze image
        quality = self.analyze_image_quality(image_path)
        surface = self.detect_surface_issues(image_path)
        luster = self.assess_luster(image_path)
        
        # Estimate wear level
        wear_level = self.estimate_wear_level(image_path, quality, surface, luster)
        
        # Calculate confidence
        confidence = self.calculate_confidence_score(quality, surface, luster)
        
        # Determine grade range based on wear level (conservative grading with simplified notation)
        if wear_level < 0.05:
            grade_range = "MS"
            grade_low, grade_high = 60, 70
        elif wear_level < 0.15:
            grade_range = "AU"
            grade_low, grade_high = 50, 58
        elif wear_level < 0.30:
            grade_range = "EF"
            grade_low, grade_high = 40, 45
        elif wear_level < 0.45:
            grade_range = "VF"
            grade_low, grade_high = 20, 35
        elif wear_level < 0.60:
            grade_range = "F"
            grade_low, grade_high = 12, 15
        elif wear_level < 0.75:
            grade_range = "VG"
            grade_low, grade_high = 8, 10
        elif wear_level < 0.85:
            grade_range = "G"
            grade_low, grade_high = 4, 6
        elif wear_level < 0.95:
            grade_range = "FR"
            grade_low, grade_high = 2, 2
        else:
            grade_range = "P"
            grade_low, grade_high = 1, 1
        
        # Generate notes
        notes = self.generate_notes(wear_level, surface, luster, quality)
        
        return {
            'grade_range': grade_range,
            'grade_low': grade_low,
            'grade_high': grade_high,
            'confidence_score': round(confidence * 100, 1),
            'notes': '; '.join(notes),
            'wear_level': round(wear_level * 100, 1),
            'has_scratches': surface['scratches'] > 0.2,
            'has_corrosion': surface['corrosion'] > 0.1,
            'has_cleaning_marks': surface['cleaning_marks'] > 0.3,
            'has_damage': surface['damage'] > 0.2,
            'luster_present': luster['luster_score'] > 0.3,
            'image_quality_limitations': quality['sharpness'] < 100
        }
