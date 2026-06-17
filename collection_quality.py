"""Deterministic collection quality scoring and improvement planning."""

import csv
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from collection_intelligence import CollectionIntelligenceEngine, SILVER_DENOMINATION_TERMS


@dataclass
class QualityCategoryScore:
    name: str
    score: int
    explanation: str
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "explanation": self.explanation,
            "metrics": dict(self.metrics),
        }


@dataclass
class QualityFinding:
    title: str
    detail: str
    impact_score: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "detail": self.detail,
            "impact_score": self.impact_score,
        }


@dataclass
class QualityRecommendedAction:
    rank: int
    action: str
    why_it_matters: str
    expected_impact: str
    priority_score: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "action": self.action,
            "why_it_matters": self.why_it_matters,
            "expected_impact": self.expected_impact,
            "priority_score": self.priority_score,
        }


@dataclass
class CollectionQualityReport:
    overall_quality_score: int
    category_scores: List[QualityCategoryScore] = field(default_factory=list)
    strengths: List[QualityFinding] = field(default_factory=list)
    weaknesses: List[QualityFinding] = field(default_factory=list)
    recommended_actions: List[QualityRecommendedAction] = field(default_factory=list)
    supporting_metrics: Dict[str, Any] = field(default_factory=dict)

    def category_score(self, name: str) -> int:
        for category in self.category_scores:
            if category.name == name:
                return category.score
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_quality_score": self.overall_quality_score,
            "category_scores": [category.to_dict() for category in self.category_scores],
            "strengths": [finding.to_dict() for finding in self.strengths],
            "weaknesses": [finding.to_dict() for finding in self.weaknesses],
            "recommended_actions": [action.to_dict() for action in self.recommended_actions],
            "supporting_metrics": dict(self.supporting_metrics),
        }


class CollectionQualityEngine:
    """Score collection quality using only existing collection and WANT_LIST data."""

    SCORE_WEIGHTS = {
        "Completeness": 0.35,
        "Upgrade": 0.20,
        "WANT_LIST Progress": 0.15,
        "Diversity": 0.15,
        "Certification": 0.15,
    }

    def __init__(self, items: Iterable[Any], staged_want_list_intents: Optional[Iterable[Any]] = None):
        self.items = list(items or [])
        self.staged_want_list_intents = list(staged_want_list_intents or [])
        self.intelligence = CollectionIntelligenceEngine(self.items)

    def generate_report(self) -> CollectionQualityReport:
        gap_report = self.intelligence.generate_gap_report()
        series_rows = gap_report["series_rows"]
        duplicates = gap_report["duplicates"]
        upgrade_candidates = gap_report["upgrade_candidates"]
        want_targets = self.intelligence.generate_want_list(
            limit=10,
            staged_want_list_intents=self.staged_want_list_intents,
        )

        supporting_metrics = self._supporting_metrics(gap_report, want_targets)
        category_scores = [
            self._completeness_score(series_rows),
            self._upgrade_score(upgrade_candidates),
            self._want_list_score(),
            self._diversity_score(gap_report),
            self._certification_score(),
        ]
        overall = self._overall_score(category_scores)
        strengths = self._strengths(category_scores, supporting_metrics)
        weaknesses = self._weaknesses(category_scores, series_rows, upgrade_candidates, supporting_metrics)
        actions = self._recommended_actions(series_rows, upgrade_candidates, duplicates, want_targets)

        return CollectionQualityReport(
            overall_quality_score=overall,
            category_scores=category_scores,
            strengths=strengths,
            weaknesses=weaknesses,
            recommended_actions=actions,
            supporting_metrics=supporting_metrics,
        )

    def format_markdown(self) -> str:
        report = self.generate_report()
        lines = [
            "# Collection Quality Report",
            "",
            f"- Overall quality score: {report.overall_quality_score}",
            "",
            "## Category Scores",
            "",
        ]
        for category in report.category_scores:
            lines.append(f"- {category.name}: {category.score} - {category.explanation}")
        lines.extend(self._format_findings("Top Strengths", report.strengths))
        lines.extend(self._format_findings("Top Weaknesses", report.weaknesses))
        lines.extend(["", "## Recommended Actions", ""])
        if report.recommended_actions:
            for action in report.recommended_actions:
                lines.append(
                    f"{action.rank}. {action.action} - {action.why_it_matters} "
                    f"Expected impact: {action.expected_impact}"
                )
        else:
            lines.append("No recommended actions generated from available data.")
        lines.extend(["", "## Supporting Metrics", ""])
        for key, value in sorted(report.supporting_metrics.items()):
            lines.append(f"- {key}: {value}")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_markdown())
            return True
        except Exception as exc:
            print(f"Error exporting collection quality markdown: {exc}")
            return False

    def export_csv(self, output_path: str) -> bool:
        try:
            report = self.generate_report()
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Section", "Name", "Score", "Detail", "Expected Impact"])
                writer.writerow(["Overall", "Quality Score", report.overall_quality_score, "", ""])
                for category in report.category_scores:
                    writer.writerow(["Category", category.name, category.score, category.explanation, ""])
                for finding in report.strengths:
                    writer.writerow(["Strength", finding.title, finding.impact_score, finding.detail, ""])
                for finding in report.weaknesses:
                    writer.writerow(["Weakness", finding.title, finding.impact_score, finding.detail, ""])
                for action in report.recommended_actions:
                    writer.writerow([
                        "Recommended Action",
                        action.action,
                        action.priority_score,
                        action.why_it_matters,
                        action.expected_impact,
                    ])
                for key, value in sorted(report.supporting_metrics.items()):
                    writer.writerow(["Supporting Metric", key, "", value, ""])
            return True
        except Exception as exc:
            print(f"Error exporting collection quality CSV: {exc}")
            return False

    def _completeness_score(self, series_rows: List[Dict[str, Any]]) -> QualityCategoryScore:
        if not series_rows:
            return QualityCategoryScore(
                "Completeness",
                0,
                "No date-run series are available to score.",
                {"series_count": 0, "missing_dates": 0},
            )
        average_completion = sum(row["completion_percentage"] for row in series_rows) / len(series_rows)
        missing_dates = sum(self._count_csv_years(row["missing_years"]) for row in series_rows)
        score = self._clamp_score(average_completion)
        explanation = f"Average observed date-run completion is {average_completion:.1f}% across {len(series_rows)} series."
        return QualityCategoryScore(
            "Completeness",
            score,
            explanation,
            {"series_count": len(series_rows), "missing_dates": missing_dates, "average_completion": round(average_completion, 1)},
        )

    def _upgrade_score(self, upgrade_candidates: List[Dict[str, Any]]) -> QualityCategoryScore:
        if not self.items:
            return QualityCategoryScore(
                "Upgrade",
                0,
                "No owned items are available to evaluate upgrades.",
                {"upgrade_opportunities": 0},
            )
        pressure = min(100, len(upgrade_candidates) * 15)
        score = self._clamp_score(100 - pressure)
        explanation = f"{len(upgrade_candidates)} duplicate-based upgrade opportunity item(s) detected."
        return QualityCategoryScore(
            "Upgrade",
            score,
            explanation,
            {"upgrade_opportunities": len(upgrade_candidates), "upgrade_pressure": pressure},
        )

    def _want_list_score(self) -> QualityCategoryScore:
        if not self.staged_want_list_intents:
            return QualityCategoryScore(
                "WANT_LIST Progress",
                0,
                "No staged WANT_LIST context is loaded.",
                {"want_list_items": 0, "completed_targets": 0, "remaining_targets": 0, "high_priority_remaining": 0},
            )
        completed = sum(1 for intent in self.staged_want_list_intents if self._intent_completed(intent))
        total = len(self.staged_want_list_intents)
        remaining = total - completed
        high_priority_remaining = sum(
            1
            for intent in self.staged_want_list_intents
            if not self._intent_completed(intent) and int(getattr(intent, "priority_score", 0) or 0) >= 50
        )
        score = self._clamp_score((completed / total) * 100 if total else 0)
        explanation = f"{completed} of {total} staged WANT_LIST target(s) appear complete from available collection data."
        return QualityCategoryScore(
            "WANT_LIST Progress",
            score,
            explanation,
            {
                "want_list_items": total,
                "completed_targets": completed,
                "remaining_targets": remaining,
                "high_priority_remaining": high_priority_remaining,
            },
        )

    def _diversity_score(self, gap_report: Dict[str, Any]) -> QualityCategoryScore:
        country_count = len(gap_report["countries"])
        denomination_count = len(gap_report["denominations"])
        series_count = len(gap_report["series"])
        country_score = min(country_count / 5, 1) * 100
        denomination_score = min(denomination_count / 8, 1) * 100
        series_score = min(series_count / 10, 1) * 100
        score = self._clamp_score((country_score + denomination_score + series_score) / 3)
        explanation = f"{country_count} countr(ies), {denomination_count} denomination(s), and {series_count} series represented."
        return QualityCategoryScore(
            "Diversity",
            score,
            explanation,
            {"countries": country_count, "denominations": denomination_count, "series": series_count},
        )

    def _certification_score(self) -> QualityCategoryScore:
        if not self.items:
            return QualityCategoryScore(
                "Certification",
                0,
                "No owned items are available to evaluate certification coverage.",
                {"certified_items": 0, "raw_items": 0, "certified_percentage": 0.0},
            )
        certified = sum(1 for item in self.items if self._is_certified(item))
        raw = len(self.items) - certified
        percentage = (certified / len(self.items)) * 100 if self.items else 0
        explanation = f"{certified} of {len(self.items)} item(s) show certification or slab evidence."
        return QualityCategoryScore(
            "Certification",
            self._clamp_score(percentage),
            explanation,
            {"certified_items": certified, "raw_items": raw, "certified_percentage": round(percentage, 1)},
        )

    def _supporting_metrics(self, gap_report: Dict[str, Any], want_targets: List[Any]) -> Dict[str, Any]:
        newfoundland_items = sum(1 for item in self.items if "newfoundland" in (getattr(item, "country", "") or "").lower())
        silver_items = sum(1 for item in self.items if self._is_silver(getattr(item, "denomination", "")))
        certified_items = sum(1 for item in self.items if self._is_certified(item))
        return {
            "total_items": len(self.items),
            "series_count": len(gap_report["series"]),
            "missing_date_groups": len(gap_report["missing_dates"]),
            "duplicate_groups": len(gap_report["duplicates"]),
            "upgrade_opportunities": len(gap_report["upgrade_candidates"]),
            "want_list_items": len(self.staged_want_list_intents),
            "priority_targets": len(want_targets),
            "newfoundland_items": newfoundland_items,
            "silver_items": silver_items,
            "certified_items": certified_items,
            "certified_percentage": round((certified_items / len(self.items)) * 100, 1) if self.items else 0.0,
        }

    def _strengths(
        self,
        category_scores: List[QualityCategoryScore],
        metrics: Dict[str, Any],
    ) -> List[QualityFinding]:
        strengths: List[QualityFinding] = []
        score_map = {category.name: category for category in category_scores}
        if metrics["newfoundland_items"] >= 3:
            strengths.append(QualityFinding(
                "Strong Newfoundland representation",
                f"{metrics['newfoundland_items']} Newfoundland item(s) are represented.",
                85,
            ))
        if metrics["silver_items"] >= 2:
            strengths.append(QualityFinding(
                "Strong silver coverage",
                f"{metrics['silver_items']} silver-denomination item(s) are represented.",
                75,
            ))
        if score_map["Completeness"].score >= 70:
            strengths.append(QualityFinding(
                "Good observed date-run completion",
                score_map["Completeness"].explanation,
                score_map["Completeness"].score,
            ))
        if score_map["Certification"].score >= 50:
            strengths.append(QualityFinding(
                "High certified coin percentage",
                score_map["Certification"].explanation,
                score_map["Certification"].score,
            ))
        if score_map["Upgrade"].score >= 90 and self.items:
            strengths.append(QualityFinding(
                "Low duplicate upgrade pressure",
                "Few duplicate-based upgrade opportunities were detected.",
                score_map["Upgrade"].score,
            ))
        return sorted(strengths, key=lambda item: (-item.impact_score, item.title))[:5]

    def _weaknesses(
        self,
        category_scores: List[QualityCategoryScore],
        series_rows: List[Dict[str, Any]],
        upgrade_candidates: List[Dict[str, Any]],
        metrics: Dict[str, Any],
    ) -> List[QualityFinding]:
        weaknesses: List[QualityFinding] = []
        score_map = {category.name: category for category in category_scores}
        if not self.items:
            weaknesses.append(QualityFinding("No collection data loaded", "Load collection data before quality can be assessed.", 100))
            return weaknesses

        low_completion = [row for row in series_rows if row["missing_years"] and row["completion_percentage"] < 70]
        for row in low_completion[:3]:
            weaknesses.append(QualityFinding(
                f"Low completion in {row['series']}",
                f"Missing {row['missing_years']}; completion is {row['completion_percentage']:.1f}%.",
                100 - int(row["completion_percentage"]),
            ))
        if upgrade_candidates:
            weaknesses.append(QualityFinding(
                "Duplicate-based upgrade pressure",
                f"{len(upgrade_candidates)} upgrade opportunity item(s) indicate lower-grade duplicates.",
                min(95, 50 + len(upgrade_candidates) * 10),
            ))
        if score_map["Certification"].score < 20:
            weaknesses.append(QualityFinding(
                "Low certification coverage",
                score_map["Certification"].explanation,
                80,
            ))
        remaining_wants = score_map["WANT_LIST Progress"].metrics.get("remaining_targets", 0)
        if remaining_wants:
            weaknesses.append(QualityFinding(
                "Remaining WANT_LIST targets",
                f"{remaining_wants} staged WANT_LIST target(s) remain unresolved.",
                70,
            ))
        if not weaknesses and metrics["missing_date_groups"] == 0:
            weaknesses.append(QualityFinding(
                "No obvious gap weakness detected",
                "Available data did not expose a major gap; review target priorities manually.",
                20,
            ))
        return sorted(weaknesses, key=lambda item: (-item.impact_score, item.title))[:5]

    def _recommended_actions(
        self,
        series_rows: List[Dict[str, Any]],
        upgrade_candidates: List[Dict[str, Any]],
        duplicates: List[Dict[str, Any]],
        want_targets: List[Any],
    ) -> List[QualityRecommendedAction]:
        actions: List[QualityRecommendedAction] = []
        for row in series_rows:
            if not row["missing_years"]:
                continue
            score = self._tier_score(row["priority_tier"]) + int(row["completion_percentage"])
            actions.append(QualityRecommendedAction(
                0,
                f"Complete {row['series']}",
                f"Missing date(s): {row['missing_years']}.",
                row["suggested_next_acquisitions"],
                score,
            ))
        for target in want_targets[:5]:
            actions.append(QualityRecommendedAction(
                0,
                f"Acquire {target.coin_label}",
                target.reason,
                target.estimated_impact,
                int(target.priority_score),
            ))
        for candidate in upgrade_candidates[:5]:
            label = f"{candidate['country']} {candidate['denomination']} {candidate['year']}".strip()
            actions.append(QualityRecommendedAction(
                0,
                f"Upgrade {label}",
                candidate["reason"],
                f"Keep current best grade {candidate['current_best_grade']} and replace weaker duplicates.",
                65,
            ))
        for duplicate in duplicates[:3]:
            label = f"{duplicate['country']} {duplicate['denomination']} {duplicate['year']}".strip()
            actions.append(QualityRecommendedAction(
                0,
                f"Reduce duplicate holdings in {label}",
                f"{duplicate['count']} duplicate holding(s) detected.",
                "Lower duplicate exposure and focus budget on upgrades or gaps.",
                45,
            ))

        ranked = sorted(actions, key=lambda action: (-action.priority_score, action.action))[:10]
        for index, action in enumerate(ranked, 1):
            action.rank = index
        return ranked

    def _overall_score(self, category_scores: List[QualityCategoryScore]) -> int:
        weighted = 0.0
        for category in category_scores:
            weighted += category.score * self.SCORE_WEIGHTS[category.name]
        return self._clamp_score(weighted)

    def _intent_completed(self, intent: Any) -> bool:
        target = self._normalize_text(getattr(intent, "target_coin", "") or "")
        if not target:
            return False
        target_tokens = set(target.split())
        for item in self.items:
            label = self._normalize_text(
                " ".join([
                    getattr(item, "country", "") or "",
                    getattr(item, "denomination", "") or "",
                    getattr(item, "year", "") or "",
                    getattr(item, "title", "") or "",
                    getattr(item, "reference", "") or "",
                ])
            )
            if target in label or label in target:
                return True
            label_tokens = set(label.split())
            if target_tokens and len(target_tokens.intersection(label_tokens)) >= min(3, len(target_tokens)):
                return True
        return False

    @staticmethod
    def _count_csv_years(value: str) -> int:
        text = (value or "").strip()
        if not text:
            return 0
        return len([part for part in text.split(",") if part.strip()])

    @staticmethod
    def _tier_score(priority_tier: str) -> int:
        return {"Tier 1": 70, "Tier 2": 55, "Tier 3": 35}.get(priority_tier, 20)

    @staticmethod
    def _is_silver(denomination: str) -> bool:
        lowered = (denomination or "").lower()
        return any(term in lowered for term in SILVER_DENOMINATION_TERMS)

    @staticmethod
    def _is_certified(item: Any) -> bool:
        text = " ".join([
            str(getattr(item, "certifier", "") or ""),
            str(getattr(item, "certification_number", "") or ""),
            str(getattr(item, "notes", "") or ""),
            str(getattr(item, "comments", "") or ""),
        ]).lower()
        return any(term in text for term in ["pcgs", "ngc", "iccs", "anacs", "cert", "slab"])

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(
            "".join(char.lower() if char.isalnum() else " " for char in str(value or "")).split()
        )

    @staticmethod
    def _clamp_score(value: float) -> int:
        return max(0, min(100, int(round(value))))

    @staticmethod
    def _format_findings(title: str, findings: List[QualityFinding]) -> List[str]:
        lines = ["", f"## {title}", ""]
        if not findings:
            lines.append("- No items available.")
            return lines
        for finding in findings:
            lines.append(f"- {finding.title}: {finding.detail}")
        return lines
