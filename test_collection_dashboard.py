"""Tests for actionable Collection Dashboard."""

import os
import tempfile
import unittest

from openpyxl import Workbook

from collection_dashboard import CollectionDashboard, CollectionDashboardData
from coin_collection import CoinItem
from legacy_portfolio_importer import LegacyWantListIntent
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


def make_intent(target_coin):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id="legacy_want_list_2",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=150.0,
        why_wanted="Dashboard test target",
        status="Active",
        priority_score=75,
    )


def create_want_list_workbook(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "WANT_LIST"
    ws.append(WANT_HEADERS)
    ws.append(["Newfoundland 50 cents 1904", "High", "VF-20", 150, "Dashboard target", "Active"])
    wb.save(path)


class TestCollectionDashboard(unittest.TestCase):
    def setUp(self):
        self.items = [
            make_item("1", "Newfoundland", "20 cents", "1900", "F-12"),
            make_item("2", "Newfoundland", "20 cents", "1901", "VF-20"),
            make_item("3", "Newfoundland", "20 cents", "1903", "VF-20"),
            make_item("4", "Canada", "10 cents", "1911", "VF-20", notes="PCGS certified"),
            make_item("5", "Canada", "10 cents", "1911", "EF-40"),
            make_item("6", "Canada", "1 cent", "1859", "VG-8"),
            make_item("7", "United States", "1 cent", "1975", "VF-20"),
        ]

    def test_empty_collection(self):
        data = CollectionDashboard([]).generate_dashboard()

        self.assertEqual(data.snapshot.total_collection_items, 0)
        self.assertEqual(data.snapshot.collection_countries_count, 0)
        self.assertEqual(data.snapshot.total_want_list_items, 0)

    def test_small_collection_summary_generation(self):
        data = CollectionDashboard(self.items).generate_dashboard()

        self.assertIsInstance(data, CollectionDashboardData)
        self.assertEqual(data.snapshot.total_collection_items, 7)
        self.assertEqual(data.snapshot.collection_countries_count, 3)
        self.assertGreaterEqual(data.snapshot.collection_denominations_count, 3)

    def test_want_list_integration(self):
        data = CollectionDashboard(self.items, [make_intent("Newfoundland 50 cents 1904")]).generate_dashboard()

        self.assertEqual(data.snapshot.total_want_list_items, 1)
        self.assertTrue(data.want_list_priorities)
        self.assertTrue(any("Newfoundland" in item.title for item in data.want_list_priorities))

    def test_upgrade_opportunity_reporting(self):
        data = CollectionDashboard(self.items).generate_dashboard()

        self.assertGreaterEqual(data.snapshot.total_upgrade_opportunities, 1)
        self.assertTrue(any("1911" in item.title for item in data.best_upgrade_opportunities))

    def test_collection_gap_reporting(self):
        data = CollectionDashboard(self.items).generate_dashboard()

        self.assertTrue(data.collection_gaps)
        self.assertTrue(any("1902" in item.detail for item in data.collection_gaps))

    def test_series_completion_calculations(self):
        data = CollectionDashboard(self.items).generate_dashboard()
        nf_20 = next(row for row in data.series_completion if row.series == "Newfoundland / 20 cents")

        self.assertEqual(nf_20.missing_years, "1902")
        self.assertAlmostEqual(nf_20.completion_percentage, 75.0)

    def test_snapshot_counts_silver_and_certified_items(self):
        data = CollectionDashboard(self.items).generate_dashboard()

        self.assertGreaterEqual(data.snapshot.silver_items_count, 1)
        self.assertEqual(data.snapshot.certified_items_count, 1)

    def test_dashboard_export(self):
        dashboard = CollectionDashboard(self.items, [make_intent("Newfoundland 50 cents 1904")])
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "dashboard.csv")
            md_path = os.path.join(temp_dir, "dashboard.md")

            self.assertTrue(dashboard.export_csv(csv_path))
            self.assertTrue(dashboard.export_markdown(md_path))

            with open(csv_path, "r", encoding="utf-8") as handle:
                csv_text = handle.read()
                self.assertIn("Top Collection Priorities", csv_text)
                self.assertIn("Overall Quality Score", csv_text)
            with open(md_path, "r", encoding="utf-8") as handle:
                markdown_text = handle.read()
                self.assertIn("# Collection Dashboard", markdown_text)
                self.assertIn("## Collection Quality", markdown_text)

    def test_shared_session_context_integration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook_path = os.path.join(temp_dir, "want.xlsx")
            create_want_list_workbook(workbook_path)
            context = SessionContext()
            context.load_want_list_context(workbook_path, self.items)

            data = CollectionDashboard(self.items, context.get_want_list_intents()).generate_dashboard()

        self.assertEqual(data.snapshot.total_want_list_items, 1)
        self.assertTrue(data.want_list_priorities)


if __name__ == "__main__":
    unittest.main()
