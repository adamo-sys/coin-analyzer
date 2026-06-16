"""v0.6 Melt Value Engine release audit tests."""

import unittest
import tempfile
import os
import time
from melt_value_engine import (
    MeltValueEngine,
    ASWReferenceLoader,
    ManualSpotPriceProvider,
    ApiSpotPriceProvider,
)
from buy_advisor import BuyAdvisor
from upgrade_advisor import UpgradeAdvisor
from coin_collection import CoinCollection, CoinItem


class TestV06MeltValueAudit(unittest.TestCase):
    """Comprehensive v0.6 release audit tests."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.asw_loader = ASWReferenceLoader()
        self.manual_provider = ManualSpotPriceProvider(default_spot_price_cad=35.0)
        self.api_provider = ApiSpotPriceProvider(default_spot_price_cad=35.0)
        self.manual_engine = MeltValueEngine(self.asw_loader, self.manual_provider)
        self.api_engine = MeltValueEngine(self.asw_loader, self.api_provider)
        
        # Create test collection
        self.temp_dir = tempfile.TemporaryDirectory()
        self.collection_path = os.path.join(self.temp_dir.name, "collection.json")
        self.collection = CoinCollection(self.collection_path)
        
        # Add test coins
        self.collection.add_item(CoinItem(
            id="1", country="Canada", denomination="dime", year="1935",
            grade="VF-20", quantity=1, image_path="", notes="", date_added="2026-06-15"
        ))
        self.collection.add_item(CoinItem(
            id="2", country="Canada", denomination="quarter", year="1940",
            grade="VF-30", quantity=1, image_path="", notes="", date_added="2026-06-15"
        ))
        self.collection.add_item(CoinItem(
            id="3", country="Newfoundland", denomination="50 cent", year="1909",
            grade="F-12", quantity=1, image_path="", notes="", date_added="2026-06-15"
        ))
        self.collection.add_item(CoinItem(
            id="4", country="Canada", denomination="1 cent", year="1859",
            grade="VG-8", quantity=1, image_path="", notes="", date_added="2026-06-15"
        ))
        self.collection.add_item(CoinItem(
            id="5", country="Argentina", denomination="1.0", year="1960",
            grade="VF-20", quantity=1, image_path="", notes="", date_added="2026-06-15"
        ))
        
        self.buy_advisor = BuyAdvisor(self.collection)
        self.upgrade_advisor = UpgradeAdvisor(self.collection.items)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
        # Clean up test cache file
        try:
            if os.path.exists("data/test_silver_spot_cache.json"):
                os.remove("data/test_silver_spot_cache.json")
        except:
            pass
    
    def test_manual_spot_price_provider(self):
        """Test ManualSpotPriceProvider works."""
        provider = ManualSpotPriceProvider(default_spot_price_cad=35.0)
        self.assertEqual(provider.get_spot_price(), 35.0)
        
        provider.set_manual_spot_price(40.0)
        self.assertEqual(provider.get_spot_price(), 40.0)
        
        provider.reset_to_default()
        self.assertEqual(provider.get_spot_price(), 35.0)
    
    def test_api_spot_price_provider(self):
        """Test ApiSpotPriceProvider works."""
        provider = ApiSpotPriceProvider(default_spot_price_cad=35.0)
        # Should return default price when no cache and API fails
        self.assertEqual(provider.get_spot_price(), 35.0)
    
    def test_api_failure_fallback(self):
        """Test API failure falls back to cached/default price."""
        provider = ApiSpotPriceProvider(default_spot_price_cad=35.0)
        
        # Set cached price
        provider._cached_price = 40.0
        provider._cache_timestamp = time.time()
        
        # API should fail but fallback to cached
        price, warning = provider.refresh_spot_price()
        self.assertEqual(price, 40.0)
        self.assertIsNotNone(warning)
        self.assertIn("API", warning)
    
    def test_24_hour_cache_validity(self):
        """Test 24-hour cache validity."""
        provider = ApiSpotPriceProvider(default_spot_price_cad=35.0)
        
        # Fresh cache
        provider._cached_price = 40.0
        provider._cache_timestamp = time.time()
        self.assertTrue(provider._is_cache_valid())
        
        # Stale cache (25 hours old)
        provider._cache_timestamp = time.time() - (25 * 3600)
        self.assertFalse(provider._is_cache_valid())
    
    def test_melt_value_engine_canadian_silver_dime(self):
        """Test melt value calculation for Canadian silver dime."""
        result = self.manual_engine.calculate_melt_value(
            country="Canada",
            denomination="dime",
            year="1935"
        )
        
        self.assertTrue(result.is_silver)
        self.assertGreater(result.melt_value_cad, 0)
        self.assertEqual(result.source, "ESTIMATED")
        self.assertEqual(result.confidence, "LOW")
    
    def test_melt_value_engine_canadian_silver_quarter(self):
        """Test melt value calculation for Canadian silver quarter."""
        result = self.manual_engine.calculate_melt_value(
            country="Canada",
            denomination="quarter",
            year="1940"
        )
        
        self.assertTrue(result.is_silver)
        self.assertGreater(result.melt_value_cad, 0)
        self.assertEqual(result.source, "ESTIMATED")
        self.assertEqual(result.confidence, "LOW")
    
    def test_melt_value_engine_newfoundland_silver(self):
        """Test melt value calculation for Newfoundland silver."""
        result = self.manual_engine.calculate_melt_value(
            country="Newfoundland",
            denomination="50 cent",
            year="1909"
        )
        
        self.assertTrue(result.is_silver)
        self.assertGreater(result.melt_value_cad, 0)
        self.assertEqual(result.source, "ESTIMATED")
        self.assertEqual(result.confidence, "LOW")
    
    def test_melt_value_engine_1859_large_cent_non_silver(self):
        """Test melt value calculation for 1859 Large Cent (non-silver)."""
        result = self.manual_engine.calculate_melt_value(
            country="Canada",
            denomination="1 cent",
            year="1859"
        )
        
        self.assertFalse(result.is_silver)
        self.assertEqual(result.melt_value_cad, 0.0)
        self.assertEqual(result.asw_oz, 0.0)
    
    def test_melt_value_engine_world_base_metal_non_silver(self):
        """Test melt value calculation for random world base metal (non-silver)."""
        result = self.manual_engine.calculate_melt_value(
            country="Argentina",
            denomination="1.0",
            year="1960"
        )
        
        self.assertFalse(result.is_silver)
        self.assertEqual(result.melt_value_cad, 0.0)
        self.assertEqual(result.asw_oz, 0.0)
    
    def test_manual_spot_price_override(self):
        """Test manual spot price override works."""
        provider = ManualSpotPriceProvider(default_spot_price_cad=35.0)
        engine = MeltValueEngine(self.asw_loader, provider)
        
        # Calculate with default price
        result1 = engine.calculate_melt_value(
            country="Canada",
            denomination="dime",
            year="1935"
        )
        
        # Override spot price
        provider.set_manual_spot_price(40.0)
        result2 = engine.calculate_melt_value(
            country="Canada",
            denomination="dime",
            year="1935"
        )
        
        # Melt value should increase with higher spot price
        self.assertGreater(result2.melt_value_cad, result1.melt_value_cad)
    
    def test_buy_advisor_still_works(self):
        """Test Buy Advisor still works with melt value integration."""
        rec = self.buy_advisor.advise(
            country="Argentina",
            denomination="1.0",
            year="1960",
            asking_price=2.00,
            shipping=1.00,
            tax_fees=0.20,
        )
        
        # Should still work and identify as duplicate
        self.assertTrue(rec.already_owned)
        self.assertEqual(rec.recommendation, "Duplicate")
        self.assertEqual(rec.purchase_verdict, "PASS")
    
    def test_buy_advisor_displays_melt_value_as_supporting_factor(self):
        """Test Buy Advisor displays melt value as supporting factor only."""
        rec = self.buy_advisor.advise(
            country="Canada",
            denomination="dime",
            year="1935",
            asking_price=5.00,
            shipping=1.00,
            tax_fees=0.20,
        )
        
        # Melt value should be available for silver coins
        self.assertTrue(rec.melt_value_available)
        self.assertIsNotNone(rec.melt_value_cad)
        # Melt value should be mentioned in explanation
        self.assertIn("Melt value", rec.explanation)
    
    def test_buy_advisor_not_driven_by_melt_value(self):
        """Test Buy Advisor recommendations are not driven by melt value alone."""
        # Test a duplicate scenario - should still be PASS regardless of melt value
        rec = self.buy_advisor.advise(
            country="Argentina",
            denomination="1.0",
            year="1960",
            asking_price=2.00,
            shipping=1.00,
            tax_fees=0.20,
        )
        
        # Should still be PASS even though it's non-silver (no melt value)
        self.assertEqual(rec.purchase_verdict, "PASS")
    
    def test_upgrade_advisor_still_works(self):
        """Test Upgrade Advisor still works with melt value integration."""
        rec = self.upgrade_advisor.analyze_upgrade(
            candidate_country="Canada",
            candidate_denomination="dime",
            candidate_year="1935",
            candidate_grade="EF-40",
            candidate_estimate=15.0
        )
        
        # Should still work and provide a verdict
        self.assertIsNotNone(rec.verdict)
        self.assertIn(rec.verdict, ["Strong Upgrade", "Upgrade", "Hold Existing", "Duplicate", "Pass"])
    
    def test_upgrade_advisor_displays_melt_value_as_supporting_factor(self):
        """Test Upgrade Advisor displays melt value as supporting factor only."""
        rec = self.upgrade_advisor.analyze_upgrade(
            candidate_country="Canada",
            candidate_denomination="dime",
            candidate_year="1935",
            candidate_grade="EF-40",
            candidate_estimate=15.0
        )
        
        # Melt value should be available for silver coins
        self.assertIsNotNone(rec.candidate_melt_value_cad)
        self.assertIsNotNone(rec.existing_melt_value_cad)
        # Melt value should be mentioned in explanation
        self.assertIn("Melt Value Analysis", rec.explanation)
    
    def test_upgrade_advisor_not_driven_by_melt_value(self):
        """Test Upgrade Advisor recommendations are not driven by melt value alone."""
        # Test a lower-grade candidate - should still be Hold Existing regardless of melt value
        rec = self.upgrade_advisor.analyze_upgrade(
            candidate_country="Canada",
            candidate_denomination="dime",
            candidate_year="1935",
            candidate_grade="G-4",
            candidate_estimate=5.0
        )
        
        # Should still be Hold Existing even though it has melt value
        self.assertEqual(rec.verdict, "Hold Existing")
    
    def test_non_silver_coins_no_false_melt_values(self):
        """Test non-silver coins do not receive false melt values."""
        # Test 1859 Large Cent
        result1 = self.manual_engine.calculate_melt_value(
            country="Canada",
            denomination="1 cent",
            year="1859"
        )
        self.assertFalse(result1.is_silver)
        self.assertEqual(result1.melt_value_cad, 0.0)
        
        # Test world base metal
        result2 = self.manual_engine.calculate_melt_value(
            country="Argentina",
            denomination="1.0",
            year="1960"
        )
        self.assertFalse(result2.is_silver)
        self.assertEqual(result2.melt_value_cad, 0.0)


if __name__ == '__main__':
    unittest.main()
