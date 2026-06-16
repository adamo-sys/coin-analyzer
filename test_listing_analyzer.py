"""Tests for the offline Listing Analyzer workflow."""

import os
import tempfile
import unittest

from openpyxl import Workbook

from coin_collection import CoinItem
from focused_collection_intelligence import MatchStatus
from legacy_portfolio_importer import LegacyWantListIntent
from listing_analyzer import ListingAnalyzer, ListingCandidate, is_valid_listing_url
from session_context import SessionContext


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
        "date_added": "2026-06-16",
    }
    data.update(overrides)
    return CoinItem(**data)


def make_intent(target_coin, priority="High", target_grade="VF-20", budget=150.0):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id="legacy_want_list_2",
        target_coin=target_coin,
        priority=priority,
        target_grade=target_grade,
        budget=budget,
        why_wanted="Listing analyzer test target",
        status="Active",
        priority_score=75,
    )


def create_want_list_workbook(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "WANT_LIST"
    ws.append(WANT_HEADERS)
    ws.append([
        "Newfoundland 50 cents 1904",
        "High",
        "VF-20",
        150,
        "Shared context target",
        "Active",
    ])
    wb.save(path)


class TestListingCandidate(unittest.TestCase):
    """Verify deterministic listing input behavior."""

    def test_listing_candidate_creation(self):
        listing = ListingCandidate(
            title="1904 Newfoundland 50 cents VF20",
            price="$100.00",
            shipping="12.50",
            url="https://example.com/listing/1",
            notes="Looks original",
            seller="Dealer",
            source="Auction",
        )

        self.assertEqual(listing.price, 100.0)
        self.assertEqual(listing.shipping, 12.5)
        self.assertEqual(listing.total_cost, 112.5)
        self.assertEqual(listing.url, "https://example.com/listing/1")
        self.assertTrue(listing.created_at)

    def test_url_validation(self):
        self.assertTrue(is_valid_listing_url(""))
        self.assertTrue(is_valid_listing_url("https://example.com/item"))
        self.assertTrue(is_valid_listing_url("http://example.com/item"))
        self.assertFalse(is_valid_listing_url("ftp://example.com/item"))
        self.assertFalse(is_valid_listing_url("not a url"))

    def test_total_cost_calculation(self):
        listing = ListingCandidate("Canada 1 cent 1920", price=25, shipping=4.75)
        self.assertEqual(listing.total_cost, 29.75)

    def test_missing_url_is_allowed(self):
        listing = ListingCandidate("Canada 1 cent 1920", price=25)
        self.assertNotIn("Invalid URL format", listing.validate())

    def test_missing_shipping_defaults_to_zero(self):
        listing = ListingCandidate("Canada 1 cent 1920", price=25)
        self.assertEqual(listing.shipping, 0.0)
        self.assertEqual(listing.total_cost, 25.0)

    def test_missing_price_warns(self):
        listing = ListingCandidate("Canada 1 cent 1920")
        self.assertIn("Missing asking price", listing.validate())


class TestListingAnalyzer(unittest.TestCase):
    """Verify listings are routed through Acquisition Workflow and shared context."""

    def test_want_list_listing(self):
        analyzer = ListingAnalyzer([], [make_intent("Newfoundland 50 cents 1904")])

        result = analyzer.analyze(ListingCandidate(
            title="1904 Newfoundland 50 cents VF20 PCGS",
            price=100,
            shipping=10,
            url="https://example.com/nfld-1904",
        ))

        self.assertEqual(result.want_list_status, "ON_WANT_LIST")
        self.assertEqual(result.intelligence_result.match_status, MatchStatus.WANT_LIST_MATCH)
        self.assertIn(result.recommendation, {"MUST BUY", "STRONG BUY", "BUY"})

    def test_duplicate_listing(self):
        analyzer = ListingAnalyzer([
            make_item("1", "Canada", "1 cent", "1967", "VF-30")
        ])

        result = analyzer.analyze(ListingCandidate(
            title="1967 Canada 1 cent VF30",
            price=5,
        ))

        self.assertEqual(result.duplicate_status, "SAME_GRADE_DUPLICATE")
        self.assertEqual(result.recommendation, "PASS")

    def test_upgrade_listing(self):
        analyzer = ListingAnalyzer([
            make_item("1", "Canada", "10 cents", "1911", "VF-20")
        ])

        result = analyzer.analyze(ListingCandidate(
            title="1911 Canada 10 cents EF40 PCGS",
            price=80,
            shipping=5,
        ))

        self.assertEqual(result.upgrade_status, "UPGRADE")
        self.assertIn(result.recommendation, {"STRONG BUY", "BUY"})

    def test_collection_gap_listing(self):
        analyzer = ListingAnalyzer([
            make_item("1", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("2", "Newfoundland", "50 cents", "1902", "VF-20"),
        ])

        result = analyzer.analyze(ListingCandidate(
            title="1901 Newfoundland 50 cents VF20 PCGS",
            price=70,
            shipping=5,
        ))

        self.assertEqual(result.intelligence_result.match_status, MatchStatus.COLLECTION_GAP)
        self.assertIn(result.recommendation, {"STRONG BUY", "BUY", "WATCH"})

    def test_newfoundland_acquisition_target_listing(self):
        analyzer = ListingAnalyzer([], [make_intent("Newfoundland 50 cents 1904")])

        result = analyzer.analyze(ListingCandidate(
            title="1904 Newfoundland 50 cents VF20 PCGS",
            price=125,
        ))

        self.assertEqual(result.want_list_status, "ON_WANT_LIST")
        self.assertIn("High-Priority Series: Newfoundland", result.acquisition_decision.priority_reasons)

    def test_canadian_silver_listing(self):
        analyzer = ListingAnalyzer([], [make_intent("Canada silver dollar 1935")])

        result = analyzer.analyze(ListingCandidate(
            title="1935 Canada silver dollar EF40 PCGS",
            price=120,
        ))

        self.assertEqual(result.want_list_status, "ON_WANT_LIST")
        self.assertIn("High-Priority Series: Canadian silver", result.acquisition_decision.priority_reasons)

    def test_1859_large_cent_listing(self):
        analyzer = ListingAnalyzer([], [make_intent("Canada 1859 large cent")])

        result = analyzer.analyze(ListingCandidate(
            title="1859 Canada Large Cent VF20 PCGS Narrow 9",
            price=125,
        ))

        self.assertEqual(result.want_list_status, "ON_WANT_LIST")
        self.assertIn("High-Priority Series: 1859 Canadian Large Cent", result.acquisition_decision.priority_reasons)

    def test_missing_price_listing(self):
        analyzer = ListingAnalyzer([], [make_intent("Canada 1 cent 1920")])

        result = analyzer.analyze(ListingCandidate(
            title="1920 Canada 1 cent VF20",
        ))

        self.assertEqual(result.listing.total_cost, 0.0)
        self.assertIn("Missing asking price", result.warnings)
        self.assertIn(result.recommendation, {"WATCH", "REVIEW"})

    def test_shared_session_context_integration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook_path = os.path.join(temp_dir, "want_list.xlsx")
            create_want_list_workbook(workbook_path)
            context = SessionContext()
            load_result = context.load_want_list_context(workbook_path, [])

            analyzer = ListingAnalyzer([], context.get_want_list_intents())
            result = analyzer.analyze(ListingCandidate(
                title="1904 Newfoundland 50 cents VF20 PCGS",
                price=100,
                shipping=10,
            ))

        self.assertTrue(load_result.success)
        self.assertEqual(context.want_list_count, 1)
        self.assertEqual(result.want_list_status, "ON_WANT_LIST")

    def test_url_is_reference_only_and_not_required(self):
        analyzer = ListingAnalyzer([])

        result = analyzer.analyze(ListingCandidate(
            title="1975 Argentina 1 cent VF20",
            price=1,
        ))

        self.assertEqual(result.listing.url, "")
        self.assertEqual(result.recommendation, "PASS")


if __name__ == "__main__":
    unittest.main()
