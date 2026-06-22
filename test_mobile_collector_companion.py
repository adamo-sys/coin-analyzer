import os
import tempfile
import unittest

from deal_hunter import DealListing
from mobile_collector_companion import (
    MobileCollectorCompanion,
    MobileCompanionReport,
    MobileSession,
    WORKFLOW_AUCTION_PREVIEW,
    WORKFLOW_COIN_SHOW,
)
from photo_capture_workflow import PhotoCaptureWorkflow
from watchlist_engine import Watchlist, WatchlistItem, WatchPriority, WATCH_TYPE_SERIES


class TestMobileCollectorCompanion(unittest.TestCase):
    def make_listing(self, title="Newfoundland 1904H 50 cents EF40", price=145.0):
        return DealListing(
            title=title,
            price_cad=price,
            shipping_cad=12.0,
            seller="Field Dealer",
            source="Coin Show",
            listing_url="https://field.test/candidate",
            description=title,
        )

    def test_mobile_session_creation(self):
        companion = MobileCollectorCompanion()

        session = companion.start_session(WORKFLOW_COIN_SHOW, location="Bourse floor", notes="Quick review")

        self.assertIsInstance(session, MobileSession)
        self.assertEqual(session.workflow_type, WORKFLOW_COIN_SHOW)
        self.assertIn("coin-show", session.session_id)

    def test_mobile_workflows_include_required_field_workflows(self):
        names = {workflow.name for workflow in MobileCollectorCompanion.workflows()}

        self.assertIn("Coin Show Workflow", names)
        self.assertIn("Dealer Visit Workflow", names)
        self.assertIn("Antique Market Workflow", names)
        self.assertIn("Coin Shop Workflow", names)
        self.assertIn("Auction Preview Workflow", names)

    def test_quick_decision_summary_uses_existing_intelligence(self):
        companion = MobileCollectorCompanion()

        decision = companion.quick_decision(self.make_listing())

        self.assertIn(decision.recommendation, {"BUY", "WATCH", "PASS", "REVIEW"})
        self.assertGreaterEqual(decision.confidence, 0)
        self.assertTrue(decision.top_reasons)
        self.assertIn("Newfoundland", decision.candidate_title)

    def test_mobile_collection_context_contains_watchlists_and_priorities(self):
        watchlist = Watchlist("Field Watches", [
            WatchlistItem("Newfoundland", WATCH_TYPE_SERIES, "Newfoundland", WatchPriority.CRITICAL)
        ])
        companion = MobileCollectorCompanion(watchlists=[watchlist])

        context = companion.collection_context([self.make_listing()])

        self.assertIn("active target", context.watchlist_summary)
        self.assertIn("Newfoundland", "; ".join(context.active_targets))
        self.assertIn("Newfoundland coinage", context.collection_priorities)

    def test_mobile_dashboard_surfaces_decisions_alerts_and_targets(self):
        companion = MobileCollectorCompanion()

        dashboard = companion.dashboard([self.make_listing("Canada 1926 Near 6 nickel VF", 95)])

        self.assertTrue(dashboard.active_watchlists)
        self.assertTrue(dashboard.quick_decisions)
        self.assertTrue(dashboard.high_priority_targets)

    def test_field_work_mode_is_short_form(self):
        companion = MobileCollectorCompanion()

        mode = companion.field_work_mode([
            self.make_listing("Canada 1973 Large Bust quarter ICCS AU", 140),
            self.make_listing("World base metal token souvenir", 5),
        ])

        self.assertIn("candidate", mode.minimal_summary)
        self.assertEqual(len(mode.quick_decisions), 2)

    def test_mobile_report_generation_and_exports(self):
        companion = MobileCollectorCompanion()

        report = companion.generate_report([self.make_listing()], workflow_type=WORKFLOW_AUCTION_PREVIEW)

        self.assertIsInstance(report, MobileCompanionReport)
        self.assertEqual(report.workflow.name, WORKFLOW_AUCTION_PREVIEW)
        self.assertIn("Mobile Collector Companion Report", report.format_markdown())

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "mobile.csv")
            md_path = os.path.join(temp_dir, "mobile.md")
            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            with open(csv_path, encoding="utf-8") as handle:
                self.assertIn("candidate_title", handle.readline())
            with open(md_path, encoding="utf-8") as handle:
                self.assertIn("Mobile Collector Companion Report", handle.read())

    def test_mobile_report_includes_phone_photo_capture_summary(self):
        photo_workflow = PhotoCaptureWorkflow()
        photo_workflow.capture_coin_pair("Canada 1911 10 cents", front_path="front.jpg")
        companion = MobileCollectorCompanion(photo_capture_workflow=photo_workflow)

        report = companion.generate_report([self.make_listing()])

        self.assertEqual(report.photo_capture_report.total_sessions, 1)
        self.assertEqual(report.photo_capture_report.total_photos, 1)
        self.assertEqual(report.photo_capture_report.missing_back_count, 1)
        self.assertIn("Phone Photo Capture", report.format_markdown())

    def test_field_test_snapshot_integration(self):
        companion = MobileCollectorCompanion()

        report = companion.run_field_test_snapshot()

        self.assertGreaterEqual(report.scenario_count, 1)
        self.assertIn("Field Test", report.format_markdown())


if __name__ == "__main__":
    unittest.main()
