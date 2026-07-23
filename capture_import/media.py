"""Exact-byte JPEG/PNG validation for referenced package media."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import PurePosixPath
import warnings
import zipfile

from PIL import Image

from .archive import MANIFEST_NAME, ArchiveEntry, CapturePackageArchiveReader, ValidatedArchiveIndex
from .enums import ImageRole
from .errors import InvalidMedia, MediaMissing, PackageTooLarge, UnreferencedArchiveEntry
from .image_validation import require_complete_jpeg
from .models import PackageManifest
from .validation_limits import ValidationLimits

_ROLE_ORDER = {ImageRole.FRONT: 0, ImageRole.REVERSE: 1, ImageRole.EDGE: 2}


@dataclass(frozen=True, slots=True)
class ValidatedMedia:
    """Canonical descriptor for exact accepted archive image bytes."""

    coin_id: str
    role: ImageRole
    archive_path: str
    mime_type: str
    byte_length: int
    width: int
    height: int
    sha256: str


class CapturePackageMediaValidator:
    """Validate every referenced image and reject every hidden payload."""

    def __init__(self, limits: ValidationLimits | None = None) -> None:
        self.limits = limits or ValidationLimits()

    def validate(
        self,
        archive: zipfile.ZipFile,
        index: ValidatedArchiveIndex,
        manifest: PackageManifest,
        reader: CapturePackageArchiveReader,
    ) -> tuple[ValidatedMedia, ...]:
        referenced: set[str] = set()
        validated: list[ValidatedMedia] = []
        for coin in sorted(manifest.coins, key=lambda item: item.position):
            for image in sorted(coin.photos, key=lambda item: _ROLE_ORDER[item.role]):
                if image.path in referenced:
                    raise InvalidMedia()
                referenced.add(image.path)
                entry = index.entry(image.path)
                if entry is None or entry.is_directory:
                    raise MediaMissing()
                if entry.uncompressed_size != image.byte_length:
                    raise InvalidMedia()
                if entry.uncompressed_size > self.limits.image_bytes:
                    raise PackageTooLarge()
                payload = reader.read_entry(archive, entry, self.limits.image_bytes)
                actual_format, width, height = self._validate_image(payload)
                expected_format = "JPEG" if image.mime_type == "image/jpeg" else "PNG"
                expected_suffix = ".jpg" if actual_format == "JPEG" else ".png"
                if actual_format != expected_format or PurePosixPath(image.path).suffix != expected_suffix:
                    raise InvalidMedia()
                if (width, height) != (image.width, image.height):
                    raise InvalidMedia()
                validated.append(
                    ValidatedMedia(
                        coin_id=coin.id,
                        role=image.role,
                        archive_path=image.path,
                        mime_type=image.mime_type,
                        byte_length=len(payload),
                        width=width,
                        height=height,
                        sha256=sha256(payload).hexdigest(),
                    )
                )
        expected_files = referenced | {MANIFEST_NAME}
        if {entry.name for entry in index.files} != expected_files:
            raise UnreferencedArchiveEntry()
        required_directories = {
            prefix + "/"
            for path in referenced
            for prefix in self._parent_prefixes(path)
        }
        for directory in index.directories:
            if directory.name not in required_directories:
                raise UnreferencedArchiveEntry()
        return tuple(validated)

    def verify_payload(self, payload: bytes, expected: ValidatedMedia) -> None:
        """Revalidate copied bytes against one immutable media descriptor."""

        if not isinstance(payload, bytes) or not isinstance(expected, ValidatedMedia):
            raise InvalidMedia()
        if len(payload) != expected.byte_length or sha256(payload).hexdigest() != expected.sha256:
            raise InvalidMedia()
        actual_format, width, height = self._validate_image(payload)
        expected_format = "JPEG" if expected.mime_type == "image/jpeg" else "PNG"
        if actual_format != expected_format or (width, height) != (
            expected.width,
            expected.height,
        ):
            raise InvalidMedia()

    def _validate_image(self, payload: bytes) -> tuple[str, int, int]:
        if payload.startswith(b"\x89PNG\r\n\x1a\n"):
            self._require_complete_png(payload)
        elif payload.startswith(b"\xff\xd8"):
            self._require_complete_jpeg(payload)
        else:
            raise InvalidMedia()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(payload)) as probe:
                    image_format = probe.format
                    width, height = probe.size
                    if getattr(probe, "n_frames", 1) != 1:
                        raise InvalidMedia()
                    self._validate_dimensions(width, height)
                    probe.verify()
                with Image.open(BytesIO(payload)) as decoded:
                    if getattr(decoded, "n_frames", 1) != 1:
                        raise InvalidMedia()
                    decoded.load()
                    if decoded.format != image_format or decoded.size != (width, height):
                        raise InvalidMedia()
        except InvalidMedia:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning, OSError, SyntaxError, ValueError) as error:
            raise InvalidMedia(error) from error
        if image_format not in {"JPEG", "PNG"}:
            raise InvalidMedia()
        return image_format, width, height

    def _validate_dimensions(self, width: int, height: int) -> None:
        if width < 1 or height < 1:
            raise InvalidMedia()
        if width > self.limits.image_dimension or height > self.limits.image_dimension:
            raise PackageTooLarge()
        if width * height > self.limits.image_pixels:
            raise PackageTooLarge()

    @staticmethod
    def _require_complete_png(payload: bytes) -> None:
        offset = 8
        found_end = False
        while offset + 12 <= len(payload):
            length = int.from_bytes(payload[offset : offset + 4], "big")
            chunk_type = payload[offset + 4 : offset + 8]
            offset += 12 + length
            if offset > len(payload):
                raise InvalidMedia()
            if chunk_type == b"IEND":
                if length != 0 or offset != len(payload):
                    raise InvalidMedia()
                found_end = True
                break
        if not found_end:
            raise InvalidMedia()

    @staticmethod
    def _require_complete_jpeg(payload: bytes) -> None:
        """Parse markers and entropy data, requiring the first JPEG to end at EOF."""

        try:
            require_complete_jpeg(payload)
        except ValueError as exc:
            raise InvalidMedia() from exc

    @staticmethod
    def _parent_prefixes(path: str) -> tuple[str, ...]:
        parts = PurePosixPath(path).parts
        return tuple("/".join(parts[:index]) for index in range(1, len(parts)))
