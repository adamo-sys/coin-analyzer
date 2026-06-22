import csv
import os
import tempfile
import unittest

from coin_collection import CoinItem
from collector_workflow_integration import (
    APPROVE,
    REJECT,
    REVIEW,
    STAGE_ENTRY_REVIEW,
    STAGE_FINAL_REVIEW,
    STAGE_OCR_REVIEW,
    CollectorWorkflowIntegrationEngine,
    WorkflowCompletionReport,
    WorkflowHealthReport,
    WorkflowSession,
)
from mobile_collector_companion import MobileCollectorCompanion
from photo_capture_workflow import PhotoCaptureWorkflow


class TestCollectorWorkflowIntegration(unittest.TestCase):
    def make_item(self):
        return CoinItem("1", "", "Canada", "5 cents", "1945", "VF-20", "", "2026-06-22")

    def make_engine(self):
        return CollectorWorkflowIntegrationEngine(collection_items=[self.make_item()])

    def test_workflow_creation_runs_end_to_end_stages(self):
        report = self.make_engine().run_workflow(subject="Canada 1945 5 cents", raw_text="Canada 1945 5 cents George VI")

        self.assertIsInstance(report, WorkflowCompletionReport)
        self.assertEqual(report.stage_count, 7)
        self.assertEqual(report.session.ocr_report.candidate_count, 1)
        self.assertEqual(report.session.entry_report.candidate_count, 1)
        self.assertIn("Collection mutation performed: NO", report.format_markdown())

    def test_workflow_progression_with_photo_capture(self):
        workflow = PhotoCaptureWorkflow()
        engine = CollectorWorkflowIntegrationEngine(photo_capture_workflow=workflow)

        report = engine.run_workflow(
            subject="Canada 1945 5 cents",
            raw_text="Canada 1945 5 cents George VI",
            front_path="front.jpg",
            back_path="back.jpg",
        )

        self.assertEqual(len(report.session.photo_sessions), 1)
        self.assertEqual(report.session.photo_sessions[0].subject, "Canada 1945 5 cents")
        self.assertTrue(report.session.stage(STAGE_OCR_REVIEW))

    def test_workflow_resume_round_trip(self):
        engine = self.make_engine()
        report = engine.run_workflow(raw_text="Canada 1945 5 cents George VI")

        resumed = engine.resume_session(report.session.to_dict())

        self.assertIsInstance(resumed, WorkflowSession)
        self.assertEqual(resumed.session_id, report.session.session_id)
        self.assertEqual(len(resumed.stages), len(report.session.stages))

    def test_review_checkpoints_allow_approve_reject_review(self):
        engine = self.make_engine()
        session = engine.run_workflow(raw_text="Canada 1945 5 cents George VI").session

        approved = engine.review_stage(session, STAGE_OCR_REVIEW, APPROVE, "OCR looks correct")
        rejected = engine.review_stage(session, STAGE_ENTRY_REVIEW, REJECT, "Duplicate risk")
        review = engine.review_stage(session, STAGE_FINAL_REVIEW, REVIEW, "Needs manual save")

        self.assertEqual(approved.decision, APPROVE)
        self.assertEqual(rejected.decision, REJECT)
        self.assertEqual(review.decision, REVIEW)
        self.assertEqual(session.status, "REJECTED")

    def test_portfolio_preview_integration_is_preview_only(self):
        report = self.make_engine().run_workflow(raw_text="Canada 1945 5 cents George VI")

        preview = "; ".join(report.session.portfolio_previews)

        self.assertIn("Preview only", preview)
        self.assertIn("Collection value impact", preview)

    def test_health_report_tracks_completion_escalations_and_confidence(self):
        engine = self.make_engine()
        session_a = engine.run_workflow(raw_text="Canada 1945 5 cents George VI").session
        session_b = engine.run_workflow(raw_text="uncertain token").session

        health = engine.health_report([session_a, session_b])

        self.assertIsInstance(health, WorkflowHealthReport)
        self.assertEqual(health.total_workflows, 2)
        self.assertGreaterEqual(health.review_escalations, 1)
        self.assertIn(STAGE_OCR_REVIEW, health.stage_completion_rates())
        self.assertIn("Collector Workflow Health Report", health.format_markdown())

    def test_exports_completion_and_health_reports(self):
        engine = self.make_engine()
        report = engine.run_workflow(raw_text="Canada 1945 5 cents George VI")
        health = engine.health_report([report.session])

        with tempfile.TemporaryDirectory() as temp_dir:
            report_md = os.path.join(temp_dir, "workflow.md")
            report_csv = os.path.join(temp_dir, "workflow.csv")
            health_md = os.path.join(temp_dir, "health.md")
            health_csv = os.path.join(temp_dir, "health.csv")
            self.assertTrue(report.export_markdown(report_md))
            self.assertTrue(report.export_csv(report_csv))
            self.assertTrue(health.export_markdown(health_md))
            self.assertTrue(health.export_csv(health_csv))
            with open(report_csv, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["session_id"], report.session.session_id)
            with open(health_md, encoding="utf-8") as handle:
                self.assertIn("Collector Workflow Health Report", handle.read())

    def test_mobile_companion_includes_workflow_summary(self):
        workflow_report = self.make_engine().run_workflow(raw_text="Canada 1945 5 cents George VI")

        companion_report = MobileCollectorCompanion().generate_report(workflow_completion_report=workflow_report)

        markdown = companion_report.format_markdown()
        self.assertIn("Collector Workflow Integration", markdown)
        self.assertIn("Workflow stages", markdown)


if __name__ == "__main__":
    unittest.main()
