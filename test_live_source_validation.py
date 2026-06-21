import os
import tempfile
import unittest

from live_deal_hunter import LiveListing, LiveListingBatch, RSSListingConnector
from live_source_validation import (
    ISSUE_DUPLICATE_URL,
    ISSUE_MALFORMED_URL,
    ISSUE_MISSING_PRICE,
    ISSUE_MISSING_SELLER,
    ISSUE_MISSING_TITLE,
    ISSUE_MISSING_URL,
    ISSUE_NON_CAD,
    ISSUE_UNKNOWN_CURRENCY,
    ListingFreshness,
    LiveSourceValidator,
    SourceHealthStatus,
)


def listing(**overrides):
    values = {
        "title": "1901 Newfoundland 50 cents VF20",
        "price": 95.0,
        "shipping": 5.0,
        "currency": "CAD",
        "seller": "trusted-seller",
        "source": "Fixture RSS",
        "url": "https://www.ebay.ca/itm/validation-1",
        "listing_timestamp": "Sat, 20 Jun 2026 12:00:00 GMT",
        "raw_metadata": {"description": "Newfoundland silver coin"},
    }
    values.update(overrides)
    return LiveListing(**values)


class TestLiveSourceValidation(unittest.TestCase):
    def setUp(self):
        self.validator = LiveSourceValidator()

    def validate_one(self, item):
        return self.validator.validate_listings([item])[0]

    def test_missing_title(self):
        result = self.validate_one(listing(title=""))
        self.assertIn(ISSUE_MISSING_TITLE, result.issue_codes)
        self.assertFalse(result.valid_for_pipeline)

    def test_missing_price(self):
        result = self.validate_one(listing(price=0))
        self.assertIn(ISSUE_MISSING_PRICE, result.issue_codes)
        self.assertFalse(result.valid_for_pipeline)

    def test_missing_seller(self):
        result = self.validate_one(listing(seller=""))
        self.assertIn(ISSUE_MISSING_SELLER, result.issue_codes)
        self.assertTrue(result.valid_for_pipeline)
        self.assertTrue(result.review_required)

    def test_missing_url(self):
        result = self.validate_one(listing(url=""))
        self.assertIn(ISSUE_MISSING_URL, result.issue_codes)
        self.assertFalse(result.valid_for_pipeline)

    def test_cad_listing(self):
        result = self.validate_one(listing())
        self.assertEqual(result.freshness, ListingFreshness.FRESH)
        self.assertTrue(result.valid_for_pipeline)
        self.assertNotIn(ISSUE_NON_CAD, result.issue_codes)

    def test_non_cad_listing(self):
        result = self.validate_one(listing(currency="USD"))
        self.assertIn(ISSUE_NON_CAD, result.issue_codes)
        self.assertTrue(result.valid_for_pipeline)
        self.assertTrue(result.review_required)

    def test_unknown_currency(self):
        result = self.validate_one(listing(currency="UNKNOWN"))
        self.assertIn(ISSUE_UNKNOWN_CURRENCY, result.issue_codes)
        self.assertTrue(result.review_required)

    def test_stale_listing(self):
        result = self.validate_one(listing(listing_timestamp="Fri, 01 May 2026 12:00:00 GMT"))
        self.assertEqual(result.freshness, ListingFreshness.STALE)
        self.assertTrue(result.review_required)

    def test_duplicate_urls(self):
        first = listing(url="https://www.ebay.ca/itm/dup")
        second = listing(url="https://www.ebay.ca/itm/dup", title="1902 Newfoundland 50 cents")
        results = self.validator.validate_listings([first, second])
        self.assertTrue(results[0].valid_for_pipeline)
        self.assertIn(ISSUE_DUPLICATE_URL, results[1].issue_codes)
        self.assertFalse(results[1].valid_for_pipeline)

    def test_malformed_urls(self):
        result = self.validate_one(listing(url="not-a-url"))
        self.assertIn(ISSUE_MALFORMED_URL, result.issue_codes)
        self.assertFalse(result.valid_for_pipeline)

    def test_source_health_scoring(self):
        batch = LiveListingBatch("Unhealthy fixture", listings=[
            listing(url="https://www.ebay.ca/itm/ok"),
            listing(url="https://www.ebay.ca/itm/ok", title="duplicate"),
            listing(url="not-a-url"),
            listing(title="", url="https://www.ebay.ca/itm/missing-title"),
        ])
        report = self.validator.validate_batch(batch)
        self.assertEqual(report.source_health.status, SourceHealthStatus.UNHEALTHY)
        self.assertLess(report.summary.validation_pass_rate, 0.5)
        self.assertEqual(report.summary.duplicate_count, 1)
        self.assertEqual(report.summary.malformed_count, 1)

    def test_validation_reports_and_exports(self):
        batch = LiveListingBatch("Report fixture", listings=[
            listing(),
            listing(url="", title="Missing URL"),
        ])
        report = self.validator.validate_batch(batch)
        self.assertIn("Live Source Validation Report", report.format_markdown())
        self.assertEqual(report.summary.total_listings, 2)
        self.assertEqual(report.summary.invalid_count, 1)
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "validation.csv")
            md_path = os.path.join(tmpdir, "validation.md")
            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            self.assertTrue(os.path.exists(csv_path))
            self.assertTrue(os.path.exists(md_path))

    def test_live_deal_hunter_fixture_validation(self):
        fixture_path = os.path.join("test_data", "deal_hunter", "sample_live_rss.xml")
        with open(fixture_path, "r", encoding="utf-8") as handle:
            feed_text = handle.read()
        batch = RSSListingConnector().parse_feed(feed_text, source_name="Fixture RSS")
        report = self.validator.validate_batch(batch)
        self.assertEqual(report.summary.total_listings, 4)
        self.assertEqual(report.summary.valid_count, 2)
        self.assertEqual(report.summary.invalid_count, 2)


if __name__ == "__main__":
    unittest.main()
