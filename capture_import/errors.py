"""Typed exceptions for capture-package import failures."""

from __future__ import annotations

from .enums import ErrorCategory

_PUBLIC_MESSAGES = {
    ErrorCategory.PACKAGE_NOT_FOUND: "The capture package could not be found.",
    ErrorCategory.PACKAGE_NOT_ZIP: "The selected file is not a valid capture package.",
    ErrorCategory.PACKAGE_CHANGED: "The capture package changed during review.",
    ErrorCategory.PACKAGE_LIMIT_EXCEEDED: "The capture package exceeds a supported limit.",
    ErrorCategory.ARCHIVE_ENTRY_UNSAFE: "The capture package contains an unsafe entry.",
    ErrorCategory.ARCHIVE_NAME_COLLISION: "The capture package contains conflicting entry names.",
    ErrorCategory.ARCHIVE_ENTRY_UNREFERENCED: "The capture package contains an unexpected entry.",
    ErrorCategory.MANIFEST_MISSING: "The capture package manifest is missing.",
    ErrorCategory.MANIFEST_INVALID: "The capture package manifest is invalid.",
    ErrorCategory.EMPTY_PACKAGE: "The capture package contains no coins.",
    ErrorCategory.UNSUPPORTED_PACKAGE_VERSION: "The capture package version is not supported.",
    ErrorCategory.MEDIA_MISSING: "A required capture image is missing.",
    ErrorCategory.MEDIA_INVALID: "A capture image is invalid.",
    ErrorCategory.PREVIEW_STALE: "The import preview is no longer current.",
    ErrorCategory.DUPLICATE_PACKAGE: "This capture package was imported previously.",
    ErrorCategory.COLLECTION_CHANGED: "The collection changed after preview.",
    ErrorCategory.IMPORT_LOCKED: "Another collection update is in progress.",
    ErrorCategory.MANAGED_PATH_COLLISION: "A managed image destination already exists.",
    ErrorCategory.SNAPSHOT_FAILED: "The protected package snapshot could not be prepared.",
    ErrorCategory.SNAPSHOT_RECOVERY_REQUIRED: "Package snapshot recovery is required.",
    ErrorCategory.COPYING_IMAGES_FAILED: "Capture images could not be prepared.",
    ErrorCategory.COLLECTION_COMMIT_FAILED: "The collection update could not be completed.",
    ErrorCategory.AUDIT_FINALIZATION_PENDING: "Import audit finalization is pending.",
    ErrorCategory.JOURNAL_CORRUPT: "The import journal is invalid.",
    ErrorCategory.RECOVERY_REQUIRED: "Import recovery is required.",
    ErrorCategory.ROLLBACK_FAILED: "The import could not be rolled back safely.",
}


class CaptureImportError(Exception):
    """Base exception carrying a stable, sanitized error category."""

    category = ErrorCategory.MANIFEST_INVALID

    def __init__(self, diagnostic_context: object | None = None) -> None:
        self.safe_message = _PUBLIC_MESSAGES.get(
            self.category, "The capture-package import could not be completed."
        )
        self._diagnostic_context = diagnostic_context
        super().__init__(self.safe_message)


class PackageNotFound(CaptureImportError):
    category = ErrorCategory.PACKAGE_NOT_FOUND


class PackageNotZip(CaptureImportError):
    category = ErrorCategory.PACKAGE_NOT_ZIP


class PackageChanged(CaptureImportError):
    category = ErrorCategory.PACKAGE_CHANGED


class PackageTooLarge(CaptureImportError):
    category = ErrorCategory.PACKAGE_LIMIT_EXCEEDED


class UnsafeArchiveEntry(CaptureImportError):
    category = ErrorCategory.ARCHIVE_ENTRY_UNSAFE


class ArchiveNameCollision(CaptureImportError):
    category = ErrorCategory.ARCHIVE_NAME_COLLISION


class UnreferencedArchiveEntry(CaptureImportError):
    category = ErrorCategory.ARCHIVE_ENTRY_UNREFERENCED


class ManifestMissing(CaptureImportError):
    category = ErrorCategory.MANIFEST_MISSING


class InvalidManifest(CaptureImportError):
    category = ErrorCategory.MANIFEST_INVALID


class EmptyPackage(CaptureImportError):
    category = ErrorCategory.EMPTY_PACKAGE


class UnsupportedVersion(CaptureImportError):
    category = ErrorCategory.UNSUPPORTED_PACKAGE_VERSION


class MediaMissing(CaptureImportError):
    category = ErrorCategory.MEDIA_MISSING


class InvalidMedia(CaptureImportError):
    category = ErrorCategory.MEDIA_INVALID


class PreviewStale(CaptureImportError):
    category = ErrorCategory.PREVIEW_STALE


class DuplicatePackage(CaptureImportError):
    category = ErrorCategory.DUPLICATE_PACKAGE


class CollectionChanged(CaptureImportError):
    category = ErrorCategory.COLLECTION_CHANGED


class ImportLocked(CaptureImportError):
    category = ErrorCategory.IMPORT_LOCKED


class ImageCollision(CaptureImportError):
    category = ErrorCategory.MANAGED_PATH_COLLISION


class SnapshotFailed(CaptureImportError):
    category = ErrorCategory.SNAPSHOT_FAILED


class SnapshotRecoveryRequired(CaptureImportError):
    category = ErrorCategory.SNAPSHOT_RECOVERY_REQUIRED


class ImageCopyFailed(CaptureImportError):
    category = ErrorCategory.COPYING_IMAGES_FAILED


class CollectionCommitFailed(CaptureImportError):
    category = ErrorCategory.COLLECTION_COMMIT_FAILED


class AuditFinalizationPending(CaptureImportError):
    category = ErrorCategory.AUDIT_FINALIZATION_PENDING


class JournalCorrupt(CaptureImportError):
    category = ErrorCategory.JOURNAL_CORRUPT


class RecoveryRequired(CaptureImportError):
    category = ErrorCategory.RECOVERY_REQUIRED


class RollbackFailed(CaptureImportError):
    category = ErrorCategory.ROLLBACK_FAILED
