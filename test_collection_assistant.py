"""
Tests for the Collection Assistant Engine.

These tests verify deterministic collection assistance without AI,
forecasting, machine learning, or external APIs.
"""

import unittest
from datetime import datetime
import os
import tempfile
import shutil

from collection_assistant import (
    CollectionAssistantEngine,
    AssistantSummary,
    CollectionAssistantCandidate,
    AssistantReviewQueue,
    ProductivityMetrics,
    SideBySideComparison,
    PhotoInfo,
    OCRCandidate,
    CollectionMatch,
    CollectionGapInfo,
    AcquisitionPriorityInfo,
    ReviewStatus,
    PhotoSide,
    PhotoQuality,
    CandidateSource,
)


class TestCollectionAssistantEngine(unittest.TestCase):
    """Test suite for CollectionAssistantEngine."""

    def setUp(self):
        """Set up test fixtures."""
        self.engine = CollectionAssistantEngine()
        self.session = self.engine.start_session("test_session")
        # Create a default candidate for tests that need one
        self.temp_dir = tempfile.mkdtemp()
        self.temp_photo_path = os.path.join(self.temp_dir, "test_photo.jpg")
        with open(self.temp_photo_path, "wb") as f:
            f.write(b"fake photo data")
        self.engine.add_photos_to_session("test_session", [self.temp_photo_path], auto_pair=False)

    def tearDown(self):
        """Clean up temp files."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_candidate_with_ocr(self, ocr_text: str, candidate_id: str = "test_session_candidate_1") -> CollectionAssistantCandidate:
        """Helper to create a candidate with OCR data."""
        self.engine.process_ocr_for_candidate("test_session", candidate_id, ocr_text)
        return next(c for c in self.session.queue.candidates if c.id == candidate_id)

    def test_engine_initialization(self):
        """Test engine initializes with empty sessions."""
        self.assertEqual(len(self.engine.sessions), 1)
        self.assertEqual(self.engine.session_counter, 1)

    def test_start_session(self):
        """Test starting a new session."""
        session = self.engine.start_session("session_2")
        self.assertEqual(session.session_id, "session_2")
        self.assertEqual(session.status, "active")
        self.assertEqual(len(self.engine.sessions), 2)

    def test_start_session_auto_id(self):
        """Test starting a session with auto-generated ID."""
        session = self.engine.start_session()
        self.assertTrue(session.session_id.startswith("session_"))
        self.assertEqual(len(self.engine.sessions), 2)

    def test_add_photos_to_session(self):
        """Test adding photos to a session."""
        temp_path = os.path.join(self.temp_dir, "extra_photo.jpg")
        with open(temp_path, "wb") as f:
            f.write(b"fake photo data")

        photos = self.engine.add_photos_to_session(
            "test_session", [temp_path], auto_pair=False
        )
        self.assertEqual(len(photos), 1)
        self.assertEqual(photos[0].file_path, temp_path)
        # setUp already added 1 photo, so this makes 2
        self.assertEqual(self.session.metrics.photos_processed, 2)
        self.assertEqual(self.session.metrics.candidates_generated, 2)

    def test_add_photos_with_obverse_reverse(self):
        """Test adding obverse and reverse photos with auto-pairing."""
        obverse_path = os.path.join(self.temp_dir, "coin_obverse.jpg")
        reverse_path = os.path.join(self.temp_dir, "coin_reverse.jpg")
        with open(obverse_path, "wb") as f:
            f.write(b"fake photo data")
        with open(reverse_path, "wb") as f:
            f.write(b"fake photo data")

        photos = self.engine.add_photos_to_session(
            "test_session", [obverse_path, reverse_path], auto_pair=True
        )
        self.assertEqual(len(photos), 2)
        # Check pairing
        obverse = next(p for p in photos if p.side == PhotoSide.OBVERSE)
        reverse = next(p for p in photos if p.side == PhotoSide.REVERSE)
        self.assertTrue(obverse.has_pair)
        self.assertTrue(reverse.has_pair)
        self.assertEqual(obverse.paired_photo, reverse_path)
        self.assertEqual(reverse.paired_photo, obverse_path)

    def test_detect_side_from_filename(self):
        """Test side detection from filename."""
        self.assertEqual(
            self.engine._detect_side_from_filename("coin_obverse.jpg"),
            PhotoSide.OBVERSE
        )
        self.assertEqual(
            self.engine._detect_side_from_filename("coin_reverse.jpg"),
            PhotoSide.REVERSE
        )
        self.assertEqual(
            self.engine._detect_side_from_filename("coin_front.jpg"),
            PhotoSide.OBVERSE
        )
        self.assertEqual(
            self.engine._detect_side_from_filename("coin_back.jpg"),
            PhotoSide.REVERSE
        )
        self.assertEqual(
            self.engine._detect_side_from_filename("coin.jpg"),
            PhotoSide.UNKNOWN
        )

    def test_assess_photo_quality(self):
        """Test photo quality assessment."""
        small_path = os.path.join(self.temp_dir, "small.jpg")
        medium_path = os.path.join(self.temp_dir, "medium.jpg")
        large_path = os.path.join(self.temp_dir, "large.jpg")
        with open(small_path, "wb") as f:
            f.write(b"x" * 1000)  # 1KB
        with open(medium_path, "wb") as f:
            f.write(b"x" * 500000)  # 500KB
        with open(large_path, "wb") as f:
            f.write(b"x" * 2000000)  # 2MB

        self.assertEqual(
            self.engine._assess_photo_quality(small_path),
            PhotoQuality.POOR
        )
        self.assertEqual(
            self.engine._assess_photo_quality(medium_path),
            PhotoQuality.GOOD
        )
        self.assertEqual(
            self.engine._assess_photo_quality(large_path),
            PhotoQuality.EXCELLENT
        )

    def test_auto_pair_photos(self):
        """Test auto-pairing of photos."""
        photo1 = PhotoInfo(file_path="coin1_obverse.jpg", side=PhotoSide.OBVERSE)
        photo2 = PhotoInfo(file_path="coin1_reverse.jpg", side=PhotoSide.REVERSE)
        photo3 = PhotoInfo(file_path="coin2.jpg", side=PhotoSide.UNKNOWN)

        photos = self.engine._auto_pair_photos([photo1, photo2, photo3])
        obverse = next(p for p in photos if p.side == PhotoSide.OBVERSE)
        reverse = next(p for p in photos if p.side == PhotoSide.REVERSE)

        self.assertTrue(obverse.has_pair)
        self.assertEqual(obverse.paired_photo, "coin1_reverse.jpg")
        self.assertTrue(reverse.has_pair)
        self.assertEqual(reverse.paired_photo, "coin1_obverse.jpg")

        # Single photo should not be paired
        single = next(p for p in photos if p.file_path == "coin2.jpg")
        self.assertFalse(single.has_pair)

    def test_extract_base_filename(self):
        """Test base filename extraction."""
        self.assertEqual(
            self.engine._extract_base_filename("coin_obverse.jpg"),
            "coin"
        )
        self.assertEqual(
            self.engine._extract_base_filename("coin_reverse.jpg"),
            "coin"
        )
        self.assertEqual(
            self.engine._extract_base_filename("coin_front.jpg"),
            "coin"
        )
        self.assertEqual(
            self.engine._extract_base_filename("coin.jpg"),
            "coin"
        )

    def test_parse_ocr_text(self):
        """Test OCR text parsing."""
        ocr_text = "CANADA 10 CENTS 1880"
        result = self.engine._parse_ocr_text(ocr_text)

        self.assertEqual(result.detected_year, "1880")
        self.assertEqual(result.detected_country, "Canada")
        self.assertIn("10 cents", result.detected_denomination.lower())
        self.assertGreater(result.confidence, 0.0)
        self.assertEqual(result.trust_level, "HIGH")

    def test_parse_ocr_text_empty(self):
        """Test OCR parsing with empty text."""
        result = self.engine._parse_ocr_text("")
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.trust_level, "LOW")
        self.assertTrue(len(result.warnings) > 0)

    def test_parse_ocr_text_partial(self):
        """Test OCR parsing with partial information."""
        result = self.engine._parse_ocr_text("NEWFOUNDLAND")
        self.assertEqual(result.detected_country, "Newfoundland")
        self.assertIsNone(result.detected_year)
        self.assertIsNone(result.detected_denomination)
        self.assertLess(result.confidence, 0.5)

    def test_build_suggested_identification(self):
        """Test building suggested identification."""
        ocr = OCRCandidate(
            detected_year="1880",
            detected_country="Canada",
            detected_denomination="10 Cents",
            confidence=0.9,
            trust_level="HIGH"
        )
        suggested = self.engine._build_suggested_identification(ocr)

        self.assertEqual(suggested["year"], "1880")
        self.assertEqual(suggested["country"], "Canada")
        self.assertEqual(suggested["denomination"], "10 Cents")
        self.assertEqual(suggested["confidence"], 0.9)

    def test_check_collection_exact_match(self):
        """Test exact collection match detection."""
        collection_items = [
            {"country": "Canada", "denomination": "10 Cents", "year": "1880"}
        ]
        self._create_candidate_with_ocr("CANADA 10 CENTS 1880")
        match = self.engine.check_collection_for_candidate(
            "test_session", "test_session_candidate_1", collection_items
        )
        self.assertTrue(match.matched)
        self.assertEqual(match.match_type, "exact")
        self.assertEqual(match.duplicate_risk, "high")

    def test_check_collection_no_match(self):
        """Test no collection match."""
        collection_items = [
            {"country": "Canada", "denomination": "5 Cents", "year": "1900"}
        ]
        self._create_candidate_with_ocr("CANADA 10 CENTS 1880")
        match = self.engine.check_collection_for_candidate(
            "test_session", "test_session_candidate_1", collection_items
        )
        self.assertFalse(match.matched)

    def test_check_collection_gaps(self):
        """Test collection gap detection."""
        series_data = {
            "series_definitions": [
                {
                    "name": "Newfoundland 5 Cent",
                    "owned_dates": ["1880"],
                    "missing_dates": ["1881", "1882"]
                }
            ]
        }
        self._create_candidate_with_ocr("NEWFOUNDLAND 5 CENTS 1881")
        gap = self.engine.check_collection_gaps(
            "test_session", "test_session_candidate_1", series_data
        )
        self.assertTrue(gap.fills_gap)
        self.assertEqual(gap.gap_type, "series")

    def test_check_acquisition_priority_want_list(self):
        """Test acquisition priority from WANT_LIST."""
        want_list = [
            {"country": "Canada", "denomination": "10 Cents", "year": "1880"}
        ]
        self._create_candidate_with_ocr("CANADA 10 CENTS 1880")
        priority = self.engine.check_acquisition_priority(
            "test_session", "test_session_candidate_1", want_list=want_list
        )
        self.assertTrue(priority.has_priority)
        self.assertEqual(priority.priority_category, "want_list")

    def test_build_side_by_side_comparison(self):
        """Test side-by-side comparison building."""
        self._create_candidate_with_ocr("CANADA 10 CENTS 1880")
        comparison = self.engine.build_side_by_side_comparison(
            "test_session", "test_session_candidate_1"
        )
        self.assertIsNotNone(comparison)
        self.assertIsNotNone(comparison.candidate)
        self.assertIsNotNone(comparison.evidence)
        self.assertIsNotNone(comparison.recommendations)
        self.assertIsNotNone(comparison.warnings)

    def test_review_candidate(self):
        """Test reviewing a candidate."""
        self._create_candidate_with_ocr("CANADA 10 CENTS 1880")
        result = self.engine.review_candidate(
            "test_session", "test_session_candidate_1", ReviewStatus.APPROVED, "Looks good"
        )
        self.assertTrue(result)

        candidate = self.session.queue.candidates[0]
        self.assertEqual(candidate.review_status, ReviewStatus.APPROVED)
        self.assertEqual(candidate.review_notes, "Looks good")
        self.assertIsNotNone(candidate.reviewed_at)
        self.assertEqual(self.session.metrics.approvals, 1)
        self.assertEqual(self.session.metrics.reviews_completed, 1)

    def test_review_candidate_rejected(self):
        """Test rejecting a candidate."""
        self._create_candidate_with_ocr("CANADA 10 CENTS 1880")
        self.engine.review_candidate(
            "test_session", "test_session_candidate_1", ReviewStatus.REJECTED, "Duplicate"
        )
        self.assertEqual(self.session.metrics.rejections, 1)

    def test_get_next_candidate_for_review(self):
        """Test getting next candidate for review."""
        # Add a second candidate
        temp_path2 = os.path.join(self.temp_dir, "extra2.jpg")
        with open(temp_path2, "wb") as f:
            f.write(b"fake photo data")
        self.engine.add_photos_to_session("test_session", [temp_path2])
        self.engine.process_ocr_for_candidate("test_session", "test_session_candidate_1", "CANADA 10 CENTS 1880")
        self.engine.process_ocr_for_candidate("test_session", "test_session_candidate_2", "NEWFOUNDLAND 5 CENTS 1881")

        next_candidate = self.engine.get_next_candidate_for_review("test_session")
        self.assertIsNotNone(next_candidate)

    def test_get_incomplete_reviews(self):
        """Test getting incomplete reviews."""
        self._create_candidate_with_ocr("CANADA 10 CENTS 1880")
        self.engine.review_candidate(
            "test_session", "test_session_candidate_1", ReviewStatus.INCOMPLETE
        )
        incomplete = self.engine.get_incomplete_reviews("test_session")
        self.assertEqual(len(incomplete), 1)

    def test_complete_session(self):
        """Test completing a session."""
        self._create_candidate_with_ocr("CANADA 10 CENTS 1880")
        completed = self.engine.complete_session("test_session")
        self.assertIsNotNone(completed)
        self.assertEqual(completed.status, "completed")
        self.assertIsNotNone(completed.end_time)
        self.assertGreater(completed.duration.total_seconds(), 0)

    def test_export_session_markdown(self):
        """Test session Markdown export."""
        self._create_candidate_with_ocr("CANADA 10 CENTS 1880")
        markdown = self.engine.export_session_markdown("test_session")
        self.assertIn("Collection Assistant Session Report", markdown)
        self.assertIn("test_session", markdown)

    def test_export_session_csv(self):
        """Test session CSV export."""
        self._create_candidate_with_ocr("CANADA 10 CENTS 1880")
        csv = self.engine.export_session_csv("test_session")
        lines = csv.split("\n")
        self.assertTrue(len(lines) > 1)
        self.assertIn("ID,Display,Source,Confidence,Status", lines[0])

    def test_export_productivity_report(self):
        """Test productivity report export."""
        self._create_candidate_with_ocr("CANADA 10 CENTS 1880")
        report = self.engine.export_productivity_report_markdown("test_session")
        self.assertIn("Productivity Report", report)
        self.assertIn("Photos Processed", report)

    def test_metrics_calculation(self):
        """Test productivity metrics calculations."""
        metrics = ProductivityMetrics(
            ocr_attempts=10,
            ocr_successes=8,
            candidates_generated=10,
            reviews_completed=5,
            approvals=3,
            rejections=2,
            average_confidence=0.75,
            estimated_time_saved=450,  # 7.5 minutes
        )
        self.assertEqual(metrics.ocr_success_rate, 80.0)
        self.assertEqual(metrics.review_completion_rate, 50.0)
        self.assertEqual(metrics.approval_rate, 60.0)
        self.assertEqual(metrics.estimated_time_saved_minutes, 7.5)

    def test_review_queue_filtering(self):
        """Test review queue filtering."""
        queue = AssistantReviewQueue()

        # Add candidates with different statuses
        c1 = CollectionAssistantCandidate(id="1", review_status=ReviewStatus.PENDING, confidence=0.9)
        c2 = CollectionAssistantCandidate(id="2", review_status=ReviewStatus.APPROVED, confidence=0.5)
        c3 = CollectionAssistantCandidate(id="3", review_status=ReviewStatus.PENDING, confidence=0.3)

        queue.candidates = [c1, c2, c3]

        # Test pending filter
        queue.filter_status = ReviewStatus.PENDING
        filtered = queue.get_filtered_candidates()
        self.assertEqual(len(filtered), 2)

        # Test confidence filter
        queue.filter_status = None
        queue.filter_confidence_min = 0.5
        filtered = queue.get_filtered_candidates()
        self.assertEqual(len(filtered), 2)

    def test_review_queue_completion(self):
        """Test review queue completion tracking."""
        queue = AssistantReviewQueue()
        queue.candidates = [
            CollectionAssistantCandidate(id="1", review_status=ReviewStatus.APPROVED),
            CollectionAssistantCandidate(id="2", review_status=ReviewStatus.PENDING),
        ]
        self.assertEqual(queue.completion_percentage, 50.0)
        self.assertFalse(queue.is_complete)

        queue.candidates[1].review_status = ReviewStatus.APPROVED
        self.assertEqual(queue.completion_percentage, 100.0)
        self.assertTrue(queue.is_complete)

    def test_candidate_properties(self):
        """Test candidate properties."""
        candidate = CollectionAssistantCandidate(
            id="test",
            photos=[
                PhotoInfo(file_path="obverse.jpg", side=PhotoSide.OBVERSE),
                PhotoInfo(file_path="reverse.jpg", side=PhotoSide.REVERSE),
            ],
            confidence=0.85,
            collection_match=CollectionMatch(duplicate_risk="high"),
            gap_info=CollectionGapInfo(fills_gap=True),
        )
        self.assertTrue(candidate.is_photo_pair_complete)
        self.assertTrue(candidate.has_high_confidence)
        self.assertTrue(candidate.is_duplicate_risk)
        self.assertTrue(candidate.fills_collection_gap)
        self.assertTrue(candidate.is_pending)
        self.assertFalse(candidate.is_approved)

    def test_candidate_display_label(self):
        """Test candidate display label generation."""
        candidate = CollectionAssistantCandidate(
            id="test",
            suggested_identification={
                "country": "Canada",
                "denomination": "10 Cents",
                "year": "1880"
            }
        )
        self.assertEqual(candidate.display_label, "Canada 10 Cents 1880")

        # Test with OCR only
        candidate2 = CollectionAssistantCandidate(
            id="test2",
            ocr_result=OCRCandidate(
                detected_country="Newfoundland",
                detected_denomination="5 Cents",
                detected_year="1881"
            )
        )
        self.assertEqual(candidate2.display_label, "Newfoundland 5 Cents 1881")

    def test_session_summary(self):
        """Test session summary generation."""
        session = AssistantSummary(session_id="test")
        self.assertFalse(session.is_completed)
        self.assertGreaterEqual(session.duration.total_seconds(), 0)

        dict_data = session.to_dict()
        self.assertEqual(dict_data["session_id"], "test")
        self.assertEqual(dict_data["status"], "active")

    def test_side_by_side_comparison(self):
        """Test side-by-side comparison creation."""
        candidate = CollectionAssistantCandidate(
            id="test",
            confidence=0.9,
            suggested_identification={"country": "Canada", "denomination": "10 Cents", "year": "1880"},
            collection_match=CollectionMatch(matched=False),
            gap_info=CollectionGapInfo(fills_gap=True),
        )
        comparison = SideBySideComparison(
            candidate=candidate,
            suggested_identification=candidate.suggested_identification,
            confidence=candidate.confidence,
        )
        self.assertEqual(comparison.confidence, 0.9)

    def test_multiple_sessions(self):
        """Test managing multiple sessions."""
        session1 = self.engine.start_session("session_1")
        session2 = self.engine.start_session("session_2")

        self.assertEqual(len(self.engine.sessions), 3)  # test_session + 2 new
        self.assertIn("session_1", self.engine.sessions)
        self.assertIn("session_2", self.engine.sessions)

    def test_nonexistent_session(self):
        """Test operations on nonexistent session."""
        result = self.engine.add_photos_to_session("nonexistent", [])
        self.assertEqual(result, [])

        result = self.engine.process_ocr_for_candidate("nonexistent", "id", "text")
        self.assertIsNone(result)

        result = self.engine.complete_session("nonexistent")
        self.assertIsNone(result)

    def test_nonexistent_candidate(self):
        """Test operations on nonexistent candidate."""
        result = self.engine.process_ocr_for_candidate("test_session", "nonexistent", "text")
        self.assertIsNone(result)

        result = self.engine.review_candidate("test_session", "nonexistent", ReviewStatus.APPROVED)
        self.assertFalse(result)

        result = self.engine.build_side_by_side_comparison("test_session", "nonexistent")
        self.assertIsNotNone(result)
        self.assertEqual(result.candidate.id, "nonexistent")

    def test_review_queue_navigation(self):
        """Test review queue navigation."""
        queue = AssistantReviewQueue()
        queue.candidates = [
            CollectionAssistantCandidate(id="1", review_status=ReviewStatus.PENDING),
            CollectionAssistantCandidate(id="2", review_status=ReviewStatus.PENDING),
        ]

        next_cand = queue.get_next_pending()
        self.assertIsNotNone(next_cand)
        self.assertEqual(next_cand.id, "1")

    def test_productivity_metrics_to_dict(self):
        """Test productivity metrics serialization."""
        metrics = ProductivityMetrics(
            photos_processed=5,
            ocr_attempts=5,
            ocr_successes=4,
            candidates_generated=5,
            reviews_completed=3,
            approvals=2,
            rejections=1,
            average_confidence=0.8,
            estimated_time_saved=270,
        )
        data = metrics.to_dict()
        self.assertEqual(data["photos_processed"], 5)
        self.assertEqual(data["ocr_success_rate"], "80.0%")
        self.assertEqual(data["approval_rate"], "66.7%")
        self.assertEqual(data["estimated_time_saved_minutes"], "4.5")


if __name__ == "__main__":
    unittest.main()
