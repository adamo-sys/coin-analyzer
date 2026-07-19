"""Read-only orchestration for canonical capture-package validation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import BinaryIO

from .archive import CapturePackageArchiveReader, ValidatedArchiveIndex, MANIFEST_NAME
from .errors import PackageChanged, PackageTooLarge
from .manifest import CapturePackageManifestParser
from .media import CapturePackageMediaValidator, ValidatedMedia
from .models import PackageManifest
from .models import _validate_sha256
from .snapshot import SnapshotHandle
from .validation_limits import ValidationLimits


@dataclass(frozen=True, slots=True)
class ValidatedCapturePackage:
    """Canonical in-memory result of complete read-only validation."""

    package_basename: str
    package_sha256: str
    package_byte_length: int
    archive: ValidatedArchiveIndex
    manifest: PackageManifest
    media: tuple[ValidatedMedia, ...]


class CapturePackageValidator:
    """Validate an accepted snapshot without extracting or persisting content."""

    def __init__(self, limits: ValidationLimits | None = None) -> None:
        self.limits = limits or ValidationLimits()
        self.archive_reader = CapturePackageArchiveReader(self.limits)
        self.manifest_parser = CapturePackageManifestParser(self.limits)
        self.media_validator = CapturePackageMediaValidator(self.limits)

    def validate_snapshot(
        self, handle: SnapshotHandle, package_basename: str
    ) -> ValidatedCapturePackage:
        with handle.open_package() as package:
            return self.validate_stream(
                package,
                package_basename,
                package_sha256=handle.descriptor.sha256,
                package_byte_length=handle.descriptor.byte_length,
            )

    def validate_stream(
        self,
        package: BinaryIO,
        package_basename: str,
        *,
        package_sha256: str,
        package_byte_length: int,
    ) -> ValidatedCapturePackage:
        digest = sha256()
        actual_length = 0
        try:
            _validate_sha256(package_sha256, "package_sha256")
            if (
                isinstance(package_byte_length, bool)
                or not isinstance(package_byte_length, int)
                or package_byte_length < 1
            ):
                raise ValueError("package_byte_length must be a positive integer")
            package.seek(0)
            while True:
                chunk = package.read(
                    min(
                        1024 * 1024,
                        self.limits.package_size + 1 - actual_length,
                    )
                )
                if not chunk:
                    break
                actual_length += len(chunk)
                if actual_length > self.limits.package_size:
                    raise PackageTooLarge()
                digest.update(chunk)
            package.seek(0)
        except (PackageChanged, PackageTooLarge):
            raise
        except (OSError, ValueError) as error:
            raise PackageChanged(error) from error
        if package_byte_length != actual_length or package_sha256 != digest.hexdigest():
            raise PackageChanged()
        archive, index = self.archive_reader.validate(package, package_basename)
        try:
            manifest_entry = index.entry(MANIFEST_NAME)
            assert manifest_entry is not None
            manifest_bytes = self.archive_reader.read_entry(
                archive, manifest_entry, self.limits.manifest_bytes
            )
            manifest = self.manifest_parser.parse(manifest_bytes)
            media = self.media_validator.validate(
                archive, index, manifest, self.archive_reader
            )
            return ValidatedCapturePackage(
                package_basename=package_basename,
                package_sha256=package_sha256,
                package_byte_length=package_byte_length,
                archive=index,
                manifest=manifest,
                media=media,
            )
        finally:
            archive.close()
