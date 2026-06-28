"""
Smart Phone Cataloguer — Thin orchestration facade over PhotoCaptureWorkflow.

Provides a simplified, phone-optimized API for rapid coin cataloguing
from mobile images by reusing the existing PhotoCaptureWorkflow engine.

v8.0 milestone: Smart Phone Cataloguer
"""

from typing import List, Dict, Optional, Any
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "subject": self.subject,
            "photos": self.photos,
            "status": self.status,
            "ocr_ready": self.ocr_ready,
            "review_ready": self.review_ready,
            "message": self.message,
        }


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
