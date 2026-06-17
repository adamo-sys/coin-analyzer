"""Actionable collection dashboard built from existing analysis engines."""

import csv
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from collection_intelligence import CollectionIntelligenceEngine, SILVER_DENOMINATION_TERMS
from collection_quality import CollectionQualityEngine, CollectionQualityReport
from series_tracker import SeriesReport, SeriesTracker


@dataclass
class DashboardItem:
    title: str
    detail: str
    priority: int = 0
    action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "detail": self.detail,
            "priority": self.priority,
            "action": self.action,
        }


@dataclass
class SeriesCompletion:
    series: str
    years_owned: str
    missing_years: str
    completion_percentage: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "series": self.series,
            "years_owned": self.years_owned,
            "missing_years": self.missing_years,
            "completion_percentage": self.completion_percentage,
        }


@dataclass
class CollectionSnapshot:
    total_collection_items: int
    total_want_list_items: int
    total_duplicate_items: int
    total_upgrade_opportunities: int
    collection_countries_count: int
    collection_denominations_count: int
    silver_items_count: int
    certified_items_count: int

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class CollectionDashboardData:
    snapshot: CollectionSnapshot
    quality_report: Optional[CollectionQualityReport] = None
    series_tracker_reports: List[SeriesReport] = field(default_factory=list)
    top_potential_collection_improvements: List[DashboardItem] = field(default_factory=list)
    top_series_focus: List[DashboardItem] = field(default_factory=list)
    top_collection_priorities: List[DashboardItem] = field(default_factory=list)
    best_upgrade_opportunities: List[DashboardItem] = field(default_factory=list)
    want_list_priorities: List[DashboardItem] = field(default_factory=list)
    collection_gaps: List[DashboardItem] = field(default_factory=list)
    series_completion: List[SeriesCompletion] = field(default_factory=list)
    collection_evolution: List[DashboardItem] = field(default_factory=list)


class CollectionDashboard:
    """Generate an actionable collector-facing dashboard."""

    def __init__(self, items: Iterable[Any], staged_want_list_intents: Optional[Iterable[Any]] = None):
        self.items = list(items or [])
        self.staged_want_list_intents = list(staged_want_list_intents or [])
        self.intelligence = CollectionIntelligenceEngine(self.items)

    def generate_dashboard(self) -> CollectionDashboardData:
        gap_report = self.intelligence.generate_gap_report()
        duplicates = gap_report["duplicates"]
        upgrades = gap_report["upgrade_candidates"]
        countries = gap_report["countries"]
        denominations = gap_report["denominations"]

        snapshot = CollectionSnapshot(
            total_collection_items=len(self.items),
            total_want_list_items=len(self.staged_want_list_intents),
            total_duplicate_items=sum(max(0, duplicate["count"] - 1) for duplicate in duplicates),
            total_upgrade_opportunities=len(upgrades),
            collection_countries_count=len(countries),
            collection_denominations_count=len(denominations),
            silver_items_count=self._silver_items_count(),
            certified_items_count=self._certified_items_count(),
        )

        series_completion = self._series_completion(gap_report["series_rows"])
        want_targets = self.intelligence.generate_want_list(
            limit=10,
            staged_want_list_intents=self.staged_want_list_intents,
        )
        quality_report = CollectionQualityEngine(
            self.items,
            self.staged_want_list_intents,
        ).generate_report()
        series_reports = SeriesTracker(
            self.items,
            self.staged_want_list_intents,
        ).generate_reports()

        return CollectionDashboardData(
            snapshot=snapshot,
            quality_report=quality_report,
            series_tracker_reports=series_reports,
            top_potential_collection_improvements=self._quality_improvement_panel(quality_report),
            top_series_focus=self._series_focus_panel(series_reports),
            top_collection_priorities=self._top_priorities(want_targets, series_completion, upgrades),
            best_upgrade_opportunities=self._upgrade_panel(upgrades),
            want_list_priorities=self._want_list_panel(want_targets),
            collection_gaps=self._gap_panel(gap_report["series_rows"]),
            series_completion=series_completion,
            collection_evolution=self._collection_evolution(),
        )

    def format_markdown(self) -> str:
        data = self.generate_dashboard()
        s = data.snapshot
        lines = [
            "# Collection Dashboard",
            "",
            "## Collection Snapshot",
            "",
            f"- Total collection items: {s.total_collection_items}",
            f"- Total WANT_LIST items: {s.total_want_list_items}",
            f"- Total duplicate items: {s.total_duplicate_items}",
            f"- Total upgrade opportunities: {s.total_upgrade_opportunities}",
            f"- Countries represented: {s.collection_countries_count}",
            f"- Denominations represented: {s.collection_denominations_count}",
            f"- Silver items: {s.silver_items_count}",
            f"- Certified items: {s.certified_items_count}",
        ]
        if data.quality_report:
            lines.extend([
                "",
                "## Collection Quality",
                "",
                f"- Overall quality score: {data.quality_report.overall_quality_score}",
            ])
            for category in data.quality_report.category_scores:
                lines.append(f"- {category.name}: {category.score}")
            lines.extend(self._format_quality_findings("Top Strengths", data.quality_report.strengths))
            lines.extend(self._format_quality_findings("Top Weaknesses", data.quality_report.weaknesses))
            lines.extend(["", "## Top Recommended Actions", ""])
            if data.quality_report.recommended_actions:
                for action in data.quality_report.recommended_actions[:5]:
                    lines.append(
                        f"- {action.rank}. {action.action}: {action.why_it_matters} "
                        f"Expected impact: {action.expected_impact}"
                    )
            else:
                lines.append("- No recommended actions generated.")
        lines.extend(self._format_items("Top Collection Priorities", data.top_collection_priorities))
        lines.extend(self._format_items("Top Potential Collection Improvements", data.top_potential_collection_improvements))
        lines.extend(self._format_items("Top Series", data.top_series_focus))
        lines.extend(self._format_items("Best Upgrade Opportunities", data.best_upgrade_opportunities))
        lines.extend(self._format_items("WANT_LIST Priorities", data.want_list_priorities))
        lines.extend(self._format_items("Collection Gaps", data.collection_gaps))
        lines.extend(["", "## Series Completion", ""])
        if data.series_completion:
            for row in data.series_completion:
                lines.append(f"- {row.series}: {row.completion_percentage:.1f}% complete")
        else:
            lines.append("- No series completion data available.")
        lines.extend(self._format_items("Collection Evolution", data.collection_evolution))
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_markdown())
            return True
        except Exception as exc:
            print(f"Error exporting collection dashboard markdown: {exc}")
            return False

    def export_csv(self, output_path: str) -> bool:
        try:
            data = self.generate_dashboard()
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Section", "Title", "Detail", "Priority", "Action"])
                for key, value in data.snapshot.to_dict().items():
                    writer.writerow(["Snapshot", key, value, "", ""])
                if data.quality_report:
                    writer.writerow(["Quality", "Overall Quality Score", data.quality_report.overall_quality_score, "", ""])
                    for category in data.quality_report.category_scores:
                        writer.writerow(["Quality Category", category.name, category.explanation, category.score, ""])
                    for finding in data.quality_report.strengths:
                        writer.writerow(["Quality Strength", finding.title, finding.detail, finding.impact_score, ""])
                    for finding in data.quality_report.weaknesses:
                        writer.writerow(["Quality Weakness", finding.title, finding.detail, finding.impact_score, ""])
                    for action in data.quality_report.recommended_actions[:5]:
                        writer.writerow([
                            "Quality Recommended Action",
                            action.action,
                            action.why_it_matters,
                            action.priority_score,
                            action.expected_impact,
                        ])
                self._write_items(writer, "Top Collection Priorities", data.top_collection_priorities)
                self._write_items(writer, "Top Potential Collection Improvements", data.top_potential_collection_improvements)
                self._write_items(writer, "Top Series", data.top_series_focus)
                self._write_items(writer, "Best Upgrade Opportunities", data.best_upgrade_opportunities)
                self._write_items(writer, "WANT_LIST Priorities", data.want_list_priorities)
                self._write_items(writer, "Collection Gaps", data.collection_gaps)
                for row in data.series_completion:
                    writer.writerow([
                        "Series Completion",
                        row.series,
                        f"{row.completion_percentage:.1f}% complete; missing {row.missing_years or 'none'}",
                        "",
                        "Review closest date-run completions.",
                    ])
                self._write_items(writer, "Collection Evolution", data.collection_evolution)
            return True
        except Exception as exc:
            print(f"Error exporting collection dashboard CSV: {exc}")
            return False

    def _top_priorities(self, targets, series_completion, upgrades) -> List[DashboardItem]:
        priorities: List[DashboardItem] = []
        for row in series_completion[:3]:
            if row.missing_years:
                priorities.append(DashboardItem(
                    title=f"{row.series} nearing completion",
                    detail=f"{row.completion_percentage:.1f}% complete; missing {row.missing_years}",
                    priority=int(row.completion_percentage),
                    action="Focus on missing dates with the smallest remaining gap.",
                ))
        for target in targets[:3]:
            priorities.append(DashboardItem(
                title=target.coin_label,
                detail=target.reason,
                priority=target.priority_score,
                action="Evaluate as next acquisition target.",
            ))
        for upgrade in upgrades[:2]:
            priorities.append(DashboardItem(
                title=f"{upgrade['country']} {upgrade['denomination']} {upgrade['year']}",
                detail=upgrade["reason"],
                priority=60,
                action="Consider keeping best grade and replacing lower-grade duplicates.",
            ))
        return sorted(priorities, key=lambda item: (-item.priority, item.title))[:8]

    def _upgrade_panel(self, upgrades) -> List[DashboardItem]:
        rows = []
        for upgrade in upgrades[:8]:
            rows.append(DashboardItem(
                title=f"{upgrade['country']} {upgrade['denomination']} {upgrade['year']}",
                detail=f"Current best grade: {upgrade['current_best_grade']}",
                priority=60,
                action=upgrade["reason"],
            ))
        return rows

    def _quality_improvement_panel(self, quality_report: CollectionQualityReport) -> List[DashboardItem]:
        rows = []
        for action in quality_report.recommended_actions[:8]:
            rows.append(DashboardItem(
                title=action.action,
                detail=action.why_it_matters,
                priority=action.priority_score,
                action=action.expected_impact,
            ))
        return rows

    def _series_focus_panel(self, series_reports: List[SeriesReport]) -> List[DashboardItem]:
        rows = []
        for report in sorted(series_reports, key=lambda row: (-row.priority_score, -row.completion_percentage, row.series_name))[:8]:
            detail = (
                f"{report.completion_percentage:.1f}% complete; "
                f"owned {report.owned_count}; missing {report.missing_count}; "
                f"WANT_LIST {report.want_list_count}; upgrades {report.upgrade_count}"
            )
            rows.append(DashboardItem(
                title=report.series_name,
                detail=detail,
                priority=report.priority_score,
                action="Review missing dates and priority targets for this series.",
            ))
        return rows

    def _want_list_panel(self, targets) -> List[DashboardItem]:
        rows = []
        for target in targets:
            if target.target_type in {"Explicit WANT_LIST", "Want List Target"} or "WANT_LIST" in target.reason:
                rows.append(DashboardItem(
                    title=target.coin_label,
                    detail=target.reason,
                    priority=target.priority_score,
                    action="Review active WANT_LIST opportunity.",
                ))
        if not rows:
            for target in targets[:5]:
                rows.append(DashboardItem(
                    title=target.coin_label,
                    detail=target.reason,
                    priority=target.priority_score,
                    action="Review acquisition candidate.",
                ))
        return rows[:8]

    def _gap_panel(self, series_rows) -> List[DashboardItem]:
        rows = []
        for row in series_rows[:8]:
            if row["missing_years"]:
                rows.append(DashboardItem(
                    title=row["series"],
                    detail=f"Missing: {row['missing_years']} | Completion: {row['completion_percentage']:.1f}%",
                    priority=int(row["completion_percentage"]),
                    action=row["suggested_next_acquisitions"],
                ))
        return rows

    def _series_completion(self, series_rows) -> List[SeriesCompletion]:
        rows = [
            SeriesCompletion(
                series=row["series"],
                years_owned=row["years_owned"],
                missing_years=row["missing_years"],
                completion_percentage=row["completion_percentage"],
            )
            for row in series_rows
        ]
        return sorted(rows, key=lambda row: (-row.completion_percentage, row.series))[:10]

    def _collection_evolution(self) -> List[DashboardItem]:
        by_period: Dict[str, int] = {}
        for item in self.items:
            date_added = str(getattr(item, "date_added", "") or "")
            period = date_added[:7] if len(date_added) >= 7 else "Unknown"
            by_period[period] = by_period.get(period, 0) + 1
        return [
            DashboardItem(
                title=period,
                detail=f"{count} item(s) added",
                priority=count,
                action="Use as basic collection growth signal.",
            )
            for period, count in sorted(by_period.items(), reverse=True)[:6]
        ]

    def _silver_items_count(self) -> int:
        return sum(1 for item in self.items if self._is_silver_denomination(getattr(item, "denomination", "")))

    def _certified_items_count(self) -> int:
        count = 0
        for item in self.items:
            text = " ".join([
                str(getattr(item, "certifier", "") or ""),
                str(getattr(item, "certification_number", "") or ""),
                str(getattr(item, "notes", "") or ""),
                str(getattr(item, "comments", "") or ""),
            ]).lower()
            if any(term in text for term in ["pcgs", "ngc", "iccs", "anacs", "cert", "slab"]):
                count += 1
        return count

    @staticmethod
    def _is_silver_denomination(denomination: str) -> bool:
        lowered = (denomination or "").lower()
        return any(term in lowered for term in SILVER_DENOMINATION_TERMS)

    @staticmethod
    def _format_items(title: str, items: List[DashboardItem]) -> List[str]:
        lines = ["", f"## {title}", ""]
        if not items:
            lines.append("- No items available.")
            return lines
        for item in items:
            action = f" Action: {item.action}" if item.action else ""
            lines.append(f"- {item.title}: {item.detail}.{action}")
        return lines

    @staticmethod
    def _write_items(writer, section: str, items: List[DashboardItem]) -> None:
        for item in items:
            writer.writerow([section, item.title, item.detail, item.priority, item.action])

    @staticmethod
    def _format_quality_findings(title: str, findings) -> List[str]:
        lines = ["", f"## {title}", ""]
        if not findings:
            lines.append("- No items available.")
            return lines
        for finding in findings[:5]:
            lines.append(f"- {finding.title}: {finding.detail}")
        return lines
