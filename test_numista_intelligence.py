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


class TestSlice2CNumistaContainment(unittest.TestCase):
    def test_r6_catalogue_equality_is_discovery_only(self):
        for country, year in (("", ""), ("Canada", "1900"), ("Argentina", "1960")):
            with self.subTest(country=country, year=year):
                engine = NumistaIntelligenceEngine.from_items([make_item("local", "Canada", "1 cent", "1900", numista_n="12345")])
                result = engine.analyze_data([make_numista_item("12345", "50 cents", country, year)]).item_analyses[0]
                self.assertEqual(result.status.value, "unresolved")
                self.assertIsNone(result.matched_collection_item)
                self.assertIn("discovery", " ".join(result.reasons).lower())

    def test_r6_malformed_catalogue_values_have_no_authority(self):
        for value in ("arbitrary", "123x", "0", "000", "１２３", "1" * 5000, False, None, 0):
            with self.subTest(value=value):
                engine = NumistaIntelligenceEngine.from_items([make_item("local", "", "", "", numista_n=value)])
                result = engine.analyze_data([make_numista_item(value, "", "", "")]).item_analyses[0]
                self.assertNotEqual(result.status, NumistaMatchStatus.OWNED)
                self.assertIsNone(result.matched_collection_item)

    def test_r7_weak_signatures_cannot_duplicate_or_upgrade(self):
        for numista_n in ("12346", "", None):
            for reference in ("", "KM1", "KM2"):
                for grade in ("", "UNKNOWN", "AU-50"):
                    with self.subTest(numista_n=numista_n, reference=reference, grade=grade):
                        engine = NumistaIntelligenceEngine.from_items([make_item("local", "Canada", "1 cent", "1900", "F-12", numista_n="12345", reference="KM1", title="portrait")])
                        report = engine.analyze_data([make_numista_item(numista_n, "different design", "Canada", "1900", grade, face_value="50 cents", reference=reference)])
                        self.assertEqual(report.duplicate_count, 0)
                        self.assertEqual(report.upgrade_count, 0)
                        self.assertEqual(report.duplicate_reports, [])
                        self.assertEqual(report.upgrade_reports, [])
                        self.assertIsNone(report.item_analyses[0].matched_collection_item)
                        self.assertEqual(report.item_analyses[0].upgrade_delta, 0)
                        self.assertEqual(report.item_analyses[0].status, NumistaMatchStatus.UNRESOLVED)
                        self.assertIn("discovery", " ".join(report.item_analyses[0].reasons).lower())

    def test_r8_no_hit_preserves_interest_without_gap_consequences(self):
        engine = NumistaIntelligenceEngine.from_items([])
        report = engine.analyze_data([make_numista_item("12345", "50 cents variety", "Newfoundland", "1888", estimate_cad=100)])
        result = report.item_analyses[0]
        self.assertEqual(result.status.value, "unresolved")
        self.assertTrue(result.series_relevance)
        self.assertIn("variety", " ".join(result.reasons).lower())
        self.assertEqual(result.gap_value, 0)
        self.assertEqual(result.priority, NumistaPriority.NONE)
        self.assertEqual(report.gap_count, 0)
        self.assertEqual(report.gap_reports, [])
        self.assertEqual(report.top_priorities, [])
        self.assertNotIn("acquir", " ".join(report.summary_recommendations).lower())

    def test_r9_failed_refresh_replaces_exported_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = NumistaIntelligenceEngine.from_items([])
            engine.analyze_data([make_numista_item("12345", "PREVIOUS-SYNTHETIC", "Newfoundland", "1888")])
            failed = engine.analyze_file(os.path.join(temp_dir, "missing.csv"))
            self.assertIs(engine.report, failed)
            for suffix in ("csv", "md"):
                path = os.path.join(temp_dir, "report." + suffix)
                if suffix == "csv":
                    engine.export_report_csv(path)
                else:
                    engine.export_report_markdown(path)
                with open(path, encoding="utf-8") as handle:
                    exported = handle.read()
                self.assertNotIn("PREVIOUS-SYNTHETIC", exported)
                self.assertNotIn("Consider acquiring", exported)
            self.assertIn("Failed to load", " ".join(failed.warnings))


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
        self.assertEqual(analysis.status, NumistaMatchStatus.UNRESOLVED)
        self.assertEqual(analysis.priority, NumistaPriority.NONE)
        self.assertIn("Catalogue discovery", analysis.reasons[0])
        self.assertIsNone(analysis.matched_collection_item)

    def test_duplicate_by_signature(self):
        numista_item = make_numista_item("9999", "50 cents", "Newfoundland", "1900", "F-12")
        analysis = self.analyzer.analyze_item(numista_item)
        self.assertEqual(analysis.status, NumistaMatchStatus.UNRESOLVED)
        self.assertEqual(analysis.priority, NumistaPriority.NONE)

    def test_upgrade_by_better_grade(self):
        numista_item = make_numista_item("9999", "50 cents", "Newfoundland", "1900", "AU-50")
        analysis = self.analyzer.analyze_item(numista_item)
        self.assertEqual(analysis.status, NumistaMatchStatus.UNRESOLVED)
        self.assertEqual(analysis.priority, NumistaPriority.NONE)
        self.assertEqual(analysis.upgrade_delta, 0)

    def test_newfoundland_gap(self):
        numista_item = make_numista_item("5003", "50 cents", "Newfoundland", "1904", "VF-20")
        analysis = self.analyzer.analyze_item(numista_item)
        self.assertEqual(analysis.status, NumistaMatchStatus.UNRESOLVED)
        self.assertEqual(analysis.priority, NumistaPriority.NONE)
        self.assertIn("Possible series interest", " ".join(analysis.reasons))
        self.assertEqual(analysis.gap_value, 0)

    def test_canadian_silver_gap(self):
        numista_item = make_numista_item("1003", "10 cents silver", "Canada", "1912", "VF-20")
        analysis = self.analyzer.analyze_item(numista_item)
        # Collecting-area interest does not establish a new unowned series.
        self.assertEqual(analysis.status, NumistaMatchStatus.UNRESOLVED)
        self.assertEqual(analysis.priority, NumistaPriority.NONE)

    def test_new_series_for_newfoundland(self):
        numista_item = make_numista_item("5004", "1 cent", "Newfoundland", "1913", "VF-20")
        analysis = self.analyzer.analyze_item(numista_item)
        # Heuristic series interest does not establish absence from holdings.
        self.assertEqual(analysis.status, NumistaMatchStatus.UNRESOLVED)
        self.assertEqual(analysis.priority, NumistaPriority.NONE)

    def test_not_relevant_for_unsupported_country(self):
        numista_item = make_numista_item("9999", "1 peso", "Argentina", "1960", "VF-20")
        analysis = self.analyzer.analyze_item(numista_item)
        self.assertEqual(analysis.status, NumistaMatchStatus.NOT_RELEVANT)
        self.assertEqual(analysis.priority, NumistaPriority.NONE)

    def test_variety_detection(self):
        numista_item = make_numista_item("1004", "1 cent large", "Canada", "1859", "VF-20",
                                         reference="Wide 9 variety")
        analysis = self.analyzer.analyze_item(numista_item)
        self.assertEqual(analysis.status, NumistaMatchStatus.UNRESOLVED)
        self.assertEqual(analysis.priority, NumistaPriority.NONE)
        self.assertIn("Possible variety interest", " ".join(analysis.reasons))

    def test_key_date_priority(self):
        numista_item = make_numista_item("5005", "50 cents", "Newfoundland", "1888", "VF-20")
        analysis = self.analyzer.analyze_item(numista_item)
        self.assertEqual(analysis.status, NumistaMatchStatus.UNRESOLVED)
        self.assertEqual(analysis.priority, NumistaPriority.NONE)

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
            make_numista_item("5001", "50 cents", "Newfoundland", "1900", "F-12"),  # Discovery/interest only.
            make_numista_item("5002x", "50 cents", "Newfoundland", "1902", "VF-20"),  # Discovery/interest only.
            make_numista_item("1002", "1 cent", "Canada", "1860", "VF-20"),  # not relevant (no series match)
        ]
        report = self.engine.analyze_data(numista_items)
        self.assertIsInstance(report, NumistaIntelligenceReport)
        self.assertEqual(report.total_numista_items, 3)
        self.assertEqual(report.owned_count, 0)  # Weak evidence withholds authority.
        self.assertEqual(report.gap_count, 0)  # Weak evidence withholds authority.
        self.assertEqual(report.not_relevant_count, 1)  # Canada 1 cent 1860 not in supported series

    def test_report_counts_are_correct(self):
        numista_items = [
            make_numista_item("5001", "50 cents", "Newfoundland", "1900", "F-12"),  # Discovery/interest only.
            make_numista_item("5001x", "50 cents", "Newfoundland", "1900", "F-12"),  # Discovery/interest only.
            make_numista_item("5002x", "50 cents", "Newfoundland", "1902", "AU-50"),  # Discovery/interest only.
            make_numista_item("5003", "50 cents", "Newfoundland", "1904", "VF-20"),  # Discovery/interest only.
            make_numista_item("9999", "1 peso", "Argentina", "1960", "VF-20"),  # not relevant
        ]
        report = self.engine.analyze_data(numista_items)
        self.assertEqual(report.owned_count, 0)  # Weak evidence withholds authority.
        self.assertEqual(report.duplicate_count, 0)  # Weak evidence withholds authority.
        self.assertEqual(report.upgrade_count, 0)  # No nf_1902 in engine collection to upgrade
        self.assertEqual(report.gap_count, 0)  # Weak evidence withholds authority.
        self.assertEqual(report.not_relevant_count, 1)  # Argentina

    def test_top_priorities_filtered_correctly(self):
        numista_items = [
            make_numista_item("5003", "50 cents", "Newfoundland", "1904", "VF-20"),  # Discovery/interest only.
            make_numista_item("1002", "1 cent", "Canada", "1860", "VF-20"),  # not relevant (no series match)
        ]
        report = self.engine.analyze_data(numista_items)
        self.assertEqual(report.top_priorities, [])  # No verified gap-based priority.

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
        self.assertEqual(d['owned_count'], 0)
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
            self.assertEqual(report.owned_count, 0)  # Weak evidence withholds authority.
            self.assertEqual(report.gap_count, 0)  # Weak evidence withholds authority.
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
