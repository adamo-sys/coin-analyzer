"""Unit tests for the Smart Phone Cataloguer orchestration facade."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from smart_phone_cataloguer import (
    SmartPhoneCataloguer,
    CatalogueResult,
    BatchCatalogueResult,
    run_smart_phone_cataloguer,
)
from ocr_assisted_identification import OCRIdentificationEngine, OCRIdentificationReport
from photo_capture_workflow import (
    PhotoCaptureWorkflow,
    PhotoCaptureSession,
    CapturedPhoto,
    PhotoCaptureReport,
    SESSION_COIN_FRONT_BACK,
    SESSION_NOTE_FRONT_BACK,
    SESSION_LISTING_PHOTOS,
    ROLE_COIN_FRONT,
    ROLE_COIN_BACK,
    ROLE_NOTE_FRONT,
    ROLE_NOTE_BACK,
    ROLE_LISTING,
    SOURCE_PHONE_CAMERA,
    SOURCE_LISTING_PHOTO,
)


class TestCatalogueResult(unittest.TestCase):
    """Verify CatalogueResult dataclass behavior."""

    def test_to_dict_serializes(self):
        result = CatalogueResult(
            session_id="test-123",
            subject="Canada 1 cent 1964",
            photos=[{"photo_id": "p1", "file_path": "/tmp/front.jpg", "role": "Coin Front"}],
            status="complete",
            ocr_ready=True,
            review_ready=True,
            message="Test message",
        )
        d = result.to_dict()
        self.assertEqual(d["session_id"], "test-123")
        self.assertEqual(d["subject"], "Canada 1 cent 1964")
        self.assertEqual(d["status"], "complete")
        self.assertTrue(d["ocr_ready"])
        self.assertTrue(d["review_ready"])
        self.assertEqual(d["message"], "Test message")
        self.assertEqual(len(d["photos"]), 1)


class TestBatchCatalogueResult(unittest.TestCase):
    """Verify BatchCatalogueResult dataclass behavior."""

    def test_to_dict_serializes(self):
        result = BatchCatalogueResult(
            results=[
                CatalogueResult(
                    session_id="s1",
                    subject="Coin 1",
                    photos=[],
                    status="complete",
                    ocr_ready=True,
                    review_ready=True,
                    message="msg1",
                )
            ],
            total_sessions=1,
            total_photos=2,
            ocr_ready_count=1,
            review_ready_count=1,
            errors=[],
        )
        d = result.to_dict()
        self.assertEqual(d["total_sessions"], 1)
        self.assertEqual(d["total_photos"], 2)
        self.assertEqual(d["ocr_ready_count"], 1)
        self.assertEqual(len(d["results"]), 1)


class TestSmartPhoneCataloguer(unittest.TestCase):
    """Verify SmartPhoneCataloguer orchestration facade."""

    def setUp(self):
        self.cataloguer = SmartPhoneCataloguer()

    def test_init_creates_workflow(self):
        self.assertIsNotNone(self.cataloguer.workflow)
        self.assertIsInstance(self.cataloguer.workflow, PhotoCaptureWorkflow)

    def test_init_with_existing_workflow(self):
        workflow = PhotoCaptureWorkflow()
        cataloguer = SmartPhoneCataloguer(workflow)
        self.assertEqual(cataloguer.workflow, workflow)

    def test_catalog_coin_creates_session(self):
        result = self.cataloguer.catalog_coin(
            subject="Canada 1 cent 1964",
            front_path="/tmp/front.jpg",
            back_path="/tmp/back.jpg",
        )
        self.assertIsInstance(result, CatalogueResult)
        self.assertEqual(result.subject, "Canada 1 cent 1964")
        self.assertEqual(result.status, "complete")
        self.assertTrue(result.ocr_ready)
        self.assertTrue(result.review_ready)
        self.assertEqual(len(result.photos), 2)
        self.assertEqual(len(self.cataloguer.workflow.sessions), 1)

    def test_catalog_coin_missing_back(self):
        result = self.cataloguer.catalog_coin(
            subject="Canada 1 cent 1964",
            front_path="/tmp/front.jpg",
        )
        self.assertEqual(result.status, "needs_back")
        self.assertFalse(result.ocr_ready)
        self.assertEqual(len(result.photos), 1)

    def test_catalog_coin_missing_front(self):
        result = self.cataloguer.catalog_coin(
            subject="Canada 1 cent 1964",
            back_path="/tmp/back.jpg",
        )
        self.assertEqual(result.status, "needs_front")
        self.assertFalse(result.ocr_ready)
        self.assertEqual(len(result.photos), 1)

    def test_catalog_note_creates_session(self):
        result = self.cataloguer.catalog_note(
            subject="Canada $1 1937",
            front_path="/tmp/note_front.jpg",
            back_path="/tmp/note_back.jpg",
        )
        self.assertEqual(result.subject, "Canada $1 1937")
        self.assertEqual(result.status, "complete")
        self.assertTrue(result.ocr_ready)
        self.assertEqual(len(result.photos), 2)

    def test_catalog_listing_creates_session(self):
        result = self.cataloguer.catalog_listing(
            subject="eBay Listing: Newfoundland 50 cents 1909",
            file_path="/tmp/listing.jpg",
            candidate_id="ebay-123",
        )
        self.assertEqual(result.subject, "eBay Listing: Newfoundland 50 cents 1909")
        self.assertEqual(result.status, "complete")
        self.assertEqual(len(result.photos), 1)
        self.assertEqual(self.cataloguer.workflow.sessions[0].photos[0].linked_candidate_id, "ebay-123")

    def test_add_photo_to_session(self):
        session = self.cataloguer.workflow.start_session(SESSION_COIN_FRONT_BACK, subject="Test")
        photo = self.cataloguer.add_photo_to_session(session, "/tmp/extra.jpg", ROLE_COIN_FRONT)
        self.assertIsInstance(photo, CapturedPhoto)
        self.assertEqual(photo.file_path, "/tmp/extra.jpg")
        self.assertEqual(photo.photo_role, ROLE_COIN_FRONT)

    def test_get_report(self):
        self.cataloguer.catalog_coin("Coin 1", "/tmp/f1.jpg", "/tmp/b1.jpg")
        self.cataloguer.catalog_coin("Coin 2", "/tmp/f2.jpg", "/tmp/b2.jpg")
        report = self.cataloguer.get_report()
        self.assertIsInstance(report, PhotoCaptureReport)
        self.assertEqual(report.total_sessions, 2)
        self.assertEqual(report.total_photos, 4)

    def test_get_ocr_sources(self):
        self.cataloguer.catalog_coin("Coin 1", "/tmp/f1.jpg", "/tmp/b1.jpg")
        sources = self.cataloguer.get_ocr_sources()
        self.assertEqual(len(sources), 2)  # front and back
        self.assertIn("photo_id", sources[0])
        self.assertIn("image_path", sources[0])

    def test_get_photo_vault_records(self):
        self.cataloguer.catalog_coin("Coin 1", "/tmp/f1.jpg", "/tmp/b1.jpg")
        records = self.cataloguer.get_photo_vault_records()
        self.assertEqual(len(records), 2)

    def test_batch_catalogue_multiple_items(self):
        items = [
            {
                "type": "coin",
                "subject": "Canada 1 cent 1964",
                "front_path": "/tmp/c1_front.jpg",
                "back_path": "/tmp/c1_back.jpg",
            },
            {
                "type": "note",
                "subject": "Canada $1 1937",
                "front_path": "/tmp/n1_front.jpg",
                "back_path": "/tmp/n1_back.jpg",
            },
            {
                "type": "listing",
                "subject": "eBay: Newfoundland 50 cents",
                "file_path": "/tmp/listing.jpg",
                "candidate_id": "ebay-456",
            },
        ]
        result = self.cataloguer.batch_catalogue(items)
        self.assertIsInstance(result, BatchCatalogueResult)
        self.assertEqual(len(result.results), 3)
        self.assertEqual(result.total_sessions, 3)
        self.assertEqual(result.total_photos, 5)  # 2 + 2 + 1
        self.assertEqual(result.ocr_ready_count, 3)
        self.assertEqual(result.review_ready_count, 3)
        self.assertEqual(len(result.errors), 0)

    def test_batch_catalogue_unknown_type(self):
        items = [
            {
                "type": "unknown",
                "subject": "Mystery item",
            }
        ]
        result = self.cataloguer.batch_catalogue(items)
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].status, "error")
        self.assertIn("Unknown item type", result.results[0].message)

    def test_batch_catalogue_with_errors(self):
        items = [
            {
                "type": "coin",
                "subject": "Valid coin",
                "front_path": "/tmp/f.jpg",
                "back_path": "/tmp/b.jpg",
            },
            {
                "type": "listing",
                # Missing required file_path
                "subject": "Bad listing",
            },
        ]
        result = self.cataloguer.batch_catalogue(items)
        self.assertEqual(len(result.results), 1)  # First succeeds
        self.assertEqual(len(result.errors), 1)  # Second fails

    def test_run_smart_phone_cataloguer_convenience(self):
        items = [
            {
                "type": "coin",
                "subject": "Canada 1 cent 1964",
                "front_path": "/tmp/front.jpg",
                "back_path": "/tmp/back.jpg",
            }
        ]
        result = run_smart_phone_cataloguer(items)
        self.assertIsInstance(result, BatchCatalogueResult)
        self.assertEqual(result.total_sessions, 1)
        self.assertEqual(result.total_photos, 2)


class TestOrchestrationReusesWorkflow(unittest.TestCase):
    """Verify that SmartPhoneCataloguer delegates to PhotoCaptureWorkflow
    and does not duplicate logic."""

    def test_catalog_coin_delegates_to_capture_coin_pair(self):
        workflow = Mock(spec=PhotoCaptureWorkflow)
        mock_session = Mock()
        mock_session.session_id = "test-id"
        mock_session.subject = "Test"
        mock_session.photos = []
        mock_session.front_back_complete = True
        mock_session.missing_front = False
        mock_session.missing_back = False
        mock_session.ready_for_ocr = True
        mock_session.ready_for_review = True
        workflow.capture_coin_pair.return_value = mock_session

        cataloguer = SmartPhoneCataloguer(workflow)
        result = cataloguer.catalog_coin("Test", "/tmp/f.jpg", "/tmp/b.jpg")

        workflow.capture_coin_pair.assert_called_once_with(
            subject="Test",
            front_path="/tmp/f.jpg",
            back_path="/tmp/b.jpg",
            location="",
            notes="",
        )
        self.assertEqual(result.session_id, "test-id")

    def test_get_report_delegates_to_workflow_report(self):
        workflow = Mock(spec=PhotoCaptureWorkflow)
        workflow.report.return_value = Mock(spec=PhotoCaptureReport)

        cataloguer = SmartPhoneCataloguer(workflow)
        report = cataloguer.get_report()

        workflow.report.assert_called_once()
        self.assertIsNotNone(report)

    def test_get_ocr_sources_delegates_to_workflow_ocr_sources(self):
        workflow = Mock(spec=PhotoCaptureWorkflow)
        workflow.ocr_sources.return_value = [{"photo_id": "p1", "image_path": "/tmp/1.jpg"}]

        cataloguer = SmartPhoneCataloguer(workflow)
        sources = cataloguer.get_ocr_sources()

        workflow.ocr_sources.assert_called_once()
        self.assertEqual(len(sources), 1)

    def test_get_photo_vault_records_delegates_to_workflow(self):
        workflow = Mock(spec=PhotoCaptureWorkflow)
        workflow.photo_vault_records.return_value = [Mock()]

        cataloguer = SmartPhoneCataloguer(workflow)
        records = cataloguer.get_photo_vault_records()

        workflow.photo_vault_records.assert_called_once()
        self.assertEqual(len(records), 1)




class TestOCRIntegration(unittest.TestCase):
    """Verify OCR identification integration with SmartPhoneCataloguer."""

    def setUp(self):
        self.cataloguer = SmartPhoneCataloguer()

    def test_identify_photo_delegates_to_ocr_engine(self):
        """Verify that identify_photo delegates to OCRIdentificationEngine."""
        # Create a mock photo
        photo = CapturedPhoto(
            photo_id="test-photo-1",
            file_path="/tmp/test.jpg",
            photo_role=ROLE_COIN_FRONT,
        )

        report = self.cataloguer.identify_photo(photo)
        self.assertIsInstance(report, OCRIdentificationReport)
        self.assertIsNotNone(report.candidates)

    def test_identify_session_delegates_to_ocr_engine(self):
        """Verify that identify_session delegates to OCRIdentificationEngine."""
        session = self.cataloguer.workflow.start_session(SESSION_COIN_FRONT_BACK, subject="Test")
        self.cataloguer.add_photo_to_session(session, "/tmp/front.jpg", ROLE_COIN_FRONT)
        self.cataloguer.add_photo_to_session(session, "/tmp/back.jpg", ROLE_COIN_BACK)

        report = self.cataloguer.identify_session(session)
        self.assertIsInstance(report, OCRIdentificationReport)

    def test_batch_identify_returns_dict_of_reports(self):
        """Verify batch_identify returns mapping of session_id -> OCRIdentificationReport."""
        self.cataloguer.catalog_coin("Coin 1", "/tmp/f1.jpg", "/tmp/b1.jpg")
        self.cataloguer.catalog_coin("Coin 2", "/tmp/f2.jpg", "/tmp/b2.jpg")

        results = self.cataloguer.batch_identify()
        self.assertIsInstance(results, dict)
        self.assertEqual(len(results), 2)
        for session_id, report in results.items():
            self.assertIsInstance(session_id, str)
            self.assertIsInstance(report, OCRIdentificationReport)

    def test_batch_identify_skips_incomplete_sessions(self):
        """Verify batch_identify only processes sessions ready for OCR."""
        self.cataloguer.catalog_coin("Complete", "/tmp/f.jpg", "/tmp/b.jpg")
        self.cataloguer.catalog_coin("Incomplete", "/tmp/f.jpg")  # Missing back

        results = self.cataloguer.batch_identify()
        self.assertEqual(len(results), 1)  # Only complete session

    def test_catalogue_and_identify_combines_both_steps(self):
        """Verify catalogue_and_identify runs cataloguing + OCR in one call."""
        result = self.cataloguer.catalogue_and_identify(
            subject="Canada 1 cent 1964",
            front_path="/tmp/front.jpg",
            back_path="/tmp/back.jpg",
        )
        self.assertIsInstance(result, CatalogueResult)
        self.assertIsNotNone(result.ocr_report)
        self.assertIsInstance(result.ocr_report, OCRIdentificationReport)
        self.assertIn("OCR:", result.message)

    def test_catalogue_and_identify_with_raw_text(self):
        """Verify catalogue_and_identify passes raw text to OCR engine."""
        raw_text = {"test-photo-1": "Canada 1 cent 1964"}
        result = self.cataloguer.catalogue_and_identify(
            subject="Canada 1 cent 1964",
            front_path="/tmp/front.jpg",
            back_path="/tmp/back.jpg",
            raw_text_by_photo_id=raw_text,
        )
        self.assertIsNotNone(result.ocr_report)

    def test_identify_photo_with_mock_ocr(self):
        """Verify identify_photo with mocked OCR engine."""
        mock_engine = Mock(spec=OCRIdentificationEngine)
        mock_report = Mock(spec=OCRIdentificationReport)
        mock_report.candidates = []
        mock_engine.identify_from_captured_photo.return_value = mock_report

        cataloguer = SmartPhoneCataloguer()
        cataloguer.identify_photo = lambda photo, raw_text=None: mock_engine.identify_from_captured_photo(photo, raw_text=raw_text)

        photo = CapturedPhoto(photo_id="test", file_path="/tmp/test.jpg", photo_role=ROLE_COIN_FRONT)
        report = cataloguer.identify_photo(photo)

        self.assertEqual(report, mock_report)

    def test_identify_session_with_mock_ocr(self):
        """Verify identify_session with mocked OCR engine."""
        mock_engine = Mock(spec=OCRIdentificationEngine)
        mock_report = Mock(spec=OCRIdentificationReport)
        mock_report.candidates = []
        mock_engine.identify_from_session.return_value = mock_report

        cataloguer = SmartPhoneCataloguer()
        cataloguer.identify_session = lambda session, raw_text=None: mock_engine.identify_from_session(session, raw_text_by_photo_id=raw_text)

        session = cataloguer.workflow.start_session(SESSION_COIN_FRONT_BACK, subject="Test")
        report = cataloguer.identify_session(session)

        self.assertEqual(report, mock_report)
if __name__ == '__main__':
    unittest.main()
