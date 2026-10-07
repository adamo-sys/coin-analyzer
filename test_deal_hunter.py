"""Tests for v3.1 Deal Hunter MVP."""

import csv
import json
import os
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

from acquisition_workflow import AcquisitionWorkflow
from acquisition_impact import AcquisitionImpactEngine
from listing_analyzer import ListingAnalyzer
from smart_shopping_assistant import ShoppingCandidate, SmartShoppingAssistant

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

        self.assertEqual(result.collection_status, "needs review")
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertIsNone(result.priority_score)
        self.assertIn("Newfoundland collector interest", result.reasons)

    def test_same_grade_duplicate(self):
        result = self.hunter.analyze_listing(DealListing("1900 Newfoundland 50 cents VF20 ICCS", 75, 5))

        self.assertEqual(result.collection_status, "needs review")
        self.assertEqual(result.recommendation, "REVIEW")

    def test_lower_grade_duplicate(self):
        result = self.hunter.analyze_listing(DealListing("1900 Newfoundland 50 cents VG8", 25, 5))

        self.assertEqual(result.collection_status, "needs review")
        self.assertEqual(result.recommendation, "REVIEW")

    def test_collection_gap(self):
        result = DealHunter(self.items, [], self.market).analyze_listing(DealListing("1901 Newfoundland 50 cents VF20", 85, 5))

        self.assertEqual(result.collection_status, "needs review")
        self.assertIsNone(result.collection_fit_score)

    def test_want_list_match(self):
        result = DealHunter([], self.intents).analyze_listing(DealListing("Canada chartered banknote BCS VF25", 120, 10))

        self.assertEqual(result.collection_status, "needs review")
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

        self.assertEqual(result.recommendation, "REVIEW")
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

    def test_report_generation_preserves_unranked_input_order(self):
        report = self.hunter.generate_report([
            DealListing("France 10 centimes 1975", 1, 5),
            DealListing("1901 Newfoundland 50 cents VF20 PCGS", 80, 5),
        ])

        self.assertIsInstance(report, DealHunterReport)
        self.assertIn("France", report.results[0].listing.title)
        self.assertTrue(all(row.priority_score is None for row in report.results))

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
        self.assertIsNone(result.priority_score)

    def test_1926_near_6_priority(self):
        result = self.hunter.analyze_listing(DealListing("1926 Canada 5 cents Near 6 VF20", 45, 5))

        self.assertIn("near 6", result.parsed_candidate.keywords)
        self.assertIsNone(result.priority_score)

    def test_grade_words_are_parsed(self):
        result = self.hunter.analyze_listing(DealListing("1901 Newfoundland 50 cents Very Fine", 85, 5))

        self.assertEqual(result.parsed_candidate.grade, "VF-20")
        self.assertNotIn(RISK_UNCLEAR_GRADE, result.risk_flags)

    def test_no_grade_sets_unclear_grade_flag(self):
        result = self.hunter.analyze_listing(DealListing("1901 Newfoundland 50 cents", 85, 5))

        self.assertIn(RISK_UNCLEAR_GRADE, result.risk_flags)


class TestDealHunterContainment(unittest.TestCase):
    def setUp(self):
        TestDealHunter.setUp(self)

    def test_nested_review_overrides_stale_watch_and_numeric_components(self):
        listing = DealListing("1901 Newfoundland 50 cents VF20 PCGS", 1, 2,
                              seller="Synthetic seller", listing_url="https://example.invalid/coin")
        analysis = ListingAnalyzer(self.items).analyze(listing.to_listing_candidate())
        review = analysis.acquisition_decision
        outer = replace(review, recommendation="WATCH", collection_intelligence_status="COLLECTION_GAP",
                        upgrade_status="NOT_UPGRADE", owned_current_match_summary="Retained decisive summary",
                        max_rational_price=100)
        impact = AcquisitionImpactEngine(self.items).evaluate(analysis.candidate)
        impact = replace(impact, impact_score=100, quality_delta=0, completion_delta=0,
                         collection_impact="COLLECTION_GAP", upgrade_impact="NO_UPGRADE_IMPACT",
                         want_list_impact="NO_WANT_LIST_IMPACT", acquisition_decision=review)
        from smart_shopping_assistant import ShoppingRecommendation, ShoppingRecommendationReport
        shopping = ShoppingRecommendation(1, listing.title, "WATCH", 100, 100, 0, 0,
                                          "NOT_ON_WANT_LIST", "", 100, 3, "Synthetic")
        with patch("deal_hunter.ListingAnalyzer.analyze", return_value=replace(analysis, recommendation="WATCH", max_rational_price=100)), patch(
            "deal_hunter.AcquisitionWorkflow.evaluate", return_value=outer
        ), patch("deal_hunter.AcquisitionImpactEngine.evaluate", return_value=impact), patch(
            "deal_hunter.SmartShoppingAssistant.generate_report", return_value=ShoppingRecommendationReport([shopping], best_next_purchase=shopping)
        ):
            result = self.hunter.analyze_listing(listing)
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertEqual(result.collection_status, "needs review")
        for name in ("priority_score", "collection_fit_score", "max_rational_price"):
            self.assertIsNone(getattr(result, name))
        self.assertFalse(any("collection gap" in reason.lower() for reason in result.reasons))
        self.assertTrue(any("unavailable" in reason.lower() for reason in result.reasons))
        self.assertEqual(result.listing.total_cost, 3)
        self.assertEqual(result.listing.seller, "Synthetic seller")
        self.assertEqual(result.listing.listing_url, "https://example.invalid/coin")

    def test_each_nested_authority_independently_blocks_retained_watch(self):
        listing = DealListing("1901 Newfoundland 50 cents VF20 PCGS", 1, 2)
        analysis = ListingAnalyzer(self.items).analyze(listing.to_listing_candidate())
        review = analysis.acquisition_decision
        supported = replace(review, recommendation="WATCH", collection_intelligence_status="COLLECTION_GAP",
                            upgrade_status="NOT_UPGRADE", owned_current_match_summary="Supported boundary advice",
                            max_rational_price=100, intelligence_result=None)
        impact = replace(AcquisitionImpactEngine(self.items).evaluate(analysis.candidate),
                         impact_score=100, quality_delta=0, completion_delta=0,
                         collection_impact="COLLECTION_GAP", upgrade_impact="NO_UPGRADE_IMPACT",
                         want_list_impact="NO_WANT_LIST_IMPACT", acquisition_decision=supported)
        from smart_shopping_assistant import ShoppingRecommendation, ShoppingRecommendationReport
        shopping = ShoppingRecommendation(1, listing.title, "WATCH", 100, 100, 0, 0,
                                          "NOT_ON_WANT_LIST", "", 100, 3, "Synthetic")
        for boundary in ("listing", "impact", "intelligence"):
            with self.subTest(boundary=boundary):
                attached = review if boundary == "listing" else supported
                acquisition = replace(supported, intelligence_result=review.intelligence_result) if boundary == "intelligence" else supported
                retained_impact = replace(impact, acquisition_decision=review) if boundary == "impact" else impact
                with patch("deal_hunter.ListingAnalyzer.analyze", return_value=replace(analysis, recommendation="WATCH", max_rational_price=100, acquisition_decision=attached)), patch(
                    "deal_hunter.AcquisitionWorkflow.evaluate", return_value=acquisition
                ), patch("deal_hunter.AcquisitionImpactEngine.evaluate", return_value=retained_impact), patch(
                    "deal_hunter.SmartShoppingAssistant.generate_report", return_value=ShoppingRecommendationReport([shopping], best_next_purchase=shopping)
                ):
                    result = self.hunter.analyze_listing(listing)
                self.assertEqual(result.recommendation, "REVIEW")
                self.assertIsNone(result.priority_score)
                self.assertIsNone(result.collection_fit_score)
                self.assertIsNone(result.max_rational_price)

    def test_review_survives_price_extremes(self):
        for price in (0, 0.01, 1, 10000):
            with self.subTest(price=price):
                result = self.hunter.analyze_listing(DealListing(
                    "1901 Newfoundland 50 cents VF20 PCGS silver", price))
                self.assertEqual(result.recommendation, "REVIEW")
                self.assertIsNone(result.collection_fit_score)
                self.assertIsNone(result.priority_score)
                self.assertIsNone(result.max_rational_price)

    def test_review_precedes_every_deal_override(self):
        # Attack WATCH/PASS overrides and favorable BUY conditions.
        for price, fit, priority, flags in (
            (0, 60, 80, []), (10000, 0, 0, []),
            (0.01, 100, 100, []), (5, 0, 80, [RISK_UNCLEAR_CURRENCY]),
            (5, 0, 80, [RISK_POSSIBLE_DAMAGE]),
        ):
            with self.subTest(price=price, fit=fit, flags=flags):
                self.assertEqual(self.hunter._recommendation(
                    "REVIEW", priority, fit, 0, DealListing("coin", price),
                    "", [], flags), "REVIEW")

    def test_review_fit_and_priority_cannot_be_computed(self):
        parsed = self.hunter.parse_listing(DealListing("1901 Newfoundland 50 cents VF20 silver"))
        self.assertIsNone(self.hunter._collection_fit_score("NEEDS_REVIEW", 100, parsed))
        self.assertIsNone(self.hunter._priority_score(100, 100, 100, 100, 0, parsed, "NEEDS_REVIEW"))

    def test_no_upstream_composite_rank_or_best_purchase_is_rebuilt(self):
        listing = DealListing("1901 Newfoundland 50 cents VF20 PCGS", 0.01)
        candidate = ListingAnalyzer(self.items).to_candidate_item(listing.to_listing_candidate())
        upstream = SmartShoppingAssistant(self.items).generate_report([
            ShoppingCandidate(listing.title, candidate=candidate, asking_price=0.01)
        ], include_want_list_targets=False)
        self.assertIsNone(upstream.best_next_purchase)
        self.assertIsNone(upstream.recommendations[0].rank)
        self.assertIsNone(upstream.recommendations[0].opportunity_score)
        result = self.hunter.analyze_listing(listing)
        self.assertIsNone(result.priority_score)
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertFalse(any("best next" in reason.lower() for reason in result.reasons))

    def test_maximum_price_is_not_replaced_with_asking_or_zero(self):
        listing = DealListing("1901 Newfoundland 50 cents VF20 PCGS", 20)
        candidate = ListingAnalyzer(self.items).to_candidate_item(listing.to_listing_candidate())
        self.assertIsNone(AcquisitionWorkflow(self.items).evaluate(candidate).max_rational_price)
        self.assertIsNone(self.hunter.analyze_listing(listing).max_rational_price)

    def test_withholding_duplicate_evidence_has_no_score_benefit(self):
        listing = DealListing("1900 Newfoundland 50 cents VF20 ICCS", 1)
        for items in (self.items, [], [make_item("unknown-year", "Newfoundland", "50 cents", "", "VF-20")]):
            with self.subTest(holdings=len(items)):
                result = DealHunter(items).analyze_listing(listing)
                self.assertEqual(result.recommendation, "REVIEW")
                self.assertIsNone(result.priority_score)
                self.assertIsNone(result.collection_fit_score)
                self.assertFalse(any("duplicate" in reason.lower() for reason in result.reasons))
                self.assertNotIn("already have a similar item", result.counterargument)

    def test_triplet_grade_and_upgrade_words_have_no_authority(self):
        for grade in ("VF20", "EF40", "VG8"):
            with self.subTest(grade=grade):
                result = self.hunter.analyze_listing(DealListing(
                    f"1900 Newfoundland 50 cents {grade} ICCS upgrade", 1,
                    description="upgrade fills collection gap; not duplicate"))
                self.assertEqual(result.recommendation, "REVIEW")
                self.assertIsNone(result.collection_fit_score)
                self.assertIsNone(result.priority_score)
                self.assertFalse(any("upgrade" in reason.lower() or "gap" in reason.lower()
                                     for reason in result.reasons))

    def test_incomplete_candidate_empty_collection_remains_review(self):
        result = DealHunter([]).analyze_listing(DealListing("Canada silver", 1))
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertEqual(result.collection_status, "needs review")
        self.assertIsNone(result.collection_fit_score)
        self.assertIsNone(result.priority_score)
        self.assertIsNone(result.max_rational_price)

    def test_collector_interest_and_market_observation_are_descriptive(self):
        result = self.hunter.analyze_listing(DealListing("1901 Newfoundland 50 cents VF20 PCGS", 1))
        self.assertIn("Explicit WANT_LIST match", result.reasons)
        self.assertTrue(any("observed" in reason.lower() for reason in result.reasons))
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertIsNone(result.collection_fit_score)
        self.assertIsNone(result.priority_score)

    def test_independent_facts_and_warnings_survive_review(self):
        listing = DealListing("1901 Newfoundland 50 cents VF20 PCGS damaged lot of coins",
                              10000, 40, seller="Synthetic seller", source="Manual",
                              listing_url="https://example.invalid/coin", currency="USD")
        result = self.hunter.analyze_listing(listing)
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertEqual(result.listing.total_cost, 10040)
        self.assertEqual(result.listing.price_cad, 10000)
        self.assertEqual(result.listing.shipping_cad, 40)
        self.assertEqual(result.listing.seller, "Synthetic seller")
        self.assertEqual(result.listing.source, "Manual")
        self.assertEqual(result.listing.listing_url, "https://example.invalid/coin")
        self.assertEqual(result.parsed_candidate.certifier, "PCGS")
        for flag in (RISK_HIGH_SHIPPING, RISK_POSSIBLE_DAMAGE, RISK_LOT_LISTING, RISK_UNCLEAR_CURRENCY):
            self.assertIn(flag, result.risk_flags)
        self.assertGreater(result.risk_score, 0)

    def test_nulls_and_unranked_order_survive_exports(self):
        listings = [DealListing("Canada silver", 10000),
                    DealListing("1901 Newfoundland 50 cents VF20 PCGS", 1)]
        report = self.hunter.generate_report(listings)
        self.assertEqual([row.listing.title for row in report.results], [row.title for row in listings])
        payload = json.loads(json.dumps(report.to_dict()))
        for row in payload["results"]:
            for key in ("priority_score", "collection_fit_score", "max_rational_price"):
                self.assertIsNone(row[key])
        text = report.format_markdown()
        self.assertIn("Priority score: unavailable", text)
        self.assertIn("Collection-fit score: unavailable", text)
        self.assertIn("Max rational price CAD: unavailable", text)
        self.assertIn("unranked", text.lower())
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "report.csv")
            report.export_csv(path)
            with open(path, encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    for key in ("priority_score", "collection_fit_score", "max_rational_price"):
                        self.assertEqual(row[key], "unavailable")


if __name__ == "__main__":
    unittest.main()
