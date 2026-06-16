"""Focused collection intelligence for manual candidate evaluation."""

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

from collection_intelligence import GRADE_HIERARCHY, SILVER_DENOMINATION_TERMS


class MatchStatus(str, Enum):
    """Deterministic candidate classification statuses."""

    ALREADY_OWNED = "ALREADY_OWNED"
    BETTER_GRADE_UPGRADE = "BETTER_GRADE_UPGRADE"
    SAME_GRADE_DUPLICATE = "SAME_GRADE_DUPLICATE"
    LOWER_GRADE_DUPLICATE = "LOWER_GRADE_DUPLICATE"
    WANT_LIST_MATCH = "WANT_LIST_MATCH"
    COLLECTION_GAP = "COLLECTION_GAP"
    NOT_RELEVANT = "NOT_RELEVANT"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass
class CandidateItem:
    """Manual candidate input for collection intelligence."""

    country: str = ""
    denomination: str = ""
    year: str = ""
    type_series: str = ""
    variety: str = ""
    grade: str = ""
    certifier: str = ""
    certification_number: str = ""
    asking_price: float = 0.0
    notes: str = ""


@dataclass
class ExistingMatch:
    """Structured existing collection match summary."""

    item_id: str
    country: str
    denomination: str
    year: str
    grade: str
    reference: str = ""
    title: str = ""
    notes: str = ""
    match_score: int = 0
    match_type: str = ""
    variety_match: bool = False
    certified: bool = False


@dataclass
class CollectionIntelligenceResult:
    """Structured output from candidate analysis."""

    match_status: MatchStatus
    best_existing_match: Optional[ExistingMatch]
    grade_comparison: str
    collection_impact: str
    recommendation: str
    confidence_score: int
    priority_reasons: List[str] = field(default_factory=list)
    warning_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a serializable representation."""
        return {
            "match_status": self.match_status.value,
            "best_existing_match": self.best_existing_match.__dict__ if self.best_existing_match else None,
            "grade_comparison": self.grade_comparison,
            "collection_impact": self.collection_impact,
            "recommendation": self.recommendation,
            "confidence_score": self.confidence_score,
            "priority_reasons": list(self.priority_reasons),
            "warning_flags": list(self.warning_flags),
        }


class FocusedCollectionIntelligenceEngine:
    """Evaluate a manual candidate against collection and want-list context."""

    COUNTRY_ALIASES = {
        "can": "canada",
        "cdn": "canada",
        "ca": "canada",
        "canadian": "canada",
        "nfld": "newfoundland",
        "new foundland": "newfoundland",
        "newfoundland colony": "newfoundland",
        "usa": "united states",
        "us": "united states",
        "u.s.": "united states",
        "u.s.a.": "united states",
        "uk": "united kingdom",
        "gb": "united kingdom",
        "great britain": "united kingdom",
    }

    DENOMINATION_ALIASES = {
        "1c": "1 cent",
        "1 c": "1 cent",
        "cent": "1 cent",
        "cents": "1 cent",
        "penny": "1 cent",
        "large cent": "1 cent",
        "5c": "5 cents",
        "5 c": "5 cents",
        "nickel": "5 cents",
        "10c": "10 cents",
        "10 c": "10 cents",
        "dime": "10 cents",
        "20c": "20 cents",
        "20 c": "20 cents",
        "25c": "25 cents",
        "25 c": "25 cents",
        "quarter": "25 cents",
        "50c": "50 cents",
        "50 c": "50 cents",
        "half dollar": "50 cents",
        "half-dollar": "50 cents",
        "$1": "dollar",
        "1 dollar": "dollar",
        "silver dollar": "dollar",
    }

    REVIEW_THRESHOLD = 72
    EXACT_THRESHOLD = 92

    def __init__(self, collection_items: Iterable[Any], want_list_intents: Optional[Iterable[Any]] = None):
        self.collection_items = list(collection_items or [])
        self.want_list_intents = list(want_list_intents or [])

    def analyze_candidate(self, candidate: CandidateItem) -> CollectionIntelligenceResult:
        """Classify a candidate against the collection and staged want-list intent."""
        candidate = self._normalize_candidate(candidate)
        warnings = self._candidate_warnings(candidate)
        priority_reasons = self._candidate_priority_reasons(candidate)
        matches = self._find_matches(candidate)
        best_match = matches[0] if matches else None
        want_match = self._matches_want_list(candidate)

        if best_match and best_match.match_score >= self.EXACT_THRESHOLD:
            status, grade_text, recommendation, impact, extra_reasons, extra_warnings = self._classify_existing_match(
                candidate, best_match
            )
            priority_reasons.extend(extra_reasons)
            warnings.extend(extra_warnings)
            confidence = min(100, best_match.match_score + (5 if best_match.variety_match else 0))
            return CollectionIntelligenceResult(
                match_status=status,
                best_existing_match=best_match,
                grade_comparison=grade_text,
                collection_impact=impact,
                recommendation=recommendation,
                confidence_score=confidence,
                priority_reasons=self._dedupe(priority_reasons),
                warning_flags=self._dedupe(warnings),
            )

        if want_match:
            priority_reasons.append("Explicit WANT_LIST target")
            return CollectionIntelligenceResult(
                match_status=MatchStatus.WANT_LIST_MATCH,
                best_existing_match=best_match,
                grade_comparison="No exact owned match found.",
                collection_impact="Candidate matches staged acquisition intent.",
                recommendation="BUY",
                confidence_score=85 if not best_match else max(75, best_match.match_score),
                priority_reasons=self._dedupe(priority_reasons),
                warning_flags=self._dedupe(warnings),
            )

        if self._is_collection_gap(candidate):
            priority_reasons.append("Missing date or denomination in observed collection area")
            return CollectionIntelligenceResult(
                match_status=MatchStatus.COLLECTION_GAP,
                best_existing_match=best_match,
                grade_comparison="No exact owned match found.",
                collection_impact="Candidate fills a collection gap.",
                recommendation="WATCH",
                confidence_score=78 if not best_match else max(78, best_match.match_score),
                priority_reasons=self._dedupe(priority_reasons),
                warning_flags=self._dedupe(warnings),
            )

        if best_match and best_match.match_score >= self.REVIEW_THRESHOLD:
            warnings.append("Close fuzzy match requires manual review")
            return CollectionIntelligenceResult(
                match_status=MatchStatus.NEEDS_REVIEW,
                best_existing_match=best_match,
                grade_comparison="Potential type-only or fuzzy match.",
                collection_impact="Candidate may relate to an existing collection area.",
                recommendation="REVIEW",
                confidence_score=best_match.match_score,
                priority_reasons=self._dedupe(priority_reasons),
                warning_flags=self._dedupe(warnings),
            )

        if self._is_low_priority_world_base(candidate):
            priority_reasons.append("Low-priority world base-metal candidate")

        return CollectionIntelligenceResult(
            match_status=MatchStatus.NOT_RELEVANT,
            best_existing_match=None,
            grade_comparison="No owned match found.",
            collection_impact="No collection impact detected.",
            recommendation="PASS",
            confidence_score=70,
            priority_reasons=self._dedupe(priority_reasons),
            warning_flags=self._dedupe(warnings),
        )

    def find_exact_items(self, candidate: CandidateItem) -> List[Any]:
        """Return exact owned collection items for a manual candidate."""
        normalized_candidate = self._normalize_candidate(candidate)
        exact_items = [
            item
            for item in self.collection_items
            if self._match_score(normalized_candidate, item) >= self.EXACT_THRESHOLD
            and self._variety_matches(normalized_candidate, item)
        ]
        return sorted(exact_items, key=lambda item: self._grade_score(getattr(item, "grade", "")), reverse=True)

    def _classify_existing_match(
        self, candidate: CandidateItem, match: ExistingMatch
    ) -> Tuple[MatchStatus, str, str, str, List[str], List[str]]:
        grade_delta = self._grade_score(candidate.grade) - self._grade_score(match.grade)
        reasons = []
        warnings = []
        if candidate.variety and not match.variety_match:
            warnings.append("Candidate variety differs from or is not proven on existing match")
            return (
                MatchStatus.NEEDS_REVIEW,
                f"Candidate grade {candidate.grade or 'unknown'} vs existing {match.grade or 'unknown'}.",
                "REVIEW",
                "Existing type match found, but variety needs review.",
                reasons,
                warnings,
            )
        if not candidate.grade:
            return (
                MatchStatus.ALREADY_OWNED,
                f"Existing collection grade is {match.grade or 'unknown'}; candidate grade was not provided.",
                "REVIEW",
                "Exact owned match found; grade comparison unavailable.",
                reasons,
                warnings,
            )
        if self._candidate_certified(candidate) and not match.certified and grade_delta >= 0:
            reasons.append("Certified candidate may replace raw example")
        if grade_delta > 0:
            return (
                MatchStatus.BETTER_GRADE_UPGRADE,
                f"Candidate is {grade_delta} grade step(s) higher than existing.",
                "BUY",
                "Improves collection quality without adding duplicate exposure.",
                reasons,
                warnings,
            )
        if grade_delta == 0:
            return (
                MatchStatus.SAME_GRADE_DUPLICATE,
                "Candidate grade matches best existing example.",
                "PASS",
                "Adds duplicate exposure without quality improvement.",
                reasons,
                warnings,
            )
        return (
            MatchStatus.LOWER_GRADE_DUPLICATE,
            f"Candidate is {abs(grade_delta)} grade step(s) lower than existing.",
            "PASS",
            "Candidate is a downgrade relative to the current holding.",
            reasons,
            warnings,
        )

    def _find_matches(self, candidate: CandidateItem) -> List[ExistingMatch]:
        matches = []
        for item in self.collection_items:
            score = self._match_score(candidate, item)
            if score >= self.REVIEW_THRESHOLD:
                matches.append(self._to_existing_match(candidate, item, score))
        return sorted(
            matches,
            key=lambda match: (
                -match.match_score,
                -self._grade_score(match.grade),
                match.country,
                match.denomination,
                match.year,
            ),
        )

    def _match_score(self, candidate: CandidateItem, item: Any) -> int:
        item_country = self._normalize_country(getattr(item, "country", ""))
        item_denom = self._normalize_denomination(getattr(item, "denomination", ""))
        item_year = self._clean(getattr(item, "year", ""))
        country_score = self._text_score(candidate.country, item_country)
        denom_score = self._text_score(candidate.denomination, item_denom)
        year_score = 100 if candidate.year and candidate.year == item_year else 0
        score = int((country_score * 0.35) + (denom_score * 0.35) + (year_score * 0.25))
        score += 5 if candidate.variety and self._variety_matches(candidate, item) else 0
        return min(score, 100)

    def _to_existing_match(self, candidate: CandidateItem, item: Any, score: int) -> ExistingMatch:
        return ExistingMatch(
            item_id=str(getattr(item, "id", "")),
            country=str(getattr(item, "country", "")),
            denomination=str(getattr(item, "denomination", "")),
            year=str(getattr(item, "year", "")),
            grade=str(getattr(item, "grade", "")),
            reference=str(getattr(item, "reference", "")),
            title=str(getattr(item, "title", "")),
            notes=str(getattr(item, "notes", "")),
            match_score=score,
            match_type="exact" if score >= self.EXACT_THRESHOLD else "fuzzy",
            variety_match=self._variety_matches(candidate, item),
            certified=self._item_certified(item),
        )

    def _is_collection_gap(self, candidate: CandidateItem) -> bool:
        if not candidate.country or not candidate.denomination or not candidate.year:
            return False
        same_area = [
            item for item in self.collection_items
            if self._normalize_country(getattr(item, "country", "")) == candidate.country
            and self._normalize_denomination(getattr(item, "denomination", "")) == candidate.denomination
        ]
        if same_area:
            return not any(self._clean(getattr(item, "year", "")) == candidate.year for item in same_area)
        same_country = [
            item for item in self.collection_items
            if self._normalize_country(getattr(item, "country", "")) == candidate.country
        ]
        return bool(same_country and self._is_adam_priority(candidate))

    def _matches_want_list(self, candidate: CandidateItem) -> bool:
        candidate_text = self._token_set(" ".join([
            candidate.country, candidate.denomination, candidate.year, candidate.type_series, candidate.variety
        ]))
        for intent in self.want_list_intents:
            target = getattr(intent, "target_coin", "") or str(intent)
            target_tokens = self._token_set(target)
            if target_tokens and (target_tokens.issubset(candidate_text) or candidate_text.issubset(target_tokens)):
                return True
        return False

    def _candidate_priority_reasons(self, candidate: CandidateItem) -> List[str]:
        reasons = []
        if candidate.country == "newfoundland":
            reasons.append("Adam priority: Newfoundland")
        if candidate.country == "canada" and candidate.year == "1859" and "cent" in candidate.denomination:
            reasons.append("Adam priority: 1859 Canadian Large Cent")
        if candidate.country == "canada" and self._is_silver_denomination(candidate.denomination):
            reasons.append("Adam priority: Canadian silver")
        return reasons

    def _candidate_warnings(self, candidate: CandidateItem) -> List[str]:
        warnings = []
        if not candidate.country:
            warnings.append("Missing country")
        if not candidate.denomination:
            warnings.append("Missing denomination")
        if not candidate.year:
            warnings.append("Missing year")
        if not candidate.grade:
            warnings.append("Missing grade")
        return warnings

    def _is_adam_priority(self, candidate: CandidateItem) -> bool:
        return bool(self._candidate_priority_reasons(candidate))

    def _is_low_priority_world_base(self, candidate: CandidateItem) -> bool:
        return (
            candidate.country not in {"canada", "newfoundland"}
            and any(term in candidate.denomination for term in ["cent", "penny"])
        )

    def _normalize_candidate(self, candidate: CandidateItem) -> CandidateItem:
        return CandidateItem(
            country=self._normalize_country(candidate.country),
            denomination=self._normalize_denomination(candidate.denomination),
            year=self._clean(candidate.year),
            type_series=self._clean(candidate.type_series).lower(),
            variety=self._clean(candidate.variety).lower(),
            grade=self._normalize_grade(candidate.grade),
            certifier=self._clean(candidate.certifier).upper(),
            certification_number=self._clean(candidate.certification_number),
            asking_price=float(candidate.asking_price or 0),
            notes=self._clean(candidate.notes),
        )

    def _normalize_country(self, country: str) -> str:
        cleaned = self._clean(country).lower().replace(".", "")
        return self.COUNTRY_ALIASES.get(cleaned, cleaned)

    def _normalize_denomination(self, denomination: str) -> str:
        cleaned = self._clean(denomination).lower().replace("-", " ")
        cleaned = " ".join(cleaned.split())
        if cleaned in self.DENOMINATION_ALIASES:
            return self.DENOMINATION_ALIASES[cleaned]
        return cleaned.replace("cents", "cents").replace("cent ", "cent ")

    def _normalize_grade(self, grade: str) -> str:
        return self._clean(grade).upper()

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    def _text_score(self, left: str, right: str) -> int:
        if not left or not right:
            return 0
        if left == right:
            return 100
        if left in right or right in left:
            return 90
        return int(SequenceMatcher(None, left, right).ratio() * 100)

    def _grade_score(self, grade: str) -> int:
        return GRADE_HIERARCHY.get(self._normalize_grade(grade), 0)

    def _variety_matches(self, candidate: CandidateItem, item: Any) -> bool:
        if not candidate.variety:
            return True
        haystack = " ".join([
            str(getattr(item, "reference", "")),
            str(getattr(item, "title", "")),
            str(getattr(item, "notes", "")),
            str(getattr(item, "comments", "")),
        ]).lower()
        return candidate.variety in haystack

    def _candidate_certified(self, candidate: CandidateItem) -> bool:
        text = f"{candidate.certifier} {candidate.certification_number} {candidate.notes}".lower()
        return bool(candidate.certifier or candidate.certification_number or any(term in text for term in ["pcgs", "ngc", "icc", "cert", "slab"]))

    def _item_certified(self, item: Any) -> bool:
        text = " ".join([
            str(getattr(item, "notes", "")),
            str(getattr(item, "comments", "")),
            str(getattr(item, "title", "")),
            str(getattr(item, "reference", "")),
        ]).lower()
        return any(term in text for term in ["pcgs", "ngc", "icc", "cert", "slab"])

    def _is_silver_denomination(self, denomination: str) -> bool:
        return any(term in denomination for term in SILVER_DENOMINATION_TERMS) or denomination in {
            "10 cents", "20 cents", "25 cents", "50 cents", "dollar"
        }

    def _token_set(self, value: str) -> set:
        normalized = value.lower().replace("-", " ")
        normalized = self._normalize_country(normalized)
        return {token for token in normalized.split() if token}

    @staticmethod
    def _dedupe(values: List[str]) -> List[str]:
        seen = set()
        deduped = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                deduped.append(value)
        return deduped
