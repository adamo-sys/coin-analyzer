"""Tests for v2.7 Collector Workflow Integration."""

import os
import tempfile
import unittest

from coin_collection import CoinItem
from collection_snapshot import CollectionSnapshotManager
from collector_workflows import (
    AcquisitionWorkflow,
    CollectorDailySummary,
    CollectorWorkflowEngine,
    CollectionReviewReport,
    PhotoReviewWorkflow,
    RecommendedTool,
    UnifiedWorkflowReport,
    WorkflowAction,
    WorkflowEvidence,
    WorkflowRequest,
    WorkflowState,
    WorkflowStatus,
    WorkflowSummary,
    WorkflowType,
)
from legacy_portfolio_importer import LegacyWantListIntent
from ocr_experiment import OCRExperiment
from persistence_manager import AppState, PersistenceManager
from photo_assisted_entry import PhotoCandidate
from photo_vault import PhotoRecord
from smart_shopping_assistant import ShoppingCandidate


def make_item(item_id, country, denomination, year, grade):
    return CoinItem(
        id=item_id,
        image_path="",
        country=country,
        denomination=denomination,
        year=year,
        grade=grade,
        notes="",
        date_added="2026-06-19",
    )


def make_intent(target_coin):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id="workflow-want-1",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=150.0,
        why_wanted="Workflow target",
        status="Active",
        priority_score=85,
    )


class TestCollectorWorkflows(unittest.TestCase):
    def setUp(self):
        self.items = [
            make_item("1", "Newfoundland", "50 cents", "1900", "F-12"),
            make_item("2", "Canada", "10 cents", "1911", "VF-20"),
            make_item("3", "Canada", "10 cents", "1911", "EF-40"),
        ]
        self.want_list = [make_intent("Newfoundland 50 cents 1904")]

    def test_workflow_status_tracking(self):
        status = WorkflowStatus("OCR Pending", "Needs validation", "warning", "Review OCR")
        restored = WorkflowStatus.from_dict(status.to_dict())

        self.assertEqual(restored.status, "OCR Pending")
        self.assertEqual(restored.severity, "WARNING")
        self.assertEqual(restored.action, "Review OCR")

    def test_acquisition_workflow(self):
        candidate = PhotoCandidate(
            title="Newfoundland 50 cents 1904 VF20",
            front_photo="front.jpg",
            asking_price=120,
        )

        report = AcquisitionWorkflow(self.items, self.want_list).run(
            candidate,
            raw_ocr_text="Newfoundland 1904 50 cents PCGS 1234567",
        )

        self.assertEqual(report.summary.workflow_name, "Acquisition Workflow")
        self.assertIsNotNone(report.photo_review_report)
        self.assertIsNotNone(report.ocr_report)
        self.assertIsNotNone(report.validation_report)
        self.assertIsNotNone(report.shopping_report)
        self.assertTrue(report.summary.statuses)
        self.assertIn("OCR Validation Complete", [status.status for status in report.summary.statuses])
        self.assertIn("Manual", report.format_markdown())

    def test_collection_review_workflow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_manager = CollectionSnapshotManager(os.path.join(temp_dir, "snapshots.json"))
            report = CollectorWorkflowEngine(
                self.items,
                self.want_list,
                snapshot_manager=snapshot_manager,
            ).collection_review_workflow()

            self.assertIsInstance(report, CollectionReviewReport)
            self.assertEqual(report.summary.workflow_name, "Collection Review Workflow")
            self.assertIsNotNone(report.dashboard_data)
            self.assertIsNotNone(report.quality_report)
            self.assertIsNotNone(report.integrity_report)
            self.assertIsNotNone(report.snapshot_report)
            self.assertIn("Collection Dashboard", report.format_markdown())

    def test_photo_workflow(self):
        report = PhotoReviewWorkflow(
            photo_records=[
                PhotoRecord(
                    file_path="missing-front.jpg",
                    photo_type="Collection Photo",
                    linked_collection_item_id="1",
                    linked_coin_name="Newfoundland 50 cents 1900",
                )
            ],
            collection_items=self.items,
        ).run()

        self.assertEqual(report.summary.workflow_name, "Photo Review Workflow")
        self.assertIsNotNone(report.photo_coverage_report)
        self.assertTrue(any(status.status == "Photo Missing" for status in report.summary.statuses))

    def test_daily_collector_summary(self):
        ocr_report = OCRExperiment().run("front.jpg", raw_text="blurred")
        summary = CollectorWorkflowEngine(
            self.items,
            self.want_list,
            ocr_reports=[ocr_report],
            shopping_candidates=[ShoppingCandidate("Newfoundland 50 cents 1904", asking_price=120)],
        ).daily_summary()

        self.assertIsInstance(summary, CollectorDailySummary)
        self.assertIn("Review OCR items", summary.recommended_tasks)
        self.assertIn("Create snapshot", summary.recommended_tasks)
        self.assertTrue(summary.summary.statuses)

    def test_persistence_for_workflow_state(self):
        summary = WorkflowSummary(
            "Daily Collector Summary",
            "Ready",
            "Workflow generated",
            next_actions=["Review OCR items"],
            statuses=[WorkflowStatus("OCR Pending", "One item")],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PersistenceManager(state_dir=os.path.join(temp_dir, "state"))
            saved = manager.save_state(AppState(
                workflow_statuses=[status.to_dict() for status in summary.statuses],
                workflow_summaries=[summary.to_dict()],
            ))
            loaded = manager.load_state()

            self.assertTrue(saved.success)
            self.assertEqual(len(loaded.state.workflow_summaries), 1)
            self.assertEqual(loaded.state.workflow_summaries[0]["workflow_name"], "Daily Collector Summary")
            self.assertEqual(loaded.state.workflow_statuses[0]["status"], "OCR Pending")

    def test_export_generation(self):
        report = CollectorWorkflowEngine(self.items, self.want_list).daily_summary()

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "daily.csv")
            md_path = os.path.join(temp_dir, "daily.md")

            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("workflow_status", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("Daily Collector Summary", handle.read())

    def test_unified_workflow_dtos(self):
        evidence = WorkflowEvidence("Unit Test", "Evidence detail")
        action = WorkflowAction("Review item", evidence=[evidence], recommended_tool=RecommendedTool.WORKFLOW)
        request = WorkflowRequest(WorkflowType.COLLECTION_REVIEW)
        report = UnifiedWorkflowReport(
            WorkflowType.COLLECTION_REVIEW,
            WorkflowState.READY,
            "Collection Review",
            "Ready",
            evidence=[evidence],
            next_actions=[action],
            state_reason="Collection Review is ready for review.",
            recommended_tool=RecommendedTool.COLLECTION_DASHBOARD,
        )

        self.assertEqual(request.workflow_type, WorkflowType.COLLECTION_REVIEW)
        payload = report.to_dict()
        self.assertEqual(payload["workflow_type"], "COLLECTION_REVIEW")
        self.assertEqual(payload["state_reason"], "Collection Review is ready for review.")
        self.assertEqual(payload["recommended_tool"], "COLLECTION_DASHBOARD")
        self.assertEqual(payload["recommended_tool_label"], "Collection Dashboard")
        self.assertEqual(payload["next_actions"][0]["recommended_tool"], "WORKFLOW")
        self.assertEqual(payload["next_actions"][0]["recommended_tool_label"], "Workflow Review")
        self.assertTrue(report.next_actions[0].evidence)

    def test_unified_workflow_dtos_default_explainability_metadata(self):
        report = UnifiedWorkflowReport(
            WorkflowType.DAILY_INBOX,
            WorkflowState.READY,
            "Daily Inbox",
            "Ready",
            evidence=[WorkflowEvidence("Unit Test", "Ready")],
            next_actions=[WorkflowAction("Review inbox")],
        )

        self.assertIn("Daily Inbox", report.state_reason)
        self.assertEqual(report.recommended_tool, RecommendedTool.WORKFLOW)
        self.assertEqual(report.recommended_tool_label, "Workflow Review")

    def test_run_workflow_acquisition_review(self):
        candidate = PhotoCandidate(
            title="Newfoundland 50 cents 1904 VF20",
            front_photo="front.jpg",
            asking_price=120,
        )

        report = CollectorWorkflowEngine(self.items, self.want_list).run_workflow(
            WorkflowRequest(
                WorkflowType.ACQUISITION_REVIEW,
                candidate=candidate,
                raw_ocr_text="Newfoundland 1904 50 cents",
            )
        )

        self.assertEqual(report.workflow_type, WorkflowType.ACQUISITION_REVIEW)
        self.assertIn(report.state, {WorkflowState.READY, WorkflowState.REVIEW_REQUIRED})
        self.assertIn("acquisition", report.source_reports)
        self.assertTrue(report.evidence)
        self.assertTrue(all(action.evidence for action in report.next_actions))

    def test_run_workflow_acquisition_missing_candidate(self):
        report = CollectorWorkflowEngine(self.items, self.want_list).run_workflow(
            WorkflowRequest(WorkflowType.ACQUISITION_REVIEW)
        )

        self.assertEqual(report.state, WorkflowState.NEEDS_INPUT)
        self.assertIn("candidate", report.state_reason.lower())
        self.assertEqual(report.recommended_tool, RecommendedTool.SMART_SHOPPING)
        self.assertTrue(report.warnings)
        self.assertTrue(all(action.evidence for action in report.next_actions))

    def test_run_workflow_collection_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report = CollectorWorkflowEngine(
                self.items,
                self.want_list,
                snapshot_manager=CollectionSnapshotManager(os.path.join(temp_dir, "snapshots.json")),
            ).run_workflow(WorkflowRequest(WorkflowType.COLLECTION_REVIEW))

        self.assertEqual(report.workflow_type, WorkflowType.COLLECTION_REVIEW)
        self.assertIn("collection_review", report.source_reports)
        self.assertTrue(any("Quality Reviewed" in evidence.detail for evidence in report.evidence))
        self.assertTrue(all(action.evidence for action in report.next_actions))

    def test_run_workflow_upgrade_review(self):
        candidate = make_item("candidate", "Canada", "10 cents", "1911", "AU-50")
        report = CollectorWorkflowEngine(self.items, self.want_list).run_workflow(
            WorkflowRequest(WorkflowType.UPGRADE_REVIEW, candidate=candidate)
        )

        self.assertEqual(report.workflow_type, WorkflowType.UPGRADE_REVIEW)
        self.assertIn("upgrade_recommendation", report.source_reports)
        self.assertTrue(any(evidence.source == "UpgradeAdvisor" for evidence in report.evidence))
        self.assertTrue(all(action.evidence for action in report.next_actions))

    def test_run_workflow_upgrade_missing_candidate(self):
        report = CollectorWorkflowEngine(self.items, self.want_list).run_workflow(
            WorkflowRequest(WorkflowType.UPGRADE_REVIEW)
        )

        self.assertEqual(report.state, WorkflowState.NEEDS_INPUT)
        self.assertIn("candidate", report.state_reason.lower())
        self.assertEqual(report.recommended_tool, RecommendedTool.UPGRADE_ADVISOR)
        self.assertTrue(report.evidence)

    def test_run_workflow_duplicate_review(self):
        report = CollectorWorkflowEngine(self.items, self.want_list).run_workflow(
            WorkflowRequest(WorkflowType.DUPLICATE_REVIEW)
        )

        self.assertEqual(report.workflow_type, WorkflowType.DUPLICATE_REVIEW)
        self.assertEqual(report.state, WorkflowState.REVIEW_REQUIRED)
        self.assertIn("duplicate", report.state_reason.lower())
        self.assertEqual(report.recommended_tool, RecommendedTool.DUPLICATE_REVIEW)
        self.assertTrue(any(action.recommended_tool in {RecommendedTool.DUPLICATE_REVIEW, RecommendedTool.UPGRADE_ADVISOR} for action in report.next_actions))
        self.assertIn("duplicates", report.source_reports)
        self.assertTrue(any("duplicate group" in evidence.detail for evidence in report.evidence))
        self.assertTrue(all(action.evidence for action in report.next_actions))

    def test_run_workflow_duplicate_review_complete_has_explanation(self):
        report = CollectorWorkflowEngine([], self.want_list).run_workflow(
            WorkflowRequest(WorkflowType.DUPLICATE_REVIEW)
        )

        self.assertEqual(report.state, WorkflowState.COMPLETE)
        self.assertIn("No duplicate", report.state_reason)
        self.assertEqual(report.recommended_tool, RecommendedTool.DUPLICATE_REVIEW)

    def test_run_workflow_daily_inbox(self):
        ocr_report = OCRExperiment().run("front.jpg", raw_text="blurred")
        report = CollectorWorkflowEngine(
            self.items,
            self.want_list,
            ocr_reports=[ocr_report],
            shopping_candidates=[ShoppingCandidate("Newfoundland 50 cents 1904", asking_price=120)],
        ).run_workflow(WorkflowRequest(WorkflowType.DAILY_INBOX))

        self.assertEqual(report.workflow_type, WorkflowType.DAILY_INBOX)
        self.assertTrue(report.state_reason)
        self.assertEqual(report.recommended_tool, RecommendedTool.WORKFLOW)
        self.assertTrue(any(action.recommended_tool in {RecommendedTool.OCR_EXPERIMENT, RecommendedTool.SMART_SHOPPING, RecommendedTool.PHOTO_VAULT, RecommendedTool.WORKFLOW} for action in report.next_actions))
        self.assertIn("daily_summary", report.source_reports)
        self.assertTrue(report.next_actions)
        self.assertTrue(all(action.evidence for action in report.next_actions))

    def test_run_workflow_rejects_non_request(self):
        with self.assertRaises(ValueError):
            CollectorWorkflowEngine(self.items, self.want_list).run_workflow("COLLECTION_REVIEW")

    def test_run_workflow_source_failure_degrades(self):
        engine = CollectorWorkflowEngine(self.items, self.want_list)

        def fail_collection_review():
            raise RuntimeError("source unavailable")

        engine.collection_review_workflow = fail_collection_review
        report = engine.run_workflow(WorkflowRequest(WorkflowType.COLLECTION_REVIEW))

        self.assertEqual(report.state, WorkflowState.BLOCKED)
        self.assertIn("failed", report.state_reason)
        self.assertEqual(report.recommended_tool, RecommendedTool.COLLECTION_DASHBOARD)
        self.assertIn("source unavailable", report.warnings)
        self.assertTrue(all(action.evidence for action in report.next_actions))

    def test_run_workflow_deterministic_and_read_only(self):
        before = [item.to_dict() for item in self.items]
        engine = CollectorWorkflowEngine(self.items, self.want_list)
        first = engine.run_workflow(WorkflowRequest(WorkflowType.DUPLICATE_REVIEW))
        second = engine.run_workflow(WorkflowRequest(WorkflowType.DUPLICATE_REVIEW))
        after = [item.to_dict() for item in self.items]

        self.assertEqual(before, after)
        self.assertEqual([evidence.to_dict() for evidence in first.evidence], [evidence.to_dict() for evidence in second.evidence])
        self.assertEqual([action.to_dict() for action in first.next_actions], [action.to_dict() for action in second.next_actions])
        self.assertEqual(first.to_dict(), second.to_dict())


if __name__ == "__main__":
    unittest.main()
