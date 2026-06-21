"""Tests for the v3.3 Opportunity Engine."""

import os
import tempfile
import unittest

from coin_collection import CoinItem
from deal_hunter import DealHunter, DealListing
from focused_collection_intelligence import CandidateItem
from legacy_portfolio_importer import LegacyWantListIntent
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord
from opportunity_engine import (
    OPPORTUNITY_CANADIAN_BANKNOTE,
    OPPORTUNITY_COLLECTION_GAP,
    OPPORTUNITY_NEWFOUNDLAND,
    OPPORTUNITY_UPGRADE,
    OPPORTUNITY_WANT_LIST,
    OpportunityEngine,
    OpportunityReport,
    TopOpportunitiesReport,
)
from smart_shopping_assistant import ShoppingCandidate


def make_item(item_id, country, denomination, year, grade, **overrides):
    data = {
        "id": item_id,
        "image_path": "",
        "country": country,
        "denomination": denomination,
        "year": year,
        "grade": grade,
        "notes": "",
        "date_added": "2026-06-21",
    }
    data.update(overrides)
    return CoinItem(**data)


def make_intent(target_coin, priority_score=90):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id=f"opp_{target_coin}",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=150.0,
        why_wanted="Opportunity target",
        status="Active",
        priority_score=priority_score,
    )


class TestOpportunityEngine(unittest.TestCase):
    def setUp(self):
        self.items = [
            make_item("nf1900", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("nf1902", "Newfoundland", "50 cents", "1902", "VF-20"),
            make_item("ca1911a", "Canada", "10 cents", "1911", "VG-8"),
            make_item("ca1911b", "Canada", "10 cents", "1911", "EF-40"),
            make_item("lc1859", "Canada", "1 cent", "1859", "G-4"),
        ]
        self.intents = [
            make_intent("Newfoundland 50 cents 1901", 95),
            make_intent("Canada chartered banknote BCS VF25", 80),
        ]
        self.market = MarketAwarenessEngine(observations=[
            ObservedPriceRecord("1901 Newfoundland 50 cents", "Newfoundland", "50 cents", "1901", "VF-20", 90),
            ObservedPriceRecord("1911 Canada 10 cents", "Canada", "10 cents", "1911", "EF-40", 70),
        ])
        self.engine = OpportunityEngine(self.items, self.intents, self.market)

    def test_generate_top_opportunities_report(self):
        report = self.engine.generate_report(limit=5)

        self.assertIsInstance(report, TopOpportunitiesReport)
        self.assertGreater(len(report.opportunities), 0)
        self.assertGreaterEqual(report.opportunities[0].score, report.opportunities[-1].score)

    def test_upgrade_opportunity_from_collection_targets(self):
        report = self.engine.generate_report(limit=10)

        self.assertTrue(any(row.opportunity_type == OPPORTUNITY_UPGRADE for row in report.opportunities))

    def test_collection_gap_opportunity(self):
        report = self.engine.generate_report(limit=10)

        self.assertTrue(any(row.opportunity_type in {OPPORTUNITY_COLLECTION_GAP, OPPORTUNITY_NEWFOUNDLAND, OPPORTUNITY_WANT_LIST} for row in report.opportunities))

    def test_newfoundland_priority(self):
        report = self.engine.generate_report(limit=10)

        newfoundland = [row for row in report.opportunities if "Newfoundland" in row.item_name]
        self.assertTrue(newfoundland)
        self.assertTrue(any(row.score >= 50 for row in newfoundland))

    def test_banknote_priority(self):
        report = self.engine.generate_report([
            ShoppingCandidate("Canada chartered banknote BCS VF25", asking_price=120, shipping=5)
        ], limit=10)

        self.assertTrue(any(row.opportunity_type == OPPORTUNITY_CANADIAN_BANKNOTE for row in report.opportunities))

    def test_budget_analysis(self):
        candidates = [
            ShoppingCandidate("1901 Newfoundland 50 cents VF20", asking_price=85, shipping=5),
            ShoppingCandidate("Canada chartered banknote BCS VF25", asking_price=240, shipping=10),
        ]
        report = self.engine.generate_report(candidates, budgets=[50, 100, 250, 500])

        self.assertIsNone(report.budget_recommendations[50])
        self.assertIsNotNone(report.budget_recommendations[100])
        self.assertLessEqual(report.budget_recommendations[100].total_cost, 100)

    def test_opportunity_scoring_has_components(self):
        report = self.engine.generate_report(limit=5)
        top = report.opportunities[0]

        self.assertIsNotNone(top.score_detail)
        self.assertGreaterEqual(top.score, 0)
        self.assertLessEqual(top.score, 100)

    def test_counterargument_is_always_present(self):
        report = self.engine.generate_report(limit=10)

        self.assertTrue(all(row.counterargument for row in report.opportunities))

    def test_deal_hunter_integration(self):
        hunter = DealHunter(self.items, self.intents, self.market)
        deal_result = hunter.analyze_listing(DealListing("1901 Newfoundland 50 cents VF20 PCGS", 85, 5))
        report = self.engine.generate_report(deal_hunter_results=[deal_result], limit=10)

        rows = [row for row in report.opportunities if row.source == "Deal Hunter"]
        self.assertTrue(rows)
        self.assertEqual(rows[0].total_cost, 90)

    def test_export_generation(self):
        report = self.engine.generate_report(limit=5)
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "opportunities.csv")
            md_path = os.path.join(temp_dir, "opportunities.md")
            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("counterargument", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("Opportunity Engine Report", handle.read())


if __name__ == "__main__":
    unittest.main()
