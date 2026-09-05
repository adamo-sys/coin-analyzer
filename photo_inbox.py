"""Backend Photo Inbox service for local-first incoming photo workflows.

The inbox references files in place. It never copies, moves, renames, archives,
or deletes collector photo files.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


DEFAULT_INBOX_FOLDER = os.path.join("coin_photos", "incoming")
DEFAULT_STATE_PATH = os.path.join("data", "photo_inbox_state.json")
DEFAULT_GROUPING_WINDOW_SECONDS = 90
DEFAULT_FILE_STABILITY_SECONDS = 2
DEFAULT_MAX_INBOX_ITEMS = 500
REFERENCE_IN_PLACE = "reference_in_place"
SUPPORTED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff")
PENDING_SET_STATES = {"NEW", "PROCESSING", "DEFERRED", "ERROR"}


class PhotoSetState(str, Enum):
    """Lifecycle state for a proposed group of inbox photos."""

    NEW = "NEW"
    PROCESSING = "PROCESSING"
    DEFERRED = "DEFERRED"
    ATTACHED = "ATTACHED"
    IMPORTED = "IMPORTED"
    IGNORED = "IGNORED"
    ERROR = "ERROR"

    @classmethod
    def normalize(cls, value: Any) -> "PhotoSetState":
        if isinstance(value, cls):
            return value
        text = str(value or "").strip().upper()
        try:
            return cls(text)
        except ValueError:
            return cls.ERROR


class InboxPhotoState(str, Enum):
    """Lifecycle state for an individual inbox photo reference."""

    NEW = "NEW"
    STABILIZING = "STABILIZING"
    READY = "READY"
    ASSIGNED = "ASSIGNED"
    IGNORED = "IGNORED"
    ERROR = "ERROR"
    MISSING = "MISSING"

    @classmethod
    def normalize(cls, value: Any) -> "InboxPhotoState":
        if isinstance(value, cls):
            return value
        text = str(value or "").strip().upper()
        try:
            return cls(text)
        except ValueError:
            return cls.ERROR


@dataclass
class PhotoInboxConfig:
    """Configuration for local Photo Inbox scans."""

    inbox_folder: str = DEFAULT_INBOX_FOLDER
    grouping_window_seconds: int = DEFAULT_GROUPING_WINDOW_SECONDS
    supported_extensions: Tuple[str, ...] = SUPPORTED_IMAGE_EXTENSIONS
    file_stability_seconds: int = DEFAULT_FILE_STABILITY_SECONDS
    max_inbox_items: int = DEFAULT_MAX_INBOX_ITEMS
    file_management_mode: str = REFERENCE_IN_PLACE
    state_path: str = DEFAULT_STATE_PATH

    def __post_init__(self) -> None:
        self.inbox_folder = str(self.inbox_folder or DEFAULT_INBOX_FOLDER)
        self.grouping_window_seconds = self._int_or_default(
            self.grouping_window_seconds,
            DEFAULT_GROUPING_WINDOW_SECONDS,
        )
        self.file_stability_seconds = self._int_or_default(
            self.file_stability_seconds,
            DEFAULT_FILE_STABILITY_SECONDS,
        )
        self.max_inbox_items = self._int_or_default(self.max_inbox_items, DEFAULT_MAX_INBOX_ITEMS)
        self.supported_extensions = tuple(
            sorted({self._normalize_extension(ext) for ext in self.supported_extensions or SUPPORTED_IMAGE_EXTENSIONS})
        )
        self.file_management_mode = REFERENCE_IN_PLACE
        self.state_path = str(self.state_path or DEFAULT_STATE_PATH)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inbox_folder": self.inbox_folder,
            "grouping_window_seconds": self.grouping_window_seconds,
            "supported_extensions": list(self.supported_extensions),
            "file_stability_seconds": self.file_stability_seconds,
            "max_inbox_items": self.max_inbox_items,
            "file_management_mode": self.file_management_mode,
            "state_path": self.state_path,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "PhotoInboxConfig":
        if not isinstance(data, dict):
            return cls()
        return cls(
            inbox_folder=data.get("inbox_folder", DEFAULT_INBOX_FOLDER),
            grouping_window_seconds=data.get("grouping_window_seconds", DEFAULT_GROUPING_WINDOW_SECONDS),
            supported_extensions=tuple(data.get("supported_extensions") or SUPPORTED_IMAGE_EXTENSIONS),
            file_stability_seconds=data.get("file_stability_seconds", DEFAULT_FILE_STABILITY_SECONDS),
            max_inbox_items=data.get("max_inbox_items", DEFAULT_MAX_INBOX_ITEMS),
            file_management_mode=data.get("file_management_mode", REFERENCE_IN_PLACE),
            state_path=data.get("state_path", DEFAULT_STATE_PATH),
        )

    @staticmethod
    def _normalize_extension(value: Any) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""
        return text if text.startswith(".") else f".{text}"

    @staticmethod
    def _int_or_default(value: Any, default: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return max(0, parsed)


@dataclass
class InboxPhoto:
    """Metadata for a photo discovered in the configured inbox folder."""

    id: str
    path: str
    fingerprint: str
    filename: str
    created_at: str
    modified_at: str
    first_seen_at: str
    last_seen_at: str
    size_bytes: int
    state: InboxPhotoState = InboxPhotoState.NEW
    error: str = ""
    photo_set_id: str = ""

    def __post_init__(self) -> None:
        self.id = str(self.id or "").strip()
        self.path = str(self.path or "").strip()
        self.fingerprint = str(self.fingerprint or "").strip()
        self.filename = str(self.filename or os.path.basename(self.path))
        self.created_at = str(self.created_at or "")
        self.modified_at = str(self.modified_at or "")
        self.first_seen_at = str(self.first_seen_at or "")
        self.last_seen_at = str(self.last_seen_at or self.first_seen_at)
        try:
            self.size_bytes = int(self.size_bytes)
        except (TypeError, ValueError):
            self.size_bytes = 0
        self.state = InboxPhotoState.normalize(self.state)
        self.error = str(self.error or "")
        self.photo_set_id = str(self.photo_set_id or "")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "fingerprint": self.fingerprint,
            "filename": self.filename,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "size_bytes": self.size_bytes,
            "state": self.state.value,
            "error": self.error,
            "photo_set_id": self.photo_set_id,
        }

    @classmethod
    def from_dict(cls, data: Any) -> Optional["InboxPhoto"]:
        if not isinstance(data, dict):
            return None
        photo_id = str(data.get("id") or "").strip()
        path = str(data.get("path") or "").strip()
        if not photo_id or not path:
            return None
        return cls(
            id=photo_id,
            path=path,
            fingerprint=data.get("fingerprint", ""),
            filename=data.get("filename") or os.path.basename(path),
            created_at=data.get("created_at", ""),
            modified_at=data.get("modified_at", ""),
            first_seen_at=data.get("first_seen_at", ""),
            last_seen_at=data.get("last_seen_at", ""),
            size_bytes=data.get("size_bytes", 0),
            state=data.get("state", InboxPhotoState.ERROR),
            error=data.get("error", ""),
            photo_set_id=data.get("photo_set_id", ""),
        )


@dataclass
class PhotoSet:
    """A deterministic proposed group of related inbox photos."""

    id: str
    photo_ids: List[str]
    state: PhotoSetState = PhotoSetState.NEW
    created_at: str = ""
    updated_at: str = ""
    suggested_label: str = ""
    notes: str = ""
    error: str = ""
    linked_item_id: str = ""

    def __post_init__(self) -> None:
        self.id = str(self.id or "").strip()
        self.photo_ids = [str(photo_id).strip() for photo_id in self.photo_ids or [] if str(photo_id).strip()]
        self.state = PhotoSetState.normalize(self.state)
        self.created_at = str(self.created_at or "")
        self.updated_at = str(self.updated_at or self.created_at)
        self.suggested_label = str(self.suggested_label or "")
        self.notes = str(self.notes or "")
        self.error = str(self.error or "")
        self.linked_item_id = str(self.linked_item_id or "")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "photo_ids": list(self.photo_ids),
            "state": self.state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "suggested_label": self.suggested_label,
            "notes": self.notes,
            "error": self.error,
            "linked_item_id": self.linked_item_id,
        }

    @classmethod
    def from_dict(cls, data: Any) -> Optional["PhotoSet"]:
        if not isinstance(data, dict):
            return None
        set_id = str(data.get("id") or "").strip()
        if not set_id:
            return None
        return cls(
            id=set_id,
            photo_ids=list(data.get("photo_ids") or []),
            state=data.get("state", PhotoSetState.ERROR),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            suggested_label=data.get("suggested_label", ""),
            notes=data.get("notes", ""),
            error=data.get("error", ""),
            linked_item_id=data.get("linked_item_id", ""),
        )


@dataclass
class PhotoInboxState:
    """Durable Photo Inbox state."""

    version: str = "1.0"
    photos: Dict[str, InboxPhoto] = field(default_factory=dict)
    photo_sets: Dict[str, PhotoSet] = field(default_factory=dict)
    seen_fingerprints: Dict[str, str] = field(default_factory=dict)
    last_scan_at: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "photos": [photo.to_dict() for photo in sorted(self.photos.values(), key=lambda item: item.path.lower())],
            "photo_sets": [photo_set.to_dict() for photo_set in sorted(self.photo_sets.values(), key=lambda item: item.id)],
            "seen_fingerprints": dict(sorted(self.seen_fingerprints.items())),
            "last_scan_at": self.last_scan_at,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "PhotoInboxState":
        if not isinstance(data, dict):
            return cls(errors=["Malformed photo inbox state ignored."])
        photos = {}
        for row in data.get("photos", []) or []:
            photo = InboxPhoto.from_dict(row)
            if photo:
                photos[photo.id] = photo
        photo_sets = {}
        for row in data.get("photo_sets", []) or []:
            photo_set = PhotoSet.from_dict(row)
            if photo_set:
                photo_sets[photo_set.id] = photo_set
        return cls(
            version=str(data.get("version") or "1.0"),
            photos=photos,
            photo_sets=photo_sets,
            seen_fingerprints={
                str(key): str(value)
                for key, value in (data.get("seen_fingerprints") or {}).items()
                if str(key) and str(value)
            },
            last_scan_at=str(data.get("last_scan_at") or ""),
            warnings=[str(item) for item in data.get("warnings", []) or []],
            errors=[str(item) for item in data.get("errors", []) or []],
        )


@dataclass
class PhotoInboxScanResult:
    """Summary returned by PhotoInboxManager.scan()."""

    scanned_folder: str
    discovered: int = 0
    ready: int = 0
    stabilizing: int = 0
    unsupported: int = 0
    duplicates: int = 0
    missing: int = 0
    photo_sets: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


class PhotoInboxManager:
    """Scan and group incoming photos for future GUI workflows."""

    def __init__(
        self,
        config: Optional[PhotoInboxConfig] = None,
        inbox_folder: Optional[str] = None,
        state_path: Optional[str] = None,
        now_fn: Optional[Callable[[], datetime]] = None,
    ):
        self.config = config or PhotoInboxConfig()
        if inbox_folder is not None:
            self.config.inbox_folder = str(inbox_folder)
        if state_path is not None:
            self.config.state_path = str(state_path)
        self.now_fn = now_fn or datetime.now
        self.state = self.load_state()

    def refresh(self) -> PhotoInboxScanResult:
        """Alias for scan; intended for future GUI wording."""
        return self.scan()

    def scan(self) -> PhotoInboxScanResult:
        """Scan the configured inbox folder without moving or modifying files."""
        now = self.now_fn().replace(microsecond=0)
        now_text = self._dt_to_text(now)
        result = PhotoInboxScanResult(scanned_folder=self.config.inbox_folder)
        self.state.warnings = []
        self.state.errors = []

        if not os.path.isdir(self.config.inbox_folder):
            warning = f"Inbox folder not found: {self.config.inbox_folder}"
            self.state.warnings.append(warning)
            result.warnings.append(warning)
            self.state.last_scan_at = now_text
            self.save_state()
            return result

        current_photo_ids = set()
        for entry in self._iter_inbox_files():
            if not entry.is_file():
                continue
            path = os.path.abspath(entry.path)
            if not self._is_supported(path):
                result.unsupported += 1
                continue
            try:
                stat = entry.stat()
            except OSError as exc:
                result.errors.append(f"Could not inspect {path}: {exc}")
                continue
            photo_id = self.photo_id_for_path(path)
            current_photo_ids.add(photo_id)
            previous = self.state.photos.get(photo_id)
            fingerprint = self.fingerprint_for_stat(path, stat)
            if previous and self._is_terminal_photo(previous):
                previous.last_seen_at = now_text
                continue
            if previous:
                self._update_existing_photo(previous, stat, fingerprint, now)
            else:
                previous = self._new_photo(photo_id, path, stat, fingerprint, now)
                self.state.photos[photo_id] = previous
                result.discovered += 1
            if previous.state == InboxPhotoState.READY:
                result.ready += 1
            elif previous.state == InboxPhotoState.STABILIZING:
                result.stabilizing += 1
            if fingerprint in self.state.seen_fingerprints and self.state.seen_fingerprints[fingerprint] != photo_id:
                previous.error = "Duplicate photo fingerprint already seen."
                result.duplicates += 1
            else:
                self.state.seen_fingerprints[fingerprint] = photo_id

        result.missing = self._mark_missing(current_photo_ids, now_text)
        self._build_photo_sets(now_text)
        result.photo_sets = len(self.state.photo_sets)
        self.state.last_scan_at = now_text
        self.save_state()
        return result

    def get_pending_sets(self) -> List[PhotoSet]:
        """Return non-terminal Photo Sets for future GUI review."""
        return [
            photo_set
            for photo_set in sorted(self.state.photo_sets.values(), key=lambda item: (item.created_at, item.id))
            if photo_set.state.value in PENDING_SET_STATES
        ]

    def get_photo_set_photos(self, photo_set_id: str) -> List[InboxPhoto]:
        """Return photos for a Photo Set in deterministic display order."""
        photo_set = self.state.photo_sets.get(str(photo_set_id))
        if not photo_set:
            return []
        return [self.state.photos[photo_id] for photo_id in photo_set.photo_ids if photo_id in self.state.photos]

    def mark_processing(self, photo_set_id: str) -> bool:
        return self._mark_set_state(photo_set_id, PhotoSetState.PROCESSING)

    def mark_attached(self, photo_set_id: str, item_id: str = "") -> bool:
        return self._mark_set_state(photo_set_id, PhotoSetState.ATTACHED, linked_item_id=item_id)

    def mark_imported(self, photo_set_id: str, item_id: str = "") -> bool:
        return self._mark_set_state(photo_set_id, PhotoSetState.IMPORTED, linked_item_id=item_id)

    def mark_ignored(self, photo_set_id: str) -> bool:
        return self._mark_set_state(photo_set_id, PhotoSetState.IGNORED)

    def mark_deferred(self, photo_set_id: str) -> bool:
        return self._mark_set_state(photo_set_id, PhotoSetState.DEFERRED)

    def load_state(self) -> PhotoInboxState:
        """Load durable inbox state, tolerating missing or malformed metadata."""
        if not os.path.exists(self.config.state_path):
            return PhotoInboxState()
        try:
            with open(self.config.state_path, "r", encoding="utf-8") as handle:
                return PhotoInboxState.from_dict(json.load(handle))
        except (OSError, json.JSONDecodeError) as exc:
            return PhotoInboxState(errors=[f"Could not load photo inbox state: {exc}"])

    def save_state(self) -> None:
        """Persist inbox state only; never write photo files."""
        state_dir = os.path.dirname(self.config.state_path)
        if state_dir:
            os.makedirs(state_dir, exist_ok=True)
        with open(self.config.state_path, "w", encoding="utf-8") as handle:
            json.dump(self.state.to_dict(), handle, indent=2, ensure_ascii=False)

    def _iter_inbox_files(self) -> List[os.DirEntry]:
        try:
            return sorted(os.scandir(self.config.inbox_folder), key=lambda entry: entry.name.lower())
        except OSError as exc:
            self.state.errors.append(f"Could not scan inbox folder: {exc}")
            return []

    def _is_supported(self, path: str) -> bool:
        return os.path.splitext(path)[1].lower() in self.config.supported_extensions

    def _new_photo(self, photo_id: str, path: str, stat: os.stat_result, fingerprint: str, now: datetime) -> InboxPhoto:
        state = self._state_for_file(stat, now, first_seen=now)
        return InboxPhoto(
            id=photo_id,
            path=path,
            fingerprint=fingerprint,
            filename=os.path.basename(path),
            created_at=self._timestamp_to_text(stat.st_ctime),
            modified_at=self._timestamp_to_text(stat.st_mtime),
            first_seen_at=self._dt_to_text(now),
            last_seen_at=self._dt_to_text(now),
            size_bytes=stat.st_size,
            state=state,
        )

    def _update_existing_photo(
        self,
        photo: InboxPhoto,
        stat: os.stat_result,
        fingerprint: str,
        now: datetime,
    ) -> None:
        previous_fingerprint = photo.fingerprint
        first_seen = self._text_to_dt(photo.first_seen_at) or now
        photo.fingerprint = fingerprint
        photo.modified_at = self._timestamp_to_text(stat.st_mtime)
        photo.last_seen_at = self._dt_to_text(now)
        photo.size_bytes = stat.st_size
        photo.error = ""
        if previous_fingerprint != fingerprint:
            photo.first_seen_at = self._dt_to_text(now)
            first_seen = now
            if photo.photo_set_id and photo.photo_set_id in self.state.photo_sets:
                del self.state.photo_sets[photo.photo_set_id]
            photo.photo_set_id = ""
        if photo.state not in (InboxPhotoState.ASSIGNED, InboxPhotoState.IGNORED):
            photo.state = self._state_for_file(stat, now, first_seen)

    def _state_for_file(self, stat: os.stat_result, now: datetime, first_seen: datetime) -> InboxPhotoState:
        age_seconds = (now - first_seen).total_seconds()
        modified_age_seconds = now.timestamp() - stat.st_mtime
        if age_seconds < self.config.file_stability_seconds:
            return InboxPhotoState.STABILIZING
        if modified_age_seconds < self.config.file_stability_seconds:
            return InboxPhotoState.STABILIZING
        return InboxPhotoState.READY

    def _mark_missing(self, current_photo_ids: Iterable[str], now_text: str) -> int:
        current = set(current_photo_ids)
        missing = 0
        for photo in self.state.photos.values():
            if photo.id in current or self._is_terminal_photo(photo):
                continue
            if not os.path.exists(photo.path):
                photo.state = InboxPhotoState.MISSING
                photo.error = "Photo file is missing from the inbox folder."
                photo.last_seen_at = now_text
                missing += 1
                if photo.photo_set_id in self.state.photo_sets:
                    self.state.photo_sets[photo.photo_set_id].state = PhotoSetState.ERROR
                    self.state.photo_sets[photo.photo_set_id].error = photo.error
        return missing

    def _build_photo_sets(self, now_text: str) -> None:
        ready_photos = [
            photo
            for photo in self.state.photos.values()
            if photo.state == InboxPhotoState.READY and not photo.photo_set_id
        ]
        if not ready_photos:
            return
        ready_photos = self._merge_ready_photos_into_pending_sets(ready_photos, now_text)
        if not ready_photos:
            return
        groups = self._group_ready_photos(ready_photos)
        for group in groups:
            photo_ids = [photo.id for photo in group]
            set_id = self.photo_set_id_for_photo_ids(photo_ids)
            if set_id in self.state.photo_sets:
                photo_set = self.state.photo_sets[set_id]
                photo_set.updated_at = now_text
            else:
                photo_set = PhotoSet(
                    id=set_id,
                    photo_ids=photo_ids,
                    state=PhotoSetState.NEW,
                    created_at=now_text,
                    updated_at=now_text,
                    suggested_label=self._suggested_label(group),
                )
                self.state.photo_sets[set_id] = photo_set
            for photo in group:
                photo.photo_set_id = set_id
                photo.state = InboxPhotoState.ASSIGNED

    def _merge_ready_photos_into_pending_sets(self, ready_photos: List[InboxPhoto], now_text: str) -> List[InboxPhoto]:
        remaining = []
        for photo in sorted(ready_photos, key=lambda item: (item.first_seen_at, item.filename.lower(), item.id)):
            target_set = self._matching_pending_set(photo)
            if not target_set:
                remaining.append(photo)
                continue
            existing_photos = self.get_photo_set_photos(target_set.id)
            combined = existing_photos + [photo]
            old_id = target_set.id
            new_id = self.photo_set_id_for_photo_ids([item.id for item in combined])
            if new_id != old_id:
                del self.state.photo_sets[old_id]
            target_set.id = new_id
            target_set.photo_ids = [item.id for item in sorted(combined, key=lambda item: (item.first_seen_at, item.filename.lower(), item.id))]
            target_set.updated_at = now_text
            target_set.suggested_label = self._suggested_label(self.get_photo_set_photos(new_id) or combined)
            self.state.photo_sets[new_id] = target_set
            for item in combined:
                item.photo_set_id = new_id
                item.state = InboxPhotoState.ASSIGNED
        return remaining

    def _matching_pending_set(self, photo: InboxPhoto) -> Optional[PhotoSet]:
        for photo_set in sorted(self.get_pending_sets(), key=lambda item: (item.created_at, item.id)):
            existing_photos = self.get_photo_set_photos(photo_set.id)
            if existing_photos and self._belongs_with_group(photo, existing_photos):
                return photo_set
        return None

    def _group_ready_photos(self, photos: List[InboxPhoto]) -> List[List[InboxPhoto]]:
        ordered = sorted(photos, key=lambda photo: (photo.first_seen_at, photo.filename.lower(), photo.id))
        groups: List[List[InboxPhoto]] = []
        current: List[InboxPhoto] = []
        for photo in ordered:
            if not current:
                current = [photo]
                continue
            if self._belongs_with_group(photo, current):
                current.append(photo)
            else:
                groups.append(current)
                current = [photo]
        if current:
            groups.append(current)
        return groups

    def _belongs_with_group(self, photo: InboxPhoto, group: List[InboxPhoto]) -> bool:
        first = group[0]
        first_seen = self._text_to_dt(first.first_seen_at)
        photo_seen = self._text_to_dt(photo.first_seen_at)
        if first_seen and photo_seen:
            delta = abs((photo_seen - first_seen).total_seconds())
            if delta <= self.config.grouping_window_seconds:
                return True
        first_prefix = self._filename_prefix(first.filename)
        return bool(first_prefix and first_prefix == self._filename_prefix(photo.filename))

    @staticmethod
    def _filename_prefix(filename: str) -> str:
        stem = os.path.splitext(os.path.basename(filename))[0].lower()
        removed_role_suffix = False
        for suffix in (
            "_front",
            "-front",
            " front",
            "_back",
            "-back",
            " back",
            "_obverse",
            "-obverse",
            " obverse",
            "_reverse",
            "-reverse",
            " reverse",
        ):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                removed_role_suffix = True
                break
        if removed_role_suffix:
            return stem.strip("_- ") if len(stem.strip("_- ")) >= 3 else ""
        while stem and (stem[-1].isdigit() or stem[-1] in ("_", "-", " ")):
            stem = stem[:-1]
        return stem if len(stem) >= 3 else ""

    @staticmethod
    def _suggested_label(photos: List[InboxPhoto]) -> str:
        names = [os.path.splitext(photo.filename)[0] for photo in photos]
        if len(names) == 1:
            return names[0]
        return f"{names[0]} / {names[-1]}"

    def _mark_set_state(
        self,
        photo_set_id: str,
        state: PhotoSetState,
        linked_item_id: str = "",
    ) -> bool:
        photo_set = self.state.photo_sets.get(str(photo_set_id))
        if not photo_set:
            return False
        photo_set.state = state
        photo_set.updated_at = self._dt_to_text(self.now_fn().replace(microsecond=0))
        if linked_item_id:
            photo_set.linked_item_id = str(linked_item_id)
        if state == PhotoSetState.IGNORED:
            for photo in self.get_photo_set_photos(photo_set_id):
                photo.state = InboxPhotoState.IGNORED
        elif state in (PhotoSetState.ATTACHED, PhotoSetState.IMPORTED):
            for photo in self.get_photo_set_photos(photo_set_id):
                photo.state = InboxPhotoState.ASSIGNED
        self.save_state()
        return True

    @staticmethod
    def _is_terminal_photo(photo: InboxPhoto) -> bool:
        return photo.state in (InboxPhotoState.IGNORED,)

    @staticmethod
    def photo_id_for_path(path: str) -> str:
        normalized = os.path.normcase(os.path.abspath(path))
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def fingerprint_for_stat(path: str, stat: os.stat_result) -> str:
        normalized = os.path.normcase(os.path.abspath(path))
        raw = f"{normalized}|{stat.st_size}|{getattr(stat, 'st_mtime_ns', int(stat.st_mtime * 1_000_000_000))}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def photo_set_id_for_photo_ids(photo_ids: Iterable[str]) -> str:
        raw = "|".join(sorted(str(photo_id) for photo_id in photo_ids if str(photo_id)))
        return f"set_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"

    @staticmethod
    def _dt_to_text(value: datetime) -> str:
        return value.replace(microsecond=0).isoformat(sep=" ")

    @staticmethod
    def _timestamp_to_text(value: float) -> str:
        return datetime.fromtimestamp(value).replace(microsecond=0).isoformat(sep=" ")

    @staticmethod
    def _text_to_dt(value: str) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
