"""Tests for v8.6 Workflow GUI integration helpers."""

import inspect
import unittest

from coin_collection_gui import CoinCollectionGUI
from collector_workflows import (
    RecommendedTool,
    UnifiedWorkflowReport,
    WorkflowAction,
    WorkflowEvidence,
    WorkflowSeverity,
    WorkflowState,
    WorkflowType,
)


class TestWorkflowGUIIntegration(unittest.TestCase):
    def make_gui(self):
        return CoinCollectionGUI.__new__(CoinCollectionGUI)

    def make_report(self):
        evidence = WorkflowEvidence(
            "WorkflowStatus",
            "OCR Pending: 1 OCR report needs review",
            WorkflowSeverity.WARNING,
            "Review OCR validation reports",
        )
        return UnifiedWorkflowReport(
            WorkflowType.DAILY_INBOX,
            WorkflowState.REVIEW_REQUIRED,
            "Daily Inbox",
            "Daily collector priorities generated",
            evidence=[evidence],
            next_actions=[
                WorkflowAction(
                    "Review OCR items",
                    "Daily collector priorities generated",
                    "Daily Collector Summary",
                    WorkflowState.REVIEW_REQUIRED,
                    [evidence],
                    recommended_tool=RecommendedTool.OCR_EXPERIMENT,
                )
            ],
            warnings=["OCR Pending: 1 OCR report needs review"],
            state_reason="Daily Inbox found workflow items that require collector review.",
            recommended_tool=RecommendedTool.WORKFLOW,
        )

    def test_format_unified_workflow_displays_explainability_metadata(self):
        gui = self.make_gui()
        content = gui._format_unified_workflow(self.make_report())

        self.assertIn("Workflow Type:      DAILY_INBOX", content)
        self.assertIn("State:              REVIEW_REQUIRED", content)
        self.assertIn("State Reason:       Daily Inbox found workflow items", content)
        self.assertIn("Recommended Tool:   WORKFLOW", content)
        self.assertIn("Tool Label:         Workflow Review", content)
        self.assertIn("Review OCR items", content)
        self.assertIn("Open: OCR Experiment", content)
        self.assertIn("[WARNING] WorkflowStatus", content)
        self.assertIn("Warnings", content)

    def test_format_unified_workflow_handles_empty_actions_and_evidence(self):
        gui = self.make_gui()
        report = UnifiedWorkflowReport(
            WorkflowType.DUPLICATE_REVIEW,
            WorkflowState.COMPLETE,
            "Duplicate Review",
            "No duplicates",
            evidence=[],
            next_actions=[],
            state_reason="No duplicate groups were detected.",
            recommended_tool=RecommendedTool.DUPLICATE_REVIEW,
        )

        content = gui._format_unified_workflow(report)

        self.assertIn("No workflow actions available.", content)
        self.assertIn("No workflow evidence available.", content)
        self.assertIn("DUPLICATE_REVIEW", content)

    def test_workflow_tool_mapping_uses_existing_methods_only(self):
        gui = self.make_gui()
        opened = []

        def open_smart_shopping_assistant():
            opened.append("shopping")

        gui.open_smart_shopping_assistant = open_smart_shopping_assistant

        label, command = gui._workflow_tool_button_spec(RecommendedTool.SMART_SHOPPING)
        command()

        self.assertEqual(label, "Open Smart Shopping")
        self.assertEqual(opened, ["shopping"])
        self.assertEqual(gui._workflow_tool_button_spec(RecommendedTool.UPGRADE_ADVISOR)[0], "Open Upgrade Advisor")
        self.assertIsNone(gui._workflow_tool_button_spec(RecommendedTool.NONE))
        self.assertIsNone(gui._workflow_tool_button_spec("UNKNOWN_TOOL"))

    def test_workflow_tool_specs_deduplicate_report_and_action_tools(self):
        gui = self.make_gui()
        gui.open_ocr_experiment = lambda: None
        refresh = lambda: None
        report = self.make_report()
        report.next_actions.append(
            WorkflowAction(
                "Review OCR again",
                recommended_tool=RecommendedTool.OCR_EXPERIMENT,
            )
        )

        specs = gui._workflow_tool_button_specs(report, refresh)

        labels = [label for label, _command in specs]
        self.assertEqual(labels, ["Refresh Workflow", "Open OCR Experiment"])

    def test_workspace_workflow_gui_methods_do_not_call_workflow_engine(self):
        source = "\n".join(
            [
                inspect.getsource(CoinCollectionGUI._create_workflow_tab),
                inspect.getsource(CoinCollectionGUI._refresh_workflow_tab),
                inspect.getsource(CoinCollectionGUI._refresh_workspace_tabs),
            ]
        )

        self.assertIn("get_workflows", source)
        self.assertNotIn("CollectorWorkflowEngine", source)
        self.assertNotIn("_workflow_engine()", source)


if __name__ == "__main__":
    unittest.main()
