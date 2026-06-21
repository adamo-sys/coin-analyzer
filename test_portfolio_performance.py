import os
import tempfile
import unittest

from coin_collection import CoinItem
from collection_snapshot import CollectionSnapshot, CollectionSnapshotManager
from legacy_portfolio_importer import LegacyWantListIntent
from market_awareness import MarketAwarenessEngine, PurchaseRecord
from portfolio_performance import (
    CollectionHealthScore,
    PortfolioPerformanceEngine,
    PortfolioPerformanceReport,
)


def item(
    item_id,
    country,
    denomination,
    year,
    grade="VF-20",
    estimate=0,
    notes="",
    title="",
):
    return CoinItem(
        item_id,
        "",
        country,
        denomination,
        year,
        grade,
        notes,
        "2026-06-21",
        estimate_cad=estimate,
        title=title,
    )


def want(target_coin, priority="High"):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id=f"want-{target_coin}",
        target_coin=target_coin,
        priority=priority,
        target_grade="VF-20",
        budget=100,
        why_wanted="Portfolio performance fixture",
        status="Active",
        priority_score=80,
    )


class TestPortfolioPerformance(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.snapshot_path = os.path.join(self.tempdir.name, "snapshots.json")
        self.snapshot_manager = CollectionSnapshotManager(self.snapshot_path)
        self.items = [
            item("1", "Newfoundland", "50 cents", "1900", "VF-20", 120, notes="ICCS XSZ123"),
            item("2", "Newfoundland", "50 cents", "1902", "VF-20", 110),
            item("3", "Canada", "10 cents", "1911", "VF-20", 55, notes="silver"),
            item("4", "Canada", "1 cent", "1859", "G-4", 30),
            item("5", "Canada", "1 cent", "1859", "VF-20", 90),
            item("6", "Canada", "Banknote", "1937", "VF-20", 75, title="1937 Canada banknote"),
        ]
        self.wants = [want("Newfoundland 50 cents 1901")]
        self.market = MarketAwarenessEngine(
            purchases=[PurchaseRecord("1901 Newfoundland 50 cents", purchase_price=90, shipping=5)]
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def engine(self):
        return PortfolioPerformanceEngine(
            self.items,
            self.wants,
            market_awareness_engine=self.market,
            snapshot_manager=self.snapshot_manager,
        )

    def test_growth_analysis(self):
        report = self.engine().collection_growth_report()
        self.assertEqual(report.collection_size, 6)
        self.assertEqual(report.estimated_collection_value, 480.0)
        self.assertGreaterEqual(report.silver_holdings, 1)
        self.assertEqual(report.newfoundland_count, 2)
        self.assertGreaterEqual(report.banknote_count, 1)

    def test_acquisition_analysis(self):
        report = self.engine().acquisition_performance_report()
        self.assertTrue(report.best_acquisitions)
        self.assertTrue(report.strongest_opportunity_captures)
        self.assertTrue(report.highest_collection_impact)

    def test_series_progress(self):
        report = self.engine().series_progress_report()
        names = [row.series_name for row in report.series_reports]
        self.assertTrue(any("Newfoundland" in name for name in names))
        self.assertTrue(report.nearest_completions or report.neglected_series)

    def test_budget_allocation(self):
        report = self.engine().budget_allocation_report()
        self.assertGreaterEqual(report.category_counts["Newfoundland"], 2)
        self.assertGreaterEqual(report.category_counts["Canadian silver"], 1)
        self.assertGreaterEqual(report.category_counts["Banknotes"], 1)
        self.assertGreater(report.category_estimated_values["Newfoundland"], 0)

    def test_health_score(self):
        score = self.engine().collection_health_score()
        self.assertIsInstance(score, CollectionHealthScore)
        self.assertGreaterEqual(score.score, 0)
        self.assertLessEqual(score.score, 100)
        self.assertIn("backup_readiness", score.category_scores)
        self.assertIn("snapshot_coverage", score.category_scores)

    def test_snapshot_comparison(self):
        previous = CollectionSnapshot(
            snapshot_timestamp="2026-06-20 12:00:00",
            collection_size=4,
            quality_score=50,
            integrity_score=60,
            photo_coverage=10.0,
            series_completion_metrics={"Newfoundland 50 Cents": 20.0},
            market_record_count=0,
            shopping_candidate_count=0,
        )
        self.snapshot_manager.save_snapshot(previous)
        growth = self.engine().collection_growth_report()
        self.assertIsNotNone(growth.snapshot_comparison)
        self.assertEqual(growth.snapshot_comparison.growth_summary.growth_since_last_snapshot, 2)

    def test_executive_dashboard(self):
        report = self.engine().generate_report()
        self.assertIsInstance(report, PortfolioPerformanceReport)
        self.assertGreaterEqual(report.health_score.score, 0)
        self.assertTrue(report.strengths or report.weaknesses)
        self.assertTrue(report.recommended_focus_areas)
        self.assertIn("Portfolio Performance Report", report.format_markdown())

    def test_export_generation(self):
        report = self.engine().generate_report()
        csv_path = os.path.join(self.tempdir.name, "portfolio.csv")
        md_path = os.path.join(self.tempdir.name, "portfolio.md")
        self.assertTrue(report.export_csv(csv_path))
        self.assertTrue(report.export_markdown(md_path))
        self.assertTrue(os.path.exists(csv_path))
        self.assertTrue(os.path.exists(md_path))
        with open(md_path, "r", encoding="utf-8") as handle:
            self.assertIn("Portfolio Performance Report", handle.read())


if __name__ == "__main__":
    unittest.main()
