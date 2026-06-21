"""Tests for v3.8 Market Intelligence."""

import os
import tempfile
import unittest

from coin_collection import CoinItem
from deal_hunter import DealListing
from legacy_portfolio_importer import LegacyWantListIntent
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord
from market_intelligence import (
    ComparableSale,
    MarketIntelligenceEngine,
    QUALITY_EXCELLENT,
    QUALITY_FAIR,
    QUALITY_GOOD,
    QUALITY_OVERPRICED,
    QUALITY_WEAK,
)


def make_item(item_id, country, denomination, year, grade):
    return CoinItem(
        id=item_id,
        image_path="",
        country=country,
        denomination=denomination,
        year=year,
        grade=grade,
        notes="",
        date_added="2026-06-21",
    )


def make_intent(target_coin, priority_score=90):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id=f"market_{target_coin}",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=150.0,
        why_wanted="Market intelligence target",
        status="Active",
        priority_score=priority_score,
    )


class TestMarketIntelligence(unittest.TestCase):
    def setUp(self):
        self.items = [
            make_item("nf1900", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("nf1902", "Newfoundland", "50 cents", "1902", "VF-20"),
            make_item("ca1911", "Canada", "10 cents", "1911", "VF-20"),
            make_item("lc1859", "Canada", "1 cent", "1859", "G-4"),
        ]
        self.intents = [
            make_intent("Newfoundland 50 cents 1901", 95),
            make_intent("Canada chartered banknote BCS VF25", 80),
        ]
        self.market = MarketAwarenessEngine(observations=[
            ObservedPriceRecord("1901 Newfoundland 50 cents", "Newfoundland", "50 cents", "1901", "VF-20", 95),
            ObservedPriceRecord("1901 Newfoundland 50 cents", "Newfoundland", "50 cents", "1901", "VF-20", 105),
            ObservedPriceRecord("1911 Canada 10 cents", "Canada", "10 cents", "1911", "EF-40", 70),
        ])
        self.engine = MarketIntelligenceEngine(self.items, self.intents, self.market)

    def test_fair_value_generation_from_local_comps(self):
        report = self.engine.evaluate_listing(DealListing("1901 Newfoundland 50 cents VF20 PCGS", 80, 5))

        self.assertEqual(report.fair_value.evidence_count, 2)
        self.assertEqual(report.fair_value.expected_value, 100)
        self.assertGreater(report.fair_value.aggressive_value, report.fair_value.expected_value)

    def test_confidence_scoring(self):
        report = self.engine.evaluate_listing(DealListing("1901 Newfoundland 50 cents VF20 PCGS", 80, 5))

        self.assertGreaterEqual(report.confidence.score, 70)
        self.assertIn("collection fit", report.confidence.explanation.lower())

    def test_deal_quality_classification_good_or_excellent(self):
        report = self.engine.evaluate_listing(DealListing("1901 Newfoundland 50 cents VF20 PCGS", 80, 5))

        self.assertIn(report.deal_quality.quality, {QUALITY_EXCELLENT, QUALITY_GOOD})
        self.assertTrue(report.deal_quality.reasoning)

    def test_overpriced_classification(self):
        report = self.engine.evaluate_listing(DealListing("1901 Newfoundland 50 cents VF20 PCGS", 170, 5))

        self.assertEqual(report.deal_quality.quality, QUALITY_OVERPRICED)
        self.assertIn("exceeds", " ".join(report.weaknesses + report.deal_quality.reasoning).lower())

    def test_comparable_sales_handling(self):
        report = MarketIntelligenceEngine(self.items, self.intents).evaluate_listing(
            DealListing("1904 Newfoundland 50 cents VF20", 75, 5),
            comparable_sales=[
                ComparableSale("1904 Newfoundland 50 cents comp", 90, source="Manual", sale_type="auction result"),
                ComparableSale("1904 Newfoundland 50 cents comp", 110, source="Manual", sale_type="dealer observation"),
            ],
        )

        self.assertEqual(report.fair_value.evidence_count, 2)
        self.assertEqual(report.fair_value.expected_value, 100)
        self.assertEqual(len(report.comparable_sales), 2)

    def test_risk_analysis_high_shipping_and_raw_grade(self):
        report = self.engine.evaluate_listing(DealListing("1901 Newfoundland 50 cents MS65 raw", 80, 40))

        risk_text = " ".join(report.risk_summary.risk_factors)
        self.assertIn("High shipping", risk_text)
        self.assertIn("Raw grade risk", risk_text)
        self.assertEqual(report.risk_summary.severity, "High")

    def test_counterargument_generation(self):
        report = self.engine.evaluate_listing(DealListing("1901 Newfoundland 50 cents VF20 PCGS", 80, 5))

        self.assertTrue(report.counterargument)
        self.assertTrue(
            any(term in report.counterargument.lower() for term in ["shipping", "opportunities", "review"])
        )

    def test_duplicate_handling(self):
        report = self.engine.evaluate_listing(DealListing("1900 Newfoundland 50 cents VF20 ICCS", 75, 5))

        self.assertEqual(report.deal_quality.quality, QUALITY_WEAK)
        self.assertTrue(any("Duplicate" in weakness for weakness in report.weaknesses))

    def test_upgrade_handling(self):
        report = self.engine.evaluate_listing(DealListing("1900 Newfoundland 50 cents EF40 ICCS", 90, 5))

        self.assertIn("Upgrade potential", report.strengths)
        self.assertGreater(report.confidence.upgrade_potential, 0)

    def test_unknown_or_fair_without_local_evidence(self):
        report = MarketIntelligenceEngine([], []).evaluate_listing(DealListing("Canada 25 cents 1936 VF20", 30, 5))

        self.assertIn(report.deal_quality.quality, {QUALITY_GOOD, QUALITY_FAIR, QUALITY_WEAK, "Unknown", QUALITY_OVERPRICED})
        self.assertEqual(report.fair_value.evidence_count, 0)

    def test_export_generation(self):
        report = self.engine.evaluate_listing(DealListing("1901 Newfoundland 50 cents VF20 PCGS", 80, 5))
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "market_intelligence.csv")
            md_path = os.path.join(temp_dir, "market_intelligence.md")

            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("deal_quality", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("Market Intelligence Report", handle.read())


if __name__ == "__main__":
    unittest.main()
