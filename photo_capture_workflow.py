"""Phone photo capture workflow metadata for Collector Companion.

This module organizes field-captured coin and banknote photos. It does not run
image recognition, attribution, grading, OCR identification, cloud sync, or
collection entry.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from photo_vault import PhotoRecord


SOURCE_PHONE_CAMERA = "Phone Camera"
SOURCE_LISTING_PHOTO = "Listing Photo"
SOURCE_IMPORT = "Imported Photo"

ROLE_COIN_FRONT = "Coin Front"
ROLE_COIN_BACK = "Coin Back"
ROLE_NOTE_FRONT = "Note Front"
ROLE_NOTE_BACK = "Note Back"
ROLE_LISTING = "Listing Photo"
ROLE_DETAIL = "Detail Photo"

STATUS_CAPTURED = "Captured"
STATUS_NEEDS_FRONT = "Needs Front"
STATUS_NEEDS_BACK = "Needs Back"
STATUS_COMPLETE = "Complete"
STATUS_READY_FOR_OCR = "Ready for OCR"
STATUS_READY_FOR_REVIEW = "Ready for Review"

REVIEW_PENDING = "Pending Review"
REVIEW_REVIEWED = "Reviewed"
REVIEW_HOLD = "Hold"

SESSION_COIN_FRONT_BACK = "Coin Front/Back"
SESSION_NOTE_FRONT_BACK = "Banknote Front/Back"
SESSION_LISTING_PHOTOS = "Listing Photos"

FRONT_ROLES = {ROLE_COIN_FRONT, ROLE_NOTE_FRONT}
BACK_ROLES = {ROLE_COIN_BACK, ROLE_NOTE_BACK}
OCR_READY_ROLES = {ROLE_COIN_FRONT, ROLE_COIN_BACK, ROLE_NOTE_FRONT, ROLE_NOTE_BACK, ROLE_LISTING, ROLE_DETAIL}


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        text = _text(value)
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def _normalize_choice(value: str, allowed: Iterable[str], default: str) -> str:
    text = _text(value)
    for option in allowed:
        if text.lower() == option.lower():
            return option
    return default


@dataclass
class CapturedPhoto:
    """Single metadata record for a captured or imported phone photo."""

    photo_id: str
    file_path: str
    source_type: str = SOURCE_PHONE_CAMERA
    photo_role: str = ROLE_COIN_FRONT
    captured_at: str = ""
    workflow_status: str = STATUS_CAPTURED
    review_status: str = REVIEW_PENDING
    notes: str = ""
    linked_candidate_id: str = ""
    linked_collection_item_id: str = ""
    linked_coin_name: str = ""

    def __post_init__(self) -> None:
        self.photo_id = _text(self.photo_id) or f"photo-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.file_path = _text(self.file_path)
        self.source_type = _normalize_choice(self.source_type, [SOURCE_PHONE_CAMERA, SOURCE_LISTING_PHOTO, SOURCE_IMPORT], SOURCE_PHONE_CAMERA)
        self.photo_role = _normalize_choice(
            self.photo_role,
            [ROLE_COIN_FRONT, ROLE_COIN_BACK, ROLE_NOTE_FRONT, ROLE_NOTE_BACK, ROLE_LISTING, ROLE_DETAIL],
            ROLE_COIN_FRONT,
        )
        self.captured_at = _text(self.captured_at) or _now_iso()
        self.workflow_status = _text(self.workflow_status) or STATUS_CAPTURED
        self.review_status = _normalize_choice(self.review_status, [REVIEW_PENDING, REVIEW_REVIEWED, REVIEW_HOLD], REVIEW_PENDING)
        self.notes = _text(self.notes)
        self.linked_candidate_id = _text(self.linked_candidate_id)
        self.linked_collection_item_id = _text(self.linked_collection_item_id)
        self.linked_coin_name = _text(self.linked_coin_name)

    @property
    def is_front(self) -> bool:
        return self.photo_role in FRONT_ROLES

    @property
    def is_back(self) -> bool:
        return self.photo_role in BACK_ROLES

    @property
    def ready_for_ocr(self) -> bool:
        return bool(self.file_path and self.photo_role in OCR_READY_ROLES and self.workflow_status in {STATUS_COMPLETE, STATUS_READY_FOR_OCR, STATUS_READY_FOR_REVIEW})

    @property
    def ready_for_review(self) -> bool:
        return bool(self.file_path and self.review_status == REVIEW_PENDING and self.workflow_status in {STATUS_COMPLETE, STATUS_READY_FOR_OCR, STATUS_READY_FOR_REVIEW})

    def mark_status(self, workflow_status: str = "", review_status: str = "") -> "CapturedPhoto":
        if workflow_status:
            self.workflow_status = _text(workflow_status)
        if review_status:
            self.review_status = _normalize_choice(review_status, [REVIEW_PENDING, REVIEW_REVIEWED, REVIEW_HOLD], REVIEW_PENDING)
        return self

    def to_photo_record(self) -> PhotoRecord:
        photo_type = "Candidate Photo" if self.linked_candidate_id or self.source_type == SOURCE_LISTING_PHOTO else "Reference Photo"
        return PhotoRecord(
            file_path=self.file_path,
            photo_type=photo_type,
            linked_collection_item_id=self.linked_collection_item_id,
            linked_candidate_id=self.linked_candidate_id,
            linked_coin_name=self.linked_coin_name,
            notes="; ".join(_dedupe([self.photo_role, self.workflow_status, self.notes])),
        )

    def to_ocr_source(self) -> Dict[str, str]:
        return {
            "photo_id": self.photo_id,
            "image_path": self.file_path,
            "photo_role": self.photo_role,
            "source_type": self.source_type,
            "ready_for_ocr": "YES" if self.ready_for_ocr else "NO",
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "photo_id": self.photo_id,
            "file_path": self.file_path,
            "source_type": self.source_type,
            "photo_role": self.photo_role,
            "captured_at": self.captured_at,
            "workflow_status": self.workflow_status,
            "review_status": self.review_status,
            "notes": self.notes,
            "linked_candidate_id": self.linked_candidate_id,
            "linked_collection_item_id": self.linked_collection_item_id,
            "linked_coin_name": self.linked_coin_name,
            "ready_for_ocr": "YES" if self.ready_for_ocr else "NO",
            "ready_for_review": "YES" if self.ready_for_review else "NO",
        }


@dataclass
class PhotoCaptureSession:
    """Multi-photo field capture session."""

    session_id: str
    session_type: str = SESSION_COIN_FRONT_BACK
    subject: str = ""
    location: str = ""
    started_at: str = ""
    notes: str = ""
    photos: List[CapturedPhoto] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.session_id = _text(self.session_id) or f"capture-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.session_type = _normalize_choice(self.session_type, [SESSION_COIN_FRONT_BACK, SESSION_NOTE_FRONT_BACK, SESSION_LISTING_PHOTOS], SESSION_COIN_FRONT_BACK)
        self.subject = _text(self.subject)
        self.location = _text(self.location)
        self.started_at = _text(self.started_at) or _now_iso()
        self.notes = _text(self.notes)
        self.photos = [photo if isinstance(photo, CapturedPhoto) else CapturedPhoto(**photo) for photo in self.photos]
        self.refresh_statuses()

    def add_photo(
        self,
        file_path: str,
        photo_role: str,
        source_type: str = SOURCE_PHONE_CAMERA,
        notes: str = "",
        linked_candidate_id: str = "",
        linked_collection_item_id: str = "",
        linked_coin_name: str = "",
    ) -> CapturedPhoto:
        photo = CapturedPhoto(
            photo_id=f"{self.session_id}-{len(self.photos) + 1}",
            file_path=file_path,
            source_type=source_type,
            photo_role=photo_role,
            notes=notes,
            linked_candidate_id=linked_candidate_id,
            linked_collection_item_id=linked_collection_item_id,
            linked_coin_name=linked_coin_name or self.subject,
        )
        self.photos.append(photo)
        self.refresh_statuses()
        return photo

    @property
    def front_photos(self) -> List[CapturedPhoto]:
        return [photo for photo in self.photos if photo.is_front]

    @property
    def back_photos(self) -> List[CapturedPhoto]:
        return [photo for photo in self.photos if photo.is_back]

    @property
    def missing_front(self) -> bool:
        return self.session_type in {SESSION_COIN_FRONT_BACK, SESSION_NOTE_FRONT_BACK} and not self.front_photos

    @property
    def missing_back(self) -> bool:
        return self.session_type in {SESSION_COIN_FRONT_BACK, SESSION_NOTE_FRONT_BACK} and not self.back_photos

    @property
    def front_back_complete(self) -> bool:
        if self.session_type == SESSION_LISTING_PHOTOS:
            return bool(self.photos)
        return bool(self.front_photos and self.back_photos)

    @property
    def ready_for_ocr(self) -> bool:
        return self.front_back_complete and any(photo.ready_for_ocr for photo in self.photos)

    @property
    def ready_for_review(self) -> bool:
        return self.front_back_complete and any(photo.ready_for_review for photo in self.photos)

    def refresh_statuses(self) -> None:
        complete = self.front_back_complete
        for photo in self.photos:
            if complete:
                photo.workflow_status = STATUS_READY_FOR_REVIEW if photo.review_status == REVIEW_PENDING else STATUS_COMPLETE
            elif self.missing_front:
                photo.workflow_status = STATUS_NEEDS_FRONT
            elif self.missing_back:
                photo.workflow_status = STATUS_NEEDS_BACK
            else:
                photo.workflow_status = STATUS_CAPTURED

    def mark_ready_for_ocr(self) -> None:
        if self.front_back_complete:
            for photo in self.photos:
                photo.workflow_status = STATUS_READY_FOR_OCR

    def mark_reviewed(self) -> None:
        for photo in self.photos:
            photo.mark_status(STATUS_COMPLETE, REVIEW_REVIEWED)

    def to_photo_records(self) -> List[PhotoRecord]:
        return [photo.to_photo_record() for photo in self.photos]

    def to_ocr_sources(self) -> List[Dict[str, str]]:
        return [photo.to_ocr_source() for photo in self.photos if photo.ready_for_ocr]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "session_type": self.session_type,
            "subject": self.subject,
            "location": self.location,
            "started_at": self.started_at,
            "notes": self.notes,
            "photo_count": len(self.photos),
            "missing_front": "YES" if self.missing_front else "NO",
            "missing_back": "YES" if self.missing_back else "NO",
            "ready_for_ocr": "YES" if self.ready_for_ocr else "NO",
            "ready_for_review": "YES" if self.ready_for_review else "NO",
        }


@dataclass
class PhotoCaptureReport:
    sessions: List[PhotoCaptureSession] = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        self.generated_at = _text(self.generated_at) or _now_iso()
        self.sessions = [session if isinstance(session, PhotoCaptureSession) else PhotoCaptureSession(**session) for session in self.sessions]

    @property
    def total_sessions(self) -> int:
        return len(self.sessions)

    @property
    def total_photos(self) -> int:
        return sum(len(session.photos) for session in self.sessions)

    @property
    def missing_front_count(self) -> int:
        return sum(1 for session in self.sessions if session.missing_front)

    @property
    def missing_back_count(self) -> int:
        return sum(1 for session in self.sessions if session.missing_back)

    @property
    def ready_for_ocr_count(self) -> int:
        return sum(1 for session in self.sessions if session.ready_for_ocr)

    @property
    def ready_for_review_count(self) -> int:
        return sum(1 for session in self.sessions if session.ready_for_review)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "total_sessions": self.total_sessions,
            "total_photos": self.total_photos,
            "missing_front_count": self.missing_front_count,
            "missing_back_count": self.missing_back_count,
            "ready_for_ocr_count": self.ready_for_ocr_count,
            "ready_for_review_count": self.ready_for_review_count,
            "sessions": [session.to_dict() for session in self.sessions],
        }

    def format_markdown(self) -> str:
        lines = [
            "# Phone Photo Capture Report",
            "",
            f"- Generated: {self.generated_at}",
            f"- Capture sessions: {self.total_sessions}",
            f"- Photos collected: {self.total_photos}",
            f"- Missing front photos: {self.missing_front_count}",
            f"- Missing back photos: {self.missing_back_count}",
            f"- Ready for OCR: {self.ready_for_ocr_count}",
            f"- Ready for review: {self.ready_for_review_count}",
            "",
            "## Capture Sessions",
            "",
        ]
        if not self.sessions:
            lines.append("- No capture sessions available.")
        for session in self.sessions:
            lines.append(
                f"- {session.session_id}: {session.subject or session.session_type}; "
                f"{len(session.photos)} photo(s); OCR {self._yes_no(session.ready_for_ocr)}; "
                f"review {self._yes_no(session.ready_for_review)}"
            )
            if session.missing_front:
                lines.append("  - Missing front photo")
            if session.missing_back:
                lines.append("  - Missing back photo")
            for photo in session.photos:
                lines.append(f"  - {photo.photo_role}: {photo.file_path} ({photo.workflow_status}; {photo.review_status})")
        lines.extend([
            "",
            "## Boundaries",
            "",
            "- Metadata-only photo intake.",
            "- No image recognition, attribution, grading, OCR identification, cloud sync, or collection entry.",
        ])
        return "\n".join(lines).rstrip() + "\n"

    def export_markdown(self, output_path: str) -> bool:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self.format_markdown())
        return True

    def export_csv(self, output_path: str) -> bool:
        fieldnames = [
            "session_id",
            "session_type",
            "subject",
            "location",
            "started_at",
            "photo_id",
            "file_path",
            "source_type",
            "photo_role",
            "captured_at",
            "workflow_status",
            "review_status",
            "notes",
            "ready_for_ocr",
            "ready_for_review",
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for session in self.sessions:
                for photo in session.photos:
                    row = {
                        "session_id": session.session_id,
                        "session_type": session.session_type,
                        "subject": session.subject,
                        "location": session.location,
                        "started_at": session.started_at,
                    }
                    row.update(photo.to_dict())
                    writer.writerow({key: row.get(key, "") for key in fieldnames})
        return True

    @staticmethod
    def _yes_no(value: bool) -> str:
        return "YES" if value else "NO"


class PhotoCaptureWorkflow:
    """Create and summarize field photo capture sessions."""

    def __init__(self, sessions: Optional[Iterable[PhotoCaptureSession]] = None):
        self.sessions = [session if isinstance(session, PhotoCaptureSession) else PhotoCaptureSession(**session) for session in (sessions or [])]

    def start_session(
        self,
        session_type: str = SESSION_COIN_FRONT_BACK,
        subject: str = "",
        location: str = "",
        notes: str = "",
    ) -> PhotoCaptureSession:
        slug = _normalize_choice(session_type, [SESSION_COIN_FRONT_BACK, SESSION_NOTE_FRONT_BACK, SESSION_LISTING_PHOTOS], SESSION_COIN_FRONT_BACK)
        session_id = f"photo-capture-{slug.lower().replace('/', '-').replace(' ', '-')}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        session = PhotoCaptureSession(session_id=session_id, session_type=slug, subject=subject, location=location, notes=notes)
        self.sessions.append(session)
        return session

    def capture_photo(self, session: PhotoCaptureSession, file_path: str, photo_role: str, **kwargs: Any) -> CapturedPhoto:
        return session.add_photo(file_path=file_path, photo_role=photo_role, **kwargs)

    def capture_coin_pair(self, subject: str, front_path: str = "", back_path: str = "", location: str = "", notes: str = "") -> PhotoCaptureSession:
        session = self.start_session(SESSION_COIN_FRONT_BACK, subject=subject, location=location, notes=notes)
        if front_path:
            session.add_photo(front_path, ROLE_COIN_FRONT)
        if back_path:
            session.add_photo(back_path, ROLE_COIN_BACK)
        return session

    def capture_note_pair(self, subject: str, front_path: str = "", back_path: str = "", location: str = "", notes: str = "") -> PhotoCaptureSession:
        session = self.start_session(SESSION_NOTE_FRONT_BACK, subject=subject, location=location, notes=notes)
        if front_path:
            session.add_photo(front_path, ROLE_NOTE_FRONT)
        if back_path:
            session.add_photo(back_path, ROLE_NOTE_BACK)
        return session

    def capture_listing_photo(self, subject: str, file_path: str, candidate_id: str = "", notes: str = "") -> PhotoCaptureSession:
        session = self.start_session(SESSION_LISTING_PHOTOS, subject=subject, notes=notes)
        session.add_photo(file_path, ROLE_LISTING, source_type=SOURCE_LISTING_PHOTO, linked_candidate_id=candidate_id, linked_coin_name=subject)
        return session

    def report(self) -> PhotoCaptureReport:
        return PhotoCaptureReport(self.sessions)

    def photo_vault_records(self) -> List[PhotoRecord]:
        return [record for session in self.sessions for record in session.to_photo_records()]

    def ocr_sources(self) -> List[Dict[str, str]]:
        return [source for session in self.sessions for source in session.to_ocr_sources()]
