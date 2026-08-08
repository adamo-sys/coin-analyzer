"""Ephemeral adapter from desktop image selections to capture-package input.

The established OCR composition deliberately consumes validated capture
packages.  This adapter preserves that boundary: it validates two ordinary
front/reverse image files, writes one temporary format-1.0 package, and gives
the caller an idempotent release callback.  It performs no OCR, review,
collection mutation, or durable image storage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import zipfile

from ._filesystem import (
    handle_matches_path,
    require_plain_regular_file,
)
from .enums import Composition, ImageRole
from .limits import (
    MAX_IMAGE_SIZE,
    SUPPORTED_SCHEMA,
    SUPPORTED_SCHEMA_VERSION,
)
from .media import CapturePackageMediaValidator
from .models import PackageCoin, PackageImage, PackageManifest, PackageSession
from .package import CapturePackageValidator


_SUPPORTED_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})
_MIME_BY_FORMAT = {"JPEG": "image/jpeg", "PNG": "image/png"}
_PACKAGE_SUFFIX_BY_FORMAT = {"JPEG": ".jpg", "PNG": ".png"}


class StandaloneImageIntakeError(ValueError):
    """One selected image set cannot safely enter the OCR workflow."""

    safe_message = "The selected coin images could not be prepared."


class PartialStandaloneImageSelectionError(StandaloneImageIntakeError):
    safe_message = "Select both an obverse and a reverse coin image."


class MissingStandaloneImageError(StandaloneImageIntakeError):
    safe_message = "A selected coin image no longer exists."


class UnsupportedStandaloneImageError(StandaloneImageIntakeError):
    safe_message = "Choose JPG, JPEG, or PNG coin images."


class UnreadableStandaloneImageError(StandaloneImageIntakeError):
    safe_message = "A selected coin image could not be read."


class MalformedStandaloneImageError(StandaloneImageIntakeError):
    safe_message = "A selected file is not a valid JPG or PNG image."


@dataclass(slots=True)
class TemporaryCapturePackage:
    """One owned temporary package with idempotent best-effort cleanup."""

    path: Path
    _directory: TemporaryDirectory[str]
    _released: bool = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        try:
            self._directory.cleanup()
        except OSError:
            # A process-held Windows handle may delay removal.  The
            # TemporaryDirectory finalizer retains the same cleanup fallback.
            pass


@dataclass(frozen=True, slots=True)
class _InspectedImage:
    role: ImageRole
    payload: bytes
    image_format: str
    width: int
    height: int


def create_temporary_capture_package(
    *,
    front_path: str | Path,
    reverse_path: str | Path,
) -> TemporaryCapturePackage:
    """Create one validated ephemeral package for the existing OCR pipeline."""

    if not front_path or not reverse_path:
        raise PartialStandaloneImageSelectionError()
    media_validator = CapturePackageMediaValidator()
    images = tuple(
        _inspect_image(path, role=role, validator=media_validator)
        for path, role in (
            (front_path, ImageRole.FRONT),
            (reverse_path, ImageRole.REVERSE),
        )
    )

    directory = TemporaryDirectory(prefix="coin-analyzer-image-intake-")
    package_path = Path(directory.name) / "coin-images.ca-package"
    try:
        manifest, entries = _build_manifest_and_entries(images)
        manifest_payload = json.dumps(
            manifest.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        with zipfile.ZipFile(
            package_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            archive.writestr("capture_package.json", manifest_payload)
            archive.writestr("images/", b"")
            for relative_path, payload in entries:
                archive.writestr(relative_path, payload)
        package_payload = package_path.read_bytes()
        CapturePackageValidator().validate_stream(
            BytesIO(package_payload),
            package_path.name,
            package_sha256=sha256(package_payload).hexdigest(),
            package_byte_length=len(package_payload),
        )
    except StandaloneImageIntakeError:
        directory.cleanup()
        raise
    except Exception as error:
        directory.cleanup()
        raise StandaloneImageIntakeError() from error
    return TemporaryCapturePackage(path=package_path, _directory=directory)


def _inspect_image(
    path_value: str | Path,
    *,
    role: ImageRole,
    validator: CapturePackageMediaValidator,
) -> _InspectedImage:
    path = Path(path_value).absolute()
    if path.suffix.casefold() not in _SUPPORTED_SUFFIXES:
        raise UnsupportedStandaloneImageError()
    try:
        require_plain_regular_file(path)
    except FileNotFoundError as error:
        raise MissingStandaloneImageError() from error
    except OSError as error:
        raise UnreadableStandaloneImageError() from error

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            if not handle_matches_path(handle, path):
                raise OSError("selected image identity changed")
            payload = handle.read(MAX_IMAGE_SIZE + 1)
            if len(payload) > MAX_IMAGE_SIZE:
                raise UnreadableStandaloneImageError()
            if not handle_matches_path(handle, path):
                raise OSError("selected image identity changed while read")
    except StandaloneImageIntakeError:
        raise
    except FileNotFoundError as error:
        raise MissingStandaloneImageError() from error
    except OSError as error:
        raise UnreadableStandaloneImageError() from error

    try:
        image_format, width, height = validator.inspect_payload(payload)
    except Exception as error:
        raise MalformedStandaloneImageError() from error
    expected_format = "PNG" if path.suffix.casefold() == ".png" else "JPEG"
    if image_format != expected_format:
        raise MalformedStandaloneImageError()
    return _InspectedImage(role, payload, image_format, width, height)


def _build_manifest_and_entries(
    images: tuple[_InspectedImage, ...],
) -> tuple[PackageManifest, tuple[tuple[str, bytes], ...]]:
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat().replace("+00:00", "Z")
    session_id = f"desktop-image-{uuid4().hex}"
    package_images = []
    entries = []
    for image in images:
        suffix = _PACKAGE_SUFFIX_BY_FORMAT[image.image_format]
        relative_path = f"images/{image.role.value}{suffix}"
        package_images.append(
            PackageImage(
                role=image.role,
                path=relative_path,
                original_name=f"selected-{image.role.value}{suffix}",
                mime_type=_MIME_BY_FORMAT[image.image_format],
                byte_length=len(image.payload),
                width=image.width,
                height=image.height,
                captured_at=timestamp,
            )
        )
        entries.append((relative_path, image.payload))

    coin = PackageCoin(
        id="coin-1",
        position=0,
        country="Unknown",
        denomination="Unknown",
        year="Unknown",
        mint="",
        purchase_price=Decimal("0"),
        purchase_currency="CAD",
        seller="",
        purchase_date=None,
        notes="",
        quantity=1,
        composition=Composition.OTHER,
        is_bullion=False,
        asw_troy_ounces=None,
        photos=tuple(package_images),
        created_at=timestamp,
        updated_at=timestamp,
    )
    manifest = PackageManifest(
        schema=SUPPORTED_SCHEMA,
        package_version=SUPPORTED_SCHEMA_VERSION,
        created_by="Coin Analyzer Desktop Image Intake",
        created_with="standalone-image-intake-1",
        exported_at=timestamp,
        session=PackageSession(
            id=session_id,
            name="Desktop Coin Images",
            description="",
            session_date=now.date().isoformat(),
            created_at=timestamp,
            updated_at=timestamp,
        ),
        coins=(coin,),
    )
    manifest.validate()
    return manifest, tuple(entries)
