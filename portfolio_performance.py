"""Deterministic portfolio-level collection performance reporting.

This module uses only local collection records, snapshots, and existing
analysis engines. It does not scrape, call APIs, forecast markets, provide
investment advice, purchase automatically, or mutate collection data.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from collection_integrity import CollectionIntegrityAudit
from collection_intelligence import CollectionIntelligenceEngine, SILVER_DENOMINATION_TERMS
from collection_quality import CollectionQualityEngine
from collection_snapshot import CollectionSnapshot, CollectionSnapshotManager, CollectionSnapshotReport
from market_awareness import MarketAwarenessEngine
from opportunity_engine import OpportunityEngine, OpportunityReport
from series_tracker import SeriesReport, SeriesTracker


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return " ".join(_text(value).lower().replace(".", "").split())


def _money(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    cleaned = _text(value).replace("$", "").replace(",", "")
    try:
        return round(float(cleaned), 2) if cleaned else 0.0
    except ValueError:
        return 0.0


def _quantity(item: Any) -> int:
    try:
        return max(int(getattr(item, "quantity", 1) or 1), 1)
    except (TypeError, ValueError):
        return 1


def _item_label(item: Any) -> str:
    parts = [
        _text(getattr(item, "country", "")),
        _text(getattr(item, "denomination", "")),
        _text(getattr(item, "year", "")),
        _text(getattr(item, "grade", "")),
    ]
    return " ".join(part for part in parts if part) or _text(getattr(item, "title", "")) or "Unknown item"


@dataclass
class CollectionGrowthReport:
    collection_size: int = 0
    estimated_collection_value: float = 0.0
    silver_holdings: int = 0
    slab_count: int = 0
    banknote_count: int = 0
    newfoundland_count: int = 0
    custom_category_counts: Dict[str, int] = field(default_factory=dict)
    snapshot_comparison: Optional[CollectionSnapshotReport] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "collection_size": self.collection_size,
            "estimated_collection_value": self.estimated_collection_value,
            "silver_holdings": self.silver_holdings,
            "slab_count": self.slab_count,
            "banknote_count": self.banknote_count,
            "newfoundland_count": self.newfoundland_count,
            "custom_category_counts": dict(self.custom_category_counts),
            "snapshot_comparison": self.snapshot_comparison.to_dict() if self.snapshot_comparison else None,
        }


@dataclass
class AcquisitionPerformanceReport:
    best_acquisitions: List[str] = field(default_factory=list)
    biggest_upgrades: List[str] = field(default_factory=list)
    highest_collection_impact: List[str] = field(default_factory=list)
    strongest_opportunity_captures: List[str] = field(default_factory=list)
    highest_confidence_purchases: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "best_acquisitions": list(self.best_acquisitions),
            "biggest_upgrades": list(self.biggest_upgrades),
            "highest_collection_impact": list(self.highest_collection_impact),
            "strongest_opportunity_captures": list(self.strongest_opportunity_captures),
            "highest_confidence_purchases": list(self.highest_confidence_purchases),
        }


@dataclass
class SeriesProgressReport:
    series_reports: List[SeriesReport] = field(default_factory=list)
    nearest_completions: List[str] = field(default_factory=list)
    neglected_series: List[str] = field(default_factory=list)
    strongest_performing_series: List[str] = field(default_factory=list)
    progress_since_last_snapshot: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "series_reports": [report.to_dict() for report in self.series_reports],
            "nearest_completions": list(self.nearest_completions),
            "neglected_series": list(self.neglected_series),
            "strongest_performing_series": list(self.strongest_performing_series),
            "progress_since_last_snapshot": dict(self.progress_since_last_snapshot),
        }


@dataclass
class BudgetAllocationReport:
    category_counts: Dict[str, int] = field(default_factory=dict)
    category_estimated_values: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category_counts": dict(self.category_counts),
            "category_estimated_values": dict(self.category_estimated_values),
        }


@dataclass
class CollectionHealthScore:
    score: int
    category_scores: Dict[str, int] = field(default_factory=dict)
    explanation: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "category_scores": dict(self.category_scores),
            "explanation": list(self.explanation),
        }


@dataclass
class PortfolioPerformanceReport:
    generated_at: str
    growth_report: CollectionGrowthReport
    acquisition_report: AcquisitionPerformanceReport
    series_report: SeriesProgressReport
    budget_report: BudgetAllocationReport
    health_score: CollectionHealthScore
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    opportunities: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    recommended_focus_areas: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "growth_report": self.growth_report.to_dict(),
            "acquisition_report": self.acquisition_report.to_dict(),
            "series_report": self.series_report.to_dict(),
            "budget_report": self.budget_report.to_dict(),
            "health_score": self.health_score.to_dict(),
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "opportunities": list(self.opportunities),
            "risks": list(self.risks),
            "recommended_focus_areas": list(self.recommended_focus_areas),
        }

    def format_markdown(self) -> str:
        growth = self.growth_report
        lines = [
            "# Portfolio Performance Report",
            "",
            f"- Generated: {self.generated_at}",
            "- Guidance note: deterministic local collection-performance reporting only; not investment advice.",
            "",
            "## Executive Dashboard",
            "",
            f"- Collection items: {growth.collection_size}",
            f"- Estimated collection value from local records: ${growth.estimated_collection_value:.2f}",
            f"- Health score: {self.health_score.score}/100",
            f"- Silver holdings: {growth.silver_holdings}",
            f"- Slabbed/certified items: {growth.slab_count}",
            f"- Banknote count: {growth.banknote_count}",
            f"- Newfoundland count: {growth.newfoundland_count}",
            "",
            "## Growth Summary",
            "",
        ]
        if growth.snapshot_comparison and growth.snapshot_comparison.growth_summary:
            summary = growth.snapshot_comparison.growth_summary
            lines.append(f"- Growth since previous snapshot: {summary.growth_since_last_snapshot:+d}")
            lines.append(f"- Growth since first snapshot: {summary.growth_since_first_snapshot:+d}")
            lines.append(f"- Quality delta: {growth.snapshot_comparison.quality_delta:+d}")
            lines.append(f"- Integrity delta: {growth.snapshot_comparison.integrity_delta:+d}")
            lines.append(f"- Photo coverage delta: {growth.snapshot_comparison.photo_coverage_delta:+.1f}%")
        else:
            lines.append("- No snapshot comparison available.")
        lines.extend(self._section("Strengths", self.strengths))
        lines.extend(self._section("Weaknesses", self.weaknesses))
        lines.extend(self._section("Opportunities", self.opportunities))
        lines.extend(self._section("Risks", self.risks))
        lines.extend(self._section("Recommended Focus Areas", self.recommended_focus_areas))
        lines.extend(["", "## Series Progress", ""])
        if self.series_report.series_reports:
            for report in self.series_report.series_reports:
                lines.append(
                    f"- {report.series_name}: {report.completion_percentage:.1f}% complete; "
                    f"owned {report.owned_count}; missing {report.missing_count}; priority {report.priority_score}."
                )
        else:
            lines.append("- No supported series detected.")
        lines.extend(["", "## Budget Allocation", ""])
        for category, count in sorted(self.budget_report.category_counts.items()):
            value = self.budget_report.category_estimated_values.get(category, 0.0)
            lines.append(f"- {category}: {count} items, ${value:.2f} estimated local value")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["section", "metric", "value", "detail"])
            writer.writerow(["growth", "collection_size", self.growth_report.collection_size, ""])
            writer.writerow(["growth", "estimated_collection_value", f"{self.growth_report.estimated_collection_value:.2f}", ""])
            writer.writerow(["health", "health_score", self.health_score.score, "; ".join(self.health_score.explanation)])
            for category, score in self.health_score.category_scores.items():
                writer.writerow(["health_category", category, score, ""])
            for category, count in sorted(self.budget_report.category_counts.items()):
                value = self.budget_report.category_estimated_values.get(category, 0.0)
                writer.writerow(["budget_allocation", category, count, f"estimated_value={value:.2f}"])
            for report in self.series_report.series_reports:
                writer.writerow(["series", report.series_name, f"{report.completion_percentage:.1f}", f"priority={report.priority_score}; missing={report.missing_count}"])
            for section, values in [
                ("strength", self.strengths),
                ("weakness", self.weaknesses),
                ("opportunity", self.opportunities),
                ("risk", self.risks),
                ("focus", self.recommended_focus_areas),
            ]:
                for value in values:
                    writer.writerow([section, value, "", ""])
        return True

    @staticmethod
    def _section(title: str, values: Iterable[str]) -> List[str]:
        lines = ["", f"## {title}", ""]
        rows = list(values or [])
        if rows:
            lines.extend(f"- {row}" for row in rows)
        else:
            lines.append("- No entries generated from available local data.")
        return lines


class PortfolioPerformanceEngine:
    """Analyze portfolio performance from existing local collection engines."""

    def __init__(
        self,
        items: Iterable[Any],
        staged_want_list_intents: Optional[Iterable[Any]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
        snapshot_manager: Optional[CollectionSnapshotManager] = None,
        shopping_candidates: Optional[Iterable[Any]] = None,
        photo_records: Optional[Iterable[Any]] = None,
        custom_categories: Optional[Dict[str, Iterable[str]]] = None,
    ):
        self.items = list(items or [])
        self.want_list = list(staged_want_list_intents or [])
        self.market = market_awareness_engine or MarketAwarenessEngine()
        self.snapshot_manager = snapshot_manager or CollectionSnapshotManager()
        self.shopping_candidates = list(shopping_candidates or [])
        self.photo_records = list(photo_records or [])
        self.custom_categories = custom_categories or {}
        self.intelligence = CollectionIntelligenceEngine(self.items)
        self.series_tracker = SeriesTracker(self.items, self.want_list)

    def generate_report(self) -> PortfolioPerformanceReport:
        growth = self.collection_growth_report()
        acquisition = self.acquisition_performance_report()
        series = self.series_progress_report(growth.snapshot_comparison)
        budget = self.budget_allocation_report()
        health = self.collection_health_score(growth, series, budget)
        strengths = self._strengths(growth, series, health, acquisition)
        weaknesses = self._weaknesses(growth, series, health)
        opportunities = self._opportunities(acquisition, series)
        risks = self._risks(growth, health)
        focus = self._focus_areas(opportunities, weaknesses, series)
        return PortfolioPerformanceReport(
            generated_at=_now_iso(),
            growth_report=growth,
            acquisition_report=acquisition,
            series_report=series,
            budget_report=budget,
            health_score=health,
            strengths=strengths,
            weaknesses=weaknesses,
            opportunities=opportunities,
            risks=risks,
            recommended_focus_areas=focus,
        )

    def collection_growth_report(self) -> CollectionGrowthReport:
        current = self.snapshot_manager.create_snapshot(
            self.items,
            self.want_list,
            photo_records=self.photo_records,
            market_awareness_engine=self.market,
            shopping_candidates=self.shopping_candidates,
        )
        snapshots = self.snapshot_manager.load_snapshots()
        previous = snapshots[-1] if snapshots else None
        first = snapshots[0] if snapshots else current
        comparison = self.snapshot_manager.compare_snapshots(current, previous, first)
        custom_counts = {
            name: self._count_custom_category(terms)
            for name, terms in self.custom_categories.items()
        }
        custom_counts.update({
            "Duplicates": len(self.intelligence.detect_duplicates()),
            "Upgrades": len(self.intelligence.detect_upgrade_candidates()),
        })
        return CollectionGrowthReport(
            collection_size=len(self.items),
            estimated_collection_value=self._estimated_collection_value(),
            silver_holdings=self._silver_count(),
            slab_count=self._slab_count(),
            banknote_count=self._banknote_count(),
            newfoundland_count=self._newfoundland_count(),
            custom_category_counts=custom_counts,
            snapshot_comparison=comparison,
        )

    def acquisition_performance_report(self) -> AcquisitionPerformanceReport:
        opportunities = self._opportunity_rows()
        upgrades = self.intelligence.detect_upgrade_candidates()
        purchases = sorted(
            getattr(self.market, "purchases", []),
            key=lambda row: (_money(getattr(row, "total_cost", 0)), _text(getattr(row, "item", ""))),
            reverse=True,
        )
        best = [_text(getattr(row, "item", "")) for row in purchases[:5] if _text(getattr(row, "item", ""))]
        strongest = [row.item_name for row in opportunities[:5]]
        return AcquisitionPerformanceReport(
            best_acquisitions=best or strongest[:3],
            biggest_upgrades=[
                f"{row.get('country', '')} {row.get('denomination', '')} {row.get('year', '')}".strip()
                for row in upgrades[:5]
            ],
            highest_collection_impact=strongest[:5],
            strongest_opportunity_captures=[
                f"{row.item_name} (score {row.score})" for row in opportunities[:5]
            ],
            highest_confidence_purchases=best[:5] or strongest[:5],
        )

    def series_progress_report(self, snapshot_report: Optional[CollectionSnapshotReport] = None) -> SeriesProgressReport:
        reports = self.series_tracker.generate_reports()
        nearest = [
            f"{report.series_name} ({report.completion_percentage:.1f}% complete)"
            for report in sorted(reports, key=lambda row: (-row.completion_percentage, row.missing_count, row.series_name))
            if 0 < report.completion_percentage < 100
        ][:5]
        neglected = [
            f"{report.series_name} ({report.completion_percentage:.1f}% complete; {report.missing_count} missing)"
            for report in sorted(reports, key=lambda row: (row.completion_percentage, -row.missing_count, row.series_name))
            if report.missing_count > 0
        ][:5]
        strongest = [
            f"{report.series_name} (priority {report.priority_score})"
            for report in sorted(reports, key=lambda row: (-row.priority_score, row.series_name))
        ][:5]
        progress = {}
        if snapshot_report:
            progress = {
                row.series_name: row.completion_delta
                for row in snapshot_report.series_progress
            }
        return SeriesProgressReport(
            series_reports=reports,
            nearest_completions=nearest,
            neglected_series=neglected,
            strongest_performing_series=strongest,
            progress_since_last_snapshot=progress,
        )

    def budget_allocation_report(self) -> BudgetAllocationReport:
        counts = {
            "Newfoundland": 0,
            "Canadian silver": 0,
            "Banknotes": 0,
            "Slabs": 0,
            "Upgrades": len(self.intelligence.detect_upgrade_candidates()),
            "Duplicates": len(self.intelligence.detect_duplicates()),
            "Other": 0,
        }
        values = {key: 0.0 for key in counts}
        for item in self.items:
            categories = self._item_categories(item)
            if not categories:
                categories = ["Other"]
            value = _money(getattr(item, "estimate_cad", 0)) * _quantity(item)
            for category in categories:
                counts[category] = counts.get(category, 0) + _quantity(item)
                values[category] = round(values.get(category, 0.0) + value, 2)
        return BudgetAllocationReport(counts, values)

    def collection_health_score(
        self,
        growth: Optional[CollectionGrowthReport] = None,
        series: Optional[SeriesProgressReport] = None,
        budget: Optional[BudgetAllocationReport] = None,
    ) -> CollectionHealthScore:
        growth = growth or self.collection_growth_report()
        series = series or self.series_progress_report(growth.snapshot_comparison)
        quality = CollectionQualityEngine(self.items, self.want_list).generate_report()
        integrity = CollectionIntegrityAudit(
            self.items,
            photo_records=self.photo_records,
            market_awareness_engine=self.market,
            shopping_candidates=self.shopping_candidates,
        ).run()
        duplicate_count = len(self.intelligence.detect_duplicates())
        snapshot_score = 100 if growth.snapshot_comparison and growth.snapshot_comparison.previous_snapshot else 60
        duplicate_score = max(0, 100 - duplicate_count * 12)
        want_alignment = 100 if self.want_list else 70
        backup_score = integrity.integrity_score.category_scores.get("backups", 75)
        photo_score = int(min(max(growth.snapshot_comparison.current_snapshot.photo_coverage if growth.snapshot_comparison else 0, 0), 100))
        series_score = int(round(sum(row.completion_percentage for row in series.series_reports) / len(series.series_reports))) if series.series_reports else 50
        categories = {
            "backup_readiness": backup_score,
            "collection_integrity": integrity.integrity_score.score,
            "photo_coverage": photo_score,
            "documentation_coverage": quality.category_score("Certification"),
            "duplicate_control": duplicate_score,
            "want_list_alignment": want_alignment,
            "snapshot_coverage": snapshot_score,
            "series_progress": series_score,
        }
        score = int(round(sum(categories.values()) / len(categories)))
        explanation = [
            f"Integrity score {integrity.integrity_score.score}/100.",
            f"Quality score {quality.overall_quality_score}/100.",
            f"Duplicate groups detected: {duplicate_count}.",
            f"Snapshot comparison {'available' if snapshot_score == 100 else 'limited'}.",
        ]
        return CollectionHealthScore(score=max(0, min(100, score)), category_scores=categories, explanation=explanation)

    def _estimated_collection_value(self) -> float:
        return round(sum(_money(getattr(item, "estimate_cad", 0)) * _quantity(item) for item in self.items), 2)

    def _silver_count(self) -> int:
        return sum(_quantity(item) for item in self.items if self._is_silver(item))

    def _slab_count(self) -> int:
        slab_terms = ("pcgs", "ngc", "iccs", "cert", "certified", "slab")
        return sum(_quantity(item) for item in self.items if any(term in self._item_text(item) for term in slab_terms))

    def _banknote_count(self) -> int:
        return sum(_quantity(item) for item in self.items if "banknote" in self._item_text(item) or "note" in _norm(getattr(item, "denomination", "")))

    def _newfoundland_count(self) -> int:
        return sum(_quantity(item) for item in self.items if "newfoundland" in _norm(getattr(item, "country", "")))

    def _count_custom_category(self, terms: Iterable[str]) -> int:
        normalized = [_norm(term) for term in terms or [] if _norm(term)]
        return sum(_quantity(item) for item in self.items if any(term in self._item_text(item) for term in normalized))

    def _item_categories(self, item: Any) -> List[str]:
        categories = []
        text = self._item_text(item)
        if "newfoundland" in _norm(getattr(item, "country", "")):
            categories.append("Newfoundland")
        if self._is_silver(item):
            categories.append("Canadian silver")
        if "banknote" in text or "note" in _norm(getattr(item, "denomination", "")):
            categories.append("Banknotes")
        if any(term in text for term in ("pcgs", "ngc", "iccs", "cert", "certified", "slab")):
            categories.append("Slabs")
        return categories

    def _is_silver(self, item: Any) -> bool:
        country = _norm(getattr(item, "country", ""))
        denom = _norm(getattr(item, "denomination", ""))
        text = self._item_text(item)
        return ("canada" in country or "newfoundland" in country) and (
            "silver" in text or any(term in denom for term in SILVER_DENOMINATION_TERMS)
        )

    def _item_text(self, item: Any) -> str:
        return _norm(" ".join([
            _text(getattr(item, "country", "")),
            _text(getattr(item, "denomination", "")),
            _text(getattr(item, "year", "")),
            _text(getattr(item, "grade", "")),
            _text(getattr(item, "notes", "")),
            _text(getattr(item, "comments", "")),
            _text(getattr(item, "title", "")),
        ]))

    def _opportunity_rows(self) -> List[OpportunityReport]:
        try:
            return OpportunityEngine(
                self.items,
                self.want_list,
                market_awareness_engine=self.market,
            ).generate_report(limit=10).top_overall
        except Exception:
            return []

    def _strengths(
        self,
        growth: CollectionGrowthReport,
        series: SeriesProgressReport,
        health: CollectionHealthScore,
        acquisition: AcquisitionPerformanceReport,
    ) -> List[str]:
        rows = []
        if growth.newfoundland_count:
            rows.append(f"Newfoundland representation: {growth.newfoundland_count} items.")
        if growth.silver_holdings:
            rows.append(f"Canadian/Newfoundland silver represented by {growth.silver_holdings} holdings.")
        if health.score >= 75:
            rows.append(f"Portfolio health score is strong at {health.score}/100.")
        if series.nearest_completions:
            rows.append(f"Series nearing completion: {series.nearest_completions[0]}.")
        if acquisition.strongest_opportunity_captures:
            rows.append(f"Opportunity pipeline available: {acquisition.strongest_opportunity_captures[0]}.")
        return rows[:5]

    def _weaknesses(self, growth: CollectionGrowthReport, series: SeriesProgressReport, health: CollectionHealthScore) -> List[str]:
        rows = []
        duplicate_count = growth.custom_category_counts.get("Duplicates", 0)
        if duplicate_count:
            rows.append(f"Duplicate ownership groups need review: {duplicate_count}.")
        if series.neglected_series:
            rows.append(f"Neglected supported series: {series.neglected_series[0]}.")
        if health.category_scores.get("photo_coverage", 0) < 50:
            rows.append("Photo coverage is limited for portfolio documentation.")
        if health.category_scores.get("snapshot_coverage", 0) < 100:
            rows.append("Snapshot history is limited; create snapshots after major collection changes.")
        if not rows and not self.items:
            rows.append("No collection records available for portfolio performance analysis.")
        return rows[:5]

    def _opportunities(self, acquisition: AcquisitionPerformanceReport, series: SeriesProgressReport) -> List[str]:
        rows = []
        rows.extend(acquisition.strongest_opportunity_captures[:3])
        rows.extend(series.nearest_completions[:3])
        return rows[:5]

    def _risks(self, growth: CollectionGrowthReport, health: CollectionHealthScore) -> List[str]:
        rows = []
        if health.score < 70:
            rows.append(f"Portfolio health score needs attention: {health.score}/100.")
        if growth.custom_category_counts.get("Duplicates", 0):
            rows.append("Duplicate groups may distort performance and focus metrics.")
        if health.category_scores.get("backup_readiness", 0) < 80:
            rows.append("Backup readiness should be reviewed before relying on portfolio history.")
        if not growth.snapshot_comparison or not growth.snapshot_comparison.previous_snapshot:
            rows.append("Historical comparison is limited until at least one prior snapshot exists.")
        return rows[:5]

    def _focus_areas(self, opportunities: List[str], weaknesses: List[str], series: SeriesProgressReport) -> List[str]:
        rows = []
        if series.nearest_completions:
            rows.append(f"Focus on nearest series completion: {series.nearest_completions[0]}.")
        if opportunities:
            rows.append(f"Review top portfolio opportunity: {opportunities[0]}.")
        if weaknesses:
            rows.append(f"Address portfolio weakness: {weaknesses[0]}.")
        if not rows:
            rows.append("Create or update a collection snapshot to establish a performance baseline.")
        return rows[:5]
