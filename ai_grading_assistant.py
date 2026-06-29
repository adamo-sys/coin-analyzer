"""AI Grading Assistant — v8.2 Phase 1 Core Engine.

Deterministic, explainable coin grading guidance.
Consumes CollectionIntelligenceEngine. No computer vision. No ML.
No collection mutation. Advisory-only.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "estimated_range": self.estimated_range,
            "most_likely_grade": self.most_likely_grade,
            "evidence": self.evidence,
            "review_flags": self.review_flags,
            "recommendation": self.recommendation,
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

class AIGradingAssistant:
    """Deterministic grading guidance. Thin orchestration over CollectionIntelligenceEngine."""

    MIN_PATTERN_SIZE = 3

    def __init__(self, engine: CollectionIntelligenceEngine):
        self.engine = engine
        self._patterns: Dict[str, GradePattern] = {}

    # -- Public API ---------------------------------------------------------

    def assess_candidate(self, candidate: GradingCandidate) -> GradingAssessment:
        """Assess a single candidate against collection grade patterns."""
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
                # If claimed grade matches median, strong alignment
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

        return GradingAssessment(
            candidate=candidate,
            estimated_range=(estimated_low, estimated_high),
            most_likely_grade=most_likely,
            evidence=evidence,
            review_flags=flags,
            recommendation=recommendation,
        )

    def assess_batch(self, candidates: List[GradingCandidate]) -> BatchGradingReport:
        """Assess multiple candidates."""
        return BatchGradingReport(
            assessments=[self.assess_candidate(c) for c in candidates]
        )

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
