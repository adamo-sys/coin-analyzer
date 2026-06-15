"""Unit tests for collection search and analysis behavior."""

import os
import shutil
import tempfile
import unittest

from coin_collection import CoinCollection


FIXTURE_COLLECTION = os.path.join(
    os.path.dirname(__file__),
    "test_data",
    "sample_collection.json",
)


class TestCollectionAnalysis(unittest.TestCase):
    """Exercise analysis using isolated fixture data."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.collection_path = os.path.join(self.temp_dir.name, "collection.json")
        shutil.copy(FIXTURE_COLLECTION, self.collection_path)
        self.collection = CoinCollection(self.collection_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_autocomplete_uses_numista_items_only(self):
        suggestions = self.collection.get_autocomplete_suggestions("country", "can")

        self.assertIn("Canada", suggestions)
        self.assertNotIn("Manualia", suggestions)

    def test_find_matching_coins_returns_exact_matches(self):
        matches = self.collection.find_matching_coins("Canada", "1 cent", "1966")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].id, "fixture_canada_cent_1966")

    def test_analyze_collection_gaps_counts_fixture_data(self):
        analysis = self.collection.analyze_collection_gaps()

        self.assertEqual(analysis["total_coins"], 5)
        self.assertEqual(analysis["countries"]["Canada"], 2)
        self.assertEqual(analysis["years"]["1966"], 1)
        self.assertEqual(analysis["denominations"]["1 cent"], 1)
        self.assertEqual(analysis["numista_coverage"], 80.0)


if __name__ == "__main__":
    unittest.main()
