"""Tests for the v2.4 Mobile Companion Prototype."""

import os
import tempfile
import unittest

from coin_collection import CoinItem
from collection_dashboard import CollectionDashboard
from legacy_portfolio_importer import LegacyWantListIntent
from mobile_companion import (
    ExportProvider,
    MobileAnalysisReport,
    MobileCandidateEntry,
    MobileCompanionWorkflow,
    PhoneWorkflowSimulation,
    PhotoProvider,
    StorageProvider,
)
from persistence_manager import AppState, PersistenceManager
from photo_vault import PhotoRecord


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


def make_intent(target_coin, budget=150.0):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id="mobile-want-1",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=budget,
        why_wanted="Mobile companion target",
        status="Active",
        priority_score=85,
    )


class TestMobileCompanion(unittest.TestCase):
    def setUp(self):
        self.items = [
            make_item("1", "Newfoundland", "50 cents", "1900", "F-12"),
            make_item("2", "Canada", "10 cents", "1911", "VF-20", notes="PCGS certified"),
            make_item("3", "Canada", "10 cents", "1911", "EF-40"),
            make_item("4", "Canada", "1 cent", "1859", "VG-8"),
            make_item("5", "United States", "1 cent", "1975", "VF-20"),
        ]
        self.want_list = [make_intent("Newfoundland 50 cents 1904")]
        self.photos = [
            PhotoRecord(
                file_path="coin_photos/candidates/active/nfld-1904.jpg",
                photo_type="Candidate Photo",
                linked_candidate_id="photo-1",
                linked_coin_name="Newfoundland 50 cents 1904",
            )
        ]
        self.workflow = MobileCompanionWorkflow(
            self.items,
            self.want_list,
            photo_records=self.photos,
        )

    def test_mobile_candidate_entry_minimal_valid_entry(self):
        entry = MobileCandidateEntry("Newfoundland 50 cents 1904 VF20", asking_price=120)

        self.assertEqual(entry.item_title, "Newfoundland 50 cents 1904 VF20")
        self.assertEqual(entry.total_cost, 120)
        self.assertEqual(entry.validate(), [])

    def test_mobile_candidate_entry_optional_fields_and_total_cost(self):
        entry = MobileCandidateEntry("Canada 10 cents 1911 EF40", asking_price="$10", shipping="2.50")
        listing = entry.to_listing_candidate()
        shopping = entry.to_shopping_candidate()

        self.assertEqual(entry.total_cost, 12.5)
        self.assertEqual(listing.total_cost, 12.5)
        self.assertEqual(shopping.total_cost, 12.5)
        self.assertEqual(entry.url, "")
        self.assertEqual(entry.photo_reference_id, "")

    def test_mobile_analysis_report_concise_fields(self):
        entry = MobileCandidateEntry("Newfoundland 50 cents 1904 VF20", asking_price=120)
        report = MobileAnalysisReport(
            candidate=entry,
            recommendation="STRONG BUY",
            impact_score=71,
            quality_delta=3,
            series_delta=12.5,
            want_list_status="ON_WANT_LIST",
            top_reason="Explicit WANT_LIST target",
            recommendation_summary="BUY: target is useful.",
            warning_flags=["Review coin surfaces"],
            max_rational_price=150,
        )

        self.assertEqual(report.recommendation, "BUY")
        self.assertEqual(report.want_list_status, "ON_WANT_LIST")
        self.assertIn("Explicit WANT_LIST target", report.format_markdown())
        self.assertEqual(report.to_dict()["quality_delta"], 3)

    def test_workflow_want_list_target(self):
        report = self.workflow.analyze(MobileCandidateEntry("Newfoundland 50 cents 1904 VF20", asking_price=120))

        self.assertIn(report.recommendation, {"BUY", "NEGOTIATE", "WATCH", "REVIEW"})
        self.assertEqual(report.want_list_status, "ON_WANT_LIST")
        self.assertGreater(report.impact_score, 0)
        self.assertTrue(report.top_reason)

    def test_workflow_duplicate_candidate_passes(self):
        report = self.workflow.analyze(MobileCandidateEntry("Canada 10 cents 1911 VF20", asking_price=10))

        self.assertEqual(report.recommendation, "PASS")
        self.assertGreaterEqual(report.impact_score, 0)
        self.assertTrue(any("duplicate" in warning.lower() or report.top_reason for warning in report.warning_flags + [report.top_reason]))

    def test_workflow_upgrade_candidate(self):
        report = self.workflow.analyze(MobileCandidateEntry("Canada 1 cent 1859 VF20", asking_price=60))

        self.assertIn(report.recommendation, {"BUY", "NEGOTIATE", "WATCH", "REVIEW"})
        self.assertGreaterEqual(report.impact_score, 0)
        self.assertTrue(report.recommendation_summary)

    def test_workflow_collection_gap(self):
        report = self.workflow.analyze(MobileCandidateEntry("Newfoundland 50 cents 1902 VF20", asking_price=90))

        self.assertIn(report.recommendation, {"BUY", "NEGOTIATE", "WATCH", "REVIEW"})
        self.assertGreater(report.impact_score, 0)

    def test_workflow_random_world_base_metal_non_priority(self):
        report = self.workflow.analyze(MobileCandidateEntry("Argentina 1 cent 1975 VF20", asking_price=1))

        self.assertEqual(report.recommendation, "PASS")
        self.assertEqual(report.impact_score, 0)

    def test_workflow_missing_price_is_graceful(self):
        report = self.workflow.analyze(MobileCandidateEntry("Newfoundland 50 cents 1904 VF20"))

        self.assertIn(report.recommendation, {"WATCH", "REVIEW"})
        self.assertTrue(any("Missing asking price" in warning for warning in report.warning_flags))

    def test_provider_abstractions(self):
        photo_provider = PhotoProvider(self.photos)

        self.assertIsNotNone(photo_provider.resolve_photo_reference("photo-1"))
        self.assertIn("not found", photo_provider.describe_photo_reference("missing-photo"))

    def test_export_provider_writes_csv_and_markdown(self):
        report = self.workflow.analyze(MobileCandidateEntry("Newfoundland 50 cents 1904 VF20", asking_price=120))
        exporter = ExportProvider()

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "mobile.csv")
            md_path = os.path.join(temp_dir, "mobile.md")

            self.assertTrue(exporter.export_analysis_csv(csv_path, report))
            self.assertTrue(exporter.export_analysis_markdown(md_path, report))

            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("recommendation", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("# Mobile Analysis Report", handle.read())

    def test_phone_workflow_simulation(self):
        simulation = PhoneWorkflowSimulation(self.workflow)
        report = simulation.simulate("Newfoundland 50 cents 1904 VF20", price=120, notes="Dealer table")

        self.assertIn(report.recommendation, {"BUY", "PASS", "NEGOTIATE", "WATCH", "REVIEW"})
        self.assertGreaterEqual(report.required_steps, 3)
        self.assertIn(report.workflow_complexity, {"LOW", "MEDIUM", "HIGH"})
        self.assertTrue(report.rationale)
        self.assertIn("Impact score", report.impact)

    def test_phone_workflow_export(self):
        simulation = PhoneWorkflowSimulation(self.workflow)
        report = simulation.simulate("Newfoundland 50 cents 1904 VF20", price=120)

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "phone.csv")
            md_path = os.path.join(temp_dir, "phone.md")

            self.assertTrue(simulation.export_csv(csv_path, report))
            self.assertTrue(simulation.export_markdown(md_path, report))

            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("workflow_complexity", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("# Phone Workflow Report", handle.read())

    def test_persistence_round_trip_for_mobile_activity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = PersistenceManager(state_dir=os.path.join(temp_dir, "state"))
            entry = MobileCandidateEntry("Newfoundland 50 cents 1904 VF20", asking_price=120)
            report = self.workflow.analyze(entry)
            storage = StorageProvider(manager)

            result = storage.save_mobile_activity([entry], [report])
            loaded = manager.load_state()

            self.assertTrue(result.success)
            self.assertEqual(len(loaded.state.recent_mobile_candidates), 1)
            self.assertEqual(len(loaded.state.recent_mobile_recommendations), 1)
            self.assertEqual(loaded.state.recent_mobile_candidates[0].item_title, entry.item_title)
            self.assertEqual(loaded.state.recent_mobile_recommendations[0].recommendation, report.recommendation)

    def test_persistence_create_state_accepts_mobile_activity(self):
        entry = MobileCandidateEntry("Newfoundland 50 cents 1904 VF20", asking_price=120)
        report = self.workflow.analyze(entry)
        state = AppState(recent_mobile_candidates=[entry], recent_mobile_recommendations=[report])
        payload = state.to_dict()
        restored = PersistenceManager.state_from_dict(payload)

        self.assertEqual(restored.recent_mobile_candidates[0].item_title, entry.item_title)
        self.assertEqual(restored.recent_mobile_recommendations[0].top_reason, report.top_reason)

    def test_dashboard_mobile_summary_when_reports_provided(self):
        report = self.workflow.analyze(MobileCandidateEntry("Newfoundland 50 cents 1904 VF20", asking_price=120))
        data = CollectionDashboard(self.items, self.want_list, mobile_analysis_reports=[report]).generate_dashboard()

        self.assertIsNotNone(data.mobile_companion_recommendation)
        self.assertIsNotNone(data.last_mobile_candidate)
        self.assertIsNotNone(data.top_mobile_opportunity)
        self.assertIn("Mobile", CollectionDashboard(self.items, self.want_list, mobile_analysis_reports=[report]).format_markdown())

    def test_dashboard_unchanged_without_mobile_reports(self):
        data = CollectionDashboard(self.items, self.want_list).generate_dashboard()

        self.assertIsNone(data.mobile_companion_recommendation)
        self.assertIsNone(data.last_mobile_candidate)
        self.assertIsNone(data.top_mobile_opportunity)


if __name__ == "__main__":
    unittest.main()
