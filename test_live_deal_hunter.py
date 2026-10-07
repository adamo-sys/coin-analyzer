import csv
import copy
import os
import tempfile
import unittest

from coin_collection import CoinItem
from deal_hunter import DealHunterResult, DealListing, ParsedDealCandidate
from deal_hunter_ranking import DealHunterRankingReport, RankedDeal, RankingScore
from market_intelligence import (
    DealQuality,
    FairValueEstimate,
    MarketIntelligenceEngine,
    MarketIntelligenceReport,
    OpportunityConfidence,
    RiskSummary,
)
from live_deal_hunter import (
    FLAG_DUPLICATE_URL,
    FLAG_MISSING_PRICE,
    FLAG_UNKNOWN_SELLER,
    LiveDealHunter,
    LiveDealHunterReport,
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
        from unittest.mock import patch
        from deal_hunter import DealHunterReport, DealHunterResult, ParsedDealCandidate

        batch = self.connector.parse_feed(self.feed_text, source_name="Fixture RSS")
        hunter = LiveDealHunter(self.items)
        report = hunter.analyze_batch(batch)
        self.assertIsNotNone(report.ranking_report)
        self.assertEqual(report.ranking_report.ranked_deals, [])
        self.assertEqual(len(report.ranking_report.unranked_deals), report.accepted_count)
        self.assertEqual(report.top_opportunities, [])
        for row in report.ranking_report.unranked_deals:
            self.assertEqual(row.recommendation, "REVIEW")
            self.assertIsNone(row.rank)
            self.assertIsNone(row.ranking_score.score)
        candidate = report.candidate_pool.listings[0]
        self.assertEqual(candidate.total_cost, 100)
        # Already-supported downstream result: RSS prose supplies no authority.
        supported = DealHunterResult(candidate, ParsedDealCandidate(),
                                     "Supported boundary", 80, 20, 70, 0, 120, "WATCH", "Manual review")
        with patch("deal_hunter_ranking.DealHunter.generate_report", return_value=DealHunterReport([supported])):
            supported_report = hunter.analyze_batch(batch)
        self.assertEqual(len(supported_report.ranking_report.ranked_deals), 1)
        self.assertEqual(supported_report.top_opportunities[0].rank, 1)
        self.assertIsNotNone(supported_report.top_opportunities[0].ranking_score.score)
        self.assertEqual(supported_report.top_opportunities[0].listing, candidate)

    def test_market_intelligence_integration(self):
        from unittest.mock import patch
        from deal_hunter import DealHunterResult, ParsedDealCandidate
        from deal_hunter_ranking import DealHunterRankingReport, RankedDeal, RankingScore

        batch = self.connector.parse_feed(self.feed_text, source_name="Fixture RSS")
        hunter = LiveDealHunter(self.items)
        report = hunter.analyze_batch(batch)
        self.assertEqual(report.market_intelligence_reports, [])
        self.assertEqual(len(report.ranking_report.unranked_deals), report.accepted_count)
        self.assertEqual(report.market_enrichment_report.enriched_count, report.accepted_count)
        self.assertTrue(all(row.escalated_recommendation == "REVIEW"
                            for row in report.market_enrichment_report.enriched_candidates))
        candidate = report.candidate_pool.listings[0]
        supported = DealHunterResult(candidate, ParsedDealCandidate(country="Newfoundland", denomination="50 cents", year="1901", grade="VF20"),
                                     "Supported boundary", 80, 20, 70, 0, 120, "WATCH", "Manual review")
        ranked = RankedDeal(1, candidate, supported, RankingScore(80), "WATCH", "Supported boundary", "Within budget")
        ranking = DealHunterRankingReport(ranked_deals=[ranked], candidate_count=1)
        with patch.object(hunter.ranking_engine, "rank_pool", return_value=ranking), patch(
                "market_intelligence.DealHunter.analyze_listing", return_value=supported):
            supported_report = hunter.analyze_batch(batch)
        self.assertEqual(len(supported_report.market_intelligence_reports), 1)
        market = supported_report.market_intelligence_reports[0]
        self.assertEqual(market.listing, candidate)
        self.assertEqual(market.listing.total_cost, 100)
        self.assertEqual(market.fair_value.expected_value, 120)
        self.assertIsNotNone(market.confidence.score)
        self.assertEqual(market.deal_quality.quality, "Excellent")

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

    def _valuation_report(self, expected_value=None):
        listing = DealListing("Canada 25 cents 1936 VF20", 30, 5)
        if expected_value is None:
            market = MarketIntelligenceEngine([]).evaluate_listing(listing)
        else:
            # Explicit already-supported downstream boundary, not title authority.
            supported = DealHunterResult(
                listing, ParsedDealCandidate(), "Supported boundary",
                80, 20, 70, 0, expected_value, "WATCH", "Manual review",
            )
            market = MarketIntelligenceReport(
                listing, supported, DealQuality("Fair"),
                OpportunityConfidence(score=70),
                FairValueEstimate(expected_value=expected_value,
                                  basis="Explicit supported downstream fixture"),
                RiskSummary(),
            )
        return LiveDealHunterReport(
            "Synthetic local review", "2026-10-06",
            market_intelligence_reports=[market],
        )

    def _csv_rows(self, report):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "live.csv")
            self.assertTrue(report.export_csv(path))
            with open(path, newline="", encoding="utf-8") as handle:
                return list(csv.DictReader(handle))

    def test_markdown_unavailable_valuation(self):
        report = self._valuation_report()
        before = copy.deepcopy(report.to_dict())
        self.assertIsNone(report.market_intelligence_reports[0].fair_value.expected_value)
        rendered = report.format_markdown()
        self.assertIn("expected value unavailable", rendered)
        self.assertNotIn("expected value $0.00", rendered)
        self.assertEqual(report.to_dict(), before)
        self.assertEqual(report.market_intelligence_reports[0].deal_result.recommendation, "REVIEW")

    def test_markdown_supported_zero_valuation(self):
        report = self._valuation_report(0)
        before = copy.deepcopy(report.to_dict())
        rendered = report.format_markdown()
        self.assertIn("expected value $0.00", rendered)
        self.assertNotIn("unavailable", rendered)
        self.assertIn("confidence 70", rendered)
        self.assertEqual(report.to_dict(), before)

    def test_markdown_supported_nonzero_valuation(self):
        for value, text in [(120.125, "$120.12"), (-12.5, "$-12.50")]:
            with self.subTest(value=value):
                report = self._valuation_report(value)
                before = copy.deepcopy(report.to_dict())
                self.assertIn("expected value " + text, report.format_markdown())
                self.assertEqual(report.to_dict(), before)

    def test_csv_unavailable_valuation(self):
        report = self._valuation_report()
        before = copy.deepcopy(report.to_dict())
        row = next(row for row in self._csv_rows(report) if row["section"] == "market_intelligence")
        self.assertIn("expected_value=unavailable", row["detail"])
        self.assertNotIn("expected_value=0", row["detail"])
        self.assertEqual(report.to_dict(), before)

    def test_csv_supported_zero_valuation(self):
        report = self._valuation_report(0)
        before = copy.deepcopy(report.to_dict())
        row = next(row for row in self._csv_rows(report) if row["section"] == "market_intelligence")
        self.assertEqual(row["detail"], "confidence=70; expected_value=0.00")
        self.assertEqual(report.to_dict(), before)

    def test_csv_supported_nonzero_valuation(self):
        for value, text in [(120.125, "120.12"), (-12.5, "-12.50")]:
            with self.subTest(value=value):
                report = self._valuation_report(value)
                before = copy.deepcopy(report.to_dict())
                row = next(row for row in self._csv_rows(report) if row["section"] == "market_intelligence")
                self.assertEqual(row["detail"], "confidence=70; expected_value=" + text)
                self.assertEqual(report.to_dict(), before)

    def test_mixed_supported_ranking_unresolved_market_presentation(self):
        from unittest.mock import patch

        batch = self.connector.parse_feed(self.feed_text, source_name="Fixture RSS")
        hunter = LiveDealHunter(self.items)
        candidate = batch.listings[0].to_deal_listing()
        supported = DealHunterResult(
            candidate, ParsedDealCandidate(), "Supported boundary",
            80, 20, 70, 0, 120, "WATCH", "Manual review",
        )
        ranked = RankedDeal(1, candidate, supported, RankingScore(80),
                            "WATCH", "Supported boundary", "Within budget")
        ranking = DealHunterRankingReport(ranked_deals=[ranked], candidate_count=1)
        # Retain the supplied ranking only; fresh MI and enrichment remain real.
        with patch.object(hunter.ranking_engine, "rank_pool", return_value=ranking):
            report = hunter.analyze_batch(batch)
        market = report.market_intelligence_reports[0]
        self.assertIsNone(market.fair_value.expected_value)
        self.assertEqual(market.deal_result.recommendation, "REVIEW")
        before = copy.deepcopy(report.to_dict())
        listing_before = copy.deepcopy(candidate.__dict__)
        rendered = report.format_markdown()
        rows = self._csv_rows(report)
        self.assertIn("expected value unavailable", rendered)
        self.assertIn("1. 1901 Newfoundland 50 cents VF20 C$95.00 - WATCH", rendered)
        self.assertIn("score 80, cost $100.00", rendered)
        market_row = next(row for row in rows if row["section"] == "market_intelligence")
        self.assertIn("expected_value=unavailable", market_row["detail"])
        ranked_row = next(row for row in rows if row["section"] == "top_opportunity")
        self.assertIn("score=80; cost=100.00; url=https://www.ebay.ca/itm/1001", ranked_row["detail"])
        self.assertIs(report.top_opportunities[0], ranked)
        self.assertEqual(candidate.price_cad, 95)
        self.assertEqual(candidate.shipping_cad, 5)
        self.assertEqual(report.to_dict(), before)
        self.assertEqual(candidate.__dict__, listing_before)


if __name__ == "__main__":
    unittest.main()
