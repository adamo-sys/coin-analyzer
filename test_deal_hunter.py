"""Tests for v3.1 Deal Hunter MVP."""

import os
import tempfile
import unittest

from coin_collection import CoinItem
from deal_hunter import (
    DealHunter,
    DealHunterReport,
    DealListing,
    RISK_HIGH_SHIPPING,
    RISK_LOT_LISTING,
    RISK_NEEDS_MANUAL_REVIEW,
    RISK_POSSIBLE_DAMAGE,
    RISK_RAW_OVERGRADED,
    RISK_UNCLEAR_CURRENCY,
    RISK_UNCLEAR_GRADE,
)
from legacy_portfolio_importer import LegacyWantListIntent
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord
from persistence_manager import PersistenceManager


SAMPLE_CSV = os.path.join("test_data", "deal_hunter", "sample_ebay_ca_listings.csv")


def make_item(item_id, country, denomination, year, grade, **overrides):
    data = {
        "id": item_id,
        "image_path": "",
        "country": country,
        "denomination": denomination,
        "year": year,
        "grade": grade,
        "notes": "",
        "date_added": "2026-06-20",
    }
    data.update(overrides)
    return CoinItem(**data)


def make_intent(target_coin, priority_score=90):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id=f"deal_{target_coin}",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=150.0,
        why_wanted="Deal Hunter target",
        status="Active",
        priority_score=priority_score,
    )


class TestDealHunter(unittest.TestCase):
    def setUp(self):
        self.items = [
            make_item("nf1900", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("nf1902", "Newfoundland", "50 cents", "1902", "VF-20"),
            make_item("ca1911", "Canada", "10 cents", "1911", "VF-20"),
            make_item("lc1859", "Canada", "1 cent", "1859", "VG-8"),
        ]
        self.intents = [
            make_intent("Newfoundland 50 cents 1901"),
            make_intent("Canada chartered banknote BCS VF25"),
        ]
        self.market = MarketAwarenessEngine(observations=[
            ObservedPriceRecord("1901 Newfoundland 50 cents", "Newfoundland", "50 cents", "1901", "VF-20", 90),
            ObservedPriceRecord("1911 Canada 10 cents", "Canada", "10 cents", "1911", "EF-40", 70),
        ])
        self.hunter = DealHunter(self.items, self.intents, self.market)

    def test_total_cost_calculation(self):
        listing = DealListing("1901 Newfoundland 50 cents VF20", price_cad="$80", shipping_cad="7.50")
        self.assertEqual(listing.total_cost, 87.5)

    def test_underpriced_newfoundland_upgrade_or_gap(self):
        result = DealHunter(self.items, [], self.market).analyze_listing(DealListing(
            "1901 Newfoundland 50 cents VF20 PCGS",
            price_cad=80,
            shipping_cad=5,
            seller="Canada Coins",
            source="eBay.ca",
        ))

        self.assertEqual(result.collection_status, "collection gap")
        self.assertIn(result.recommendation, {"BUY", "NEGOTIATE", "WATCH"})
        self.assertGreaterEqual(result.priority_score, 60)
        self.assertIn("Newfoundland priority", result.reasons)

    def test_same_grade_duplicate(self):
        result = self.hunter.analyze_listing(DealListing("1900 Newfoundland 50 cents VF20 ICCS", 75, 5))

        self.assertEqual(result.collection_status, "same-grade duplicate")
        self.assertEqual(result.recommendation, "PASS")

    def test_lower_grade_duplicate(self):
        result = self.hunter.analyze_listing(DealListing("1900 Newfoundland 50 cents VG8", 25, 5))

        self.assertEqual(result.collection_status, "lower-grade duplicate")
        self.assertEqual(result.recommendation, "PASS")

    def test_collection_gap(self):
        result = DealHunter(self.items, [], self.market).analyze_listing(DealListing("1901 Newfoundland 50 cents VF20", 85, 5))

        self.assertEqual(result.collection_status, "collection gap")
        self.assertGreater(result.collection_fit_score, 50)

    def test_want_list_match(self):
        result = DealHunter([], self.intents).analyze_listing(DealListing("Canada chartered banknote BCS VF25", 120, 10))

        self.assertEqual(result.collection_status, "want-list match")
        self.assertIn("Explicit WANT_LIST match", result.reasons)

    def test_high_shipping_kills_deal(self):
        result = self.hunter.analyze_listing(DealListing("1912 Canada 10 cents VF20", 25, 40))

        self.assertIn("High shipping weakens the deal", result.warnings)
        self.assertIn(RISK_HIGH_SHIPPING, result.risk_flags)
        self.assertIn(result.recommendation, {"NEGOTIATE", "WATCH", "REVIEW", "PASS"})
        self.assertNotEqual(result.recommendation, "BUY")

    def test_iccs_detection(self):
        result = self.hunter.analyze_listing(DealListing("1900 Newfoundland 50 cents VF20 ICCS", 75, 5))
        self.assertEqual(result.parsed_candidate.certifier, "ICCS")

    def test_pcgs_detection(self):
        result = self.hunter.analyze_listing(DealListing("1901 Newfoundland 50 cents VF20 PCGS", 80, 5))
        self.assertEqual(result.parsed_candidate.certifier, "PCGS")

    def test_ngc_detection(self):
        result = self.hunter.analyze_listing(DealListing("1911 Canada 10 cents EF40 NGC silver", 65, 5))
        self.assertEqual(result.parsed_candidate.certifier, "NGC")

    def test_banknote_and_bcs_detection(self):
        result = DealHunter([], self.intents).analyze_listing(DealListing("Canada chartered banknote BCS VF25", 150, 8))

        self.assertEqual(result.parsed_candidate.certifier, "BCS")
        self.assertIn("banknote", result.parsed_candidate.keywords)
        self.assertTrue(any("banknote" in reason.lower() for reason in result.reasons))

    def test_non_canadian_irrelevant_item(self):
        result = self.hunter.analyze_listing(DealListing("France 10 centimes 1975", 1, 5))

        self.assertEqual(result.recommendation, "PASS")
        self.assertIn("Non-Canadian item appears outside Adam's core priorities", result.warnings)

    def test_unclear_currency(self):
        result = self.hunter.analyze_listing(DealListing("1904 Newfoundland 50 cents VF20 USD", "90 USD", 10, currency="USD"))

        self.assertIn(result.recommendation, {"REVIEW", "PASS"})
        self.assertTrue(any("currency" in warning.lower() for warning in result.warnings))
        self.assertIn(RISK_UNCLEAR_CURRENCY, result.risk_flags)

    def test_csv_import(self):
        listings = DealHunter.import_csv(SAMPLE_CSV)

        self.assertGreaterEqual(len(listings), 8)
        self.assertIsInstance(listings[0], DealListing)
        self.assertEqual(listings[0].total_cost, 93.0)

    def test_csv_import_with_warnings_handles_missing_optional_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "minimal.csv")
            with open(csv_path, "w", encoding="utf-8") as handle:
                handle.write("listing_title,price\n1901 Newfoundland 50 cents VF20,85\n")

            result = DealHunter.import_csv_with_warnings(csv_path)

        self.assertEqual(result.rows_found, 1)
        self.assertEqual(result.importable_count, 1)
        self.assertEqual(result.listings[0].shipping_cad, 0.0)

    def test_csv_import_reports_malformed_price(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "bad_price.csv")
            with open(csv_path, "w", encoding="utf-8") as handle:
                handle.write("title,price_cad,shipping_cad,extra\n1901 Newfoundland 50 cents VF20,not-a-price,,ignored\n")

            result = DealHunter.import_csv_with_warnings(csv_path)

        self.assertEqual(result.rows_found, 1)
        self.assertEqual(result.importable_count, 1)
        self.assertTrue(any("Malformed price_cad" in warning for warning in result.warnings))

    def test_csv_import_skips_missing_required_title(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "missing_title.csv")
            with open(csv_path, "w", encoding="utf-8") as handle:
                handle.write("title,price_cad\n,85\n")

            result = DealHunter.import_csv_with_warnings(csv_path)

        self.assertEqual(result.importable_count, 0)
        self.assertEqual(result.skipped_rows, 1)
        self.assertTrue(any("missing required title" in warning for warning in result.warnings))

    def test_counterargument_before_buy(self):
        result = self.hunter.analyze_listing(DealListing("1901 Newfoundland 50 cents VF20 PCGS", 80, 5))

        self.assertTrue(result.counterargument)
        self.assertIn("better opportunities may exist", result.counterargument)

    def test_export_generation(self):
        report = self.hunter.generate_report([
            DealListing("1901 Newfoundland 50 cents VF20 PCGS", 80, 5),
            DealListing("France 10 centimes 1975", 1, 5),
        ])

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "deal_hunter.csv")
            md_path = os.path.join(temp_dir, "deal_hunter.md")
            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("deterministic CAD guidance only", handle.read())
            with open(csv_path, "r", encoding="utf-8") as handle:
                exported = handle.read()
                self.assertIn("recommendation", exported)
                self.assertIn("risk_flags", exported)
                self.assertIn("parsed_country", exported)

    def test_persistence_round_trip(self):
        listing = DealListing("1901 Newfoundland 50 cents VF20 PCGS", 80, 5)
        report = self.hunter.generate_report([listing])
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PersistenceManager(state_dir=os.path.join(temp_dir, "state"))
            state = manager.create_state(
                recent_deal_listings=[listing],
                deal_hunter_reports=[report.to_dict()],
            )
            saved = manager.save_state(state)
            loaded = manager.load_state()

        self.assertTrue(saved.success)
        self.assertEqual(len(loaded.state.recent_deal_listings), 1)
        self.assertEqual(len(loaded.state.deal_hunter_reports), 1)

    def test_report_generation_orders_best_first(self):
        report = self.hunter.generate_report([
            DealListing("France 10 centimes 1975", 1, 5),
            DealListing("1901 Newfoundland 50 cents VF20 PCGS", 80, 5),
        ])

        self.assertIsInstance(report, DealHunterReport)
        self.assertIn("Newfoundland", report.results[0].listing.title)

    def test_gui_source_contains_deal_hunter_entry(self):
        with open("coin_collection_gui.py", "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn('label="Deal Hunter"', source)
        self.assertIn("open_deal_hunter", source)

    def test_vague_estate_lot_requires_review(self):
        result = self.hunter.analyze_listing(DealListing("Estate lot old Canadian coins silver rare", 50, 18))

        self.assertIn(RISK_LOT_LISTING, result.risk_flags)
        self.assertIn(RISK_NEEDS_MANUAL_REVIEW, result.risk_flags)
        self.assertEqual(result.recommendation, "REVIEW")

    def test_raw_overgraded_listing_requires_review(self):
        result = self.hunter.analyze_listing(DealListing("Raw 1859 Canada Large Cent GEM RARE", 200, 12))

        self.assertIn(RISK_RAW_OVERGRADED, result.risk_flags)
        self.assertIn(RISK_NEEDS_MANUAL_REVIEW, result.risk_flags)
        self.assertEqual(result.recommendation, "REVIEW")

    def test_damaged_coin_keyword_requires_review(self):
        result = self.hunter.analyze_listing(DealListing("1973 Canada quarter Large Bust raw bent", 25, 5))

        self.assertIn(RISK_POSSIBLE_DAMAGE, result.risk_flags)
        self.assertEqual(result.recommendation, "REVIEW")

    def test_bulk_lot_requires_review(self):
        result = self.hunter.analyze_listing(DealListing("Bulk lot Newfoundland Canada coins mixed group", 80, 30))

        self.assertIn(RISK_LOT_LISTING, result.risk_flags)
        self.assertIn(RISK_HIGH_SHIPPING, result.risk_flags)
        self.assertEqual(result.recommendation, "REVIEW")

    def test_1973_large_bust_priority(self):
        result = self.hunter.analyze_listing(DealListing("1973 Canada quarter Large Bust VF20", 35, 5))

        self.assertIn("large bust", result.parsed_candidate.keywords)
        self.assertGreaterEqual(result.priority_score, 30)

    def test_1926_near_6_priority(self):
        result = self.hunter.analyze_listing(DealListing("1926 Canada 5 cents Near 6 VF20", 45, 5))

        self.assertIn("near 6", result.parsed_candidate.keywords)
        self.assertGreaterEqual(result.priority_score, 30)

    def test_grade_words_are_parsed(self):
        result = self.hunter.analyze_listing(DealListing("1901 Newfoundland 50 cents Very Fine", 85, 5))

        self.assertEqual(result.parsed_candidate.grade, "VF-20")
        self.assertNotIn(RISK_UNCLEAR_GRADE, result.risk_flags)

    def test_no_grade_sets_unclear_grade_flag(self):
        result = self.hunter.analyze_listing(DealListing("1901 Newfoundland 50 cents", 85, 5))

        self.assertIn(RISK_UNCLEAR_GRADE, result.risk_flags)


if __name__ == "__main__":
    unittest.main()
