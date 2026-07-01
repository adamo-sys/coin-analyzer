"""Tests for Smart Shopping Assistant."""

import os
import tempfile
import unittest

from openpyxl import Workbook

from coin_collection import CoinItem
from collection_dashboard import CollectionDashboard
from focused_collection_intelligence import CandidateItem
from legacy_portfolio_importer import LegacyWantListIntent
from listing_analyzer import ListingCandidate
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord
from session_context import SessionContext
from smart_shopping_assistant import (
    ShoppingCandidate,
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

    def test_candidate_ranking_places_highest_opportunity_first(self):
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
        self.assertEqual(report.best_next_purchase.item_name, "1901 Newfoundland 50 cents VF20")
        self.assertGreater(report.recommendations[0].opportunity_score, report.recommendations[1].opportunity_score)

    def test_strong_buy_path(self):
        candidate = ShoppingCandidate(
            "1901 Newfoundland 50 cents VF20",
            asking_price=90,
            candidate=CandidateItem("Newfoundland", "50 cents", "1901", grade="VF-20", asking_price=90),
        )

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.best_next_purchase.recommendation_status, "STRONG BUY")
        self.assertIn("WANT_LIST priority", report.best_next_purchase.reasons)
        self.assertEqual(report.best_next_purchase.market_context, "Within recent observed range")

    def test_buy_path(self):
        candidate = ShoppingCandidate(
            "1912 Canada 10 cents VF20",
            asking_price=45,
            candidate=CandidateItem("Canada", "10 cents", "1912", grade="VF-20", asking_price=45),
        )

        report = SmartShoppingAssistant(self.items, [], MarketAwarenessEngine()).generate_report([candidate], include_want_list_targets=False)

        self.assertIn(report.best_next_purchase.recommendation_status, {"BUY", "STRONG BUY"})
        self.assertGreater(report.best_next_purchase.impact_score, 0)

    def test_negotiate_path_for_above_observed_range(self):
        candidate = ShoppingCandidate(
            "1901 Newfoundland 50 cents VF20",
            asking_price=125,
            candidate=CandidateItem("Newfoundland", "50 cents", "1901", grade="VF-20", asking_price=125),
        )

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.best_next_purchase.recommendation_status, "NEGOTIATE")
        self.assertIn("Above recent observed range", report.best_next_purchase.reasons)

    def test_watch_path_for_missing_price(self):
        candidate = ShoppingCandidate(
            "1901 Newfoundland 50 cents VF20",
            candidate=CandidateItem("Newfoundland", "50 cents", "1901", grade="VF-20"),
        )

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.best_next_purchase.recommendation_status, "WATCH")
        self.assertIn("Missing asking price", report.best_next_purchase.warnings)

    def test_pass_path_for_duplicate(self):
        candidate = ShoppingCandidate(
            "1900 Newfoundland 50 cents VF20",
            asking_price=40,
            candidate=CandidateItem("Newfoundland", "50 cents", "1900", grade="VF-20", asking_price=40),
        )

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.best_next_purchase.recommendation_status, "PASS")

    def test_review_path_for_ambiguous_candidate(self):
        items = [make_item("lc1", "Canada", "1 cent", "1859", "VF-20")]
        candidate = ShoppingCandidate(
            "1859 Canada Large Cent Wide 9",
            asking_price=50,
            candidate=CandidateItem("Canada", "1 cent", "1859", variety="Wide 9", grade="VF-20", asking_price=50),
        )

        report = SmartShoppingAssistant(items, [], MarketAwarenessEngine()).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.best_next_purchase.recommendation_status, "REVIEW")

    def test_want_list_prioritization_from_intents(self):
        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report([], include_want_list_targets=True)

        self.assertIsNotNone(report.highest_priority_want_list_target)
        self.assertIn("Newfoundland 50 cents 1901", report.highest_priority_want_list_target.item_name)

    def test_upgrade_prioritization(self):
        candidate = ShoppingCandidate(
            "1911 Canada 10 cents EF40",
            asking_price=70,
            candidate=CandidateItem("Canada", "10 cents", "1911", grade="EF-40", certifier="PCGS", asking_price=70),
        )

        report = SmartShoppingAssistant(self.items, [], MarketAwarenessEngine()).generate_report([candidate], include_want_list_targets=False)

        self.assertTrue(any("Upgrade" in reason for reason in report.best_next_purchase.reasons))
        self.assertGreater(report.best_next_purchase.opportunity_score, 0)

    def test_market_awareness_integration(self):
        candidate = ShoppingCandidate(
            "1901 Newfoundland 50 cents VF20",
            asking_price=80,
            candidate=CandidateItem("Newfoundland", "50 cents", "1901", grade="VF-20", asking_price=80),
        )

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.best_next_purchase.market_context, "Below recent observed range")
        self.assertIn("Below recent observed range", report.best_next_purchase.reasons)

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
        self.assertEqual(data.shopping_report.best_next_purchase.item_name, "1901 Newfoundland 50 cents VF20")

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

        self.assertIsNotNone(report.best_next_purchase)
        self.assertEqual(report.best_next_purchase.want_list_status, "ON_WANT_LIST")

    def test_listing_candidate_conversion(self):
        listing = ListingCandidate("1901 Newfoundland 50 cents VF20", price=90, shipping=5, source="Dealer")
        candidate = ShoppingCandidate.from_listing(listing)

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.best_next_purchase.source, "Listing Analyzer")
        self.assertEqual(report.best_next_purchase.total_cost, 95.0)

    def test_photo_vault_reference_ids_are_preserved(self):
        candidate = ShoppingCandidate(
            "1901 Newfoundland 50 cents VF20",
            asking_price=90,
            candidate=CandidateItem("Newfoundland", "50 cents", "1901", grade="VF-20", asking_price=90),
            photo_reference_ids=["photo_listing_1", "photo_reference_1"],
        )

        report = SmartShoppingAssistant(self.items, self.intents, self.market).generate_report([candidate], include_want_list_targets=False)

        self.assertEqual(report.best_next_purchase.photo_reference_ids, ["photo_listing_1", "photo_reference_1"])

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
        self.assertIsNotNone(report.best_next_purchase)

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
        self.assertIsNotNone(report.best_next_purchase)

    def test_shop_report_connected_data_field_serializes(self):
        """ShoppingRecommendationReport with connected_data serializes correctly."""
        report = ShoppingRecommendationReport(
            recommendations=[],
            connected_data={"watchlist_matches": 2, "total_recommendations": 5, "match_rate": 0.4},
        )
        d = report.to_dict()
        self.assertEqual(d["connected_data"]["watchlist_matches"], 2)
        self.assertEqual(d["connected_data"]["match_rate"], 0.4)


if __name__ == "__main__":
    unittest.main()