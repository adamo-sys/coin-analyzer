"""Tests for v2.5.2 Shopping Explainability."""

import os
import tempfile
import unittest

from acquisition_impact import AcquisitionImpactEngine
from acquisition_workflow import AcquisitionWorkflow
from coin_collection import CoinItem
from focused_collection_intelligence import CandidateItem
from legacy_portfolio_importer import LegacyWantListIntent
from listing_analyzer import ListingAnalyzer, ListingCandidate
from shopping_explainability import (
    ExplainableRecommendationReport,
    RecommendationConfidence,
    RecommendationExplanation,
    ShoppingExplanationEngine,
)
from smart_shopping_assistant import ShoppingCandidate, SmartShoppingAssistant


def make_item(item_id, country, denomination, year, grade, **overrides):
    data = {
        "id": item_id,
        "image_path": "",
        "country": country,
        "denomination": denomination,
        "year": year,
        "grade": grade,
        "notes": "",
        "date_added": "2026-06-19",
    }
    data.update(overrides)
    return CoinItem(**data)


def make_intent(target_coin):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id="explain-want-1",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=150.0,
        why_wanted="Explainability target",
        status="Active",
        priority_score=85,
    )


class TestShoppingExplainability(unittest.TestCase):
    def setUp(self):
        self.items = [
            make_item("1", "Newfoundland", "50 cents", "1900", "F-12"),
            make_item("2", "Canada", "10 cents", "1911", "VF-20"),
            make_item("3", "Canada", "1 cent", "1859", "VG-8"),
        ]
        self.want_list = [make_intent("Newfoundland 50 cents 1904")]
        self.engine = ShoppingExplanationEngine()

    def recommendation_for(self, candidate):
        report = SmartShoppingAssistant(self.items, self.want_list).generate_report(
            [candidate],
            include_want_list_targets=False,
            limit=1,
        )
        return report.recommendations[0]

    def test_recommendation_explanation_structures(self):
        confidence = RecommendationConfidence("High", 91, "Decisive")
        explanation = RecommendationExplanation(
            recommendation="BUY",
            confidence=confidence,
            primary_reasons=["WANT_LIST target"],
            supporting_reasons=["Quality +2"],
            impact_summary="Impact score 70",
        )
        report = ExplainableRecommendationReport("Newfoundland 50 cents 1904", explanation)

        self.assertEqual(report.to_dict()["recommendation"], "BUY")
        self.assertIn("WANT_LIST target", report.format_markdown())

    def test_buy_explanation_generation(self):
        rec = self.recommendation_for(ShoppingCandidate(
            "Newfoundland 50 cents 1904 VF20",
            asking_price=120,
            recommendation_source="Manual",
        ))

        explanation = self.engine.explain_shopping_recommendation(rec)

        self.assertIn(explanation.explanation.recommendation, {"BUY", "STRONG BUY", "NEGOTIATE", "WATCH", "REVIEW"})
        self.assertTrue(any("WANT_LIST" in reason or "impact" in reason.lower() for reason in explanation.explanation.primary_reasons))
        self.assertIn(explanation.explanation.confidence.level, {"High", "Medium", "Low"})
        self.assertIn("Impact score", explanation.explanation.impact_summary)

    def test_pass_explanation_generation(self):
        rec = self.recommendation_for(ShoppingCandidate(
            "Canada 10 cents 1911 VF20",
            asking_price=10,
            recommendation_source="Manual",
        ))

        explanation = self.engine.explain_shopping_recommendation(rec)

        self.assertEqual(rec.recommendation_status, "PASS")
        self.assertEqual(explanation.explanation.recommendation, "PASS")
        self.assertTrue(any("duplicate" in reason.lower() or "already owned" in reason.lower() for reason in explanation.explanation.primary_reasons))

    def test_watch_explanation_generation(self):
        decision = AcquisitionWorkflow(self.items, self.want_list).evaluate(CandidateItem(
            country="Newfoundland",
            denomination="50 cents",
            year="1904",
            grade="VF-20",
            asking_price=0,
        ))

        explanation = self.engine.explain_acquisition_decision(decision, item_name="Newfoundland 50 cents 1904")

        self.assertEqual(explanation.explanation.recommendation, "WATCH")
        self.assertTrue(any("asking price" in reason.lower() or "interesting" in reason.lower() for reason in explanation.explanation.primary_reasons))

    def test_confidence_calculation(self):
        high = self.engine._confidence("BUY", 92, [])
        medium = self.engine._confidence("NEGOTIATE", 88, [])
        low = self.engine._confidence("REVIEW", 91, [])

        self.assertEqual(high.level, "High")
        self.assertEqual(medium.level, "Medium")
        self.assertEqual(low.level, "Low")

    def test_impact_explanations(self):
        candidate = CandidateItem(
            country="Newfoundland",
            denomination="50 cents",
            year="1904",
            grade="VF-20",
            asking_price=120,
        )
        decision = AcquisitionWorkflow(self.items, self.want_list).evaluate(candidate)
        impact = AcquisitionImpactEngine(self.items, self.want_list).evaluate(candidate)

        explanation = self.engine.explain_acquisition_decision(decision, impact, "Newfoundland 50 cents 1904")

        self.assertIn("Impact score", explanation.explanation.impact_summary)
        self.assertTrue(any("Quality" in reason or "Series" in reason or "WANT_LIST" in reason for reason in explanation.explanation.supporting_reasons))

    def test_ownership_explanations(self):
        decision = AcquisitionWorkflow(self.items, self.want_list).evaluate(CandidateItem(
            country="Canada",
            denomination="10 cents",
            year="1911",
            grade="VF-20",
            asking_price=10,
        ))

        explanation = self.engine.explain_acquisition_decision(decision, item_name="Canada 10 cents 1911")

        self.assertEqual(explanation.explanation.recommendation, "PASS")
        self.assertTrue(any("duplicate" in reason.lower() or "owned" in reason.lower() for reason in explanation.explanation.primary_reasons))

    def test_want_list_explanations(self):
        decision = AcquisitionWorkflow(self.items, self.want_list).evaluate(CandidateItem(
            country="Newfoundland",
            denomination="50 cents",
            year="1904",
            grade="VF-20",
            asking_price=120,
        ))

        explanation = self.engine.explain_acquisition_decision(decision, item_name="Newfoundland 50 cents 1904")

        self.assertTrue(any("WANT_LIST" in reason for reason in explanation.explanation.primary_reasons + explanation.explanation.supporting_reasons))

    def test_listing_analyzer_explanation(self):
        result = ListingAnalyzer(self.items, self.want_list).analyze(ListingCandidate(
            title="Newfoundland 50 cents 1904 VF20",
            price=120,
        ))

        explanation = self.engine.explain_listing_analysis(result)

        self.assertEqual(explanation.source, "Listing Analyzer")
        self.assertIn(explanation.explanation.recommendation, {"MUST BUY", "BUY", "NEGOTIATE", "WATCH", "REVIEW"})
        self.assertTrue(explanation.explanation.primary_reasons)

    def test_export_generation(self):
        rec = self.recommendation_for(ShoppingCandidate(
            "Newfoundland 50 cents 1904 VF20",
            asking_price=120,
        ))
        report = self.engine.explain_shopping_recommendation(rec)

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "explanation.csv")
            md_path = os.path.join(temp_dir, "explanation.md")

            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("primary_reasons", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("# Recommendation Explanation", handle.read())

    def test_existing_recommendation_behavior_unchanged(self):
        rec = self.recommendation_for(ShoppingCandidate(
            "Canada 10 cents 1911 VF20",
            asking_price=10,
        ))
        before = rec.to_dict()

        self.engine.explain_shopping_recommendation(rec)
        after = rec.to_dict()

        self.assertEqual(before, after)

    def test_smart_shopping_markdown_includes_why(self):
        assistant = SmartShoppingAssistant(self.items, self.want_list)
        report = assistant.generate_report([
            ShoppingCandidate("Newfoundland 50 cents 1904 VF20", asking_price=120),
        ], include_want_list_targets=False)
        markdown = assistant.format_markdown(report)

        self.assertIn("Why:", markdown)


if __name__ == "__main__":
    unittest.main()
