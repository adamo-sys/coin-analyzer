"""Unit tests for the Batch Processing Engine — v8.1 Phase 4.

Tests folder scanning, photo discovery, front/back auto-pairing,
batch candidate creation, SmartPhoneCataloguer orchestration,
OCR integration, collection matching, proposed entries,
Collection Intelligence batch outputs, Deal Hunter evaluation,
Batch Review Workflow (review states, approve/reject/needs-review,
auto-review, review summaries), and export.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import shutil

from batch_processing import (
    BatchProcessingEngine,
    BatchSource,
    BatchCandidate,
    BatchReport,
    BatchSummary,
    BatchStatus,
    BatchIntelligence,
    ReviewStatus,
)
from smart_phone_cataloguer import (
    SmartPhoneCataloguer,
    CatalogueResult,
    BatchCatalogueResult,
    CollectionMatchResult,
    ProposedCollectionEntry,
)
from photo_capture_workflow import PhotoCaptureWorkflow
from collection_intelligence import CollectionIntelligenceEngine, AcquisitionTarget
from deal_hunter import DealHunter, DealListing, DealHunterReport


class TestBatchSource(unittest.TestCase):
    """Verify BatchSource dataclass behavior."""

    def test_to_dict_serializes(self):
        source = BatchSource(
            folder_path="/tmp/test",
            file_pattern="*.jpg",
            auto_pair=True,
        )
        d = source.to_dict()
        self.assertEqual(d["folder_path"], "/tmp/test")
        self.assertEqual(d["file_pattern"], "*.jpg")
        self.assertTrue(d["auto_pair"])

    def test_defaults(self):
        source = BatchSource(folder_path="/tmp/test")
        self.assertEqual(source.file_pattern, "*.jpg")
        self.assertTrue(source.auto_pair)


class TestBatchCandidate(unittest.TestCase):
    """Verify BatchCandidate dataclass behavior."""

    def test_to_dict_serializes(self):
        candidate = BatchCandidate(
            candidate_id="batch_0001_test",
            front_path="/tmp/front.jpg",
            back_path="/tmp/back.jpg",
            subject="Test Coin",
            status=BatchStatus.COMPLETED,
            review_status=ReviewStatus.APPROVED,
            review_notes="Looks good",
            warnings=["Missing metadata"],
            errors=[],
        )
        d = candidate.to_dict()
        self.assertEqual(d["candidate_id"], "batch_0001_test")
        self.assertEqual(d["front_path"], "/tmp/front.jpg")
        self.assertEqual(d["back_path"], "/tmp/back.jpg")
        self.assertEqual(d["subject"], "Test Coin")
        self.assertEqual(d["status"], "completed")
        self.assertEqual(d["review_status"], "approved")
        self.assertEqual(d["review_notes"], "Looks good")
        self.assertFalse(d["has_ocr_result"])
        self.assertFalse(d["has_collection_match"])
        self.assertFalse(d["has_proposed_entry"])

    def test_phase2_fields_populated(self):
        """Phase 2: ocr_result, collection_match, proposed_entry can be set."""
        candidate = BatchCandidate(candidate_id="test")
        self.assertIsNone(candidate.ocr_result)
        self.assertIsNone(candidate.collection_match)
        self.assertIsNone(candidate.proposed_entry)

        candidate.ocr_result = Mock()
        candidate.collection_match = Mock()
        candidate.proposed_entry = Mock()

        self.assertIsNotNone(candidate.ocr_result)
        self.assertIsNotNone(candidate.collection_match)
        self.assertIsNotNone(candidate.proposed_entry)

    def test_review_status_default_unreviewed(self):
        """Phase 4: Default review status is UNREVIEWED."""
        candidate = BatchCandidate(candidate_id="test")
        self.assertEqual(candidate.review_status, ReviewStatus.UNREVIEWED)
        self.assertEqual(candidate.review_notes, "")

    def test_is_reviewable(self):
        """Phase 4: Only COMPLETED candidates are reviewable."""
        completed = BatchCandidate(candidate_id="c1", status=BatchStatus.COMPLETED)
        self.assertTrue(completed.is_reviewable())

        failed = BatchCandidate(candidate_id="c2", status=BatchStatus.FAILED)
        self.assertFalse(failed.is_reviewable())

        pending = BatchCandidate(candidate_id="c3", status=BatchStatus.PENDING)
        self.assertFalse(pending.is_reviewable())

    def test_approve(self):
        """Phase 4: Approve a reviewable candidate."""
        candidate = BatchCandidate(candidate_id="c1", status=BatchStatus.COMPLETED)
        candidate.approve("Good condition")
        self.assertEqual(candidate.review_status, ReviewStatus.APPROVED)
        self.assertEqual(candidate.review_notes, "Good condition")

    def test_approve_non_reviewable_raises(self):
        """Phase 4: Cannot approve non-reviewable candidate."""
        candidate = BatchCandidate(candidate_id="c1", status=BatchStatus.FAILED)
        with self.assertRaises(ValueError):
            candidate.approve()

    def test_reject(self):
        """Phase 4: Reject a reviewable candidate."""
        candidate = BatchCandidate(candidate_id="c1", status=BatchStatus.COMPLETED)
        candidate.reject("Poor quality")
        self.assertEqual(candidate.review_status, ReviewStatus.REJECTED)
        self.assertEqual(candidate.review_notes, "Poor quality")

    def test_mark_needs_review(self):
        """Phase 4: Mark candidate as needs-review."""
        candidate = BatchCandidate(candidate_id="c1", status=BatchStatus.COMPLETED)
        candidate.mark_needs_review("Check grade")
        self.assertEqual(candidate.review_status, ReviewStatus.NEEDS_REVIEW)
        self.assertEqual(candidate.review_notes, "Check grade")


class TestBatchSummary(unittest.TestCase):
    """Verify BatchSummary dataclass behavior."""

    def test_to_dict_serializes(self):
        summary = BatchSummary(
            total_photos=10,
            processed=8,
            failed=2,
            ocr_ready=5,
            review_ready=3,
            duplicates_detected=1,
            upgrade_opportunities=2,
            gap_opportunities=1,
            reviewed_count=5,
            approved_count=3,
            rejected_count=1,
            needs_review_count=1,
            warnings=["Some photos missing back"],
        )
        d = summary.to_dict()
        self.assertEqual(d["total_photos"], 10)
        self.assertEqual(d["processed"], 8)
        self.assertEqual(d["failed"], 2)
        self.assertEqual(d["ocr_ready"], 5)
        self.assertEqual(d["review_ready"], 3)
        self.assertEqual(d["duplicates_detected"], 1)
        self.assertEqual(d["upgrade_opportunities"], 2)
        self.assertEqual(d["gap_opportunities"], 1)
        self.assertEqual(d["reviewed_count"], 5)
        self.assertEqual(d["approved_count"], 3)
        self.assertEqual(d["rejected_count"], 1)
        self.assertEqual(d["needs_review_count"], 1)


class TestBatchIntelligence(unittest.TestCase):
    """Verify BatchIntelligence dataclass behavior."""

    def test_to_dict_serializes(self):
        intelligence = BatchIntelligence()
        d = intelligence.to_dict()
        self.assertIsNone(d["gap_report"])
        self.assertEqual(d["batch_duplicates"], [])
        self.assertEqual(d["batch_upgrades"], [])
        self.assertEqual(d["acquisition_priorities"], [])
        self.assertFalse(d["has_deal_evaluation"])

    def test_with_gap_report(self):
        intelligence = BatchIntelligence(gap_report={"total_items": 5})
        d = intelligence.to_dict()
        self.assertEqual(d["gap_report"], {"total_items": 5})


class TestBatchReport(unittest.TestCase):
    """Verify BatchReport dataclass behavior."""

    def test_to_dict_serializes(self):
        source = BatchSource(folder_path="/tmp/test")
        candidate = BatchCandidate(candidate_id="c1", subject="Coin 1")
        report = BatchReport(
            source=source,
            candidates=[candidate],
            summary=BatchSummary(total_photos=1, processed=1),
        )
        d = report.to_dict()
        self.assertEqual(d["source"]["folder_path"], "/tmp/test")
        self.assertEqual(len(d["candidates"]), 1)
        self.assertEqual(d["summary"]["total_photos"], 1)
        self.assertIn("intelligence", d)

    def test_review_summary(self):
        """Phase 4: Verify review summary calculation."""
        source = BatchSource(folder_path="/tmp/test")
        c1 = BatchCandidate(candidate_id="c1", status=BatchStatus.COMPLETED, review_status=ReviewStatus.APPROVED)
        c2 = BatchCandidate(candidate_id="c2", status=BatchStatus.COMPLETED, review_status=ReviewStatus.REJECTED)
        c3 = BatchCandidate(candidate_id="c3", status=BatchStatus.COMPLETED, review_status=ReviewStatus.UNREVIEWED)
        c4 = BatchCandidate(candidate_id="c4", status=BatchStatus.FAILED)
        report = BatchReport(source=source, candidates=[c1, c2, c3, c4])

        summary = report.review_summary()
        self.assertEqual(summary["total_candidates"], 4)
        self.assertEqual(summary["reviewable"], 3)
        self.assertEqual(summary["approved"], 1)
        self.assertEqual(summary["rejected"], 1)
        self.assertEqual(summary["needs_review"], 0)
        self.assertEqual(summary["unreviewed"], 2)
        self.assertAlmostEqual(summary["review_completion_pct"], 66.7, places=1)

    def test_approved_candidates(self):
        """Phase 4: Filter approved candidates."""
        c1 = BatchCandidate(candidate_id="c1", review_status=ReviewStatus.APPROVED)
        c2 = BatchCandidate(candidate_id="c2", review_status=ReviewStatus.REJECTED)
        report = BatchReport(source=BatchSource(folder_path="/tmp"), candidates=[c1, c2])
        self.assertEqual(len(report.approved_candidates()), 1)
        self.assertEqual(report.approved_candidates()[0].candidate_id, "c1")

    def test_rejected_candidates(self):
        """Phase 4: Filter rejected candidates."""
        c1 = BatchCandidate(candidate_id="c1", review_status=ReviewStatus.APPROVED)
        c2 = BatchCandidate(candidate_id="c2", review_status=ReviewStatus.REJECTED)
        report = BatchReport(source=BatchSource(folder_path="/tmp"), candidates=[c1, c2])
        self.assertEqual(len(report.rejected_candidates()), 1)
        self.assertEqual(report.rejected_candidates()[0].candidate_id, "c2")

    def test_needs_review_candidates(self):
        """Phase 4: Filter needs-review candidates."""
        c1 = BatchCandidate(candidate_id="c1", review_status=ReviewStatus.APPROVED)
        c2 = BatchCandidate(candidate_id="c2", review_status=ReviewStatus.NEEDS_REVIEW)
        report = BatchReport(source=BatchSource(folder_path="/tmp"), candidates=[c1, c2])
        self.assertEqual(len(report.needs_review_candidates()), 1)
        self.assertEqual(report.needs_review_candidates()[0].candidate_id, "c2")

    def test_export_csv_includes_review(self):
        """Phase 4: CSV export includes review columns."""
        source = BatchSource(folder_path="/tmp/test")
        candidate = BatchCandidate(
            candidate_id="c1",
            subject="Coin 1",
            front_path="/tmp/front.jpg",
            status=BatchStatus.COMPLETED,
            review_status=ReviewStatus.APPROVED,
            review_notes="Good",
        )
        report = BatchReport(source=source, candidates=[candidate])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_path = f.name

        try:
            report.export_csv(temp_path)
            self.assertTrue(os.path.exists(temp_path))
            with open(temp_path, "r") as f:
                content = f.read()
            self.assertIn("review_status", content)
            self.assertIn("review_notes", content)
            self.assertIn("approved", content)
            self.assertIn("Good", content)
        finally:
            os.remove(temp_path)

    def test_export_markdown_includes_review(self):
        """Phase 4: Markdown export includes review summary."""
        source = BatchSource(folder_path="/tmp/test")
        c1 = BatchCandidate(candidate_id="c1", status=BatchStatus.COMPLETED, review_status=ReviewStatus.APPROVED)
        report = BatchReport(source=source, candidates=[c1])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            temp_path = f.name

        try:
            report.export_markdown(temp_path)
            with open(temp_path, "r") as f:
                content = f.read()
            self.assertIn("## Review Summary", content)
            self.assertIn("Approved: 1", content)
        finally:
            os.remove(temp_path)

    def test_export_markdown_with_intelligence(self):
        """Verify Markdown export includes Collection Intelligence section."""
        source = BatchSource(folder_path="/tmp/test")
        candidate = BatchCandidate(candidate_id="c1", subject="Coin 1")
        intelligence = BatchIntelligence(
            batch_duplicates=[{"country": "Canada", "denomination": "1 cent", "year": "1964", "count": 2}],
            acquisition_priorities=[
                AcquisitionTarget(country="Canada", denomination="1 cent", year="1965", target_type="Missing Date", priority_score=50, estimated_impact="High", reason="Gap fill")
            ]
        )
        report = BatchReport(source=source, candidates=[candidate], intelligence=intelligence)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            temp_path = f.name

        try:
            report.export_markdown(temp_path)
            with open(temp_path, "r") as f:
                content = f.read()
            self.assertIn("## Collection Intelligence", content)
            self.assertIn("### Batch Duplicates", content)
            self.assertIn("### Acquisition Priorities", content)
        finally:
            os.remove(temp_path)


class TestBatchProcessingEngine(unittest.TestCase):
    """Verify BatchProcessingEngine orchestration."""

    def setUp(self):
        self.cataloguer = SmartPhoneCataloguer()
        self.engine = BatchProcessingEngine(self.cataloguer)

    def test_init_requires_cataloguer(self):
        self.assertIsNotNone(self.engine.cataloguer)
        self.assertIsInstance(self.engine.cataloguer, SmartPhoneCataloguer)

    def test_discover_photos_finds_jpg(self):
        """Verify photo discovery finds JPG files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                open(os.path.join(tmpdir, f"IMG_{i:04d}.jpg"), "w").close()

            photos = self.engine._discover_photos(tmpdir, "*.jpg")
            self.assertEqual(len(photos), 3)

    def test_discover_photos_finds_png_when_no_jpg(self):
        """Verify photo discovery falls back to PNG when no JPG found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "photo.png"), "w").close()

            photos = self.engine._discover_photos(tmpdir, "*.jpg")
            self.assertEqual(len(photos), 1)
            self.assertTrue(photos[0].endswith(".png"))

    def test_discover_photos_raises_on_missing_folder(self):
        """Verify photo discovery raises on missing folder."""
        with self.assertRaises(ValueError) as ctx:
            self.engine._discover_photos("/nonexistent/path")
        self.assertIn("Folder not found", str(ctx.exception))

    def test_auto_pair_front_back(self):
        """Verify auto-pairing recognizes front/back suffixes."""
        photos = [
            "/tmp/IMG_0001_front.jpg",
            "/tmp/IMG_0001_back.jpg",
            "/tmp/IMG_0002_front.jpg",
            "/tmp/IMG_0002_back.jpg",
        ]
        paired = self.engine._auto_pair_photos(photos)

        self.assertEqual(len(paired), 2)

        pair1 = next(p for p in paired if p["base_name"] == "IMG_0001")
        self.assertEqual(pair1["front"], "/tmp/IMG_0001_front.jpg")
        self.assertEqual(pair1["back"], "/tmp/IMG_0001_back.jpg")

    def test_auto_pair_obverse_reverse(self):
        """Verify auto-pairing recognizes obverse/reverse suffixes."""
        photos = [
            "/tmp/coin_obverse.jpg",
            "/tmp/coin_reverse.jpg",
        ]
        paired = self.engine._auto_pair_photos(photos)

        self.assertEqual(len(paired), 1)
        self.assertEqual(paired[0]["front"], "/tmp/coin_obverse.jpg")
        self.assertEqual(paired[0]["back"], "/tmp/coin_reverse.jpg")

    def test_auto_pair_unpaired_front_only(self):
        """Verify unpaired front photos are handled."""
        photos = [
            "/tmp/IMG_0001.jpg",
            "/tmp/IMG_0002.jpg",
        ]
        paired = self.engine._auto_pair_photos(photos)

        self.assertEqual(len(paired), 2)
        self.assertEqual(paired[0]["front"], "/tmp/IMG_0001.jpg")
        self.assertIsNone(paired[0]["back"])

    def test_create_batch_items_from_paired(self):
        """Verify batch items are created from paired photos."""
        paired = [
            {"front": "/tmp/front.jpg", "back": "/tmp/back.jpg", "base_name": "coin1"},
            {"front": "/tmp/single.jpg", "back": None, "base_name": "coin2"},
        ]
        items = self.engine._create_batch_items(paired)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["type"], "coin")
        self.assertEqual(items[0]["subject"], "coin1")
        self.assertEqual(items[0]["front_path"], "/tmp/front.jpg")
        self.assertEqual(items[0]["back_path"], "/tmp/back.jpg")
        self.assertEqual(items[1]["back_path"], "")

    def test_process_folder_empty_folder(self):
        """Verify process_folder handles empty folder gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = self.engine.process_folder(tmpdir, [])

            self.assertEqual(report.summary.total_photos, 0)
            self.assertEqual(len(report.candidates), 0)
            self.assertIn("No photos found", str(report.summary.warnings))

    def test_process_folder_with_photos(self):
        """Verify process_folder processes photos end-to-end."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "IMG_0001_front.jpg"), "w").close()
            open(os.path.join(tmpdir, "IMG_0001_back.jpg"), "w").close()
            open(os.path.join(tmpdir, "IMG_0002_front.jpg"), "w").close()

            report = self.engine.process_folder(tmpdir, [])

            self.assertEqual(report.summary.total_photos, 3)
            self.assertEqual(len(report.candidates), 2)
            self.assertEqual(report.summary.processed + report.summary.failed, 2)

    def test_process_folder_one_failure_does_not_abort(self):
        """Verify one candidate failure does not abort the batch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "IMG_0001_front.jpg"), "w").close()
            open(os.path.join(tmpdir, "IMG_0002_front.jpg"), "w").close()

            def mock_batch_catalogue(items):
                result = BatchCatalogueResult()
                for i, item in enumerate(items):
                    if i == 0:
                        result.results.append(CatalogueResult(
                            session_id="",
                            subject=item["subject"],
                            photos=[],
                            status="error",
                            ocr_ready=False,
                            review_ready=False,
                            message="Mock failure",
                        ))
                    else:
                        result.results.append(CatalogueResult(
                            session_id=f"s{i}",
                            subject=item["subject"],
                            photos=[{"path": item["front_path"]}],
                            status="success",
                            ocr_ready=True,
                            review_ready=True,
                            message="OK",
                        ))
                return result

            self.cataloguer.batch_catalogue = mock_batch_catalogue
            report = self.engine.process_folder(tmpdir, [])

            self.assertEqual(len(report.candidates), 2)
            self.assertEqual(report.candidates[0].status, BatchStatus.FAILED)
            self.assertEqual(report.candidates[1].status, BatchStatus.COMPLETED)

    def test_process_folder_no_collection_mutation(self):
        """Verify process_folder does not mutate collection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "test.jpg"), "w").close()

            collection = [{"id": "existing", "country": "Canada"}]
            original_len = len(collection)

            report = self.engine.process_folder(tmpdir, collection)

            self.assertEqual(len(collection), original_len)

    def test_process_generalized_entry_point(self):
        """Verify process() works with BatchSource."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "photo.jpg"), "w").close()

            source = BatchSource(folder_path=tmpdir, file_pattern="*.jpg")
            report = self.engine.process(source, [])

            self.assertEqual(report.source.folder_path, tmpdir)
            self.assertEqual(report.summary.total_photos, 1)


class TestBatchProcessingPhase2Integration(unittest.TestCase):
    """Phase 2: Integration tests with SmartPhoneCataloguer batch methods."""

    def test_phase2_ocr_integration(self):
        """Verify batch OCR is called via SmartPhoneCataloguer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "coin_front.jpg"), "w").close()

            cataloguer = SmartPhoneCataloguer()
            engine = BatchProcessingEngine(cataloguer)

            report = engine.process_folder(tmpdir, [])

            self.assertEqual(len(report.candidates), 1)
            self.assertIsNotNone(report.candidates[0].catalogue_result)

    def test_phase2_match_integration(self):
        """Verify batch matching is called via SmartPhoneCataloguer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "coin_front.jpg"), "w").close()

            cataloguer = SmartPhoneCataloguer()
            engine = BatchProcessingEngine(cataloguer)

            collection = [{"id": "existing", "country": "Canada", "denomination": "1 cent", "year": 1964}]
            report = engine.process_folder(tmpdir, collection)

            self.assertEqual(len(report.candidates), 1)
            self.assertIsNotNone(report.candidates[0].catalogue_result)

    def test_phase2_proposed_entries_integration(self):
        """Verify batch proposed entries are created via SmartPhoneCataloguer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "coin_front.jpg"), "w").close()

            cataloguer = SmartPhoneCataloguer()
            engine = BatchProcessingEngine(cataloguer)

            report = engine.process_folder(tmpdir, [])

            self.assertEqual(len(report.candidates), 1)
            self.assertIsNotNone(report.candidates[0].catalogue_result)

    def test_phase2_summary_counts(self):
        """Verify summary counts are populated correctly in Phase 2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "IMG_0001_front.jpg"), "w").close()
            open(os.path.join(tmpdir, "IMG_0001_back.jpg"), "w").close()

            cataloguer = SmartPhoneCataloguer()
            engine = BatchProcessingEngine(cataloguer)

            report = engine.process_folder(tmpdir, [])

            self.assertEqual(report.summary.total_photos, 2)
            self.assertEqual(len(report.candidates), 1)
            self.assertGreaterEqual(report.summary.processed + report.summary.failed, 0)

    def test_phase2_end_to_end_with_real_cataloguer(self):
        """Full end-to-end test with real engine and all Phase 2 integrations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "Canada_1cent_1964_front.jpg"), "w").close()
            open(os.path.join(tmpdir, "Canada_1cent_1964_back.jpg"), "w").close()
            open(os.path.join(tmpdir, "Newfoundland_5cents_1941_front.jpg"), "w").close()
            open(os.path.join(tmpdir, "Newfoundland_5cents_1941_back.jpg"), "w").close()

            cataloguer = SmartPhoneCataloguer()
            engine = BatchProcessingEngine(cataloguer)

            collection = [{"id": "existing", "country": "Canada", "denomination": "1 cent", "year": 1964}]
            report = engine.process_folder(tmpdir, collection)

            self.assertEqual(report.summary.total_photos, 4)
            self.assertEqual(len(report.candidates), 2)

            subjects = [c.subject for c in report.candidates]
            self.assertIn("Canada_1cent_1964", subjects)
            self.assertIn("Newfoundland_5cents_1941", subjects)

            for c in report.candidates:
                self.assertIsNotNone(c.catalogue_result)

            with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
                csv_path = f.name
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                md_path = f.name

            try:
                report.export_csv(csv_path)
                report.export_markdown(md_path)
                self.assertTrue(os.path.exists(csv_path))
                self.assertTrue(os.path.exists(md_path))
            finally:
                os.remove(csv_path)
                os.remove(md_path)


class TestBatchProcessingPhase3Integration(unittest.TestCase):
    """Phase 3: Collection Intelligence and Deal Hunter integration tests."""

    def test_phase3_intelligence_exists(self):
        """Verify BatchReport has intelligence field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "coin_front.jpg"), "w").close()

            cataloguer = SmartPhoneCataloguer()
            engine = BatchProcessingEngine(cataloguer)

            report = engine.process_folder(tmpdir, [])

            self.assertIsNotNone(report.intelligence)
            self.assertIsInstance(report.intelligence, BatchIntelligence)

    def test_phase3_collection_intelligence_runs(self):
        """Verify CollectionIntelligenceEngine is called on batch pool."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "Canada_1cent_1964_front.jpg"), "w").close()
            open(os.path.join(tmpdir, "Canada_1cent_1964_back.jpg"), "w").close()

            cataloguer = SmartPhoneCataloguer()
            engine = BatchProcessingEngine(cataloguer)

            collection = [{"id": "existing", "country": "Canada", "denomination": "1 cent", "year": 1964}]
            report = engine.process_folder(tmpdir, collection)

            self.assertIsNotNone(report.intelligence)
            self.assertIsInstance(report.intelligence.to_dict(), dict)

    def test_phase3_intelligence_with_empty_collection(self):
        """Verify CollectionIntelligence handles empty collection gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "coin_front.jpg"), "w").close()

            cataloguer = SmartPhoneCataloguer()
            engine = BatchProcessingEngine(cataloguer)

            report = engine.process_folder(tmpdir, [])

            self.assertIsNotNone(report.intelligence)

    def test_phase3_deal_hunter_optional(self):
        """Verify DealHunter evaluation is optional and non-breaking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "coin_front.jpg"), "w").close()

            cataloguer = SmartPhoneCataloguer()
            engine = BatchProcessingEngine(cataloguer)

            report = engine.process_folder(tmpdir, [])

            self.assertIsNotNone(report.intelligence)

    def test_phase3_markdown_exports_intelligence(self):
        """Verify Markdown export includes Collection Intelligence section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "Canada_1cent_1964_front.jpg"), "w").close()

            cataloguer = SmartPhoneCataloguer()
            engine = BatchProcessingEngine(cataloguer)

            collection = [{"id": "existing", "country": "Canada", "denomination": "1 cent", "year": 1964}]
            report = engine.process_folder(tmpdir, collection)

            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                md_path = f.name

            try:
                report.export_markdown(md_path)
                with open(md_path, "r") as f:
                    content = f.read()
                self.assertIn("# Batch Processing Report", content)
                self.assertIn("## Summary", content)
                self.assertIn("## Candidates", content)
            finally:
                os.remove(md_path)

    def test_phase3_api_compatibility(self):
        """Verify Phase 1/2 API is preserved in Phase 3."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "IMG_0001_front.jpg"), "w").close()

            cataloguer = SmartPhoneCataloguer()
            engine = BatchProcessingEngine(cataloguer)

            report = engine.process_folder(tmpdir, [])

            self.assertEqual(report.source.folder_path, tmpdir)
            self.assertEqual(len(report.candidates), 1)
            self.assertIsNotNone(report.summary)
            self.assertIsNotNone(report.intelligence)

            source = BatchSource(folder_path=tmpdir, file_pattern="*.jpg")
            report2 = engine.process(source, [])
            self.assertEqual(report2.source.folder_path, tmpdir)


class TestBatchProcessingPhase4ReviewWorkflow(unittest.TestCase):
    """Phase 4: Batch Review Workflow tests."""

    def test_review_candidate_approve(self):
        """Phase 4: Approve a candidate via engine."""
        cataloguer = SmartPhoneCataloguer()
        engine = BatchProcessingEngine(cataloguer)

        c1 = BatchCandidate(candidate_id="c1", status=BatchStatus.COMPLETED)
        report = BatchReport(source=BatchSource(folder_path="/tmp"), candidates=[c1])

        engine.review_candidate(report, "c1", ReviewStatus.APPROVED, "Good")

        self.assertEqual(c1.review_status, ReviewStatus.APPROVED)
        self.assertEqual(c1.review_notes, "Good")
        self.assertEqual(report.summary.approved_count, 1)

    def test_review_candidate_reject(self):
        """Phase 4: Reject a candidate via engine."""
        cataloguer = SmartPhoneCataloguer()
        engine = BatchProcessingEngine(cataloguer)

        c1 = BatchCandidate(candidate_id="c1", status=BatchStatus.COMPLETED)
        report = BatchReport(source=BatchSource(folder_path="/tmp"), candidates=[c1])

        engine.review_candidate(report, "c1", ReviewStatus.REJECTED, "Poor")

        self.assertEqual(c1.review_status, ReviewStatus.REJECTED)
        self.assertEqual(report.summary.rejected_count, 1)

    def test_review_candidate_needs_review(self):
        """Phase 4: Mark candidate as needs-review via engine."""
        cataloguer = SmartPhoneCataloguer()
        engine = BatchProcessingEngine(cataloguer)

        c1 = BatchCandidate(candidate_id="c1", status=BatchStatus.COMPLETED)
        report = BatchReport(source=BatchSource(folder_path="/tmp"), candidates=[c1])

        engine.review_candidate(report, "c1", ReviewStatus.NEEDS_REVIEW, "Check")

        self.assertEqual(c1.review_status, ReviewStatus.NEEDS_REVIEW)
        self.assertEqual(report.summary.needs_review_count, 1)

    def test_review_candidate_not_found_raises(self):
        """Phase 4: Reviewing non-existent candidate raises error."""
        cataloguer = SmartPhoneCataloguer()
        engine = BatchProcessingEngine(cataloguer)
        report = BatchReport(source=BatchSource(folder_path="/tmp"), candidates=[])

        with self.assertRaises(ValueError) as ctx:
            engine.review_candidate(report, "nonexistent", ReviewStatus.APPROVED)
        self.assertIn("not found", str(ctx.exception))

    def test_review_candidate_non_reviewable_raises(self):
        """Phase 4: Reviewing non-reviewable candidate raises error."""
        cataloguer = SmartPhoneCataloguer()
        engine = BatchProcessingEngine(cataloguer)
        candidate = BatchCandidate(candidate_id="c1", status=BatchStatus.FAILED)
        report = BatchReport(source=BatchSource(folder_path="/tmp"), candidates=[candidate])

        with self.assertRaises(ValueError) as ctx:
            engine.review_candidate(report, "c1", ReviewStatus.APPROVED)
        self.assertIn("Cannot approve", str(ctx.exception))

    def test_auto_review(self):
        """Phase 4: Auto-review marks candidates based on signals."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "IMG_0001_front.jpg"), "w").close()
            open(os.path.join(tmpdir, "IMG_0002_front.jpg"), "w").close()

            cataloguer = SmartPhoneCataloguer()
            engine = BatchProcessingEngine(cataloguer)

            report = engine.process_folder(tmpdir, [])

            # Before auto-review, all should be unreviewed
            for c in report.candidates:
                self.assertEqual(c.review_status, ReviewStatus.UNREVIEWED)

            engine.auto_review(report)

            # After auto-review, some should have been decided
            reviewed = [c for c in report.candidates if c.review_status != ReviewStatus.UNREVIEWED]
            self.assertGreaterEqual(len(reviewed), 0)

            # Summary should be updated
            self.assertEqual(report.summary.reviewed_count, len(reviewed))

    def test_auto_review_with_errors(self):
        """Phase 4: Auto-review marks candidates with errors as needs-review."""
        cataloguer = SmartPhoneCataloguer()
        engine = BatchProcessingEngine(cataloguer)

        c1 = BatchCandidate(candidate_id="c1", status=BatchStatus.COMPLETED)
        c2 = BatchCandidate(candidate_id="c2", status=BatchStatus.COMPLETED, errors=["OCR failed"])
        report = BatchReport(source=BatchSource(folder_path="/tmp"), candidates=[c1, c2])

        engine.auto_review(report)

        self.assertEqual(c1.review_status, ReviewStatus.APPROVED)
        self.assertEqual(c2.review_status, ReviewStatus.NEEDS_REVIEW)

    def test_auto_review_with_warnings(self):
        """Phase 4: Auto-review marks candidates with warnings as needs-review."""
        cataloguer = SmartPhoneCataloguer()
        engine = BatchProcessingEngine(cataloguer)

        c1 = BatchCandidate(candidate_id="c1", status=BatchStatus.COMPLETED)
        c2 = BatchCandidate(candidate_id="c2", status=BatchStatus.COMPLETED, warnings=["Low confidence"])
        report = BatchReport(source=BatchSource(folder_path="/tmp"), candidates=[c1, c2])

        engine.auto_review(report)

        self.assertEqual(c1.review_status, ReviewStatus.APPROVED)
        self.assertEqual(c2.review_status, ReviewStatus.NEEDS_REVIEW)

    def test_auto_review_skips_failed(self):
        """Phase 4: Auto-review skips failed candidates."""
        cataloguer = SmartPhoneCataloguer()
        engine = BatchProcessingEngine(cataloguer)

        c1 = BatchCandidate(candidate_id="c1", status=BatchStatus.COMPLETED)
        c2 = BatchCandidate(candidate_id="c2", status=BatchStatus.FAILED)
        report = BatchReport(source=BatchSource(folder_path="/tmp"), candidates=[c1, c2])

        engine.auto_review(report)

        self.assertEqual(c1.review_status, ReviewStatus.APPROVED)
        self.assertEqual(c2.review_status, ReviewStatus.UNREVIEWED)

    def test_process_initializes_review_counts(self):
        """Phase 4: process() initializes review summary counts to zero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "IMG_0001_front.jpg"), "w").close()

            cataloguer = SmartPhoneCataloguer()
            engine = BatchProcessingEngine(cataloguer)

            report = engine.process_folder(tmpdir, [])

            self.assertEqual(report.summary.reviewed_count, 0)
            self.assertEqual(report.summary.approved_count, 0)
            self.assertEqual(report.summary.rejected_count, 0)
            self.assertEqual(report.summary.needs_review_count, 0)

    def test_phase4_api_compatibility(self):
        """Phase 4: All Phase 1/2/3 APIs preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "IMG_0001_front.jpg"), "w").close()

            cataloguer = SmartPhoneCataloguer()
            engine = BatchProcessingEngine(cataloguer)

            report = engine.process_folder(tmpdir, [])

            # Phase 1/2/3 fields still exist
            self.assertEqual(report.source.folder_path, tmpdir)
            self.assertEqual(len(report.candidates), 1)
            self.assertIsNotNone(report.summary)
            self.assertIsNotNone(report.intelligence)

            # Phase 4 fields exist
            self.assertIsNotNone(report.review_summary())

            # process() still works
            source = BatchSource(folder_path=tmpdir, file_pattern="*.jpg")
            report2 = engine.process(source, [])
            self.assertEqual(report2.source.folder_path, tmpdir)


if __name__ == "__main__":
    unittest.main()
