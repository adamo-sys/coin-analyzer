"""Tests for v3.5 external listing connector framework."""

import os
import tempfile
import unittest

from coin_collection import CoinItem
from deal_hunter_ranking import DealHunterRankingEngine
from legacy_portfolio_importer import LegacyWantListIntent
from listing_connectors import (
    AuctionCSVConnector,
    ConnectorRegistry,
    DealerInventoryConnector,
    DuplicateOpportunityDetector,
    GenericCSVConnector,
    NormalizedListing,
    SourceSummaryReport,
    eBayCSVConnector,
)
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord


def make_item(item_id, country, denomination, year, grade):
    return CoinItem(
        id=item_id,
        image_path="",
        country=country,
        denomination=denomination,
        year=year,
        grade=grade,
        notes="",
        date_added="2026-06-21",
    )


def make_intent(target_coin, priority_score=90):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id=f"connector_{target_coin}",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=150.0,
        why_wanted="Connector target",
        status="Active",
        priority_score=priority_score,
    )


class TestListingConnectors(unittest.TestCase):
    def setUp(self):
        self.items = [
            make_item("nf1900", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("nf1902", "Newfoundland", "50 cents", "1902", "VF-20"),
            make_item("ca1911", "Canada", "10 cents", "1911", "VF-20"),
        ]
        self.intents = [make_intent("Newfoundland 50 cents 1901", 95)]
        self.market = MarketAwarenessEngine(observations=[
            ObservedPriceRecord("1901 Newfoundland 50 cents", "Newfoundland", "50 cents", "1901", "VF-20", 90),
        ])

    def _write_csv(self, name, header, rows):
        path = os.path.join(self.temp_dir.name, name)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(",".join(header) + "\n")
            for row in rows:
                handle.write(",".join(row) + "\n")
        return path

    def setUpTemp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def test_normalized_listing_total_cost_and_deal_listing_conversion(self):
        listing = NormalizedListing(
            title="1901 Newfoundland 50 cents VF20",
            price="$80",
            shipping="5",
            source="eBay.ca",
            source_type="eBay CSV",
            connector_name="eBay CSV Connector",
        )
        deal_listing = listing.to_deal_listing()

        self.assertEqual(listing.total_cost, 85)
        self.assertEqual(deal_listing.total_cost, 85)
        self.assertEqual(deal_listing.connector_name, "eBay CSV Connector")
        self.assertEqual(deal_listing.source_type, "eBay CSV")

    def test_ebay_connector_imports_rows(self):
        self.setUpTemp()
        path = self._write_csv(
            "ebay.csv",
            ["title", "price_cad", "shipping_cad", "seller", "listing_url"],
            [["1901 Newfoundland 50 cents VF20", "80", "5", "Seller A", "https://example.test/nf1901"]],
        )

        report = eBayCSVConnector().import_file(path)

        self.assertEqual(report.imported_count, 1)
        self.assertEqual(report.listings[0].source_type, "eBay CSV")
        self.assertEqual(report.validation_report.status, "OK")

    def test_auction_connector_normalizes_aliases(self):
        self.setUpTemp()
        path = self._write_csv(
            "auction.csv",
            ["lot_title", "hammer_price", "auction_house", "url"],
            [["Canada 10 cents 1911 EF40 silver", "70", "Auction House", "https://example.test/lot1"]],
        )

        report = AuctionCSVConnector().import_file(path)

        self.assertEqual(report.imported_count, 1)
        self.assertEqual(report.listings[0].title, "Canada 10 cents 1911 EF40 silver")
        self.assertEqual(report.listings[0].price, 70)
        self.assertEqual(report.listings[0].source_type, "Auction CSV")

    def test_dealer_connector_normalizes_inventory(self):
        self.setUpTemp()
        path = self._write_csv(
            "dealer.csv",
            ["item", "dealer_price", "dealer", "url"],
            [["Newfoundland 5 cents 1945 ICCS", "42", "Dealer One", "https://example.test/dealer1"]],
        )

        report = DealerInventoryConnector().import_file(path)

        self.assertEqual(report.imported_count, 1)
        self.assertEqual(report.listings[0].seller, "Dealer One")
        self.assertEqual(report.listings[0].source_type, "Dealer Inventory")

    def test_generic_connector_uses_common_aliases(self):
        self.setUpTemp()
        path = self._write_csv(
            "generic.csv",
            ["name", "cost", "shipping", "url"],
            [["Canada chartered banknote BCS VF25", "120", "10", "https://example.test/note"]],
        )

        report = GenericCSVConnector().import_file(path)

        self.assertEqual(report.imported_count, 1)
        self.assertEqual(report.listings[0].title, "Canada chartered banknote BCS VF25")
        self.assertEqual(report.listings[0].total_cost, 130)

    def test_validation_reports_malformed_imports(self):
        self.setUpTemp()
        path = self._write_csv(
            "bad.csv",
            ["title", "price_cad", "listing_url", "extra_column"],
            [["", "85", "https://example.test/missing-title", "x"], ["1901 Newfoundland 50 cents VF20", "bad-price", "bad-url", "x"]],
        )

        report = eBayCSVConnector().import_file(path)

        self.assertEqual(report.validation_report.rows_found, 2)
        self.assertEqual(report.validation_report.skipped_rows, 1)
        self.assertTrue(any("missing required title" in warning for warning in report.validation_report.warnings))
        self.assertTrue(any("Malformed price_cad" in warning for warning in report.validation_report.warnings))
        self.assertTrue(any("unsupported URL format" in warning for warning in report.validation_report.warnings))
        self.assertIn("extra_column", report.validation_report.unsupported_columns)

    def test_source_summary_report(self):
        listings = [
            NormalizedListing("A", source="eBay.ca", source_type="eBay CSV", connector_name="eBay CSV Connector"),
            NormalizedListing("B", source="Dealer One", source_type="Dealer Inventory", connector_name="Dealer Inventory Connector"),
        ]

        summary = SourceSummaryReport.from_listings(listings)

        self.assertEqual(summary.source_counts["eBay.ca"], 1)
        self.assertEqual(summary.source_type_counts["Dealer Inventory"], 1)
        self.assertIn("Source Summary Report", summary.format_markdown())

    def test_duplicate_opportunity_detector(self):
        listings = [
            NormalizedListing("1901 Newfoundland 50 cents VF20", price=80, shipping=5, seller="A", source="eBay", url="https://example.test/1"),
            NormalizedListing("1901 Newfoundland 50 cents VF20", price=82, shipping=5, seller="B", source="Dealer", url="https://example.test/1"),
            NormalizedListing("1901 Newfoundland 50 cents VF20 PCGS", price=90, shipping=5, seller="C", source="Auction"),
        ]

        findings = DuplicateOpportunityDetector().detect(listings)
        kinds = {finding.duplicate_type for finding in findings}

        self.assertIn("identical_url", kinds)
        self.assertIn("likely_same_opportunity", kinds)

    def test_registry_multi_file_imports(self):
        self.setUpTemp()
        ebay = self._write_csv("ebay.csv", ["title", "price_cad"], [["1901 Newfoundland 50 cents VF20", "80"]])
        dealer = self._write_csv("dealer.csv", ["item", "dealer_price"], [["Canada 10 cents 1911 EF40 silver", "70"]])
        registry = ConnectorRegistry()

        report = registry.import_files([
            {"connector_name": "eBay CSV Connector", "path": ebay},
            {"connector_name": "Dealer Inventory Connector", "path": dealer},
        ])

        self.assertEqual(report.imported_count, 2)
        pool = report.to_candidate_pool()
        self.assertEqual(pool.candidate_count, 2)

    def test_multi_source_ranking_integration(self):
        self.setUpTemp()
        ebay = self._write_csv("ebay.csv", ["title", "price_cad", "shipping_cad"], [["1901 Newfoundland 50 cents VF20", "80", "5"]])
        auction = self._write_csv("auction.csv", ["lot_title", "hammer_price"], [["Canada 10 cents 1911 EF40 silver", "70"]])
        registry = ConnectorRegistry()
        import_report = registry.import_files([
            {"connector_name": "eBay CSV Connector", "path": ebay},
            {"connector_name": "Auction CSV Connector", "path": auction},
        ])
        engine = DealHunterRankingEngine(self.items, self.intents, self.market)

        ranking = registry.rank_reports([import_report], engine)

        self.assertEqual(ranking.candidate_count, 2)
        self.assertTrue(ranking.ranked_deals)
        self.assertTrue(any("Newfoundland" in deal.listing.title for deal in ranking.ranked_deals))

    def test_report_exports(self):
        self.setUpTemp()
        path = self._write_csv("ebay.csv", ["title", "price_cad"], [["1901 Newfoundland 50 cents VF20", "80"]])
        report = eBayCSVConnector().import_file(path)
        summary = SourceSummaryReport.from_listings(report.listings)

        import_csv = os.path.join(self.temp_dir.name, "import.csv")
        import_md = os.path.join(self.temp_dir.name, "import.md")
        validation_csv = os.path.join(self.temp_dir.name, "validation.csv")
        summary_md = os.path.join(self.temp_dir.name, "summary.md")
        self.assertTrue(report.export_csv(import_csv))
        self.assertTrue(report.export_markdown(import_md))
        self.assertTrue(report.validation_report.export_csv(validation_csv))
        self.assertTrue(summary.export_markdown(summary_md))
        with open(import_md, "r", encoding="utf-8") as handle:
            self.assertIn("Connector Import Report", handle.read())
        with open(validation_csv, "r", encoding="utf-8") as handle:
            self.assertIn("connector_name", handle.read())


if __name__ == "__main__":
    unittest.main()
