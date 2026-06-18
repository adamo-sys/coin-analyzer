"""Tests for the v2.0 Collector Operating System consolidation layer."""

import os
import tempfile
import unittest

from coin_collection import CoinItem
from collector_operating_system import (
    CollectionHealthReportEngine,
    CollectorHome,
    PersistenceFinding,
)
from legacy_portfolio_importer import LegacyWantListIntent
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord
from photo_vault import PhotoRecord
from smart_shopping_assistant import ShoppingCandidate


def make_item(item_id, country, denomination, year, grade, **overrides):
    data = {
        "id": item_id,
        "image_path": "",
        "country": country,
        "denomination": denomination,
        "year": year,
        "grade": grade,
        "notes": "",
        "date_added": "2026-06-18",
    }
    data.update(overrides)
    return CoinItem(**data)


def make_intent(target_coin, priority_score=80):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id="legacy_want_list_2",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=150.0,
        why_wanted="Collector Operating System test target",
        status="Active",
        priority_score=priority_score,
    )


class TestCollectorOperatingSystem(unittest.TestCase):
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
        self.want_list = [make_intent("Newfoundland 50 cents 1904")]
        self.market = MarketAwarenessEngine(
            observations=[
                ObservedPriceRecord(
                    item_name="Newfoundland 50 cents 1904",
                    country="Newfoundland",
                    denomination="50 cents",
                    year="1904",
                    grade="VF-20",
                    observed_price=125,
                    shipping=10,
                    source="Local observation",
                    notes="Comparable opportunity",
                    linked_photo_ids=["photo-1"],
                )
            ]
        )
        self.photos = [
            PhotoRecord(
                file_path="coin_photos/collection/Newfoundland/1900-20c.jpg",
                photo_type="Collection Photo",
                linked_collection_item_id="1",
                linked_coin_name="Newfoundland 20 cents 1900",
                pcgs_number="PCGS123",
            )
        ]
        self.candidates = [
            ShoppingCandidate(
                item_name="Newfoundland 50 cents 1904",
                source="Manual",
                asking_price=120,
                shipping=5,
                recommendation_source="Test",
            )
        ]

    def test_collector_home_generates_summary(self):
        home = CollectorHome(
            self.items,
            self.want_list,
            self.candidates,
            market_awareness_engine=self.market,
            photo_records=self.photos,
        ).generate_home()

        self.assertEqual(home.collection_summary["total_collection_items"], 7)
        self.assertEqual(home.collection_summary["total_want_list_items"], 1)
        self.assertGreaterEqual(home.collection_quality_score, 0)
        self.assertIn("items with photos", home.photo_coverage_summary)
        self.assertTrue(home.workflow_steps)

    def test_collector_home_reuses_smart_shopping_output(self):
        home = CollectorHome(
            self.items,
            self.want_list,
            self.candidates,
            market_awareness_engine=self.market,
        ).generate_home()

        self.assertIn("Newfoundland 50 cents 1904", home.best_next_purchase)
        self.assertIn("score", home.best_next_purchase)

    def test_collection_health_report_combines_existing_engines(self):
        report = CollectionHealthReportEngine(
            self.items,
            self.want_list,
            self.candidates,
            market_awareness_engine=self.market,
            photo_records=self.photos,
        ).generate_report()

        self.assertEqual(report.dashboard_data.snapshot.total_collection_items, 7)
        self.assertTrue(report.series_reports)
        self.assertTrue(report.shopping_report.recommendations)
        self.assertIn("observation_count", report.market_summary)
        self.assertTrue(report.priorities)

    def test_end_to_end_workflow_mentions_core_steps(self):
        markdown = CollectorHome(
            self.items,
            self.want_list,
            self.candidates,
            market_awareness_engine=self.market,
            photo_records=self.photos,
        ).format_markdown()

        self.assertIn("Listing Analyzer", markdown)
        self.assertIn("Acquisition Impact", markdown)
        self.assertIn("Smart Shopping Assistant", markdown)
        self.assertIn("Photo Vault", markdown)
        self.assertIn("Market Awareness", markdown)
        self.assertIn("Collection Health Report", markdown)

    def test_health_report_exports_csv_and_markdown(self):
        engine = CollectionHealthReportEngine(
            self.items,
            self.want_list,
            self.candidates,
            market_awareness_engine=self.market,
            photo_records=self.photos,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "health.csv")
            md_path = os.path.join(temp_dir, "health.md")

            self.assertTrue(engine.export_csv(csv_path))
            self.assertTrue(engine.export_markdown(md_path))

            with open(csv_path, "r", encoding="utf-8") as handle:
                csv_text = handle.read()
            with open(md_path, "r", encoding="utf-8") as handle:
                markdown_text = handle.read()

        self.assertIn("Persistence Audit", csv_text)
        self.assertIn("# Collection Health Report", markdown_text)
        self.assertIn("## Persistence Audit", markdown_text)

    def test_collector_home_exports_csv_and_markdown(self):
        home = CollectorHome(
            self.items,
            self.want_list,
            self.candidates,
            market_awareness_engine=self.market,
            photo_records=self.photos,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "home.csv")
            md_path = os.path.join(temp_dir, "home.md")

            self.assertTrue(home.export_csv(csv_path))
            self.assertTrue(home.export_markdown(md_path))

            with open(csv_path, "r", encoding="utf-8") as handle:
                csv_text = handle.read()
            with open(md_path, "r", encoding="utf-8") as handle:
                markdown_text = handle.read()

        self.assertIn("Best Next Purchase", csv_text)
        self.assertIn("# Collector Home", markdown_text)
        self.assertIn("## Collector Workflow", markdown_text)

    def test_persistence_findings_document_restart_behavior(self):
        findings = CollectionHealthReportEngine(self.items).persistence_audit()
        by_area = {finding.area: finding for finding in findings}

        self.assertIsInstance(findings[0], PersistenceFinding)
        self.assertTrue(by_area["Collection JSON"].survives_restart)
        self.assertFalse(by_area["Shared Session Context"].survives_restart)
        self.assertTrue(by_area["Series Definitions"].survives_restart)

    def test_empty_collection_is_supported(self):
        home = CollectorHome([]).generate_home()
        report = CollectionHealthReportEngine([]).generate_report()

        self.assertEqual(home.collection_summary["total_collection_items"], 0)
        self.assertEqual(report.dashboard_data.snapshot.total_collection_items, 0)
        self.assertTrue(report.persistence_findings)

    def test_photo_and_market_context_are_reflected(self):
        report = CollectionHealthReportEngine(
            self.items,
            self.want_list,
            self.candidates,
            market_awareness_engine=self.market,
            photo_records=self.photos,
        ).generate_report()

        self.assertEqual(report.dashboard_data.photo_coverage.items_with_photos, 1)
        self.assertEqual(report.market_summary["observation_count"], 1)


if __name__ == "__main__":
    unittest.main()
