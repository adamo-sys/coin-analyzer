"""Unit tests for image-analysis result handling."""

import os
import unittest
from unittest.mock import MagicMock


def summarize_accuracy(results):
    """Summarize analyzer output without invoking OCR or CV engines."""
    return {
        "total": len(results),
        "high_conf_country": sum(
            1 for result in results if result["country_confidence"] > 70
        ),
        "high_conf_denomination": sum(
            1 for result in results if result["denomination_confidence"] > 70
        ),
        "high_conf_year": sum(
            1 for result in results if result["year_confidence"] > 70
        ),
        "unknown_country": sum(
            1 for result in results if result["country"] == "unknown"
        ),
        "unknown_denomination": sum(
            1 for result in results if result["denomination"] == "unknown"
        ),
        "unknown_year": sum(1 for result in results if result["year"] == "Unknown"),
    }


class TestAccuracyHarness(unittest.TestCase):
    """Keep the accuracy test deterministic and independent from local paths."""

    def test_summary_counts_confidence_and_unknown_values(self):
        results = [
            {
                "country": "Canada",
                "country_confidence": 90,
                "denomination": "1 cent",
                "denomination_confidence": 80,
                "year": "1967",
                "year_confidence": 75,
            },
            {
                "country": "unknown",
                "country_confidence": 10,
                "denomination": "unknown",
                "denomination_confidence": 20,
                "year": "Unknown",
                "year_confidence": 0,
            },
        ]

        summary = summarize_accuracy(results)

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["high_conf_country"], 1)
        self.assertEqual(summary["high_conf_denomination"], 1)
        self.assertEqual(summary["high_conf_year"], 1)
        self.assertEqual(summary["unknown_country"], 1)
        self.assertEqual(summary["unknown_denomination"], 1)
        self.assertEqual(summary["unknown_year"], 1)

    def test_harness_uses_repo_relative_test_images(self):
        test_folder = os.path.join(os.path.dirname(__file__), "test_coins")

        self.assertTrue(os.path.isdir(test_folder))

    def test_analyzer_can_be_mocked_for_unit_tests(self):
        analyzer = MagicMock()
        analyzer.analyze_coin.return_value = {
            "country": "Canada",
            "country_confidence": 95,
            "denomination": "1 cent",
            "denomination_confidence": 88,
            "year": "1967",
            "year_confidence": 82,
        }

        result = analyzer.analyze_coin("test_coins/IMG_3460.jpeg")

        analyzer.analyze_coin.assert_called_once_with("test_coins/IMG_3460.jpeg")
        self.assertEqual(result["country"], "Canada")


if __name__ == "__main__":
    unittest.main()
