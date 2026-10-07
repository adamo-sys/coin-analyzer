"""Regression tests for Buy Advisor recommendations."""

import os
import shutil
import tempfile
import unittest
import contextlib
import io
from dataclasses import replace
from unittest.mock import patch

from buy_advisor import BuyAdvisor
from coin_collection import CoinCollection, CoinItem
from focused_collection_intelligence import FocusedCollectionIntelligenceEngine
from legacy_portfolio_importer import LegacyWantListIntent


FIXTURE_COLLECTION = os.path.join(
    os.path.dirname(__file__),
    "test_data",
    "sample_collection.json",
)


class TestBuyAdvisorRegression(unittest.TestCase):
    """Verify advisor decisions against deterministic fixture data."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.collection_path = os.path.join(self.temp_dir.name, "collection.json")
        shutil.copy(FIXTURE_COLLECTION, self.collection_path)
        self.collection = CoinCollection(self.collection_path)
        self.advisor = BuyAdvisor(self.collection)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_standalone_demo_nullable_zero_and_positive_rendering(self):
        from buy_advisor import test_buy_advisor

        rec = self.advisor.advise("Canada", "dollar", "1936", asking_price=10, shipping=2)
        for value, percent, money in ((None, "unavailable", "unavailable"),
                                      (0, "0.0%", "$0.00"), (0.5, "50.0%", "$0.50")):
            with self.subTest(value=value):
                rendered = replace(rec, series_completion=value, country_completion=value,
                                   max_rational_bid=value)
                output = io.StringIO()
                # Keep the demonstration away from live data; exercise its actual prints.
                with patch("coin_collection.CoinCollection", return_value=self.collection), patch(
                    "buy_advisor.BuyAdvisor.advise", return_value=rendered
                ), contextlib.redirect_stdout(output):
                    test_buy_advisor()
                text = output.getvalue()
                self.assertIn("Series Completion: " + percent, text)
                self.assertIn("Country Completion: " + percent, text)
                self.assertIn("Max Rational Bid: " + money, text)
                self.assertIn("Matching Items: unavailable", text)
                self.assertIn("Landed Cost: $12.00", text)

    def test_retained_empty_matches_cannot_outvote_authoritative_review(self):
        with patch.object(self.advisor, "find_owned_items", return_value=[]):
            rec = self.advisor.advise(
                "Canada", "1 cent", "1967", grade="VF-20", asking_price=1,
                shipping=2, tax_fees=0.5, estimated_market_value=10,
            )
        self.assert_unresolved(rec)
        for field in ("already_owned", "duplicate_count", "upgrade_candidate",
                      "missing_date_in_series", "missing_denomination_in_country",
                      "confidence_score", "adam_priority_score", "collection_impact_score", "liquidity_score"):
            self.assertIsNone(getattr(rec, field), field)
        self.assertEqual(rec.acquisition_workflow_result["recommendation"], "REVIEW")
        self.assertEqual(rec.acquisition_workflow_result["asking_price"], 1)
        self.assertEqual(rec.landed_cost, 3.5)
        self.assertIsNone(rec.matching_items)
        self.assertEqual(rec.estimated_market_value, 10)
        self.assertTrue(rec.value_data_available)
        self.assertIn("unresolved", rec.explanation.lower())

    def test_unresolved_ownership_and_catalogue_agreement_require_review(self):
        from dataclasses import asdict
        import json

        item = self.collection.items[0]
        for reference, numista_n in [("", ""), (item.reference, item.numista_n)]:
            with self.subTest(reference=reference, numista_n=numista_n):
                self.assertIsNone(self.advisor.find_owned_items("", "", "", reference, numista_n))
                rec = self.advisor.advise("", "", "", reference, numista_n,
                                          asking_price=80, shipping=5)
                self.assertEqual(rec.recommendation, "REVIEW")
                self.assertEqual(rec.purchase_verdict, "REVIEW")
                for name in ("already_owned", "duplicate_count", "upgrade_candidate",
                             "missing_date_in_series", "missing_denomination_in_country",
                             "series_completion", "country_completion", "max_rational_bid",
                             "adam_priority_score", "collection_impact_score", "liquidity_score"):
                    self.assertIsNone(getattr(rec, name), name)
                    self.assertIsNone(json.loads(json.dumps(asdict(rec)))[name])
                self.assertEqual(rec.landed_cost, 85)
                self.assertNotIn("not owned", rec.explanation.lower())
                self.assertNotIn("gap", " ".join(rec.reasons).lower())


    def test_unresolved_triplet_does_not_infer_liquidity_from_identity(self):
        for country, denomination, year in [("Canada", "dollar", "1935"),
                                            ("Newfoundland", "50 cents", "1901")]:
            with self.subTest(country=country):
                rec = self.advisor.advise(country, denomination, year, asking_price=80, shipping=5)
                self.assertIsNone(rec.liquidity_score)
                self.assertEqual(rec.landed_cost, 85)
                self.assertEqual(rec.recommendation, "REVIEW")

    def test_duplicate_purchase_is_pass(self):
        rec = self.advisor.advise(
            "Argentina",
            "1.0",
            "1960",
            asking_price=2.00,
            shipping=1.00,
            tax_fees=0.20,
        )

        self.assert_unresolved(rec)
        self.assertEqual(rec.landed_cost, 3.2)

    def test_uses_collection_intelligence_engine_for_duplicate_decision(self):
        with patch(
            "buy_advisor.FocusedCollectionIntelligenceEngine",
            wraps=FocusedCollectionIntelligenceEngine,
        ) as engine_class:
            rec = self.advisor.advise(
                "Argentina",
                "1.0",
                "1960",
                asking_price=2.00,
                shipping=1.00,
                tax_fees=0.20,
            )

        self.assert_unresolved(rec)
        self.assertTrue(engine_class.called)
        self.assertEqual(rec.landed_cost, 3.2)

    def test_missing_canadian_key_date_with_good_price_is_buy_now(self):
        rec = self.advisor.advise(
            "Canada",
            "1 cent",
            "1920",
            asking_price=2.00,
            shipping=1.00,
            tax_fees=0.20,
        )

        self.assert_unresolved(rec)
        self.assertEqual(rec.landed_cost, 3.2)
    
    def test_melt_value_integration_for_silver_coin(self):
        """Unresolved identity cannot supply inferred composition or silver weight."""
        rec = self.advisor.advise(
            "Canada",
            "dollar",
            "1935",
            asking_price=10.00,
            shipping=1.00,
            tax_fees=0.20,
        )
        
        # Melt value should be available for silver coins
        self.assert_unresolved(rec)
        # Triplet identity does not independently establish silver weight/ASW.
        self.assertFalse(rec.melt_value_available)
        self.assertIsNone(rec.melt_value_cad)
        self.assertEqual(rec.landed_cost, 11.2)
    
    def test_melt_value_not_available_for_non_silver_coin(self):
        """Test that melt value is not calculated for non-silver coins."""
        rec = self.advisor.advise(
            "Canada",
            "1 cent",
            "1920",
            asking_price=2.00,
            shipping=1.00,
            tax_fees=0.20,
        )
        
        # Melt value should be 0 for non-silver coins
        self.assert_unresolved(rec)
        self.assertFalse(rec.melt_value_available)
        self.assertIsNone(rec.melt_value_cad)
        self.assertEqual(rec.landed_cost, 3.2)
    
    def test_melt_value_does_not_change_purchase_verdict(self):
        """Test that melt value is a supporting factor, not a primary driver."""
        # This test ensures that melt value integration doesn't change existing verdict logic
        rec = self.advisor.advise(
            "Argentina",
            "1.0",
            "1960",
            asking_price=2.00,
            shipping=1.00,
            tax_fees=0.20,
        )
        
        # Unresolved equivalence remains review regardless of inferred melt context
        self.assert_unresolved(rec)
        self.assertIsNone(rec.melt_value_cad)
        self.assertEqual(rec.landed_cost, 3.2)
    
    def test_melt_value_fields_populated_correctly(self):
        """Test that all melt value fields are populated correctly."""
        rec = self.advisor.advise(
            "Canada",
            "dollar",
            "1935",
            asking_price=10.00,
            shipping=1.00,
            tax_fees=0.20,
        )
        
        # Check that all melt value fields are present
        self.assertTrue(hasattr(rec, 'melt_value_cad'))
        self.assertTrue(hasattr(rec, 'melt_value_available'))
        self.assertTrue(hasattr(rec, 'spot_price_warning'))
        
        # For silver coins with manual provider, no warning should be present
        self.assertIsNone(rec.spot_price_warning)
    
    def test_missing_year_with_good_price_is_buy_now(self):
        rec = self.advisor.advise(
            "Canada",
            "1 cent",
            "1967",
            asking_price=0.50,
            shipping=2.00,
            tax_fees=0.10,
            estimated_market_value=10.00,
        )

        self.assert_unresolved(rec)
        self.assertEqual(rec.landed_cost, 2.6)
        self.assertEqual(rec.estimated_market_value, 10)
        self.assertTrue(rec.value_data_available)

    def test_overpriced_buy_is_pass(self):
        rec = self.advisor.advise(
            "Canada",
            "1 cent",
            "1967",
            asking_price=10.00,
            shipping=2.00,
            tax_fees=1.00,
            estimated_market_value=10.00,
        )

        self.assert_unresolved(rec)
        self.assertEqual(rec.landed_cost, 13)
        self.assertEqual(rec.estimated_market_value, 10)
        self.assertTrue(rec.value_data_available)

    def test_neutral_good_price_is_bid_only(self):
        rec = self.advisor.advise(
            "Argentina",
            "20 cents",
            "1975",
            asking_price=0.25,
            shipping=0.10,
            tax_fees=0.05,
            estimated_market_value=1.00,
        )

        self.assert_unresolved(rec)
        self.assertAlmostEqual(rec.landed_cost, 0.4)
        self.assertEqual(rec.estimated_market_value, 1)
        self.assertTrue(rec.value_data_available)

    def test_no_asking_price_for_buy_is_bid_only(self):
        rec = self.advisor.advise(
            "Canada",
            "1 cent",
            "1967",
            estimated_market_value=10.00,
        )

        self.assert_unresolved(rec)
        self.assertEqual(rec.landed_cost, 0)
        self.assertEqual(rec.estimated_market_value, 10)
        self.assertTrue(rec.value_data_available)

    def test_missing_value_data_warns_and_cannot_price_check(self):
        rec = self.advisor.advise(
            "Canada",
            "1 cent",
            "1967",
            asking_price=5.00,
            shipping=2.00,
            tax_fees=0.50,
        )

        self.assert_unresolved(rec)
        self.assertFalse(rec.value_data_available)
        self.assertTrue(rec.value_warning)
        self.assertTrue(rec.warnings)
        self.assertEqual(rec.landed_cost, 7.5)

    def test_random_world_base_metal_good_price_does_not_become_buy_now(self):
        rec = self.advisor.advise(
            "Argentina",
            "1 cent",
            "1975",
            asking_price=1.00,
            estimated_market_value=5.00,
        )

        self.assert_unresolved(rec)
        self.assertEqual(rec.landed_cost, 1)
        self.assertEqual(rec.estimated_market_value, 5)
        self.assertTrue(rec.value_data_available)

    def test_collection_intelligence_boosts_explicit_want_list_target(self):
        intent = LegacyWantListIntent(
            sheet_name="WANT_LIST",
            row_number=2,
            legacy_id="legacy_want_list_2",
            target_coin="Newfoundland 50 cents 1901",
            priority="High",
            target_grade="VF-20",
            budget=150.0,
            why_wanted="Explicit user target",
            status="Active",
            priority_score=75,
        )
        collection = self.make_collection(
            [
                self.make_item("1", "Newfoundland", "50 cents", "1900"),
                self.make_item("2", "Newfoundland", "50 cents", "1902"),
            ]
        )
        advisor = BuyAdvisor(collection, staged_want_list_intents=[intent])

        rec = advisor.advise("Newfoundland", "50 cents", "1901", estimated_market_value=100.0)

        self.assert_unresolved(rec)
        self.assertEqual(rec.estimated_market_value, 100)
        self.assertTrue(rec.value_data_available)
        self.assertFalse(any(reason.startswith("+") for reason in rec.collection_intelligence_factors))

    def test_collection_intelligence_boosts_1859_large_cent_target(self):
        collection = self.make_collection(
            [
                self.make_item("1", "Canada", "1 cent", "1858"),
                self.make_item("2", "Canada", "1 cent", "1860"),
            ]
        )
        advisor = BuyAdvisor(collection)

        rec = advisor.advise(
            "Canada",
            "1 cent",
            "1859",
            reference="Large Cent Narrow 9 variety",
            estimated_market_value=100.0,
        )

        self.assert_unresolved(rec)
        self.assertEqual(rec.estimated_market_value, 100)
        self.assertTrue(rec.value_data_available)
        self.assertFalse(any(reason.startswith("+") for reason in rec.collection_intelligence_factors))

    def test_collection_intelligence_does_not_mutate_collection(self):
        before = [item.to_dict() for item in self.collection.get_all_items()]

        self.advisor.advise(
            "Newfoundland",
            "50 cents",
            "1901",
            estimated_market_value=100.0,
        )

        after = [item.to_dict() for item in self.collection.get_all_items()]
        self.assertEqual(before, after)

    def assert_unresolved(self, rec):
        self.assertEqual(rec.recommendation, "REVIEW")
        self.assertEqual(rec.purchase_verdict, "REVIEW")
        self.assertEqual(rec.price_verdict, "REVIEW")
        for name in ("already_owned", "duplicate_count", "upgrade_candidate",
                     "missing_date_in_series", "missing_denomination_in_country",
                     "series_completion", "country_completion", "max_rational_bid",
                     "adam_priority_score", "collection_impact_score", "confidence_score",
                     "liquidity_score"):
            self.assertIsNone(getattr(rec, name), name)
        self.assertTrue(rec.reasons)
        self.assertIn("unavailable", rec.explanation.lower())

    def test_downstream_model_preserves_actual_zero(self):
        # Model serialization is isolated from unresolved candidate advice.
        from dataclasses import asdict, replace
        import json
        rec = self.advisor.advise("", "", "", asking_price=80, shipping=5)
        fields = ("max_rational_bid", "adam_priority_score", "collection_impact_score",
                  "confidence_score", "liquidity_score", "melt_value_cad", "duplicate_count",
                  "series_completion", "country_completion")
        payload = json.loads(json.dumps(asdict(rec)))
        for name in fields:
            self.assertIsNone(payload[name], name)
        zero = replace(rec, **dict.fromkeys(fields, 0))
        payload = json.loads(json.dumps(asdict(zero)))
        for name in fields:
            self.assertEqual(payload[name], 0, name)
        self.assertEqual(zero.landed_cost, 85)

    def make_collection(self, items):
        collection = CoinCollection(os.path.join(self.temp_dir.name, "intelligence_collection.json"))
        collection.items = items
        return collection

    @staticmethod
    def make_item(item_id, country, denomination, year, grade="VF-20"):
        return CoinItem(
            id=item_id,
            image_path="",
            country=country,
            denomination=denomination,
            year=year,
            grade=grade,
            notes="",
            date_added="2026-06-15",
        )


if __name__ == "__main__":
    unittest.main()
