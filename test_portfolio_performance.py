import json
import os
import tempfile
import unittest
from decimal import Decimal

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
    **kwargs,
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
        **kwargs,
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

    def test_financial_summary_uses_exact_record_level_costs_and_quantity_for_estimates_only(self):
        items = [
            item(
                "cad",
                "Canada",
                "1 cent",
                "1967",
                estimate=20.125,
                quantity=3,
                purchase_price="10.125",
                shipping_cost="0.200",
                purchase_currency="CAD",
                acquisition_date="2025-04-03",
                purchase_source="Dealer",
            ),
            item(
                "usd",
                "United States",
                "1 cent",
                "1909",
                estimate=30,
                purchase_price="5.50",
                purchase_currency="USD",
                purchase_source="Auction",
            ),
            item(
                "unspecified",
                "Canada",
                "5 cents",
                "1922",
                estimate=40,
                purchase_price="2.25",
                purchase_currency=None,
            ),
        ]
        summary = PortfolioPerformanceEngine(items, snapshot_manager=self.snapshot_manager).portfolio_financial_summary()

        self.assertEqual(3, summary.collection_record_count)
        self.assertEqual(5, summary.total_quantity_count)
        self.assertEqual(Decimal("10.325"), summary.recorded_costs_by_currency["CAD"])
        self.assertEqual(Decimal("5.50"), summary.recorded_costs_by_currency["USD"])
        self.assertEqual(Decimal("2.25"), summary.recorded_costs_by_currency["Unspecified"])
        self.assertEqual(Decimal("10.325"), summary.comparable_cad_cost)
        self.assertEqual(Decimal("60.375"), summary.comparable_approximate_estimated_cad_value)
        self.assertEqual(Decimal("50.050"), summary.estimated_gain_loss)
        self.assertEqual(Decimal("484.75"), summary.estimated_roi_percent)

    def test_financial_summary_accepts_legacy_record_without_acquisition_fields(self):
        legacy = CoinItem.from_dict({
            "id": "legacy",
            "country": "Canada",
            "denomination": "1 cent",
            "year": "1967",
            "grade": "VF-20",
            "date_added": "2026-06-01",
            "estimate_cad": 12.5,
        })
        summary = PortfolioPerformanceEngine([legacy], snapshot_manager=self.snapshot_manager).portfolio_financial_summary()

        self.assertIsNone(legacy.purchase_currency)
        self.assertIsNone(legacy.total_cost)
        self.assertEqual(0, summary.acquisition_cost_record_count)
        self.assertEqual(1, summary.usable_valuation_record_count)
        self.assertEqual(1, summary.comparison_exclusions["no_recorded_acquisition_cost"])

    def test_none_and_explicit_zero_have_distinct_acquisition_coverage(self):
        items = [
            item("missing", "Canada", "1 cent", "1966", estimate=10, purchase_currency=None),
            item("zero", "Canada", "1 cent", "1967", estimate=10, purchase_price="0", purchase_currency="CAD"),
        ]
        summary = PortfolioPerformanceEngine(items, snapshot_manager=self.snapshot_manager).portfolio_financial_summary()

        self.assertEqual(1, summary.acquisition_cost_record_count)
        self.assertEqual(Decimal("50.0"), summary.acquisition_cost_coverage_percent)
        self.assertEqual(Decimal("0"), summary.recorded_costs_by_currency["CAD"])
        self.assertEqual(1, summary.comparable_cad_record_count)
        self.assertEqual(Decimal("10"), summary.estimated_gain_loss)
        self.assertIsNone(summary.estimated_roi_percent)

    def test_legacy_valuation_boundary_rejects_zero_negative_boolean_and_non_finite_values(self):
        items = [
            item("zero", "Canada", "1 cent", "1960", estimate=0),
            item("negative", "Canada", "1 cent", "1961", estimate=-1),
            item("boolean", "Canada", "1 cent", "1962", estimate=True),
            item("nan", "Canada", "1 cent", "1963", estimate=float("nan")),
            item("infinity", "Canada", "1 cent", "1964", estimate=float("inf")),
            item("usable", "Canada", "1 cent", "1965", estimate="12.340"),
        ]
        summary = PortfolioPerformanceEngine(items, snapshot_manager=self.snapshot_manager).portfolio_financial_summary()

        self.assertEqual(1, summary.usable_valuation_record_count)
        self.assertEqual(Decimal("12.340"), summary.approximate_estimated_cad_value)

    def test_comparable_cad_exclusions_are_mutually_exclusive(self):
        items = [
            item("no-cost", "Canada", "1 cent", "1960", estimate=10, purchase_currency=None),
            item("unspecified", "Canada", "1 cent", "1961", estimate=10, purchase_price="1", purchase_currency=None),
            item("usd", "Canada", "1 cent", "1962", estimate=10, purchase_price="1", purchase_currency="USD"),
            item("no-value", "Canada", "1 cent", "1963", estimate=0, purchase_price="1", purchase_currency="CAD"),
            item("eligible", "Canada", "1 cent", "1964", estimate=10, purchase_price="1", purchase_currency="CAD"),
        ]
        summary = PortfolioPerformanceEngine(items, snapshot_manager=self.snapshot_manager).portfolio_financial_summary()

        self.assertEqual(1, summary.comparable_cad_record_count)
        self.assertEqual(4, summary.comparable_excluded_record_count)
        self.assertEqual(4, sum(summary.comparison_exclusions.values()))
        self.assertEqual(1, summary.comparison_exclusions["no_recorded_acquisition_cost"])
        self.assertEqual(1, summary.comparison_exclusions["unspecified_currency"])
        self.assertEqual(1, summary.comparison_exclusions["non_cad_currency"])
        self.assertEqual(1, summary.comparison_exclusions["no_usable_valuation_estimate"])

    def test_source_and_year_breakdowns_include_missing_buckets_and_isolate_currency(self):
        items = [
            item(
                "dated",
                "Canada",
                "1 cent",
                "1967",
                purchase_price="2.50",
                purchase_currency="CAD",
                purchase_source="Dealer",
                acquisition_date="2024-05-01",
            ),
            item(
                "missing",
                "Canada",
                "1 cent",
                "1968",
                purchase_price="3.75",
                purchase_currency="USD",
            ),
        ]
        summary = PortfolioPerformanceEngine(items, snapshot_manager=self.snapshot_manager).portfolio_financial_summary()
        sources = {row.label: row for row in summary.source_breakdown}
        years = {row.label: row for row in summary.acquisition_year_breakdown}

        self.assertEqual(Decimal("2.50"), sources["Dealer"].recorded_costs_by_currency["CAD"])
        self.assertEqual(Decimal("3.75"), sources["Unspecified source"].recorded_costs_by_currency["USD"])
        self.assertEqual(Decimal("2.50"), years["2024"].recorded_costs_by_currency["CAD"])
        self.assertEqual(Decimal("3.75"), years["No acquisition date"].recorded_costs_by_currency["USD"])

    def test_financial_reporting_is_read_only_and_json_safe(self):
        items = [
            item(
                "stable",
                "Canada",
                "1 cent",
                "1967",
                estimate=5.5,
                purchase_price="1.250",
                purchase_currency="CAD",
            )
        ]
        before = [row.to_dict() for row in items]
        report = PortfolioPerformanceEngine(items, snapshot_manager=self.snapshot_manager).generate_report()
        after = [row.to_dict() for row in items]

        self.assertEqual(before, after)
        json.dumps(report.to_dict())
        self.assertEqual("1.250", report.financial_summary.to_dict()["comparable_cad_cost"])

    def test_financial_exports_are_deterministic_and_label_legacy_estimates(self):
        items = [
            item(
                "export",
                "Canada",
                "1 cent",
                "1967",
                estimate=10,
                purchase_price="4",
                purchase_currency="CAD",
            )
        ]
        report = PortfolioPerformanceEngine(items, snapshot_manager=self.snapshot_manager).generate_report()
        first_csv = os.path.join(self.tempdir.name, "first.csv")
        second_csv = os.path.join(self.tempdir.name, "second.csv")
        first_md = os.path.join(self.tempdir.name, "first.md")
        second_md = os.path.join(self.tempdir.name, "second.md")
        report.export_csv(first_csv)
        report.export_csv(second_csv)
        report.export_markdown(first_md)
        report.export_markdown(second_md)

        with open(first_csv, "r", encoding="utf-8") as handle:
            csv_text = handle.read()
        with open(second_csv, "r", encoding="utf-8") as handle:
            self.assertEqual(csv_text, handle.read())
        with open(first_md, "r", encoding="utf-8") as handle:
            markdown = handle.read()
        with open(second_md, "r", encoding="utf-8") as handle:
            self.assertEqual(markdown, handle.read())
        self.assertIn("approximate_estimated_cad_value", csv_text)
        self.assertIn("Approximate legacy estimated CAD value", markdown)
        self.assertIn("Estimated ROI", markdown)


if __name__ == "__main__":
    unittest.main()
