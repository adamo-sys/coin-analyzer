"""Tests for v2.5.2 Shopping Explainability."""

import csv
import json
import os
import tempfile
import unittest
from dataclasses import replace
from types import SimpleNamespace

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
        self.assertTrue(any("review" in reason.lower() for reason in explanation.explanation.primary_reasons))
        self.assertIn(explanation.explanation.confidence.level, {"High", "Medium", "Low", "Unavailable"})
        self.assertIn("Impact score", explanation.explanation.impact_summary)

    def test_pass_explanation_generation(self):
        rec = self.recommendation_for(ShoppingCandidate(
            "Canada 10 cents 1911 VF20",
            asking_price=10,
            recommendation_source="Manual",
        ))

        explanation = self.engine.explain_shopping_recommendation(rec)

        self.assertEqual(rec.recommendation_status, "REVIEW")
        self.assertEqual(explanation.explanation.recommendation, "REVIEW")
        self.assertIn("Ownership unresolved", explanation.format_markdown())

    def test_watch_explanation_generation(self):
        decision = AcquisitionWorkflow(self.items, self.want_list).evaluate(CandidateItem(
            country="Newfoundland",
            denomination="50 cents",
            year="1904",
            grade="VF-20",
            asking_price=0,
        ))

        explanation = self.engine.explain_acquisition_decision(decision, item_name="Newfoundland 50 cents 1904")

        self.assertEqual(explanation.explanation.recommendation, "REVIEW")
        self.assertIn("Missing asking price", explanation.explanation.warnings)

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
        self.assertIn("quality unavailable", explanation.explanation.impact_summary)

    def test_ownership_explanations(self):
        decision = AcquisitionWorkflow(self.items, self.want_list).evaluate(CandidateItem(
            country="Canada",
            denomination="10 cents",
            year="1911",
            grade="VF-20",
            asking_price=10,
        ))

        explanation = self.engine.explain_acquisition_decision(decision, item_name="Canada 10 cents 1911")

        self.assertEqual(explanation.explanation.recommendation, "REVIEW")
        self.assertIn("Ownership unresolved", explanation.format_markdown())

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

    def test_unranked_smart_shopping_explanation_includes_review_reason(self):
        assistant = SmartShoppingAssistant(self.items, self.want_list)
        report = assistant.generate_report([
            ShoppingCandidate("Newfoundland 50 cents 1904 VF20", asking_price=120),
        ], include_want_list_targets=False)
        markdown = self.engine.explain_shopping_recommendation(report.recommendations[0]).format_markdown()

        self.assertIn("Review required", markdown)


class TestContainedShoppingExplainability(unittest.TestCase):
    """Catch coercion, negative certainty, and prose bypass at the final boundary."""

    def setUp(self):
        self.engine = ShoppingExplanationEngine()
        self.items = [make_item("owned", "Canada", "10 cents", "1911", "VF-20")]

    def shopping_row(self, title="Canada 10 cents 1911 MS65", items=None):
        return SmartShoppingAssistant(self.items if items is None else items).generate_report(
            [ShoppingCandidate(title, asking_price=25)], include_want_list_targets=False,
        ).recommendations[0]

    def stale_positive_row(self):
        row = self.shopping_row()
        row.recommendation_status = "BUY"
        row.opportunity_score, row.rank = 59, 1
        row.impact_score, row.quality_delta, row.series_delta = 40, 2, 3
        row.max_rational_price = 80
        row.reasons = ["Fills a collection gap", "Best Next Purchase #1"]
        row.acquisition_decision = replace(
            row.acquisition_decision, recommendation="BUY", collection_intelligence_status="COLLECTION_GAP",
            owned_current_match_summary="Synthetic supported boundary advice", upgrade_status="NOT_UPGRADE",
            max_rational_price=80, confidence_score=90, priority_reasons=[], intelligence_result=None,
        )
        row.impact_report = replace(
            row.impact_report, acquisition_decision=row.acquisition_decision,
            collection_impact="COLLECTION_GAP", impact_score=40, quality_delta=2, completion_delta=3,
            upgrade_impact="NO_UPGRADE_IMPACT", want_list_impact="NO_WANT_LIST_IMPACT",
            recommendation_reasoning=["Fills a collection gap", "Replace existing"],
        )
        return row

    def assert_stale_consequences_contained(self, row):
        report = self.engine.explain_shopping_recommendation(row)
        self.assert_contained(report)
        payload = json.loads(json.dumps(report.to_dict()))
        for name in ("max_rational_price", "composite_score", "rank", "impact_score", "quality_delta", "completion_delta", "collection_impact"):
            with self.subTest(field=name):
                self.assertIsNone(payload["details"][name])
        self.assertIn("Recommendation: REVIEW", report.format_markdown())
        self.assertIn("quality unavailable", report.explanation.impact_summary)
        self.assertNotIn("Best Next Purchase", report.format_markdown())
        self.assertNotIn("Asking price is at or below", report.format_markdown())
        self.assertNotIn("Positive acquisition impact", report.format_markdown())
        self.assertEqual(payload["details"]["total_cost"], 25)

    def test_authoritative_ownership_summary_overrides_stale_buy_gap_and_price(self):
        for status in ("BUY", "PASS", "WATCH", "NEGOTIATE"):
            with self.subTest(status=status):
                row = self.stale_positive_row()
                row.recommendation_status = status
                row.acquisition_decision.owned_current_match_summary = "UNRESOLVED: owned issue equivalence unavailable"
                self.assert_stale_consequences_contained(row)

    def test_nested_real_review_overrides_stale_buy_composite_rank_and_deltas(self):
        row = self.stale_positive_row()
        row.impact_report.acquisition_decision = AcquisitionWorkflow([]).evaluate(CandidateItem(asking_price=25))
        self.assert_stale_consequences_contained(row)

    def test_collection_impact_structured_unavailable_contains_direct_entry(self):
        row = self.stale_positive_row()
        row.impact_report = replace(row.impact_report, collection_impact="UNAVAILABLE: missing evidence")
        self.assert_stale_consequences_contained(row)

    def test_upgrade_impact_structured_unavailable_contains_direct_entry(self):
        row = self.stale_positive_row()
        row.impact_report = replace(row.impact_report, upgrade_impact="UNAVAILABLE: missing evidence")
        self.assert_stale_consequences_contained(row)

    def test_want_list_impact_structured_unavailable_contains_direct_entry(self):
        row = self.stale_positive_row()
        row.impact_report = replace(row.impact_report, want_list_impact="UNAVAILABLE: missing evidence")
        self.assert_stale_consequences_contained(row)

    def test_structured_unavailable_case_and_whitespace_contains_direct_entry(self):
        for value in ("UNAVAILABLE", " unavailable ", " unavailable: missing evidence ",
                      "Unavailable: Missing Evidence"):
            with self.subTest(value=value):
                row = self.stale_positive_row()
                row.impact_report = replace(row.impact_report, collection_impact=value)
                self.assert_stale_consequences_contained(row)

    def test_unavailable_in_ordinary_prose_is_not_a_structured_sentinel(self):
        for value in ("availability unavailable later", "this note discusses unavailable inventory"):
            with self.subTest(value=value):
                row = self.stale_positive_row()
                row.impact_report = replace(row.impact_report, collection_impact=value)
                self.assertFalse(self.engine._unresolved(row, row.acquisition_decision, row.impact_report))

    def test_supported_positive_direct_entry_preserves_advice_and_price_context(self):
        report = self.engine.explain_shopping_recommendation(self.stale_positive_row())
        self.assertEqual(report.explanation.recommendation, "BUY")
        for field, expected in (("composite_score", 59), ("rank", 1), ("max_rational_price", 80),
                                ("impact_score", 40), ("quality_delta", 2), ("completion_delta", 3),
                                ("total_cost", 25)):
            with self.subTest(field=field):
                self.assertEqual(report.details[field], expected)
        for reason in ("Fills a collection gap", "Positive acquisition impact",
                       "Asking price is at or below max rational price"):
            self.assertIn(reason, report.explanation.primary_reasons)

    def test_nested_review_alone_dominates_and_preserves_independent_context(self):
        row = self.stale_positive_row()
        row.impact_report.acquisition_decision = replace(row.acquisition_decision, recommendation="REVIEW")
        row.warnings = ["Damage warning", "Lot warning", "Currency warning"]
        row.market_context = "Synthetic market observation: 20 CAD"
        row.acquisition_decision.want_list_status = "ON_WANT_LIST"
        self.assert_stale_consequences_contained(row)
        text = self.engine.explain_shopping_recommendation(row).format_markdown()
        for value in row.warnings + [row.market_context, "WANT_LIST"]:
            self.assertIn(value, text)

    def test_each_required_unavailable_consequence_overrides_stale_positive_fields(self):
        for layer, field in (("acquisition_decision", "max_rational_price"),
                             ("impact_report", "impact_score"), ("impact_report", "quality_delta"),
                             ("impact_report", "completion_delta"), ("impact_report", "upgrade_impact"),
                             ("impact_report", "want_list_impact")):
            with self.subTest(layer=layer, field=field):
                row = self.stale_positive_row()
                setattr(getattr(row, layer), field, None)
                self.assert_stale_consequences_contained(row)

    def test_normalized_review_at_each_layer_contains_stale_summary_and_values(self):
        for layer in ("outer", "direct", "nested"):
            with self.subTest(layer=layer):
                row = self.stale_positive_row()
                if layer == "outer":
                    row.recommendation_status = " REVIEW "
                elif layer == "direct":
                    row.acquisition_decision = replace(row.acquisition_decision, recommendation=" REVIEW ")
                else:
                    row.impact_report.acquisition_decision = replace(row.acquisition_decision, recommendation=" REVIEW ")
                self.assert_stale_consequences_contained(row)

    def assert_contained(self, report):
        self.assertEqual(report.explanation.recommendation, "REVIEW")
        text = report.format_markdown().lower()
        for phrase in (
            "not owned", "no current owned match", "new to collection", "collection gap",
            "not a duplicate", "no duplicates", "duplicate-free", "safe from duplication",
            "not_an_upgrade", "not an upgrade", "upgrade available", "better-grade upgrade",
            "keep existing", "replace existing", "no impact", "no collection benefit",
            "safe buy", "top pick", "#1", "$0", "quality 0", "completion 0%",
        ):
            self.assertNotIn(phrase, text)
        for phrase in ("ownership unresolved", "duplicate unresolved", "upgrade unresolved"):
            self.assertIn(phrase, text)

    def test_review_and_unresolved_states_across_entry_points(self):
        candidate = CandidateItem(country="Canada", denomination="10 cents", year="1911", grade="MS-65", asking_price=25)
        decision = AcquisitionWorkflow(self.items).evaluate(candidate)
        impact = AcquisitionImpactEngine(self.items).evaluate(candidate)
        listing = ListingAnalyzer(self.items).analyze(ListingCandidate("Canada 10 cents 1911 MS65", price=25))
        reports = [
            self.engine.explain_shopping_recommendation(self.shopping_row()),
            self.engine.explain_listing_analysis(listing),
            self.engine.explain_acquisition_decision(decision, impact),
        ]
        for report in reports:
            with self.subTest(source=report.source):
                self.assert_contained(report)

    def test_optional_numerics_are_null_and_explicitly_unavailable(self):
        report = self.engine.explain_shopping_recommendation(self.shopping_row())
        data = json.loads(json.dumps(report.to_dict()))
        for field in ("max_rational_price", "priority", "fit_score", "composite_score", "impact_score", "quality_delta", "completion_delta", "rank"):
            with self.subTest(field=field):
                self.assertIn(field, data["details"])
                self.assertIsNone(data["details"][field])
                self.assertIn(f"{field}: unavailable", report.format_markdown())
        self.assertIsNone(data["confidence"]["score"])
        self.assertIn("quality unavailable", report.explanation.impact_summary)
        self.assertIn("series completion unavailable", report.explanation.impact_summary)

    def test_listing_numerics_remain_null(self):
        result = ListingAnalyzer(self.items).analyze(ListingCandidate("Canada 10 cents 1911", price=25))
        data = self.engine.explain_listing_analysis(result).to_dict()
        for key in ("priority", "impact_score", "quality_delta", "completion_delta", "max_rational_price"):
            self.assertIsNone(data["details"][key])

    def test_unavailable_collection_impact_preserves_json_null(self):
        report = self.engine.explain_shopping_recommendation(self.shopping_row())
        data = json.loads(json.dumps(report.to_dict()))
        self.assertIsNone(data["details"]["collection_impact"])
        self.assertIn("collection impact unresolved", report.explanation.impact_summary)

    def test_acquisition_without_impact_does_not_imply_no_benefit(self):
        decision = AcquisitionWorkflow([]).evaluate(CandidateItem(asking_price=12))
        report = self.engine.explain_acquisition_decision(decision)
        self.assert_contained(report)
        self.assertIn("unavailable", report.explanation.impact_summary.lower())

    def test_equal_grade_does_not_supply_duplicate_certainty(self):
        self.assert_contained(self.engine.explain_shopping_recommendation(self.shopping_row("Canada 10 cents 1911 VF20")))

    def test_missing_holding_year_does_not_supply_gap(self):
        items = [make_item("unknown-year", "Canada", "10 cents", "", "VF-20")]
        self.assert_contained(self.engine.explain_shopping_recommendation(self.shopping_row(items=items)))

    def test_incomplete_candidate_empty_collection_does_not_supply_newness(self):
        self.assert_contained(self.engine.explain_shopping_recommendation(self.shopping_row("Canada", items=[])))

    def test_no_raw_intelligence_or_reason_bypass(self):
        row = self.shopping_row("Canada 10 cents 1911 MS65 upgrade")
        poison = ["Upgrade available", "Not a duplicate", "Fills a collection gap", "Best Next Purchase #1", "No current owned match"]
        row.reasons = poison
        row.acquisition_decision.priority_reasons = poison
        row.acquisition_decision.owned_current_match_summary = "No current owned match"
        row.impact_report.recommendation_reasoning = poison
        row.acquisition_decision.intelligence_result = SimpleNamespace(
            match_status="BETTER_GRADE_UPGRADE", recommendation="BUY", fit_score=99,
            type_series="collection gap", variety="upgrade", owned_matches=[self.items[0]],
        )
        self.assert_contained(self.engine.explain_shopping_recommendation(row))

    def test_contained_acquisition_overrides_stale_outer_recommendation(self):
        for status in ("BUY", "PASS", "WATCH", "NEGOTIATE"):
            row = self.shopping_row()
            row.recommendation_status = status
            with self.subTest(status=status):
                self.assert_contained(self.engine.explain_shopping_recommendation(row))

    def test_listing_explicit_unresolved_states_override_stale_status(self):
        listing = ListingAnalyzer(self.items).analyze(ListingCandidate("Canada 10 cents 1911", price=25))
        listing.recommendation = "PASS"
        listing.acquisition_decision = None
        listing.acquisition_impact_report = None
        self.assert_contained(self.engine.explain_listing_analysis(listing))

    def test_all_unresolved_has_no_best_or_input_order_rank(self):
        assistant = SmartShoppingAssistant(self.items)
        candidates = [ShoppingCandidate("Canada 10 cents 1911 MS65", asking_price=25), ShoppingCandidate("Canada", asking_price=15)]
        for inputs in (candidates, list(reversed(candidates))):
            upstream = assistant.generate_report(inputs, include_want_list_targets=False)
            self.assertIsNone(upstream.best_next_purchase)
            for row in upstream.recommendations:
                report = self.engine.explain_shopping_recommendation(row)
                self.assert_contained(report)
                self.assertIn("No supported best purchase can be determined from current evidence", report.format_markdown())
                self.assertNotIn("no good purchases", report.format_markdown().lower())

    def test_explicit_interest_survives_without_advice(self):
        candidate = CandidateItem(country="Newfoundland", denomination="50 cents", year="1904", grade="VF-20", asking_price=120)
        decision = AcquisitionWorkflow([], [make_intent("Newfoundland 50 cents 1904")]).evaluate(candidate)
        report = self.engine.explain_acquisition_decision(decision)
        self.assert_contained(report)
        self.assertIn("WANT_LIST", report.format_markdown())
        self.assertIn("High-Priority Series: Newfoundland", report.format_markdown())

    def test_independent_warnings_and_listing_metadata_survive(self):
        listing = ListingCandidate("Canada 10 cents 1911 damaged lot USD upgrade", price=25, shipping=3,
                                   url="https://example.com/synthetic", seller="Synthetic seller", source="Manual",
                                   description="Synthetic descriptive text")
        result = ListingAnalyzer(self.items).analyze(listing)
        result.warnings.extend(["Damage warning", "Lot warning", "Currency warning", "Price warning"])
        report = self.engine.explain_listing_analysis(result)
        self.assert_contained(report)
        for warning in result.warnings:
            self.assertIn(warning, report.explanation.warnings)
        data = report.to_dict()["details"]
        for key, expected in (("asking_price", 25), ("shipping", 3), ("total_cost", 28), ("url", listing.url), ("seller", listing.seller), ("description", listing.description)):
            self.assertEqual(data[key], expected)
            self.assertIn(str(expected), report.format_markdown())

    def test_market_context_survives(self):
        row = self.shopping_row()
        row.market_context = "Observed synthetic market range: 20 to 40 CAD"
        report = self.engine.explain_shopping_recommendation(row)
        self.assert_contained(report)
        self.assertIn(row.market_context, report.format_markdown())

    def test_csv_and_markdown_exports_preserve_unavailable(self):
        report = self.engine.explain_shopping_recommendation(self.shopping_row())
        with tempfile.TemporaryDirectory() as directory:
            csv_path = os.path.join(directory, "synthetic.csv")
            md_path = os.path.join(directory, "synthetic.md")
            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            with open(csv_path, encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["confidence_score"], "unavailable")
            for key in ("max_rational_price", "priority", "fit_score", "composite_score", "impact_score", "quality_delta", "completion_delta", "rank"):
                self.assertEqual(row[key], "unavailable")
            with open(md_path, encoding="utf-8") as handle:
                text = handle.read()
            self.assertIn("quality unavailable", text)
            self.assertNotIn("completion 0%", text)

    def test_missing_optional_fields_do_not_default_to_zero(self):
        row = SimpleNamespace(recommendation_status="REVIEW", item_name="Synthetic", total_cost=None)
        report = self.engine.explain_shopping_recommendation(row)
        self.assert_contained(report)
        self.assertIsNone(report.to_dict()["details"]["max_rational_price"])
        self.assertIn("unavailable", report.format_markdown())

    def test_unavailable_composite_cannot_publish_stale_rank(self):
        row = SimpleNamespace(recommendation_status="BUY", item_name="Synthetic", total_cost=25,
                              opportunity_score=None, rank=1, reasons=["Top pick #1"], warnings=[])
        report = self.engine.explain_shopping_recommendation(row)
        self.assert_contained(report)
        self.assertIsNone(report.to_dict()["details"]["rank"])

    def test_optional_numerics_in_other_statuses_never_raise_or_become_zero(self):
        for status in ("BUY", "PASS", "WATCH", "NEGOTIATE"):
            with self.subTest(status=status):
                decision = SimpleNamespace(recommendation=status, asking_price=None, max_rational_price=None,
                                           confidence_score=None, priority_reasons=[], warning_flags=[])
                impact = SimpleNamespace(impact_score=None, quality_delta=None, completion_delta=None)
                report = self.engine.explain_acquisition_decision(decision, impact)
                self.assertIn("quality unavailable", report.explanation.impact_summary)
                self.assertIn("series completion unavailable", report.explanation.impact_summary)
                self.assertIsNone(report.to_dict()["details"]["max_rational_price"])
                self.assertNotIn("Max rational price is zero", report.format_markdown())

    def test_each_explicit_unresolved_state_remains_unresolved_in_json(self):
        for field in ("ownership_status", "duplicate_status", "upgrade_status", "collection_impact"):
            with self.subTest(field=field):
                row = SimpleNamespace(recommendation_status="BUY", item_name="Synthetic", reasons=[], warnings=[])
                setattr(row, field, "UNRESOLVED")
                report = self.engine.explain_shopping_recommendation(row)
                self.assert_contained(report)
                self.assertEqual(report.to_dict()["details"][field], None if field == "collection_impact" else "UNRESOLVED")

    def test_supported_actual_zero_and_decisive_status_are_preserved(self):
        # A boundary fixture with supported legacy outputs; no SAME_ISSUE activation.
        decision = SimpleNamespace(recommendation="PASS", collection_intelligence_status="SAME_GRADE_DUPLICATE",
                                   owned_current_match_summary="Supported owned match", want_list_status="NOT_ON_WANT_LIST",
                                   upgrade_status="NOT_AN_UPGRADE", asking_price=10, max_rational_price=0,
                                   confidence_score=90, priority_reasons=[], warning_flags=[])
        impact = SimpleNamespace(impact_score=0, collection_impact="LOW", quality_delta=0, completion_delta=0,
                                 upgrade_impact="No supported upgrade", recommendation_reasoning=[])
        report = self.engine.explain_acquisition_decision(decision, impact)
        self.assertEqual(report.explanation.recommendation, "PASS")
        self.assertEqual(report.to_dict()["details"]["max_rational_price"], 0)
        self.assertIn("quality 0", report.explanation.impact_summary)
        self.assertIn("series completion 0%", report.explanation.impact_summary)
        self.assertIn("Same-grade duplicate", report.explanation.primary_reasons)


if __name__ == "__main__":
    unittest.main()
