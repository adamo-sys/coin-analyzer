"""Tests for v2.8 Collector Home Dashboard."""

import os
import tempfile
import unittest

from backup_manager import BackupManager
from coin_collection import CoinItem
from collection_snapshot import CollectionSnapshotManager
from collector_home_dashboard import (
    CollectorHomeDashboard,
    CollectorHomeReport,
    DailyCollectorAction,
    HomeStatusCard,
    HomeStatusSeverity,
)
from legacy_portfolio_importer import LegacyWantListIntent
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord
from ocr_experiment import OCRExperiment
from persistence_manager import AppState, PersistenceManager
from photo_assisted_entry import PhotoCandidate
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
        "date_added": "2026-06-19",
    }
    data.update(overrides)
    return CoinItem(**data)


def make_intent(target_coin):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id="home-want-1",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=150.0,
        why_wanted="Collector Home target",
        status="Active",
        priority_score=85,
    )


class TestCollectorHomeDashboard(unittest.TestCase):
    def setUp(self):
        self.items = [
            make_item("1", "Newfoundland", "20 cents", "1900", "F-12"),
            make_item("2", "Newfoundland", "20 cents", "1901", "VF-20"),
            make_item("3", "Canada", "10 cents", "1911", "VF-20", notes="PCGS certified"),
            make_item("4", "Canada", "10 cents", "1911", "EF-40"),
            make_item("5", "Canada", "1 cent", "1859", "VG-8"),
        ]
        self.want_list = [make_intent("Newfoundland 50 cents 1904")]
        self.shopping = [
            ShoppingCandidate(
                item_name="Newfoundland 50 cents 1904",
                asking_price=120,
                shipping=5,
                source="Dealer table",
                recommendation_source="Test",
            )
        ]
        self.market = MarketAwarenessEngine(
            observations=[
                ObservedPriceRecord(
                    item_name="Newfoundland 50 cents 1904",
                    country="Newfoundland",
                    denomination="50 cents",
                    year="1904",
                    grade="VF-20",
                    observed_price=125,
                    shipping=5,
                    source="Local observation",
                )
            ]
        )

    def make_dashboard(self, temp_dir, **overrides):
        manager = PersistenceManager(state_dir=os.path.join(temp_dir, "state"))
        backup = BackupManager(
            backup_dir=os.path.join(temp_dir, "backups"),
            persistence_manager=manager,
            collection_json_path=os.path.join(temp_dir, "collection.json"),
        )
        snapshot = CollectionSnapshotManager(os.path.join(temp_dir, "snapshots.json"))
        kwargs = {
            "collection_items": self.items,
            "want_list_intents": self.want_list,
            "shopping_candidates": self.shopping,
            "market_awareness_engine": self.market,
            "snapshot_manager": snapshot,
            "backup_manager": backup,
        }
        kwargs.update(overrides)
        return CollectorHomeDashboard(**kwargs)

    def test_home_dashboard_imports_and_generates_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report = self.make_dashboard(temp_dir).generate_report()

            self.assertIsInstance(report, CollectorHomeReport)
            self.assertEqual(len(report.status_cards), 5)
            self.assertTrue(report.daily_actions)
            self.assertIn("Collector Home Dashboard", report.format_markdown())

    def test_daily_action_ranking_prefers_action_required(self):
        actions = [
            DailyCollectorAction("Routine review", urgency=100, severity=HomeStatusSeverity.INFO, source="Test"),
            DailyCollectorAction("Back up collection data", urgency=50, severity=HomeStatusSeverity.ACTION_REQUIRED, source="Test"),
        ]

        ordered = sorted(actions, key=lambda action: action.rank_key)

        self.assertEqual(ordered[0].title, "Back up collection data")

    def test_status_severity_calculation(self):
        card = HomeStatusCard(
            "Data Safety",
            HomeStatusSeverity.ACTION_REQUIRED,
            "Backup missing",
            metrics={"Issue count": 1},
        )

        self.assertEqual(card.severity, "ACTION_REQUIRED")
        self.assertEqual(card.metrics["Issue count"], 1)

    def test_backup_status_card_surfaces_missing_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report = self.make_dashboard(temp_dir).generate_report()
            card = next(card for card in report.status_cards if card.title == "Data Safety")

            self.assertIn(card.severity, {"WARNING", "ACTION_REQUIRED"})
            self.assertTrue(any("collection" in warning.lower() or "backup" in warning.lower() for warning in report.warnings))

    def test_integrity_status_card_uses_integrity_report(self):
        bad_items = self.items + [make_item("6", "", "", "", "")]
        with tempfile.TemporaryDirectory() as temp_dir:
            report = self.make_dashboard(temp_dir, collection_items=bad_items).generate_report()
            card = next(card for card in report.status_cards if card.title == "Collection Health")

            self.assertIn(card.severity, {"WARNING", "ACTION_REQUIRED"})
            self.assertGreaterEqual(card.metrics["Collection items"], 6)

    def test_ocr_review_status_card_counts_low_trust_items(self):
        ocr_report = OCRExperiment().run("coin.jpg", raw_text="blurred")
        with tempfile.TemporaryDirectory() as temp_dir:
            report = self.make_dashboard(temp_dir, ocr_reports=[ocr_report]).generate_report()
            card = next(card for card in report.status_cards if card.title == "Review Queue")

            self.assertEqual(card.metrics["OCR items awaiting review"], 1)
            self.assertEqual(card.severity, "WARNING")

    def test_photo_coverage_status_card_reports_photo_issues(self):
        photo = PhotoRecord(
            file_path=os.path.join("missing", "coin.jpg"),
            photo_type="Collection Photo",
            linked_collection_item_id="1",
            linked_coin_name="Newfoundland 20 cents 1900",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            report = self.make_dashboard(temp_dir, photo_records=[photo]).generate_report()
            card = next(card for card in report.status_cards if card.title == "Review Queue")

            self.assertGreaterEqual(card.metrics["Photo issues"], 1)
            self.assertIn("Add", " ".join(card.actions))

    def test_snapshot_trend_status_card_reports_progress(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dashboard = self.make_dashboard(temp_dir)
            previous = dashboard.snapshot_manager.create_snapshot(self.items[:2], self.want_list)
            dashboard.snapshot_manager.save_snapshot(previous)

            report = dashboard.generate_report()
            card = next(card for card in report.status_cards if card.title == "Progress")

            self.assertIn("Growth since last snapshot", card.metrics)
            self.assertGreaterEqual(card.metrics["Growth since last snapshot"], 0)
            self.assertTrue(report.recent_progress)

    def test_top_opportunity_card_uses_smart_shopping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report = self.make_dashboard(temp_dir).generate_report()
            card = next(card for card in report.status_cards if card.title == "Acquisition Focus")

            self.assertIn("Newfoundland 50 cents 1904", card.headline)
            self.assertTrue(report.top_opportunities)

    def test_export_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report = self.make_dashboard(temp_dir).generate_report()
            csv_path = os.path.join(temp_dir, "home.csv")
            md_path = os.path.join(temp_dir, "home.md")

            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))

            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("Daily Action", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("## Status Cards", handle.read())

    def test_persistence_compatibility_for_home_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PersistenceManager(state_dir=os.path.join(temp_dir, "state"))
            report = self.make_dashboard(temp_dir).generate_report()
            action_id = report.daily_actions[0].action_id

            state = manager.create_state(
                home_reports=[report.to_dict()],
                acknowledged_home_actions=[action_id],
            )
            saved = manager.save_state(state)
            loaded = manager.load_state()

            self.assertTrue(saved.success)
            self.assertEqual(len(loaded.state.home_reports), 1)
            self.assertEqual(loaded.state.acknowledged_home_actions, [action_id])
            restored = CollectorHomeReport.from_dict(loaded.state.home_reports[0])
            self.assertEqual(restored.summary_headline, report.summary_headline)

    def test_dashboard_remains_useful_without_optional_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report = self.make_dashboard(
                temp_dir,
                collection_items=[],
                want_list_intents=[],
                shopping_candidates=[],
                market_awareness_engine=MarketAwarenessEngine(),
            ).generate_report()

            self.assertEqual(len(report.status_cards), 5)
            self.assertTrue(report.summary_headline)
            self.assertTrue(report.daily_actions)


if __name__ == "__main__":
    unittest.main()
