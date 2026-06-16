"""Unit tests for collection intelligence refinement utilities (v0.8)."""

import unittest
from collection_intelligence_refined import (
    normalize_grade,
    grade_score,
    format_score_breakdown,
    safe_str,
    safe_int,
    safe_float,
    normalize_country,
    normalize_denomination,
    normalize_year,
    is_blank,
    format_priority_reasons,
    get_grade_improvement,
    is_upgrade,
)


class TestGradeNormalization(unittest.TestCase):
    """Test grade normalization utilities."""

    def test_normalize_grade_basic(self):
        """Test basic grade normalization."""
        self.assertEqual(normalize_grade("VF-20"), "VF-20")
        self.assertEqual(normalize_grade("vf-20"), "VF-20")
        self.assertEqual(normalize_grade("  vf-20  "), "VF-20")
        self.assertEqual(normalize_grade(""), "")
        self.assertEqual(normalize_grade(None), "")

    def test_grade_score(self):
        """Test grade score calculation."""
        self.assertEqual(grade_score("VF-20"), 7)
        self.assertEqual(grade_score("MS-65"), 20)
        self.assertEqual(grade_score("PO-1"), 1)
        self.assertEqual(grade_score("MS-70"), 25)
        self.assertEqual(grade_score("invalid"), 0)
        self.assertEqual(grade_score(""), 0)
        self.assertEqual(grade_score(None), 0)

    def test_get_grade_improvement(self):
        """Test grade improvement calculation."""
        self.assertEqual(get_grade_improvement("VF-20", "EF-40"), 2)
        self.assertEqual(get_grade_improvement("VF-20", "VF-30"), 1)
        self.assertEqual(get_grade_improvement("EF-40", "VF-20"), -2)
        self.assertEqual(get_grade_improvement("VF-20", "VF-20"), 0)
        self.assertEqual(get_grade_improvement("", "VF-20"), 7)
        self.assertEqual(get_grade_improvement("VF-20", ""), -7)

    def test_is_upgrade(self):
        """Test upgrade detection."""
        self.assertTrue(is_upgrade("VF-20", "EF-40"))
        self.assertTrue(is_upgrade("VF-20", "VF-30"))
        self.assertFalse(is_upgrade("EF-40", "VF-20"))
        self.assertFalse(is_upgrade("VF-20", "VF-20"))
        self.assertTrue(is_upgrade("", "VF-20"))
        self.assertFalse(is_upgrade("VF-20", ""))


class TestScoreBreakdown(unittest.TestCase):
    """Test score breakdown formatting."""

    def test_format_score_breakdown_basic(self):
        """Test basic score breakdown formatting."""
        result = format_score_breakdown(100, [("Base", 50), ("Bonus", 50)])
        self.assertIn("Score: 100", result)
        self.assertIn("Base: +50", result)
        self.assertIn("Bonus: +50", result)

    def test_format_score_breakdown_negative(self):
        """Test score breakdown with negative components."""
        result = format_score_breakdown(40, [("Base", 50), ("Penalty", -10)])
        self.assertIn("Score: 40", result)
        self.assertIn("Base: +50", result)
        self.assertIn("Penalty: -10", result)

    def test_format_score_breakdown_empty(self):
        """Test score breakdown with no components."""
        result = format_score_breakdown(100, [])
        self.assertEqual(result, "Score: 100")


class TestMissingBlankDataHandling(unittest.TestCase):
    """Test missing/blank data handling utilities."""

    def test_safe_str(self):
        """Test safe string conversion."""
        self.assertEqual(safe_str("test"), "test")
        self.assertEqual(safe_str("  test  "), "test")
        self.assertEqual(safe_str(""), "")
        self.assertEqual(safe_str(None), "")
        self.assertEqual(safe_str(123), "123")
        self.assertEqual(safe_str(0), "0")

    def test_safe_int(self):
        """Test safe integer conversion."""
        self.assertEqual(safe_int("123"), 123)
        self.assertEqual(safe_int("  123  "), 123)
        self.assertEqual(safe_int("invalid"), 0)
        self.assertEqual(safe_int(""), 0)
        self.assertEqual(safe_int(None), 0)
        self.assertEqual(safe_int("invalid", 5), 5)

    def test_safe_float(self):
        """Test safe float conversion."""
        self.assertEqual(safe_float("123.45"), 123.45)
        self.assertEqual(safe_float("  123.45  "), 123.45)
        self.assertEqual(safe_float("invalid"), 0.0)
        self.assertEqual(safe_float(""), 0.0)
        self.assertEqual(safe_float(None), 0.0)
        self.assertEqual(safe_float("invalid", 5.5), 5.5)

    def test_is_blank(self):
        """Test blank detection."""
        self.assertTrue(is_blank(None))
        self.assertTrue(is_blank(""))
        self.assertTrue(is_blank("  "))
        self.assertFalse(is_blank("test"))
        self.assertFalse(is_blank("  test  "))


class TestStringNormalization(unittest.TestCase):
    """Test string normalization utilities."""

    def test_normalize_country(self):
        """Test country normalization."""
        self.assertEqual(normalize_country("Canada"), "canada")
        self.assertEqual(normalize_country("  Canada  "), "canada")
        self.assertEqual(normalize_country(""), "")
        self.assertEqual(normalize_country(None), "")

    def test_normalize_denomination(self):
        """Test denomination normalization."""
        self.assertEqual(normalize_denomination("Dime"), "dime")
        self.assertEqual(normalize_denomination("  Dime  "), "dime")
        self.assertEqual(normalize_denomination(""), "")
        self.assertEqual(normalize_denomination(None), "")

    def test_normalize_year(self):
        """Test year normalization."""
        self.assertEqual(normalize_year("1935"), "1935")
        self.assertEqual(normalize_year("  1935  "), "1935")
        self.assertEqual(normalize_year(""), "")
        self.assertEqual(normalize_year(None), "")


class TestPriorityReasons(unittest.TestCase):
    """Test priority reason formatting."""

    def test_format_priority_reasons_basic(self):
        """Test basic priority reason formatting."""
        reasons = ["Adam priority: Newfoundland coinage", "Fills collection gap"]
        result = format_priority_reasons(reasons)
        self.assertIn("Adam priority: Newfoundland coinage.", result)
        self.assertIn("Fills collection gap.", result)

    def test_format_priority_reasons_with_periods(self):
        """Test priority reasons that already have periods."""
        reasons = ["Adam priority: Newfoundland coinage.", "Fills collection gap."]
        result = format_priority_reasons(reasons)
        # Should not double-add periods
        self.assertEqual(result.count(".."), 0)

    def test_format_priority_reasons_empty(self):
        """Test empty priority reasons."""
        result = format_priority_reasons([])
        self.assertEqual(result, "")

    def test_format_priority_reasons_blank(self):
        """Test blank priority reasons."""
        reasons = ["", "  ", "Valid reason"]
        result = format_priority_reasons(reasons)
        self.assertEqual(result, "Valid reason.")


if __name__ == '__main__':
    unittest.main()
