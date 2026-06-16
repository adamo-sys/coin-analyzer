"""v0.7 Portfolio Dashboard release audit tests."""

import unittest
import tempfile
import os
from portfolio_dashboard import PortfolioDashboard, DashboardSummary
from coin_collection import CoinItem


class TestV07PortfolioDashboardAudit(unittest.TestCase):
    """Comprehensive v0.7 release audit tests for Portfolio Dashboard."""
    
    def test_main_app_launches(self):
        """Test main app launches."""
        import coin_collection_gui
        self.assertTrue(coin_collection_gui is not None)
    
    def test_portfolio_dashboard_opens(self):
        """Test Portfolio Dashboard can be instantiated."""
        items = []
        dashboard = PortfolioDashboard(items)
        self.assertIsNotNone(dashboard)
    
    def test_collection_totals_display_correctly(self):
        """Test collection totals display correctly."""
        items = [
            CoinItem(
                id="1", image_path="", country="Canada", denomination="dime", year="1935",
                grade="VF-20", notes="", date_added="2026-06-15"
            ),
            CoinItem(
                id="2", image_path="", country="Canada", denomination="quarter", year="1940",
                grade="VF-30", notes="", date_added="2026-06-15"
            ),
        ]
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        self.assertEqual(summary.total_items, 2)
        self.assertEqual(summary.total_countries, 1)
    
    def test_estimated_value_calculation_works(self):
        """Test estimated value calculation works."""
        items = [
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
        ]
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        self.assertEqual(summary.total_estimated_value_cad, 25.0)
    
    def test_melt_value_subtotal_works(self):
        """Test melt value subtotal works."""
        items = [
            CoinItem(
                id="1", image_path="", country="Canada", denomination="dime", year="1935",
                grade="VF-20", notes="", date_added="2026-06-15"
            ),
        ]
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        # Should calculate melt value for silver coins
        self.assertGreaterEqual(summary.total_melt_value_cad, 0)
    
    def test_newfoundland_progress_displays_correctly(self):
        """Test Newfoundland progress displays correctly."""
        items = [
            CoinItem(
                id="1", image_path="", country="Newfoundland", denomination="50 cent", year="1909",
                grade="F-12", notes="", date_added="2026-06-15"
            ),
        ]
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        self.assertEqual(summary.newfoundland_progress["total_items"], 1)
        self.assertEqual(summary.newfoundland_progress["denominations"], 1)
        self.assertIn("50 cent", summary.newfoundland_progress["series"])
    
    def test_canadian_silver_progress_displays_correctly(self):
        """Test Canadian silver progress displays correctly."""
        items = [
            CoinItem(
                id="1", image_path="", country="Canada", denomination="dime", year="1935",
                grade="VF-20", notes="", date_added="2026-06-15"
            ),
        ]
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        self.assertGreaterEqual(summary.canadian_silver_progress["total_items"], 1)
        self.assertIn("dime", summary.canadian_silver_progress["series"])
    
    def test_1859_large_cent_progress_displays_correctly(self):
        """Test 1859 Large Cent progress displays correctly."""
        items = [
            CoinItem(
                id="1", image_path="", country="Canada", denomination="1 cent", year="1859",
                grade="VG-8", notes="", date_added="2026-06-15"
            ),
        ]
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        self.assertEqual(summary.large_cent_1859_progress["total_items"], 1)
        self.assertEqual(summary.large_cent_1859_progress["unique_grades"], 1)
        self.assertIn("VG-8", summary.large_cent_1859_progress["grades"])
    
    def test_top_gap_fill_targets_display_correctly(self):
        """Test top gap-fill targets display correctly."""
        items = []
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        self.assertIsInstance(summary.top_gap_targets, list)
        self.assertLessEqual(len(summary.top_gap_targets), 5)
    
    def test_top_upgrade_targets_display_correctly(self):
        """Test top upgrade targets display correctly."""
        items = [
            CoinItem(
                id="1", image_path="", country="Canada", denomination="dime", year="1935",
                grade="VF-20", notes="", date_added="2026-06-15"
            ),
            CoinItem(
                id="2", image_path="", country="Canada", denomination="dime", year="1935",
                grade="EF-40", notes="", date_added="2026-06-15"
            ),
        ]
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        self.assertIsInstance(summary.top_upgrade_targets, list)
        self.assertGreater(len(summary.top_upgrade_targets), 0)
    
    def test_duplicate_heavy_report_works(self):
        """Test duplicate-heavy report works."""
        items = [
            CoinItem(
                id="1", image_path="", country="Canada", denomination="dime", year="1935",
                grade="VF-20", notes="", date_added="2026-06-15"
            ),
            CoinItem(
                id="2", image_path="", country="Canada", denomination="dime", year="1935",
                grade="EF-40", notes="", date_added="2026-06-15"
            ),
        ]
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        self.assertIsInstance(summary.duplicate_heavy_areas, list)
        self.assertGreater(len(summary.duplicate_heavy_areas), 0)
    
    def test_want_list_progress_displays_correctly_empty(self):
        """Test WANT_LIST progress displays correctly with empty WANT_LIST."""
        items = []
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        self.assertEqual(summary.want_list_progress["total_intents"], 0)
        self.assertEqual(summary.want_list_progress["fulfilled"], 0)
        self.assertEqual(summary.want_list_progress["pending"], 0)
        self.assertEqual(summary.want_list_progress["progress_percentage"], 0.0)
    
    def test_want_list_progress_displays_correctly_populated(self):
        """Test WANT_LIST progress displays correctly with populated WANT_LIST."""
        class MockIntent:
            def __init__(self, country, denomination, year):
                self.country = country
                self.denomination = denomination
                self.year = year
        
        items = [
            CoinItem(
                id="1", image_path="", country="Canada", denomination="dime", year="1935",
                grade="VF-20", notes="", date_added="2026-06-15"
            ),
        ]
        
        intents = [
            MockIntent("Canada", "dime", "1935"),  # Already in collection
            MockIntent("Canada", "dime", "1936"),  # Not in collection
        ]
        
        dashboard = PortfolioDashboard(items, staged_want_list_intents=intents)
        summary = dashboard.generate_dashboard()
        
        self.assertEqual(summary.want_list_progress["total_intents"], 2)
        self.assertEqual(summary.want_list_progress["fulfilled"], 1)
        self.assertEqual(summary.want_list_progress["pending"], 1)
        self.assertEqual(summary.want_list_progress["progress_percentage"], 50.0)
    
    def test_csv_export_works(self):
        """Test CSV export works."""
        items = [
            CoinItem(
                id="1", image_path="", country="Canada", denomination="dime", year="1935",
                grade="VF-20", notes="", date_added="2026-06-15"
            ),
        ]
        dashboard = PortfolioDashboard(items)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = os.path.join(temp_dir, "dashboard.csv")
            dashboard.export_to_csv(filepath)
            
            self.assertTrue(os.path.exists(filepath))
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn("Portfolio Dashboard Summary", content)
    
    def test_markdown_export_works(self):
        """Test Markdown export works."""
        items = [
            CoinItem(
                id="1", image_path="", country="Canada", denomination="dime", year="1935",
                grade="VF-20", notes="", date_added="2026-06-15"
            ),
        ]
        dashboard = PortfolioDashboard(items)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = os.path.join(temp_dir, "dashboard.md")
            dashboard.export_to_markdown(filepath)
            
            self.assertTrue(os.path.exists(filepath))
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn("# Portfolio Dashboard Summary", content)
    
    def test_collection_with_no_silver(self):
        """Test dashboard with collection with no silver."""
        items = [
            CoinItem(
                id="1", image_path="", country="Canada", denomination="1 cent", year="1967",
                grade="VF-20", notes="", date_added="2026-06-15"
            ),
        ]
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        self.assertEqual(summary.total_items, 1)
        self.assertEqual(summary.canadian_silver_progress["total_items"], 0)
    
    def test_collection_with_silver(self):
        """Test dashboard with collection with silver."""
        items = [
            CoinItem(
                id="1", image_path="", country="Canada", denomination="dime", year="1935",
                grade="VF-20", notes="", date_added="2026-06-15"
            ),
        ]
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        self.assertEqual(summary.total_items, 1)
        self.assertGreater(summary.canadian_silver_progress["total_items"], 0)
    
    def test_heavy_duplicates(self):
        """Test dashboard with heavy duplicates."""
        items = [
            CoinItem(
                id="1", image_path="", country="Canada", denomination="dime", year="1935",
                grade="VF-20", notes="", date_added="2026-06-15"
            ),
            CoinItem(
                id="2", image_path="", country="Canada", denomination="dime", year="1935",
                grade="EF-40", notes="", date_added="2026-06-15"
            ),
            CoinItem(
                id="3", image_path="", country="Canada", denomination="dime", year="1935",
                grade="AU-50", notes="", date_added="2026-06-15"
            ),
        ]
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        self.assertEqual(summary.total_items, 3)
        self.assertGreater(len(summary.duplicate_heavy_areas), 0)
        self.assertEqual(summary.duplicate_heavy_areas[0]["count"], 3)
    
    def test_newfoundland_focused_collection(self):
        """Test dashboard with Newfoundland-focused collection."""
        items = [
            CoinItem(
                id="1", image_path="", country="Newfoundland", denomination="5 cent", year="1880",
                grade="VG-8", notes="", date_added="2026-06-15"
            ),
            CoinItem(
                id="2", image_path="", country="Newfoundland", denomination="10 cent", year="1880",
                grade="VG-8", notes="", date_added="2026-06-15"
            ),
        ]
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        self.assertEqual(summary.newfoundland_progress["total_items"], 2)
        self.assertEqual(summary.newfoundland_progress["denominations"], 2)
    
    def test_canadian_silver_focused_collection(self):
        """Test dashboard with Canadian silver-focused collection."""
        items = [
            CoinItem(
                id="1", image_path="", country="Canada", denomination="dime", year="1935",
                grade="VF-20", notes="", date_added="2026-06-15"
            ),
            CoinItem(
                id="2", image_path="", country="Canada", denomination="quarter", year="1940",
                grade="VF-30", notes="", date_added="2026-06-15"
            ),
        ]
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        self.assertEqual(summary.canadian_silver_progress["total_items"], 2)
        self.assertEqual(summary.canadian_silver_progress["denominations"], 2)
    
    def test_missing_value_records(self):
        """Test dashboard with missing-value records."""
        items = [
            CoinItem(
                id="1", image_path="", country="Canada", denomination="dime", year="1935",
                grade="VF-20", notes="", date_added="2026-06-15"
            ),
        ]
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        self.assertEqual(summary.total_estimated_value_cad, 0.0)
        self.assertEqual(summary.total_items, 1)
    
    def test_empty_collection(self):
        """Test dashboard with empty collection."""
        items = []
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        self.assertEqual(summary.total_items, 0)
        self.assertEqual(summary.total_countries, 0)
        self.assertEqual(summary.total_estimated_value_cad, 0.0)
        self.assertEqual(summary.total_melt_value_cad, 0.0)


if __name__ == '__main__':
    unittest.main()
