"""Unit tests for Melt Value Engine."""

import unittest
import tempfile
import os
import time
from melt_value_engine import (
    MeltValueEngine,
    ASWReferenceLoader,
    SpotPriceProvider,
    ManualSpotPriceProvider,
    ApiSpotPriceProvider,
    ASWReferenceEntry,
    MeltValueResult,
)


class TestManualSpotPriceProvider(unittest.TestCase):
    """Test ManualSpotPriceProvider functionality."""
    
    def test_default_spot_price(self):
        """Test default spot price."""
        provider = ManualSpotPriceProvider(default_spot_price_cad=35.0)
        self.assertEqual(provider.get_spot_price(), 35.0)
    
    def test_manual_override(self):
        """Test manual spot price override."""
        provider = ManualSpotPriceProvider(default_spot_price_cad=35.0)
        provider.set_manual_spot_price(40.0)
        self.assertEqual(provider.get_spot_price(), 40.0)
    
    def test_reset_to_default(self):
        """Test reset to default spot price."""
        provider = ManualSpotPriceProvider(default_spot_price_cad=35.0)
        provider.set_manual_spot_price(40.0)
        provider.reset_to_default()
        self.assertEqual(provider.get_spot_price(), 35.0)
    
    def test_none_manual_price(self):
        """Test that None manual price uses default."""
        provider = ManualSpotPriceProvider(default_spot_price_cad=35.0)
        provider.manual_spot_price_cad = None
        self.assertEqual(provider.get_spot_price(), 35.0)
    
    def test_refresh_spot_price(self):
        """Test refresh spot price returns current price with no warning."""
        provider = ManualSpotPriceProvider(default_spot_price_cad=35.0)
        price, warning = provider.refresh_spot_price()
        self.assertEqual(price, 35.0)
        self.assertIsNone(warning)


class TestApiSpotPriceProvider(unittest.TestCase):
    """Test ApiSpotPriceProvider functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.original_cache_file = ApiSpotPriceProvider.CACHE_FILE
        self.cache_directory = tempfile.TemporaryDirectory()
        ApiSpotPriceProvider.CACHE_FILE = os.path.join(
            self.cache_directory.name,
            "silver_spot_cache.json",
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        ApiSpotPriceProvider.CACHE_FILE = self.original_cache_file
        self.cache_directory.cleanup()
    
    def test_default_spot_price(self):
        """Test default spot price when no cache."""
        provider = ApiSpotPriceProvider(default_spot_price_cad=35.0)
        self.assertEqual(provider.get_spot_price(), 35.0)
    
    def test_manual_override(self):
        """Test manual spot price override."""
        provider = ApiSpotPriceProvider(default_spot_price_cad=35.0)
        provider.set_manual_spot_price(40.0)
        self.assertEqual(provider.get_spot_price(), 40.0)
    
    def test_api_failure_fallback(self):
        """Test API failure falls back to cached/default price."""
        provider = ApiSpotPriceProvider(default_spot_price_cad=35.0)
        price, warning = provider.refresh_spot_price()
        
        # Should return default price since API returns None
        self.assertEqual(price, 35.0)
        self.assertIsNotNone(warning)  # Should have warning about API failure
    
    def test_cached_fallback(self):
        """Test cached price fallback when API fails."""
        provider = ApiSpotPriceProvider(default_spot_price_cad=35.0)
        
        # Manually set cached price
        provider._cached_price = 40.0
        provider._cache_timestamp = time.time()
        
        price, warning = provider.refresh_spot_price()
        
        # Should return cached price
        self.assertEqual(price, 40.0)
        self.assertIsNotNone(warning)
    
    def test_cache_validity(self):
        """Test cache validity check."""
        provider = ApiSpotPriceProvider(default_spot_price_cad=35.0)
        
        # No cache
        self.assertFalse(provider._is_cache_valid())
        
        # Fresh cache
        provider._cached_price = 40.0
        provider._cache_timestamp = time.time()
        self.assertTrue(provider._is_cache_valid())
        
        # Stale cache (25 hours old)
        provider._cache_timestamp = time.time() - (25 * 3600)
        self.assertFalse(provider._is_cache_valid())
    
    def test_cache_persistence(self):
        """Test cache save and load."""
        provider = ApiSpotPriceProvider(default_spot_price_cad=35.0)
        provider._cached_price = 40.0
        provider._cache_timestamp = time.time()
        provider._save_cache()
        
        # Create new provider and load cache
        provider2 = ApiSpotPriceProvider(default_spot_price_cad=35.0)
        self.assertEqual(provider2._cached_price, 40.0)
        self.assertIsNotNone(provider2._cache_timestamp)
    
    def test_reset_to_default(self):
        """Test reset to default clears cache and manual override."""
        provider = ApiSpotPriceProvider(default_spot_price_cad=35.0)
        provider.set_manual_spot_price(40.0)
        provider._cached_price = 45.0
        provider._cache_timestamp = time.time()
        
        provider.reset_to_default()
        
        self.assertIsNone(provider.manual_spot_price_cad)
        self.assertIsNone(provider._cached_price)
        self.assertIsNone(provider._cache_timestamp)
        self.assertEqual(provider.get_spot_price(), 35.0)


class TestASWReferenceLoader(unittest.TestCase):
    """Test ASWReferenceLoader functionality."""
    
    def test_initialization(self):
        """Test loader initialization."""
        loader = ASWReferenceLoader()
        self.assertFalse(loader.is_loaded())
        self.assertEqual(len(loader._asw_cache), 0)
    
    def test_cache_entry(self):
        """Test entry caching."""
        loader = ASWReferenceLoader()
        entry = ASWReferenceEntry(
            country_series="Canada",
            denomination="dollar",
            year_range="1935-1967",
            asw_oz=0.0588,
            notes="Silver dollar"
        )
        loader._cache_entry(entry)
        
        self.assertTrue(loader.is_loaded())
        found = loader.find_asw_entry("Canada", "dollar")
        self.assertIsNotNone(found)
        self.assertEqual(found.asw_oz, 0.0588)
    
    def test_case_insensitive_lookup(self):
        """Test case-insensitive lookup."""
        loader = ASWReferenceLoader()
        entry = ASWReferenceEntry(
            country_series="Canada",
            denomination="dollar",
            year_range="1935-1967",
            asw_oz=0.0588,
            notes="Silver dollar"
        )
        loader._cache_entry(entry)
        
        # Test different cases
        self.assertIsNotNone(loader.find_asw_entry("canada", "dollar"))
        self.assertIsNotNone(loader.find_asw_entry("CANADA", "DOLLAR"))
        self.assertIsNotNone(loader.find_asw_entry("Canada", "DOLLAR"))
    
    def test_missing_entry(self):
        """Test lookup of missing entry."""
        loader = ASWReferenceLoader()
        entry = ASWReferenceEntry(
            country_series="Canada",
            denomination="dollar",
            year_range="1935-1967",
            asw_oz=0.0588,
            notes="Silver dollar"
        )
        loader._cache_entry(entry)
        
        self.assertIsNone(loader.find_asw_entry("USA", "dollar"))
        self.assertIsNone(loader.find_asw_entry("Canada", "quarter"))
    
    def test_clear_cache(self):
        """Test cache clearing."""
        loader = ASWReferenceLoader()
        entry = ASWReferenceEntry(
            country_series="Canada",
            denomination="dollar",
            year_range="1935-1967",
            asw_oz=0.0588,
            notes="Silver dollar"
        )
        loader._cache_entry(entry)
        self.assertTrue(loader.is_loaded())
        
        loader.clear_cache()
        self.assertFalse(loader.is_loaded())
        self.assertEqual(len(loader._asw_cache), 0)
    
    def test_load_from_workbook_missing_sheet(self):
        """Test loading from workbook without ASW_REFERENCE sheet."""
        loader = ASWReferenceLoader()
        
        # Create a temporary workbook without ASW_REFERENCE sheet
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            temp_path = f.name
        
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            wb.remove(wb.active)
            wb.create_sheet("OTHER_SHEET")
            wb.save(temp_path)
            wb.close()
            
            entries = loader.load_from_workbook(temp_path)
            self.assertEqual(len(entries), 0)
            self.assertFalse(loader.is_loaded())
            
        finally:
            # Give Excel time to release the file
            import time
            time.sleep(0.1)
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except PermissionError:
                # If file is still locked, skip cleanup
                pass


class TestMeltValueEngine(unittest.TestCase):
    """Test MeltValueEngine functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.asw_loader = ASWReferenceLoader()
        self.spot_provider = ManualSpotPriceProvider(default_spot_price_cad=35.0)
        self.engine = MeltValueEngine(self.asw_loader, self.spot_provider)
    
    def test_silver_coin_detection(self):
        """Test silver coin detection."""
        # Canadian silver
        self.assertTrue(self.engine._is_silver_coin("Canada", "dollar"))
        self.assertTrue(self.engine._is_silver_coin("Canada", "quarter"))
        self.assertTrue(self.engine._is_silver_coin("Canada", "dime"))
        
        # Newfoundland silver
        self.assertTrue(self.engine._is_silver_coin("Newfoundland", "50 cent"))
        self.assertTrue(self.engine._is_silver_coin("Newfoundland", "10 cent"))
        
        # Non-silver
        self.assertFalse(self.engine._is_silver_coin("Canada", "1 cent"))
        self.assertFalse(self.engine._is_silver_coin("USA", "1 cent"))
    
    def test_asw_estimation(self):
        """Test ASW estimation for silver coins."""
        # Canadian silver denominations
        self.assertGreater(self.engine._estimate_asw("dollar"), 0)
        self.assertGreater(self.engine._estimate_asw("quarter"), 0)
        self.assertGreater(self.engine._estimate_asw("dime"), 0)
        
        # Non-silver
        self.assertEqual(self.engine._estimate_asw("1 cent"), 0.0)
    
    def test_melt_value_calculation_with_manual_asw(self):
        """Test melt value calculation with manual ASW."""
        result = self.engine.calculate_melt_value(
            country="Canada",
            denomination="dollar",
            year="1935",
            manual_asw_oz=0.0588
        )
        
        self.assertEqual(result.coin_country, "Canada")
        self.assertEqual(result.coin_denomination, "dollar")
        self.assertEqual(result.asw_oz, 0.0588)
        self.assertEqual(result.source, "CALCULATED")
        self.assertEqual(result.confidence, "HIGH")
        self.assertTrue(result.is_silver)
        self.assertAlmostEqual(result.melt_value_cad, 0.0588 * 35.0, places=2)
    
    def test_melt_value_calculation_with_workbook_asw(self):
        """Test melt value calculation with workbook ASW."""
        # Add entry to cache
        entry = ASWReferenceEntry(
            country_series="Canada",
            denomination="dollar",
            year_range="1935-1967",
            asw_oz=0.0588,
            notes="Silver dollar"
        )
        self.asw_loader._cache_entry(entry)
        
        result = self.engine.calculate_melt_value(
            country="Canada",
            denomination="dollar",
            year="1935"
        )
        
        self.assertEqual(result.asw_oz, 0.0588)
        self.assertEqual(result.source, "WORKBOOK")
        self.assertEqual(result.confidence, "HIGH")
    
    def test_melt_value_calculation_with_estimated_asw(self):
        """Test melt value calculation with estimated ASW."""
        result = self.engine.calculate_melt_value(
            country="Canada",
            denomination="dollar",
            year="1935"
        )
        
        self.assertEqual(result.source, "ESTIMATED")
        self.assertEqual(result.confidence, "LOW")
        self.assertGreater(result.asw_oz, 0)
    
    def test_melt_value_for_non_silver(self):
        """Test melt value for non-silver coin."""
        result = self.engine.calculate_melt_value(
            country="Canada",
            denomination="1 cent",
            year="1967"
        )
        
        self.assertFalse(result.is_silver)
        self.assertEqual(result.melt_value_cad, 0.0)
        self.assertEqual(result.asw_oz, 0.0)
    
    def test_melt_value_with_workbook_bullion_reference(self):
        """Test melt value with workbook bullion value preserved."""
        result = self.engine.calculate_melt_value(
            country="Canada",
            denomination="dollar",
            year="1935",
            manual_asw_oz=0.0588,
            workbook_bullion_value=2.50
        )
        
        self.assertEqual(result.workbook_bullion_value, 2.50)
    
    def test_spot_price_changes(self):
        """Test that spot price changes affect melt value."""
        result1 = self.engine.calculate_melt_value(
            country="Canada",
            denomination="dollar",
            year="1935",
            manual_asw_oz=0.0588
        )
        
        self.spot_provider.set_manual_spot_price(40.0)
        result2 = self.engine.calculate_melt_value(
            country="Canada",
            denomination="dollar",
            year="1935",
            manual_asw_oz=0.0588
        )
        
        self.assertGreater(result2.melt_value_cad, result1.melt_value_cad)
    
    def test_newfoundland_silver_detection(self):
        """Test Newfoundland silver coin detection."""
        result = self.engine.calculate_melt_value(
            country="Newfoundland",
            denomination="50 cent",
            year="1909",
            manual_asw_oz=0.0588
        )
        
        self.assertTrue(result.is_silver)
        self.assertGreater(result.melt_value_cad, 0)
    
    def test_refresh_spot_price_flag(self):
        """Test refresh_spot flag triggers refresh."""
        result = self.engine.calculate_melt_value(
            country="Canada",
            denomination="dollar",
            year="1935",
            manual_asw_oz=0.0588,
            refresh_spot=True
        )
        
        # Should have no warning for manual provider
        self.assertIsNone(result.spot_price_warning)
    
    def test_spot_price_warning_in_result(self):
        """Test that spot price warnings are included in result."""
        # Use API provider to test warnings
        api_provider = ApiSpotPriceProvider(default_spot_price_cad=35.0)
        api_engine = MeltValueEngine(self.asw_loader, api_provider)
        
        result = api_engine.calculate_melt_value(
            country="Canada",
            denomination="dollar",
            year="1935",
            manual_asw_oz=0.0588,
            refresh_spot=True
        )
        
        # Should have warning since API returns None
        self.assertIsNotNone(result.spot_price_warning)


if __name__ == '__main__':
    unittest.main()
