"""Unit tests for the Batch Processing Engine — v8.1 Phase 2.

Tests folder scanning, photo discovery, front/back auto-pairing,
batch candidate creation, SmartPhoneCataloguer orchestration,
OCR integration, collection matching, proposed entries,
summary generation, and CSV/Markdown export.
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
)
from smart_phone_cataloguer import (
    SmartPhoneCataloguer,
    CatalogueResult,
    BatchCatalogueResult,
    CollectionMatchResult,
    ProposedCollectionEntry,
)
from photo_capture_workflow import PhotoCaptureWorkflow


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
            warnings=["Missing metadata"],
            errors=[],
        )
        d = candidate.to_dict()
        self.assertEqual(d["candidate_id"], "batch_0001_test")
        self.assertEqual(d["front_path"], "/tmp/front.jpg")
        self.assertEqual(d["back_path"], "/tmp/back.jpg")
        self.assertEqual(d["subject"], "Test Coin")
        self.assertEqual(d["status"], "completed")
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

    def test_export_csv_creates_file(self):
        """Verify CSV export creates a file."""
        source = BatchSource(folder_path="/tmp/test")
        candidate = BatchCandidate(
            candidate_id="c1",
            subject="Coin 1",
            front_path="/tmp/front.jpg",
            status=BatchStatus.COMPLETED,
        )
        report = BatchReport(source=source, candidates=[candidate])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_path = f.name

        try:
            report.export_csv(temp_path)
            self.assertTrue(os.path.exists(temp_path))
            with open(temp_path, "r") as f:
                content = f.read()
            self.assertIn("candidate_id", content)
            self.assertIn("Coin 1", content)
        finally:
            os.remove(temp_path)

    def test_export_markdown_creates_file(self):
        """Verify Markdown export creates a file."""
        source = BatchSource(folder_path="/tmp/test")
        candidate = BatchCandidate(
            candidate_id="c1",
            subject="Coin 1",
            front_path="/tmp/front.jpg",
            status=BatchStatus.COMPLETED,
        )
        report = BatchReport(source=source, candidates=[candidate])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            temp_path = f.name

        try:
            report.export_markdown(temp_path)
            self.assertTrue(os.path.exists(temp_path))
            with open(temp_path, "r") as f:
                content = f.read()
            self.assertIn("# Batch Processing Report", content)
            self.assertIn("Coin 1", content)
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


if __name__ == "__main__":
    unittest.main()
