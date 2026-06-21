"""Deal Hunter candidate pool ranking and import framework."""

import csv
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from deal_hunter import DealHunter, DealHunterCSVImportResult, DealHunterResult, DealListing
from market_awareness import MarketAwarenessEngine
from opportunity_engine import OpportunityEngine


DEFAULT_BUDGETS = (50, 100, 250, 500)
PROFILE_EBAY = "eBay CSV"
PROFILE_AUCTION = "Auction CSV"
PROFILE_DEALER = "Dealer CSV"
PROFILE_CUSTOM = "Custom CSV"


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _dedupe(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


@dataclass
class ImportProfile:
    """CSV import profile for future offline listing connectors."""

    name: str
    required_fields: List[str] = field(default_factory=lambda: ["title", "price_cad"])
    field_aliases: Dict[str, List[str]] = field(default_factory=dict)
    description: str = ""

    @classmethod
    def ebay_csv(cls) -> "ImportProfile":
        return cls(PROFILE_EBAY, description="Deal Hunter eBay.ca-style CSV columns.")

    @classmethod
    def auction_csv(cls) -> "ImportProfile":
        return cls(
            PROFILE_AUCTION,
            field_aliases={"title": ["lot_title", "title"], "price_cad": ["hammer_price", "price_cad", "price"]},
            description="Offline auction CSV mapping framework; no live auction fetching.",
        )

    @classmethod
    def dealer_csv(cls) -> "ImportProfile":
        return cls(
            PROFILE_DEALER,
            field_aliases={"title": ["item", "title"], "price_cad": ["dealer_price", "price_cad", "price"]},
            description="Offline dealer-list CSV mapping framework; no dealer-site fetching.",
        )

    @classmethod
    def custom_csv(cls, aliases: Optional[Dict[str, List[str]]] = None) -> "ImportProfile":
        return cls(PROFILE_CUSTOM, field_aliases=aliases or {}, description="Custom local CSV mapping.")

    def normalize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        normalized = DealHunter._normalize_csv_row(row)
        if self.field_aliases:
            lowered = {str(key or "").strip().lower(): value for key, value in (row or {}).items()}
            for target, aliases in self.field_aliases.items():
                for alias in aliases:
                    key = str(alias or "").strip().lower()
                    if key in lowered and lowered[key] not in (None, ""):
                        normalized[target] = lowered[key]
                        break
        return normalized

    def validate_normalized_row(self, row: Dict[str, Any], row_number: int) -> List[str]:
        warnings = []
        for field_name in self.required_fields:
            if str(row.get(field_name) or "").strip() == "":
                warnings.append(f"Row {row_number}: missing required {field_name}")
        url = str(row.get("listing_url") or "").strip()
        if url and not (url.startswith("http://") or url.startswith("https://")):
            warnings.append(f"Row {row_number}: unsupported URL format")
        return warnings


@dataclass
class CandidatePoolImportResult:
    rows_found: int = 0
    imported_count: int = 0
    duplicate_count: int = 0
    skipped_rows: int = 0
    warnings: List[str] = field(default_factory=list)


@dataclass
class CandidatePool:
    """Collection of imported/manual Deal Hunter candidate listings."""

    listings: List[DealListing] = field(default_factory=list)
    import_warnings: List[str] = field(default_factory=list)
    duplicate_keys: List[str] = field(default_factory=list)

    @classmethod
    def from_listings(cls, listings: Iterable[DealListing]) -> "CandidatePool":
        pool = cls()
        pool.add_listings(listings)
        return pool

    @property
    def candidate_count(self) -> int:
        return len(self.listings)

    def add_listing(self, listing: DealListing) -> bool:
        key = self._listing_key(listing)
        if key in {self._listing_key(row) for row in self.listings}:
            self.duplicate_keys.append(key)
            return False
        self.listings.append(listing)
        return True

    def add_listings(self, listings: Iterable[DealListing]) -> CandidatePoolImportResult:
        result = CandidatePoolImportResult()
        for listing in listings or []:
            result.rows_found += 1
            if self.add_listing(listing):
                result.imported_count += 1
            else:
                result.duplicate_count += 1
        return result

    def import_csv(self, input_path: str, profile: Optional[ImportProfile] = None) -> CandidatePoolImportResult:
        profile = profile or ImportProfile.ebay_csv()
        imported = self._import_with_profile(input_path, profile)
        pool_result = self.add_listings(imported.listings)
        warnings = _dedupe(list(imported.warnings) + list(pool_result.warnings))
        result = CandidatePoolImportResult(
            rows_found=imported.rows_found,
            imported_count=pool_result.imported_count,
            duplicate_count=pool_result.duplicate_count,
            skipped_rows=imported.skipped_rows,
            warnings=warnings,
        )
        self.import_warnings = _dedupe(list(self.import_warnings) + warnings)
        return result

    def detect_duplicates(self) -> List[Dict[str, Any]]:
        buckets: Dict[str, List[DealListing]] = {}
        for listing in self.listings:
            buckets.setdefault(self._listing_key(listing), []).append(listing)
        rows = []
        for key, listings in buckets.items():
            if len(listings) > 1:
                rows.append({"key": key, "count": len(listings), "titles": [row.title for row in listings]})
        for key in self.duplicate_keys:
            rows.append({"key": key, "count": 1, "titles": []})
        return rows

    def source_summary(self) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for listing in self.listings:
            source = listing.source or "Unknown"
            summary[source] = summary.get(source, 0) + 1
        return summary

    @staticmethod
    def _listing_key(listing: DealListing) -> str:
        if listing.listing_url:
            return f"url:{_normalize(listing.listing_url)}"
        return "listing:" + "|".join([
            _normalize(listing.title),
            f"{listing.price_cad:.2f}",
            f"{listing.shipping_cad:.2f}",
            _normalize(listing.seller),
        ])

    @staticmethod
    def _import_with_profile(input_path: str, profile: ImportProfile) -> DealHunterCSVImportResult:
        listings = []
        warnings = []
        skipped = 0
        rows_found = 0
        with open(input_path, "r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row_number, row in enumerate(reader, start=2):
                rows_found += 1
                normalized = profile.normalize_row(row)
                row_warnings = profile.validate_normalized_row(normalized, row_number)
                if any("missing required" in warning for warning in row_warnings):
                    skipped += 1
                    warnings.extend(row_warnings)
                    continue
                listing = DealListing.from_dict(normalized)
                warnings.extend(row_warnings)
                warnings.extend(f"Row {row_number}: {warning}" for warning in listing.input_warnings)
                listings.append(listing)
        return DealHunterCSVImportResult(rows_found, listings, skipped, _dedupe(warnings))


@dataclass
class RankingScore:
    """Explainable 0-100 ranking score."""

    score: int
    deal_score: int = 0
    opportunity_score: int = 0
    collection_fit: int = 0
    upgrade_value: int = 0
    gap_value: int = 0
    want_list_relevance: int = 0
    liquidity: int = 0
    risk: int = 0
    budget_fit: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class RankedDeal:
    rank: int
    listing: DealListing
    deal_result: DealHunterResult
    ranking_score: RankingScore
    recommendation: str
    collection_impact: str
    budget_fit: str
    risk_flags: List[str] = field(default_factory=list)
    counterargument: str = ""
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "title": self.listing.title,
            "total_cost": self.listing.total_cost,
            "recommendation": self.recommendation,
            "ranking_score": self.ranking_score.score,
            "collection_impact": self.collection_impact,
            "budget_fit": self.budget_fit,
            "risk_flags": "; ".join(self.risk_flags),
            "counterargument": self.counterargument,
            "source": self.source,
            "seller": self.listing.seller,
            "listing_url": self.listing.listing_url,
            **{f"score_{key}": value for key, value in self.ranking_score.to_dict().items() if key != "score"},
        }


@dataclass
class BudgetOpportunityReport:
    budget: int
    best_deals: List[RankedDeal] = field(default_factory=list)
    reasoning: str = ""
    counterargument: str = ""


@dataclass
class DealHunterRankingReport:
    ranked_deals: List[RankedDeal] = field(default_factory=list)
    budget_reports: Dict[int, BudgetOpportunityReport] = field(default_factory=dict)
    category_views: Dict[str, List[RankedDeal]] = field(default_factory=dict)
    candidate_count: int = 0
    duplicate_count: int = 0
    source_summary: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = self.generated_at or _now_iso()

    def format_markdown(self) -> str:
        lines = [
            "# Deal Hunter Ranking Report",
            "",
            f"- Generated: {self.generated_at}",
            f"- Candidate count: {self.candidate_count}",
            f"- Duplicate imports detected: {self.duplicate_count}",
            "- Guidance note: deterministic local ranking only; no scraping, APIs, live pricing, or automatic purchasing.",
            "",
            "## Top Opportunities Overall",
            "",
        ]
        lines.extend(self._format_deals(self.category_views.get("Top Opportunities Overall", [])))
        lines.extend(["", "## Budget Optimization", ""])
        for budget, report in self.budget_reports.items():
            lines.append(f"### ${budget}")
            lines.append(f"- Reasoning: {report.reasoning}")
            lines.append(f"- Counterargument: {report.counterargument}")
            lines.extend(self._format_deals(report.best_deals))
        for name, deals in self.category_views.items():
            if name == "Top Opportunities Overall":
                continue
            lines.extend(["", f"## {name}", ""])
            lines.extend(self._format_deals(deals))
        if self.warnings:
            lines.extend(["", "## Import Warnings", ""])
            lines.extend(f"- {warning}" for warning in self.warnings)
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            fieldnames = [
                "rank",
                "title",
                "total_cost",
                "recommendation",
                "ranking_score",
                "collection_impact",
                "budget_fit",
                "risk_flags",
                "counterargument",
                "source",
                "seller",
                "listing_url",
                "score_deal_score",
                "score_opportunity_score",
                "score_collection_fit",
                "score_upgrade_value",
                "score_gap_value",
                "score_want_list_relevance",
                "score_liquidity",
                "score_risk",
                "score_budget_fit",
            ]
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for deal in self.ranked_deals:
                writer.writerow(deal.to_dict())
        return True

    @staticmethod
    def _format_deals(deals: List[RankedDeal]) -> List[str]:
        if not deals:
            return ["- No matching ranked deals."]
        lines = []
        for deal in deals:
            lines.append(
                f"{deal.rank}. {deal.listing.title} - {deal.recommendation} "
                f"(ranking {deal.ranking_score.score}, cost ${deal.listing.total_cost:.2f})"
            )
            lines.append(f"   - Impact: {deal.collection_impact}")
            lines.append(f"   - Counterargument: {deal.counterargument}")
            if deal.risk_flags:
                lines.append(f"   - Risks: {', '.join(deal.risk_flags)}")
        return lines


TopOpportunitiesReport = DealHunterRankingReport


class DealHunterRankingEngine:
    """Rank large candidate pools using Deal Hunter and Opportunity Engine outputs."""

    def __init__(
        self,
        collection_items: Iterable[Any],
        want_list_intents: Optional[Iterable[Any]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
    ):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()

    def rank_pool(self, pool: CandidatePool, budgets: Iterable[int] = DEFAULT_BUDGETS, limit: int = 5) -> DealHunterRankingReport:
        hunter = DealHunter(self.collection_items, self.want_list_intents, self.market_awareness_engine)
        deal_results = hunter.generate_report(pool.listings).results
        opportunity_report = OpportunityEngine(
            self.collection_items,
            self.want_list_intents,
            self.market_awareness_engine,
        ).generate_report(deal_hunter_results=deal_results, limit=50)
        opportunity_by_title = {_normalize(row.item_name): row for row in opportunity_report.opportunities}
        ranked = [self._rank_result(result, opportunity_by_title.get(_normalize(result.listing.title))) for result in deal_results]
        ranked.sort(key=lambda row: (-row.ranking_score.score, row.listing.total_cost, row.listing.title))
        ranked = self._consolidate(ranked)
        for index, deal in enumerate(ranked, 1):
            deal.rank = index
        budget_reports = {int(budget): self._budget_report(ranked, int(budget), limit) for budget in budgets}
        return DealHunterRankingReport(
            ranked_deals=ranked,
            budget_reports=budget_reports,
            category_views=self._category_views(ranked, limit),
            candidate_count=pool.candidate_count,
            duplicate_count=len(pool.duplicate_keys),
            source_summary=pool.source_summary(),
            warnings=list(pool.import_warnings),
        )

    def _rank_result(self, result: DealHunterResult, opportunity: Optional[Any]) -> RankedDeal:
        detail = RankingScore(
            score=0,
            deal_score=result.priority_score,
            opportunity_score=opportunity.score if opportunity else 0,
            collection_fit=result.collection_fit_score,
            upgrade_value=22 if "upgrade" in result.collection_status.lower() else 0,
            gap_value=20 if "gap" in result.collection_status.lower() else 0,
            want_list_relevance=25 if "Explicit WANT_LIST match" in result.reasons else 0,
            liquidity=result.liquidity_score,
            risk=result.risk_score,
            budget_fit=self._budget_points(result.listing.total_cost),
        )
        score = int(round(detail.deal_score * 0.30))
        score += int(round(detail.opportunity_score * 0.25))
        score += int(round(detail.collection_fit * 0.18))
        score += detail.upgrade_value + detail.gap_value + detail.want_list_relevance
        score += int(round(detail.liquidity * 0.08))
        score += detail.budget_fit
        score -= int(round(detail.risk * 0.22))
        if result.recommendation == "PASS":
            score = min(score, 20)
        if result.recommendation == "REVIEW":
            score = min(score, 70)
        detail.score = max(0, min(100, score))
        return RankedDeal(
            rank=0,
            listing=result.listing,
            deal_result=result,
            ranking_score=detail,
            recommendation=result.recommendation,
            collection_impact=result.collection_status,
            budget_fit=self._budget_fit(result.listing.total_cost),
            risk_flags=list(result.risk_flags),
            counterargument=result.counterargument,
            source=result.listing.source or "Manual",
        )

    def _category_views(self, ranked: List[RankedDeal], limit: int) -> Dict[str, List[RankedDeal]]:
        return {
            "Top Opportunities Overall": ranked[:limit],
            "Top Opportunities Under $50": [row for row in ranked if 0 < row.listing.total_cost <= 50][:limit],
            "Top Opportunities Under $100": [row for row in ranked if 0 < row.listing.total_cost <= 100][:limit],
            "Top Opportunities Under $250": [row for row in ranked if 0 < row.listing.total_cost <= 250][:limit],
            "Top Opportunities Under $500": [row for row in ranked if 0 < row.listing.total_cost <= 500][:limit],
            "Top Newfoundland Opportunities": [row for row in ranked if "newfoundland" in row.listing.title.lower()][:limit],
            "Top Canadian Silver Opportunities": [row for row in ranked if self._is_canadian_silver(row)][:limit],
            "Top Banknote Opportunities": [row for row in ranked if "banknote" in row.listing.title.lower()][:limit],
            "Top Upgrade Opportunities": [row for row in ranked if "upgrade" in row.collection_impact.lower()][:limit],
            "Top Collection Gap Opportunities": [row for row in ranked if "gap" in row.collection_impact.lower()][:limit],
            "Top Want-List Opportunities": [row for row in ranked if "Explicit WANT_LIST match" in row.deal_result.reasons][:limit],
        }

    @staticmethod
    def _consolidate(ranked: List[RankedDeal]) -> List[RankedDeal]:
        selected: Dict[str, RankedDeal] = {}
        for deal in ranked:
            parsed = deal.deal_result.parsed_candidate
            key = "|".join([
                _normalize(parsed.country),
                _normalize(parsed.denomination),
                _normalize(parsed.year),
                _normalize(parsed.series_type),
                _normalize(parsed.grade),
                deal.collection_impact.lower(),
            ])
            if not key.strip("|"):
                key = _normalize(deal.listing.title)
            existing = selected.get(key)
            if not existing or deal.ranking_score.score > existing.ranking_score.score:
                selected[key] = deal
        return list(selected.values())

    def _budget_report(self, ranked: List[RankedDeal], budget: int, limit: int) -> BudgetOpportunityReport:
        affordable = [row for row in ranked if 0 < row.listing.total_cost <= budget]
        best = affordable[:limit]
        if best:
            top = best[0]
            reasoning = f"{top.listing.title} gives the best ranked collection impact within ${budget}."
            counter = top.counterargument
        else:
            reasoning = f"No priced ranked deal fits within ${budget}."
            counter = "Wait for a better-priced opportunity or increase budget."
        return BudgetOpportunityReport(budget, best, reasoning, counter)

    @staticmethod
    def _budget_points(total_cost: float) -> int:
        if total_cost <= 0:
            return 0
        if total_cost <= 50:
            return 18
        if total_cost <= 100:
            return 14
        if total_cost <= 250:
            return 10
        if total_cost <= 500:
            return 6
        return -8

    @staticmethod
    def _budget_fit(total_cost: float) -> str:
        if total_cost <= 0:
            return "No price supplied"
        for budget in DEFAULT_BUDGETS:
            if total_cost <= budget:
                return f"Within ${budget}"
        return "Above $500"

    @staticmethod
    def _is_canadian_silver(row: RankedDeal) -> bool:
        title = row.listing.title.lower()
        return "canada" in title and any(term in title for term in ["silver", "10 cents", "25 cents", "50 cents", "dollar", "dime", "quarter"])
