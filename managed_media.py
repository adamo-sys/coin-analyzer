"""Collection-owned media ingestion for ordinary manual-entry items."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import re
import stat
from typing import Iterable
from uuid import uuid4

from coin_collection import ItemPhoto


class ManagedMediaIngestionError(RuntimeError):
    """Raised when ordinary-entry media cannot be copied and verified."""


@dataclass(frozen=True, slots=True)
class _CreatedManagedFile:
    path: str
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class ManagedMediaIngestion:
    """Verified managed photos and the exact files created for them."""

    photos: tuple[ItemPhoto, ...]
    created_files: tuple[_CreatedManagedFile, ...]
    created_item_directory: str | None


class OrdinaryEntryManagedMediaStore:
    """Copy ordinary-entry photos into collection-owned storage."""

    _SAFE_ITEM_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
    _SAFE_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,10}")

    def __init__(self, collection_storage_path: str) -> None:
        collection_path = Path(collection_storage_path)
        self.root = collection_path.parent / "managed_media" / "ordinary"

    def ingest(
        self,
        item_id: str,
        photos: Iterable[ItemPhoto],
    ) -> ManagedMediaIngestion:
        """Copy all photos and return rebuilt metadata only after verification."""
        if self._SAFE_ITEM_ID.fullmatch(str(item_id or "")) is None:
            raise ManagedMediaIngestionError("The item ID is unsafe for managed media.")

        source_photos = tuple(photos)
        if any(not isinstance(photo, ItemPhoto) for photo in source_photos):
            raise ManagedMediaIngestionError("Managed media requires ItemPhoto values.")
        if any(photo.capture_import_media is not None for photo in source_photos):
            raise ManagedMediaIngestionError(
                "Capture/import media cannot enter the ordinary-entry media path."
            )

        item_directory = self.root / item_id
        directory_existed = item_directory.exists()
        created: list[_CreatedManagedFile] = []
        rebuilt: list[ItemPhoto] = []
        try:
            item_directory.mkdir(parents=True, exist_ok=True)
            if item_directory.is_symlink() or not item_directory.is_dir():
                raise ManagedMediaIngestionError(
                    "The managed-media item path is not a plain directory."
                )

            for photo in source_photos:
                source = Path(photo.path)
                if not source.is_file():
                    raise ManagedMediaIngestionError(
                        f"Source photo is missing or is not a file: {photo.path}"
                    )
                destination = item_directory / (
                    f"{uuid4().hex}{self._preserved_extension(source)}"
                )
                byte_length, copied_sha256 = self._copy_exclusively(
                    source, destination
                )
                identity = os.stat(destination, follow_symlinks=False)
                created.append(
                    _CreatedManagedFile(
                        path=str(destination),
                        device=identity.st_dev,
                        inode=identity.st_ino,
                    )
                )
                verified_length, verified_sha256 = self._hash_file(destination)
                if (
                    verified_length != byte_length
                    or verified_sha256 != copied_sha256
                ):
                    raise ManagedMediaIngestionError(
                        "A managed photo did not verify after copying."
                    )
                rebuilt.append(
                    ItemPhoto(
                        path=str(destination),
                        role=photo.role,
                        is_primary=photo.is_primary,
                        notes=photo.notes,
                        display_order=photo.display_order,
                    )
                )

            return ManagedMediaIngestion(
                photos=tuple(rebuilt),
                created_files=tuple(created),
                created_item_directory=(
                    None if directory_existed else str(item_directory)
                ),
            )
        except Exception as error:
            partial = ManagedMediaIngestion(
                photos=tuple(rebuilt),
                created_files=tuple(created),
                created_item_directory=(
                    None if directory_existed else str(item_directory)
                ),
            )
            self.rollback(partial)
            if isinstance(error, ManagedMediaIngestionError):
                raise
            raise ManagedMediaIngestionError(
                "Ordinary-entry managed media ingestion failed."
            ) from error

    def rollback(self, ingestion: ManagedMediaIngestion) -> tuple[str, ...]:
        """Remove only unchanged filesystem objects created by this ingestion."""
        retained: list[str] = []
        for created in reversed(ingestion.created_files):
            try:
                current = os.stat(created.path, follow_symlinks=False)
                if (
                    stat.S_ISREG(current.st_mode)
                    and current.st_dev == created.device
                    and current.st_ino == created.inode
                ):
                    os.unlink(created.path)
                else:
                    retained.append(created.path)
            except FileNotFoundError:
                continue
            except OSError:
                retained.append(created.path)

        if ingestion.created_item_directory:
            try:
                os.rmdir(ingestion.created_item_directory)
            except OSError:
                pass
        return tuple(reversed(retained))

    @classmethod
    def _preserved_extension(cls, source: Path) -> str:
        suffix = source.suffix
        return suffix.lower() if cls._SAFE_EXTENSION.fullmatch(suffix) else ""

    @staticmethod
    def _copy_exclusively(source: Path, destination: Path) -> tuple[int, str]:
        digest = sha256()
        byte_length = 0
        descriptor = -1
        created_identity: tuple[int, int] | None = None
        try:
            descriptor = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            created = os.fstat(descriptor)
            created_identity = (created.st_dev, created.st_ino)
            with source.open("rb") as source_handle, os.fdopen(
                descriptor, "wb"
            ) as destination_handle:
                descriptor = -1
                while True:
                    chunk = source_handle.read(1024 * 1024)
                    if not chunk:
                        break
                    destination_handle.write(chunk)
                    digest.update(chunk)
                    byte_length += len(chunk)
                destination_handle.flush()
                os.fsync(destination_handle.fileno())
        except Exception:
            if descriptor >= 0:
                os.close(descriptor)
                descriptor = -1
            if created_identity is not None:
                try:
                    current = os.stat(destination, follow_symlinks=False)
                    if (
                        stat.S_ISREG(current.st_mode)
                        and (current.st_dev, current.st_ino) == created_identity
                    ):
                        os.unlink(destination)
                except OSError:
                    pass
            raise
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        return byte_length, digest.hexdigest()

    @staticmethod
    def _hash_file(path: Path) -> tuple[int, str]:
        digest = sha256()
        byte_length = 0
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                byte_length += len(chunk)
        return byte_length, digest.hexdigest()
