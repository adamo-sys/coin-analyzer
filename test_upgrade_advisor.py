"""
Unit tests for Upgrade Advisor.
"""

import unittest
import os
import tempfile
from dataclasses import dataclass
from upgrade_advisor import UpgradeAdvisor, UpgradeRecommendation
from coin_collection import CoinItem


@dataclass
class MockCoinItem:
    """Mock coin item for testing."""
    id: str
    country: str
    denomination: str
    year: str
    grade: str
    estimate_cad: float = 0.0


class TestUpgradeAdvisor(unittest.TestCase):
    """Test Upgrade Advisor functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock collection items
        self.collection_items = [
            MockCoinItem("1", "Canada", "1 cent", "1967", "VF-20", 5.0),
            MockCoinItem("2", "Canada", "1 cent", "1967", "VF-30", 10.0),
            MockCoinItem("3", "Newfoundland", "50 cents", "1909", "F-12", 50.0),
            MockCoinItem("4", "Canada", "dollar", "1935", "VF-20", 100.0),
            MockCoinItem("5", "Canada", "1 cent", "1859", "VG-8", 200.0),
        ]
        
        self.advisor = UpgradeAdvisor(self.collection_items)
    
    def test_better_grade_upgrade(self):
        """Test that a better grade candidate is identified as an upgrade."""
        recommendation = self.advisor.analyze_upgrade(
            "Canada", "1 cent", "1967", "EF-40", 20.0
        )
        
        # EF-40 (score 9) vs VF-30 (score 8) = +1 grade improvement = 10 points
        # Below threshold for Upgrade (40), so Hold Existing
        self.assertEqual(recommendation.verdict, "Hold Existing")
        self.assertEqual(recommendation.grade_improvement, 1)
    
    def test_same_grade_duplicate(self):
        """Test that same-grade candidate is not an upgrade."""
        recommendation = self.advisor.analyze_upgrade(
            "Canada", "1 cent", "1967", "VF-30", 10.0
        )
        
        self.assertEqual(recommendation.verdict, "Hold Existing")
        self.assertEqual(recommendation.grade_improvement, 0)
    
    def test_lower_grade_candidate(self):
        """Test that lower-grade candidate is not an upgrade."""
        recommendation = self.advisor.analyze_upgrade(
            "Canada", "1 cent", "1967", "VG-8", 3.0
        )
        
        self.assertEqual(recommendation.verdict, "Hold Existing")
        self.assertLess(recommendation.grade_improvement, 0)
    
    def test_newfoundland_upgrade(self):
        """Test Newfoundland upgrade gets priority boost."""
        recommendation = self.advisor.analyze_upgrade(
            "Newfoundland", "50 cents", "1909", "VF-20", 75.0
        )
        
        # F-12 (score 6) to VF-20 (score 7) = +1 grade improvement = 10 points
        # Newfoundland boost = 30 points
        # Total = 40 points, which is exactly the threshold for "Upgrade"
        self.assertEqual(recommendation.verdict, "Upgrade")
        self.assertGreater(recommendation.upgrade_score, 30)
    
    def test_canadian_silver_upgrade(self):
        """Test Canadian silver upgrade gets priority boost."""
        recommendation = self.advisor.analyze_upgrade(
            "Canada", "dollar", "1935", "EF-40", 150.0
        )
        
        # VF-20 (score 7) to EF-40 (score 9) = +2 grade improvement = 20 points
        # Canadian silver boost = 25 points
        # Total = 45 points, which is above threshold for "Upgrade" but below "Strong Upgrade"
        self.assertEqual(recommendation.verdict, "Upgrade")
        self.assertGreater(recommendation.upgrade_score, 40)
    
    def test_1859_large_cent_upgrade(self):
        """Test 1859 Large Cent upgrade gets priority boost."""
        recommendation = self.advisor.analyze_upgrade(
            "Canada", "1 cent", "1859", "VF-20", 250.0
        )
        
        # VG-8 (score 5) to VF-20 (score 7) = +2 grade improvement = 20 points
        # 1859 Large Cent boost = 35 points
        # Total = 55 points, which is above threshold for "Upgrade" but below "Strong Upgrade"
        self.assertEqual(recommendation.verdict, "Upgrade")
        self.assertGreater(recommendation.upgrade_score, 40)
    
    def test_no_match_pass(self):
        """Test that candidate with no collection match returns Pass."""
        recommendation = self.advisor.analyze_upgrade(
            "USA", "1 cent", "1900", "VF-20", 5.0
        )
        
        self.assertEqual(recommendation.verdict, "Pass")
        self.assertEqual(recommendation.upgrade_score, 0)
    
    def test_read_only_behavior(self):
        """Test that Upgrade Advisor does not modify collection."""
        original_count = len(self.collection_items)
        
        self.advisor.analyze_upgrade(
            "Canada", "1 cent", "1967", "EF-40", 20.0
        )
        
        # Collection should not be modified
        self.assertEqual(len(self.collection_items), original_count)
    
    def test_csv_export(self):
        """Test CSV export functionality."""
        recommendations = [
            self.advisor.analyze_upgrade("Canada", "1 cent", "1967", "EF-40", 20.0),
            self.advisor.analyze_upgrade("Newfoundland", "50 cents", "1909", "VF-20", 75.0),
        ]
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name
        
        try:
            # Export to CSV
            result = self.advisor.export_to_csv(recommendations, temp_path)
            self.assertTrue(result)
            
            # Verify file exists
            self.assertTrue(os.path.exists(temp_path))
            
            # Verify file has content
            with open(temp_path, 'r') as f:
                content = f.read()
                self.assertIn("candidate_country", content)
                self.assertIn("verdict", content)
        
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def test_value_improvement_calculation(self):
        """Test value improvement calculation."""
        recommendation = self.advisor.analyze_upgrade(
            "Canada", "1 cent", "1967", "EF-40", 25.0
        )
        
        # Best existing is VF-30 with estimate 10.0
        # Candidate is EF-40 with estimate 25.0
        self.assertGreater(recommendation.value_improvement, 0)
    
    def test_explanation_generation(self):
        """Test that explanation is generated correctly."""
        recommendation = self.advisor.analyze_upgrade(
            "Canada", "1 cent", "1967", "EF-40", 20.0
        )
        
        self.assertIsNotNone(recommendation.explanation)
        self.assertIn("Upgrade Analysis", recommendation.explanation)
        self.assertIn("Candidate Coin", recommendation.explanation)
        self.assertIn("Existing Coin", recommendation.explanation)
    
    def test_ungraded_candidate(self):
        """Test candidate with no grade."""
        recommendation = self.advisor.analyze_upgrade(
            "Canada", "1 cent", "1967", "", 20.0
        )
        
        # Ungraded candidate (score 0) vs VF-30 (score 8) = -8 grade improvement
        # Should still work but with negative grade improvement
        self.assertIsNotNone(recommendation)
        self.assertEqual(recommendation.grade_improvement, -8)
        self.assertEqual(recommendation.verdict, "Hold Existing")
    
    def test_ungraded_existing(self):
        """Test when existing item has no grade."""
        collection = [MockCoinItem("1", "Canada", "1 cent", "1967", "", 5.0)]
        advisor = UpgradeAdvisor(collection)
        
        recommendation = advisor.analyze_upgrade(
            "Canada", "1 cent", "1967", "VF-20", 20.0
        )
        
        # Should still work
        self.assertIsNotNone(recommendation)
        self.assertEqual(recommendation.verdict, "Upgrade")


if __name__ == '__main__':
    unittest.main()
