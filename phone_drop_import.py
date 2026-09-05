"""Copy phone-transferred images into Coin Analyzer-owned Photo Inbox storage.

Phone Drop Import deliberately creates durable app-owned copies while leaving
source files untouched. Photo Inbox remains reference-in-place and discovers
only the copied files afterward.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Tuple

from photo_inbox import DEFAULT_INBOX_FOLDER, SUPPORTED_IMAGE_EXTENSIONS


UNSUPPORTED_PHONE_EXTENSIONS = (".heic", ".heif")


@dataclass(frozen=True)
class PhoneDropImportedFile:
    source_path: str
    destination_path: str
    sha256: str
    duplicate: bool = False


@dataclass(frozen=True)
class PhoneDropRejectedFile:
    source_path: str
    reason: str


@dataclass
class PhoneDropImportResult:
    destination_folder: str
    imported: List[PhoneDropImportedFile] = field(default_factory=list)
    duplicates: List[PhoneDropImportedFile] = field(default_factory=list)
    rejected: List[PhoneDropRejectedFile] = field(default_factory=list)

    @property
    def copied_count(self) -> int:
        return len(self.imported)

    @property
    def duplicate_count(self) -> int:
        return len(self.duplicates)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)

    @property
    def imported_paths(self) -> Tuple[str, ...]:
        return tuple(item.destination_path for item in self.imported)


class PhoneDropImporter:
    """Bounded local importer for phone-transferred image files."""

    def __init__(
        self,
        destination_folder: str = DEFAULT_INBOX_FOLDER,
        supported_extensions: Iterable[str] = SUPPORTED_IMAGE_EXTENSIONS,
    ) -> None:
        self.destination_folder = os.path.abspath(str(destination_folder))
        self.supported_extensions = tuple(
            sorted({self._normalize_extension(ext) for ext in supported_extensions})
        )

    def import_files(self, source_paths: Iterable[str]) -> PhoneDropImportResult:
        """Copy supported source files without moving or modifying originals."""

        os.makedirs(self.destination_folder, exist_ok=True)
        result = PhoneDropImportResult(destination_folder=self.destination_folder)

        for raw_source in source_paths:
            source = os.path.abspath(str(raw_source))
            rejection = self._validate_source(source)
            if rejection:
                result.rejected.append(PhoneDropRejectedFile(source, rejection))
                continue

            digest = self._sha256_file(source)
            destination = self._destination_for(source, digest)

            if os.path.exists(destination):
                if self._sha256_file(destination) == digest:
                    result.duplicates.append(
                        PhoneDropImportedFile(source, destination, digest, duplicate=True)
                    )
                    continue
                destination = self._collision_destination(source, digest)

            shutil.copy2(source, destination)
            result.imported.append(PhoneDropImportedFile(source, destination, digest))

        return result

    def _validate_source(self, source: str) -> str:
        if not os.path.exists(source):
            return "Source image does not exist."
        if not os.path.isfile(source):
            return "Source path is not a file."

        extension = Path(source).suffix.lower()
        if extension in UNSUPPORTED_PHONE_EXTENSIONS:
            return (
                f"Unsupported phone image format {extension}. "
                "Phone Drop Import v1 supports JPEG, PNG, WebP, BMP, and TIFF images; "
                "export or share this image in one of those formats first."
            )
        if extension not in self.supported_extensions:
            supported = ", ".join(self.supported_extensions)
            return f"Unsupported image extension {extension or '(none)'}. Supported: {supported}."
        return ""

    def _destination_for(self, source: str, digest: str) -> str:
        source_path = Path(source)
        safe_stem = self._safe_stem(source_path.stem)
        extension = source_path.suffix.lower()
        filename = f"{safe_stem}--{digest[:16]}{extension}"
        return os.path.join(self.destination_folder, filename)

    def _collision_destination(self, source: str, digest: str) -> str:
        """Return a non-overwriting deterministic fallback for a rare name collision."""

        source_path = Path(source)
        safe_stem = self._safe_stem(source_path.stem)
        extension = source_path.suffix.lower()
        for digest_length in range(20, 65, 4):
            candidate = os.path.join(
                self.destination_folder,
                f"{safe_stem}--{digest[:digest_length]}{extension}",
            )
            if not os.path.exists(candidate):
                return candidate
            if self._sha256_file(candidate) == digest:
                return candidate

        counter = 2
        while True:
            candidate = os.path.join(
                self.destination_folder,
                f"{safe_stem}--{digest}-{counter}{extension}",
            )
            if not os.path.exists(candidate):
                return candidate
            if self._sha256_file(candidate) == digest:
                return candidate
            counter += 1

    @staticmethod
    def _safe_stem(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip()).strip("-._")
        return cleaned or "phone-photo"

    @staticmethod
    def _sha256_file(path: str) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _normalize_extension(value: str) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""
        return text if text.startswith(".") else f".{text}"
