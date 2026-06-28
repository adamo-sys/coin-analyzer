"""
Smart Phone Cataloguer — Thin orchestration facade over PhotoCaptureWorkflow.

Provides a simplified, phone-optimized API for rapid coin cataloguing
from mobile images by reusing the existing PhotoCaptureWorkflow engine.

v8.0 milestone: Smart Phone Cataloguer
"""

from typing import List, Dict, Optional, Any, Iterable
from dataclasses import dataclass, field
from datetime import datetime

from photo_capture_workflow import (
    PhotoCaptureWorkflow,
    PhotoCaptureSession,
    CapturedPhoto,
    PhotoCaptureReport,
    SESSION_COIN_FRONT_BACK,
    SESSION_NOTE_FRONT_BACK,
    SESSION_LISTING_PHOTOS,
    ROLE_COIN_FRONT,
    ROLE_COIN_BACK,
    ROLE_NOTE_FRONT,
    ROLE_NOTE_BACK,
    ROLE_LISTING,
    SOURCE_PHONE_CAMERA,
    SOURCE_LISTING_PHOTO,
    SOURCE_IMPORT,
)

from ocr_assisted_identification import OCRIdentificationEngine, OCRIdentificationReport
from collection_intelligence import CollectionIntelligenceEngine, AcquisitionTarget
from coin_collection import CoinItem


@dataclass

class CatalogueResult:
    """Result of a single photo cataloguing attempt."""
    session_id: str
    subject: str
    photos: List[Dict[str, Any]]
    status: str
    ocr_ready: bool
    review_ready: bool
    message: str
    ocr_report: Optional[OCRIdentificationReport] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "subject": self.subject,
            "photos": self.photos,
            "status": self.status,
            "ocr_ready": self.ocr_ready,
            "review_ready": self.review_ready,
            "message": self.message,
            "ocr_candidate_count": len(self.ocr_report.candidates) if self.ocr_report else 0,
        }


@dataclass
class CollectionMatchResult:
    """Result of matching a catalogued item against the existing collection."""
    session_id: str
    subject: str
    is_duplicate: bool
    duplicate_count: int
    is_upgrade_candidate: bool
    current_best_grade: str
    gap_analysis: Optional[Dict[str, Any]] = None
    acquisition_targets: List[Dict[str, Any]] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "subject": self.subject,
            "is_duplicate": self.is_duplicate,
            "duplicate_count": self.duplicate_count,
            "is_upgrade_candidate": self.is_upgrade_candidate,
            "current_best_grade": self.current_best_grade,
            "gap_analysis": self.gap_analysis,
            "acquisition_targets": self.acquisition_targets,
            "message": self.message,
        }


@dataclass
class ProposedCollectionEntry:
    """A proposed collection entry draft, ready for user review.

    This is a read-only proposed entry. No collection mutation occurs.
    The user must explicitly confirm before any item is added to the collection.
    """
    session_id: str
    proposed_item: Dict[str, Any]
    ocr_metadata: Optional[Dict[str, Any]] = None
    match_analysis: Optional[Dict[str, Any]] = None
    confidence_score: float = 0.0
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    status: str = "pending_review"  # pending_review, duplicate_detected, upgrade_candidate, gap_fill

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "proposed_item": self.proposed_item,
            "ocr_metadata": self.ocr_metadata,
            "match_analysis": self.match_analysis,
            "confidence_score": self.confidence_score,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "status": self.status,
        }

    def to_coin_item(self) -> CoinItem:
        """Convert the proposed entry to a CoinItem for review.

        This does NOT add the item to the collection. It creates the item
        for display and validation purposes only.
        """
        data = self.proposed_item.copy()
        # Ensure all required CoinItem fields are present
        defaults = {
            "id": data.get("id", ""),
            "image_path": data.get("image_path", ""),
            "country": data.get("country", ""),
            "denomination": data.get("denomination", ""),
            "year": data.get("year", ""),
            "grade": data.get("grade", ""),
            "notes": data.get("notes", ""),
            "date_added": data.get("date_added", ""),
            "auto_detected": data.get("auto_detected", False),
            "detection_confidence": data.get("detection_confidence", 0.0),
            "issuer": data.get("issuer", ""),
            "currency": data.get("currency", ""),
            "face_value": data.get("face_value", ""),
            "reference": data.get("reference", ""),
            "numista_n": data.get("numista_n", ""),
            "title": data.get("title", ""),
            "quantity": data.get("quantity", 1),
            "estimate_cad": data.get("estimate_cad", 0.0),
            "comments": data.get("comments", ""),
            "from_numista": data.get("from_numista", False),
        }
        return CoinItem(**defaults)


@dataclass
class BatchCatalogueResult:
    """Result of a batch cataloguing operation."""
    results: List[CatalogueResult] = field(default_factory=list)
    total_sessions: int = 0
    total_photos: int = 0
    ocr_ready_count: int = 0
    review_ready_count: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "total_sessions": self.total_sessions,
            "total_photos": self.total_photos,
            "ocr_ready_count": self.ocr_ready_count,
            "review_ready_count": self.review_ready_count,
            "errors": self.errors,
        }


class SmartPhoneCataloguer:
    """Orchestrates photo-to-collection workflow using existing PhotoCaptureWorkflow.

    This is a thin facade that simplifies the PhotoCaptureWorkflow API for
    phone-optimized single-coin and batch cataloguing workflows.
    """

    def __init__(self, workflow: Optional[PhotoCaptureWorkflow] = None):
        self.workflow = workflow or PhotoCaptureWorkflow()

    def catalog_coin(self, subject: str, front_path: str = "", back_path: str = "",
                     location: str = "", notes: str = "") -> CatalogueResult:
        """Catalogue a single coin from front/back photos.

        Reuses PhotoCaptureWorkflow.capture_coin_pair() for session creation.
        """
        session = self.workflow.capture_coin_pair(
            subject=subject,
            front_path=front_path,
            back_path=back_path,
            location=location,
            notes=notes,
        )
        return self._session_to_result(session)

    def catalog_note(self, subject: str, front_path: str = "", back_path: str = "",
                     location: str = "", notes: str = "") -> CatalogueResult:
        """Catalogue a banknote from front/back photos.

        Reuses PhotoCaptureWorkflow.capture_note_pair() for session creation.
        """
        session = self.workflow.capture_note_pair(
            subject=subject,
            front_path=front_path,
            back_path=back_path,
            location=location,
            notes=notes,
        )
        return self._session_to_result(session)

    def catalog_listing(self, subject: str, file_path: str, candidate_id: str = "",
                        notes: str = "") -> CatalogueResult:
        """Catalogue a listing photo (e.g., from eBay, auction site).

        Reuses PhotoCaptureWorkflow.capture_listing_photo() for session creation.
        """
        session = self.workflow.capture_listing_photo(
            subject=subject,
            file_path=file_path,
            candidate_id=candidate_id,
            notes=notes,
        )
        return self._session_to_result(session)

    def add_photo_to_session(self, session: PhotoCaptureSession, file_path: str,
                             photo_role: str, **kwargs: Any) -> CapturedPhoto:
        """Add a photo to an existing session.

        Reuses PhotoCaptureWorkflow.capture_photo() for photo addition.
        """
        return self.workflow.capture_photo(session, file_path, photo_role, **kwargs)

    def batch_catalogue(self, items: List[Dict[str, Any]]) -> BatchCatalogueResult:
        """Catalogue multiple items from a batch of photo paths.

        Each item dict should have:
        - 'type': 'coin', 'note', or 'listing'
        - 'subject': item description
        - 'front_path': front photo path (for coin/note)
        - 'back_path': back photo path (for coin/note)
        - 'file_path': single photo path (for listing)
        - 'location': optional location
        - 'notes': optional notes
        - 'candidate_id': optional candidate ID (for listing)
        """
        result = BatchCatalogueResult()

        for item in items:
            try:
                item_type = item.get("type", "coin")
                subject = item.get("subject", "Unknown")

                # Validate required fields
                if item_type == "listing" and not item.get("file_path"):
                    raise ValueError("Listing items require 'file_path'")

                if item_type == "coin":
                    catalogue_result = self.catalog_coin(
                        subject=subject,
                        front_path=item.get("front_path", ""),
                        back_path=item.get("back_path", ""),
                        location=item.get("location", ""),
                        notes=item.get("notes", ""),
                    )
                elif item_type == "note":
                    catalogue_result = self.catalog_note(
                        subject=subject,
                        front_path=item.get("front_path", ""),
                        back_path=item.get("back_path", ""),
                        location=item.get("location", ""),
                        notes=item.get("notes", ""),
                    )
                elif item_type == "listing":
                    catalogue_result = self.catalog_listing(
                        subject=subject,
                        file_path=item.get("file_path", ""),
                        candidate_id=item.get("candidate_id", ""),
                        notes=item.get("notes", ""),
                    )
                else:
                    catalogue_result = CatalogueResult(
                        session_id="",
                        subject=subject,
                        photos=[],
                        status="error",
                        ocr_ready=False,
                        review_ready=False,
                        message=f"Unknown item type: {item_type}",
                    )

                result.results.append(catalogue_result)
                if catalogue_result.ocr_ready:
                    result.ocr_ready_count += 1
                if catalogue_result.review_ready:
                    result.review_ready_count += 1

            except Exception as e:
                result.errors.append(f"Failed to catalogue {item.get('subject', 'Unknown')}: {str(e)}")

        result.total_sessions = len(self.workflow.sessions)
        result.total_photos = sum(len(s.photos) for s in self.workflow.sessions)
        return result

    def get_report(self) -> PhotoCaptureReport:
        """Get a report of all capture sessions.

        Reuses PhotoCaptureWorkflow.report().
        """
        return self.workflow.report()

    def get_ocr_sources(self) -> List[Dict[str, str]]:
        """Get all photos ready for OCR processing.

        Reuses PhotoCaptureWorkflow.ocr_sources().
        """
        return self.workflow.ocr_sources()

    def get_photo_vault_records(self) -> List[Any]:
        """Get all photo vault records for storage.

        Reuses PhotoCaptureWorkflow.photo_vault_records().
        """
        return self.workflow.photo_vault_records()

    def _session_to_result(self, session: PhotoCaptureSession) -> CatalogueResult:
        """Convert a PhotoCaptureSession to a CatalogueResult."""
        photos = []
        for photo in session.photos:
            photos.append({
                "photo_id": photo.photo_id,
                "file_path": photo.file_path,
                "role": photo.photo_role,
                "status": photo.workflow_status,
                "review": photo.review_status,
                "ready_for_ocr": photo.ready_for_ocr,
            })

        status = "complete" if session.front_back_complete else "incomplete"
        if session.missing_front:
            status = "needs_front"
        elif session.missing_back:
            status = "needs_back"

        return CatalogueResult(
            session_id=session.session_id,
            subject=session.subject,
            photos=photos,
            status=status,
            ocr_ready=session.ready_for_ocr,
            review_ready=session.ready_for_review,
            message=f"Session {session.session_id}: {len(session.photos)} photo(s), status: {status}",
        )


    def identify_session(self, session: PhotoCaptureSession, raw_text_by_photo_id: Optional[Dict[str, str]] = None) -> OCRIdentificationReport:
        """Run OCR identification on a completed photo capture session.

        Reuses OCRIdentificationEngine.identify_from_session() for metadata extraction.
        """
        engine = OCRIdentificationEngine()
        return engine.identify_from_session(session, raw_text_by_photo_id=raw_text_by_photo_id)

    def identify_photo(self, photo: CapturedPhoto, raw_text: Optional[str] = None) -> OCRIdentificationReport:
        """Run OCR identification on a single captured photo.

        Reuses OCRIdentificationEngine.identify_from_captured_photo() for metadata extraction.
        """
        engine = OCRIdentificationEngine()
        return engine.identify_from_captured_photo(photo, raw_text=raw_text)

    def batch_identify(self, raw_text_by_photo_id: Optional[Dict[str, str]] = None) -> Dict[str, OCRIdentificationReport]:
        """Run OCR identification on all sessions in the workflow.

        Returns a mapping of session_id -> OCRIdentificationReport.
        """
        results = {}
        for session in self.workflow.sessions:
            if session.ready_for_ocr:
                results[session.session_id] = self.identify_session(session, raw_text_by_photo_id)
        return results

    def catalogue_and_identify(self, subject: str, front_path: str = "", back_path: str = "",
                                location: str = "", notes: str = "",
                                raw_text_by_photo_id: Optional[Dict[str, str]] = None) -> CatalogueResult:
        """Catalogue a coin and immediately run OCR identification.

        Combines catalog_coin() + identify_session() for streamlined workflow.
        """
        result = self.catalog_coin(subject, front_path, back_path, location, notes)
        if result.ocr_ready:
            session = self.workflow.sessions[-1]
            ocr_report = self.identify_session(session, raw_text_by_photo_id)
            result.ocr_report = ocr_report
            result.message += f" | OCR: {ocr_report.candidate_count} candidate(s)"
        return result


    def match_against_collection(self, collection_items: Iterable, 
                                  session: Optional[PhotoCaptureSession] = None) -> CollectionMatchResult:
        """Match a catalogued session against the existing collection.

        Reuses CollectionIntelligenceEngine for duplicate detection, gap analysis,
        and upgrade candidate identification.
        """
        engine = CollectionIntelligenceEngine(collection_items)

        # Detect duplicates
        duplicates = engine.detect_duplicates()

        # Detect upgrade candidates
        upgrade_candidates = engine.detect_upgrade_candidates()

        # Generate acquisition priorities (gap analysis)
        priorities = engine.generate_acquisition_priorities()

        # Check if this session's subject matches any duplicates
        subject = session.subject if session else ""
        is_duplicate = False
        duplicate_count = 0
        is_upgrade_candidate = False
        current_best_grade = ""

        for dup in duplicates:
            if subject and (dup["country"] in subject or dup["denomination"] in subject or dup["year"] in subject):
                is_duplicate = True
                duplicate_count = dup["count"]
                break

        for candidate in upgrade_candidates:
            if subject and (candidate["country"] in subject or candidate["denomination"] in subject or candidate["year"] in subject):
                is_upgrade_candidate = True
                current_best_grade = candidate["current_best_grade"]
                break

        # Gap analysis for the series this item belongs to
        gap_analysis = None
        series_analysis = engine.analyze_by_series()
        for (country, denomination), data in series_analysis.items():
            if subject and country in subject and denomination in subject:
                gap_analysis = {
                    "series": f"{country} / {denomination}",
                    "years_owned": data.get("years", []),
                    "missing_years": data.get("missing_years", []),
                    "completion_percentage": data.get("completion_percentage", 0.0),
                    "year_count": data.get("year_count", 0),
                }
                break

        # Acquisition targets relevant to this item
        acquisition_targets = []
        for target in priorities[:5]:  # Top 5 priorities
            if subject and (target.country in subject or target.denomination in subject):
                acquisition_targets.append(target.to_dict())

        message = f"Collection match: {len(duplicates)} duplicates, {len(upgrade_candidates)} upgrades, {len(priorities)} priorities"
        if is_duplicate:
            message += f" | Duplicate detected ({duplicate_count} copies)"
        if is_upgrade_candidate:
            message += f" | Upgrade candidate (best grade: {current_best_grade})"

        return CollectionMatchResult(
            session_id=session.session_id if session else "",
            subject=subject,
            is_duplicate=is_duplicate,
            duplicate_count=duplicate_count,
            is_upgrade_candidate=is_upgrade_candidate,
            current_best_grade=current_best_grade,
            gap_analysis=gap_analysis,
            acquisition_targets=acquisition_targets,
            message=message,
        )

    def batch_match(self, collection_items: Iterable) -> Dict[str, CollectionMatchResult]:
        """Match all sessions in the workflow against the collection.

        Returns a mapping of session_id -> CollectionMatchResult.
        """
        results = {}
        for session in self.workflow.sessions:
            results[session.session_id] = self.match_against_collection(collection_items, session)
        return results

    def get_gap_report(self, collection_items: Iterable) -> Dict[str, Any]:
        """Generate a full collection gap report.

        Reuses CollectionIntelligenceEngine.generate_gap_report().
        """
        engine = CollectionIntelligenceEngine(collection_items)
        return engine.generate_gap_report()

    def get_want_list(self, collection_items: Iterable, limit: int = 10) -> List[Dict[str, Any]]:
        """Generate a prioritized want list.

        Reuses CollectionIntelligenceEngine.generate_want_list().
        """
        engine = CollectionIntelligenceEngine(collection_items)
        targets = engine.generate_want_list(limit=limit)
        return [target.to_dict() for target in targets]

    def catalogue_match_and_identify(self, collection_items: Iterable, subject: str,
                                       front_path: str = "", back_path: str = "",
                                       location: str = "", notes: str = "",
                                       raw_text_by_photo_id: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Complete workflow: catalogue + OCR + collection match in one call.

        Combines catalogue_and_identify() + match_against_collection() for streamlined workflow.
        """
        catalogue_result = self.catalogue_and_identify(subject, front_path, back_path, location, notes, raw_text_by_photo_id)
        session = self.workflow.sessions[-1] if self.workflow.sessions else None
        match_result = self.match_against_collection(collection_items, session)

        return {
            "catalogue": catalogue_result.to_dict(),
            "match": match_result.to_dict(),
        }


    def create_proposed_entry(self, session: PhotoCaptureSession,
                               ocr_report: Optional[OCRIdentificationReport] = None,
                               match_result: Optional[CollectionMatchResult] = None) -> ProposedCollectionEntry:
        """Create a proposed collection entry from a completed session.

        This is read-only. No collection mutation occurs.
        The entry contains all metadata from OCR and collection matching
        for user review before confirmation.
        """
        # Build proposed item from session metadata and OCR results
        proposed_item = {
            "id": f"proposed_{session.session_id}",
            "image_path": session.photos[0].file_path if session.photos else "",
            "country": "",
            "denomination": "",
            "year": "",
            "grade": "",
            "notes": session.notes,
            "date_added": datetime.now().isoformat(),
            "auto_detected": ocr_report is not None,
            "detection_confidence": 0.0,
            "issuer": "",
            "currency": "",
            "face_value": "",
            "reference": "",
            "numista_n": "",
            "title": session.subject,
            "quantity": 1,
            "estimate_cad": 0.0,
            "comments": "",
            "from_numista": False,
        }

        # Extract metadata from OCR report if available
        ocr_metadata = None
        confidence_score = 0.0
        if ocr_report and ocr_report.candidates:
            top_candidate = ocr_report.candidates[0]
            proposed_item["country"] = top_candidate.country
            proposed_item["denomination"] = top_candidate.denomination
            proposed_item["year"] = top_candidate.year
            proposed_item["grade"] = getattr(top_candidate, "grade", "")
            proposed_item["reference"] = getattr(top_candidate, "reference", "")
            proposed_item["numista_n"] = getattr(top_candidate, "numista_n", "")
            proposed_item["title"] = getattr(top_candidate, "title", session.subject)
            proposed_item["detection_confidence"] = getattr(top_candidate, "overall_confidence", getattr(top_candidate, "confidence_score", 0.0))
            confidence_score = getattr(top_candidate, "overall_confidence", getattr(top_candidate, "confidence_score", 0.0))

            ocr_metadata = {
                "candidate_count": len(ocr_report.candidates),
                "top_candidate_country": top_candidate.country,
                "top_candidate_denomination": top_candidate.denomination,
                "top_candidate_year": top_candidate.year,
                "top_candidate_grade": "",  # grade not available on OCRIdentificationCandidate
                "top_candidate_confidence": getattr(top_candidate, "confidence_score", 0.0),  # overall_confidence not available, use confidence_score
                "evidence_summary": getattr(ocr_report, "evidence_summary", ""),
            }

        # Build match analysis from collection match result
        match_analysis = None
        warnings = []
        recommendations = []
        status = "pending_review"

        if match_result:
            match_analysis = match_result.to_dict()
            if match_result.is_duplicate:
                warnings.append(f"Duplicate detected: {match_result.duplicate_count} existing copies")
                recommendations.append("Review existing items before adding")
                status = "duplicate_detected"
            if match_result.is_upgrade_candidate:
                warnings.append(f"Upgrade candidate: current best grade is {match_result.current_best_grade}")
                recommendations.append("Consider if this is a better grade than existing")
                status = "upgrade_candidate"
            if match_result.gap_analysis and match_result.gap_analysis.get("missing_years"):
                recommendations.append("This item fills a gap in the series")
                status = "gap_fill"

        return ProposedCollectionEntry(
            session_id=session.session_id,
            proposed_item=proposed_item,
            ocr_metadata=ocr_metadata,
            match_analysis=match_analysis,
            confidence_score=confidence_score,
            warnings=warnings,
            recommendations=recommendations,
            status=status,
        )

    def batch_create_proposed_entries(self, collection_items: Iterable,
                                       raw_text_by_photo_id: Optional[Dict[str, str]] = None) -> List[ProposedCollectionEntry]:
        """Create proposed entries for all sessions in the workflow.

        Runs OCR + collection matching for each session and returns
        structured review objects. No collection mutation.
        """
        entries = []

        for session in self.workflow.sessions:
            if not session.ready_for_ocr:
                continue

            # Run OCR
            ocr_report = self.identify_session(session, raw_text_by_photo_id)

            # Run collection match
            match_result = self.match_against_collection(collection_items, session)

            # Create proposed entry
            entry = self.create_proposed_entry(session, ocr_report, match_result)
            entries.append(entry)

        return entries

    def review_entry(self, entry: ProposedCollectionEntry) -> Dict[str, Any]:
        """Generate a review summary for a proposed entry.

        Returns a structured review object with all metadata,
        warnings, and recommendations for user decision.
        """
        review = {
            "session_id": entry.session_id,
            "status": entry.status,
            "proposed_item": entry.proposed_item,
            "confidence_score": entry.confidence_score,
            "warnings": entry.warnings,
            "recommendations": entry.recommendations,
            "ocr_metadata": entry.ocr_metadata,
            "match_analysis": entry.match_analysis,
            "can_add_to_collection": len(entry.warnings) == 0 or entry.status == "gap_fill",
            "requires_user_review": True,
        }

        # Add review-specific guidance
        if entry.status == "duplicate_detected":
            review["review_guidance"] = "This item appears to be a duplicate. Please review existing collection items before confirming."
        elif entry.status == "upgrade_candidate":
            review["review_guidance"] = "This item may be an upgrade over existing items. Please verify grade and condition."
        elif entry.status == "gap_fill":
            review["review_guidance"] = "This item fills a gap in your collection series. Recommended for acquisition."
        else:
            review["review_guidance"] = "Please review the proposed item details and confirm accuracy."

        return review

    def full_catalogue_workflow(self, collection_items: Iterable, subject: str,
                                  front_path: str = "", back_path: str = "",
                                  location: str = "", notes: str = "",
                                  raw_text_by_photo_id: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Complete read-only workflow: catalogue + OCR + match + propose entry.

        This is the full Smart Phone Cataloguer workflow without any
        collection mutation. Returns a structured review object.
        """
        # Step 1: Catalogue photos
        catalogue_result = self.catalogue_and_identify(subject, front_path, back_path, location, notes, raw_text_by_photo_id)

        # Step 2: Get the session
        session = self.workflow.sessions[-1] if self.workflow.sessions else None
        if not session:
            return {
                "error": "No session created",
                "catalogue": catalogue_result.to_dict() if catalogue_result else None,
            }

        # Step 3: Collection match
        match_result = self.match_against_collection(collection_items, session)

        # Step 4: Create proposed entry
        ocr_report = catalogue_result.ocr_report if catalogue_result else None
        proposed_entry = self.create_proposed_entry(session, ocr_report, match_result)

        # Step 5: Generate review
        review = self.review_entry(proposed_entry)

        return {
            "catalogue": catalogue_result.to_dict() if catalogue_result else None,
            "match": match_result.to_dict() if match_result else None,
            "proposed_entry": proposed_entry.to_dict(),
            "review": review,
            "workflow_complete": True,
            "requires_user_confirmation": True,
        }


def run_smart_phone_cataloguer(items: List[Dict[str, Any]]) -> BatchCatalogueResult:
    """Convenience function to run a batch cataloguing operation."""
    cataloguer = SmartPhoneCataloguer()
    return cataloguer.batch_catalogue(items)


if __name__ == "__main__":
    # Example usage
    items = [
        {
            "type": "coin",
            "subject": "Canada 1 cent 1964",
            "front_path": "/path/to/front.jpg",
            "back_path": "/path/to/back.jpg",
        }
    ]
    result = run_smart_phone_cataloguer(items)
    print(f"Catalogued {result.total_sessions} sessions, {result.total_photos} photos")
    for r in result.results:
        print(f"  - {r.subject}: {r.status} (OCR ready: {r.ocr_ready})")
