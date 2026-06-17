"""Tests for the Series Tracker engine."""

import os
import tempfile
import unittest

from acquisition_impact import AcquisitionImpactEngine
from coin_collection import CoinItem
from collection_dashboard import CollectionDashboard
from focused_collection_intelligence import CandidateItem
from legacy_portfolio_importer import LegacyWantListIntent
from series_definitions import SERIES_DEFINITIONS
from series_tracker import SeriesTracker


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


def make_intent(target_coin, priority_score=75):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id=f"want_{target_coin}",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=150.0,
        why_wanted="Series tracker test target",
        status="Active",
        priority_score=priority_score,
    )


class TestSeriesTracker(unittest.TestCase):
    def setUp(self):
        self.items = [
            make_item("1", "Newfoundland", "20 cents", "1894", "F-12"),
            make_item("2", "Newfoundland", "20 cents", "1896", "VF-20"),
            make_item("3", "Newfoundland", "20 cents", "1900", "EF-40"),
            make_item("4", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("5", "Newfoundland", "50 cents", "1902", "VF-20"),
            make_item("6", "Canada", "1 cent", "1859", "VG-8"),
            make_item("7", "Canada", "1 cent", "1859", "VF-20"),
            make_item("8", "Canada", "dollar", "1935", "VF-20"),
        ]

    def test_series_definition_loading(self):
        names = [definition.name for definition in SERIES_DEFINITIONS]

        self.assertIn("Newfoundland 20 Cents", names)
        self.assertIn("Canadian Large Cents", names)
        self.assertIn("Canadian Silver Dollars", names)

    def test_series_completion_calculation(self):
        reports = SeriesTracker(self.items).generate_reports()
        nf_20 = next(report for report in reports if report.series_name == "Newfoundland 20 Cents")

        self.assertEqual(nf_20.owned_count, 3)
        self.assertEqual(nf_20.missing_count, 4)
        self.assertAlmostEqual(nf_20.completion_percentage, 42.9)

    def test_missing_date_detection(self):
        report = next(
            row for row in SeriesTracker(self.items).generate_reports()
            if row.series_name == "Newfoundland 20 Cents"
        )
        missing_years = [missing.year for missing in report.missing_dates]

        self.assertIn("1895", missing_years)
        self.assertIn("1899", missing_years)

    def test_want_list_integration(self):
        intents = [make_intent("Newfoundland 20 cents 1899")]
        report = next(
            row for row in SeriesTracker(self.items, intents).generate_reports()
            if row.series_name == "Newfoundland 20 Cents"
        )

        self.assertEqual(report.want_list_count, 1)
        self.assertTrue(any(missing.year == "1899" and missing.is_want_list_target for missing in report.missing_dates))

    def test_upgrade_integration(self):
        report = next(
            row for row in SeriesTracker(self.items).generate_reports()
            if row.series_name == "Canadian Large Cents"
        )

        self.assertEqual(report.upgrade_count, 1)

    def test_priority_score_generation(self):
        intents = [make_intent("Newfoundland 20 cents 1899")]
        report = next(
            row for row in SeriesTracker(self.items, intents).generate_reports()
            if row.series_name == "Newfoundland 20 Cents"
        )

        self.assertGreater(report.priority_score, 80)

    def test_dashboard_integration(self):
        data = CollectionDashboard(self.items, [make_intent("Newfoundland 20 cents 1899")]).generate_dashboard()

        self.assertTrue(data.series_tracker_reports)
        self.assertTrue(data.top_series_focus)
        self.assertTrue(any("Newfoundland 20 Cents" in item.title for item in data.top_series_focus))

    def test_acquisition_impact_integration(self):
        candidate = CandidateItem("Newfoundland", "20 cents", "1899", grade="VF-20", asking_price=100)
        report = AcquisitionImpactEngine(self.items, [make_intent("Newfoundland 20 cents 1899")]).evaluate(candidate)

        self.assertEqual(report.series_name, "Newfoundland 20 Cents")
        self.assertNotEqual(report.series_priority_after, 0)
        self.assertEqual(report.series_priority_delta, report.series_priority_after - report.series_priority_before)

    def test_export_support(self):
        tracker = SeriesTracker(self.items, [make_intent("Newfoundland 20 cents 1899")])
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "series.csv")
            md_path = os.path.join(temp_dir, "series.md")

            self.assertTrue(tracker.export_csv(csv_path))
            self.assertTrue(tracker.export_markdown(md_path))

            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("Series Summary", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("# Series Tracker", handle.read())


if __name__ == "__main__":
    unittest.main()
