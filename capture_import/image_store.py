"""Ownership-scoped managed image persistence for capture-package imports."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Callable, Mapping

from coin_collection import ItemPhoto, PhotoRole

from ._filesystem import (
    delete_open_file,
    ensure_plain_directory,
    handle_object_identity,
    handle_matches_path,
    is_link_or_reparse,
    open_existing_binary_for_delete,
    open_exclusive_binary,
    path_object_identity,
    require_plain_directory,
    require_plain_regular_file,
)
from ._json import canonical_json_bytes, parse_bounded_json_object
from .archive import CapturePackageArchiveReader
from .enums import ImageRole
from .durable_models import (
    ExpectedImageEvidence,
    NativeObjectIdentity,
    OwnershipDescriptor,
    VerifiedImageEvidence,
)
from .errors import ImageCollision, ImageCopyFailed, RecoveryRequired
from .media import CapturePackageMediaValidator, ValidatedMedia
from .lock import PackageImportLock, require_verified_import_lock
from .models import _validate_uuid
from .package import ValidatedCapturePackage
from .snapshot import SnapshotHandle

OWNER_FILENAME = ".import-owner.json"
OWNERSHIP_SCHEMA_VERSION = "1.0"
CreatedCallback = Callable[[str], None]

_ROLE_FILENAMES = {
    ImageRole.FRONT: "front",
    ImageRole.REVERSE: "reverse",
    ImageRole.EDGE: "edge",
}
_PHOTO_ROLES = {
    ImageRole.FRONT: PhotoRole.FRONT,
    ImageRole.REVERSE: PhotoRole.BACK,
    ImageRole.EDGE: PhotoRole.EDGE,
}


@dataclass(frozen=True, slots=True)
class ManagedImage:
    source_coin_id: str
    desktop_item_id: str
    role: ImageRole
    managed_relative_path: str
    collection_path: str
    sha256: str
    byte_length: int


@dataclass(frozen=True, slots=True)
class ManagedImagePlan:
    import_id: str
    ownership_token: str
    import_root_relative_path: str
    expected_relative_paths: tuple[str, ...]
    source_to_desktop: tuple[tuple[str, str], ...]
    media: tuple[ManagedImage, ...]

    def validate(self) -> None:
        _validate_uuid(self.import_id, "import_id")
        _validate_uuid(self.ownership_token, "ownership_token")
        if self.import_root_relative_path != f"imports/{self.import_id}":
            raise ValueError("import root does not match import_id.")
        if self.expected_relative_paths != tuple(sorted(set(self.expected_relative_paths))):
            raise ValueError("expected paths must be unique and sorted.")
        if not self.source_to_desktop:
            raise ValueError("At least one selected coin is required.")
        if len({source for source, _ in self.source_to_desktop}) != len(self.source_to_desktop):
            raise ValueError("Source coin IDs must be unique.")
        desktop_ids = tuple(desktop for _, desktop in self.source_to_desktop)
        if len(set(desktop_ids)) != len(desktop_ids):
            raise ValueError("Desktop item IDs must be unique.")
        for desktop_id in desktop_ids:
            _validate_uuid(desktop_id, "desktop_item_id")
        if any(image.desktop_item_id not in desktop_ids for image in self.media):
            raise ValueError("Managed media refers to an unknown desktop item.")


class ManagedCollectionImageStore:
    """Copy verified package media into one exclusively owned import root."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        collection_path_prefix: str = "coin_photos/collection",
    ) -> None:
        self._root = Path(root).absolute()
        prefix = PurePosixPath(collection_path_prefix)
        if prefix.is_absolute() or ".." in prefix.parts:
            raise ValueError("collection_path_prefix must be relative.")
        self._collection_path_prefix = prefix.as_posix().rstrip("/")
        self._reader = CapturePackageArchiveReader()
        self._media_validator = CapturePackageMediaValidator()
        self._live_root_identities: dict[str, tuple[int, int]] = {}
        self._live_object_identities: dict[str, dict[str, tuple[int, int]]] = {}

    @property
    def root(self) -> Path:
        return self._root

    def plan(
        self,
        package: ValidatedCapturePackage,
        *,
        import_id: str,
        ownership_token: str,
        source_to_desktop: Mapping[str, str],
    ) -> ManagedImagePlan:
        _validate_uuid(import_id, "import_id")
        _validate_uuid(ownership_token, "ownership_token")
        ordered_mapping = tuple(source_to_desktop.items())
        media_by_coin: dict[str, list[ManagedImage]] = {}
        root_relative = f"imports/{import_id}"
        expected = {root_relative, f"{root_relative}/{OWNER_FILENAME}"}
        for source_id, desktop_id in ordered_mapping:
            _validate_uuid(desktop_id, "desktop_item_id")
            item_root = f"{root_relative}/{desktop_id}"
            expected.add(item_root)
            media_by_coin[source_id] = []
            for descriptor in sorted(
                (value for value in package.media if value.coin_id == source_id),
                key=lambda value: value.role.value,
            ):
                suffix = ".jpg" if descriptor.mime_type == "image/jpeg" else ".png"
                relative = f"{item_root}/{_ROLE_FILENAMES[descriptor.role]}{suffix}"
                expected.add(relative)
                media_by_coin[source_id].append(
                    ManagedImage(
                        source_coin_id=source_id,
                        desktop_item_id=desktop_id,
                        role=descriptor.role,
                        managed_relative_path=relative,
                        collection_path=f"{self._collection_path_prefix}/{relative}",
                        sha256=descriptor.sha256,
                        byte_length=descriptor.byte_length,
                    )
                )
        flattened = tuple(
            image
            for source_id, _ in ordered_mapping
            for image in media_by_coin.get(source_id, ())
        )
        result = ManagedImagePlan(
            import_id=import_id,
            ownership_token=ownership_token,
            import_root_relative_path=root_relative,
            expected_relative_paths=tuple(sorted(expected)),
            source_to_desktop=ordered_mapping,
            media=flattened,
        )
        result.validate()
        return result

    def copy(
        self,
        snapshot: SnapshotHandle,
        package: ValidatedCapturePackage,
        plan: ManagedImagePlan,
        on_created: CreatedCallback,
        *,
        import_lock: PackageImportLock,
    ) -> dict[str, tuple[ItemPhoto, ...]]:
        """Create every planned object exclusively and verify exact copied bytes."""

        require_verified_import_lock(import_lock, import_id=plan.import_id)
        plan.validate()
        snapshot.validate()
        import_root = self._resolve(plan.import_root_relative_path)
        created: list[Path] = []
        try:
            require_verified_import_lock(import_lock, import_id=plan.import_id)
            ensure_plain_directory(self._root / "imports")
            require_verified_import_lock(import_lock, import_id=plan.import_id)
            os.mkdir(import_root, 0o700)
            self._live_root_identities[plan.import_id] = path_object_identity(
                import_root
            )
            self._live_object_identities[plan.import_id] = {
                plan.import_root_relative_path: path_object_identity(import_root)
            }
            created.append(import_root)
            on_created(plan.import_root_relative_path)
            marker_path = import_root / OWNER_FILENAME
            marker = {
                "ownership_schema_version": OWNERSHIP_SCHEMA_VERSION,
                "import_id": plan.import_id,
                "random_ownership_token": plan.ownership_token,
            }
            require_verified_import_lock(import_lock, import_id=plan.import_id)
            self._write_exclusive_verified(marker_path, canonical_json_bytes(marker))
            self._record_live_identity(
                plan.import_id,
                f"{plan.import_root_relative_path}/{OWNER_FILENAME}",
                marker_path,
            )
            created.append(marker_path)
            on_created(f"{plan.import_root_relative_path}/{OWNER_FILENAME}")

            item_directories: set[str] = set()
            by_source: dict[str, list[ItemPhoto]] = {
                source_id: [] for source_id, _ in plan.source_to_desktop
            }
            descriptor_by_key = {
                (value.coin_id, value.role): value for value in package.media
            }
            with snapshot.open_package() as package_handle:
                archive, _ = self._reader.validate(
                    package_handle, package.package_basename
                )
                try:
                    for image in plan.media:
                        item_relative = str(PurePosixPath(image.managed_relative_path).parent)
                        if item_relative not in item_directories:
                            require_verified_import_lock(
                                import_lock,
                                import_id=plan.import_id,
                            )
                            item_path = self._resolve(item_relative)
                            os.mkdir(item_path, 0o700)
                            self._record_live_identity(
                                plan.import_id, item_relative, item_path
                            )
                            created.append(item_path)
                            item_directories.add(item_relative)
                            on_created(item_relative)
                        expected = descriptor_by_key[(image.source_coin_id, image.role)]
                        entry = package.archive.entry(expected.archive_path)
                        if entry is None:
                            raise ImageCopyFailed()
                        payload = self._reader.read_entry(
                            archive, entry, expected.byte_length
                        )
                        self._media_validator.verify_payload(payload, expected)
                        destination = self._resolve(image.managed_relative_path)
                        require_verified_import_lock(
                            import_lock,
                            import_id=plan.import_id,
                        )
                        self._write_exclusive_verified(
                            destination, payload, expected=expected
                        )
                        self._record_live_identity(
                            plan.import_id,
                            image.managed_relative_path,
                            destination,
                        )
                        created.append(destination)
                        on_created(image.managed_relative_path)
                        by_source[image.source_coin_id].append(
                            ItemPhoto(
                                path=image.collection_path,
                                role=_PHOTO_ROLES[image.role],
                                is_primary=image.role is ImageRole.FRONT,
                                display_order=len(by_source[image.source_coin_id]),
                            )
                        )
                finally:
                    archive.close()
            self.verify(plan)
            return {key: tuple(value) for key, value in by_source.items()}
        except FileExistsError as error:
            raise ImageCollision(error) from error
        except (ImageCollision, ImageCopyFailed):
            raise
        except Exception as error:
            raise ImageCopyFailed(error) from error

    def expected_evidence(
        self, package: ValidatedCapturePackage, plan: ManagedImagePlan
    ) -> tuple[ExpectedImageEvidence, ...]:
        """Build the immutable schema-2 expected managed-image inventory."""

        descriptors = {(value.coin_id, value.role): value for value in package.media}
        result: list[ExpectedImageEvidence] = []
        for image in plan.media:
            source = descriptors[(image.source_coin_id, image.role)]
            result.append(
                ExpectedImageEvidence(
                    relative_path=image.managed_relative_path,
                    role=image.role.value,
                    byte_length=image.byte_length,
                    sha256=image.sha256,
                    media_type=source.mime_type,
                    width=source.width,
                    height=source.height,
                )
            )
        return tuple(result)

    def verified_evidence(
        self, package: ValidatedCapturePackage, plan: ManagedImagePlan
    ) -> tuple[VerifiedImageEvidence, ...]:
        """Return exact held-identity evidence after complete managed-image copy."""

        self.verify(plan)
        expected = self.expected_evidence(package, plan)
        result: list[VerifiedImageEvidence] = []
        for item in expected:
            path = self._resolve(item.relative_path)
            result.append(
                VerifiedImageEvidence(
                    relative_path=item.relative_path,
                    role=item.role,
                    byte_length=item.byte_length,
                    sha256=item.sha256,
                    media_type=item.media_type,
                    width=item.width,
                    height=item.height,
                    parent_identity=NativeObjectIdentity.from_native(
                        path_object_identity(path.parent), windows=os.name == "nt"
                    ),
                    object_identity=NativeObjectIdentity.from_native(
                        path_object_identity(path), windows=os.name == "nt"
                    ),
                )
            )
        return tuple(result)

    def ownership_descriptors(
        self, plan: ManagedImagePlan, *, require_complete: bool = True
    ) -> tuple[OwnershipDescriptor, ...]:
        """Return the complete exact managed-image cleanup inventory."""

        actual = self._require_owned_tree(plan, require_complete=require_complete)
        descriptors: list[OwnershipDescriptor] = []
        for path, (native_identity, mode) in sorted(
            actual.items(),
            key=lambda item: (len(item[0].parts), str(item[0])),
            reverse=True,
        ):
            relative = path.relative_to(self._root).as_posix()
            if stat.S_ISDIR(mode):
                length = None
                digest = None
                kind = "DIRECTORY"
            else:
                payload = path.read_bytes()
                length = len(payload)
                digest = sha256(payload).hexdigest()
                kind = "FILE"
            descriptors.append(
                OwnershipDescriptor(
                    root="MANAGED_IMAGE",
                    relative_path=relative,
                    object_kind=kind,
                    ownership_token=plan.ownership_token,
                    expected_byte_length=length,
                    expected_sha256=digest,
                    parent_identity=NativeObjectIdentity.from_native(
                        path_object_identity(path.parent), windows=os.name == "nt"
                    ),
                    object_identity=NativeObjectIdentity.from_native(
                        native_identity, windows=os.name == "nt"
                    ),
                )
            )
        return tuple(descriptors)

    def cleanup(
        self,
        plan: ManagedImagePlan,
        *,
        import_lock: PackageImportLock,
        ownership_recorded: bool = True,
    ) -> None:
        """Remove only the exact root whose strict owner marker matches ``plan``."""

        require_verified_import_lock(import_lock, import_id=plan.import_id)
        plan.validate()
        import_root = self._resolve(plan.import_root_relative_path)
        if not import_root.exists():
            self._live_root_identities.pop(plan.import_id, None)
            self._live_object_identities.pop(plan.import_id, None)
            return
        try:
            if not ownership_recorded:
                identity = self._live_root_identities.get(plan.import_id)
                if identity != path_object_identity(import_root):
                    return
                if any(import_root.iterdir()):
                    raise RecoveryRequired()
                require_verified_import_lock(import_lock, import_id=plan.import_id)
                os.rmdir(import_root)
                self._live_root_identities.pop(plan.import_id, None)
                self._live_object_identities.pop(plan.import_id, None)
                return
            self._verify_live_identities(plan)
            actual = self._require_owned_tree(plan, require_complete=False)
            for path in sorted(
                (
                    path
                    for path in actual
                    if path != import_root and not stat.S_ISDIR(actual[path][1])
                ),
                key=lambda value: len(value.parts),
                reverse=True,
            ):
                require_verified_import_lock(import_lock, import_id=plan.import_id)
                handle = open_existing_binary_for_delete(path)
                try:
                    if handle_object_identity(handle) != actual[path][0]:
                        raise RecoveryRequired()
                    delete_open_file(handle, path)
                finally:
                    handle.close()
            for path in sorted(
                (path for path in actual if stat.S_ISDIR(actual[path][1])),
                key=lambda value: len(value.parts),
                reverse=True,
            ):
                require_verified_import_lock(import_lock, import_id=plan.import_id)
                if path_object_identity(path) != actual[path][0]:
                    raise RecoveryRequired()
                os.rmdir(path)
            self._live_root_identities.pop(plan.import_id, None)
            self._live_object_identities.pop(plan.import_id, None)
        except RecoveryRequired:
            raise
        except OSError as error:
            raise RecoveryRequired(error) from error

    def verify(self, plan: ManagedImagePlan) -> None:
        """Verify ownership, exact inventory, lengths, and hashes without mutation."""

        actual = self._require_owned_tree(plan, require_complete=True)
        import_root = self._resolve(plan.import_root_relative_path)
        root_identity = actual.get(import_root, (None, 0))[0]
        if root_identity is None:
            raise RecoveryRequired()
        for image in plan.media:
            path = self._resolve(image.managed_relative_path)
            inventoried_identity = actual.get(path, (None, 0))[0]
            if inventoried_identity is None:
                raise RecoveryRequired()
            info = require_plain_regular_file(path)
            if info.st_size != image.byte_length:
                raise RecoveryRequired()
            digest = sha256()
            length = 0
            with open_existing_binary_for_delete(path) as handle:
                if handle_object_identity(handle) != inventoried_identity:
                    raise RecoveryRequired()
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    length += len(chunk)
                    if length > image.byte_length:
                        raise RecoveryRequired()
                    digest.update(chunk)
                if not handle_matches_path(handle, path):
                    raise RecoveryRequired()
            if length != image.byte_length or digest.hexdigest() != image.sha256:
                raise RecoveryRequired()
        if path_object_identity(import_root) != root_identity:
            raise RecoveryRequired()

    def _require_owned_tree(
        self, plan: ManagedImagePlan, *, require_complete: bool
    ) -> dict[Path, tuple[tuple[int, int], int]]:
        import_root = self._resolve(plan.import_root_relative_path)
        require_plain_directory(self._root)
        require_plain_directory(import_root)
        marker_path = import_root / OWNER_FILENAME
        marker_info = require_plain_regular_file(marker_path)
        if marker_info.st_size > 4096:
            raise RecoveryRequired()
        with open_existing_binary_for_delete(marker_path) as marker_handle:
            if handle_object_identity(marker_handle) != path_object_identity(marker_path):
                raise RecoveryRequired()
            raw_marker = marker_handle.read(4097)
            if not handle_matches_path(marker_handle, marker_path):
                raise RecoveryRequired()
        marker = parse_bounded_json_object(raw_marker, "managed image owner")
        if marker != {
            "ownership_schema_version": OWNERSHIP_SCHEMA_VERSION,
            "import_id": plan.import_id,
            "random_ownership_token": plan.ownership_token,
        }:
            raise RecoveryRequired()
        expected = {self._resolve(path) for path in plan.expected_relative_paths}
        actual = self._inventory_plain_tree(import_root)
        actual_paths = set(actual)
        if (require_complete and actual_paths != expected) or not actual_paths.issubset(
            expected
        ):
            raise RecoveryRequired()
        return actual

    def _resolve(self, relative: str) -> Path:
        pure = PurePosixPath(relative)
        if pure.is_absolute() or not pure.parts or ".." in pure.parts:
            raise RecoveryRequired()
        result = self._root.joinpath(*pure.parts)
        try:
            result.relative_to(self._root)
        except ValueError as error:
            raise RecoveryRequired(error) from error
        return result

    @staticmethod
    def _inventory_plain_tree(
        root: Path,
    ) -> dict[Path, tuple[tuple[int, int], int]]:
        """Enumerate a tree without following a link or reparse point."""

        pending = [root]
        result: dict[Path, tuple[tuple[int, int], int]] = {}
        while pending:
            directory = pending.pop()
            require_plain_directory(directory)
            if is_link_or_reparse(directory):
                raise RecoveryRequired()
            directory_info = directory.lstat()
            result[directory] = (
                path_object_identity(directory),
                directory_info.st_mode,
            )
            with os.scandir(directory) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    if is_link_or_reparse(path):
                        raise RecoveryRequired()
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(path)
                    elif entry.is_file(follow_symlinks=False):
                        require_plain_regular_file(path)
                        path_info = path.lstat()
                        result[path] = (path_object_identity(path), path_info.st_mode)
                    else:
                        raise RecoveryRequired()
        return result

    def _write_exclusive_verified(
        self,
        path: Path,
        payload: bytes,
        *,
        expected: ValidatedMedia | None = None,
    ) -> None:
        handle = open_exclusive_binary(path)
        try:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            if not handle_matches_path(handle, path):
                raise RecoveryRequired()
            handle.seek(0)
            persisted = handle.read(len(payload) + 1)
            if persisted != payload or not handle_matches_path(handle, path):
                raise ImageCopyFailed()
            if expected is not None:
                if (
                    len(persisted) != expected.byte_length
                    or sha256(persisted).hexdigest() != expected.sha256
                ):
                    raise ImageCopyFailed()
                self._media_validator.verify_payload(persisted, expected)
        finally:
            handle.close()

    def _record_live_identity(
        self, import_id: str, relative_path: str, path: Path
    ) -> None:
        identities = self._live_object_identities.get(import_id)
        if identities is None:
            raise RecoveryRequired()
        identities[relative_path] = path_object_identity(path)

    def _verify_live_identities(self, plan: ManagedImagePlan) -> None:
        identities = self._live_object_identities.get(plan.import_id)
        if identities is None:
            return
        for relative_path, expected in identities.items():
            path = self._resolve(relative_path)
            try:
                actual = path_object_identity(path)
            except OSError as error:
                raise RecoveryRequired(error) from error
            if actual != expected:
                raise RecoveryRequired()
