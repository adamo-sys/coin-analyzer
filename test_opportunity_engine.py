"""Tests for the v3.3 Opportunity Engine."""

import os
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

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
    OpportunityScore,
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
    def test_real_needs_review_dominates_stale_deal_advice(self):
        result = DealHunter([]).analyze_listing(DealListing("Unattributed coin lot", 80, 5))
        self.assertEqual(result.collection_status, "needs review")
        for spelling in (result.collection_status, "NEEDS REVIEW", "NEEDS_REVIEW"):
            for status in ("BUY", "WATCH", "PASS"):
                with self.subTest(spelling=spelling, status=status):
                    stale = replace(result, collection_status=spelling, recommendation=status,
                                    priority_score=90, collection_fit_score=90, max_rational_price=100)
                    report = OpportunityEngine([]).generate_report(deal_hunter_results=[stale])
                    self.assertEqual(report.opportunities, [])
                    row = report.unranked_opportunities[0]
                    self.assertIsNone(row.score)
                    self.assertIsNone(row.rank)
                    self.assertEqual(row.recommendation, "REVIEW")
                    self.assertTrue(all(row is None for row in report.budget_recommendations.values()))

    def test_relationship_warning_prose_does_not_penalize_shopping(self):
        from smart_shopping_assistant import ShoppingRecommendation

        engine = OpportunityEngine([])
        row = ShoppingRecommendation(1, "Synthetic", "BUY", 10, 20, 0, 0,
                                     "", "", 100, 12, "Manual")
        baseline = engine._from_shopping(row)
        for text in ("duplicate", "not a duplicate", "upgrade", "not an upgrade", "collection gap", "not a collection gap"):
            with self.subTest(text=text):
                actual = engine._from_shopping(replace(row, warnings=[text]))
                self.assertEqual(actual.score, baseline.score)
                self.assertEqual(actual.score_detail.risk, baseline.score_detail.risk)
                self.assertEqual(actual.opportunity_type, baseline.opportunity_type)
                self.assertIn(text, actual.risks)

    def test_review_dominates_retained_numeric_components(self):
        from smart_shopping_assistant import SmartShoppingAssistant
        engine = OpportunityEngine([])
        deal = DealHunter([]).analyze_listing(DealListing("Unattributed coin lot", 80, 5))
        retained = replace(deal, priority_score=90, collection_fit_score=90)
        self.assertIsNone(engine._from_deal_hunter(retained).score)
        shopping = SmartShoppingAssistant([])._evaluate_candidate(ShoppingCandidate("Unattributed coin lot", asking_price=80, shipping=5))
        row = engine._from_shopping(replace(shopping, opportunity_score=90, impact_score=90, quality_delta=0, series_delta=0))
        self.assertIsNone(row.score)
        self.assertEqual(row.total_cost, 85)
        self.assertEqual(row.recommendation, "REVIEW")

    def test_stale_rank_and_absent_components_remain_unavailable(self):
        engine = OpportunityEngine([])
        unavailable = OpportunityReport(4, "Boundary", "Unresolved", None, recommendation="REVIEW")
        with patch.object(engine, "_deal_hunter_opportunities", return_value=[unavailable]):
            report = engine.generate_report()
        self.assertIsNone(report.unranked_opportunities[0].rank)
        for key in ("collection_fit", "upgrade_impact", "completion_impact", "collection_priority"):
            self.assertIsNone(unavailable.to_dict()[key])
            self.assertEqual(OpportunityReport(None, "Boundary", "Zero", 0, score_detail=OpportunityScore(0)).to_dict()[key], 0)

    def test_negative_relationship_narrative_has_no_bonus(self):
        from deal_hunter import DealHunterResult, ParsedDealCandidate
        from smart_shopping_assistant import ShoppingRecommendation
        engine = OpportunityEngine([])
        deal = DealHunterResult(DealListing("Boundary", 20), ParsedDealCandidate(), "Supported boundary", 20, 0, 20, 0, 20, "WATCH", "Context")
        shopping = ShoppingRecommendation(None, "Boundary", "WATCH", 20, 20, 0, 0, "", "", 20, 20, "Manual")
        for reason in ("not an upgrade", "not a collection gap"):
            self.assertEqual(engine._from_deal_hunter(replace(deal, collection_status=reason, reasons=[reason])).score, engine._from_deal_hunter(deal).score)
            self.assertEqual(engine._from_shopping(replace(shopping, reasons=[reason])).score, engine._from_shopping(shopping).score)

    def test_real_unresolved_outputs_are_unranked_and_preserve_nulls(self):
        from smart_shopping_assistant import SmartShoppingAssistant
        import json

        engine = OpportunityEngine([])
        shopping = SmartShoppingAssistant([]).generate_report(
            [ShoppingCandidate("Unattributed coin lot", asking_price=80, shipping=5)],
            include_want_list_targets=False).recommendations[0]
        deal = DealHunter([]).analyze_listing(DealListing("Unattributed coin lot", 80, 5))
        for row in [engine._from_shopping(shopping), engine._from_deal_hunter(deal)]:
            self.assertIsNone(row.score)
            self.assertIsNone(row.rank)
            self.assertIsNone(row.score_detail.score)
            self.assertEqual(row.total_cost, 85)
            self.assertTrue(row.risks)
            self.assertIsNone(json.loads(json.dumps(row.to_dict()))["score"])
        report = engine.generate_report(deal_hunter_results=[deal])
        self.assertEqual(report.opportunities, [])
        self.assertEqual(len(report.unranked_opportunities), 1)
        self.assertIsNone(report.unranked_opportunities[0].rank)
        self.assertIn("unavailable", report.format_markdown())

    def test_mixed_pool_ranks_only_supported_opportunities(self):
        import json
        engine = OpportunityEngine([])
        unresolved = engine._from_deal_hunter(
            DealHunter([]).analyze_listing(DealListing("Unattributed coin lot", 80, 5)))
        # Explicit already-supported downstream models, not candidate identity evidence.
        supported = OpportunityReport(None, "Boundary fixture", "Supported downstream", 75,
                                      total_cost=75, score_detail=OpportunityScore(75))
        zero = OpportunityReport(None, "Boundary fixture", "Supported zero", 0,
                                 total_cost=40, score_detail=OpportunityScore(0))
        with patch.object(engine, "_deal_hunter_opportunities", return_value=[unresolved, zero, supported]):
            report = engine.generate_report()
        self.assertEqual([row.score for row in report.opportunities], [75, 0])
        self.assertEqual([row.rank for row in report.opportunities], [1, 2])
        self.assertEqual(report.budget_recommendations[100].item_name, "Supported downstream")
        self.assertEqual(report.unranked_opportunities, [unresolved])
        self.assertIsNone(unresolved.score)
        self.assertIsNone(unresolved.rank)
        payload = json.loads(json.dumps(report.to_dict()))
        self.assertEqual(payload["opportunities"][1]["score"], 0)
        self.assertIsNone(payload["unranked_opportunities"][0]["score"])
        self.assertIn("Score: 0", report.format_markdown())

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

        rows = report.unranked_opportunities
        self.assertTrue(rows)
        self.assertTrue(any("1901" in row.item_name for row in rows))
        for row in rows:
            self.assertIsNone(row.score)
            self.assertIsNone(row.rank)
            self.assertEqual(row.recommendation, "REVIEW")

    def test_newfoundland_priority(self):
        report = self.engine.generate_report(limit=10)

        rows = [row for row in report.unranked_opportunities if "Newfoundland" in row.item_name]
        self.assertTrue(rows)
        self.assertTrue(all(row.score is None and row.rank is None for row in rows))

    def test_banknote_priority(self):
        report = self.engine.generate_report([
            ShoppingCandidate("Canada chartered banknote BCS VF25", asking_price=120, shipping=5)
        ], limit=10)

        rows = [row for row in report.unranked_opportunities if "banknote" in row.item_name]
        self.assertTrue(rows)
        self.assertEqual(rows[0].opportunity_type, OPPORTUNITY_CANADIAN_BANKNOTE)
        self.assertIsNone(rows[0].score)
        self.assertIsNone(rows[0].rank)
        self.assertEqual(rows[0].total_cost, 125)

    def test_budget_analysis(self):
        candidates = [
            ShoppingCandidate("1901 Newfoundland 50 cents VF20", asking_price=85, shipping=5),
            ShoppingCandidate("Canada chartered banknote BCS VF25", asking_price=240, shipping=10),
        ]
        report = self.engine.generate_report(candidates, budgets=[50, 100, 250, 500])

        for budget in (50, 100, 250, 500):
            self.assertIsNone(report.budget_recommendations[budget])
        rows = {row.item_name: row for row in report.unranked_opportunities}
        self.assertEqual(rows["1901 Newfoundland 50 cents VF20"].total_cost, 90)
        self.assertEqual(rows["Canada chartered banknote BCS VF25"].total_cost, 250)
        self.assertTrue(all(row.score is None and row.rank is None for row in rows.values()))

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

        rows = [row for row in report.unranked_opportunities if row.source == "Deal Hunter"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].total_cost, 90)
        self.assertIsNone(rows[0].score)
        self.assertIsNone(rows[0].rank)
        self.assertEqual(rows[0].recommendation, "REVIEW")

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
