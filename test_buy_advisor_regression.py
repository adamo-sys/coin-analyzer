"""Regression tests for Buy Advisor recommendations."""

import os
import shutil
import tempfile
import unittest

from buy_advisor import BuyAdvisor
from coin_collection import CoinCollection, CoinItem
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

    def test_duplicate_purchase_is_pass(self):
        rec = self.advisor.advise(
            "Argentina",
            "1.0",
            "1960",
            asking_price=2.00,
            shipping=1.00,
            tax_fees=0.20,
        )

        self.assertTrue(rec.already_owned)
        self.assertEqual(rec.recommendation, "Duplicate")
        self.assertEqual(rec.purchase_verdict, "PASS")

    def test_missing_canadian_key_date_with_good_price_is_buy_now(self):
        rec = self.advisor.advise(
            "Canada",
            "1 cent",
            "1967",
            asking_price=0.50,
            shipping=2.00,
            tax_fees=0.10,
            estimated_market_value=10.00,
        )

        self.assertFalse(rec.already_owned)
        self.assertEqual(rec.recommendation, "Buy")
        self.assertEqual(rec.price_verdict, "Good price")
        self.assertEqual(rec.purchase_verdict, "BUY NOW")

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

        self.assertEqual(rec.recommendation, "Buy")
        self.assertEqual(rec.price_verdict, "Overpriced")
        self.assertEqual(rec.purchase_verdict, "PASS")

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

        self.assertEqual(rec.recommendation, "Neutral")
        self.assertEqual(rec.price_verdict, "Good price")
        self.assertEqual(rec.purchase_verdict, "BID ONLY")

    def test_no_asking_price_for_buy_is_bid_only(self):
        rec = self.advisor.advise(
            "Canada",
            "1 cent",
            "1967",
            estimated_market_value=10.00,
        )

        self.assertEqual(rec.recommendation, "Buy")
        self.assertEqual(rec.price_verdict, "No asking price entered")
        self.assertEqual(rec.purchase_verdict, "BID ONLY")

    def test_missing_value_data_warns_and_cannot_price_check(self):
        rec = self.advisor.advise(
            "Canada",
            "1 cent",
            "1967",
            asking_price=5.00,
            shipping=2.00,
            tax_fees=0.50,
        )

        self.assertFalse(rec.value_data_available)
        self.assertEqual(rec.max_rational_bid, 0.0)
        self.assertEqual(rec.price_verdict, "Cannot price-check")
        self.assertEqual(rec.purchase_verdict, "WATCHLIST")

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

        self.assertIn("+50 Explicit WANT_LIST target", rec.collection_intelligence_factors)
        self.assertIn("+30 Missing Newfoundland date", rec.collection_intelligence_factors)
        self.assertIn("+20 Completes date run", rec.collection_intelligence_factors)
        self.assertIn("+25 Newfoundland priority", rec.collection_intelligence_factors)
        self.assertGreaterEqual(rec.collection_impact_score, 125)
        self.assertGreaterEqual(rec.adam_priority_score, rec.collection_impact_score)

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

        self.assertIn("+25 Fills collection gap", rec.collection_intelligence_factors)
        self.assertIn("+20 Completes date run", rec.collection_intelligence_factors)
        self.assertIn("+30 1859 Large Cent target", rec.collection_intelligence_factors)

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
