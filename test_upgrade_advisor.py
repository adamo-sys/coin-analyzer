"""
Unit tests for Upgrade Advisor.
"""

import unittest
import os
import tempfile
from dataclasses import dataclass
from unittest.mock import patch
from upgrade_advisor import UpgradeAdvisor, UpgradeRecommendation
from coin_collection import CoinItem
from focused_collection_intelligence import FocusedCollectionIntelligenceEngine


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

    def test_uses_collection_intelligence_engine_for_upgrade_match(self):
        """Upgrade Advisor routes match/upgrade classification through Collection Intelligence."""
        with patch(
            "upgrade_advisor.FocusedCollectionIntelligenceEngine",
            wraps=FocusedCollectionIntelligenceEngine,
        ) as engine_class:
            recommendation = self.advisor.analyze_upgrade(
                "Canada", "1 cent", "1967", "EF-40", 20.0
            )

        self.assertTrue(engine_class.called)
        self.assertEqual(recommendation.existing_grade, "VF-30")
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
    
    def test_melt_value_integration_for_silver_coin(self):
        """Test that melt value is calculated for silver coins."""
        recommendation = self.advisor.analyze_upgrade(
            "Canada", "dollar", "1935", "EF-40", 150.0
        )
        
        # Melt value should be available for silver coins
        self.assertIsNotNone(recommendation.candidate_melt_value_cad)
        self.assertIsNotNone(recommendation.existing_melt_value_cad)
        self.assertIsNotNone(recommendation.melt_value_improvement)
        # Melt value should be mentioned in explanation
        self.assertIn("Melt Value Analysis", recommendation.explanation)
    
    def test_melt_value_not_available_for_non_silver_coin(self):
        """Test that melt value is not calculated for non-silver coins."""
        recommendation = self.advisor.analyze_upgrade(
            "Canada", "1 cent", "1967", "EF-40", 20.0
        )
        
        # Melt value should be 0 for non-silver coins
        self.assertEqual(recommendation.candidate_melt_value_cad, 0.0)
        self.assertEqual(recommendation.existing_melt_value_cad, 0.0)
        self.assertEqual(recommendation.melt_value_improvement, 0.0)
    
    def test_melt_value_does_not_change_verdict(self):
        """Test that melt value is a supporting factor, not a primary driver."""
        # This test ensures that melt value integration doesn't change existing verdict logic
        recommendation = self.advisor.analyze_upgrade(
            "Canada", "1 cent", "1967", "EF-40", 20.0
        )
        
        # Should still be Hold Existing regardless of melt value
        self.assertEqual(recommendation.verdict, "Hold Existing")
    
    def test_melt_value_fields_populated_correctly(self):
        """Test that all melt value fields are populated correctly."""
        recommendation = self.advisor.analyze_upgrade(
            "Canada", "dollar", "1935", "EF-40", 150.0
        )
        
        # Check that all melt value fields are present
        self.assertTrue(hasattr(recommendation, 'candidate_melt_value_cad'))
        self.assertTrue(hasattr(recommendation, 'existing_melt_value_cad'))
        self.assertTrue(hasattr(recommendation, 'melt_value_improvement'))
        self.assertTrue(hasattr(recommendation, 'spot_price_warning'))
        
        # For silver coins with manual provider, no warning should be present
        self.assertIsNone(recommendation.spot_price_warning)
    
    def test_melt_value_improvement_calculation(self):
        """Test that melt value improvement is calculated correctly."""
        recommendation = self.advisor.analyze_upgrade(
            "Canada", "dollar", "1935", "EF-40", 150.0
        )
        
        # Both coins have same ASW, so melt value improvement should be 0
        self.assertEqual(recommendation.melt_value_improvement, 0.0)


if __name__ == '__main__':
    unittest.main()
