"""Unit tests for Portfolio Dashboard."""

import unittest
import tempfile
import os
from portfolio_dashboard import PortfolioDashboard, DashboardSummary
from coin_collection import CoinItem


class TestPortfolioDashboard(unittest.TestCase):
    """Test Portfolio Dashboard functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create test items
        self.items = [
            CoinItem(
                id="1", image_path="", country="Canada", denomination="dime", year="1935",
                grade="VF-20", notes="", date_added="2026-06-15",
                estimate_cad=10.0
            ),
            CoinItem(
                id="2", image_path="", country="Canada", denomination="quarter", year="1940",
                grade="VF-30", notes="", date_added="2026-06-15",
                estimate_cad=15.0
            ),
            CoinItem(
                id="3", image_path="", country="Newfoundland", denomination="50 cent", year="1909",
                grade="F-12", notes="", date_added="2026-06-15",
                estimate_cad=25.0
            ),
            CoinItem(
                id="4", image_path="", country="Canada", denomination="1 cent", year="1859",
                grade="VG-8", notes="", date_added="2026-06-15",
                estimate_cad=50.0
            ),
            CoinItem(
                id="5", image_path="", country="Canada", denomination="dime", year="1935",
                grade="EF-40", notes="", date_added="2026-06-15",
                estimate_cad=20.0
            ),
        ]
        
        self.dashboard = PortfolioDashboard(self.items)
    
    def test_generate_dashboard(self):
        """Test dashboard generation."""
        summary = self.dashboard.generate_dashboard()
        
        self.assertIsInstance(summary, DashboardSummary)
        self.assertEqual(summary.total_items, 5)
        self.assertEqual(summary.total_countries, 2)
        self.assertGreater(summary.total_estimated_value_cad, 0)
    
    def test_total_estimated_value_calculation(self):
        """Test total estimated value calculation."""
        summary = self.dashboard.generate_dashboard()
        
        # Should sum all estimates: 10 + 15 + 25 + 50 + 20 = 120
        self.assertEqual(summary.total_estimated_value_cad, 120.0)
    
    def test_total_melt_value_calculation(self):
        """Test total melt value calculation."""
        summary = self.dashboard.generate_dashboard()
        
        # Should calculate melt value for silver coins
        self.assertGreaterEqual(summary.total_melt_value_cad, 0)
    
    def test_newfoundland_progress(self):
        """Test Newfoundland progress calculation."""
        summary = self.dashboard.generate_dashboard()
        
        self.assertEqual(summary.newfoundland_progress["total_items"], 1)
        self.assertEqual(summary.newfoundland_progress["denominations"], 1)
        self.assertIn("50 cent", summary.newfoundland_progress["series"])
    
    def test_canadian_silver_progress(self):
        """Test Canadian silver progress calculation."""
        summary = self.dashboard.generate_dashboard()
        
        # Should include dimes and quarters
        self.assertGreaterEqual(summary.canadian_silver_progress["total_items"], 2)
        self.assertIn("dime", summary.canadian_silver_progress["series"])
    
    def test_large_cent_1859_progress(self):
        """Test 1859 Large Cent progress calculation."""
        summary = self.dashboard.generate_dashboard()
        
        self.assertEqual(summary.large_cent_1859_progress["total_items"], 1)
        self.assertEqual(summary.large_cent_1859_progress["unique_grades"], 1)
        self.assertIn("VG-8", summary.large_cent_1859_progress["grades"])
    
    def test_top_gap_targets(self):
        """Test top gap targets generation."""
        summary = self.dashboard.generate_dashboard()
        
        self.assertIsInstance(summary.top_gap_targets, list)
        self.assertLessEqual(len(summary.top_gap_targets), 5)
    
    def test_top_upgrade_targets(self):
        """Test top upgrade targets generation."""
        summary = self.dashboard.generate_dashboard()
        
        self.assertIsInstance(summary.top_upgrade_targets, list)
        # Should have at least one duplicate (two 1935 dimes)
        self.assertGreater(len(summary.top_upgrade_targets), 0)
    
    def test_duplicate_heavy_areas(self):
        """Test duplicate-heavy areas detection."""
        summary = self.dashboard.generate_dashboard()
        
        self.assertIsInstance(summary.duplicate_heavy_areas, list)
        # Should detect the duplicate 1935 dimes
        self.assertGreater(len(summary.duplicate_heavy_areas), 0)
    
    def test_want_list_progress_empty(self):
        """Test WANT_LIST progress with no intents."""
        summary = self.dashboard.generate_dashboard()
        
        self.assertEqual(summary.want_list_progress["total_intents"], 0)
        self.assertEqual(summary.want_list_progress["fulfilled"], 0)
        self.assertEqual(summary.want_list_progress["pending"], 0)
        self.assertEqual(summary.want_list_progress["progress_percentage"], 0.0)
    
    def test_want_list_progress_with_intents(self):
        """Test WANT_LIST progress with staged intents."""
        # Create mock want list intents
        class MockIntent:
            def __init__(self, country, denomination, year):
                self.country = country
                self.denomination = denomination
                self.year = year
        
        intents = [
            MockIntent("Canada", "dime", "1935"),  # Already in collection
            MockIntent("Canada", "dime", "1936"),  # Not in collection
        ]
        
        dashboard = PortfolioDashboard(self.items, staged_want_list_intents=intents)
        summary = dashboard.generate_dashboard()
        
        self.assertEqual(summary.want_list_progress["total_intents"], 2)
        self.assertEqual(summary.want_list_progress["fulfilled"], 1)
        self.assertEqual(summary.want_list_progress["pending"], 1)
        self.assertEqual(summary.want_list_progress["progress_percentage"], 50.0)
    
    def test_export_to_csv(self):
        """Test CSV export."""
        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = os.path.join(temp_dir, "dashboard.csv")
            self.dashboard.export_to_csv(filepath)
            
            self.assertTrue(os.path.exists(filepath))
            
            # Check file has content
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn("Portfolio Dashboard Summary", content)
                self.assertIn("Total Items", content)
    
    def test_export_to_markdown(self):
        """Test Markdown export."""
        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = os.path.join(temp_dir, "dashboard.md")
            self.dashboard.export_to_markdown(filepath)
            
            self.assertTrue(os.path.exists(filepath))
            
            # Check file has content
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn("# Portfolio Dashboard Summary", content)
                self.assertIn("Collection Overview", content)
    
    def test_empty_collection(self):
        """Test dashboard with empty collection."""
        dashboard = PortfolioDashboard([])
        summary = dashboard.generate_dashboard()
        
        self.assertEqual(summary.total_items, 0)
        self.assertEqual(summary.total_countries, 0)
        self.assertEqual(summary.total_estimated_value_cad, 0.0)
        self.assertEqual(summary.total_melt_value_cad, 0.0)
    
    def test_collection_with_no_estimates(self):
        """Test dashboard with items that have no estimates."""
        items_no_value = [
            CoinItem(
                id="1", image_path="", country="Canada", denomination="dime", year="1935",
                grade="VF-20", notes="", date_added="2026-06-15"
            ),
        ]
        
        dashboard = PortfolioDashboard(items_no_value)
        summary = dashboard.generate_dashboard()
        
        self.assertEqual(summary.total_estimated_value_cad, 0.0)


if __name__ == '__main__':
    unittest.main()
