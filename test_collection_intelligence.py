"""Unit tests for the collection intelligence engine."""

import csv
import os
import tempfile
import unittest
from datetime import datetime

from coin_collection import CoinItem
from collection_intelligence import CollectionIntelligenceEngine


def make_item(item_id, country, denomination, year, grade="VF-20", **overrides):
    values = {
        "id": item_id,
        "image_path": "",
        "country": country,
        "denomination": denomination,
        "year": year,
        "grade": grade,
        "notes": "",
        "date_added": datetime.now().isoformat(),
        "auto_detected": False,
        "detection_confidence": 0.0,
        "reference": "",
        "numista_n": "",
        "title": "",
        "quantity": 1,
        "estimate_cad": 0.0,
        "from_numista": True,
    }
    values.update(overrides)
    return CoinItem(**values)


class TestCollectionIntelligenceEngine(unittest.TestCase):
    """Verify reusable collection analysis behavior."""

    def setUp(self):
        self.items = [
            make_item("nf_1900", "Newfoundland", "50 cents", "1900", "F-12"),
            make_item("nf_1902", "Newfoundland", "50 cents", "1902", "VF-20"),
            make_item("can_1859_a", "Canada", "1 cent", "1859", "VG-8", reference="Narrow 9"),
            make_item("can_1859_b", "Canada", "1 cent", "1859", "VF-20", reference="Narrow 9"),
            make_item("can_1910", "Canada", "10 cents", "1910", "F-12"),
            make_item("can_1912", "Canada", "10 cents", "1912", "F-12"),
        ]
        self.engine = CollectionIntelligenceEngine(self.items)

    def test_analyze_by_country_counts_items(self):
        countries = self.engine.analyze_by_country()

        self.assertEqual(countries["Newfoundland"]["count"], 2)
        self.assertEqual(countries["Canada"]["count"], 4)

    def test_detect_missing_years_by_series(self):
        missing = self.engine.detect_missing_years()

        self.assertEqual(missing[("Newfoundland", "50 cents")], [1901])

    def test_completion_percentages(self):
        series = self.engine.analyze_by_series()

        self.assertAlmostEqual(series[("Newfoundland", "50 cents")]["completion_percentage"], 66.666, places=2)

    def test_detect_duplicates_and_upgrade_candidates(self):
        duplicates = self.engine.detect_duplicates()
        upgrades = self.engine.detect_upgrade_candidates()

        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["country"], "Canada")
        self.assertEqual(upgrades[0]["current_best_grade"], "VF-20")

    def test_newfoundland_missing_date_is_high_priority(self):
        targets = self.engine.generate_want_list(limit=10)

        self.assertEqual(targets[0].country, "Newfoundland")
        self.assertEqual(targets[0].year, "1901")
        self.assertIn("Newfoundland", targets[0].reason)

    def test_gap_report_markdown_contains_required_sections(self):
        markdown = self.engine.format_gap_report_markdown()

        self.assertIn("# Collection Gap Report", markdown)
        self.assertIn("## Series Gap Analysis", markdown)
        self.assertIn("## Missing Dates", markdown)
        self.assertIn("## Completion Percentages", markdown)
        self.assertIn("## Upgrade Opportunities", markdown)
        self.assertIn("## Priority Acquisition Targets", markdown)

    def test_gap_report_rows_include_priority_tiers_and_suggestions(self):
        rows = self.engine.generate_gap_report_rows()
        by_series = {row["series"]: row for row in rows}

        self.assertEqual(by_series["Newfoundland / 50 cents"]["priority_tier"], "Tier 1")
        self.assertEqual(by_series["Canada / 10 cents"]["priority_tier"], "Tier 1")
        self.assertEqual(by_series["Canada / 1 cent"]["priority_tier"], "Tier 2")
        self.assertEqual(by_series["Canada / 10 cents"]["missing_years"], "1911")
        self.assertIn("Acquire missing date", by_series["Canada / 10 cents"]["suggested_next_acquisitions"])
        self.assertAlmostEqual(
            by_series["Canada / 10 cents"]["completion_percentage"],
            66.666,
            places=2,
        )

    def test_gap_report_csv_export_is_read_only(self):
        before_ids = [item.id for item in self.items]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "gap_report.csv")

            self.assertTrue(self.engine.export_gap_report_csv(output_path))
            with open(output_path, "r", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual([item.id for item in self.items], before_ids)
        self.assertTrue(rows)
        self.assertEqual(
            set(rows[0].keys()),
            {
                "priority_tier",
                "series",
                "country",
                "denomination",
                "years_owned",
                "missing_years",
                "completion_percentage",
                "suggested_next_acquisitions",
            },
        )
        canada_silver = next(row for row in rows if row["series"] == "Canada / 10 cents")
        self.assertEqual(canada_silver["priority_tier"], "Tier 1")
        self.assertEqual(canada_silver["missing_years"], "1911")

    def test_want_list_csv_export(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "want_list.csv")

            self.assertTrue(self.engine.export_want_list_csv(output_path, limit=10))
            with open(output_path, "r", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertTrue(rows)
        self.assertEqual(rows[0]["country"], "Newfoundland")


if __name__ == "__main__":
    unittest.main()
