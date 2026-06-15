"""Collection intelligence engine for gap reports and acquisition planning."""

import csv
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


GRADE_HIERARCHY = {
    "PO-1": 1,
    "FR-2": 2,
    "AG-3": 3,
    "G-4": 4,
    "VG-8": 5,
    "F-12": 6,
    "VF-20": 7,
    "VF-30": 8,
    "EF-40": 9,
    "EF-45": 10,
    "AU-50": 11,
    "AU-53": 12,
    "AU-55": 13,
    "AU-58": 14,
    "MS-60": 15,
    "MS-61": 16,
    "MS-62": 17,
    "MS-63": 18,
    "MS-64": 19,
    "MS-65": 20,
    "MS-66": 21,
    "MS-67": 22,
    "MS-68": 23,
    "MS-69": 24,
    "MS-70": 25,
}

SILVER_DENOMINATION_TERMS = (
    "silver",
    "10 cents",
    "10 cent",
    "dime",
    "25 cents",
    "25 cent",
    "quarter",
    "50 cents",
    "50 cent",
    "half dollar",
    "dollar",
)

NEWFOUNDLAND_FOCUS_TERMS = ("5 cent", "5 cents", "10 cent", "10 cents", "20 cent", "20 cents", "50 cent", "50 cents")


@dataclass
class AcquisitionTarget:
    """A prioritized acquisition recommendation."""

    country: str
    denomination: str
    year: str
    target_type: str
    priority_score: int
    estimated_impact: str
    reason: str
    reference: str = ""
    current_best_grade: str = ""

    def to_dict(self) -> Dict:
        return {
            "country": self.country,
            "denomination": self.denomination,
            "year": self.year,
            "target_type": self.target_type,
            "priority_score": self.priority_score,
            "estimated_impact": self.estimated_impact,
            "reason": self.reason,
            "reference": self.reference,
            "current_best_grade": self.current_best_grade,
        }


class CollectionIntelligenceEngine:
    """Reusable collection analysis for reports, want lists, and evaluators."""

    def __init__(self, items: Iterable):
        self.items = list(items)

    def analyze_by_country(self) -> Dict[str, Dict]:
        countries: Dict[str, Dict] = {}
        for item in self.items:
            country = item.country or "Unknown"
            data = countries.setdefault(
                country,
                {"count": 0, "denominations": set(), "years": set(), "items": []},
            )
            data["count"] += max(int(getattr(item, "quantity", 1) or 1), 1)
            if item.denomination:
                data["denominations"].add(item.denomination)
            if item.year:
                data["years"].add(item.year)
            data["items"].append(item)

        for data in countries.values():
            data["denominations"] = sorted(data["denominations"])
            data["years"] = sorted(data["years"])
        return countries

    def analyze_by_denomination(self) -> Dict[str, Dict]:
        denominations: Dict[str, Dict] = {}
        for item in self.items:
            denomination = item.denomination or "Unknown"
            data = denominations.setdefault(
                denomination,
                {"count": 0, "countries": set(), "years": set(), "items": []},
            )
            data["count"] += max(int(getattr(item, "quantity", 1) or 1), 1)
            if item.country:
                data["countries"].add(item.country)
            if item.year:
                data["years"].add(item.year)
            data["items"].append(item)

        for data in denominations.values():
            data["countries"] = sorted(data["countries"])
            data["years"] = sorted(data["years"])
        return denominations

    def analyze_by_series(self) -> Dict[Tuple[str, str], Dict]:
        series: Dict[Tuple[str, str], Dict] = {}
        for item in self.items:
            key = (item.country or "Unknown", item.denomination or "Unknown")
            data = series.setdefault(
                key,
                {"country": key[0], "denomination": key[1], "years": set(), "items": []},
            )
            year = self._parse_year(item.year)
            if year is not None:
                data["years"].add(year)
            data["items"].append(item)

        completion = self.calculate_completion_percentages(series)
        for key, data in series.items():
            years = sorted(data["years"])
            data["year_count"] = len(years)
            data["years"] = years
            data["missing_years"] = self.detect_missing_years_for_years(years)
            data["completion_percentage"] = completion[key]
            data["priority_score"] = self._adam_priority_score(
                data["country"],
                data["denomination"],
                str(years[0]) if years else "",
                "",
            )
        return series

    def detect_missing_years(self) -> Dict[Tuple[str, str], List[int]]:
        return {
            key: data["missing_years"]
            for key, data in self.analyze_by_series().items()
            if data["missing_years"]
        }

    def calculate_completion_percentages(self, series: Optional[Dict[Tuple[str, str], Dict]] = None) -> Dict[Tuple[str, str], float]:
        series = series if series is not None else self.analyze_by_series()
        percentages: Dict[Tuple[str, str], float] = {}
        for key, data in series.items():
            years = sorted(data["years"])
            if not years:
                percentages[key] = 0.0
                continue
            expected_count = (years[-1] - years[0]) + 1
            percentages[key] = (len(years) / expected_count) * 100 if expected_count else 0.0
        return percentages

    def detect_duplicates(self) -> List[Dict]:
        grouped: Dict[Tuple[str, str, str, str, str], List] = {}
        for item in self.items:
            key = self._identity_key(item)
            grouped.setdefault(key, []).append(item)

        duplicates = []
        for key, group in grouped.items():
            total_quantity = sum(max(int(getattr(item, "quantity", 1) or 1), 1) for item in group)
            if len(group) > 1 or total_quantity > 1:
                duplicates.append(
                    {
                        "key": key,
                        "country": key[0],
                        "denomination": key[1],
                        "year": key[2],
                        "reference": key[3],
                        "numista_n": key[4],
                        "count": total_quantity,
                        "items": group,
                    }
                )
        return sorted(duplicates, key=lambda item: (-item["count"], item["country"], item["denomination"], item["year"]))

    def detect_upgrade_candidates(self) -> List[Dict]:
        candidates = []
        for duplicate in self.detect_duplicates():
            graded = [
                item for item in duplicate["items"]
                if self._grade_score(item.grade) > 0
            ]
            if len(graded) < 2:
                continue
            sorted_items = sorted(graded, key=lambda item: self._grade_score(item.grade), reverse=True)
            best = sorted_items[0]
            replacements = sorted_items[1:]
            if replacements:
                candidates.append(
                    {
                        "country": duplicate["country"],
                        "denomination": duplicate["denomination"],
                        "year": duplicate["year"],
                        "best_item": best,
                        "replacement_candidates": replacements,
                        "current_best_grade": best.grade,
                        "reason": "Keep highest-grade duplicate and consider replacing lower-grade examples.",
                    }
                )
        return candidates

    def generate_acquisition_priorities(self, limit: Optional[int] = None) -> List[AcquisitionTarget]:
        targets: List[AcquisitionTarget] = []
        for key, series in self.analyze_by_series().items():
            country, denomination = key
            for year in series["missing_years"]:
                score = self._adam_priority_score(country, denomination, str(year), "")
                score += self._budget_priority_score(series["items"])
                completion_gain = self._completion_gain(series)
                targets.append(
                    AcquisitionTarget(
                        country=country,
                        denomination=denomination,
                        year=str(year),
                        target_type="Missing Date",
                        priority_score=score + 20,
                        estimated_impact=f"Adds about {completion_gain:.1f} percentage points to this date run.",
                        reason=self._priority_reason(country, denomination, str(year), "Missing date in observed series."),
                    )
                )

        for candidate in self.detect_upgrade_candidates():
            country = candidate["country"]
            denomination = candidate["denomination"]
            year = candidate["year"]
            score = self._adam_priority_score(country, denomination, year, "")
            targets.append(
                AcquisitionTarget(
                    country=country,
                    denomination=denomination,
                    year=year,
                    target_type="Upgrade Candidate",
                    priority_score=score + 15,
                    estimated_impact="Improves quality without expanding duplicate exposure.",
                    reason=self._priority_reason(country, denomination, year, candidate["reason"]),
                    current_best_grade=candidate["current_best_grade"],
                )
            )

        targets.sort(key=lambda target: (-target.priority_score, target.country, target.denomination, target.year))
        return targets[:limit] if limit is not None else targets

    def generate_gap_report(self) -> Dict:
        series = self.analyze_by_series()
        priorities = self.generate_acquisition_priorities()
        return {
            "summary": {
                "total_items": len(self.items),
                "total_countries": len(self.analyze_by_country()),
                "total_denominations": len(self.analyze_by_denomination()),
                "total_series": len(series),
            },
            "countries": self.analyze_by_country(),
            "denominations": self.analyze_by_denomination(),
            "series": series,
            "missing_dates": self.detect_missing_years(),
            "completion_percentages": {
                f"{country} / {denomination}": data["completion_percentage"]
                for (country, denomination), data in series.items()
            },
            "duplicates": self.detect_duplicates(),
            "upgrade_candidates": self.detect_upgrade_candidates(),
            "priority_targets": priorities,
            "series_rows": self.generate_gap_report_rows(),
        }

    def generate_gap_report_rows(self) -> List[Dict]:
        """Return country/denomination date-run rows for the gap report MVP."""
        rows = []
        for (country, denomination), data in self.analyze_by_series().items():
            years = data["years"]
            missing_years = data["missing_years"]
            rows.append(
                {
                    "series": f"{country} / {denomination}",
                    "country": country,
                    "denomination": denomination,
                    "years_owned": self._format_years(years) if years else "",
                    "missing_years": self._format_years(missing_years) if missing_years else "",
                    "completion_percentage": data["completion_percentage"],
                    "priority_tier": self._priority_tier(country, denomination, years),
                    "suggested_next_acquisitions": self._suggest_next_acquisitions(
                        country, denomination, years, missing_years
                    ),
                }
            )

        rows.sort(
            key=lambda row: (
                self._priority_tier_rank(row["priority_tier"]),
                -row["completion_percentage"],
                row["country"],
                row["denomination"],
            )
        )
        return rows

    def generate_want_list(self, limit: int = 10) -> List[AcquisitionTarget]:
        return self.generate_acquisition_priorities(limit=limit)

    def export_gap_report_markdown(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_gap_report_markdown())
            return True
        except Exception as exc:
            print(f"Error exporting gap report markdown: {exc}")
            return False

    def export_gap_report_csv(self, output_path: str) -> bool:
        """Export the read-only collection gap report rows to CSV."""
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                fieldnames = [
                    "priority_tier",
                    "series",
                    "country",
                    "denomination",
                    "years_owned",
                    "missing_years",
                    "completion_percentage",
                    "suggested_next_acquisitions",
                ]
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for row in self.generate_gap_report_rows():
                    output_row = row.copy()
                    output_row["completion_percentage"] = f"{row['completion_percentage']:.1f}"
                    writer.writerow(output_row)
            return True
        except Exception as exc:
            print(f"Error exporting gap report CSV: {exc}")
            return False

    def export_want_list_markdown(self, output_path: str, limit: int = 10) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_want_list_markdown(limit=limit))
            return True
        except Exception as exc:
            print(f"Error exporting want list markdown: {exc}")
            return False

    def export_want_list_csv(self, output_path: str, limit: int = 10) -> bool:
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                fieldnames = [
                    "priority_score",
                    "target_type",
                    "country",
                    "denomination",
                    "year",
                    "estimated_impact",
                    "reason",
                    "reference",
                    "current_best_grade",
                ]
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for target in self.generate_want_list(limit=limit):
                    writer.writerow(target.to_dict())
            return True
        except Exception as exc:
            print(f"Error exporting want list CSV: {exc}")
            return False

    def format_gap_report_text(self) -> str:
        report = self.generate_gap_report()
        lines = [
            "Collection Gap Report",
            "",
            f"Total Items: {report['summary']['total_items']}",
            f"Countries: {report['summary']['total_countries']}",
            f"Denominations: {report['summary']['total_denominations']}",
            f"Series: {report['summary']['total_series']}",
            "",
            "Series Gap Analysis",
        ]
        if report["series_rows"]:
            for row in report["series_rows"]:
                lines.append(
                    f"- {row['priority_tier']} | {row['series']} | "
                    f"Owned: {row['years_owned'] or 'none'} | "
                    f"Missing: {row['missing_years'] or 'none'} | "
                    f"Completion: {row['completion_percentage']:.1f}% | "
                    f"Next: {row['suggested_next_acquisitions']}"
                )
        else:
            lines.append("- No series data available.")

        lines.extend(["", "Missing Dates"])
        missing = report["missing_dates"]
        if missing:
            for (country, denomination), years in missing.items():
                lines.append(f"- {country} {denomination}: {self._format_years(years)}")
        else:
            lines.append("- No missing dates detected from observed series ranges.")

        lines.extend(["", "Completion Percentages"])
        for label, percent in sorted(report["completion_percentages"].items()):
            lines.append(f"- {label}: {percent:.1f}%")

        lines.extend(["", "Upgrade Opportunities"])
        if report["upgrade_candidates"]:
            for candidate in report["upgrade_candidates"]:
                lines.append(
                    f"- {candidate['country']} {candidate['denomination']} {candidate['year']}: "
                    f"best grade {candidate['current_best_grade']}"
                )
        else:
            lines.append("- No duplicate-based upgrade opportunities detected.")

        lines.extend(["", "Duplicate Holdings"])
        if report["duplicates"]:
            for duplicate in report["duplicates"]:
                lines.append(
                    f"- {duplicate['country']} {duplicate['denomination']} {duplicate['year']}: "
                    f"{duplicate['count']} held"
                )
        else:
            lines.append("- No duplicate holdings detected.")

        lines.extend(["", "Priority Acquisition Targets"])
        for target in report["priority_targets"][:10]:
            lines.append(
                f"- [{target.priority_score}] {target.country} {target.denomination} {target.year} "
                f"({target.target_type}) - {target.reason}"
            )
        if not report["priority_targets"]:
            lines.append("- No priority targets generated.")

        return "\n".join(lines)

    def format_gap_report_markdown(self) -> str:
        report = self.generate_gap_report()
        lines = [
            "# Collection Gap Report",
            "",
            "## Summary",
            "",
            f"- Total items: {report['summary']['total_items']}",
            f"- Countries: {report['summary']['total_countries']}",
            f"- Denominations: {report['summary']['total_denominations']}",
            f"- Series: {report['summary']['total_series']}",
            "",
            "## Series Gap Analysis",
            "",
        ]
        if report["series_rows"]:
            for row in report["series_rows"]:
                lines.append(
                    f"- **{row['series']}** ({row['priority_tier']}): "
                    f"owned {row['years_owned'] or 'none'}; "
                    f"missing {row['missing_years'] or 'none'}; "
                    f"completion {row['completion_percentage']:.1f}%; "
                    f"next {row['suggested_next_acquisitions']}"
                )
        else:
            lines.append("- No series data available.")

        lines.extend([
            "",
            "## Missing Dates",
            "",
        ])
        missing = report["missing_dates"]
        if missing:
            for (country, denomination), years in missing.items():
                lines.append(f"- **{country} {denomination}**: {self._format_years(years)}")
        else:
            lines.append("- No missing dates detected from observed series ranges.")

        lines.extend(["", "## Completion Percentages", ""])
        for label, percent in sorted(report["completion_percentages"].items()):
            lines.append(f"- **{label}**: {percent:.1f}%")

        lines.extend(["", "## Upgrade Opportunities", ""])
        if report["upgrade_candidates"]:
            for candidate in report["upgrade_candidates"]:
                replacements = ", ".join(item.grade or "ungraded" for item in candidate["replacement_candidates"])
                lines.append(
                    f"- **{candidate['country']} {candidate['denomination']} {candidate['year']}**: "
                    f"best grade {candidate['current_best_grade']}; lower-grade duplicates: {replacements}."
                )
        else:
            lines.append("- No duplicate-based upgrade opportunities detected.")

        lines.extend(["", "## Duplicate Holdings", ""])
        if report["duplicates"]:
            for duplicate in report["duplicates"]:
                lines.append(
                    f"- **{duplicate['country']} {duplicate['denomination']} {duplicate['year']}**: "
                    f"{duplicate['count']} held."
                )
        else:
            lines.append("- No duplicate holdings detected.")

        lines.extend(["", "## Priority Acquisition Targets", ""])
        for target in report["priority_targets"][:10]:
            lines.append(
                f"- **[{target.priority_score}] {target.country} {target.denomination} {target.year}** "
                f"({target.target_type}): {target.reason} Impact: {target.estimated_impact}"
            )
        if not report["priority_targets"]:
            lines.append("- No priority targets generated.")

        lines.append("")
        return "\n".join(lines)

    def format_want_list_markdown(self, limit: int = 10) -> str:
        lines = ["# Want List", ""]
        targets = self.generate_want_list(limit=limit)
        if not targets:
            lines.append("No acquisition targets generated.")
            return "\n".join(lines) + "\n"

        for index, target in enumerate(targets, 1):
            lines.extend(
                [
                    f"## {index}. {target.country} {target.denomination} {target.year}",
                    "",
                    f"- Type: {target.target_type}",
                    f"- Priority score: {target.priority_score}",
                    f"- Estimated impact: {target.estimated_impact}",
                    f"- Reason: {target.reason}",
                    "",
                ]
            )
        return "\n".join(lines)

    @staticmethod
    def detect_missing_years_for_years(years: List[int]) -> List[int]:
        if len(years) < 2:
            return []
        observed = set(years)
        return [year for year in range(min(years), max(years) + 1) if year not in observed]

    def _identity_key(self, item) -> Tuple[str, str, str, str, str]:
        return (
            (item.country or "").strip(),
            (item.denomination or "").strip(),
            (item.year or "").strip(),
            (item.reference or "").strip(),
            (item.numista_n or "").strip(),
        )

    @staticmethod
    def _parse_year(year: str) -> Optional[int]:
        try:
            return int(str(year).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _grade_score(grade: str) -> int:
        return GRADE_HIERARCHY.get((grade or "").strip(), 0)

    def _adam_priority_score(self, country: str, denomination: str, year: str, reference: str) -> int:
        country_lower = (country or "").lower()
        denom_lower = (denomination or "").lower()
        reference_lower = (reference or "").lower()
        score = 10

        if "newfoundland" in country_lower:
            score += 50
            if any(term in denom_lower for term in NEWFOUNDLAND_FOCUS_TERMS):
                score += 20

        if "canada" in country_lower and year == "1859" and ("cent" in denom_lower or "large" in denom_lower):
            score += 45
            if any(term in reference_lower for term in ("narrow 9", "wide 9", "8 over 9", "8/9", "variety")):
                score += 15

        if "canada" in country_lower and any(term in denom_lower for term in SILVER_DENOMINATION_TERMS):
            score += 30

        if "duplicate" not in reference_lower:
            score += 5

        return score

    @staticmethod
    def _budget_priority_score(items: List) -> int:
        estimates = [
            CollectionIntelligenceEngine._estimate_value(item)
            for item in items
            if CollectionIntelligenceEngine._estimate_value(item) > 0
        ]
        if not estimates:
            return 0
        average_estimate = sum(estimates) / len(estimates)
        if average_estimate <= 20:
            return 10
        if average_estimate <= 100:
            return 5
        return 0

    @staticmethod
    def _estimate_value(item) -> float:
        try:
            return float(getattr(item, "estimate_cad", 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    def _priority_reason(self, country: str, denomination: str, year: str, base_reason: str) -> str:
        reasons = [base_reason]
        country_lower = (country or "").lower()
        denom_lower = (denomination or "").lower()
        if "newfoundland" in country_lower:
            reasons.append("Adam priority: Newfoundland coinage.")
        if "canada" in country_lower and year == "1859" and "cent" in denom_lower:
            reasons.append("Adam priority: 1859 Canadian Large Cent varieties.")
        if "canada" in country_lower and any(term in denom_lower for term in SILVER_DENOMINATION_TERMS):
            reasons.append("Adam priority: Canadian silver.")
        if not any("Adam priority" in reason for reason in reasons):
            reasons.append("Supports date-run completion and gap reduction.")
        return " ".join(reasons)

    def _priority_tier(self, country: str, denomination: str, years: List[int]) -> str:
        country_lower = (country or "").lower()
        denom_lower = (denomination or "").lower()
        if "newfoundland" in country_lower:
            return "Tier 1"
        if "canada" in country_lower and self._is_canada_silver_denomination(denom_lower):
            return "Tier 1"
        if (
            "canada" in country_lower
            and 1859 in years
            and ("cent" in denom_lower or "large" in denom_lower)
        ):
            return "Tier 2"
        return "Tier 3"

    @staticmethod
    def _priority_tier_rank(priority_tier: str) -> int:
        return {"Tier 1": 1, "Tier 2": 2, "Tier 3": 3}.get(priority_tier, 9)

    def _suggest_next_acquisitions(
        self,
        country: str,
        denomination: str,
        years: List[int],
        missing_years: List[int],
    ) -> str:
        country_lower = (country or "").lower()
        denom_lower = (denomination or "").lower()

        if missing_years:
            year_text = self._format_years(missing_years[:5])
            if len(missing_years) > 5:
                year_text += ", ..."
            return f"Acquire missing date(s): {year_text}."

        if (
            "canada" in country_lower
            and 1859 in years
            and ("cent" in denom_lower or "large" in denom_lower)
        ):
            return "Review 1859 Large Cent varieties and upgrade opportunities."

        if "newfoundland" in country_lower:
            return "Seek higher-grade Newfoundland examples or key-date upgrades."

        if "canada" in country_lower and self._is_canada_silver_denomination(denom_lower):
            return "Target Canadian silver upgrades or adjacent missing dates as the run expands."

        return "No immediate date gap detected from the current observed range."

    @staticmethod
    def _is_canada_silver_denomination(denomination_lower: str) -> bool:
        return any(term in denomination_lower for term in SILVER_DENOMINATION_TERMS)

    @staticmethod
    def _completion_gain(series: Dict) -> float:
        years = series["years"]
        if not years:
            return 0.0
        expected_count = (max(years) - min(years)) + 1
        return (1 / expected_count) * 100 if expected_count else 0.0

    @staticmethod
    def _format_years(years: List[int]) -> str:
        return ", ".join(str(year) for year in years)
