"""Tests for Smart Shopping Assistant."""

import os
import csv
import json
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

from openpyxl import Workbook

from coin_collection import CoinItem
from acquisition_workflow import AcquisitionWorkflow
from acquisition_impact import AcquisitionImpactEngine
from collection_dashboard import CollectionDashboard
from focused_collection_intelligence import CandidateItem
from focused_collection_intelligence import MatchStatus
from legacy_portfolio_importer import LegacyWantListIntent
from listing_analyzer import ListingCandidate
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord
from session_context import SessionContext
from smart_shopping_assistant import (
    ShoppingCandidate,
    ShoppingRecommendation,
    ShoppingRecommendationReport,
    SmartShoppingAssistant,
)


WANT_HEADERS = [
    "Target Coin",
    "Priority",
    "Target Grade",
    "Budget",
    "Why Wanted",
    "Status",
]


def make_item(item_id, country, denomination, year, grade, **overrides):
    data = {
        "id": item_id,
        "image_path": "",
        "country": country,
        "denomination": denomination,
        "year": year,
        "grade": grade,
        "notes": "",
        "date_added": "2026-06-18",
    }
    data.update(overrides)
    return CoinItem(**data)


def make_intent(target_coin, priority_score=90):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id=f"want_{target_coin}",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=150.0,
        why_wanted="Smart shopping target",
        status="Active",
        priority_score=priority_score,
    )


def make_workbook(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "WANT_LIST"
    ws.append(WANT_HEADERS)
    ws.append(["Newfoundland 50 cents 1901", "High", "VF-20", 150, "Smart target", "Active"])
    wb.save(path)


class TestSmartShoppingAssistant(unittest.TestCase):
    def setUp(self):
        self.items = [
            make_item("1", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("2", "Newfoundland", "50 cents", "1902", "VF-20"),
            make_item("3", "Canada", "10 cents", "1911", "VF-20"),
        ]
        self.intents = [make_intent("Newfoundland 50 cents 1901", 95)]
        self.market = MarketAwarenessEngine(observations=[
            ObservedPriceRecord("1901 Newfoundland 50 cents", "Newfoundland", "50 cents", "1901", observed_price=85),
            ObservedPriceRecord("1901 Newfoundland 50 cents", "Newfoundland", "50 cents", "1901", observed_price=95),
            ObservedPriceRecord("1901 Newfoundland 50 cents", "Newfoundland", "50 cents", "1901", observed_price=105),
        ])

    def test_unresolved_candidates_are_unranked(self):
        candidates = [
            ShoppingCandidate(
                "1975 Argentina 1 cent VF20",
                asking_price=1,
                candidate=CandidateItem("Argentina", "1 cent", "1975", grade="VF-20", asking_price=1),
            ),
            ShoppingCandidate(
                "1901 Newfoundland 50 cents VF20",
                asking_price=90,
                candidate=CandidateItem("Newfoundland", "50 cents", "1901", grade="VF-20", asking_price=90),
            ),
        ]

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report(candidates, include_want_list_targets=False)

        self.assertIsInstance(report, ShoppingRecommendationReport)
        self.assertIsNone(report.best_next_purchase)
        self.assertTrue(all(row.opportunity_score is None and row.rank is None for row in report.recommendations))

    def test_want_list_interest_does_not_authorize_strong_buy(self):
        candidate = ShoppingCandidate(
            "1901 Newfoundland 50 cents VF20",
            asking_price=90,
            candidate=CandidateItem("Newfoundland", "50 cents", "1901", grade="VF-20", asking_price=90),
        )

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.recommendations[0].recommendation_status, "REVIEW")
        self.assertIn("Explicit WANT_LIST Target", report.recommendations[0].reasons)
        self.assertEqual(report.recommendations[0].market_context, "Within recent observed range")

    def test_triplet_gap_does_not_authorize_buy(self):
        candidate = ShoppingCandidate(
            "1912 Canada 10 cents VF20",
            asking_price=45,
            candidate=CandidateItem("Canada", "10 cents", "1912", grade="VF-20", asking_price=45),
        )

        report = SmartShoppingAssistant(self.items, [], MarketAwarenessEngine()).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.recommendations[0].recommendation_status, "REVIEW")
        self.assertIsNone(report.recommendations[0].impact_score)

    def test_above_observed_range_remains_review(self):
        candidate = ShoppingCandidate(
            "1901 Newfoundland 50 cents VF20",
            asking_price=125,
            candidate=CandidateItem("Newfoundland", "50 cents", "1901", grade="VF-20", asking_price=125),
        )

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.recommendations[0].recommendation_status, "REVIEW")
        self.assertIn("Above recent observed range", report.recommendations[0].reasons)

    def test_missing_price_warning_remains_review(self):
        candidate = ShoppingCandidate(
            "1901 Newfoundland 50 cents VF20",
            candidate=CandidateItem("Newfoundland", "50 cents", "1901", grade="VF-20"),
        )

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.recommendations[0].recommendation_status, "REVIEW")
        self.assertIn("Missing asking price", report.recommendations[0].warnings)

    def test_triplet_duplicate_remains_review(self):
        candidate = ShoppingCandidate(
            "1900 Newfoundland 50 cents VF20",
            asking_price=40,
            candidate=CandidateItem("Newfoundland", "50 cents", "1900", grade="VF-20", asking_price=40),
        )

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.recommendations[0].recommendation_status, "REVIEW")

    def test_review_path_for_ambiguous_candidate(self):
        items = [make_item("lc1", "Canada", "1 cent", "1859", "VF-20")]
        candidate = ShoppingCandidate(
            "1859 Canada Large Cent Wide 9",
            asking_price=50,
            candidate=CandidateItem("Canada", "1 cent", "1859", variety="Wide 9", grade="VF-20", asking_price=50),
        )

        report = SmartShoppingAssistant(items, [], MarketAwarenessEngine()).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.recommendations[0].recommendation_status, "REVIEW")

    def test_want_list_prioritization_from_intents(self):
        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report([], include_want_list_targets=True)

        self.assertIsNotNone(report.highest_priority_want_list_target)
        self.assertIn("Newfoundland 50 cents 1901", report.highest_priority_want_list_target.item_name)

    def test_triplet_upgrade_is_not_prioritized(self):
        candidate = ShoppingCandidate(
            "1911 Canada 10 cents EF40",
            asking_price=70,
            candidate=CandidateItem("Canada", "10 cents", "1911", grade="EF-40", certifier="PCGS", asking_price=70),
        )

        report = SmartShoppingAssistant(self.items, [], MarketAwarenessEngine()).generate_report([candidate], include_want_list_targets=False)

        self.assertNotIn("Upgrade opportunity", report.recommendations[0].reasons)
        self.assertIsNone(report.recommendations[0].opportunity_score)

    def test_market_awareness_integration(self):
        candidate = ShoppingCandidate(
            "1901 Newfoundland 50 cents VF20",
            asking_price=80,
            candidate=CandidateItem("Newfoundland", "50 cents", "1901", grade="VF-20", asking_price=80),
        )

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.recommendations[0].market_context, "Below recent observed range")
        self.assertIn("Below recent observed range", report.recommendations[0].reasons)

    def test_dashboard_integration(self):
        candidate = ShoppingCandidate(
            "1901 Newfoundland 50 cents VF20",
            asking_price=90,
            candidate=CandidateItem("Newfoundland", "50 cents", "1901", grade="VF-20", asking_price=90),
        )

        data = CollectionDashboard(
            self.items,
            self.intents,
            market_awareness_engine=self.market,
            shopping_candidates=[candidate],
        ).generate_dashboard()

        self.assertIsNotNone(data.shopping_report)
        self.assertEqual(data.shopping_report.recommendations[0].item_name, "1901 Newfoundland 50 cents VF20")

    def test_export_support(self):
        candidate = ShoppingCandidate(
            "1901 Newfoundland 50 cents VF20",
            asking_price=90,
            candidate=CandidateItem("Newfoundland", "50 cents", "1901", grade="VF-20", asking_price=90),
        )
        assistant = SmartShoppingAssistant(self.items, self.intents, self.market)
        report = assistant.generate_report([candidate], include_want_list_targets=False)
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "shopping.csv")
            md_path = os.path.join(temp_dir, "shopping.md")

            self.assertTrue(assistant.export_csv(csv_path, report))
            self.assertTrue(assistant.export_markdown(md_path, report))

            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("recommendation_status", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("# Smart Shopping Assistant", handle.read())

    def test_shared_session_context_integration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook_path = os.path.join(temp_dir, "want.xlsx")
            make_workbook(workbook_path)
            context = SessionContext()
            context.load_want_list_context(workbook_path, self.items)

            report = SmartShoppingAssistant(
                self.items,
                context.get_want_list_intents(),
                self.market,
            ).generate_report([], include_want_list_targets=True)

        self.assertIsNone(report.best_next_purchase)
        self.assertEqual(report.recommendations[0].want_list_status, "ON_WANT_LIST")

    def test_listing_candidate_conversion(self):
        listing = ListingCandidate("1901 Newfoundland 50 cents VF20", price=90, shipping=5, source="Dealer")
        candidate = ShoppingCandidate.from_listing(listing)

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.recommendations[0].source, "Listing Analyzer")
        self.assertEqual(report.recommendations[0].total_cost, 95.0)

    def test_photo_vault_reference_ids_are_preserved(self):
        candidate = ShoppingCandidate(
            "1901 Newfoundland 50 cents VF20",
            asking_price=90,
            candidate=CandidateItem("Newfoundland", "50 cents", "1901", grade="VF-20", asking_price=90),
            photo_reference_ids=["photo_listing_1", "photo_reference_1"],
        )

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.recommendations[0].photo_reference_ids, ["photo_listing_1", "photo_reference_1"])

    # ---------------------------------------------------------------------------
    # Phase 3: Connected Data integration tests
    # ---------------------------------------------------------------------------

    def test_generate_report_without_connected_data(self):
        """Existing call without connected_data_engine works unchanged."""
        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report(
            [], include_want_list_targets=True
        )
        self.assertIsInstance(report, ShoppingRecommendationReport)
        self.assertIsNone(report.connected_data)
        self.assertIsNone(report.best_next_purchase)

    def test_generate_report_with_connected_data(self):
        """Connected data engine populates metadata on report."""
        from connected_data import ConnectedDataEngine, ConnectedContext
        from unittest.mock import MagicMock

        watchlist_item = MagicMock()
        watchlist_item.id = "wl1"
        watchlist_item.keyword = "Newfoundland"
        watchlist_item.name = None

        shopping = MagicMock()
        shopping.id = "s1"
        shopping.title = "1901 Newfoundland 50 cents"
        shopping.country = "Newfoundland"
        shopping.denomination = "50 cents"
        shopping.year = "1901"

        context = ConnectedContext(
            collection_items=self.items,
            watchlists=[watchlist_item],
            shopping_candidates=[shopping],
            want_list_intents=self.intents,
        )
        engine = ConnectedDataEngine(context)

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report(
            [], include_want_list_targets=True, connected_data_engine=engine
        )
        self.assertIsNotNone(report.connected_data)
        self.assertIn("watchlist_matches", report.connected_data)
        self.assertIn("total_recommendations", report.connected_data)
        self.assertIn("match_rate", report.connected_data)

    def test_generate_report_with_connected_data_engine_failure(self):
        """Connected data engine failure handled gracefully; report is still valid."""
        from unittest.mock import MagicMock

        broken_engine = MagicMock()
        broken_engine.connect.side_effect = RuntimeError("Engine failed")

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report(
            [], include_want_list_targets=True, connected_data_engine=broken_engine
        )
        self.assertIsInstance(report, ShoppingRecommendationReport)
        self.assertIsNone(report.connected_data)
        self.assertIsNone(report.best_next_purchase)

    def test_shop_report_connected_data_field_serializes(self):
        """ShoppingRecommendationReport with connected_data serializes correctly."""
        report = ShoppingRecommendationReport(
            recommendations=[],
            connected_data={"watchlist_matches": 2, "total_recommendations": 5, "match_rate": 0.4},
        )
        d = report.to_dict()
        self.assertEqual(d["connected_data"]["watchlist_matches"], 2)
        self.assertEqual(d["connected_data"]["match_rate"], 0.4)


class TestShoppingContainment(unittest.TestCase):
    """Catch partial scoring, evidence bypass, and input-order designations."""

    def setUp(self):
        self.item = make_item("1", "Canada", "10 cents", "1911", "VF-20")
        self.candidate = ShoppingCandidate(
            "1911 Canada 10 cents EF40", asking_price=10,
            candidate=CandidateItem("Canada", "10 cents", "1911", grade="EF-40"),
        )
        self.assistant = SmartShoppingAssistant([self.item])

    def report(self, candidates=None, assistant=None):
        return (assistant or self.assistant).generate_report(
            candidates if candidates is not None else [self.candidate],
            include_want_list_targets=False,
        )

    def boundary_advice(self):
        # Numeric boundary fixtures exercise legacy arithmetic without activating
        # canonical equivalence in any production engine or candidate schema.
        decision = AcquisitionWorkflow([]).evaluate(self.candidate.candidate)
        decision = replace(
            decision, collection_intelligence_status="COLLECTION_GAP",
            owned_current_match_summary="Synthetic supported boundary advice",
            recommendation="BUY", upgrade_status="NOT_UPGRADE", max_rational_price=80,
            intelligence_result=None, warning_flags=[], priority_reasons=[],
        )
        impact = AcquisitionImpactEngine([]).evaluate(self.candidate.candidate)
        impact = replace(
            impact, impact_score=40, quality_delta=2, completion_delta=3,
            collection_impact="COLLECTION_GAP", upgrade_impact="NO_UPGRADE_IMPACT",
            want_list_impact="NO_WANT_LIST_IMPACT", acquisition_decision=decision,
            recommendation_reasoning=[],
        )
        return decision, impact

    def test_public_impact_without_acquisition_blocks_each_unavailable_component(self):
        from smart_shopping_assistant import ShoppingRecommendation

        _, impact = self.boundary_advice()
        for field in ("impact_score", "quality_delta", "completion_delta", "collection_impact", "upgrade_impact", "want_list_impact"):
            with self.subTest(field=field):
                row = ShoppingRecommendation(
                    1, "Synthetic boundary", "BUY", 90, 90, 2, 3,
                    "ON_WANT_LIST", "Independent market context", 100, 12, "Manual",
                    warnings=["Independent warning"],
                    impact_report=replace(impact, acquisition_decision=None, **{field: None}),
                )
                report = ShoppingRecommendationReport([row], best_next_purchase=row)
                payload = report.to_dict()
                self.assertEqual(row.recommendation_status, "REVIEW")
                for key in ("rank", "opportunity_score", "impact_score", "max_rational_price"):
                    self.assertIsNone(payload["recommendations"][0][key])
                self.assertIsNone(report.best_next_purchase)
                self.assertEqual(row.total_cost, 12)
                self.assertEqual(row.market_context, "Independent market context")
                self.assertIn("Independent warning", row.warnings)

    def test_structured_intelligence_unavailable_prefixes_block_advice(self):
        decision, impact = self.boundary_advice()
        intelligence = AcquisitionWorkflow([]).evaluate(self.candidate.candidate).intelligence_result
        intelligence = replace(intelligence, match_status=MatchStatus.COLLECTION_GAP,
                               recommendation="BUY", grade_comparison="Supported", collection_impact="Supported")
        for field in ("grade_comparison", "collection_impact"):
            for sentinel in ("UNAVAILABLE", " unavailable ", "UNAVAILABLE: missing evidence", " unavailable: missing evidence "):
                with self.subTest(field=field, sentinel=sentinel):
                    nested = replace(intelligence, **{field: sentinel})
                    attached = replace(decision, intelligence_result=nested)
                    self.assertIsNone(self.assistant._opportunity_score(
                        self.candidate, attached, impact, "BUY"))
            prose = replace(intelligence, **{field: "Some unrelated evidence is unavailable today"})
            self.assertIsNotNone(self.assistant._opportunity_score(
                self.candidate, replace(decision, intelligence_result=prose), impact, "BUY"))


    def test_review_with_numeric_legacy_components_still_has_no_composite(self):
        decision, impact = self.boundary_advice()
        decision = replace(decision, recommendation="REVIEW")
        self.assertIsNone(self.assistant._opportunity_score(self.candidate, decision, impact, "REVIEW"))

    def test_review_candidate_has_no_numeric_rank(self):
        row = self.report().recommendations[0]
        self.assertEqual(row.recommendation_status, "REVIEW")
        self.assertIsNone(row.opportunity_score)
        self.assertIsNone(row.rank)

    def test_review_candidate_is_not_best_next_purchase(self):
        self.assertIsNone(self.report().best_next_purchase)

    def test_all_review_candidates_have_no_best_or_impact_fallback(self):
        report = self.report([self.candidate, ShoppingCandidate("Unidentified coin", asking_price=1)])
        self.assertEqual(len(report.recommendations), 2)
        self.assertIsNone(report.best_next_purchase)
        self.assertIsNone(report.highest_impact_candidate)
        self.assertTrue(all(row.rank is None and row.opportunity_score is None for row in report.recommendations))

    def test_duplicate_cap_removal_cannot_improve_an_unresolved_score(self):
        decision, impact = self.boundary_advice()
        duplicate = replace(decision, collection_intelligence_status="SAME_GRADE_DUPLICATE", recommendation="PASS")
        self.assertEqual(self.assistant._opportunity_score(self.candidate, duplicate, impact, "PASS"), 15)
        unresolved = replace(
            duplicate, collection_intelligence_status="NEEDS_REVIEW", recommendation="REVIEW",
            owned_current_match_summary="UNRESOLVED", upgrade_status="UNRESOLVED", max_rational_price=None,
        )
        # The removed duplicate cap must yield unavailable, never the larger
        # partial score produced by adding remaining supported components.
        self.assertIsNone(self.assistant._opportunity_score(self.candidate, unresolved, impact, "REVIEW"))

    def test_each_unavailable_component_blocks_the_entire_composite(self):
        decision, impact = self.boundary_advice()
        for field in ("impact_score", "quality_delta", "completion_delta", "collection_impact", "upgrade_impact", "want_list_impact"):
            with self.subTest(field=field):
                unavailable = replace(impact, **{field: None})
                self.assertIsNone(self.assistant._opportunity_score(self.candidate, decision, unavailable, "BUY"))

    def test_unresolved_upgrade_or_ownership_or_max_price_blocks_scoring(self):
        decision, impact = self.boundary_advice()
        for fields in (
            {"upgrade_status": "UNRESOLVED"},
            {"owned_current_match_summary": "UNRESOLVED: ownership unavailable"},
            {"collection_intelligence_status": "NEEDS_REVIEW"},
            {"collection_intelligence_status": None},
            {"max_rational_price": None},
        ):
            with self.subTest(fields=fields):
                self.assertIsNone(self.assistant._opportunity_score(self.candidate, replace(decision, **fields), impact, "BUY"))

    def test_unavailable_fields_are_not_zero_or_neutral(self):
        row = self.report().recommendations[0]
        for field in ("opportunity_score", "impact_score", "quality_delta", "series_delta", "max_rational_price"):
            with self.subTest(field=field):
                self.assertIsNone(getattr(row, field))
        self.assertEqual(row.acquisition_decision.upgrade_status, "UNRESOLVED")
        self.assertIsNone(row.impact_report.upgrade_impact)
        self.assertIsNone(row.impact_report.collection_impact)
        self.assertNotIn("Upgrade opportunity", row.reasons)

    def test_equal_grade_triplet_is_not_duplicate_pass_or_zero_price(self):
        self.candidate.candidate.grade = "VF-20"
        row = self.report().recommendations[0]
        self.assertEqual(row.recommendation_status, "REVIEW")
        self.assertIsNone(row.max_rational_price)
        self.assertIsNone(row.opportunity_score)
        self.assertIsNone(row.rank)

    def test_missing_holding_year_does_not_supply_gap_or_newness(self):
        assistant = SmartShoppingAssistant([make_item("1", "Canada", "10 cents", "", "VF-20")])
        row = self.report(assistant=assistant).recommendations[0]
        self.assertIn("UNRESOLVED", row.acquisition_decision.owned_current_match_summary)
        self.assertIsNone(row.opportunity_score)
        self.assertIsNone(row.impact_report.collection_impact)
        self.assertNotIn("Collection Gap", row.reasons)

    def test_incomplete_candidate_in_empty_collection_remains_unresolved(self):
        row = self.report([ShoppingCandidate("Unidentified coin", asking_price=1)], SmartShoppingAssistant([])).recommendations[0]
        self.assertIn("UNRESOLVED", row.acquisition_decision.owned_current_match_summary)
        self.assertEqual(row.recommendation_status, "REVIEW")
        self.assertIsNone(row.opportunity_score)
        self.assertIsNone(row.impact_report.collection_impact)

    def test_upgrade_title_cannot_supply_authority(self):
        for title in ("1911 Canada 10 cents EF40", "1911 Canada 10 cents EF40 upgrade"):
            with self.subTest(title=title):
                report = self.report([ShoppingCandidate(title, asking_price=10)])
                row = report.recommendations[0]
                self.assertEqual(row.recommendation_status, "REVIEW")
                self.assertIsNone(row.opportunity_score)
                self.assertIsNone(report.best_next_purchase)
                self.assertNotIn("Upgrade opportunity", row.reasons)

    def test_explicit_interest_is_visible_but_does_not_supply_purchase_advice(self):
        assistant = SmartShoppingAssistant([], [make_intent("Canada 10 cents 1911", 100)])
        self.candidate.want_list_priority = 100
        report = self.report(assistant=assistant)
        row = report.recommendations[0]
        self.assertEqual(row.want_list_status, "ON_WANT_LIST")
        self.assertIn("Explicit WANT_LIST Target", row.reasons)
        self.assertEqual(row.recommendation_status, "REVIEW")
        self.assertIsNone(row.opportunity_score)
        self.assertIsNone(report.best_next_purchase)
        # Independent interest can retain its existing designation without using
        # the unavailable purchase composite to select between interest targets.
        self.assertIs(report.highest_priority_want_list_target, row)

    def test_listing_warnings_and_independent_metadata_remain_visible(self):
        listing = ListingCandidate(
            "1911 Canada 10 cents EF40 damaged lot USD", price=10, shipping=2.5,
            url="https://example.com/item/42", seller="Synthetic seller", source="Manual",
            description="cleaned multiple coins",
        )
        candidate = ShoppingCandidate.from_listing(listing)
        row = self.report([candidate]).recommendations[0]
        self.assertEqual(row.total_cost, 12.5)
        self.assertEqual(candidate.asking_price, 10)
        self.assertEqual(candidate.shipping, 2.5)
        self.assertEqual(candidate.url, "https://example.com/item/42")
        self.assertEqual(candidate.seller, "Synthetic seller")
        self.assertEqual(candidate.source, "Manual")
        self.assertTrue(any("damage" in w.lower() or "clean" in w.lower() for w in row.warnings))
        self.assertTrue(any("lot" in w.lower() for w in row.warnings))
        self.assertTrue(any("currency" in w.lower() for w in row.warnings))
        self.assertEqual(row.recommendation_status, "REVIEW")
        self.assertIsNone(row.opportunity_score)

    def test_independent_series_interest_survives_without_composite_benefit(self):
        for title, interest in (
            ("1901 Newfoundland 50 cents VF20", "High-Priority Series: Newfoundland"),
            ("1859 Canada 1 cent VF20", "High-Priority Series: 1859 Canadian Large Cent"),
            ("1911 Canada 10 cents VF20", "High-Priority Series: Canadian silver"),
            ("1975 Argentina 1 cent VF20", "Low-priority world base-metal candidate"),
        ):
            with self.subTest(title=title):
                report = self.report([ShoppingCandidate(title, asking_price=1)])
                row = report.recommendations[0]
                self.assertIn(interest, row.reasons)
                self.assertEqual(row.recommendation_status, "REVIEW")
                self.assertIsNone(row.opportunity_score)
                self.assertIsNone(row.rank)
                self.assertIsNone(row.max_rational_price)
                self.assertIsNone(report.best_next_purchase)

    def test_unsupported_priority_reason_cannot_bypass_containment(self):
        decision = AcquisitionWorkflow([self.item]).evaluate(self.candidate.candidate)
        decision = replace(decision, priority_reasons=["Collection Gap", "Upgrade Candidate", "Eliminates upgrade gap"])
        with patch("smart_shopping_assistant.AcquisitionWorkflow.evaluate", return_value=decision):
            row = self.report().recommendations[0]
        for reason in decision.priority_reasons:
            self.assertNotIn(reason, row.reasons)
        self.assertIsNone(row.opportunity_score)

    def test_json_csv_and_markdown_preserve_unavailable_advice(self):
        report = self.report()
        payload = json.loads(json.dumps(report.to_dict()))
        fields = ("rank", "opportunity_score", "impact_score", "quality_delta", "series_delta", "max_rational_price")
        for field in fields:
            self.assertIsNone(payload["recommendations"][0][field])
        self.assertIsNone(payload["best_next_purchase"])
        markdown = self.assistant.format_markdown(report)
        self.assertNotIn("## Best Next Purchase", markdown)
        self.assertIn("Unranked", markdown)
        self.assertIn("unavailable", markdown.lower())
        self.assertNotIn("score 0", markdown)
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "shopping.csv")
            self.assertTrue(self.assistant.export_csv(path, report))
            with open(path, newline="", encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))
            for field in fields:
                self.assertEqual(row[field], "unavailable")

    def test_csv_supported_zero_remains_zero(self):
        # A supported numeric report boundary, independent of unresolved
        # acquisition advice, distinguishes real zero from withheld evidence.
        row = ShoppingRecommendation(0, "Supported zero", "WATCH", 0, 0, 0, 0.0,
                                     "NOT_ON_WANT_LIST", "safe market observation", 0.0, 12, "Synthetic",
                                     warnings=["safe warning"])
        report = ShoppingRecommendationReport([row])
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "zero.csv")
            self.assertTrue(self.assistant.export_csv(path, report))
            with open(path, newline="", encoding="utf-8") as handle:
                exported = next(csv.DictReader(handle))
        for field in ("rank", "opportunity_score", "impact_score", "quality_delta"):
            self.assertEqual(exported[field], "0")
        for field in ("series_delta", "max_rational_price"):
            self.assertEqual(exported[field], "0.0")
        self.assertEqual(exported["total_cost"], "12")
        self.assertEqual(exported["warnings"], "safe warning")

    def test_first_review_candidate_cannot_beat_supported_comparable_advice(self):
        # Current engines cannot emit resolved candidates. Inject a numeric
        # recommendation only at the assistant report boundary to test sorting.
        unresolved = ShoppingRecommendation(None, "Unresolved", "REVIEW", None, None, None, None,
                                            "NOT_ON_WANT_LIST", "", None, 1, "Synthetic")
        supported = ShoppingRecommendation(None, "Supported", "BUY", 45, 30, 2, 1,
                                          "NOT_ON_WANT_LIST", "", 80, 50, "Synthetic")
        for rows in ([unresolved, supported], [supported, unresolved]):
            with self.subTest(first=rows[0].item_name):
                with patch.object(self.assistant, "_evaluate_candidate", side_effect=rows):
                    report = self.report([self.candidate, self.candidate])
                self.assertIs(report.best_next_purchase, supported)
                self.assertEqual(supported.rank, 1)
                self.assertIsNone(unresolved.rank)
                self.assertIsNone(unresolved.opportunity_score)
                self.assertIs(report.highest_impact_candidate, supported)

    def test_review_and_pass_are_not_best_even_with_legacy_numeric_scores(self):
        for status in ("REVIEW", "PASS"):
            with self.subTest(status=status):
                row = ShoppingRecommendation(None, "Unsupported", status, 100, 100, 1, 1,
                                             "NOT_ON_WANT_LIST", "", 80, 1, "Synthetic")
                with patch.object(self.assistant, "_evaluate_candidate", return_value=row):
                    report = self.report()
                self.assertIsNone(report.best_next_purchase)

    def test_retained_raw_intelligence_cannot_reconstruct_withheld_advice(self):
        decision = AcquisitionWorkflow([self.item]).evaluate(self.candidate.candidate)
        for status in (MatchStatus.SAME_GRADE_DUPLICATE, MatchStatus.BETTER_GRADE_UPGRADE, MatchStatus.COLLECTION_GAP):
            with self.subTest(status=status):
                raw = replace(decision.intelligence_result, match_status=status, recommendation="BUY", collection_impact="COLLECTION_GAP")
                with patch("smart_shopping_assistant.AcquisitionWorkflow.evaluate", return_value=replace(decision, intelligence_result=raw)):
                    report = self.report()
                self.assertEqual(report.recommendations[0].recommendation_status, "REVIEW")
                self.assertIsNone(report.recommendations[0].opportunity_score)
                self.assertIsNone(report.best_next_purchase)

    def test_conflicting_buy_fields_cannot_override_unavailable_impact(self):
        decision, impact = self.boundary_advice()
        impact = replace(impact, impact_score=None, quality_delta=None, completion_delta=None, collection_impact=None)
        with patch("smart_shopping_assistant.AcquisitionWorkflow.evaluate", return_value=decision), patch(
            "smart_shopping_assistant.AcquisitionImpactEngine.evaluate", return_value=impact
        ):
            report = self.report()
        self.assertEqual(report.recommendations[0].recommendation_status, "REVIEW")
        self.assertIsNone(report.recommendations[0].opportunity_score)
        self.assertIsNone(report.best_next_purchase)

    def test_supported_boundary_components_keep_legacy_arithmetic(self):
        decision, impact = self.boundary_advice()
        self.assertEqual(self.assistant._opportunity_score(self.candidate, decision, impact, "BUY"), 59)

    def test_nested_review_sentinels_override_supported_outer_fields(self):
        decision, impact = self.boundary_advice()
        for recommendation in ("REVIEW", " REVIEW ", "review"):
            with self.subTest(recommendation=recommendation):
                nested = replace(decision, recommendation=recommendation)
                retained = replace(impact, acquisition_decision=nested)
                self.assertEqual(self.assistant._shopping_status(decision, retained), "REVIEW")
                self.assertIsNone(self.assistant._opportunity_score(self.candidate, decision, retained, "BUY"))
        lower_unresolved = replace(decision, owned_current_match_summary="unresolved: owned issue equivalence unavailable")
        self.assertIsNone(self.assistant._opportunity_score(self.candidate, lower_unresolved, impact, "BUY"))
        descriptive = replace(decision, owned_current_match_summary="Synthetic supported preview of review history")
        self.assertEqual(self.assistant._opportunity_score(self.candidate, descriptive, impact, "BUY"), 59)

    def test_stale_outer_buy_is_contained_at_report_and_public_export(self):
        decision, impact = self.boundary_advice()
        nested = replace(decision, recommendation=" REVIEW ")
        row = ShoppingRecommendation(4, "Retained BUY", "BUY", 59, 40, 2, 3,
                                     "NOT_ON_WANT_LIST", "safe observation", 100, 12, "Synthetic",
                                     warnings=["safe warning"], acquisition_decision=decision,
                                     impact_report=replace(impact, acquisition_decision=nested))
        public_report = ShoppingRecommendationReport([row], best_next_purchase=row, highest_impact_candidate=row)
        payload = public_report.to_dict()
        self.assertIsNone(payload["best_next_purchase"])
        self.assertIsNone(payload["recommendations"][0]["opportunity_score"])
        self.assertIsNone(payload["recommendations"][0]["rank"])
        self.assertNotIn("## Best Next Purchase", self.assistant.format_markdown(public_report))
        with patch.object(self.assistant, "_evaluate_candidate", return_value=row):
            report = self.report()
        self.assertIsNone(report.best_next_purchase)
        self.assertEqual(row.recommendation_status, "REVIEW")
        for name in ("rank", "opportunity_score", "impact_score", "quality_delta", "series_delta", "max_rational_price"):
            self.assertIsNone(getattr(row, name))
        self.assertEqual(row.total_cost, 12)
        self.assertEqual(row.market_context, "safe observation")
        self.assertEqual(row.warnings, ["safe warning"])
        self.assertTrue(any("unavailable" in reason for reason in row.reasons))


if __name__ == "__main__":
    unittest.main()
