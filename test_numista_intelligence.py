"""Unit tests for the Numista Intelligence engine."""

import csv
import json
import os
import tempfile
import unittest
from datetime import datetime

from coin_collection import CoinItem, CoinCollection
from numista_intelligence import (
    NumistaDataModel,
    NumistaCollectionAnalyzer,
    NumistaIntelligenceEngine,
    NumistaMatchStatus,
    NumistaPriority,
    NumistaItemAnalysis,
    NumistaIntelligenceReport,
    run_numista_intelligence,
)


def make_item(item_id, country, denomination, year, grade="VF-20", **overrides):
    """Create a CoinItem fixture."""
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
        "issuer": country,
        "currency": "",
        "face_value": "",
        "reference": "",
        "numista_n": "",
        "title": "",
        "quantity": 1,
        "estimate_cad": 0.0,
        "comments": "",
        "from_numista": True,
    }
    values.update(overrides)
    return CoinItem(**values)


def make_numista_item(numista_n, title, country, year, grade="", **overrides):
    """Create a Numista item dict fixture."""
    values = {
        "numista_n": numista_n,
        "title": title,
        "country": country,
        "issuer": country,
        "face_value": title,  # Use title as face_value for denomination matching
        "currency": "",
        "year": year,
        "grade": grade,
        "reference": "",
        "comment": "",
        "private_comment": "",
        "quantity": 1,
        "estimate_cad": 0.0,
    }
    values.update(overrides)
    return values


class TestNumistaDataModel(unittest.TestCase):
    """Verify Numista data parsing and normalization."""

    def test_load_from_csv_with_expected_columns(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['N# number (with link)', 'Title', 'Country', 'Issuer',
                           'Face value', 'Currency', 'Year', 'Grade', 'Reference',
                           'Comment', 'Private comment', 'Quantity', 'Estimate (CAD)'])
            writer.writerow(['N#12345', '1 cent - Victoria', 'Canada', 'Canada',
                           '1 cent', 'Canadian dollar', '1859', 'VF-20', 'KM# 1',
                           '', '', '1', '25.00'])
            writer.writerow(['N#12346', '50 cents - Edward VII', 'Newfoundland', 'Newfoundland',
                           '50 cents', 'Newfoundland dollar', '1909', 'F-12', 'KM# 12',
                           '', '', '1', '150.00'])
            temp_path = f.name

        try:
            model = NumistaDataModel()
            success = model.load_from_csv(temp_path)
            self.assertTrue(success)
            self.assertEqual(len(model.get_items()), 2)

            item = model.get_items()[0]
            self.assertEqual(item['numista_n'], '12345')
            self.assertEqual(item['title'], '1 cent - Victoria')
            self.assertEqual(item['country'], 'Canada')
            self.assertEqual(item['year'], '1859')
            self.assertEqual(item['grade'], 'VF-20')
            self.assertEqual(item['estimate_cad'], 25.0)
        finally:
            os.unlink(temp_path)

    def test_load_from_csv_with_empty_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['N# number (with link)', 'Title', 'Country', 'Year'])
            temp_path = f.name

        try:
            model = NumistaDataModel()
            success = model.load_from_csv(temp_path)
            self.assertTrue(success)
            self.assertEqual(len(model.get_items()), 0)
        finally:
            os.unlink(temp_path)

    def test_load_from_missing_file_returns_error(self):
        model = NumistaDataModel()
        success = model.load_from_csv('nonexistent_file.csv')
        self.assertFalse(success)
        self.assertGreater(len(model.parse_errors), 0)

    def test_extract_numista_n_from_link(self):
        model = NumistaDataModel()
        self.assertEqual(model._extract_numista_n('N#12345'), '12345')
        self.assertEqual(model._extract_numista_n('https://numista.com/catalogue/pieces12345'), '12345')
        self.assertEqual(model._extract_numista_n(''), '')
        self.assertEqual(model._extract_numista_n(None), '')

    def test_clean_value_handles_nan(self):
        model = NumistaDataModel()
        import math
        self.assertEqual(model._clean_value(float('nan')), '')
        self.assertEqual(model._clean_value('test'), 'test')
        self.assertEqual(model._clean_value(123), '123')

    def test_format_year_converts_float(self):
        model = NumistaDataModel()
        self.assertEqual(model._format_year(1859.0), '1859')
        self.assertEqual(model._format_year('1859'), '1859')
        self.assertEqual(model._format_year(''), '')

    def test_validation_summary_reports_counts(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['N# number (with link)', 'Title', 'Country', 'Year'])
            writer.writerow(['N#100', 'Test', 'Canada', '1960'])
            temp_path = f.name

        try:
            model = NumistaDataModel()
            model.load_from_csv(temp_path)
            summary = model.get_validation_summary()
            self.assertEqual(summary['total_rows'], 1)
            self.assertEqual(summary['normalized_items'], 1)
            self.assertEqual(summary['parse_errors'], 0)
        finally:
            os.unlink(temp_path)


class TestNumistaCollectionAnalyzer(unittest.TestCase):
    """Verify Numista collection analysis behavior."""

    def setUp(self):
        self.items = [
            make_item("nf_1900", "Newfoundland", "50 cents", "1900", "F-12", numista_n="5001"),
            make_item("nf_1902", "Newfoundland", "50 cents", "1902", "VF-20", numista_n="5002"),
            make_item("can_1859", "Canada", "1 cent", "1859", "VG-8", numista_n="1001", reference="Narrow 9"),
            make_item("can_1910", "Canada", "10 cents", "1910", "F-12", numista_n="1002"),
        ]
        self.collection = CoinCollection.__new__(CoinCollection)
        self.collection.items = self.items
        self.analyzer = NumistaCollectionAnalyzer(self.collection)

    def test_owned_by_numista_n(self):
        numista_item = make_numista_item("5001", "50 cents", "Newfoundland", "1900")
        analysis = self.analyzer.analyze_item(numista_item)
        self.assertEqual(analysis.status, NumistaMatchStatus.OWNED)
        self.assertEqual(analysis.priority, NumistaPriority.NONE)
        self.assertIn("Already owned", analysis.reasons[0])

    def test_duplicate_by_signature(self):
        numista_item = make_numista_item("9999", "50 cents", "Newfoundland", "1900", "F-12")
        analysis = self.analyzer.analyze_item(numista_item)
        self.assertEqual(analysis.status, NumistaMatchStatus.DUPLICATE)
        self.assertEqual(analysis.priority, NumistaPriority.NONE)

    def test_upgrade_by_better_grade(self):
        numista_item = make_numista_item("9999", "50 cents", "Newfoundland", "1900", "AU-50")
        analysis = self.analyzer.analyze_item(numista_item)
        self.assertEqual(analysis.status, NumistaMatchStatus.UPGRADE)
        self.assertEqual(analysis.priority, NumistaPriority.HIGH)
        self.assertIn("Upgrade", analysis.reasons[0])

    def test_newfoundland_gap(self):
        numista_item = make_numista_item("5003", "50 cents", "Newfoundland", "1904", "VF-20")
        analysis = self.analyzer.analyze_item(numista_item)
        self.assertEqual(analysis.status, NumistaMatchStatus.GAP)
        self.assertEqual(analysis.priority, NumistaPriority.HIGH)
        self.assertIn("Collection gap", analysis.reasons[0])

    def test_canadian_silver_gap(self):
        numista_item = make_numista_item("1003", "10 cents silver", "Canada", "1912", "VF-20")
        analysis = self.analyzer.analyze_item(numista_item)
        # Canadian silver without specific series match becomes NEW_SERIES
        self.assertEqual(analysis.status, NumistaMatchStatus.NEW_SERIES)
        self.assertEqual(analysis.priority, NumistaPriority.MEDIUM)

    def test_new_series_for_newfoundland(self):
        numista_item = make_numista_item("5004", "1 cent", "Newfoundland", "1913", "VF-20")
        analysis = self.analyzer.analyze_item(numista_item)
        # Newfoundland 1 cent matches supported series, so it's GAP not NEW_SERIES
        self.assertEqual(analysis.status, NumistaMatchStatus.GAP)
        self.assertEqual(analysis.priority, NumistaPriority.HIGH)

    def test_not_relevant_for_unsupported_country(self):
        numista_item = make_numista_item("9999", "1 peso", "Argentina", "1960", "VF-20")
        analysis = self.analyzer.analyze_item(numista_item)
        self.assertEqual(analysis.status, NumistaMatchStatus.NOT_RELEVANT)
        self.assertEqual(analysis.priority, NumistaPriority.NONE)

    def test_variety_detection(self):
        numista_item = make_numista_item("1004", "1 cent large", "Canada", "1859", "VF-20",
                                         reference="Wide 9 variety")
        analysis = self.analyzer.analyze_item(numista_item)
        self.assertEqual(analysis.status, NumistaMatchStatus.VARIETY)
        self.assertEqual(analysis.priority, NumistaPriority.HIGH)

    def test_key_date_priority(self):
        numista_item = make_numista_item("5005", "50 cents", "Newfoundland", "1888", "VF-20")
        analysis = self.analyzer.analyze_item(numista_item)
        self.assertEqual(analysis.status, NumistaMatchStatus.GAP)
        self.assertEqual(analysis.priority, NumistaPriority.HIGH)

    def test_grade_comparison_upgrade(self):
        self.assertTrue(self.analyzer._is_upgrade(
            make_item("test", "Canada", "1 cent", "1900", "F-12"),
            NumistaItemAnalysis("", "", "Canada", "1 cent", "1900", "VF-20", "", "", "", "", 0.0,
                            NumistaMatchStatus.GAP, NumistaPriority.MEDIUM)
        ))
        self.assertFalse(self.analyzer._is_upgrade(
            make_item("test", "Canada", "1 cent", "1900", "VF-20"),
            NumistaItemAnalysis("", "", "Canada", "1 cent", "1900", "F-12", "", "", "", "", 0.0,
                            NumistaMatchStatus.GAP, NumistaPriority.MEDIUM)
        ))

    def test_newfoundland_detection(self):
        analysis = NumistaItemAnalysis("", "", "Newfoundland", "", "", "", "", "Newfoundland", "", "", 0.0,
                                       NumistaMatchStatus.GAP, NumistaPriority.HIGH)
        self.assertTrue(self.analyzer._is_newfoundland(analysis))

        analysis2 = NumistaItemAnalysis("", "", "Canada", "", "", "", "", "Canada", "", "", 0.0,
                                        NumistaMatchStatus.GAP, NumistaPriority.MEDIUM)
        self.assertFalse(self.analyzer._is_newfoundland(analysis2))

    def test_canadian_silver_detection(self):
        analysis = NumistaItemAnalysis("", "", "Canada", "10 cents", "", "", "", "Canada", "", "", 0.0,
                                       NumistaMatchStatus.GAP, NumistaPriority.MEDIUM)
        self.assertTrue(self.analyzer._is_canadian_silver(analysis))

        analysis2 = NumistaItemAnalysis("", "", "Canada", "1 cent", "", "", "", "Canada", "", "", 0.0,
                                        NumistaMatchStatus.GAP, NumistaPriority.MEDIUM)
        self.assertFalse(self.analyzer._is_canadian_silver(analysis2))

    def test_has_variety_indicators(self):
        analysis = NumistaItemAnalysis("", "Wide 9 variety", "Canada", "", "", "Wide 9", "", "", "", "", 0.0,
                                       NumistaMatchStatus.GAP, NumistaPriority.MEDIUM)
        self.assertTrue(self.analyzer._has_variety_indicators(analysis))

        analysis2 = NumistaItemAnalysis("", "Regular issue", "Canada", "", "", "", "", "", "", "", 0.0,
                                        NumistaMatchStatus.GAP, NumistaPriority.MEDIUM)
        self.assertFalse(self.analyzer._has_variety_indicators(analysis2))


class TestNumistaIntelligenceEngine(unittest.TestCase):
    """Verify end-to-end Numista Intelligence engine behavior."""

    def setUp(self):
        self.items = [
            make_item("nf_1900", "Newfoundland", "50 cents", "1900", "F-12", numista_n="5001"),
            make_item("can_1859", "Canada", "1 cent", "1859", "VG-8", numista_n="1001"),
        ]
        self.collection = CoinCollection.__new__(CoinCollection)
        self.collection.items = self.items
        self.engine = NumistaIntelligenceEngine(self.collection)

    def test_analyze_data_returns_report(self):
        numista_items = [
            make_numista_item("5001", "50 cents", "Newfoundland", "1900", "F-12"),  # owned (matches nf_1900 by N#)
            make_numista_item("5002x", "50 cents", "Newfoundland", "1902", "VF-20"),  # gap (Newfoundland 50 cents series, not in collection)
            make_numista_item("1002", "1 cent", "Canada", "1860", "VF-20"),  # not relevant (no series match)
        ]
        report = self.engine.analyze_data(numista_items)
        self.assertIsInstance(report, NumistaIntelligenceReport)
        self.assertEqual(report.total_numista_items, 3)
        self.assertEqual(report.owned_count, 1)  # N#5001 matches nf_1900
        self.assertEqual(report.gap_count, 1)  # 5002x is Newfoundland 50 cents gap
        self.assertEqual(report.not_relevant_count, 1)  # Canada 1 cent 1860 not in supported series

    def test_report_counts_are_correct(self):
        numista_items = [
            make_numista_item("5001", "50 cents", "Newfoundland", "1900", "F-12"),  # owned (matches nf_1900 by N#)
            make_numista_item("5001x", "50 cents", "Newfoundland", "1900", "F-12"),  # duplicate (same country/year as nf_1900)
            make_numista_item("5002x", "50 cents", "Newfoundland", "1902", "AU-50"),  # gap (Newfoundland 50 cents series)
            make_numista_item("5003", "50 cents", "Newfoundland", "1904", "VF-20"),  # gap (Newfoundland 50 cents series)
            make_numista_item("9999", "1 peso", "Argentina", "1960", "VF-20"),  # not relevant
        ]
        report = self.engine.analyze_data(numista_items)
        self.assertEqual(report.owned_count, 1)  # N#5001 matches nf_1900
        self.assertEqual(report.duplicate_count, 1)  # 5001x same country/year as nf_1900
        self.assertEqual(report.upgrade_count, 0)  # No nf_1902 in engine collection to upgrade
        self.assertEqual(report.gap_count, 2)  # 5002x and 5003 are Newfoundland 50 cents gaps
        self.assertEqual(report.not_relevant_count, 1)  # Argentina

    def test_top_priorities_filtered_correctly(self):
        numista_items = [
            make_numista_item("5003", "50 cents", "Newfoundland", "1904", "VF-20"),  # HIGH gap
            make_numista_item("1002", "1 cent", "Canada", "1860", "VF-20"),  # not relevant (no series match)
        ]
        report = self.engine.analyze_data(numista_items)
        self.assertEqual(len(report.top_priorities), 1)  # Only Newfoundland gap is prioritized
        self.assertEqual(report.top_priorities[0].priority, NumistaPriority.HIGH)

    def test_summary_recommendations_generated(self):
        numista_items = [
            make_numista_item("5003", "50 cents", "Newfoundland", "1904", "VF-20"),
        ]
        report = self.engine.analyze_data(numista_items)
        self.assertGreater(len(report.summary_recommendations), 0)
        rec_text = ' '.join(report.summary_recommendations).lower()
        self.assertIn("gap", rec_text)

    def test_report_to_dict_serializes(self):
        numista_items = [
            make_numista_item("5001", "50 cents", "Newfoundland", "1900", "F-12"),
        ]
        report = self.engine.analyze_data(numista_items)
        d = report.to_dict()
        self.assertEqual(d['total_numista_items'], 1)
        self.assertEqual(d['owned_count'], 1)
        self.assertIn('report_date', d)

    def test_analyze_file_with_csv(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['N# number (with link)', 'Title', 'Country', 'Issuer',
                           'Face value', 'Currency', 'Year', 'Grade', 'Reference',
                           'Comment', 'Private comment', 'Quantity', 'Estimate (CAD)'])
            writer.writerow(['N#5001', '50 cents', 'Newfoundland', 'Newfoundland',
                           '50 cents', 'Newfoundland dollar', '1900', 'F-12', 'KM# 12',
                           '', '', '1', '50.00'])
            writer.writerow(['N#5003', '50 cents', 'Newfoundland', 'Newfoundland',
                           '50 cents', 'Newfoundland dollar', '1904', 'VF-20', 'KM# 14',
                           '', '', '1', '75.00'])
            temp_path = f.name

        try:
            report = self.engine.analyze_file(temp_path)
            self.assertEqual(report.total_numista_items, 2)
            self.assertEqual(report.owned_count, 1)
            self.assertEqual(report.gap_count, 1)
        finally:
            os.unlink(temp_path)

    def test_export_report_csv(self):
        numista_items = [
            make_numista_item("5001", "50 cents", "Newfoundland", "1900", "F-12"),
            make_numista_item("5003", "50 cents", "Newfoundland", "1904", "VF-20"),
        ]
        self.engine.analyze_data(numista_items)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            temp_path = f.name

        try:
            self.engine.export_report_csv(temp_path)
            with open(temp_path, 'r', newline='') as f:
                reader = csv.reader(f)
                rows = list(reader)
            self.assertEqual(len(rows), 3)  # header + 2 items
            self.assertEqual(rows[0][0], 'Numista N#')
            self.assertEqual(rows[1][0], '5001')
        finally:
            os.unlink(temp_path)

    def test_export_report_markdown(self):
        numista_items = [
            make_numista_item("5001", "50 cents", "Newfoundland", "1900", "F-12"),
        ]
        self.engine.analyze_data(numista_items)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            temp_path = f.name

        try:
            self.engine.export_report_markdown(temp_path)
            with open(temp_path, 'r') as f:
                content = f.read()
            self.assertIn('Numista Intelligence Report', content)
            self.assertIn('Summary', content)
        finally:
            os.unlink(temp_path)

    def test_error_report_on_load_failure(self):
        report = self.engine.analyze_file('nonexistent_file.csv')
        self.assertEqual(report.total_numista_items, 0)
        self.assertEqual(report.analyzed_items, 0)
        self.assertGreater(len(report.warnings), 0)
        self.assertIn("Failed to load", report.warnings[0])

    def test_export_without_report_raises(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            temp_path = f.name
        try:
            with self.assertRaises(ValueError):
                self.engine.export_report_csv(temp_path)
        finally:
            os.unlink(temp_path)


class TestRunNumistaIntelligence(unittest.TestCase):
    """Verify convenience function behavior."""

    def test_run_with_csv_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['N# number (with link)', 'Title', 'Country', 'Year', 'Grade'])
            writer.writerow(['N#9999', 'Test', 'Canada', '1960', 'VF-20'])
            temp_path = f.name

        # Create empty collection file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as cf:
            json.dump([], cf)
            collection_path = cf.name

        try:
            report = run_numista_intelligence(temp_path, collection_path)
            self.assertIsInstance(report, NumistaIntelligenceReport)
            self.assertEqual(report.total_numista_items, 1)
        finally:
            os.unlink(temp_path)
            os.unlink(collection_path)


if __name__ == '__main__':
    unittest.main()
