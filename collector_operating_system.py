"""Collector Operating System consolidation reports for v2.0."""

import csv
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from collection_dashboard import CollectionDashboard, CollectionDashboardData
from collection_quality import CollectionQualityEngine, CollectionQualityReport
from market_awareness import MarketAwarenessEngine
from photo_vault import PhotoRecord
from series_tracker import SeriesReport, SeriesTracker
from smart_shopping_assistant import (
    ShoppingCandidate,
    ShoppingRecommendationReport,
    SmartShoppingAssistant,
)


@dataclass
class PersistenceFinding:
    area: str
    survives_restart: bool
    storage_location: str
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "area": self.area,
            "survives_restart": self.survives_restart,
            "storage_location": self.storage_location,
            "notes": self.notes,
        }


@dataclass
class CollectorHomeData:
    collection_summary: Dict[str, Any]
    best_next_purchase: str = ""
    highest_impact_opportunity: str = ""
    top_want_list_target: str = ""
    series_closest_to_completion: str = ""
    collection_quality_score: int = 0
    recent_market_activity: List[str] = field(default_factory=list)
    photo_coverage_summary: str = ""
    workflow_steps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "collection_summary": dict(self.collection_summary),
            "best_next_purchase": self.best_next_purchase,
            "highest_impact_opportunity": self.highest_impact_opportunity,
            "top_want_list_target": self.top_want_list_target,
            "series_closest_to_completion": self.series_closest_to_completion,
            "collection_quality_score": self.collection_quality_score,
            "recent_market_activity": list(self.recent_market_activity),
            "photo_coverage_summary": self.photo_coverage_summary,
            "workflow_steps": list(self.workflow_steps),
        }


@dataclass
class CollectionHealthReport:
    dashboard_data: CollectionDashboardData
    quality_report: CollectionQualityReport
    series_reports: List[SeriesReport] = field(default_factory=list)
    shopping_report: Optional[ShoppingRecommendationReport] = None
    market_summary: Dict[str, Any] = field(default_factory=dict)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    priorities: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    persistence_findings: List[PersistenceFinding] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dashboard_data": self.dashboard_data.snapshot.to_dict(),
            "quality_report": self.quality_report.to_dict(),
            "series_reports": [report.to_dict() for report in self.series_reports],
            "shopping_report": self.shopping_report.to_dict() if self.shopping_report else None,
            "market_summary": dict(self.market_summary),
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "priorities": list(self.priorities),
            "recommended_actions": list(self.recommended_actions),
            "persistence_findings": [finding.to_dict() for finding in self.persistence_findings],
        }


class CollectorHome:
    """Unified collector-facing entry point composed from existing engines."""

    WORKFLOW_STEPS = [
        "Review Collector Home",
        "Open Listing Analyzer for candidate details",
        "Check Acquisition Impact",
        "Compare opportunities in Smart Shopping Assistant",
        "Reference Photo Vault records",
        "Record observed or purchase data in Market Awareness",
        "Review Dashboard and Collection Health Report",
    ]

    def __init__(
        self,
        items: Iterable[Any],
        want_list_intents: Optional[Iterable[Any]] = None,
        shopping_candidates: Optional[Iterable[ShoppingCandidate]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
        photo_records: Optional[Iterable[PhotoRecord]] = None,
    ):
        self.items = list(items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.shopping_candidates = list(shopping_candidates or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()
        self.photo_records = list(photo_records or [])

    def generate_home(self) -> CollectorHomeData:
        dashboard = CollectionDashboard(
            self.items,
            self.want_list_intents,
            photo_records=self.photo_records,
            market_awareness_engine=self.market_awareness_engine,
            shopping_candidates=self.shopping_candidates,
        ).generate_dashboard()
        quality = dashboard.quality_report or CollectionQualityEngine(
            self.items,
            self.want_list_intents,
        ).generate_report()
        shopping = dashboard.shopping_report or SmartShoppingAssistant(
            self.items,
            self.want_list_intents,
            self.market_awareness_engine,
        ).generate_report(
            self.shopping_candidates,
            include_want_list_targets=bool(self.want_list_intents),
            limit=5,
        )
        series_reports = dashboard.series_tracker_reports or SeriesTracker(
            self.items,
            self.want_list_intents,
        ).generate_reports()

        return CollectorHomeData(
            collection_summary=dashboard.snapshot.to_dict(),
            best_next_purchase=self._recommendation_label(shopping.best_next_purchase),
            highest_impact_opportunity=self._recommendation_label(shopping.highest_impact_candidate),
            top_want_list_target=self._recommendation_label(shopping.highest_priority_want_list_target),
            series_closest_to_completion=self._closest_series(series_reports),
            collection_quality_score=quality.overall_quality_score,
            recent_market_activity=list((dashboard.market_report.recent_activity if dashboard.market_report else [])[:5]),
            photo_coverage_summary=self._photo_summary(dashboard),
            workflow_steps=list(self.WORKFLOW_STEPS),
        )

    def format_markdown(self) -> str:
        home = self.generate_home()
        lines = [
            "# Collector Home",
            "",
            "## Collection Summary",
            "",
        ]
        for key, value in home.collection_summary.items():
            lines.append(f"- {key}: {value}")
        lines.extend([
            "",
            "## Focus",
            "",
            f"- Best next purchase: {home.best_next_purchase or 'No opportunity available'}",
            f"- Highest impact opportunity: {home.highest_impact_opportunity or 'No opportunity available'}",
            f"- Top WANT_LIST target: {home.top_want_list_target or 'No WANT_LIST target available'}",
            f"- Series closest to completion: {home.series_closest_to_completion or 'No supported series available'}",
            f"- Collection quality score: {home.collection_quality_score}",
            f"- Photo coverage: {home.photo_coverage_summary or 'No photo coverage data'}",
            "",
            "## Recent Market Activity",
            "",
        ])
        if home.recent_market_activity:
            lines.extend(f"- {activity}" for activity in home.recent_market_activity)
        else:
            lines.append("- No market activity recorded.")
        lines.extend(["", "## Collector Workflow", ""])
        lines.extend(f"{index}. {step}" for index, step in enumerate(home.workflow_steps, 1))
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_markdown())
            return True
        except Exception as exc:
            print(f"Error exporting collector home markdown: {exc}")
            return False

    def export_csv(self, output_path: str) -> bool:
        try:
            home = self.generate_home()
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Section", "Name", "Value"])
                for key, value in home.collection_summary.items():
                    writer.writerow(["Collection Summary", key, value])
                writer.writerow(["Focus", "Best Next Purchase", home.best_next_purchase])
                writer.writerow(["Focus", "Highest Impact Opportunity", home.highest_impact_opportunity])
                writer.writerow(["Focus", "Top WANT_LIST Target", home.top_want_list_target])
                writer.writerow(["Focus", "Series Closest To Completion", home.series_closest_to_completion])
                writer.writerow(["Focus", "Collection Quality Score", home.collection_quality_score])
                writer.writerow(["Focus", "Photo Coverage", home.photo_coverage_summary])
                for activity in home.recent_market_activity:
                    writer.writerow(["Recent Market Activity", activity, ""])
                for index, step in enumerate(home.workflow_steps, 1):
                    writer.writerow(["Collector Workflow", index, step])
            return True
        except Exception as exc:
            print(f"Error exporting collector home CSV: {exc}")
            return False

    @staticmethod
    def _recommendation_label(recommendation: Any) -> str:
        if not recommendation:
            return ""
        return f"{recommendation.item_name} ({recommendation.recommendation_status}, score {recommendation.opportunity_score})"

    @staticmethod
    def _closest_series(series_reports: List[SeriesReport]) -> str:
        candidates = [report for report in series_reports if report.missing_count > 0]
        if not candidates:
            candidates = list(series_reports)
        if not candidates:
            return ""
        row = sorted(candidates, key=lambda report: (-report.completion_percentage, report.missing_count, report.series_name))[0]
        return f"{row.series_name} ({row.completion_percentage:.1f}% complete)"

    @staticmethod
    def _photo_summary(dashboard: CollectionDashboardData) -> str:
        coverage = dashboard.photo_coverage
        if not coverage:
            return ""
        return f"{coverage.items_with_photos}/{coverage.total_collection_items} items with photos ({coverage.photo_coverage_percentage:.1f}%)"


class CollectionHealthReportEngine:
    """Generate a consolidated health report from existing collection systems."""

    def __init__(
        self,
        items: Iterable[Any],
        want_list_intents: Optional[Iterable[Any]] = None,
        shopping_candidates: Optional[Iterable[ShoppingCandidate]] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
        photo_records: Optional[Iterable[PhotoRecord]] = None,
    ):
        self.items = list(items or [])
        self.want_list_intents = list(want_list_intents or [])
        self.shopping_candidates = list(shopping_candidates or [])
        self.market_awareness_engine = market_awareness_engine or MarketAwarenessEngine()
        self.photo_records = list(photo_records or [])

    def generate_report(self) -> CollectionHealthReport:
        dashboard = CollectionDashboard(
            self.items,
            self.want_list_intents,
            photo_records=self.photo_records,
            market_awareness_engine=self.market_awareness_engine,
            shopping_candidates=self.shopping_candidates,
        ).generate_dashboard()
        quality = dashboard.quality_report or CollectionQualityEngine(
            self.items,
            self.want_list_intents,
        ).generate_report()
        series_reports = dashboard.series_tracker_reports or SeriesTracker(
            self.items,
            self.want_list_intents,
        ).generate_reports()
        shopping = dashboard.shopping_report or SmartShoppingAssistant(
            self.items,
            self.want_list_intents,
            self.market_awareness_engine,
        ).generate_report(
            self.shopping_candidates,
            include_want_list_targets=bool(self.want_list_intents),
            limit=5,
        )
        market = dashboard.market_report.summary.to_dict() if dashboard.market_report else {}
        return CollectionHealthReport(
            dashboard_data=dashboard,
            quality_report=quality,
            series_reports=series_reports,
            shopping_report=shopping,
            market_summary=market,
            strengths=[f"{finding.title}: {finding.detail}" for finding in quality.strengths[:5]],
            weaknesses=[f"{finding.title}: {finding.detail}" for finding in quality.weaknesses[:5]],
            priorities=self._priorities(dashboard, shopping, series_reports),
            recommended_actions=[
                f"{action.rank}. {action.action}: {action.why_it_matters} Expected impact: {action.expected_impact}"
                for action in quality.recommended_actions[:5]
            ],
            persistence_findings=self.persistence_audit(),
        )

    def persistence_audit(self) -> List[PersistenceFinding]:
        return [
            PersistenceFinding(
                "Collection JSON",
                True,
                "data/collection.json",
                "Owned collection records persist through CoinCollection JSON storage.",
            ),
            PersistenceFinding(
                "Shared Session Context",
                False,
                "Runtime memory",
                "Workbook and WANT_LIST context are intentionally per-session and must be reloaded after restart.",
            ),
            PersistenceFinding(
                "Market Awareness",
                False,
                "Runtime/local supplied records",
                "Market records are deterministic local structures; persistence can be added later without changing scoring logic.",
            ),
            PersistenceFinding(
                "Photo Vault",
                False,
                "Runtime/local supplied records",
                "Photo records link local file paths and cert metadata but do not yet have a dedicated persistent database.",
            ),
            PersistenceFinding(
                "Series Definitions",
                True,
                "series_definitions.py",
                "Supported series definitions are version-controlled code data.",
            ),
            PersistenceFinding(
                "Shopping Assistant Candidates",
                False,
                "Runtime/manual input",
                "Shopping opportunities are supplied at runtime or derived from staged WANT_LIST and local observations.",
            ),
        ]

    def format_markdown(self) -> str:
        report = self.generate_report()
        lines = [
            "# Collection Health Report",
            "",
            "## Dashboard Summary",
            "",
        ]
        for key, value in report.dashboard_data.snapshot.to_dict().items():
            lines.append(f"- {key}: {value}")
        lines.extend([
            "",
            "## Quality Summary",
            "",
            f"- Overall quality score: {report.quality_report.overall_quality_score}",
            "",
            "## Strengths",
            "",
        ])
        lines.extend(f"- {value}" for value in report.strengths) if report.strengths else lines.append("- No strengths available.")
        lines.extend(["", "## Weaknesses", ""])
        lines.extend(f"- {value}" for value in report.weaknesses) if report.weaknesses else lines.append("- No weaknesses available.")
        lines.extend(["", "## Priorities", ""])
        lines.extend(f"- {value}" for value in report.priorities) if report.priorities else lines.append("- No priorities available.")
        lines.extend(["", "## Recommended Actions", ""])
        lines.extend(f"- {value}" for value in report.recommended_actions) if report.recommended_actions else lines.append("- No recommended actions available.")
        lines.extend(["", "## Series Summary", ""])
        for series in report.series_reports[:8]:
            lines.append(f"- {series.series_name}: {series.completion_percentage:.1f}% complete; priority {series.priority_score}")
        lines.extend(["", "## Market Summary", ""])
        for key, value in sorted(report.market_summary.items()):
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Persistence Audit", ""])
        for finding in report.persistence_findings:
            survives = "yes" if finding.survives_restart else "no"
            lines.append(f"- {finding.area}: survives restart {survives}; {finding.storage_location}. {finding.notes}")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_markdown())
            return True
        except Exception as exc:
            print(f"Error exporting collection health report markdown: {exc}")
            return False

    def export_csv(self, output_path: str) -> bool:
        try:
            report = self.generate_report()
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Section", "Name", "Value", "Detail"])
                for key, value in report.dashboard_data.snapshot.to_dict().items():
                    writer.writerow(["Dashboard Summary", key, value, ""])
                writer.writerow(["Quality Summary", "Overall Quality Score", report.quality_report.overall_quality_score, ""])
                for strength in report.strengths:
                    writer.writerow(["Strength", strength, "", ""])
                for weakness in report.weaknesses:
                    writer.writerow(["Weakness", weakness, "", ""])
                for priority in report.priorities:
                    writer.writerow(["Priority", priority, "", ""])
                for action in report.recommended_actions:
                    writer.writerow(["Recommended Action", action, "", ""])
                for series in report.series_reports[:8]:
                    writer.writerow(["Series Summary", series.series_name, f"{series.completion_percentage:.1f}%", f"Priority {series.priority_score}"])
                for key, value in sorted(report.market_summary.items()):
                    writer.writerow(["Market Summary", key, value, ""])
                for finding in report.persistence_findings:
                    writer.writerow(["Persistence Audit", finding.area, "yes" if finding.survives_restart else "no", f"{finding.storage_location}: {finding.notes}"])
            return True
        except Exception as exc:
            print(f"Error exporting collection health report CSV: {exc}")
            return False

    @staticmethod
    def _priorities(
        dashboard: CollectionDashboardData,
        shopping: Optional[ShoppingRecommendationReport],
        series_reports: List[SeriesReport],
    ) -> List[str]:
        rows = []
        if shopping and shopping.best_next_purchase:
            rows.append(f"Best next purchase: {shopping.best_next_purchase.item_name} ({shopping.best_next_purchase.recommendation_status})")
        if shopping and shopping.highest_impact_candidate:
            rows.append(f"Highest impact opportunity: {shopping.highest_impact_candidate.item_name}")
        if shopping and shopping.highest_priority_want_list_target:
            rows.append(f"Top WANT_LIST target: {shopping.highest_priority_want_list_target.item_name}")
        if series_reports:
            top_series = sorted(series_reports, key=lambda report: (-report.priority_score, report.series_name))[0]
            rows.append(f"Series focus: {top_series.series_name} ({top_series.completion_percentage:.1f}% complete)")
        for item in dashboard.top_collection_priorities[:3]:
            rows.append(f"{item.title}: {item.detail}")
        return rows[:8]
