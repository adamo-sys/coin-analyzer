"""
Collection Assistant Engine

Orchestrates existing Photo Capture, OCR Identification, Collection Intelligence,
Collection Insights, and Acquisition Strategy engines into a single guided review
experience for dramatically reducing manual cataloguing work while preserving
user review and approval for every collection change.

This is NOT AI reasoning, forecasting, machine learning, or external APIs.
All assistance is deterministic, explainable, reproducible, and derived only from local data.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
import os


class ReviewStatus(Enum):
    """Status of a candidate in the review queue."""
    PENDING = "pending"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    INCOMPLETE = "incomplete"


class PhotoSide(Enum):
    """Which side of the coin a photo represents."""
    OBVERSE = "obverse"
    REVERSE = "reverse"
    UNKNOWN = "unknown"
    BOTH = "both"


class PhotoQuality(Enum):
    """Quality assessment of a photo."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNUSABLE = "unusable"


class CandidateSource(Enum):
    """Source of a candidate."""
    OCR = "ocr"
    MANUAL = "manual"
    IMPORT = "import"
    PHOTO = "photo"


@dataclass
class PhotoInfo:
    """Information about a photo used in the assistant workflow."""
    file_path: str
    side: PhotoSide = PhotoSide.UNKNOWN
    quality: PhotoQuality = PhotoQuality.GOOD
    orientation: int = 0  # degrees rotation
    width: int = 0
    height: int = 0
    has_pair: bool = False
    paired_photo: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class OCRCandidate:
    """OCR extraction result for a candidate."""
    raw_text: str = ""
    detected_year: Optional[str] = None
    detected_denomination: Optional[str] = None
    detected_country: Optional[str] = None
    detected_variety: Optional[str] = None
    confidence: float = 0.0
    trust_level: str = "LOW"
    validation_score: float = 0.0
    evidence: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    retry_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CollectionMatch:
    """Match result from existing collection lookup."""
    matched: bool = False
    match_type: str = ""  # "exact", "similar", "duplicate", "upgrade"
    existing_item: Optional[Dict[str, Any]] = None
    similarity_score: float = 0.0
    duplicate_risk: str = "none"  # "none", "low", "medium", "high"
    upgrade_opportunity: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class CollectionGapInfo:
    """Gap analysis for a candidate."""
    fills_gap: bool = False
    gap_type: str = ""  # "series", "date", "denomination", "country"
    series_name: Optional[str] = None
    missing_dates: List[str] = field(default_factory=list)
    impact_score: float = 0.0


@dataclass
class AcquisitionPriorityInfo:
    """Acquisition priority for a candidate if available."""
    has_priority: bool = False
    priority_category: str = ""  # "want_list", "series_completion", "gap_fill", "diversification"
    priority_score: float = 0.0
    budget_guidance: str = ""
    strategic_reason: str = ""


@dataclass
class CollectionAssistantCandidate:
    """A single candidate in the collection assistant workflow."""
    id: str
    source: CandidateSource = CandidateSource.OCR
    photos: List[PhotoInfo] = field(default_factory=list)
    ocr_result: Optional[OCRCandidate] = None
    manual_data: Dict[str, Any] = field(default_factory=dict)
    collection_match: CollectionMatch = field(default_factory=CollectionMatch)
    gap_info: CollectionGapInfo = field(default_factory=CollectionGapInfo)
    acquisition_priority: AcquisitionPriorityInfo = field(default_factory=AcquisitionPriorityInfo)
    suggested_identification: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.PENDING
    review_notes: str = ""
    reviewed_at: Optional[datetime] = None
    reviewed_by: str = "collector"
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def display_label(self) -> str:
        """Generate a human-readable label for this candidate."""
        if self.suggested_identification:
            country = self.suggested_identification.get("country", "")
            denom = self.suggested_identification.get("denomination", "")
            year = self.suggested_identification.get("year", "")
            parts = [p for p in [country, denom, year] if p]
            if parts:
                return " ".join(parts)
        if self.ocr_result and self.ocr_result.detected_year:
            parts = []
            if self.ocr_result.detected_country:
                parts.append(self.ocr_result.detected_country)
            if self.ocr_result.detected_denomination:
                parts.append(self.ocr_result.detected_denomination)
            parts.append(self.ocr_result.detected_year)
            return " ".join(parts)
        return f"Candidate {self.id}"

    @property
    def is_photo_pair_complete(self) -> bool:
        """Check if both obverse and reverse photos are present."""
        sides = {p.side for p in self.photos}
        return PhotoSide.OBVERSE in sides and PhotoSide.REVERSE in sides

    @property
    def has_high_confidence(self) -> bool:
        """Check if candidate has high confidence."""
        return self.confidence >= 0.8

    @property
    def is_duplicate_risk(self) -> bool:
        """Check if candidate poses a duplicate risk."""
        return self.collection_match.duplicate_risk in ("medium", "high")

    @property
    def fills_collection_gap(self) -> bool:
        """Check if candidate fills a collection gap."""
        return self.gap_info.fills_gap

    @property
    def is_approved(self) -> bool:
        return self.review_status == ReviewStatus.APPROVED

    @property
    def is_rejected(self) -> bool:
        return self.review_status == ReviewStatus.REJECTED

    @property
    def is_pending(self) -> bool:
        return self.review_status == ReviewStatus.PENDING

    @property
    def is_reviewed(self) -> bool:
        return self.review_status in (ReviewStatus.APPROVED, ReviewStatus.REJECTED, ReviewStatus.NEEDS_REVIEW)


@dataclass
class AssistantReviewQueue:
    """Queue of candidates for review."""
    candidates: List[CollectionAssistantCandidate] = field(default_factory=list)
    current_index: int = 0
    filter_status: Optional[ReviewStatus] = None
    filter_confidence_min: float = 0.0
    sort_by: str = "confidence"  # "confidence", "timestamp", "priority", "gap"

    @property
    def total_count(self) -> int:
        return len(self.candidates)

    @property
    def reviewed_count(self) -> int:
        return sum(1 for c in self.candidates if c.is_reviewed)

    @property
    def pending_count(self) -> int:
        return sum(1 for c in self.candidates if c.is_pending)

    @property
    def approved_count(self) -> int:
        return sum(1 for c in self.candidates if c.is_approved)

    @property
    def rejected_count(self) -> int:
        return sum(1 for c in self.candidates if c.is_rejected)

    @property
    def completion_percentage(self) -> float:
        if not self.candidates:
            return 0.0
        return (self.reviewed_count / self.total_count) * 100

    @property
    def is_complete(self) -> bool:
        return self.completion_percentage >= 100

    @property
    def has_incomplete_reviews(self) -> bool:
        return any(c.review_status == ReviewStatus.INCOMPLETE for c in self.candidates)

    def get_filtered_candidates(self) -> List[CollectionAssistantCandidate]:
        """Get candidates filtered by current filter settings."""
        result = self.candidates.copy()
        if self.filter_status:
            result = [c for c in result if c.review_status == self.filter_status]
        if self.filter_confidence_min > 0:
            result = [c for c in result if c.confidence >= self.filter_confidence_min]
        return result

    def get_next_pending(self) -> Optional[CollectionAssistantCandidate]:
        """Get the next pending candidate."""
        for c in self.candidates:
            if c.is_pending:
                return c
        return None

    def get_high_priority_candidates(self) -> List[CollectionAssistantCandidate]:
        """Get candidates with high priority or gap-filling potential."""
        return [c for c in self.candidates if c.fills_collection_gap or c.confidence >= 0.8]

    def get_duplicate_risk_candidates(self) -> List[CollectionAssistantCandidate]:
        """Get candidates with duplicate risk."""
        return [c for c in self.candidates if c.is_duplicate_risk]

    def advance(self) -> Optional[CollectionAssistantCandidate]:
        """Advance to the next candidate in the queue."""
        filtered = self.get_filtered_candidates()
        if self.current_index < len(filtered) - 1:
            self.current_index += 1
            return filtered[self.current_index]
        return None

    def go_back(self) -> Optional[CollectionAssistantCandidate]:
        """Go back to the previous candidate in the queue."""
        if self.current_index > 0:
            self.current_index -= 1
            filtered = self.get_filtered_candidates()
            return filtered[self.current_index]
        return None


@dataclass
class ProductivityMetrics:
    """Productivity metrics for a collection assistant session."""
    photos_processed: int = 0
    ocr_attempts: int = 0
    ocr_successes: int = 0
    candidates_generated: int = 0
    reviews_completed: int = 0
    approvals: int = 0
    rejections: int = 0
    needs_review: int = 0
    average_confidence: float = 0.0
    total_session_time: float = 0.0  # seconds
    estimated_time_saved: float = 0.0  # seconds
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def ocr_success_rate(self) -> float:
        if self.ocr_attempts == 0:
            return 0.0
        return (self.ocr_successes / self.ocr_attempts) * 100

    @property
    def review_completion_rate(self) -> float:
        if self.candidates_generated == 0:
            return 0.0
        return (self.reviews_completed / self.candidates_generated) * 100

    @property
    def approval_rate(self) -> float:
        if self.reviews_completed == 0:
            return 0.0
        return (self.approvals / self.reviews_completed) * 100

    @property
    def estimated_time_saved_minutes(self) -> float:
        return self.estimated_time_saved / 60

    def to_dict(self) -> Dict[str, Any]:
        return {
            "photos_processed": self.photos_processed,
            "ocr_attempts": self.ocr_attempts,
            "ocr_successes": self.ocr_successes,
            "ocr_success_rate": f"{self.ocr_success_rate:.1f}%",
            "candidates_generated": self.candidates_generated,
            "reviews_completed": self.reviews_completed,
            "review_completion_rate": f"{self.review_completion_rate:.1f}%",
            "approvals": self.approvals,
            "rejections": self.rejections,
            "needs_review": self.needs_review,
            "approval_rate": f"{self.approval_rate:.1f}%",
            "average_confidence": f"{self.average_confidence:.1%}",
            "total_session_time_seconds": self.total_session_time,
            "estimated_time_saved_minutes": f"{self.estimated_time_saved_minutes:.1f}",
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AssistantSummary:
    """Summary of a collection assistant session."""
    session_id: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    queue: AssistantReviewQueue = field(default_factory=AssistantReviewQueue)
    metrics: ProductivityMetrics = field(default_factory=ProductivityMetrics)
    status: str = "active"  # "active", "completed", "paused"
    notes: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def duration(self) -> timedelta:
        if self.end_time:
            return self.end_time - self.start_time
        return datetime.now() - self.start_time

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration.total_seconds(),
            "status": self.status,
            "total_candidates": self.queue.total_count,
            "reviewed": self.queue.reviewed_count,
            "approved": self.queue.approved_count,
            "rejected": self.queue.rejected_count,
            "pending": self.queue.pending_count,
            "completion_percentage": f"{self.queue.completion_percentage:.1f}%",
            "metrics": self.metrics.to_dict(),
            "notes": self.notes,
        }


@dataclass
class SideBySideComparison:
    """Side-by-side comparison for review."""
    candidate: CollectionAssistantCandidate
    existing_match: Optional[Dict[str, Any]] = None
    suggested_identification: Dict[str, Any] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    confidence: float = 0.0


class CollectionAssistantEngine:
    """Engine for orchestrating collection assistant workflows."""

    def __init__(self):
        self.sessions: Dict[str, AssistantSummary] = {}
        self.session_counter = 0

    def start_session(self, session_id: Optional[str] = None) -> AssistantSummary:
        """Start a new collection assistant session."""
        self.session_counter += 1
        if not session_id:
            session_id = f"session_{self.session_counter}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        session = AssistantSummary(session_id=session_id)
        self.sessions[session_id] = session
        return session

    def add_photos_to_session(
        self,
        session_id: str,
        photo_paths: List[str],
        auto_pair: bool = True
    ) -> List[PhotoInfo]:
        """Add photos to a session and optionally auto-pair obverse/reverse."""
        session = self.sessions.get(session_id)
        if not session:
            return []

        photos = []
        for path in photo_paths:
            if not os.path.exists(path):
                continue
            photo = PhotoInfo(
                file_path=path,
                side=self._detect_side_from_filename(path),
                quality=self._assess_photo_quality(path),
            )
            photos.append(photo)
            session.metrics.photos_processed += 1

        # Auto-pair photos if enabled
        if auto_pair and len(photos) >= 2:
            photos = self._auto_pair_photos(photos)

        # Create a candidate for each photo group
        for photo in photos:
            candidate_id = f"{session_id}_candidate_{len(session.queue.candidates) + 1}"
            candidate = CollectionAssistantCandidate(
                id=candidate_id,
                source=CandidateSource.PHOTO,
                photos=[photo],
            )
            session.queue.candidates.append(candidate)
            session.metrics.candidates_generated += 1

        return photos

    def _detect_side_from_filename(self, file_path: str) -> PhotoSide:
        """Detect obverse/reverse from filename keywords."""
        lower_name = os.path.basename(file_path).lower()
        obverse_terms = ("obverse", "front", "obv", "f_", "_f", "_f_", "front_", "_front")
        reverse_terms = ("reverse", "back", "rev", "r_", "_r", "_r_", "back_", "_back")

        if any(term in lower_name for term in obverse_terms):
            return PhotoSide.OBVERSE
        if any(term in lower_name for term in reverse_terms):
            return PhotoSide.REVERSE
        return PhotoSide.UNKNOWN

    def _assess_photo_quality(self, file_path: str) -> PhotoQuality:
        """Assess photo quality from file metadata."""
        try:
            size = os.path.getsize(file_path)
            if size < 50 * 1024:  # < 50KB
                return PhotoQuality.POOR
            elif size < 200 * 1024:  # < 200KB
                return PhotoQuality.FAIR
            elif size < 1000 * 1024:  # < 1MB
                return PhotoQuality.GOOD
            else:
                return PhotoQuality.EXCELLENT
        except OSError:
            return PhotoQuality.UNUSABLE

    def _auto_pair_photos(self, photos: List[PhotoInfo]) -> List[PhotoInfo]:
        """Auto-pair obverse and reverse photos based on filenames."""
        # Simple pairing: group by base filename (without side indicator)
        groups: Dict[str, List[PhotoInfo]] = {}
        for photo in photos:
            base = self._extract_base_filename(photo.file_path)
            groups.setdefault(base, []).append(photo)

        for base, group in groups.items():
            if len(group) >= 2:
                # Mark as paired
                for photo in group:
                    photo.has_pair = True
                    # Find the paired photo (different side)
                    for other in group:
                        if other.file_path != photo.file_path:
                            photo.paired_photo = other.file_path

        return photos

    def _extract_base_filename(self, file_path: str) -> str:
        """Extract base filename without side indicators."""
        name = os.path.splitext(os.path.basename(file_path))[0].lower()
        # Remove common side indicators
        for suffix in ("_obverse", "_reverse", "_front", "_back", "_obv", "_rev",
                       "_f", "_r", "_o", "_b", " obverse", " reverse", " front", " back"):
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        return name.strip("_-")

    def process_ocr_for_candidate(
        self,
        session_id: str,
        candidate_id: str,
        ocr_text: Optional[str] = None
    ) -> Optional[OCRCandidate]:
        """Process OCR for a candidate."""
        session = self.sessions.get(session_id)
        if not session:
            return None

        candidate = next(
            (c for c in session.queue.candidates if c.id == candidate_id),
            None
        )
        if not candidate:
            return None

        session.metrics.ocr_attempts += 1

        if not ocr_text:
            # Simulate OCR from photo (in real use, this would call OCR engine)
            ocr_text = self._simulate_ocr_from_photos(candidate.photos)

        # Parse OCR text for coin information
        ocr_result = self._parse_ocr_text(ocr_text)
        candidate.ocr_result = ocr_result

        if ocr_result.confidence >= 0.5:
            session.metrics.ocr_successes += 1

        # Build suggested identification
        candidate.suggested_identification = self._build_suggested_identification(ocr_result)

        # Update candidate confidence
        candidate.confidence = ocr_result.confidence
        candidate.evidence = ocr_result.evidence

        return ocr_result

    def _simulate_ocr_from_photos(self, photos: List[PhotoInfo]) -> str:
        """Simulate OCR text from photos."""
        # In a real implementation, this would call the OCR engine
        # For now, return empty text to allow manual entry
        return ""

    def _parse_ocr_text(self, ocr_text: str) -> OCRCandidate:
        """Parse OCR text to extract coin information."""
        import re

        result = OCRCandidate(raw_text=ocr_text)

        if not ocr_text:
            result.confidence = 0.0
            result.warnings.append("No OCR text available")
            return result

        # Extract year (4 digits, typically 1800-2026)
        year_match = re.search(r'\b(1[8-9]\d{2}|20\d{2})\b', ocr_text)
        if year_match:
            result.detected_year = year_match.group(1)
            result.evidence.append(f"Year detected: {result.detected_year}")

        # Extract denomination
        denom_patterns = [
            r'\b(\d+\s*(?:cents?|cent))\b',
            r'\b(dime|quarter|half dollar|dollar|penny|nickel)\b',
            r'\b(\d+\s*\xc2\xa2)\b',  # ¢ symbol
        ]
        for pattern in denom_patterns:
            match = re.search(pattern, ocr_text, re.IGNORECASE)
            if match:
                result.detected_denomination = match.group(1).strip()
                result.evidence.append(f"Denomination detected: {result.detected_denomination}")
                break

        # Extract country
        country_patterns = [
            r'\b(canada|newfoundland|united states|uk|great britain|australia)\b',
            r'\b(cdn|ca|us|uk|au)\b',
        ]
        for pattern in country_patterns:
            match = re.search(pattern, ocr_text, re.IGNORECASE)
            if match:
                country = match.group(1).lower()
                if country in ("cdn", "ca"):
                    country = "canada"
                elif country == "us":
                    country = "united states"
                elif country == "au":
                    country = "australia"
                result.detected_country = country.title()
                result.evidence.append(f"Country detected: {result.detected_country}")
                break

        # Calculate confidence based on how many fields were detected
        detected_fields = sum(1 for f in [result.detected_year, result.detected_denomination,
                                           result.detected_country] if f)
        result.confidence = detected_fields / 3.0

        # Set trust level
        if result.confidence >= 0.8:
            result.trust_level = "HIGH"
        elif result.confidence >= 0.5:
            result.trust_level = "MEDIUM"
        else:
            result.trust_level = "LOW"

        if result.confidence < 0.5:
            result.warnings.append("Low confidence detection. Manual review recommended.")

        return result

    def _build_suggested_identification(self, ocr_result: OCRCandidate) -> Dict[str, Any]:
        """Build suggested identification from OCR result."""
        if not ocr_result:
            return {}

        return {
            "year": ocr_result.detected_year or "",
            "denomination": ocr_result.detected_denomination or "",
            "country": ocr_result.detected_country or "",
            "variety": ocr_result.detected_variety or "",
            "confidence": ocr_result.confidence,
            "trust_level": ocr_result.trust_level,
        }

    def check_collection_for_candidate(
        self,
        session_id: str,
        candidate_id: str,
        collection_items: List[Dict[str, Any]]
    ) -> CollectionMatch:
        """Check if candidate already exists in collection."""
        session = self.sessions.get(session_id)
        if not session:
            return CollectionMatch()

        candidate = next(
            (c for c in session.queue.candidates if c.id == candidate_id),
            None
        )
        if not candidate:
            return CollectionMatch()

        match = CollectionMatch()
        suggested = candidate.suggested_identification

        if not suggested or not collection_items:
            return match

        # Look for exact or similar matches
        for item in collection_items:
            item_year = str(item.get("year", ""))
            item_denom = str(item.get("denomination", "")).lower()
            item_country = str(item.get("country", "")).lower()

            cand_year = str(suggested.get("year", ""))
            cand_denom = str(suggested.get("denomination", "")).lower()
            cand_country = str(suggested.get("country", "")).lower()

            # Exact match check
            if (item_year == cand_year and
                item_denom == cand_denom and
                item_country == cand_country):
                match.matched = True
                match.match_type = "exact"
                match.existing_item = item
                match.duplicate_risk = "high"
                match.notes.append(f"Exact duplicate found: {item_country.title()} {item_denom} {item_year}")
                return match

            # Similar match check
            score = 0
            if item_year == cand_year:
                score += 0.4
            if item_denom == cand_denom:
                score += 0.3
            if item_country == cand_country:
                score += 0.3

            if score > match.similarity_score:
                match.similarity_score = score
                if score >= 0.7:
                    match.matched = True
                    match.match_type = "similar"
                    match.existing_item = item
                    match.duplicate_risk = "medium"
                    match.notes.append(f"Similar item found: {item_country.title()} {item_denom} {item_year}")

        if not match.matched:
            match.notes.append("No matching item found in collection")

        return match

    def check_collection_gaps(
        self,
        session_id: str,
        candidate_id: str,
        series_data: Optional[Dict[str, Any]] = None
    ) -> CollectionGapInfo:
        """Check if candidate fills a collection gap."""
        session = self.sessions.get(session_id)
        if not session:
            return CollectionGapInfo()

        candidate = next(
            (c for c in session.queue.candidates if c.id == candidate_id),
            None
        )
        if not candidate:
            return CollectionGapInfo()

        gap = CollectionGapInfo()
        suggested = candidate.suggested_identification

        if not suggested:
            return gap

        # Check for series gaps if series data provided
        if series_data:
            series_definitions = series_data.get("series_definitions", [])
            for series_def in series_definitions:
                series_name = series_def.get("name", "")
                owned_dates = series_def.get("owned_dates", [])
                missing_dates = series_def.get("missing_dates", [])
                cand_year = str(suggested.get("year", ""))

                if cand_year in missing_dates:
                    gap.fills_gap = True
                    gap.gap_type = "series"
                    gap.series_name = series_name
                    gap.missing_dates = [cand_year]
                    gap.impact_score = 0.8
                    return gap

        # Check for country/denomination gaps
        if suggested.get("country") and suggested.get("denomination"):
            gap.fills_gap = True
            gap.gap_type = "denomination"
            gap.impact_score = 0.5

        return gap

    def check_acquisition_priority(
        self,
        session_id: str,
        candidate_id: str,
        want_list: Optional[List[Dict[str, Any]]] = None,
        strategy_data: Optional[Dict[str, Any]] = None
    ) -> AcquisitionPriorityInfo:
        """Check if candidate matches acquisition priorities."""
        session = self.sessions.get(session_id)
        if not session:
            return AcquisitionPriorityInfo()

        candidate = next(
            (c for c in session.queue.candidates if c.id == candidate_id),
            None
        )
        if not candidate:
            return AcquisitionPriorityInfo()

        priority = AcquisitionPriorityInfo()
        suggested = candidate.suggested_identification

        if not suggested:
            return priority

        # Check WANT_LIST
        if want_list:
            for want in want_list:
                want_year = str(want.get("year", ""))
                want_denom = str(want.get("denomination", "")).lower()
                want_country = str(want.get("country", "")).lower()

                cand_year = str(suggested.get("year", ""))
                cand_denom = str(suggested.get("denomination", "")).lower()
                cand_country = str(suggested.get("country", "")).lower()

                if (want_year == cand_year and
                    want_denom == cand_denom and
                    want_country == cand_country):
                    priority.has_priority = True
                    priority.priority_category = "want_list"
                    priority.priority_score = 1.0
                    priority.strategic_reason = "Item is on the WANT_LIST"
                    return priority

        # Check strategy data for priority matches
        if strategy_data:
            immediate_priorities = strategy_data.get("immediate_priorities", [])
            for p in immediate_priorities:
                target = p.get("target", "").lower()
                cand_label = candidate.display_label.lower()
                if cand_label in target or target in cand_label:
                    priority.has_priority = True
                    priority.priority_category = "strategy"
                    priority.priority_score = 0.9
                    priority.strategic_reason = p.get("strategic_reason", "")
                    priority.budget_guidance = p.get("budget_guidance", "")
                    return priority

        return priority

    def build_side_by_side_comparison(
        self,
        session_id: str,
        candidate_id: str
    ) -> SideBySideComparison:
        """Build a side-by-side comparison for review."""
        session = self.sessions.get(session_id)
        if not session:
            return SideBySideComparison(
                candidate=CollectionAssistantCandidate(id=candidate_id)
            )

        candidate = next(
            (c for c in session.queue.candidates if c.id == candidate_id),
            None
        )
        if not candidate:
            return SideBySideComparison(
                candidate=CollectionAssistantCandidate(id=candidate_id)
            )

        comparison = SideBySideComparison(
            candidate=candidate,
            existing_match=candidate.collection_match.existing_item if candidate.collection_match else None,
            suggested_identification=candidate.suggested_identification,
            confidence=candidate.confidence,
        )

        # Build evidence
        evidence = []
        if candidate.ocr_result:
            evidence.append(f"OCR confidence: {candidate.ocr_result.confidence:.1%}")
            evidence.append(f"Trust level: {candidate.ocr_result.trust_level}")
        if candidate.fills_collection_gap:
            evidence.append(f"Fills gap: {candidate.gap_info.gap_type}")
        if candidate.acquisition_priority.has_priority:
            evidence.append(f"Priority: {candidate.acquisition_priority.priority_category}")
        comparison.evidence = evidence

        # Build recommendations
        recommendations = []
        if candidate.has_high_confidence and not candidate.is_duplicate_risk:
            recommendations.append("High confidence, no duplicates. Consider approval.")
        if candidate.fills_collection_gap:
            recommendations.append("Fills collection gap. Consider approval.")
        if candidate.is_duplicate_risk:
            recommendations.append("Duplicate risk detected. Review carefully.")
        if not candidate.has_high_confidence:
            recommendations.append("Low confidence. Verify manually before approval.")
        if not candidate.is_photo_pair_complete:
            recommendations.append("Incomplete photo pair. Consider adding missing side.")
        comparison.recommendations = recommendations

        # Build warnings
        warnings = []
        if candidate.is_duplicate_risk:
            warnings.append(f"Duplicate risk: {candidate.collection_match.duplicate_risk}")
        if not candidate.has_high_confidence:
            warnings.append("Low confidence detection")
        if not candidate.is_photo_pair_complete:
            warnings.append("Missing photo side")
        comparison.warnings = warnings

        return comparison

    def review_candidate(
        self,
        session_id: str,
        candidate_id: str,
        status: ReviewStatus,
        notes: str = ""
    ) -> bool:
        """Review a candidate and update its status."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        candidate = next(
            (c for c in session.queue.candidates if c.id == candidate_id),
            None
        )
        if not candidate:
            return False

        candidate.review_status = status
        candidate.review_notes = notes
        candidate.reviewed_at = datetime.now()

        # Update metrics
        session.metrics.reviews_completed += 1
        if status == ReviewStatus.APPROVED:
            session.metrics.approvals += 1
        elif status == ReviewStatus.REJECTED:
            session.metrics.rejections += 1
        elif status == ReviewStatus.NEEDS_REVIEW:
            session.metrics.needs_review += 1

        # Update average confidence
        if session.metrics.reviews_completed > 0:
            total_conf = sum(c.confidence for c in session.queue.candidates if c.is_reviewed)
            session.metrics.average_confidence = total_conf / session.metrics.reviews_completed

        # Estimate time saved (rough heuristic: 120 seconds per item for manual entry vs 30 with assistant)
        session.metrics.estimated_time_saved = session.metrics.reviews_completed * 90

        return True

    def get_next_candidate_for_review(
        self,
        session_id: str
    ) -> Optional[CollectionAssistantCandidate]:
        """Get the next candidate ready for review."""
        session = self.sessions.get(session_id)
        if not session:
            return None

        # Prioritize: high confidence, gap-filling, non-duplicate candidates
        candidates = session.queue.candidates
        prioritized = sorted(
            candidates,
            key=lambda c: (
                c.review_status == ReviewStatus.PENDING,
                c.fills_collection_gap,
                c.has_high_confidence,
                not c.is_duplicate_risk,
                c.confidence,
            ),
            reverse=True
        )

        for candidate in prioritized:
            if candidate.is_pending:
                return candidate

        return None

    def get_incomplete_reviews(self, session_id: str) -> List[CollectionAssistantCandidate]:
        """Get candidates with incomplete reviews."""
        session = self.sessions.get(session_id)
        if not session:
            return []

        return [c for c in session.queue.candidates if c.review_status == ReviewStatus.INCOMPLETE]

    def complete_session(self, session_id: str) -> Optional[AssistantSummary]:
        """Complete a collection assistant session."""
        session = self.sessions.get(session_id)
        if not session:
            return None

        session.end_time = datetime.now()
        session.status = "completed"
        session.metrics.total_session_time = session.duration.total_seconds()

        # Mark any remaining pending as incomplete
        for candidate in session.queue.candidates:
            if candidate.is_pending:
                candidate.review_status = ReviewStatus.INCOMPLETE

        return session

    def export_session_markdown(self, session_id: str) -> str:
        """Export session as Markdown."""
        session = self.sessions.get(session_id)
        if not session:
            return ""

        lines = [
            "# Collection Assistant Session Report",
            "",
            f"**Session ID:** {session.session_id}",
            f"**Start Time:** {session.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Status:** {session.status}",
            f"**Duration:** {session.duration.total_seconds() / 60:.1f} minutes",
            "",
            "## Summary",
            "",
            f"- Total Candidates: {session.queue.total_count}",
            f"- Reviewed: {session.queue.reviewed_count}",
            f"- Approved: {session.queue.approved_count}",
            f"- Rejected: {session.queue.rejected_count}",
            f"- Pending: {session.queue.pending_count}",
            f"- Completion: {session.queue.completion_percentage:.1f}%",
            "",
            "## Productivity Metrics",
            "",
            f"- Photos Processed: {session.metrics.photos_processed}",
            f"- OCR Success Rate: {session.metrics.ocr_success_rate:.1f}%",
            f"- Average Confidence: {session.metrics.average_confidence:.1%}",
            f"- Estimated Time Saved: {session.metrics.estimated_time_saved_minutes:.1f} minutes",
            "",
            "## Candidates",
            "",
        ]

        for candidate in session.queue.candidates:
            lines.extend([
                f"### {candidate.display_label}",
                "",
                f"- **Status:** {candidate.review_status.value}",
                f"- **Confidence:** {candidate.confidence:.1%}",
                f"- **Source:** {candidate.source.value}",
                f"- **Photos:** {len(candidate.photos)}",
            ])
            if candidate.is_photo_pair_complete:
                lines.append("- **Photo Pair:** Complete")
            else:
                lines.append("- **Photo Pair:** Incomplete")
            if candidate.collection_match.matched:
                lines.append(f"- **Duplicate Risk:** {candidate.collection_match.duplicate_risk}")
            if candidate.fills_collection_gap:
                lines.append(f"- **Gap Fill:** {candidate.gap_info.gap_type}")
            if candidate.acquisition_priority.has_priority:
                lines.append(f"- **Priority:** {candidate.acquisition_priority.priority_category}")
            if candidate.review_notes:
                lines.append(f"- **Notes:** {candidate.review_notes}")
            lines.append("")

        return "\n".join(lines)

    def export_session_csv(self, session_id: str) -> str:
        """Export session as CSV."""
        session = self.sessions.get(session_id)
        if not session:
            return ""

        lines = [
            "ID,Display,Source,Confidence,Status,DuplicateRisk,GapFill,Priority,Photos,ReviewNotes"
        ]

        for c in session.queue.candidates:
            gap = "yes" if c.fills_collection_gap else "no"
            priority = "yes" if c.acquisition_priority.has_priority else "no"
            lines.append(
                f'"{c.id}","{c.display_label}","{c.source.value}",{c.confidence:.2f},'
                f'"{c.review_status.value}","{c.collection_match.duplicate_risk}",'
                f'"{gap}","{priority}",{len(c.photos)},"{c.review_notes}"'
            )

        return "\n".join(lines)

    def export_review_queue_markdown(self, session_id: str) -> str:
        """Export review queue as Markdown."""
        session = self.sessions.get(session_id)
        if not session:
            return ""

        lines = ["# Collection Assistant Review Queue", ""]

        for candidate in session.queue.candidates:
            if not candidate.is_pending:
                continue
            lines.extend([
                f"## {candidate.display_label}",
                "",
                f"- **ID:** {candidate.id}",
                f"- **Confidence:** {candidate.confidence:.1%}",
                f"- **Source:** {candidate.source.value}",
                f"- **Photos:** {len(candidate.photos)}",
            ])
            if candidate.suggested_identification:
                lines.append(f"- **Suggested:** {candidate.suggested_identification}")
            lines.append("")

        return "\n".join(lines)

    def export_productivity_report_markdown(self, session_id: str) -> str:
        """Export productivity report as Markdown."""
        session = self.sessions.get(session_id)
        if not session:
            return ""

        metrics = session.metrics
        return f"""# Productivity Report

**Session:** {session.session_id}
**Generated:** {metrics.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

## Metrics

| Metric | Value |
|--------|-------|
| Photos Processed | {metrics.photos_processed} |
| OCR Attempts | {metrics.ocr_attempts} |
| OCR Successes | {metrics.ocr_successes} |
| OCR Success Rate | {metrics.ocr_success_rate:.1f}% |
| Candidates Generated | {metrics.candidates_generated} |
| Reviews Completed | {metrics.reviews_completed} |
| Approval Rate | {metrics.approval_rate:.1f}% |
| Average Confidence | {metrics.average_confidence:.1%} |
| Estimated Time Saved | {metrics.estimated_time_saved_minutes:.1f} minutes |

## Session Status

- Total Duration: {session.duration.total_seconds() / 60:.1f} minutes
- Completion: {session.queue.completion_percentage:.1f}%
"""
