"""
Test script to analyze coin images and show accuracy improvements.
This script tests the new CV-first approach with confidence scoring.
"""

import os
import sys
from image_analyzer import CoinAnalyzer

def test_accuracy():
    """Test the new CV-first approach on test_coins folder."""
    
    # Initialize analyzer
    analyzer = CoinAnalyzer()
    
    # Test folder
    test_folder = r"C:\Users\<username>\CascadeProjects\coin-analyzer\test_coins"
    
    # Get all image files
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
    image_files = [
        f for f in os.listdir(test_folder)
        if any(f.lower().endswith(ext) for ext in image_extensions)
    ]
    
    print(f"Testing {len(image_files)} images from {test_folder}")
    print("=" * 80)
    
    results = []
    
    for i, filename in enumerate(image_files, 1):
        image_path = os.path.join(test_folder, filename)
        print(f"\n[{i}/{len(image_files)}] Analyzing: {filename}")
        print("-" * 80)
        
        try:
            result = analyzer.analyze_coin(image_path)
            
            print(f"Country: {result['country']} (Confidence: {result['country_confidence']}%)")
            print(f"Denomination: {result['denomination']} (Confidence: {result['denomination_confidence']}%)")
            print(f"Year: {result['year']} (Confidence: {result['year_confidence']}%)")
            print(f"Orientation: {result['orientation']}")
            print(f"Grade: {result['grade_range']} (Confidence: {result['confidence_score']}%)")
            print(f"Status: {result.get('status', 'N/A')}")
            print(f"\nOCR Preview (first 100 chars):")
            print(f"  {result['ocr_text_preview']}")
            
            results.append(result)
            
        except Exception as e:
            print(f"ERROR: {str(e)}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    # Count confidence levels
    high_conf_country = sum(1 for r in results if r['country_confidence'] > 70)
    high_conf_denom = sum(1 for r in results if r['denomination_confidence'] > 70)
    high_conf_year = sum(1 for r in results if r['year_confidence'] > 70)
    
    print(f"Country detection: {high_conf_country}/{len(results)} with >70% confidence")
    print(f"Denomination detection: {high_conf_denom}/{len(results)} with >70% confidence")
    print(f"Year detection: {high_conf_year}/{len(results)} with >70% confidence")
    
    # Count unknown results
    unknown_country = sum(1 for r in results if r['country'] == 'unknown')
    unknown_denom = sum(1 for r in results if r['denomination'] == 'unknown')
    unknown_year = sum(1 for r in results if r['year'] == 'Unknown')
    
    print(f"\nUnknown results:")
    print(f"  Country: {unknown_country}/{len(results)}")
    print(f"  Denomination: {unknown_denom}/{len(results)}")
    print(f"  Year: {unknown_year}/{len(results)}")
    
    return results

if __name__ == "__main__":
    test_accuracy()
