"""Tests for local-only Market Awareness Layer."""

import os
import tempfile
import unittest

from acquisition_impact import AcquisitionImpactEngine
from collection_dashboard import CollectionDashboard
from coin_collection import CoinItem
from focused_collection_intelligence import CandidateItem
from market_awareness import (
    AuctionRecord,
    MarketAwarenessEngine,
    ObservedPriceRecord,
    PurchaseRecord,
    SaleRecord,
)


def make_item(item_id, country, denomination, year, grade, **overrides):
    data = {
        "id": item_id,
        "image_path": "",
        "country": country,
        "denomination": denomination,
        "year": year,
        "grade": grade,
        "notes": "",
        "date_added": "2026-06-17",
    }
    data.update(overrides)
    return CoinItem(**data)


class TestMarketAwarenessEngine(unittest.TestCase):
    def test_observation_creation_calculates_total_cost(self):
        record = ObservedPriceRecord(
            item_name="1896 Newfoundland 20 cents Large 96",
            country="Newfoundland",
            denomination="20 cents",
            year="1896",
            grade="VF-20",
            observed_price="$24.00",
            shipping="6",
            source="eBay",
        )

        self.assertEqual(record.total_observed_cost, 30.0)
        self.assertEqual(record.source, "eBay")
        self.assertTrue(record.date_observed)

    def test_purchase_creation_calculates_total_cost(self):
        record = PurchaseRecord(
            item="1904H Newfoundland 50 cents EF40",
            purchase_price=120,
            shipping=12.5,
            seller="Local dealer",
            source="Coin show",
        )

        self.assertEqual(record.total_cost, 132.5)
        self.assertEqual(record.seller, "Local dealer")

    def test_sale_creation_calculates_net_proceeds(self):
        record = SaleRecord(
            item="Duplicate Canada dime",
            sale_price=40,
            fees=4.75,
            buyer_source="Local collector",
        )

        self.assertEqual(record.net_proceeds, 35.25)
        self.assertEqual(record.buyer_source, "Local collector")

    def test_auction_tracking_normalizes_status(self):
        won = AuctionRecord("Newfoundland 5 cents", bid_amount=75, winning_bid=70, auction_result="won")
        lost = AuctionRecord("Newfoundland 10 cents", bid_amount=60, winning_bid=85, auction_result="LOST")
        passed = AuctionRecord("World base metal lot", auction_result="skip")

        self.assertEqual(won.auction_result, "Won")
        self.assertEqual(lost.auction_result, "Lost")
        self.assertEqual(passed.auction_result, "Passed")

    def test_dashboard_integration_reports_market_counts(self):
        items = [make_item("1", "Newfoundland", "20 cents", "1896", "VF-20")]
        engine = MarketAwarenessEngine(
            observations=[ObservedPriceRecord("1896 Newfoundland 20 cents", observed_price=24, shipping=6)],
            purchases=[PurchaseRecord("1896 Newfoundland 20 cents", purchase_price=25)],
            sales=[SaleRecord("Duplicate dime", sale_price=40, fees=5)],
            auctions=[AuctionRecord("Newfoundland 5 cents", auction_result="Won")],
        )

        data = CollectionDashboard(items, market_awareness_engine=engine).generate_dashboard()

        self.assertIsNotNone(data.market_report)
        self.assertEqual(data.market_report.summary.observation_count, 1)
        self.assertEqual(data.market_report.summary.purchase_count, 1)
        self.assertEqual(data.market_report.summary.sale_count, 1)
        self.assertEqual(data.market_report.summary.auction_count, 1)
        self.assertTrue(data.market_report.recent_activity)

    def test_acquisition_integration_reports_historical_context(self):
        engine = MarketAwarenessEngine(observations=[
            ObservedPriceRecord("1911 Canada 10 cents", "Canada", "10 cents", "1911", observed_price=18),
            ObservedPriceRecord("1911 Canada 10 cents", "Canada", "10 cents", "1911", observed_price=20),
            ObservedPriceRecord("1911 Canada 10 cents", "Canada", "10 cents", "1911", observed_price=22),
        ])
        candidate = CandidateItem("Canada", "10 cents", "1911", grade="EF-40", asking_price=19)

        report = AcquisitionImpactEngine([], market_awareness_engine=engine).evaluate(candidate)

        self.assertEqual(report.historical_observed_costs, [18.0, 20.0, 22.0])
        self.assertEqual(report.market_context_summary, "Within recent observed range")
        self.assertIn("market_context_summary", report.to_dict())

    def test_export_support_includes_all_record_types(self):
        engine = MarketAwarenessEngine(
            observations=[ObservedPriceRecord("1896 Newfoundland 20 cents", observed_price=24, source="eBay")],
            purchases=[PurchaseRecord("1904H Newfoundland 50 cents", purchase_price=120)],
            sales=[SaleRecord("Duplicate Canada dime", sale_price=40)],
            auctions=[AuctionRecord("Newfoundland 5 cents", auction_result="Lost", winning_bid=80)],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "market.csv")
            md_path = os.path.join(temp_dir, "market.md")

            self.assertTrue(engine.export_csv(csv_path))
            self.assertTrue(engine.export_markdown(md_path))

            with open(csv_path, "r", encoding="utf-8") as handle:
                csv_text = handle.read()
            with open(md_path, "r", encoding="utf-8") as handle:
                markdown_text = handle.read()

        self.assertIn("Observation", csv_text)
        self.assertIn("Purchase", csv_text)
        self.assertIn("Sale", csv_text)
        self.assertIn("Auction", csv_text)
        self.assertIn("# Market Awareness Report", markdown_text)

    def test_photo_vault_reference_ids_are_preserved(self):
        record = PurchaseRecord(
            item="1945 Newfoundland 5 cents AU55",
            purchase_price=90,
            linked_photo_ids=["photo_xsz431"],
        )
        engine = MarketAwarenessEngine(purchases=[record])
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "market.csv")

            self.assertTrue(engine.export_csv(csv_path))

            with open(csv_path, "r", encoding="utf-8") as handle:
                csv_text = handle.read()

        self.assertIn("photo_xsz431", csv_text)


if __name__ == "__main__":
    unittest.main()
