import os
import tempfile
import unittest

from coin_collection import CoinItem
from live_deal_hunter import (
    FLAG_DUPLICATE_URL,
    FLAG_MISSING_PRICE,
    FLAG_UNKNOWN_SELLER,
    LiveDealHunter,
    LiveListingBatch,
    RSSListingConnector,
)


FIXTURE_PATH = os.path.join("test_data", "deal_hunter", "sample_live_rss.xml")


def make_item(item_id, country, denomination, year, grade="VF-20"):
    return CoinItem(item_id, "", country, denomination, year, grade, "", "2026-06-21")


class FailingSource:
    source_name = "Failing test source"

    def fetch_listings(self):
        return LiveListingBatch(self.source_name, errors=["network error: fixture unavailable"])


class TestLiveDealHunter(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE_PATH, "r", encoding="utf-8") as handle:
            self.feed_text = handle.read()
        self.connector = RSSListingConnector("https://www.ebay.ca/sch/i.html?_nkw=test&_rss=1")
        self.items = [
            make_item("1", "Newfoundland", "50 cents", "1900"),
            make_item("2", "Newfoundland", "50 cents", "1902"),
            make_item("3", "Canada", "10 cents", "1910"),
        ]

    def test_rss_feed_parsing(self):
        batch = self.connector.parse_feed(self.feed_text, source_name="Fixture RSS")
        self.assertEqual(batch.listing_count, 4)
        self.assertEqual(batch.listings[0].title, "1901 Newfoundland 50 cents VF20 C$95.00")
        self.assertEqual(batch.listings[0].price, 95.0)
        self.assertEqual(batch.listings[0].shipping, 5.0)
        self.assertEqual(batch.listings[0].currency, "CAD")

    def test_source_validation(self):
        batch = self.connector.parse_feed(self.feed_text, source_name="Fixture RSS")
        duplicate = batch.listings[2]
        missing = batch.listings[3]
        self.assertIn(FLAG_DUPLICATE_URL, duplicate.validation_flags)
        self.assertIn(FLAG_MISSING_PRICE, missing.validation_flags)
        self.assertIn(FLAG_UNKNOWN_SELLER, missing.validation_flags)

    def test_listing_normalization(self):
        batch = self.connector.parse_feed(self.feed_text, source_name="Fixture RSS")
        normalized = batch.listings[0].to_normalized_listing()
        deal_listing = normalized.to_deal_listing()
        self.assertEqual(normalized.source_type, "Live RSS")
        self.assertEqual(deal_listing.title, batch.listings[0].title)
        self.assertEqual(deal_listing.listing_url, "https://www.ebay.ca/itm/1001")

    def test_candidate_pool_integration(self):
        batch = self.connector.parse_feed(self.feed_text, source_name="Fixture RSS")
        report = LiveDealHunter(self.items).analyze_batch(batch)
        self.assertEqual(report.listing_count, 4)
        self.assertEqual(report.accepted_count, 2)
        self.assertEqual(report.rejected_count, 2)
        self.assertEqual(report.candidate_pool.candidate_count, 2)

    def test_ranking_integration(self):
        batch = self.connector.parse_feed(self.feed_text, source_name="Fixture RSS")
        report = LiveDealHunter(self.items).analyze_batch(batch)
        self.assertIsNotNone(report.ranking_report)
        self.assertGreaterEqual(len(report.ranking_report.ranked_deals), 1)
        self.assertTrue(report.top_opportunities)

    def test_market_intelligence_integration(self):
        batch = self.connector.parse_feed(self.feed_text, source_name="Fixture RSS")
        report = LiveDealHunter(self.items).analyze_batch(batch)
        self.assertGreaterEqual(len(report.market_intelligence_reports), 1)
        self.assertTrue(report.market_intelligence_reports[0].deal_quality.quality)

    def test_duplicate_detection(self):
        batch = self.connector.parse_feed(self.feed_text, source_name="Fixture RSS")
        report = LiveDealHunter(self.items).analyze_batch(batch)
        self.assertTrue(any("Duplicate listing URL" in warning for warning in report.validation_warnings))

    def test_report_generation_and_exports(self):
        batch = self.connector.parse_feed(self.feed_text, source_name="Fixture RSS")
        report = LiveDealHunter(self.items).analyze_batch(batch)
        self.assertIn("Live Deal Hunter Report", report.format_markdown())
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "live.csv")
            md_path = os.path.join(tmpdir, "live.md")
            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            self.assertTrue(os.path.exists(csv_path))
            self.assertTrue(os.path.exists(md_path))

    def test_failure_handling(self):
        report = LiveDealHunter(self.items).run_source(FailingSource())
        self.assertEqual(report.listing_count, 0)
        self.assertEqual(report.accepted_count, 0)
        self.assertIn("network error", report.errors[0])

    def test_malformed_feed_failure(self):
        batch = self.connector.parse_feed("<rss><bad>", source_name="Broken RSS")
        self.assertEqual(batch.listing_count, 0)
        self.assertTrue(batch.errors)


if __name__ == "__main__":
    unittest.main()
