"""Series-level progress tracking for supported collection goals."""

import csv
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from collection_intelligence import CollectionIntelligenceEngine
from focused_collection_intelligence import CandidateItem
from series_definitions import SERIES_DEFINITIONS, SeriesDefinition


@dataclass
class MissingDateInfo:
    year: str
    is_want_list_target: bool = False
    priority_score: int = 0
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "year": self.year,
            "is_want_list_target": self.is_want_list_target,
            "priority_score": self.priority_score,
            "reason": self.reason,
        }


@dataclass
class SeriesReport:
    series_key: str
    series_name: str
    owned_dates: List[str] = field(default_factory=list)
    missing_dates: List[MissingDateInfo] = field(default_factory=list)
    owned_count: int = 0
    missing_count: int = 0
    completion_percentage: float = 0.0
    want_list_count: int = 0
    upgrade_count: int = 0
    priority_score: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "series_key": self.series_key,
            "series_name": self.series_name,
            "owned_dates": list(self.owned_dates),
            "missing_dates": [missing.to_dict() for missing in self.missing_dates],
            "owned_count": self.owned_count,
            "missing_count": self.missing_count,
            "completion_percentage": self.completion_percentage,
            "want_list_count": self.want_list_count,
            "upgrade_count": self.upgrade_count,
            "priority_score": self.priority_score,
        }


class SeriesTracker:
    """Generate deterministic series progress reports from local collection data."""

    def __init__(
        self,
        items: Iterable[Any],
        staged_want_list_intents: Optional[Iterable[Any]] = None,
        series_definitions: Optional[Iterable[SeriesDefinition]] = None,
    ):
        self.items = list(items or [])
        self.staged_want_list_intents = list(staged_want_list_intents or [])
        self.series_definitions = list(series_definitions or SERIES_DEFINITIONS)
        self.intelligence = CollectionIntelligenceEngine(self.items)

    def generate_reports(self) -> List[SeriesReport]:
        reports = []
        upgrades = self.intelligence.detect_upgrade_candidates()
        for definition in self.series_definitions:
            owned_items = self._items_for_definition(definition)
            want_list_count = self._want_list_count(definition)
            if not owned_items and not want_list_count:
                continue
            owned_years = sorted({
                year for year in (definition.parse_year(getattr(item, "year", "")) for item in owned_items)
                if year is not None
            })
            missing_years = CollectionIntelligenceEngine.detect_missing_years_for_years(owned_years)
            missing_dates = [
                MissingDateInfo(
                    year=str(year),
                    is_want_list_target=self._want_list_targets_year(definition, str(year)),
                    priority_score=self._missing_date_priority(definition, str(year)),
                    reason=self._missing_date_reason(definition, str(year)),
                )
                for year in missing_years
            ]
            owned_count = len(owned_years)
            missing_count = len(missing_dates)
            completion = self._completion_percentage(owned_count, missing_count)
            upgrade_count = self._upgrade_count(definition, upgrades)
            priority_score = self._priority_score(
                definition,
                completion,
                missing_count,
                want_list_count,
                upgrade_count,
            )
            reports.append(SeriesReport(
                series_key=definition.key,
                series_name=definition.name,
                owned_dates=[str(year) for year in owned_years],
                missing_dates=missing_dates,
                owned_count=owned_count,
                missing_count=missing_count,
                completion_percentage=completion,
                want_list_count=want_list_count,
                upgrade_count=upgrade_count,
                priority_score=priority_score,
            ))
        return sorted(reports, key=lambda report: (-report.priority_score, report.series_name))

    def find_report_for_candidate(self, candidate: CandidateItem) -> Optional[SeriesReport]:
        definition = self.find_definition_for_candidate(candidate)
        if not definition:
            return None
        for report in self.generate_reports():
            if report.series_key == definition.key:
                return report
        return None

    def find_definition_for_candidate(self, candidate: CandidateItem) -> Optional[SeriesDefinition]:
        for definition in self.series_definitions:
            if definition.matches(candidate.country, candidate.denomination, candidate.year):
                return definition
        return None

    def top_missing_dates(self, limit: int = 10) -> List[Dict[str, Any]]:
        rows = []
        for report in self.generate_reports():
            for missing in report.missing_dates:
                rows.append({
                    "series_name": report.series_name,
                    "year": missing.year,
                    "is_want_list_target": missing.is_want_list_target,
                    "priority_score": missing.priority_score + report.priority_score,
                    "reason": missing.reason,
                })
        return sorted(rows, key=lambda row: (-row["priority_score"], row["series_name"], row["year"]))[:limit]

    def format_markdown(self) -> str:
        reports = self.generate_reports()
        lines = ["# Series Tracker", ""]
        if not reports:
            lines.append("No supported series detected from available collection or WANT_LIST data.")
            return "\n".join(lines) + "\n"
        lines.extend(["## Series Summary", ""])
        for report in reports:
            lines.append(
                f"- **{report.series_name}**: {report.completion_percentage:.1f}% complete; "
                f"owned {report.owned_count}; missing {report.missing_count}; "
                f"WANT_LIST {report.want_list_count}; upgrades {report.upgrade_count}; "
                f"priority {report.priority_score}."
            )
        lines.extend(["", "## Missing Dates", ""])
        for row in self.top_missing_dates(limit=25):
            want = " WANT_LIST target." if row["is_want_list_target"] else ""
            lines.append(f"- **{row['series_name']} {row['year']}**: {row['reason']}.{want}")
        lines.extend(["", "## Priority Rankings", ""])
        for index, report in enumerate(reports, 1):
            lines.append(f"{index}. {report.series_name} - priority {report.priority_score}")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_markdown())
            return True
        except Exception as exc:
            print(f"Error exporting series tracker markdown: {exc}")
            return False

    def export_csv(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow([
                    "Section",
                    "Series",
                    "Year",
                    "Owned Count",
                    "Missing Count",
                    "Completion %",
                    "WANT_LIST Count",
                    "Upgrade Count",
                    "Priority Score",
                    "Detail",
                ])
                for report in self.generate_reports():
                    writer.writerow([
                        "Series Summary",
                        report.series_name,
                        "",
                        report.owned_count,
                        report.missing_count,
                        f"{report.completion_percentage:.1f}",
                        report.want_list_count,
                        report.upgrade_count,
                        report.priority_score,
                        f"Owned dates: {', '.join(report.owned_dates) or 'none'}",
                    ])
                    for missing in report.missing_dates:
                        writer.writerow([
                            "Missing Date",
                            report.series_name,
                            missing.year,
                            "",
                            "",
                            "",
                            "yes" if missing.is_want_list_target else "no",
                            "",
                            missing.priority_score,
                            missing.reason,
                        ])
            return True
        except Exception as exc:
            print(f"Error exporting series tracker CSV: {exc}")
            return False

    def _items_for_definition(self, definition: SeriesDefinition) -> List[Any]:
        return [
            item for item in self.items
            if definition.matches(
                getattr(item, "country", ""),
                getattr(item, "denomination", ""),
                getattr(item, "year", ""),
            )
        ]

    def _want_list_count(self, definition: SeriesDefinition) -> int:
        return sum(1 for intent in self.staged_want_list_intents if self._intent_matches_definition(intent, definition))

    def _want_list_targets_year(self, definition: SeriesDefinition, year: str) -> bool:
        for intent in self.staged_want_list_intents:
            text = self._intent_text(intent)
            if year in text and self._intent_matches_definition(intent, definition):
                return True
        return False

    def _intent_matches_definition(self, intent: Any, definition: SeriesDefinition) -> bool:
        text = self._intent_text(intent)
        country_match = definition.country.lower() in text
        denomination_match = any(term in text for term in definition.denomination_terms)
        if not country_match or not denomination_match:
            return False
        year = self._first_year(text)
        return definition.matches(definition.country, next(iter(definition.denomination_terms)), year or "")

    @staticmethod
    def _intent_text(intent: Any) -> str:
        return " ".join([
            str(getattr(intent, "target_coin", "") or ""),
            str(getattr(intent, "why_wanted", "") or ""),
            str(getattr(intent, "target_grade", "") or ""),
        ]).lower()

    @staticmethod
    def _first_year(text: str) -> str:
        for token in text.replace("-", " ").replace("/", " ").split():
            if token.isdigit() and len(token) == 4:
                return token
        return ""

    def _upgrade_count(self, definition: SeriesDefinition, upgrades: List[Dict[str, Any]]) -> int:
        return sum(
            1 for upgrade in upgrades
            if definition.matches(upgrade["country"], upgrade["denomination"], upgrade["year"])
        )

    @staticmethod
    def _completion_percentage(owned_count: int, missing_count: int) -> float:
        total = owned_count + missing_count
        return round((owned_count / total) * 100, 1) if total else 0.0

    def _priority_score(
        self,
        definition: SeriesDefinition,
        completion: float,
        missing_count: int,
        want_list_count: int,
        upgrade_count: int,
    ) -> int:
        near_completion = int(completion * 0.35) if missing_count else 0
        want_score = min(30, want_list_count * 12)
        upgrade_score = min(20, upgrade_count * 10)
        quality_impact = min(20, missing_count * 4 + int(completion / 20))
        score = definition.priority_base + near_completion + want_score + upgrade_score + quality_impact
        return max(0, min(100, score))

    def _missing_date_priority(self, definition: SeriesDefinition, year: str) -> int:
        score = definition.priority_base
        if self._want_list_targets_year(definition, year):
            score += 25
        return max(0, min(100, score))

    def _missing_date_reason(self, definition: SeriesDefinition, year: str) -> str:
        reason = f"Missing {year} from {definition.name}"
        if self._want_list_targets_year(definition, year):
            reason += "; explicit WANT_LIST target"
        return reason
