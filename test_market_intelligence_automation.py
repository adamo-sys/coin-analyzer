import os
import csv
import json
from dataclasses import replace
import tempfile
import unittest
from unittest.mock import patch

from coin_collection import CoinItem
from deal_hunter import DealListing, DealHunterReport, DealHunterResult, ParsedDealCandidate
from market_intelligence import MarketIntelligenceEngine
from deal_hunter_ranking import CandidatePool, DealHunterRankingEngine
from live_deal_hunter import LiveDealHunter, RSSListingConnector
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord
from market_intelligence_automation import (
    FairValueEvidenceSummary,
    MarketIntelligenceAutomationEngine,
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
    def test_supported_scores_and_relationship_authority_survive_descriptive_prose(self):
        for title in ("Newfoundland 50 cents 1901", "1859 Canada Large Cent", "Canada 10 cents silver"):
            for value in (0, 60):
                with self.subTest(title=title, value=value):
                    candidate = listing(title, 30, 5)
                    result = DealHunterResult(candidate, ParsedDealCandidate(country="Canada", denomination="10 cents", year="1901", grade="VF20"),
                                              "Supported boundary", 80, 20, value, 0, value, "WATCH", "Manual review",
                                              reasons=["Explicit WANT_LIST match", "upgrade", "collection gap"])
                    with patch("market_intelligence.DealHunter.analyze_listing", return_value=result):
                        row = self.engine.enrich_candidate({"listing": candidate, "recommendation": "WATCH"})
                    self.assertEqual(row.collection_relevance.collection_relevance_score, value)
                    self.assertNotIn("Want-List Match", row.collection_relevance.classifications)
                    self.assertNotIn("Upgrade", row.collection_relevance.classifications)
                    self.assertNotIn("Collection Gap", row.collection_relevance.classifications)
                    self.assertEqual(row.collection_relevance.collection_goal_advanced, "General collection fit")
                    self.assertEqual(row.escalated_recommendation, "REVIEW" if value == 0 else "WATCH")

    def test_unavailable_ordinary_flow_preserves_context_and_exports(self):
        candidate = listing("Canada 25 cents 1936 VF20", 30, 5)
        report = MarketIntelligenceAutomationEngine([]).enrich_candidates([
            {"listing": candidate, "recommendation": "BUY"}])
        self.assertEqual(report.errors, [])
        row = report.enriched_candidates[0]
        self.assertIsNone(row.collection_relevance.collection_relevance_score)
        self.assertIsNone(row.opportunity_confidence)
        self.assertIsNone(row.fair_value_estimate)
        self.assertEqual(row.escalated_recommendation, "REVIEW")
        self.assertEqual(row.collection_relevance.classifications, [])
        self.assertEqual(row.original_listing, candidate)
        self.assertEqual(candidate.total_cost, 35)
        self.assertTrue(row.market_intelligence_warnings)
        self.assertIsNone(json.loads(json.dumps(row.to_dict()))["fair_value_estimate"])
        self.assertIn("Expected fair value CAD: unavailable", report.format_markdown())
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.csv")
            report.export_csv(path)
            with open(path, encoding="utf-8", newline="") as handle:
                exported = next(csv.DictReader(handle))
            for key in ("collection_relevance_score", "opportunity_confidence", "fair_value_estimate"):
                self.assertEqual(exported[key], "unavailable")

    def test_supported_zero_positive_and_unavailable_confidence(self):
        for value in (0, 100):
            candidate = listing("Synthetic supported consumer", 30, 5)
            result = DealHunterResult(candidate, ParsedDealCandidate(country="Canada", denomination="25 cents", year="1936", grade="VF20"),
                                      "Supported boundary", value, 20, value, 0, value, "WATCH", "Manual review")
            with patch("market_intelligence.DealHunter.analyze_listing", return_value=result):
                market_report = MarketIntelligenceEngine([]).evaluate_listing(candidate)
            engine = MarketIntelligenceAutomationEngine([])
            with patch.object(engine.market_intelligence_engine, "evaluate_listing", return_value=market_report):
                row = engine.enrich_candidate({"listing": candidate, "recommendation": "WATCH"})
            self.assertEqual(row.collection_relevance.collection_relevance_score, value)
            self.assertEqual(row.fair_value_estimate, value)
            self.assertEqual(row.opportunity_confidence, 60 if value == 0 else 85)
            self.assertEqual(row.escalated_recommendation, "REVIEW" if value == 0 else "WATCH")
            for score, expected in ((None, "REVIEW"), (0, "REVIEW"), (80, "WATCH")):
                changed = replace(market_report, confidence=replace(market_report.confidence, score=score))
                with patch.object(engine.market_intelligence_engine, "evaluate_listing", return_value=changed):
                    row = engine.enrich_candidate({"listing": candidate, "recommendation": "WATCH"})
                self.assertEqual(row.escalated_recommendation, "REVIEW" if value == 0 else expected)
                self.assertEqual(row.opportunity_confidence, score)

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
        self.assertEqual(enriched.fair_value_estimate, 100)
        self.assertIsNone(enriched.collection_relevance.collection_relevance_score)
        self.assertIsNone(enriched.opportunity_confidence)
        self.assertEqual(enriched.escalated_recommendation, "REVIEW")
        self.assertEqual(enriched.original_listing.total_cost, 85)

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
        self.assertNotIn("Upgrade", enriched.collection_relevance.classifications)
        self.assertIsNone(enriched.collection_relevance.collection_relevance_score)
        self.assertEqual(enriched.escalated_recommendation, "REVIEW")
        self.assertEqual(enriched.original_listing.total_cost, 50)
        self.assertTrue(enriched.market_intelligence_warnings)

    def test_want_list_classification(self):
        want_engine = MarketIntelligenceAutomationEngine(
            self.items,
            want_list_intents=[type("Want", (), {"target_coin": "1901 Newfoundland 50 cents", "priority": "High"})()],
            market_awareness_engine=self.market,
        )
        enriched = want_engine.enrich_candidate(listing("1901 Newfoundland 50 cents VF20", 80, 5))
        self.assertEqual(enriched.collection_relevance.classifications, [])
        self.assertIsNone(enriched.collection_relevance.collection_relevance_score)
        self.assertEqual(enriched.escalated_recommendation, "REVIEW")
        self.assertEqual(enriched.fair_value_estimate, 100)
        self.assertEqual(enriched.original_listing.total_cost, 85)

    def test_collection_gap_classification(self):
        enriched = self.engine.enrich_candidate(listing("1901 Newfoundland 50 cents VF20", 80, 5))
        self.assertEqual(enriched.collection_relevance.classifications, [])
        self.assertIsNone(enriched.collection_relevance.collection_relevance_score)
        self.assertEqual(enriched.escalated_recommendation, "REVIEW")
        self.assertEqual(enriched.fair_value_estimate, 100)
        self.assertEqual(enriched.original_listing.total_cost, 85)

    def test_duplicate_classification(self):
        enriched = self.engine.enrich_candidate(listing("1900 Newfoundland 50 cents VF20", 80, 5))
        self.assertEqual(enriched.collection_relevance.classifications, [])
        self.assertIsNone(enriched.collection_relevance.collection_relevance_score)
        self.assertEqual(enriched.escalated_recommendation, "REVIEW")
        self.assertEqual(enriched.original_listing.total_cost, 85)
        self.assertTrue(enriched.market_intelligence_warnings)

    def test_low_confidence_escalation_preserves_original(self):
        enriched = self.engine.enrich_candidate(listing("Unknown world token as-is", 0, 0, seller="", source="Manual"))
        self.assertEqual(enriched.original_recommendation, "UNKNOWN")
        self.assertEqual(enriched.escalated_recommendation, "REVIEW")
        self.assertTrue(enriched.escalation_reason)
        self.assertIsNone(enriched.opportunity_confidence)
        self.assertEqual(enriched.original_listing.total_cost, 0)

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
        self.assertEqual(ranking.ranked_deals, [])
        self.assertEqual(len(ranking.unranked_deals), 2)
        self.assertEqual(report.candidates_processed, 2)
        self.assertEqual(report.enriched_count, 2)
        self.assertEqual(report.skipped_count, 0)
        self.assertEqual(report.errors, [])
        for row in report.enriched_candidates:
            self.assertEqual(row.escalated_recommendation, "REVIEW")
            self.assertIsNone(row.opportunity_confidence)
            self.assertIsNone(row.collection_relevance.collection_relevance_score)
        self.assertEqual(report.enriched_candidates[0].fair_value_estimate, 100)
        self.assertEqual(report.enriched_candidates[0].original_listing.total_cost, 85)
        # Supply numeric authority explicitly at the downstream result boundary.
        candidate = listing("Synthetic supported ranking", 30, 5)
        supported = DealHunterResult(candidate, ParsedDealCandidate(country="Canada", denomination="25 cents", year="1936", grade="VF20"),
                                     "Supported boundary", 80, 20, 80, 0, 100, "WATCH", "Manual review")
        with patch("deal_hunter_ranking.DealHunter.generate_report", return_value=DealHunterReport([supported])):
            ranking = DealHunterRankingEngine([]).rank_pool(CandidatePool.from_listings([candidate]))
        self.assertEqual(len(ranking.ranked_deals), 1)
        with patch("market_intelligence.DealHunter.analyze_listing", return_value=supported):
            positive = self.engine.enrich_ranking_report(ranking)
        self.assertEqual(positive.enriched_count, 1)
        self.assertEqual(positive.errors, [])
        self.assertEqual(positive.enriched_candidates[0].fair_value_estimate, 100)
        self.assertEqual(positive.enriched_candidates[0].collection_relevance.collection_relevance_score, 80)
        self.assertEqual(positive.enriched_candidates[0].escalated_recommendation, "WATCH")

    def test_live_deal_hunter_integration(self):
        fixture_path = os.path.join("test_data", "deal_hunter", "sample_live_rss.xml")
        with open(fixture_path, "r", encoding="utf-8") as handle:
            batch = RSSListingConnector().parse_feed(handle.read(), source_name="Fixture RSS")
        live_report = LiveDealHunter(self.items, market_awareness_engine=self.market).analyze_batch(batch)
        self.assertIsNotNone(live_report.market_enrichment_report)
        self.assertGreaterEqual(live_report.market_enrichment_report.enriched_count, 1)
        enrichment = self.engine.enrich_live_deal_hunter_report(live_report)
        self.assertEqual(enrichment.enriched_count, live_report.accepted_count)
        self.assertEqual(enrichment.errors, [])
        self.assertTrue(all(row.escalated_recommendation == "REVIEW" for row in enrichment.enriched_candidates))

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
