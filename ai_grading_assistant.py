"""AI Grading Assistant — v8.2 Phase 3 Collection Intelligence Integration.

Deterministic, explainable coin grading guidance.
Consumes CollectionIntelligenceEngine. Integrates with Photo Capture and OCR workflows.
No computer vision. No ML. No collection mutation. Advisory-only.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from collection_intelligence import GRADE_HIERARCHY
from collection_intelligence_refined import normalize_grade, grade_score
from collection_intelligence import CollectionIntelligenceEngine


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class GradingCandidate:
    """A coin candidate for grading assessment."""
    country: str
    denomination: str
    year: Optional[str] = None
    series: Optional[str] = None
    variety: Optional[str] = None
    claimed_grade: Optional[str] = None
    photo_references: List[str] = field(default_factory=list)
    ocr_evidence: Optional[Dict[str, Any]] = None
    manual_description: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "country": self.country,
            "denomination": self.denomination,
            "year": self.year,
            "series": self.series,
            "variety": self.variety,
            "claimed_grade": self.claimed_grade,
            "photo_references": self.photo_references,
            "ocr_evidence": self.ocr_evidence,
            "manual_description": self.manual_description,
            "notes": self.notes,
        }

    # -- Factory methods for Phase 2 integration ----------------------------

    @classmethod
    def from_ocr_candidate(cls, ocr_candidate: Any) -> "GradingCandidate":
        """Create GradingCandidate from OCRIdentificationCandidate."""
        return cls(
            country=getattr(ocr_candidate, "country", "") or "",
            denomination=getattr(ocr_candidate, "denomination", "") or "",
            year=getattr(ocr_candidate, "year", None) or None,
            series=getattr(ocr_candidate, "series_type", None) or None,
            variety="; ".join(getattr(ocr_candidate, "possible_variety_keywords", [])) or None,
            photo_references=[getattr(ocr_candidate, "image_path", "")] if getattr(ocr_candidate, "image_path", "") else [],
            ocr_evidence=ocr_candidate.to_dict() if hasattr(ocr_candidate, "to_dict") else None,
            notes=getattr(ocr_candidate, "title", "") or "",
        )

    @classmethod
    def from_captured_photo(cls, photo: Any, ocr_report: Optional[Any] = None) -> "GradingCandidate":
        """Create GradingCandidate from CapturedPhoto plus optional OCR report."""
        ocr_evidence = None
        country, denomination, year, series = "", "", None, None

        if ocr_report and hasattr(ocr_report, "candidates"):
            candidates = getattr(ocr_report, "candidates", [])
            if candidates:
                best = candidates[0]
                country = getattr(best, "country", "") or ""
                denomination = getattr(best, "denomination", "") or ""
                year = getattr(best, "year", None) or None
                series = getattr(best, "series_type", None) or None
                ocr_evidence = best.to_dict() if hasattr(best, "to_dict") else None

        return cls(
            country=country,
            denomination=denomination,
            year=year,
            series=series,
            photo_references=[getattr(photo, "file_path", "")] if getattr(photo, "file_path", "") else [],
            ocr_evidence=ocr_evidence,
            notes=getattr(photo, "notes", "") or "",
        )

    @classmethod
    def from_batch_candidate(cls, batch_candidate: Any) -> "GradingCandidate":
        """Create GradingCandidate from BatchCandidate."""
        ocr_report = getattr(batch_candidate, "ocr_result", None)
        ocr_evidence = None
        country, denomination, year, series = "", "", None, None
        claimed_grade = None

        if ocr_report and hasattr(ocr_report, "candidates"):
            candidates = getattr(ocr_report, "candidates", [])
            if candidates:
                best = candidates[0]
                country = getattr(best, "country", "") or ""
                denomination = getattr(best, "denomination", "") or ""
                year = getattr(best, "year", None) or None
                series = getattr(best, "series_type", None) or None
                ocr_evidence = best.to_dict() if hasattr(best, "to_dict") else None

        proposed = getattr(batch_candidate, "proposed_entry", None)
        if proposed and hasattr(proposed, "grade"):
            claimed_grade = getattr(proposed, "grade", None) or None

        photo_refs = []
        front = getattr(batch_candidate, "front_path", None)
        back = getattr(batch_candidate, "back_path", None)
        if front:
            photo_refs.append(front)
        if back:
            photo_refs.append(back)

        return cls(
            country=country,
            denomination=denomination,
            year=year,
            series=series,
            claimed_grade=claimed_grade,
            photo_references=photo_refs,
            ocr_evidence=ocr_evidence,
            notes=getattr(batch_candidate, "subject", "") or "",
        )


@dataclass
class GradePattern:
    """Grade distribution for a country/denomination/series from collection."""
    country: str
    denomination: str
    series: Optional[str] = None
    total_items: int = 0
    grade_counts: Dict[str, int] = field(default_factory=dict)
    typical_range: Tuple[Optional[str], Optional[str]] = (None, None)
    median_grade: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "country": self.country,
            "denomination": self.denomination,
            "series": self.series,
            "total_items": self.total_items,
            "grade_counts": self.grade_counts,
            "typical_range": self.typical_range,
            "median_grade": self.median_grade,
        }


@dataclass
class GradingAssessment:
    """Assessment result for a single candidate."""
    candidate: GradingCandidate
    estimated_range: Tuple[Optional[str], Optional[str]] = (None, None)
    most_likely_grade: Optional[str] = None
    evidence: List[str] = field(default_factory=list)
    review_flags: List[str] = field(default_factory=list)
    recommendation: str = "REVIEW"  # PROCEED, CAUTION, REVIEW
    collection_context: Dict[str, Any] = field(default_factory=dict)  # Phase 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "estimated_range": self.estimated_range,
            "most_likely_grade": self.most_likely_grade,
            "evidence": self.evidence,
            "review_flags": self.review_flags,
            "recommendation": self.recommendation,
            "collection_context": self.collection_context,
        }


@dataclass
class BatchGradingReport:
    """Report for multiple candidates."""
    assessments: List[GradingAssessment] = field(default_factory=list)

    def by_recommendation(self, recommendation: str) -> List[GradingAssessment]:
        return [a for a in self.assessments if a.recommendation == recommendation]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assessments": [a.to_dict() for a in self.assessments],
            "summary": {
                "total": len(self.assessments),
                "PROCEED": len(self.by_recommendation("PROCEED")),
                "CAUTION": len(self.by_recommendation("CAUTION")),
                "REVIEW": len(self.by_recommendation("REVIEW")),
            },
        }


# ---------------------------------------------------------------------------
# Core Engine
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Export helpers (stateless, no class hierarchy)
# ---------------------------------------------------------------------------

def _format_assessment_markdown(assessment: GradingAssessment) -> str:
    """Format a single assessment as Markdown text."""
    c = assessment.candidate
    lines = [
        f"### {c.country} {c.denomination} {c.year or ''}",
        "",
        f"- **Claimed grade:** {c.claimed_grade or 'Not provided'}",
        f"- **Estimated range:** {assessment.estimated_range[0] or 'Unknown'} – {assessment.estimated_range[1] or 'Unknown'}",
        f"- **Most likely:** {assessment.most_likely_grade or 'Unknown'}",
        f"- **Recommendation:** {assessment.recommendation}",
    ]
    if assessment.evidence:
        lines.extend(["", "**Evidence:**"])
        for ev in assessment.evidence:
            lines.append(f"- {ev}")
    if assessment.review_flags:
        lines.extend(["", "**Review flags:**"])
        for flag in assessment.review_flags:
            lines.append(f"- {flag}")
    if assessment.collection_context:
        lines.extend(["", "**Collection context:**"])
        for key, val in assessment.collection_context.items():
            lines.append(f"- {key}: {val}")
    lines.append("")
    return "\n".join(lines)


def _format_report_markdown(report: BatchGradingReport) -> str:
    """Format a batch report as Markdown text."""
    lines = [
        "# AI Grading Assessment Report",
        "",
        "## Summary",
        "",
        f"- Total candidates: {len(report.assessments)}",
        f"- PROCEED: {len(report.by_recommendation('PROCEED'))}",
        f"- CAUTION: {len(report.by_recommendation('CAUTION'))}",
        f"- REVIEW: {len(report.by_recommendation('REVIEW'))}",
        "",
        "## Assessments",
        "",
    ]
    for assessment in report.assessments:
        lines.append(_format_assessment_markdown(assessment))
    return "\n".join(lines)


def _format_report_csv(report: BatchGradingReport) -> str:
    """Format a batch report as CSV text."""
    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Country", "Denomination", "Year", "Claimed Grade",
        "Estimated Low", "Estimated High", "Most Likely",
        "Recommendation", "Review Flags"
    ])
    for a in report.assessments:
        c = a.candidate
        writer.writerow([
            c.country, c.denomination, c.year or "",
            c.claimed_grade or "",
            a.estimated_range[0] or "",
            a.estimated_range[1] or "",
            a.most_likely_grade or "",
            a.recommendation,
            "; ".join(a.review_flags),
        ])
    return output.getvalue()

class AIGradingAssistant:
    """Deterministic grading guidance. Thin orchestration over CollectionIntelligenceEngine."""

    MIN_PATTERN_SIZE = 3

    def __init__(self, engine: CollectionIntelligenceEngine):
        self.engine = engine
        self._patterns: Dict[str, GradePattern] = {}

    # -- Public API ---------------------------------------------------------

    def assess_candidate(self, candidate: GradingCandidate) -> GradingAssessment:
        """Assess a single candidate against collection grade patterns and intelligence."""
        pattern = self._get_pattern(candidate.country, candidate.denomination, candidate.series)
        evidence: List[str] = []
        flags: List[str] = []

        # Evidence gathering
        if candidate.claimed_grade:
            evidence.append(f"Claimed grade: {candidate.claimed_grade}")
        if candidate.ocr_evidence:
            evidence.append("OCR identification evidence available")
        if candidate.photo_references:
            evidence.append(f"{len(candidate.photo_references)} photo reference(s)")
        if candidate.manual_description:
            evidence.append("Manual description provided")

        # Assessment based on pattern
        if pattern and pattern.total_items >= self.MIN_PATTERN_SIZE:
            evidence.append(f"Collection pattern from {pattern.total_items} items (median: {pattern.median_grade})")
            estimated_low, estimated_high = pattern.typical_range
            most_likely = pattern.median_grade

            # Check claimed grade against pattern
            if candidate.claimed_grade:
                claimed_score = grade_score(candidate.claimed_grade)
                low_score = grade_score(pattern.typical_range[0]) if pattern.typical_range[0] else 0
                high_score = grade_score(pattern.typical_range[1]) if pattern.typical_range[1] else 25

                if claimed_score < low_score:
                    flags.append(f"Claimed grade {candidate.claimed_grade} is below typical collection range ({pattern.typical_range[0]}–{pattern.typical_range[1]})")
                elif claimed_score > high_score:
                    flags.append(f"Claimed grade {candidate.claimed_grade} is above typical collection range ({pattern.typical_range[0]}–{pattern.typical_range[1]})")
                else:
                    evidence.append("Claimed grade falls within typical collection range")

            # Recommendation: evidence-based, not numeric heuristic
            if flags:
                recommendation = "REVIEW"
            elif candidate.claimed_grade and pattern.median_grade:
                if normalize_grade(candidate.claimed_grade) == pattern.median_grade:
                    recommendation = "PROCEED"
                else:
                    recommendation = "CAUTION"
            else:
                recommendation = "CAUTION"
        else:
            estimated_low, estimated_high = None, None
            most_likely = None
            flags.append("No collection pattern available — manual review recommended")
            if candidate.claimed_grade:
                evidence.append(f"Relying on claimed grade only: {candidate.claimed_grade}")
            recommendation = "REVIEW"

        # Phase 3: Build collection context from existing intelligence
        collection_context = self._build_collection_context(candidate)

        # Phase 3: Enhance flags with collection intelligence
        if collection_context.get("duplicate_risk"):
            flags.append(f"Duplicate risk: {collection_context['duplicate_risk']}")
            if recommendation == "PROCEED":
                recommendation = "CAUTION"

        if collection_context.get("upgrade_opportunities"):
            evidence.append(f"Upgrade opportunity: {collection_context['upgrade_opportunities']}")

        return GradingAssessment(
            candidate=candidate,
            estimated_range=(estimated_low, estimated_high),
            most_likely_grade=most_likely,
            evidence=evidence,
            review_flags=flags,
            recommendation=recommendation,
            collection_context=collection_context,
        )

    def assess_batch(self, candidates: List[GradingCandidate]) -> BatchGradingReport:
        """Assess multiple candidates."""
        return BatchGradingReport(
            assessments=[self.assess_candidate(c) for c in candidates]
        )

    # -- Export (Phase 4) ---------------------------------------------------

    def export_assessment(self, assessment: GradingAssessment, format: str, path: str) -> bool:
        """Export a single assessment to file (markdown or csv)."""
        fmt = format.lower()
        try:
            if fmt == "markdown":
                text = _format_assessment_markdown(assessment)
            elif fmt == "csv":
                # Single assessment as one-row CSV
                import csv, io
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["Country", "Denomination", "Year", "Claimed Grade",
                                 "Estimated Low", "Estimated High", "Most Likely",
                                 "Recommendation", "Review Flags"])
                c = assessment.candidate
                writer.writerow([
                    c.country, c.denomination, c.year or "",
                    c.claimed_grade or "",
                    assessment.estimated_range[0] or "",
                    assessment.estimated_range[1] or "",
                    assessment.most_likely_grade or "",
                    assessment.recommendation,
                    "; ".join(assessment.review_flags),
                ])
                text = output.getvalue()
            else:
                return False
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            return True
        except Exception:
            return False

    def export_report(self, report: BatchGradingReport, format: str, path: str) -> bool:
        """Export a batch report to file (markdown or csv)."""
        fmt = format.lower()
        try:
            if fmt == "markdown":
                text = _format_report_markdown(report)
            elif fmt == "csv":
                text = _format_report_csv(report)
            else:
                return False
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(text)
            return True
        except Exception:
            return False


    # -- Phase 3: Collection Intelligence Integration -------------------------

    def _build_collection_context(self, candidate: GradingCandidate) -> Dict[str, Any]:
        """Build collection context by reusing existing engine methods."""
        context: Dict[str, Any] = {}

        # Collection count for country/denomination
        by_country = self.engine.analyze_by_country()
        country_data = by_country.get(candidate.country, {})
        if country_data:
            context["collection_count_for_country"] = country_data.get("count", 0)
            context["denominations_in_country"] = country_data.get("denominations", [])

        # Duplicate risk
        duplicates = self.engine.detect_duplicates()
        for dup in duplicates:
            if (dup.get("country") == candidate.country and
                dup.get("denomination") == candidate.denomination and
                dup.get("year") == candidate.year):
                context["duplicate_risk"] = f"Already own {dup.get('count', 1)} example(s)"
                break

        # Upgrade opportunities for same country/denomination/year
        upgrades = self.engine.detect_upgrade_candidates()
        matching_upgrades = [
            u for u in upgrades
            if (u.get("country") == candidate.country and
                u.get("denomination") == candidate.denomination and
                u.get("year") == candidate.year)
        ]
        if matching_upgrades:
            best = matching_upgrades[0]
            context["upgrade_opportunities"] = (
                f"Existing best grade is {best.get('current_best_grade', 'unknown')}; "
                f"this candidate may be an upgrade"
            )

        # Series completion context
        if candidate.series:
            series_analysis = self.engine.analyze_by_series()
            key = (candidate.country, candidate.denomination)
            if key in series_analysis:
                context["series_items"] = series_analysis[key].get("year_count", 0)

        return context

    # -- Internal -----------------------------------------------------------

    def _get_pattern(self, country: str, denomination: str, series: Optional[str] = None) -> Optional[GradePattern]:
        """Get cached or compute grade pattern from collection engine."""
        key = f"{country}|{denomination}|{series or ''}"
        if key not in self._patterns:
            self._patterns[key] = self._compute_pattern(country, denomination, series)
        return self._patterns[key]

    def _compute_pattern(self, country: str, denomination: str, series: Optional[str] = None) -> Optional[GradePattern]:
        """Compute grade pattern by querying engine.items."""
        items = [
            item for item in self.engine.items
            if self._match(item, country, denomination, series)
        ]
        if not items:
            return None

        grades = [normalize_grade(getattr(item, "grade", "")) for item in items]
        grades = [g for g in grades if g]

        if not grades:
            return GradePattern(country=country, denomination=denomination, series=series, total_items=len(items))

        grade_counts: Dict[str, int] = {}
        for g in grades:
            grade_counts[g] = grade_counts.get(g, 0) + 1

        sorted_grades = sorted(grade_counts.keys(), key=lambda g: GRADE_HIERARCHY.get(g, 0))
        sorted_all = []
        for g in sorted_grades:
            sorted_all.extend([g] * grade_counts[g])

        median = sorted_all[len(sorted_all) // 2]
        low_idx = max(0, len(sorted_all) // 4)
        high_idx = min(len(sorted_all) - 1, 3 * len(sorted_all) // 4)

        return GradePattern(
            country=country,
            denomination=denomination,
            series=series,
            total_items=len(items),
            grade_counts=grade_counts,
            typical_range=(sorted_all[low_idx], sorted_all[high_idx]),
            median_grade=median,
        )

    @staticmethod
    def _match(item: Any, country: str, denomination: str, series: Optional[str]) -> bool:
        """Check if collection item matches filters."""
        c = (getattr(item, "country", "") or "").strip().lower()
        d = (getattr(item, "denomination", "") or "").strip().lower()
        s = (getattr(item, "series", "") or "").strip().lower()
        return c == country.strip().lower() and d == denomination.strip().lower() and (not series or s == series.strip().lower())
