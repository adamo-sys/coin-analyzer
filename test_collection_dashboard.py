"""Tests for actionable Collection Dashboard."""

import csv
import os
import tempfile
import unittest

from openpyxl import Workbook

from collection_dashboard import CollectionDashboard, CollectionDashboardData
from coin_collection import CoinItem, IdentificationStatus, ItemType
from collection_intelligence import CollectionIntelligenceEngine
from collection_quality import CollectionQualityEngine
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
        # Legacy counts remain descriptive; they cannot authorize specimen advice.
        self.assertEqual(len(data.best_upgrade_opportunities), 1)
        self.assertIn("unavailable", data.best_upgrade_opportunities[0].title)
        self.assertEqual(data.best_upgrade_opportunities[0].action, "")

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

    def test_quality_improvement_display_withholds_legacy_disposition(self):
        items = [
            make_item("a", "Canada", "10 cents", "1911", "F-12"),
            make_item("b", "Canada", "10 cents", "1911", "EF-40", quantity=3),
        ]
        dashboard = CollectionDashboard(items, [make_intent("Canada 10 cents 1911")])
        data = dashboard.generate_dashboard()
        panel = data.top_potential_collection_improvements
        self.assertEqual([row.title for row in panel], ["Acquire Canada 10 cents 1911"])
        self.assertIn("Explicit WANT_LIST", panel[0].detail)
        self.assertIn("Human-curated", panel[0].action)
        # Legacy dashboard metrics remain deferred; omitted advice is not zero evidence.
        self.assertEqual(data.snapshot.total_upgrade_opportunities, 1)
        quality_section = dashboard.format_markdown().split("## Top Recommended Actions", 1)[1].split("\n## ", 1)[0]
        self.assertIn("Acquire Canada 10 cents 1911", quality_section)
        self.assertNotIn("replace weaker", quality_section)
        self.assertNotIn("Reduce duplicate holdings", quality_section)


class TestDashboardLegacyAuthorityContainment(unittest.TestCase):
    def assert_contained(self, data):
        advice = data.top_collection_priorities + data.want_list_priorities
        text = " ".join(f"{row.title} {row.detail} {row.action}" for row in advice).lower()
        for phrase in ("keep highest", "keeping best", "replacing lower", "upgrade opportunity:",
                       "reduce duplicate", "replacement candidate"):
            self.assertNotIn(phrase, text)
        self.assertEqual(len(data.best_upgrade_opportunities), 1)
        limitation = data.best_upgrade_opportunities[0]
        self.assertIn("unavailable", limitation.title.lower())
        self.assertIn("do not establish", limitation.detail)
        self.assertEqual(limitation.action, "")
        self.assertEqual(limitation.priority, 0)
        displayed = text + " " + limitation.detail.lower()
        for phrase in ("no duplicates", "no replacement needed", "no action required",
                       "holdings are optimal", "all examples are distinct"):
            self.assertNotIn(phrase, displayed)

    def test_legacy_groups_never_authorize_disposition(self):
        cases = [
            ("weak fields", {}, {}, "F-12", "EF-40"),
            ("unidentified", {"identification_status": IdentificationStatus.UNIDENTIFIED}, {}, "F-12", "EF-40"),
            ("partial", {"identification_status": IdentificationStatus.PARTIAL}, {}, "F-12", "EF-40"),
            ("different types", {"item_type": ItemType.BANKNOTE}, {}, "F-12", "EF-40"),
            ("grade differences", {}, {}, "VG-8", "AU-50"),
            ("equal grades", {}, {}, "VF-20", "VF-20"),
            ("multiple records", {}, {}, "", ""),
            ("recorded quantities", {"quantity": 4}, {"quantity": 3}, "F-12", "EF-40"),
        ]
        for name, first, second, low, high in cases:
            with self.subTest(name=name):
                items = [make_item("a", "Canada", "10 cents", "1911", low, **first),
                         make_item("b", "Canada", "10 cents", "1911", high, **second)]
                engine = CollectionIntelligenceEngine(items)
                self.assertTrue(engine.detect_duplicates())
                data = CollectionDashboard(items).generate_dashboard()
                self.assert_contained(data)
                self.assertEqual(data.snapshot.total_duplicate_items,
                                 sum(row["count"] - 1 for row in engine.detect_duplicates()))
                self.assertEqual(data.snapshot.total_upgrade_opportunities,
                                 len(engine.detect_upgrade_candidates()))
                self.assertEqual(data.snapshot.total_collection_items, 2)
                self.assertEqual(data.quality_report.to_dict(),
                                 CollectionQualityEngine(items).generate_report().to_dict())

    def test_same_recorded_issue_still_does_not_authorize_disposition(self):
        fields = {"identification_status": IdentificationStatus.IDENTIFIED,
                  "issuer": "Canada", "type_design": "Synthetic issue", "numista_n": "12345"}
        items = [make_item("a", "Canada", "10 cents", "1911", "F-12", **fields),
                 make_item("b", "Canada", "10 cents", "1911", "EF-40", **fields)]
        self.assertTrue(CollectionIntelligenceEngine(items).analyze_same_issue_records()["established_groups"])
        self.assert_contained(CollectionDashboard(items).generate_dashboard())

    def test_single_record_quantity_does_not_authorize_disposition(self):
        data = CollectionDashboard([make_item("a", "Canada", "10 cents", "1911", "VF-20", quantity=5)]).generate_dashboard()
        self.assert_contained(data)
        self.assertEqual(data.snapshot.total_duplicate_items, 4)
        self.assertEqual(data.snapshot.total_upgrade_opportunities, 0)

    def test_unsafe_targets_cannot_crowd_out_explicit_want_before_limits(self):
        items = [make_item(f"{year}-{grade}", "Canada", "10 cents", str(year), grade)
                 for year in range(1900, 1912) for grade in ("F-12", "EF-40")]
        want = make_intent("France 1 franc 2000")
        want.priority_score = 0
        engine = CollectionIntelligenceEngine(items)
        before = engine.generate_want_list(limit=10, staged_want_list_intents=[want])
        self.assertTrue(all(target.target_type == "Upgrade Candidate" for target in before))
        data = CollectionDashboard(items, [want]).generate_dashboard()
        self.assert_contained(data)
        for panel in (data.top_collection_priorities, data.want_list_priorities):
            self.assertEqual([row.title for row in panel], [want.target_coin])
            self.assertIn("Explicit WANT_LIST", panel[0].detail)
        self.assertEqual(data.snapshot.total_upgrade_opportunities, 12)

    def test_matching_explicit_want_survives_and_quality_containment_remains(self):
        items = [make_item("a", "Canada", "10 cents", "1911", "F-12"),
                 make_item("b", "Canada", "10 cents", "1911", "EF-40")]
        want = make_intent("Canada 10 cents 1911")
        data = CollectionDashboard(items, [want]).generate_dashboard()
        self.assert_contained(data)
        for panel in (data.top_collection_priorities, data.want_list_priorities):
            self.assertEqual([row.title for row in panel], [want.target_coin])
            self.assertIn("Explicit WANT_LIST", panel[0].detail)
        self.assertEqual([row.action for row in data.quality_report.recommended_actions],
                         ["Acquire Canada 10 cents 1911"])

    def test_missing_date_priorities_and_want_fallback_remain(self):
        items = [make_item("a", "Canada", "10 cents", "1910", "F-12"),
                 make_item("b", "Canada", "10 cents", "1912", "EF-40")]
        data = CollectionDashboard(items).generate_dashboard()
        self.assert_contained(data)
        self.assertTrue(any("nearing completion" in row.title for row in data.top_collection_priorities))
        self.assertTrue(any("1911" in row.title and row.action == "Review acquisition candidate."
                            for row in data.want_list_priorities))

    def test_markdown_and_csv_withhold_legacy_advice_preserve_metrics_and_want(self):
        items = [make_item("a", "Canada", "10 cents", "1911", "F-12"),
                 make_item("b", "Canada", "10 cents", "1911", "EF-40", quantity=3)]
        dashboard = CollectionDashboard(items, [make_intent("Canada 10 cents 1911")])
        markdown = dashboard.format_markdown()
        self.assertIn("Total duplicate items: 3", markdown)
        self.assertIn("Total upgrade opportunities: 1", markdown)
        self.assertIn("Upgrade/replacement advice unavailable", markdown)
        self.assertIn("Acquire Canada 10 cents 1911", markdown)
        for phrase in ("Keep highest-grade", "replacing lower-grade", "Upgrade opportunity:", "Reduce duplicate holdings"):
            self.assertNotIn(phrase, markdown)
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "dashboard.csv")
            self.assertTrue(dashboard.export_csv(path))
            with open(path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        for section in ("Top Collection Priorities", "WANT_LIST Priorities"):
            advice = [row for row in rows if row["Section"] == section]
            self.assertEqual([row["Title"] for row in advice], ["Canada 10 cents 1911"])
            self.assertIn("Explicit WANT_LIST", advice[0]["Detail"])
        upgrade_rows = [row for row in rows if row["Section"] == "Best Upgrade Opportunities"]
        self.assertEqual(len(upgrade_rows), 1)
        self.assertIn("unavailable", upgrade_rows[0]["Title"])
        self.assertEqual(upgrade_rows[0]["Action"], "")
        quality_actions = [row["Title"] for row in rows if row["Section"] == "Quality Recommended Action"]
        self.assertEqual(quality_actions, ["Acquire Canada 10 cents 1911"])
        metrics = {row["Title"]: row["Detail"] for row in rows if row["Section"] == "Snapshot"}
        self.assertEqual(metrics["total_duplicate_items"], "3")
        self.assertEqual(metrics["total_upgrade_opportunities"], "1")


if __name__ == "__main__":
    unittest.main()
