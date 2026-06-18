"""Tests for the v2.3 Mobile Readiness audit layer."""

import os
import tempfile
import unittest

from mobile_readiness import (
    ApiEndpointMapping,
    MobileReadinessAuditor,
    MobileReadinessReport,
    MobileReadinessScore,
    ServiceBoundaryFinding,
)


class TestMobileReadiness(unittest.TestCase):
    def setUp(self):
        self.auditor = MobileReadinessAuditor()

    def test_report_generates_structured_data(self):
        report = self.auditor.generate_report()

        self.assertIsInstance(report, MobileReadinessReport)
        self.assertTrue(report.desktop_dependencies)
        self.assertTrue(report.service_boundaries)
        self.assertTrue(report.mobile_inputs)
        self.assertTrue(report.api_mappings)
        self.assertTrue(report.phone_workflow)
        self.assertIsInstance(report.score, MobileReadinessScore)

    def test_mobile_readiness_score_is_deterministic(self):
        score = self.auditor.mobile_readiness_score()

        self.assertEqual(score.overall_score, 68)
        self.assertEqual(score.architecture, 72)
        self.assertEqual(score.workflow, 62)
        self.assertEqual(score.persistence, 76)
        self.assertEqual(score.exports, 68)
        self.assertEqual(score.inputs, 64)
        self.assertIn("Tkinter", " ".join(score.blockers))

    def test_desktop_dependency_audit_identifies_mobile_blockers(self):
        findings = {finding.area: finding for finding in self.auditor.desktop_dependency_audit()}

        self.assertEqual(findings["Tkinter GUI"].status, "BLOCKER")
        self.assertEqual(findings["File dialogs"].status, "BLOCKER")
        self.assertIn("storage", findings["Persistence workflows"].abstraction_point.lower())
        self.assertIn("URI", findings["Photo workflows"].recommendation)

    def test_service_boundary_review_covers_core_services(self):
        findings = {finding.service: finding for finding in self.auditor.service_boundary_review()}

        self.assertIsInstance(findings["Collection Intelligence"], ServiceBoundaryFinding)
        self.assertEqual(findings["Collection Intelligence"].boundary_status, "READY")
        self.assertIn("analyze_candidate", findings["Collection Intelligence"].mobile_notes)
        self.assertEqual(findings["Backup Manager"].boundary_status, "PARTIAL")
        self.assertIn("filesystem", findings["Backup Manager"].recommendation.lower())

    def test_mobile_input_readiness_covers_phone_workflows(self):
        findings = {finding.workflow: finding for finding in self.auditor.mobile_input_readiness()}

        self.assertTrue(findings["Manual candidate entry"].supported)
        self.assertTrue(findings["Pasted listing text"].supported)
        self.assertTrue(findings["Pasted URLs"].supported)
        self.assertTrue(findings["Photo references"].supported)
        self.assertTrue(findings["Persisted context"].supported)
        self.assertIn("dealer-table", findings["Manual candidate entry"].recommendation)

    def test_api_readiness_mapping_is_documentation_only(self):
        mappings = {mapping.endpoint: mapping for mapping in self.auditor.api_readiness_mapping()}

        self.assertIsInstance(mappings["analyze_candidate"], ApiEndpointMapping)
        self.assertIn("CollectionIntelligenceEngine", mappings["analyze_candidate"].existing_source)
        self.assertIn("CollectionHealthReportEngine", mappings["collection_health"].existing_source)
        self.assertIn("SmartShoppingAssistant", mappings["shopping_recommendations"].existing_source)
        self.assertIn("CollectionDashboard", mappings["dashboard_summary"].existing_source)
        self.assertIn("no API implemented", mappings["analyze_candidate"].notes)

    def test_phone_workflow_audit_reaches_buy_pass_decision(self):
        steps = self.auditor.phone_workflow_audit()
        combined = " ".join(step.action + " " + step.improvement for step in steps)

        self.assertEqual([step.step_number for step in steps], list(range(1, len(steps) + 1)))
        self.assertIn("BUY", combined)
        self.assertIn("PASS", combined)
        self.assertGreaterEqual(len(steps), 5)

    def test_report_serializes_to_dict(self):
        payload = self.auditor.generate_report().to_dict()

        self.assertIn("desktop_dependencies", payload)
        self.assertIn("service_boundaries", payload)
        self.assertIn("api_mappings", payload)
        self.assertEqual(payload["score"]["overall_score"], 68)

    def test_markdown_and_csv_exports(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "mobile-readiness.csv")
            md_path = os.path.join(temp_dir, "mobile-readiness.md")

            self.assertTrue(self.auditor.export_csv(csv_path))
            self.assertTrue(self.auditor.export_markdown(md_path))

            with open(csv_path, "r", encoding="utf-8") as handle:
                csv_text = handle.read()
            with open(md_path, "r", encoding="utf-8") as handle:
                markdown_text = handle.read()

        self.assertIn("Desktop Dependency", csv_text)
        self.assertIn("analyze_candidate", csv_text)
        self.assertIn("# Mobile Readiness Report", markdown_text)
        self.assertIn("## API Readiness Mapping", markdown_text)


if __name__ == "__main__":
    unittest.main()
