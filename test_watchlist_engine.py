import os
import tempfile
import unittest
from types import SimpleNamespace

from deal_hunter import DealListing
from watchlist_engine import (
    ALERT_TYPE_COLLECTION_GAP_OPPORTUNITY,
    ALERT_TYPE_HIGH_PRIORITY_OPPORTUNITY,
    ALERT_TYPE_RARE_TARGET_OPPORTUNITY,
    ALERT_TYPE_UPGRADE_OPPORTUNITY,
    ALERT_TYPE_WATCHLIST_MATCH,
    AlertEngine,
    WatchPriority,
    Watchlist,
    WatchlistEngine,
    WatchlistItem,
    WATCH_TYPE_KEYWORD,
    WATCH_TYPE_SERIES,
    WATCH_TYPE_SPECIFIC_COIN,
)


class TestWatchlistEngine(unittest.TestCase):
    def make_listing(self, title, description="", price=25.0):
        return DealListing(
            title=title,
            price_cad=price,
            shipping_cad=5.0,
            seller="Test Seller",
            source="Fixture Source",
            listing_url="https://example.test/listing",
            description=description,
        )

    def make_enriched_candidate(self, title, classifications=None, relevance=80, recommendation="BUY"):
        listing = self.make_listing(title, description="Fixture candidate")
        relevance_summary = SimpleNamespace(
            collection_relevance_score=relevance,
            collection_goal_advanced="Collection gap and upgrade opportunity",
            relevance_explanation="Advances a tracked collector goal",
            classifications=classifications or ["Collection Gap"],
        )
        market_report = SimpleNamespace(confidence=SimpleNamespace(score=70))
        return SimpleNamespace(
            original_listing=listing,
            original_recommendation="WATCH",
            escalated_recommendation=recommendation,
            collection_relevance=relevance_summary,
            market_report=market_report,
            opportunity_confidence=70,
        )

    def test_watchlist_creation_and_remove(self):
        watchlist = Watchlist("Test Watches")
        item = WatchlistItem(
            name="Newfoundland 20 Cents",
            watch_type=WATCH_TYPE_SERIES,
            query="Newfoundland 20 cents",
            priority="HIGH",
        )
        watchlist.add_item(item)

        self.assertEqual(watchlist.active_items()[0].priority, WatchPriority.HIGH)
        self.assertTrue(watchlist.remove_item("Newfoundland 20 Cents"))
        self.assertEqual(watchlist.active_items(), [])

    def test_keyword_watch_matches_listing_text(self):
        watchlist = Watchlist("Keywords", [
            WatchlistItem("Near 6", WATCH_TYPE_KEYWORD, "near 6", WatchPriority.CRITICAL),
        ])
        listing = self.make_listing("Canada 1926 Near 6 nickel VF")

        report = WatchlistEngine([watchlist]).scan([listing])

        self.assertEqual(len(report.matches), 1)
        self.assertEqual(report.matches[0].watch_item.name, "Near 6")
        self.assertGreaterEqual(report.matches[0].confidence, 60)

    def test_specific_coin_watch_requires_target_terms(self):
        watchlist = Watchlist("Specific", [
            WatchlistItem(
                "1973 Large Bust Quarter",
                WATCH_TYPE_SPECIFIC_COIN,
                "1973 Large Bust quarter Canada",
                WatchPriority.CRITICAL,
            )
        ])

        matched = WatchlistEngine([watchlist]).scan([
            self.make_listing("1973 Canada Large Bust quarter"),
            self.make_listing("1974 Canada quarter"),
        ])

        self.assertEqual(len(matched.matches), 1)
        self.assertIn("1973", matched.matches[0].candidate_title)

    def test_series_watch_handles_canadian_silver(self):
        watchlist = Watchlist("Series", [
            WatchlistItem("Canadian Silver", WATCH_TYPE_SERIES, "Canada silver dime quarter half dollar", WatchPriority.HIGH)
        ])
        listing = self.make_listing("1912 Canada silver dime ICCS VF")

        report = WatchlistEngine([watchlist]).scan([listing])

        self.assertEqual(len(report.matches), 1)
        self.assertGreaterEqual(report.matches[0].confidence, 80)

    def test_priority_sorting_places_critical_first(self):
        watchlist = Watchlist("Priorities", [
            WatchlistItem("General Canada", WATCH_TYPE_KEYWORD, "Canada", WatchPriority.LOW),
            WatchlistItem("Newfoundland", WATCH_TYPE_KEYWORD, "Newfoundland", WatchPriority.CRITICAL),
        ])

        report = WatchlistEngine([watchlist]).scan([
            self.make_listing("Canada quarter"),
            self.make_listing("Newfoundland 50 cents"),
        ])

        self.assertEqual(report.matches[0].watch_item.priority, WatchPriority.CRITICAL)

    def test_adam_presets_include_required_targets(self):
        preset = WatchlistEngine.adam_presets()
        names = {item.name for item in preset.items}

        self.assertIn("Newfoundland Coins", names)
        self.assertIn("1859 Large Cent Varieties", names)
        self.assertIn("1926 Near 6 Nickel", names)
        self.assertIn("1973 Large Bust Quarter", names)

    def test_alert_generation_for_watchlist_match(self):
        watchlist = Watchlist("Watch", [
            WatchlistItem("Newfoundland", WATCH_TYPE_SERIES, "Newfoundland", WatchPriority.CRITICAL),
        ])
        candidate = self.make_enriched_candidate("1901 Newfoundland 50 cents", ["Collection Gap"], relevance=85)

        report = AlertEngine(WatchlistEngine([watchlist])).generate_alerts([candidate])

        self.assertTrue(any(alert.alert_type == ALERT_TYPE_WATCHLIST_MATCH for alert in report.alerts))
        self.assertGreaterEqual(report.alerts[0].score.score, 50)

    def test_alert_generation_for_upgrade_gap_high_priority_and_rare_target(self):
        candidate = self.make_enriched_candidate(
            "1859 Canada Large Cent Wide 9 upgrade",
            ["Upgrade Opportunity", "Collection Gap"],
            relevance=90,
        )

        report = AlertEngine(WatchlistEngine([])).generate_alerts([candidate], watchlists=[])
        alert_types = {alert.alert_type for alert in report.alerts}

        self.assertIn(ALERT_TYPE_UPGRADE_OPPORTUNITY, alert_types)
        self.assertIn(ALERT_TYPE_COLLECTION_GAP_OPPORTUNITY, alert_types)
        self.assertIn(ALERT_TYPE_HIGH_PRIORITY_OPPORTUNITY, alert_types)
        self.assertIn(ALERT_TYPE_RARE_TARGET_OPPORTUNITY, alert_types)

    def test_report_exports_markdown_and_csv(self):
        watchlist = Watchlist("Export Watch", [
            WatchlistItem("Newfoundland", WATCH_TYPE_SERIES, "Newfoundland", WatchPriority.HIGH),
        ])
        listing = self.make_listing("Newfoundland 5 cents")
        engine = WatchlistEngine([watchlist])
        watch_report = engine.scan([listing])
        alert_report = AlertEngine(engine).generate_alerts([listing])

        with tempfile.TemporaryDirectory() as temp_dir:
            watch_csv = os.path.join(temp_dir, "watch.csv")
            alert_csv = os.path.join(temp_dir, "alerts.csv")
            watch_md = os.path.join(temp_dir, "watch.md")
            alert_md = os.path.join(temp_dir, "alerts.md")

            self.assertTrue(watch_report.export_csv(watch_csv))
            self.assertTrue(alert_report.export_csv(alert_csv))
            self.assertTrue(watch_report.export_markdown(watch_md))
            self.assertTrue(alert_report.export_markdown(alert_md))

            with open(watch_md, encoding="utf-8") as handle:
                self.assertIn("Watchlist Report", handle.read())
            with open(alert_md, encoding="utf-8") as handle:
                self.assertIn("Alert Report", handle.read())
            with open(alert_csv, encoding="utf-8") as handle:
                self.assertIn("candidate_title", handle.readline())

    def test_pipeline_like_enriched_candidate_integration(self):
        candidate = self.make_enriched_candidate(
            "1904H Newfoundland 50 cents EF40",
            classifications=["Collection Gap", "High Priority Opportunity"],
            relevance=88,
            recommendation="BUY",
        )
        watchlist = Watchlist("Pipeline Watches", [
            WatchlistItem("Newfoundland Silver", WATCH_TYPE_SERIES, "Newfoundland silver 50 cents", WatchPriority.CRITICAL)
        ])

        watch_report = WatchlistEngine([watchlist]).scan([candidate])
        alert_report = AlertEngine(WatchlistEngine([watchlist])).generate_alerts([candidate])

        self.assertEqual(len(watch_report.matches), 1)
        self.assertEqual(watch_report.matches[0].recommendation, "BUY")
        self.assertTrue(any(alert.score.score >= 70 for alert in alert_report.alerts))


if __name__ == "__main__":
    unittest.main()
