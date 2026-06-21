"""Tests for v3.7 Live Deal Hunter readiness models."""

from datetime import datetime, timedelta
import os
import tempfile
import unittest

from live_deal_hunter_readiness import (
    LiveDealHunterReadinessAudit,
    LiveListingBatch,
    LiveListingSource,
    LiveSourceFailure,
    LiveSourceValidationReport,
    RateLimitPolicy,
    STALENESS_FRESH,
    STALENESS_STALE,
    STALENESS_UNKNOWN,
    classify_staleness,
)


class TestLiveDealHunterReadiness(unittest.TestCase):
    def test_readiness_report_generation(self):
        report = LiveDealHunterReadinessAudit().run()

        self.assertEqual(report.status, "READY_WITH_GUARDRAILS")
        self.assertFalse(report.blockers)
        self.assertTrue(any("No automatic purchasing" in rule for rule in report.safety_rules))
        self.assertTrue(report.rate_limit_policies)

    def test_live_source_contract_model_has_no_fetch_implementation(self):
        source = LiveListingSource("Future eBay Source", requires_authentication=True)

        self.assertFalse(source.supports_fetch)
        with self.assertRaises(NotImplementedError):
            source.fetch_listings()

    def test_live_listing_batch_contract(self):
        batch = LiveListingBatch(
            "Future Dealer",
            listings=[{
                "title": "1901 Newfoundland 50 cents VF20",
                "price": 80,
                "shipping": 5,
                "currency": "CAD",
                "seller": "Dealer",
                "url": "https://example.test/listing",
                "image_url": "https://example.test/image.jpg",
                "raw_metadata": {"lot": "A1"},
            }],
        )

        self.assertEqual(batch.source_name, "Future Dealer")
        self.assertEqual(len(batch.listings), 1)
        self.assertTrue(batch.fetched_at)

    def test_source_validation_report_ok(self):
        batch = LiveListingBatch(
            "Future eBay",
            listings=[{
                "title": "1901 Newfoundland 50 cents VF20",
                "price": 80,
                "shipping": 5,
                "currency": "CAD",
                "seller": "Seller A",
                "url": "https://example.test/nf1901",
                "fetched_timestamp": datetime.now().isoformat(sep=" "),
                "raw_metadata": {},
            }],
        )

        report = LiveSourceValidationReport.validate_batch(batch)

        self.assertEqual(report.status, "OK")
        self.assertEqual(report.listings_checked, 1)

    def test_source_validation_report_flags_bad_rows(self):
        stale_time = (datetime.now() - timedelta(days=3)).isoformat(sep=" ")
        batch = LiveListingBatch(
            "Future eBay",
            listings=[
                {
                    "title": "",
                    "price": "",
                    "shipping": "",
                    "currency": "USD",
                    "seller": "",
                    "url": "bad-url",
                    "image_url": "bad-image",
                    "fetched_timestamp": stale_time,
                    "raw_metadata": "not-structured",
                },
                {
                    "title": "Duplicate listing",
                    "price": 10,
                    "shipping": 2,
                    "currency": "CAD",
                    "seller": "Seller",
                    "url": "https://example.test/dup",
                    "fetched_timestamp": datetime.now().isoformat(sep=" "),
                },
                {
                    "title": "Duplicate listing again",
                    "price": 11,
                    "shipping": 2,
                    "currency": "CAD",
                    "seller": "Seller",
                    "url": "https://example.test/dup",
                    "fetched_timestamp": datetime.now().isoformat(sep=" "),
                },
            ],
        )

        report = LiveSourceValidationReport.validate_batch(batch)
        finding_types = {finding.finding_type for finding in report.findings}

        self.assertEqual(report.status, "FAIL")
        self.assertIn("MISSING_TITLE", finding_types)
        self.assertIn("MISSING_PRICE", finding_types)
        self.assertIn("MISSING_SHIPPING", finding_types)
        self.assertIn("NON_CAD_CURRENCY", finding_types)
        self.assertIn("MALFORMED_URL", finding_types)
        self.assertIn("STALE_LISTING", finding_types)
        self.assertIn("DUPLICATE_URL", finding_types)
        self.assertTrue(report.duplicate_urls)

    def test_staleness_flags(self):
        now = datetime(2026, 6, 21, 12, 0, 0)

        self.assertEqual(classify_staleness("2026-06-21 11:00:00", now=now), STALENESS_FRESH)
        self.assertEqual(classify_staleness("2026-06-19 11:00:00", now=now), STALENESS_STALE)
        self.assertEqual(classify_staleness("", now=now), STALENESS_UNKNOWN)

    def test_rate_limit_policy_model(self):
        policy = RateLimitPolicy("Future Auction", allowed_fetch_cadence_minutes=60, batch_size_guidance=75)
        row = policy.to_dict()

        self.assertEqual(row["source_name"], "Future Auction")
        self.assertEqual(row["allowed_fetch_cadence_minutes"], 60)
        self.assertIn("Manual retry", row["retry_guidance"])

    def test_failure_model(self):
        failure = LiveSourceFailure("Future eBay", "rate_limited", "Source returned rate limit.", retryable=True)
        row = failure.to_dict()

        self.assertEqual(row["failure_type"], "rate_limited")
        self.assertTrue(row["retryable"])
        self.assertTrue(row["occurred_at"])

    def test_readiness_audit_includes_validation_report(self):
        batch = LiveListingBatch("Future eBay", listings=[{"title": "", "price": "", "shipping": ""}])

        report = LiveDealHunterReadinessAudit().run(batch)

        self.assertEqual(report.validation_report.status, "FAIL")
        self.assertIn("Resolve live source validation warnings", report.required_next_steps[0])

    def test_export_generation(self):
        report = LiveDealHunterReadinessAudit().run()
        validation = LiveSourceValidationReport.validate_batch(LiveListingBatch("Future eBay", listings=[]))

        with tempfile.TemporaryDirectory() as temp_dir:
            readiness_csv = os.path.join(temp_dir, "readiness.csv")
            readiness_md = os.path.join(temp_dir, "readiness.md")
            validation_csv = os.path.join(temp_dir, "validation.csv")
            validation_md = os.path.join(temp_dir, "validation.md")

            self.assertTrue(report.export_csv(readiness_csv))
            self.assertTrue(report.export_markdown(readiness_md))
            self.assertTrue(validation.export_csv(validation_csv))
            self.assertTrue(validation.export_markdown(validation_md))
            with open(readiness_md, "r", encoding="utf-8") as handle:
                self.assertIn("Live Deal Hunter Readiness Report", handle.read())
            with open(validation_csv, "r", encoding="utf-8") as handle:
                self.assertIn("finding_type", handle.read())


if __name__ == "__main__":
    unittest.main()
