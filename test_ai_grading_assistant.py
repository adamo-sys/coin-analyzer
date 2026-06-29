"""Unit tests for AI Grading Assistant — v8.2 Phase 1."""

import unittest

from ai_grading_assistant import (
    AIGradingAssistant,
    GradingCandidate,
    GradePattern,
    GradingAssessment,
    BatchGradingReport,
)
from collection_intelligence import CollectionIntelligenceEngine


class MockItem:
    def __init__(self, country, denomination, year, grade, series=None):
        self.country = country
        self.denomination = denomination
        self.year = year
        self.grade = grade
        self.series = series


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
        self.assertEqual(d["total_items"], 5)


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
        self.assertIn("VF-20", pattern.grade_counts)
        self.assertIn("EF-40", pattern.grade_counts)

    def test_series_filtering(self):
        items = [
            MockItem("Canada", "5 cents", "1940", "VG-8", "George VI"),
            MockItem("Canada", "5 cents", "1941", "VF-20", "George VI"),
            MockItem("Canada", "5 cents", "1942", "EF-40", "Elizabeth II"),
        ]
        engine = CollectionIntelligenceEngine(items)
        assistant = AIGradingAssistant(engine)
        p_george = assistant._get_pattern("Canada", "5 cents", "George VI")
        p_all = assistant._get_pattern("Canada", "5 cents")
        self.assertEqual(p_george.total_items, 2)
        self.assertEqual(p_all.total_items, 3)

    def test_ungraded_items_excluded_from_counts(self):
        items = [
            MockItem("Canada", "5 cents", "1940", ""),
            MockItem("Canada", "5 cents", "1941", "VF-20"),
            MockItem("Canada", "5 cents", "1942", "VF-20"),
        ]
        engine = CollectionIntelligenceEngine(items)
        assistant = AIGradingAssistant(engine)
        pattern = assistant._get_pattern("Canada", "5 cents")
        self.assertEqual(pattern.total_items, 3)
        self.assertNotIn("", pattern.grade_counts)

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

    def test_assess_with_pattern(self):
        c = GradingCandidate(country="Canada", denomination="5 cents", claimed_grade="VF-20")
        a = self.assistant.assess_candidate(c)
        self.assertIsNotNone(a.collection_pattern if hasattr(a, "collection_pattern") else True)
        self.assertIsNotNone(a.most_likely_grade)
        self.assertIn(a.recommendation, ["PROCEED", "CAUTION", "REVIEW"])

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

    def test_claimed_grade_above_range_review(self):
        c = GradingCandidate(country="Canada", denomination="5 cents", claimed_grade="MS-65")
        a = self.assistant.assess_candidate(c)
        self.assertEqual(a.recommendation, "REVIEW")
        self.assertTrue(any("above typical collection range" in f for f in a.review_flags))

    def test_no_collection_data_review(self):
        engine = CollectionIntelligenceEngine([])
        assistant = AIGradingAssistant(engine)
        c = GradingCandidate(country="Canada", denomination="25 cents", claimed_grade="VF-20")
        a = assistant.assess_candidate(c)
        self.assertEqual(a.recommendation, "REVIEW")
        self.assertTrue(any("No collection pattern available" in f for f in a.review_flags))

    def test_evidence_includes_claimed_grade(self):
        c = GradingCandidate(country="Canada", denomination="5 cents", claimed_grade="VF-20", photo_references=["img.jpg"])
        a = self.assistant.assess_candidate(c)
        self.assertIn("Claimed grade: VF-20", a.evidence)
        self.assertIn("1 photo reference(s)", a.evidence)

    def test_ocr_evidence_in_summary(self):
        c = GradingCandidate(country="Canada", denomination="5 cents", ocr_evidence={"country": "Canada"})
        a = self.assistant.assess_candidate(c)
        self.assertIn("OCR identification evidence available", a.evidence)


class TestBatchAssessment(unittest.TestCase):
    def setUp(self):
        items = [
            MockItem("Canada", "5 cents", "1940", "VG-8"),
            MockItem("Canada", "5 cents", "1941", "VF-20"),
            MockItem("Canada", "5 cents", "1942", "EF-40"),
        ]
        self.engine = CollectionIntelligenceEngine(items)
        self.assistant = AIGradingAssistant(self.engine)

    def test_batch_returns_report(self):
        candidates = [
            GradingCandidate("Canada", "5 cents", claimed_grade="VF-20"),
            GradingCandidate("Canada", "5 cents", claimed_grade="PO-1"),
        ]
        report = self.assistant.assess_batch(candidates)
        self.assertEqual(len(report.assessments), 2)
        d = report.to_dict()
        self.assertEqual(d["summary"]["total"], 2)

    def test_by_recommendation(self):
        candidates = [
            GradingCandidate("Canada", "5 cents", claimed_grade="VF-20"),
            GradingCandidate("Canada", "5 cents", claimed_grade="PO-1"),
        ]
        report = self.assistant.assess_batch(candidates)
        review = report.by_recommendation("REVIEW")
        self.assertEqual(len(review), 1)


class TestAssessmentSerialization(unittest.TestCase):
    def test_to_dict(self):
        c = GradingCandidate("Canada", "5 cents", year="1943")
        a = GradingAssessment(candidate=c, estimated_range=("VF-20", "EF-40"), most_likely_grade="VF-20", recommendation="CAUTION")
        d = a.to_dict()
        self.assertEqual(d["candidate"]["country"], "Canada")
        self.assertEqual(d["recommendation"], "CAUTION")


if __name__ == "__main__":
    unittest.main()
