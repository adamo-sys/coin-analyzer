import os
import tempfile
import unittest

from ocr_experiment import OCRExperiment
from ocr_validation import OCRValidationEngine
from photo_capture_workflow import (
    REVIEW_REVIEWED,
    ROLE_COIN_BACK,
    ROLE_COIN_FRONT,
    ROLE_LISTING,
    ROLE_NOTE_BACK,
    ROLE_NOTE_FRONT,
    SESSION_COIN_FRONT_BACK,
    SESSION_NOTE_FRONT_BACK,
    SOURCE_LISTING_PHOTO,
    STATUS_COMPLETE,
    STATUS_NEEDS_BACK,
    STATUS_READY_FOR_OCR,
    PhotoCaptureReport,
    PhotoCaptureWorkflow,
)
from photo_vault import PhotoRecord


class TestPhotoCaptureWorkflow(unittest.TestCase):
    def test_photo_capture_session_creation(self):
        workflow = PhotoCaptureWorkflow()

        session = workflow.start_session(SESSION_COIN_FRONT_BACK, subject="Newfoundland 50 cents", location="Bourse")

        self.assertEqual(session.session_type, SESSION_COIN_FRONT_BACK)
        self.assertIn("photo-capture-coin-front-back", session.session_id)
        self.assertTrue(session.missing_front)
        self.assertTrue(session.missing_back)

    def test_front_back_pairing_and_missing_back(self):
        workflow = PhotoCaptureWorkflow()
        session = workflow.capture_coin_pair("Canada 1926 nickel", front_path="front.jpg")

        self.assertFalse(session.missing_front)
        self.assertTrue(session.missing_back)
        self.assertEqual(session.photos[0].workflow_status, STATUS_NEEDS_BACK)
        session.add_photo("back.jpg", ROLE_COIN_BACK)

        self.assertTrue(session.front_back_complete)
        self.assertFalse(session.missing_back)
        self.assertTrue(session.ready_for_review)

    def test_note_front_back_workflow(self):
        workflow = PhotoCaptureWorkflow()
        session = workflow.capture_note_pair("Bank of Canada note", front_path="note-front.jpg", back_path="note-back.jpg")

        self.assertEqual(session.session_type, SESSION_NOTE_FRONT_BACK)
        self.assertEqual(session.front_photos[0].photo_role, ROLE_NOTE_FRONT)
        self.assertEqual(session.back_photos[0].photo_role, ROLE_NOTE_BACK)
        self.assertTrue(session.ready_for_review)

    def test_workflow_state_transitions(self):
        workflow = PhotoCaptureWorkflow()
        session = workflow.capture_coin_pair("Newfoundland 1904H 50 cents", "front.jpg", "back.jpg")

        session.mark_ready_for_ocr()
        self.assertTrue(all(photo.workflow_status == STATUS_READY_FOR_OCR for photo in session.photos))
        self.assertTrue(session.ready_for_ocr)

        session.mark_reviewed()
        self.assertTrue(all(photo.workflow_status == STATUS_COMPLETE for photo in session.photos))
        self.assertTrue(all(photo.review_status == REVIEW_REVIEWED for photo in session.photos))
        self.assertFalse(session.ready_for_review)

    def test_listing_photo_workflow_and_photo_vault_records(self):
        workflow = PhotoCaptureWorkflow()
        session = workflow.capture_listing_photo("Auction lot", "listing.jpg", candidate_id="lot-1")

        self.assertEqual(session.photos[0].source_type, SOURCE_LISTING_PHOTO)
        self.assertEqual(session.photos[0].photo_role, ROLE_LISTING)
        self.assertTrue(session.ready_for_review)
        records = workflow.photo_vault_records()
        self.assertIsInstance(records[0], PhotoRecord)
        self.assertEqual(records[0].photo_type, "Candidate Photo")
        self.assertEqual(records[0].linked_candidate_id, "lot-1")

    def test_ocr_readiness_sources(self):
        workflow = PhotoCaptureWorkflow()
        session = workflow.capture_coin_pair("Canada 1859 cent", "front.jpg", "back.jpg")
        session.mark_ready_for_ocr()

        sources = workflow.ocr_sources()

        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0]["ready_for_ocr"], "YES")

    def test_export_generation(self):
        workflow = PhotoCaptureWorkflow()
        workflow.capture_coin_pair("Canada 1911 10 cents", "front.jpg", "back.jpg")
        report = workflow.report()

        self.assertIsInstance(report, PhotoCaptureReport)
        self.assertIn("Phone Photo Capture Report", report.format_markdown())

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "capture.csv")
            md_path = os.path.join(temp_dir, "capture.md")
            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            with open(csv_path, encoding="utf-8") as handle:
                self.assertIn("session_id", handle.readline())
            with open(md_path, encoding="utf-8") as handle:
                self.assertIn("Photos collected: 2", handle.read())

    def test_ocr_and_validation_adapters_accept_captured_photo(self):
        workflow = PhotoCaptureWorkflow()
        session = workflow.capture_coin_pair("Canada 1945 5 cents", "front.jpg", "back.jpg")
        captured = session.front_photos[0]

        ocr_report = OCRExperiment().from_captured_photo(captured, raw_text="Canada 1945 5 cents")
        validation = OCRValidationEngine().validate_captured_photo(captured, raw_text="Canada 1945 5 cents")

        self.assertIn("1945", ocr_report.possible_years)
        self.assertIn(validation.trust_level.value, {"HIGH", "MEDIUM", "LOW"})


if __name__ == "__main__":
    unittest.main()
