"""Tests for the offline Listing Analyzer workflow."""

import os
import tempfile
import unittest
import json
from dataclasses import replace
from unittest.mock import patch

from openpyxl import Workbook

from coin_collection import CoinItem
from focused_collection_intelligence import MatchStatus
from legacy_portfolio_importer import LegacyWantListIntent
from listing_analyzer import ListingAnalyzer, ListingCandidate, is_valid_listing_url
from acquisition_workflow import AcquisitionWorkflow
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
        self.assertEqual(result.intelligence_result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertEqual(result.recommendation, "REVIEW")

    def test_duplicate_listing(self):
        analyzer = ListingAnalyzer([
            make_item("1", "Canada", "1 cent", "1967", "VF-30")
        ])

        result = analyzer.analyze(ListingCandidate(
            title="1967 Canada 1 cent VF30",
            price=5,
        ))

        self.assertEqual(result.duplicate_status, "UNRESOLVED")
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertIsNone(result.max_rational_price)

    def test_upgrade_listing(self):
        analyzer = ListingAnalyzer([
            make_item("1", "Canada", "10 cents", "1911", "VF-20")
        ])

        result = analyzer.analyze(ListingCandidate(
            title="1911 Canada 10 cents EF40 PCGS",
            price=80,
            shipping=5,
        ))

        self.assertEqual(result.upgrade_status, "UNRESOLVED")
        self.assertEqual(result.recommendation, "REVIEW")

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

        self.assertEqual(result.intelligence_result.match_status, MatchStatus.NEEDS_REVIEW)
        self.assertIsNone(result.collection_impact)
        self.assertEqual(result.recommendation, "REVIEW")

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
        self.assertEqual(result.recommendation, "REVIEW")


class TestListingContainment(unittest.TestCase):
    """Unresolved advice cannot gain authority at the listing boundary."""

    def test_real_review_contains_injected_stale_impact_before_serialization(self):
        from acquisition_impact import AcquisitionImpactEngine

        analyzer = ListingAnalyzer([])
        listing = ListingCandidate("1967 Canada 1 cent VF30 damaged lot USD", price=25, shipping=3,
                                   url="https://example.com/synthetic", seller="Synthetic seller", source="Manual")
        candidate = analyzer.to_candidate_item(listing)
        stale = replace(AcquisitionImpactEngine([]).evaluate(candidate), collection_impact="COLLECTION_GAP",
                        impact_score=40, quality_delta=2, completion_delta=3,
                        upgrade_impact="REPLACE_EXISTING", recommendation_reasoning=["Collection Gap", "Replace existing"])
        with patch("listing_analyzer.AcquisitionImpactEngine.evaluate", return_value=stale):
            result = analyzer.analyze(listing)
        self.assertEqual(result.acquisition_decision.recommendation, "REVIEW")
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertEqual(result.ownership_status, "UNRESOLVED")
        payload = json.loads(json.dumps(result.to_dict()))
        for name in ("collection_impact", "acquisition_impact_score", "quality_impact", "completion_impact"):
            with self.subTest(field=name):
                self.assertIsNone(getattr(result, name))
                self.assertIsNone(payload[name])
        for name in ("collection_impact", "impact_score", "quality_delta", "completion_delta", "upgrade_impact"):
            self.assertIsNone(getattr(result.acquisition_impact_report, name))
        self.assertNotIn("Collection Gap", result.recommendation_reasoning)
        self.assertNotIn("Replace existing", result.recommendation_reasoning)
        self.assertEqual(payload["listing"]["total_cost"], 28)
        self.assertEqual(payload["listing"]["seller"], "Synthetic seller")
        self.assertEqual(result.candidate.grade, "VF-30")
        for risk in ("damage", "lot", "currency"):
            self.assertTrue(any(risk in warning.lower() for warning in result.warnings))
        # Containment must not alter the supplied upstream report.
        self.assertEqual(stale.impact_score, 40)

    def test_upstream_review_keeps_ownership_and_duplicate_unresolved(self):
        result = ListingAnalyzer([]).analyze(ListingCandidate("1967 Canada 1 cent VF30", price=5))
        self.assertEqual(result.acquisition_decision.collection_intelligence_status, "NEEDS_REVIEW")
        self.assertEqual(result.ownership_status, "UNRESOLVED")
        self.assertEqual(result.duplicate_status, "UNRESOLVED")
        self.assertEqual(result.recommendation, "REVIEW")

    def test_no_supported_match_does_not_establish_newness(self):
        result = ListingAnalyzer([]).analyze(ListingCandidate("1967 Canada 1 cent VF30", price=5))
        self.assertIsNone(result.intelligence_result.best_existing_match)
        self.assertEqual(result.ownership_status, "UNRESOLVED")
        self.assertIsNone(result.collection_impact)
        self.assertNotIn("No current owned match", json.dumps(result.to_dict()))
        self.assertNotIn("No current owned match", result.acquisition_decision.owned_current_match_summary)

    def test_unresolved_duplicate_never_receives_numeric_priority(self):
        for holdings in ([], [make_item("1", "Canada", "1 cent", "1967", "VF-30")]):
            with self.subTest(holdings=bool(holdings)):
                result = ListingAnalyzer(holdings).analyze(ListingCandidate("1967 Canada 1 cent VF30", price=5))
                self.assertEqual(result.duplicate_status, "UNRESOLVED")
                self.assertIsNone(result.priority_score)

    def test_unavailable_maximum_price_is_not_zero(self):
        result = ListingAnalyzer([]).analyze(ListingCandidate("1967 Canada 1 cent VF30", price=5))
        self.assertIsNone(result.max_rational_price)

    def test_unavailable_impact_and_deltas_remain_unavailable(self):
        result = ListingAnalyzer([]).analyze(ListingCandidate("1967 Canada 1 cent VF30", price=5))
        self.assertIsNone(result.acquisition_impact_score)
        self.assertIsNone(result.quality_impact)
        self.assertIsNone(result.completion_impact)
        self.assertIsNone(result.collection_impact)

    def test_higher_grade_triplet_cannot_authorize_upgrade_advice(self):
        result = ListingAnalyzer([make_item("1", "Canada", "10 cents", "1911", "VF-20")]).analyze(
            ListingCandidate("1911 Canada 10 cents EF40 PCGS", price=80))
        self.assertEqual(result.ownership_status, "UNRESOLVED")
        self.assertEqual(result.upgrade_status, "UNRESOLVED")
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertIsNone(result.priority_score)

    def test_equal_grade_triplet_cannot_authorize_duplicate_pass(self):
        result = ListingAnalyzer([make_item("1", "Canada", "1 cent", "1967", "VF-30")]).analyze(
            ListingCandidate("1967 Canada 1 cent VF30", price=5))
        self.assertEqual(result.duplicate_status, "UNRESOLVED")
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertIsNone(result.max_rational_price)

    def test_missing_holding_year_cannot_establish_collection_gap(self):
        result = ListingAnalyzer([make_item("1", "Canada", "1 cent", "", "VF-30")]).analyze(
            ListingCandidate("1967 Canada 1 cent VF30", price=5))
        self.assertEqual(result.ownership_status, "UNRESOLVED")
        self.assertIsNone(result.collection_impact)
        self.assertNotIn("Collection Gap", result.recommendation_reasoning)

    def test_incomplete_candidate_and_empty_collection_are_unresolved(self):
        result = ListingAnalyzer([]).analyze(ListingCandidate("Unidentified coin", price=1))
        self.assertEqual(result.ownership_status, "UNRESOLVED")
        self.assertEqual(result.duplicate_status, "UNRESOLVED")
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertIsNone(result.priority_score)

    def test_upgrade_word_supplies_no_identity_authority(self):
        analyzer = ListingAnalyzer([make_item("1", "Canada", "10 cents", "1911", "VF-20")])
        for title in ("1911 Canada 10 cents EF40 PCGS", "1911 Canada 10 cents EF40 PCGS upgrade"):
            with self.subTest(title=title):
                result = analyzer.analyze(ListingCandidate(title, price=80))
                self.assertEqual(result.ownership_status, "UNRESOLVED")
                self.assertEqual(result.duplicate_status, "UNRESOLVED")
                self.assertEqual(result.upgrade_status, "UNRESOLVED")
                self.assertEqual(result.recommendation, "REVIEW")
                self.assertIsNone(result.priority_score)
                self.assertIsNone(result.acquisition_impact_score)
                for canonical in ("type_design", "reference", "issuer", "status"):
                    self.assertNotIn(canonical, result.candidate.__dict__)

    def test_explicit_interest_is_visible_without_purchase_or_ranking(self):
        result = ListingAnalyzer([], [make_intent("Newfoundland 50 cents 1904")]).analyze(
            ListingCandidate("1904 Newfoundland 50 cents VF20 PCGS", price=1))
        self.assertEqual(result.want_list_status, "ON_WANT_LIST")
        self.assertIn("Explicit WANT_LIST Target", result.recommendation_reasoning)
        self.assertEqual(result.ownership_status, "UNRESOLVED")
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertIsNone(result.priority_score)

    def test_listing_risks_and_metadata_survive_unresolved_identity(self):
        result = ListingAnalyzer([]).analyze(ListingCandidate(
            "1904 Newfoundland 50 cents VF20 PCGS damaged lot USD", price="$10", shipping="2.50",
            url="https://example.com/item/ref-42", seller="Synthetic seller", source="Manual",
            notes="cleaned", description="multiple coins"))
        self.assertEqual(result.ownership_status, "UNRESOLVED")
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertEqual(result.listing.total_cost, 12.5)
        self.assertEqual(result.candidate.asking_price, 12.5)
        self.assertEqual(result.candidate.grade, "VF-20")
        self.assertEqual(result.candidate.certifier, "PCGS")
        self.assertEqual(result.listing.url, "https://example.com/item/ref-42")
        self.assertEqual(result.listing.seller, "Synthetic seller")
        self.assertEqual(result.listing.source, "Manual")
        self.assertTrue(any("damage" in warning.lower() or "clean" in warning.lower() for warning in result.warnings))
        self.assertTrue(any("lot" in warning.lower() for warning in result.warnings))
        self.assertTrue(any("currency" in warning.lower() for warning in result.warnings))

    def test_serialization_preserves_nulls_and_unresolved_states(self):
        result = ListingAnalyzer([]).analyze(ListingCandidate("1967 Canada 1 cent VF30", price=5))
        payload = json.loads(json.dumps(result.to_dict()))
        for key in ("priority_score", "max_rational_price", "acquisition_impact_score",
                    "quality_impact", "completion_impact", "collection_impact"):
            with self.subTest(key=key):
                self.assertIsNone(payload[key])
        for key in ("ownership_status", "duplicate_status", "upgrade_status"):
            self.assertEqual(payload[key], "UNRESOLVED")

    def test_retained_raw_intelligence_cannot_bypass_acquisition_containment(self):
        # Inject legacy summaries that the workflow may retain under REVIEW.
        # Current focused intelligence no longer emits these, so exercise the
        # downstream trust boundary with a real decision and altered raw context.
        analyzer = ListingAnalyzer([])
        listing = ListingCandidate("1967 Canada 1 cent VF30", price=5)
        decision = AcquisitionWorkflow([]).evaluate(analyzer.to_candidate_item(listing))
        for status in (MatchStatus.SAME_GRADE_DUPLICATE, MatchStatus.BETTER_GRADE_UPGRADE,
                       MatchStatus.COLLECTION_GAP, MatchStatus.WANT_LIST_MATCH, "DIFFERENT_ISSUE", None):
            with self.subTest(status=status):
                raw = replace(decision.intelligence_result, match_status=status, collection_impact="COLLECTION_GAP")
                retained = replace(decision, intelligence_result=raw)
                with patch("listing_analyzer.AcquisitionWorkflow.evaluate", return_value=retained):
                    result = analyzer.analyze(listing)
                self.assertEqual(result.ownership_status, "UNRESOLVED")
                self.assertEqual(result.duplicate_status, "UNRESOLVED")
                self.assertIsNone(result.collection_impact)
                self.assertIsNone(result.priority_score)
                self.assertEqual(result.recommendation, "REVIEW")

    def test_authoritative_review_status_cannot_be_strengthened_by_purchase_fields(self):
        analyzer = ListingAnalyzer([])
        listing = ListingCandidate("1967 Canada 1 cent VF30", price=5)
        decision = AcquisitionWorkflow([]).evaluate(analyzer.to_candidate_item(listing))
        for status in ("NEEDS_REVIEW", "REVIEW", None, "DIFFERENT_ISSUE"):
            with self.subTest(status=status):
                conflicting = replace(decision, collection_intelligence_status=status,
                                      recommendation="BUY", max_rational_price=100, upgrade_status="UPGRADE",
                                      intelligence_result=None)
                with patch("listing_analyzer.AcquisitionWorkflow.evaluate", return_value=conflicting):
                    result = analyzer.analyze(listing)
                self.assertEqual(result.recommendation, "REVIEW")
                self.assertEqual(result.ownership_status, "UNRESOLVED")
                self.assertEqual(result.duplicate_status, "UNRESOLVED")
                self.assertEqual(result.upgrade_status, "UNRESOLVED")
                self.assertIsNone(result.max_rational_price)


if __name__ == "__main__":
    unittest.main()
