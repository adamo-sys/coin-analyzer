import os
import tempfile
import unittest

from field_test_framework import (
    FalsePositiveAudit,
    FieldTestReport,
    OpportunityQualityReport,
    PipelineHealthReport,
    ScenarioRunner,
    default_field_test_scenarios,
)
from live_deal_hunter import LiveListing, LiveListingBatch, LiveDealHunter
from watchlist_engine import Watchlist, WatchlistEngine, WatchlistItem, WatchPriority, WATCH_TYPE_SERIES


class TestFieldTestFramework(unittest.TestCase):
    def test_scenario_library_contains_required_cases(self):
        scenarios = default_field_test_scenarios()
        names = {scenario.name for scenario in scenarios}

        self.assertIn("Newfoundland upgrade", names)
        self.assertIn("Newfoundland duplicate", names)
        self.assertIn("1859 variety candidate", names)
        self.assertIn("1926 Near 6 candidate", names)
        self.assertIn("Canadian silver lot", names)
        self.assertIn("Banknote opportunity", names)
        self.assertIn("High shipping trap", names)
        self.assertIn("Non-CAD listing", names)
        self.assertIn("Weak title listing", names)
        self.assertIn("Duplicate URL listing", names)
        self.assertIn("False positive watchlist match", names)
        self.assertIn("Strong watchlist match", names)

    def test_scenario_execution_runs_existing_pipeline(self):
        scenario = default_field_test_scenarios()[0]

        result = ScenarioRunner().run_scenario(scenario)

        self.assertEqual(result.scenario.name, "Newfoundland upgrade")
        self.assertEqual(result.pipeline_health.listings_processed, 1)
        self.assertGreaterEqual(result.pipeline_health.accepted_count, 0)
        self.assertIsNotNone(result.live_deal_hunter_report.validation_report)
        self.assertIsInstance(result.opportunity_quality, OpportunityQualityReport)

    def test_pipeline_health_reporting_counts_duplicates(self):
        duplicate_scenario = [scenario for scenario in default_field_test_scenarios() if scenario.name == "Duplicate URL listing"][0]

        result = ScenarioRunner().run_scenario(duplicate_scenario)

        self.assertEqual(result.pipeline_health.listings_processed, 2)
        self.assertGreaterEqual(result.pipeline_health.duplicates_detected, 1)
        self.assertIn(result.pipeline_health.health_status, {"REVIEW", "WARNING"})

    def test_alert_tuning_lowers_souvenir_token_match_confidence(self):
        watchlist = Watchlist("Tuning", [
            WatchlistItem("Newfoundland", WATCH_TYPE_SERIES, "Newfoundland", WatchPriority.CRITICAL),
        ])
        listing = LiveListing(
            title="Newfoundland dog token souvenir not coin",
            price=10,
            shipping=3,
            seller="Seller",
            source="Fixture",
            url="https://field.test/token",
            raw_metadata={"description": "Newfoundland dog token souvenir not coin"},
        )

        result = ScenarioRunner(watchlists=[watchlist]).run_scenario(
            default_field_test_scenarios()[-2]
        )
        direct_report = WatchlistEngine([watchlist]).scan([listing.to_deal_listing()])

        self.assertTrue(direct_report.matches)
        self.assertLess(direct_report.matches[0].confidence, 75)
        self.assertGreaterEqual(result.false_positive_audit.finding_count, 1)

    def test_opportunity_quality_reporting_tracks_review_and_confidence(self):
        scenario = default_field_test_scenarios()[0]
        live_report = LiveDealHunter([], []).analyze_batch(scenario.to_batch())
        candidates = live_report.market_enrichment_report.enriched_candidates

        report = OpportunityQualityReport.from_candidates(candidates)

        self.assertGreaterEqual(report.total_recommendations, 1)
        self.assertGreaterEqual(
            report.buy_recommendations + report.review_recommendations + report.pass_recommendations
            + report.watch_recommendations + report.negotiate_recommendations,
            1,
        )

    def test_false_positive_audit_flags_weak_keyword_and_duplicate(self):
        duplicate_scenario = [scenario for scenario in default_field_test_scenarios() if scenario.name == "Duplicate URL listing"][0]
        result = ScenarioRunner().run_scenario(duplicate_scenario)

        audit = result.false_positive_audit

        self.assertIsInstance(audit, FalsePositiveAudit)
        self.assertGreaterEqual(audit.finding_count, 1)
        self.assertIn("False Positive Audit", audit.format_markdown())

    def test_field_test_report_export_generation(self):
        report = ScenarioRunner().run_scenarios(default_field_test_scenarios()[:2])

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "field.csv")
            md_path = os.path.join(temp_dir, "field.md")
            quality_csv = os.path.join(temp_dir, "quality.csv")
            health_md = os.path.join(temp_dir, "health.md")
            false_csv = os.path.join(temp_dir, "false.csv")

            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            self.assertTrue(report.results[0].opportunity_quality.export_csv(quality_csv))
            self.assertTrue(report.results[0].pipeline_health.export_markdown(health_md))
            self.assertTrue(report.results[0].false_positive_audit.export_csv(false_csv))

            with open(csv_path, encoding="utf-8") as handle:
                self.assertIn("scenario_id", handle.readline())
            with open(md_path, encoding="utf-8") as handle:
                self.assertIn("Field Test & Tuning Report", handle.read())

    def test_full_default_field_test_report(self):
        report = ScenarioRunner().run_scenarios(default_field_test_scenarios())

        self.assertIsInstance(report, FieldTestReport)
        self.assertGreaterEqual(report.scenario_count, 12)
        self.assertGreaterEqual(report.review_count, 1)


if __name__ == "__main__":
    unittest.main()
