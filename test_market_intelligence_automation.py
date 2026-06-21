import os
import tempfile
import unittest
from unittest.mock import patch

from coin_collection import CoinItem
from deal_hunter import DealListing
from deal_hunter_ranking import CandidatePool, DealHunterRankingEngine
from live_deal_hunter import LiveDealHunter, RSSListingConnector
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord
from market_intelligence_automation import (
    FairValueEvidenceSummary,
    MarketIntelligenceAutomationEngine,
    REVIEW_CONFIDENCE_THRESHOLD,
)


def item(item_id, country, denomination, year, grade="VF-20"):
    return CoinItem(item_id, "", country, denomination, year, grade, "", "2026-06-21")


def listing(title, price=80, shipping=5, seller="seller", source="Manual"):
    return DealListing(
        title=title,
        price_cad=price,
        shipping_cad=shipping,
        seller=seller,
        source=source,
        listing_url=f"https://example.test/{abs(hash(title))}",
        description=title,
    )


class TestMarketIntelligenceAutomation(unittest.TestCase):
    def setUp(self):
        self.items = [
            item("1", "Newfoundland", "50 cents", "1900"),
            item("2", "Newfoundland", "50 cents", "1902"),
            item("3", "Canada", "10 cents", "1910"),
            item("4", "Canada", "1 cent", "1859", "G-4"),
        ]
        self.market = MarketAwarenessEngine()
        self.market.observations.append(ObservedPriceRecord(
            item_name="1901 Newfoundland 50 cents VF20",
            country="Newfoundland",
            denomination="50 cents",
            year="1901",
            grade="VF-20",
            observed_price=95,
            shipping=5,
            source="Local comp",
            date_observed="2026-06-20",
        ))
        self.engine = MarketIntelligenceAutomationEngine(self.items, market_awareness_engine=self.market)

    def test_single_candidate_enrichment(self):
        enriched = self.engine.enrich_candidate(listing("1901 Newfoundland 50 cents VF20", 80, 5))
        self.assertEqual(enriched.original_recommendation, "UNKNOWN")
        self.assertTrue(enriched.deal_quality)
        self.assertGreater(enriched.fair_value_estimate, 0)
        self.assertGreaterEqual(enriched.collection_relevance.collection_relevance_score, 0)

    def test_candidate_pool_enrichment(self):
        pool = CandidatePool.from_listings([
            listing("1901 Newfoundland 50 cents VF20", 80, 5),
            listing("1911 Canada 10 cents silver VF20", 25, 4),
        ])
        report = self.engine.enrich_candidate_pool(pool)
        self.assertEqual(report.candidates_processed, 2)
        self.assertEqual(report.enriched_count, 2)
        self.assertEqual(report.skipped_count, 0)

    def test_batch_enrichment(self):
        report = self.engine.enrich_candidates([
            listing("1901 Newfoundland 50 cents VF20", 80, 5),
            {"listing": listing("1859 Canada Large Cent Wide 9 VF20", 60, 5), "recommendation": "WATCH"},
        ])
        self.assertEqual(report.enriched_count, 2)
        self.assertEqual(report.enriched_candidates[1].original_recommendation, "WATCH")

    def test_upgrade_classification(self):
        enriched = self.engine.enrich_candidate(listing("1859 Canada 1 cent VF20 Large Cent", 45, 5))
        self.assertIn("Upgrade", enriched.collection_relevance.classifications)

    def test_want_list_classification(self):
        want_engine = MarketIntelligenceAutomationEngine(
            self.items,
            want_list_intents=[type("Want", (), {"target_coin": "1901 Newfoundland 50 cents", "priority": "High"})()],
            market_awareness_engine=self.market,
        )
        enriched = want_engine.enrich_candidate(listing("1901 Newfoundland 50 cents VF20", 80, 5))
        self.assertIn("Want-List Match", enriched.collection_relevance.classifications)

    def test_collection_gap_classification(self):
        enriched = self.engine.enrich_candidate(listing("1901 Newfoundland 50 cents VF20", 80, 5))
        self.assertTrue(
            "Collection Gap" in enriched.collection_relevance.classifications
            or "General Collection Fit" in enriched.collection_relevance.classifications
        )

    def test_duplicate_classification(self):
        enriched = self.engine.enrich_candidate(listing("1900 Newfoundland 50 cents VF20", 80, 5))
        self.assertTrue(any("Duplicate" in row for row in enriched.collection_relevance.classifications))

    def test_low_confidence_escalation_preserves_original(self):
        enriched = self.engine.enrich_candidate(listing("Unknown world token as-is", 0, 0, seller="", source="Manual"))
        self.assertEqual(enriched.original_recommendation, "UNKNOWN")
        self.assertEqual(enriched.escalated_recommendation, "REVIEW")
        self.assertTrue(enriched.escalation_reason)
        self.assertLess(enriched.opportunity_confidence, REVIEW_CONFIDENCE_THRESHOLD)

    def test_fair_value_evidence_summary(self):
        enriched = self.engine.enrich_candidate(listing("1901 Newfoundland 50 cents VF20", 80, 5))
        summary = enriched.evidence_summary
        self.assertIsInstance(summary, FairValueEvidenceSummary)
        self.assertGreaterEqual(summary.comparable_sales_count, 1)
        self.assertIn(summary.evidence_quality, {"Moderate", "Strong"})

    def test_ranking_integration(self):
        pool = CandidatePool.from_listings([
            listing("1901 Newfoundland 50 cents VF20", 80, 5),
            listing("1911 Canada 10 cents silver VF20", 25, 4),
        ])
        ranking = DealHunterRankingEngine(self.items, market_awareness_engine=self.market).rank_pool(pool)
        report = self.engine.enrich_ranking_report(ranking)
        self.assertEqual(report.enriched_count, len(ranking.ranked_deals))
        self.assertTrue(report.enriched_candidates[0].deal_quality)

    def test_live_deal_hunter_integration(self):
        fixture_path = os.path.join("test_data", "deal_hunter", "sample_live_rss.xml")
        with open(fixture_path, "r", encoding="utf-8") as handle:
            batch = RSSListingConnector().parse_feed(handle.read(), source_name="Fixture RSS")
        live_report = LiveDealHunter(self.items, market_awareness_engine=self.market).analyze_batch(batch)
        self.assertIsNotNone(live_report.market_enrichment_report)
        self.assertGreaterEqual(live_report.market_enrichment_report.enriched_count, 1)

    def test_export_generation(self):
        report = self.engine.enrich_candidates([listing("1901 Newfoundland 50 cents VF20", 80, 5)])
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "automation.csv")
            md_path = os.path.join(tmpdir, "automation.md")
            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            self.assertTrue(os.path.exists(csv_path))
            self.assertTrue(os.path.exists(md_path))
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("Market Intelligence Automation Report", handle.read())

    def test_no_live_price_retrieval(self):
        candidate = listing("1901 Newfoundland 50 cents VF20", 80, 5)
        with patch("urllib.request.urlopen", side_effect=AssertionError("network should not be used")):
            enriched = self.engine.enrich_candidate(candidate)
        self.assertTrue(enriched.deal_quality)


if __name__ == "__main__":
    unittest.main()
