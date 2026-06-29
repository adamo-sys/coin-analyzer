"""Unit tests for AI Grading Assistant — v8.2 Phase 3 Collection Intelligence Integration."""

import unittest
from unittest.mock import Mock
import tempfile
import os

from ai_grading_assistant import (
    AIGradingAssistant,
    GradingCandidate,
    GradePattern,
    GradingAssessment,
    BatchGradingReport,
)
from collection_intelligence import CollectionIntelligenceEngine


class MockItem:
    def __init__(self, country, denomination, year, grade, series=None, quantity=1, reference="", numista_n=""):
        self.country = country
        self.denomination = denomination
        self.year = year
        self.grade = grade
        self.series = series
        self.quantity = quantity
        self.reference = reference
        self.numista_n = numista_n


# ---------------------------------------------------------------------------
# Phase 1 & 2 regression tests (preserved)
# ---------------------------------------------------------------------------

class TestGradingCandidate(unittest.TestCase):
    def test_to_dict(self):
        c = GradingCandidate(country="Canada", denomination="5 cents", year="1943", claimed_grade="VF-20")
        d = c.to_dict()
        self.assertEqual(d["country"], "Canada")
        self.assertEqual(d["claimed_grade"], "VF-20")

    def test_defaults(self):
        c = GradingCandidate(country="Canada", denomination="5 cents")
        self.assertIsNone(c.year)
        self.assertEqual(c.photo_references, [])


class TestGradePattern(unittest.TestCase):
    def test_to_dict(self):
        p = GradePattern(country="Canada", denomination="5 cents", total_items=5, median_grade="VF-20")
        d = p.to_dict()
        self.assertEqual(d["median_grade"], "VF-20")


class TestAIGradingAssistantPatterns(unittest.TestCase):
    def test_empty_engine_no_pattern(self):
        engine = CollectionIntelligenceEngine([])
        assistant = AIGradingAssistant(engine)
        pattern = assistant._get_pattern("Canada", "5 cents")
        self.assertIsNone(pattern)

    def test_pattern_computed_from_engine(self):
        items = [
            MockItem("Canada", "5 cents", "1940", "VG-8"),
            MockItem("Canada", "5 cents", "1941", "VF-20"),
            MockItem("Canada", "5 cents", "1942", "VF-20"),
            MockItem("Canada", "5 cents", "1943", "EF-40"),
            MockItem("Canada", "5 cents", "1944", "EF-40"),
        ]
        engine = CollectionIntelligenceEngine(items)
        assistant = AIGradingAssistant(engine)
        pattern = assistant._get_pattern("Canada", "5 cents")
        self.assertIsNotNone(pattern)
        self.assertEqual(pattern.total_items, 5)
        self.assertEqual(pattern.median_grade, "VF-20")

    def test_caching(self):
        items = [MockItem("Canada", "5 cents", "1940", "VF-20")]
        engine = CollectionIntelligenceEngine(items)
        assistant = AIGradingAssistant(engine)
        p1 = assistant._get_pattern("Canada", "5 cents")
        p2 = assistant._get_pattern("Canada", "5 cents")
        self.assertIs(p1, p2)


class TestAIGradingAssistantAssessment(unittest.TestCase):
    def setUp(self):
        items = [
            MockItem("Canada", "5 cents", "1940", "VG-8"),
            MockItem("Canada", "5 cents", "1941", "VF-20"),
            MockItem("Canada", "5 cents", "1942", "VF-20"),
            MockItem("Canada", "5 cents", "1943", "EF-40"),
            MockItem("Canada", "5 cents", "1944", "EF-40"),
        ]
        self.engine = CollectionIntelligenceEngine(items)
        self.assistant = AIGradingAssistant(self.engine)

    def test_claimed_grade_matches_median_proceed(self):
        c = GradingCandidate(country="Canada", denomination="5 cents", claimed_grade="VF-20")
        a = self.assistant.assess_candidate(c)
        self.assertEqual(a.recommendation, "PROCEED")

    def test_claimed_grade_different_caution(self):
        c = GradingCandidate(country="Canada", denomination="5 cents", claimed_grade="EF-40")
        a = self.assistant.assess_candidate(c)
        self.assertEqual(a.recommendation, "CAUTION")

    def test_claimed_grade_below_range_review(self):
        c = GradingCandidate(country="Canada", denomination="5 cents", claimed_grade="PO-1")
        a = self.assistant.assess_candidate(c)
        self.assertEqual(a.recommendation, "REVIEW")
        self.assertTrue(any("below typical collection range" in f for f in a.review_flags))

    def test_no_collection_data_review(self):
        engine = CollectionIntelligenceEngine([])
        assistant = AIGradingAssistant(engine)
        c = GradingCandidate(country="Canada", denomination="25 cents", claimed_grade="VF-20")
        a = assistant.assess_candidate(c)
        self.assertEqual(a.recommendation, "REVIEW")

    def test_batch_assessment(self):
        candidates = [
            GradingCandidate("Canada", "5 cents", claimed_grade="VF-20"),
            GradingCandidate("Canada", "5 cents", claimed_grade="PO-1"),
        ]
        report = self.assistant.assess_batch(candidates)
        self.assertEqual(len(report.assessments), 2)
        d = report.to_dict()
        self.assertEqual(d["summary"]["total"], 2)


# ---------------------------------------------------------------------------
# Phase 2 integration tests (preserved)
# ---------------------------------------------------------------------------

class TestGradingCandidateFromOCR(unittest.TestCase):
    def test_from_ocr_candidate_basic(self):
        ocr = Mock()
        ocr.country = "Canada"
        ocr.denomination = "5 cents"
        ocr.year = "1943"
        ocr.series_type = ""
        ocr.possible_variety_keywords = ["Double HP"]
        ocr.image_path = "/photos/img.jpg"
        ocr.title = "Canada 1943 5 cents"
        ocr.to_dict = Mock(return_value={"country": "Canada"})

        gc = GradingCandidate.from_ocr_candidate(ocr)
        self.assertEqual(gc.country, "Canada")
        self.assertEqual(gc.photo_references, ["/photos/img.jpg"])
        self.assertIsNotNone(gc.ocr_evidence)

    def test_from_ocr_candidate_empty(self):
        ocr = Mock()
        ocr.country = ""
        ocr.denomination = ""
        ocr.year = ""
        ocr.series_type = ""
        ocr.possible_variety_keywords = []
        ocr.image_path = ""
        ocr.title = ""
        ocr.to_dict = Mock(return_value={})

        gc = GradingCandidate.from_ocr_candidate(ocr)
        self.assertEqual(gc.country, "")
        self.assertEqual(gc.photo_references, [])


class TestGradingCandidateFromCapturedPhoto(unittest.TestCase):
    def test_from_photo_with_ocr(self):
        photo = Mock()
        photo.file_path = "/photos/front.jpg"
        photo.notes = "Found at show"

        ocr_candidate = Mock()
        ocr_candidate.country = "Canada"
        ocr_candidate.denomination = "25 cents"
        ocr_candidate.year = "1967"
        ocr_candidate.series_type = ""
        ocr_candidate.to_dict = Mock(return_value={"country": "Canada"})

        ocr_report = Mock()
        ocr_report.candidates = [ocr_candidate]

        gc = GradingCandidate.from_captured_photo(photo, ocr_report)
        self.assertEqual(gc.country, "Canada")
        self.assertEqual(gc.photo_references, ["/photos/front.jpg"])

    def test_from_photo_without_ocr(self):
        photo = Mock()
        photo.file_path = "/photos/front.jpg"
        photo.notes = ""

        gc = GradingCandidate.from_captured_photo(photo)
        self.assertEqual(gc.country, "")
        self.assertEqual(gc.photo_references, ["/photos/front.jpg"])


class TestGradingCandidateFromBatchCandidate(unittest.TestCase):
    def test_from_batch_with_ocr_and_proposed(self):
        ocr_candidate = Mock()
        ocr_candidate.country = "Canada"
        ocr_candidate.denomination = "5 cents"
        ocr_candidate.year = "1943"
        ocr_candidate.series_type = ""
        ocr_candidate.to_dict = Mock(return_value={"country": "Canada"})

        ocr_report = Mock()
        ocr_report.candidates = [ocr_candidate]

        proposed = Mock()
        proposed.grade = "VF-20"

        batch = Mock()
        batch.front_path = "/photos/front.jpg"
        batch.back_path = "/photos/back.jpg"
        batch.ocr_result = ocr_report
        batch.proposed_entry = proposed
        batch.subject = "Canada 5c 1943"

        gc = GradingCandidate.from_batch_candidate(batch)
        self.assertEqual(gc.country, "Canada")
        self.assertEqual(gc.claimed_grade, "VF-20")
        self.assertEqual(gc.photo_references, ["/photos/front.jpg", "/photos/back.jpg"])

    def test_from_batch_minimal(self):
        batch = Mock()
        batch.front_path = None
        batch.back_path = None
        batch.ocr_result = None
        batch.proposed_entry = None
        batch.subject = ""

        gc = GradingCandidate.from_batch_candidate(batch)
        self.assertEqual(gc.country, "")
        self.assertEqual(gc.photo_references, [])
        self.assertIsNone(gc.claimed_grade)


class TestIntegrationEndToEnd(unittest.TestCase):
    def test_ocr_to_assessment(self):
        items = [
            MockItem("Canada", "5 cents", "1940", "VG-8"),
            MockItem("Canada", "5 cents", "1941", "VF-20"),
            MockItem("Canada", "5 cents", "1942", "VF-20"),
            MockItem("Canada", "5 cents", "1943", "EF-40"),
            MockItem("Canada", "5 cents", "1944", "EF-40"),
        ]
        engine = CollectionIntelligenceEngine(items)
        assistant = AIGradingAssistant(engine)

        ocr = Mock()
        ocr.country = "Canada"
        ocr.denomination = "5 cents"
        ocr.year = "1945"
        ocr.series_type = ""
        ocr.possible_variety_keywords = []
        ocr.image_path = "/photos/1945.jpg"
        ocr.title = "Canada 1945 5 cents"
        ocr.to_dict = Mock(return_value={"country": "Canada", "denomination": "5 cents"})

        candidate = GradingCandidate.from_ocr_candidate(ocr)
        assessment = assistant.assess_candidate(candidate)

        self.assertEqual(assessment.candidate.country, "Canada")
        self.assertIsNotNone(assessment.most_likely_grade)
        self.assertIn(assessment.recommendation, ["PROCEED", "CAUTION", "REVIEW"])
        self.assertIn("OCR identification evidence available", assessment.evidence)

    def test_batch_candidate_pipeline(self):
        items = [
            MockItem("Canada", "5 cents", "1940", "VG-8"),
            MockItem("Canada", "5 cents", "1941", "VF-20"),
            MockItem("Canada", "5 cents", "1942", "VF-20"),
            MockItem("Canada", "5 cents", "1943", "EF-40"),
            MockItem("Canada", "5 cents", "1944", "EF-40"),
        ]
        engine = CollectionIntelligenceEngine(items)
        assistant = AIGradingAssistant(engine)

        ocr_candidate = Mock()
        ocr_candidate.country = "Canada"
        ocr_candidate.denomination = "5 cents"
        ocr_candidate.year = "1945"
        ocr_candidate.series_type = ""
        ocr_candidate.to_dict = Mock(return_value={"country": "Canada"})

        ocr_report = Mock()
        ocr_report.candidates = [ocr_candidate]

        proposed = Mock()
        proposed.grade = "VF-20"

        batch = Mock()
        batch.front_path = "/photos/1945_front.jpg"
        batch.back_path = "/photos/1945_back.jpg"
        batch.ocr_result = ocr_report
        batch.proposed_entry = proposed
        batch.subject = "Canada 5c 1945"

        candidate = GradingCandidate.from_batch_candidate(batch)
        assessment = assistant.assess_candidate(candidate)

        self.assertEqual(assessment.recommendation, "PROCEED")
        self.assertEqual(assessment.candidate.claimed_grade, "VF-20")


# ---------------------------------------------------------------------------
# Phase 3: Collection Intelligence Integration tests
# ---------------------------------------------------------------------------

class TestCollectionContext(unittest.TestCase):
    """Verify collection_context is populated from existing engine methods."""

    def test_collection_count_in_context(self):
        items = [
            MockItem("Canada", "5 cents", "1940", "VG-8"),
            MockItem("Canada", "5 cents", "1941", "VF-20"),
            MockItem("Canada", "5 cents", "1942", "VF-20"),
            MockItem("Canada", "5 cents", "1943", "EF-40"),
            MockItem("Canada", "5 cents", "1944", "EF-40"),
        ]
        engine = CollectionIntelligenceEngine(items)
        assistant = AIGradingAssistant(engine)

        c = GradingCandidate(country="Canada", denomination="5 cents", claimed_grade="VF-20")
        a = assistant.assess_candidate(c)

        self.assertIn("collection_count_for_country", a.collection_context)
        self.assertEqual(a.collection_context["collection_count_for_country"], 5)
        self.assertIn("denominations_in_country", a.collection_context)

    def test_duplicate_risk_flagged(self):
        items = [
            MockItem("Canada", "5 cents", "1943", "VG-8", reference="KM-1", numista_n="12345"),
            MockItem("Canada", "5 cents", "1943", "VF-20", reference="KM-1", numista_n="12345"),
        ]
        engine = CollectionIntelligenceEngine(items)
        assistant = AIGradingAssistant(engine)

        c = GradingCandidate(country="Canada", denomination="5 cents", year="1943", claimed_grade="EF-40")
        a = assistant.assess_candidate(c)

        self.assertTrue(any("Duplicate risk" in f for f in a.review_flags))
        # Base recommendation is REVIEW because EF-40 is above typical range for VG-8/VF-20 collection
        self.assertEqual(a.recommendation, "REVIEW")

    def test_no_duplicate_risk_for_new_year(self):
        items = [
            MockItem("Canada", "5 cents", "1940", "VG-8"),
            MockItem("Canada", "5 cents", "1941", "VF-20"),
        ]
        engine = CollectionIntelligenceEngine(items)
        assistant = AIGradingAssistant(engine)

        c = GradingCandidate(country="Canada", denomination="5 cents", year="1943", claimed_grade="VF-20")
        a = assistant.assess_candidate(c)

        self.assertFalse(any("Duplicate risk" in f for f in a.review_flags))

    def test_upgrade_opportunity_in_evidence(self):
        items = [
            MockItem("Canada", "5 cents", "1943", "VG-8", reference="KM-1", numista_n="12345"),
            MockItem("Canada", "5 cents", "1943", "VF-20", reference="KM-1", numista_n="12345"),
        ]
        engine = CollectionIntelligenceEngine(items)
        assistant = AIGradingAssistant(engine)

        c = GradingCandidate(country="Canada", denomination="5 cents", year="1943", claimed_grade="EF-40")
        a = assistant.assess_candidate(c)

        self.assertTrue(any("Upgrade opportunity" in e for e in a.evidence))
        self.assertIn("upgrade_opportunities", a.collection_context)

    def test_collection_context_in_to_dict(self):
        items = [MockItem("Canada", "5 cents", "1940", "VG-8")]
        engine = CollectionIntelligenceEngine(items)
        assistant = AIGradingAssistant(engine)

        c = GradingCandidate(country="Canada", denomination="5 cents", claimed_grade="VF-20")
        a = assistant.assess_candidate(c)
        d = a.to_dict()

        self.assertIn("collection_context", d)
        self.assertIsInstance(d["collection_context"], dict)

    def test_series_context_when_series_provided(self):
        items = [
            MockItem("Canada", "5 cents", "1940", "VG-8", series="George VI"),
            MockItem("Canada", "5 cents", "1941", "VF-20", series="George VI"),
        ]
        engine = CollectionIntelligenceEngine(items)
        assistant = AIGradingAssistant(engine)

        c = GradingCandidate(country="Canada", denomination="5 cents", series="George VI", claimed_grade="VF-20")
        a = assistant.assess_candidate(c)

        # analyze_by_series groups by (country, denomination), not by series name
        # series_items is available but counts all items for that country/denomination
        self.assertIn("series_items", a.collection_context)
        self.assertEqual(a.collection_context["series_items"], 2)

    def test_batch_with_collection_context(self):
        items = [
            MockItem("Canada", "5 cents", "1943", "VG-8", reference="KM-1", numista_n="12345"),
            MockItem("Canada", "5 cents", "1943", "VF-20", reference="KM-1", numista_n="12345"),
        ]
        engine = CollectionIntelligenceEngine(items)
        assistant = AIGradingAssistant(engine)

        candidates = [
            GradingCandidate("Canada", "5 cents", year="1943", claimed_grade="EF-40"),
            GradingCandidate("Canada", "5 cents", year="1944", claimed_grade="VF-20"),
        ]
        report = assistant.assess_batch(candidates)

        # First candidate has duplicate risk
        a1 = report.assessments[0]
        self.assertTrue(any("Duplicate risk" in f for f in a1.review_flags))

        # Second candidate does not
        a2 = report.assessments[1]
        self.assertFalse(any("Duplicate risk" in f for f in a2.review_flags))




# ---------------------------------------------------------------------------
# Phase 4: Export tests
# ---------------------------------------------------------------------------

class TestExportAssessment(unittest.TestCase):
    """Verify single assessment export to Markdown and CSV."""

    def setUp(self):
        items = [
            MockItem("Canada", "5 cents", "1940", "VG-8"),
            MockItem("Canada", "5 cents", "1941", "VF-20"),
            MockItem("Canada", "5 cents", "1942", "VF-20"),
            MockItem("Canada", "5 cents", "1943", "EF-40"),
            MockItem("Canada", "5 cents", "1944", "EF-40"),
        ]
        self.engine = CollectionIntelligenceEngine(items)
        self.assistant = AIGradingAssistant(self.engine)

    def test_export_markdown_creates_file(self):
        c = GradingCandidate(country="Canada", denomination="5 cents", claimed_grade="VF-20")
        a = self.assistant.assess_candidate(c)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            path = f.name
        try:
            result = self.assistant.export_assessment(a, "markdown", path)
            self.assertTrue(result)
            with open(path, 'r') as f:
                content = f.read()
            self.assertIn("Canada", content)
            self.assertIn("VF-20", content)
            self.assertIn("PROCEED", content)
        finally:
            os.unlink(path)

    def test_export_csv_creates_file(self):
        c = GradingCandidate(country="Canada", denomination="5 cents", claimed_grade="VF-20")
        a = self.assistant.assess_candidate(c)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            path = f.name
        try:
            result = self.assistant.export_assessment(a, "csv", path)
            self.assertTrue(result)
            with open(path, 'r') as f:
                content = f.read()
            self.assertIn("Canada", content)
            self.assertIn("VF-20", content)
            self.assertIn("PROCEED", content)
        finally:
            os.unlink(path)

    def test_export_invalid_format_returns_false(self):
        c = GradingCandidate(country="Canada", denomination="5 cents", claimed_grade="VF-20")
        a = self.assistant.assess_candidate(c)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            path = f.name
        try:
            result = self.assistant.export_assessment(a, "json", path)
            self.assertFalse(result)
        finally:
            os.unlink(path)


class TestExportReport(unittest.TestCase):
    """Verify batch report export to Markdown and CSV."""

    def setUp(self):
        items = [
            MockItem("Canada", "5 cents", "1940", "VG-8"),
            MockItem("Canada", "5 cents", "1941", "VF-20"),
            MockItem("Canada", "5 cents", "1942", "VF-20"),
            MockItem("Canada", "5 cents", "1943", "EF-40"),
            MockItem("Canada", "5 cents", "1944", "EF-40"),
        ]
        self.engine = CollectionIntelligenceEngine(items)
        self.assistant = AIGradingAssistant(self.engine)

    def test_export_report_markdown(self):
        candidates = [
            GradingCandidate("Canada", "5 cents", claimed_grade="VF-20"),
            GradingCandidate("Canada", "5 cents", claimed_grade="PO-1"),
        ]
        report = self.assistant.assess_batch(candidates)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            path = f.name
        try:
            result = self.assistant.export_report(report, "markdown", path)
            self.assertTrue(result)
            with open(path, 'r') as f:
                content = f.read()
            self.assertIn("AI Grading Assessment Report", content)
            self.assertIn("PROCEED", content)
            self.assertIn("REVIEW", content)
            self.assertIn("Summary", content)
        finally:
            os.unlink(path)

    def test_export_report_csv(self):
        candidates = [
            GradingCandidate("Canada", "5 cents", claimed_grade="VF-20"),
            GradingCandidate("Canada", "5 cents", claimed_grade="PO-1"),
        ]
        report = self.assistant.assess_batch(candidates)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            path = f.name
        try:
            result = self.assistant.export_report(report, "csv", path)
            self.assertTrue(result)
            with open(path, 'r') as f:
                content = f.read()
            self.assertIn("Canada", content)
            self.assertIn("VF-20", content)
            self.assertIn("PROCEED", content)
            self.assertIn("REVIEW", content)
        finally:
            os.unlink(path)

    def test_export_report_invalid_format(self):
        candidates = [GradingCandidate("Canada", "5 cents", claimed_grade="VF-20")]
        report = self.assistant.assess_batch(candidates)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            path = f.name
        try:
            result = self.assistant.export_report(report, "json", path)
            self.assertFalse(result)
        finally:
            os.unlink(path)

if __name__ == "__main__":
    unittest.main()
