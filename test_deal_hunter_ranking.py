"""Tests for v3.4 Deal Hunter Ranking and Import Framework."""

import os
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

from coin_collection import CoinItem
from deal_hunter import DealHunter, DealHunterReport, DealHunterResult, DealListing, ParsedDealCandidate
from deal_hunter_ranking import (
    CandidatePool,
    DealHunterRankingEngine,
    DealHunterRankingReport,
    ImportProfile,
    TopOpportunitiesReport,
)
from legacy_portfolio_importer import LegacyWantListIntent
from market_awareness import MarketAwarenessEngine, ObservedPriceRecord


def make_item(item_id, country, denomination, year, grade, **overrides):
    data = {
        "id": item_id,
        "image_path": "",
        "country": country,
        "denomination": denomination,
        "year": year,
        "grade": grade,
        "notes": "",
        "date_added": "2026-06-21",
    }
    data.update(overrides)
    return CoinItem(**data)


def make_intent(target_coin, priority_score=90):
    return LegacyWantListIntent(
        sheet_name="WANT_LIST",
        row_number=2,
        legacy_id=f"rank_{target_coin}",
        target_coin=target_coin,
        priority="High",
        target_grade="VF-20",
        budget=150.0,
        why_wanted="Deal Hunter ranking target",
        status="Active",
        priority_score=priority_score,
    )


class TestDealHunterRanking(unittest.TestCase):
    def test_real_needs_review_dominates_stale_pool_advice(self):
        result = DealHunter([]).analyze_listing(DealListing("Unattributed coin lot", 80, 5))
        self.assertEqual(result.collection_status, "needs review")
        for status in ("BUY", "WATCH", "PASS"):
            with self.subTest(status=status):
                stale = replace(result, recommendation=status, priority_score=90,
                                collection_fit_score=90, max_rational_price=100)
                with patch("deal_hunter_ranking.DealHunter.generate_report", return_value=DealHunterReport([stale])):
                    report = DealHunterRankingEngine([]).rank_pool(CandidatePool.from_listings([result.listing]))
                self.assertEqual(report.ranked_deals, [])
                self.assertIsNone(report.unranked_deals[0].rank)
                self.assertIsNone(report.unranked_deals[0].ranking_score.score)

    def test_relationship_prose_does_not_supply_categories_or_scores(self):
        from opportunity_engine import OpportunityReport

        result = DealHunterResult(DealListing("Synthetic", 80, 5), ParsedDealCandidate(),
                                  "Supported boundary", 80, 20, 70, 0, 100, "WATCH", "Review")
        opportunity = OpportunityReport(1, "Collection Opportunity", "Synthetic", 50, recommendation="WATCH")
        engine = DealHunterRankingEngine([])
        baseline = engine._rank_result(result, opportunity)
        for text in ("duplicate", "not a duplicate", "upgrade", "not an upgrade", "collection gap", "not a collection gap"):
            with self.subTest(text=text):
                row = engine._rank_result(replace(result, collection_status=text), opportunity)
                views = engine._category_views([row], 5)
                self.assertEqual(row.ranking_score.score, baseline.ranking_score.score)
                self.assertEqual(views["Top Upgrade Opportunities"], [])
                self.assertEqual(views["Top Collection Gap Opportunities"], [])

    def test_review_retained_numerics_cannot_rank(self):
        from opportunity_engine import OpportunityReport
        result = DealHunter([]).analyze_listing(DealListing("Unattributed coin lot", 80, 5))
        retained = replace(result, priority_score=90, collection_fit_score=90)
        ranked = DealHunterRankingEngine([])._rank_result(retained, OpportunityReport(None, "Boundary", "Retained", 90))
        self.assertIsNone(ranked.ranking_score.score)
        self.assertIsNone(ranked.rank)
        self.assertEqual(ranked.recommendation, "REVIEW")
        self.assertEqual(ranked.listing.total_cost, 85)

    def test_negative_relationship_narrative_has_no_bonus(self):
        from opportunity_engine import OpportunityReport
        result = DealHunterResult(DealListing("Boundary", 20), ParsedDealCandidate(), "Supported boundary", 20, 0, 20, 0, 20, "WATCH", "Context")
        engine = DealHunterRankingEngine([])
        opportunity = OpportunityReport(None, "Boundary", "Supported", 17)
        baseline = engine._rank_result(result, opportunity).ranking_score.score
        for text in ("not an upgrade", "not a collection gap"):
            self.assertEqual(engine._rank_result(replace(result, collection_status=text, reasons=[text]), opportunity).ranking_score.score, baseline)

    def test_unresolved_pool_is_retained_without_numeric_rank(self):
        import json

        report = DealHunterRankingEngine([]).rank_pool(CandidatePool.from_listings([
            DealListing("Unattributed coin lot", 80, 5, seller="Synthetic seller"),
            DealListing("Another unattributed lot", 40, 2),
        ]))
        self.assertEqual(report.ranked_deals, [])
        self.assertEqual(len(report.unranked_deals), 2)
        for row in report.unranked_deals:
            self.assertIsNone(row.rank)
            self.assertIsNone(row.ranking_score.score)
            self.assertIsNone(json.loads(json.dumps(row.to_dict()))["ranking_score"])
            self.assertTrue(row.risk_flags)
        self.assertEqual(report.unranked_deals[0].listing.total_cost, 85)
        self.assertEqual(report.unranked_deals[0].listing.seller, "Synthetic seller")
        self.assertIn("unavailable", report.format_markdown())

    def test_mixed_pool_only_supported_deal_receives_rank(self):
        import json
        unresolved = DealHunter([]).analyze_listing(DealListing("Unattributed coin lot", 80, 5))
        # Already-supported DealHunterResult boundary fixtures; these do not
        # claim that a parsed country/denomination/year supports these scores.
        supported = DealHunterResult(
            DealListing("Supported downstream", 70, 5), ParsedDealCandidate(),
            "Supported boundary", 80, 20, 70, 0, 100, "WATCH", "Manual review")
        zero = DealHunterResult(
            DealListing("Supported zero", 0, 0), ParsedDealCandidate(),
            "Supported zero boundary", 0, 0, 0, 100, 0, "WATCH", "Manual review")
        results = [unresolved, zero, supported]
        with patch("deal_hunter_ranking.DealHunter.generate_report", return_value=DealHunterReport(results)):
            report = DealHunterRankingEngine([]).rank_pool(CandidatePool.from_listings(row.listing for row in results))
        self.assertEqual([row.ranking_score.score for row in report.ranked_deals], [70, 0])
        self.assertEqual([row.rank for row in report.ranked_deals], [1, 2])
        self.assertEqual(len(report.unranked_deals), 1)
        self.assertIsNone(report.unranked_deals[0].rank)
        self.assertIsNone(report.unranked_deals[0].ranking_score.score)
        self.assertEqual(report.ranked_deals[0].ranking_score.opportunity_score, 69)
        self.assertEqual(report.ranked_deals[1].deal_result.max_rational_price, 0)
        payload = json.loads(json.dumps({"ranked_deals": [row.to_dict() for row in report.ranked_deals],
                                         "unranked_deals": [row.to_dict() for row in report.unranked_deals]}))
        self.assertEqual(payload["ranked_deals"][1]["ranking_score"], 0)
        self.assertIsNone(payload["unranked_deals"][0]["ranking_score"])

    def setUp(self):
        self.items = [
            make_item("nf1900", "Newfoundland", "50 cents", "1900", "VF-20"),
            make_item("nf1902", "Newfoundland", "50 cents", "1902", "VF-20"),
            make_item("ca1911", "Canada", "10 cents", "1911", "VF-20"),
            make_item("lc1859", "Canada", "1 cent", "1859", "G-4"),
        ]
        self.intents = [
            make_intent("Newfoundland 50 cents 1901", 95),
            make_intent("Canada chartered banknote BCS VF25", 80),
        ]
        self.market = MarketAwarenessEngine(observations=[
            ObservedPriceRecord("1901 Newfoundland 50 cents", "Newfoundland", "50 cents", "1901", "VF-20", 90),
            ObservedPriceRecord("1911 Canada 10 cents", "Canada", "10 cents", "1911", "EF-40", 70),
        ])
        self.engine = DealHunterRankingEngine(self.items, self.intents, self.market)
        self.listings = [
            DealListing("1901 Newfoundland 50 cents VF20 PCGS", 85, 5, seller="A", source="Manual", listing_url="https://example.test/nf1901"),
            DealListing("1904 Newfoundland 50 cents VF20", 70, 5, seller="A", source="Manual", listing_url="https://example.test/nf1904"),
            DealListing("1911 Canada 10 cents EF40 silver ICCS", 65, 5, seller="B", source="Manual", listing_url="https://example.test/ca1911"),
            DealListing("Canada chartered banknote BCS VF25", 120, 10, seller="C", source="Dealer", listing_url="https://example.test/note"),
            DealListing("France 10 centimes 1975", 1, 5, seller="D", source="Manual", listing_url="https://example.test/france"),
        ]

    def test_candidate_pool_creation(self):
        pool = CandidatePool.from_listings(self.listings[:2])

        self.assertEqual(pool.candidate_count, 2)
        self.assertEqual(pool.source_summary()["Manual"], 2)

    def test_duplicate_detection_by_url(self):
        pool = CandidatePool()
        self.assertTrue(pool.add_listing(self.listings[0]))
        self.assertFalse(pool.add_listing(DealListing("Duplicate Newfoundland", 85, 5, listing_url="https://example.test/nf1901")))

        self.assertEqual(pool.candidate_count, 1)
        self.assertTrue(pool.detect_duplicates())

    def test_duplicate_import_handling(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "duplicates.csv")
            with open(csv_path, "w", encoding="utf-8") as handle:
                handle.write("title,price_cad,shipping_cad,listing_url\n")
                handle.write("1901 Newfoundland 50 cents VF20,85,5,https://example.test/nf1901\n")
                handle.write("1901 Newfoundland 50 cents VF20,87,5,https://example.test/nf1901\n")

            pool = CandidatePool()
            result = pool.import_csv(csv_path)

        self.assertEqual(result.rows_found, 2)
        self.assertEqual(result.imported_count, 1)
        self.assertEqual(result.duplicate_count, 1)

    def test_import_profiles_normalize_auction_and_dealer_rows(self):
        auction = ImportProfile.auction_csv().normalize_row({"lot_title": "Newfoundland 5 cents 1945", "hammer_price": "40"})
        dealer = ImportProfile.dealer_csv().normalize_row({"item": "Canada silver dollar 1958", "dealer_price": "55"})

        self.assertEqual(auction["title"], "Newfoundland 5 cents 1945")
        self.assertEqual(auction["price_cad"], "40")
        self.assertEqual(dealer["title"], "Canada silver dollar 1958")
        self.assertEqual(dealer["price_cad"], "55")

    def test_malformed_import_warnings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "malformed.csv")
            with open(csv_path, "w", encoding="utf-8") as handle:
                handle.write("name,cost,url\n")
                handle.write(",85,https://example.test/missing-title\n")
                handle.write("1901 Newfoundland 50 cents VF20,not-a-price,bad-url\n")

            profile = ImportProfile.custom_csv({"title": ["name"], "price_cad": ["cost"], "listing_url": ["url"]})
            pool = CandidatePool()
            result = pool.import_csv(csv_path, profile)

        self.assertEqual(result.skipped_rows, 1)
        self.assertTrue(any("missing required title" in warning for warning in result.warnings))
        self.assertTrue(any("unsupported URL format" in warning for warning in result.warnings))
        self.assertTrue(any("Malformed price_cad" in warning for warning in result.warnings))

    def test_ranking_score_generation(self):
        report = self.engine.rank_pool(CandidatePool.from_listings(self.listings), limit=3)

        self.assertIsInstance(report, DealHunterRankingReport)
        self.assertIsInstance(report, TopOpportunitiesReport)
        self.assertEqual(report.ranked_deals, [])
        self.assertEqual(len(report.unranked_deals), 5)
        self.assertEqual(report.candidate_count, 5)
        for row in report.unranked_deals:
            self.assertIsNone(row.rank)
            self.assertIsNone(row.ranking_score.score)

    def test_budget_ranking(self):
        report = self.engine.rank_pool(CandidatePool.from_listings(self.listings), budgets=[50, 100, 250, 500])

        self.assertIn(100, report.budget_reports)
        self.assertEqual(report.budget_reports[100].best_deals, [])
        self.assertEqual(len(report.unranked_deals), 5)
        self.assertEqual(report.unranked_deals[0].listing.total_cost, 90)

    def test_budget_points_exact_boundaries(self):
        cases = [
            (-1, 0),
            (0, 0),
            (0.01, 18),
            (50, 18),
            (50.01, 14),
            (100, 14),
            (100.01, 10),
            (250, 10),
            (250.01, 6),
            (500, 6),
            (500.01, -8),
        ]

        for total_cost, expected in cases:
            with self.subTest(total_cost=total_cost):
                self.assertEqual(self.engine._budget_points(total_cost), expected)

    def test_newfoundland_category(self):
        report = self.engine.rank_pool(CandidatePool.from_listings(self.listings))

        self.assertEqual(report.category_views["Top Newfoundland Opportunities"], [])
        rows = [row for row in report.unranked_deals if "Newfoundland" in row.listing.title]
        self.assertTrue(rows)
        self.assertTrue(all(row.rank is None and row.ranking_score.score is None for row in rows))

    def test_banknote_category(self):
        report = self.engine.rank_pool(CandidatePool.from_listings(self.listings))

        self.assertEqual(report.category_views["Top Banknote Opportunities"], [])
        rows = [row for row in report.unranked_deals if "banknote" in row.listing.title]
        self.assertTrue(rows)
        self.assertTrue(all(row.rank is None and row.ranking_score.score is None for row in rows))

    def test_upgrade_category(self):
        report = self.engine.rank_pool(CandidatePool.from_listings(self.listings))

        self.assertEqual(report.category_views["Top Upgrade Opportunities"], [])
        rows = [row for row in report.unranked_deals if "1911 Canada" in row.listing.title]
        self.assertTrue(rows)
        self.assertTrue(all(row.rank is None and row.ranking_score.score is None for row in rows))

    def test_collection_gap_category(self):
        report = self.engine.rank_pool(CandidatePool.from_listings(self.listings))

        self.assertEqual(report.category_views["Top Collection Gap Opportunities"], [])
        rows = [row for row in report.unranked_deals if "1901 Newfoundland" in row.listing.title]
        self.assertTrue(rows)
        self.assertTrue(all(row.rank is None and row.ranking_score.score is None for row in rows))

    def test_export_generation(self):
        report = self.engine.rank_pool(CandidatePool.from_listings(self.listings))
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "ranking.csv")
            md_path = os.path.join(temp_dir, "ranking.md")
            self.assertTrue(report.export_csv(csv_path))
            self.assertTrue(report.export_markdown(md_path))
            with open(csv_path, "r", encoding="utf-8") as handle:
                self.assertIn("ranking_score", handle.read())
            with open(md_path, "r", encoding="utf-8") as handle:
                self.assertIn("Deal Hunter Ranking Report", handle.read())


if __name__ == "__main__":
    unittest.main()
