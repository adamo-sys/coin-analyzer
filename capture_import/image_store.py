"""Ownership-scoped managed image persistence for capture-package imports."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Callable, Mapping

from coin_collection import (
    CaptureImportMediaProvenance,
    ItemPhoto,
    PhotoRole,
)

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
    ExpectedImageV3,
    NativeObjectIdentity,
    OwnershipDescriptor,
    VerifiedImageEvidence,
    VerifiedImageV3,
)
from .errors import ImageCollision, ImageCopyFailed, RecoveryRequired
from .media import CapturePackageMediaValidator, ValidatedMedia
from .lock import PackageImportLock, require_verified_import_lock
from .limits import (
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
    MAX_PROCESSED_ARTIFACT_SIZE,
)
from .models import _validate_uuid
from .package import ValidatedCapturePackage
from .processed_snapshot import ProcessedSnapshotHandle
from .snapshot import SnapshotHandle

OWNER_FILENAME = ".import-owner.json"
OWNERSHIP_SCHEMA_VERSION = "1.0"
CreatedCallback = Callable[[str], None]
ProcessedVerifiedCallback = Callable[[VerifiedImageV3], None]

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


@dataclass(frozen=True, slots=True)
class ProcessedManagedImage:
    source_coin_id: str
    desktop_item_id: str
    role: ImageRole
    managed_relative_path: str
    collection_path: str
    sha256: str
    byte_length: int
    media_type: str
    width: int
    height: int
    source_snapshot_id: str
    source_artifact_key: str
    variant: str
    artifact_index: int


@dataclass(frozen=True, slots=True)
class ProcessedManagedImagePlan:
    import_id: str
    ownership_token: str
    import_root_relative_path: str
    expected_relative_paths: tuple[str, ...]
    source_to_desktop: tuple[tuple[str, str], ...]
    processed_snapshot_id: str
    package_sha256: str
    media: tuple[ProcessedManagedImage, ...]

    def validate(self) -> None:
        _validate_uuid(self.import_id, "import_id")
        _validate_uuid(self.ownership_token, "ownership_token")
        _validate_uuid(self.processed_snapshot_id, "processed_snapshot_id")
        if (
            not isinstance(self.package_sha256, str)
            or len(self.package_sha256) != 64
            or any(value not in "0123456789abcdef" for value in self.package_sha256)
        ):
            raise ValueError("package_sha256 must be lowercase SHA-256.")
        if self.import_root_relative_path != f"imports/{self.import_id}":
            raise ValueError("import root does not match import_id.")
        if self.expected_relative_paths != tuple(
            sorted(set(self.expected_relative_paths))
        ):
            raise ValueError("expected paths must be unique and sorted.")
        if not self.source_to_desktop or not self.media:
            raise ValueError("Processed image plan must not be empty.")
        sources = tuple(source for source, _desktop in self.source_to_desktop)
        desktops = tuple(desktop for _source, desktop in self.source_to_desktop)
        if len(set(sources)) != len(sources) or len(set(desktops)) != len(desktops):
            raise ValueError("Processed source and desktop IDs must be unique.")
        for desktop_id in desktops:
            _validate_uuid(desktop_id, "desktop_item_id")
        if any(
            image.source_coin_id not in sources
            or image.desktop_item_id not in desktops
            or image.source_snapshot_id != self.processed_snapshot_id
            or image.media_type != "image/jpeg"
            or image.variant not in {"NORMALIZED", "CROPPED"}
            or image.artifact_index < 0
            for image in self.media
        ):
            raise ValueError("Processed managed image evidence is inconsistent.")
        mapping = dict(self.source_to_desktop)
        for image in self.media:
            if image.desktop_item_id != mapping[image.source_coin_id]:
                raise ValueError("Processed source/desktop mapping is inconsistent.")
            if (
                not isinstance(image.source_artifact_key, str)
                or not 1 <= len(image.source_artifact_key) <= 255
                or not isinstance(image.sha256, str)
                or len(image.sha256) != 64
                or any(value not in "0123456789abcdef" for value in image.sha256)
                or not 1 <= image.byte_length <= MAX_PROCESSED_ARTIFACT_SIZE
                or not 1 <= image.width <= MAX_IMAGE_DIMENSION
                or not 1 <= image.height <= MAX_IMAGE_DIMENSION
                or image.width * image.height > MAX_IMAGE_PIXELS
            ):
                raise ValueError("Processed managed image fields are invalid.")
            item_root = (
                f"{self.import_root_relative_path}/{image.desktop_item_id}"
            )
            expected_path = f"{item_root}/{_ROLE_FILENAMES[image.role]}.jpg"
            collection_path = PurePosixPath(image.collection_path)
            expected_parts = PurePosixPath(expected_path).parts
            if (
                image.managed_relative_path != expected_path
                or collection_path.is_absolute()
                or ".." in collection_path.parts
                or collection_path.parts[-len(expected_parts) :]
                != expected_parts
            ):
                raise ValueError("Processed managed image path is not canonical.")
        identities = tuple(
            (image.source_coin_id, image.role) for image in self.media
        )
        if len(set(identities)) != len(identities):
            raise ValueError("Processed source coin/role identities must be unique.")
        if len({image.managed_relative_path for image in self.media}) != len(
            self.media
        ):
            raise ValueError("Processed managed paths must be unique.")
        if len({image.artifact_index for image in self.media}) != len(self.media):
            raise ValueError("Processed artifact indices must be unique.")


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

    def plan_processed(
        self,
        processed_snapshot: ProcessedSnapshotHandle,
        package: ValidatedCapturePackage,
        *,
        import_id: str,
        ownership_token: str,
        source_to_desktop: Mapping[str, str],
    ) -> ProcessedManagedImagePlan:
        """Plan managed JPEGs exclusively from a verified processed manifest."""

        _validate_uuid(import_id, "import_id")
        _validate_uuid(ownership_token, "ownership_token")
        processed_snapshot.validate()
        manifest = processed_snapshot.manifest
        if (
            manifest.source_package_sha256 != package.package_sha256
            or manifest.source_package_byte_length != package.package_byte_length
            or manifest.source_package_version != package.manifest.package_version
        ):
            raise ValueError("Processed snapshot does not match the package.")
        package_media = {
            (item.coin_id, item.role.value): item for item in package.media
        }
        for descriptor in manifest.artifacts:
            source = package_media.get((descriptor.source_coin_id, descriptor.role))
            if (
                source is None
                or descriptor.source_artifact.package_media_relative_path
                != source.archive_path
                or descriptor.source_artifact.package_media_sha256 != source.sha256
            ):
                raise ValueError("Processed artifact is mismapped to package media.")
        ordered_mapping = tuple(source_to_desktop.items())
        selected = {source for source, _desktop in ordered_mapping}
        if not selected or len(selected) != len(ordered_mapping):
            raise ValueError("Processed source selection must be non-empty and unique.")
        if not selected.issubset({item.id for item in package.manifest.coins}):
            raise ValueError("Processed source selection contains an unknown coin.")
        for _source, desktop_id in ordered_mapping:
            _validate_uuid(desktop_id, "desktop_item_id")
        root_relative = f"imports/{import_id}"
        expected = {root_relative, f"{root_relative}/{OWNER_FILENAME}"}
        planned: list[ProcessedManagedImage] = []
        by_source = dict(ordered_mapping)
        for index, descriptor in enumerate(manifest.artifacts):
            if descriptor.source_coin_id not in selected:
                continue
            desktop_id = by_source[descriptor.source_coin_id]
            item_root = f"{root_relative}/{desktop_id}"
            expected.add(item_root)
            role = ImageRole(descriptor.role)
            relative = f"{item_root}/{_ROLE_FILENAMES[role]}.jpg"
            expected.add(relative)
            planned.append(
                ProcessedManagedImage(
                    source_coin_id=descriptor.source_coin_id,
                    desktop_item_id=desktop_id,
                    role=role,
                    managed_relative_path=relative,
                    collection_path=f"{self._collection_path_prefix}/{relative}",
                    sha256=descriptor.sha256,
                    byte_length=descriptor.byte_length,
                    media_type=descriptor.content_type,
                    width=descriptor.width,
                    height=descriptor.height,
                    source_snapshot_id=manifest.processed_snapshot_id,
                    source_artifact_key=descriptor.artifact_key,
                    variant=descriptor.variant,
                    artifact_index=index,
                )
            )
        if {item.source_coin_id for item in planned} != selected:
            raise ValueError("Selected coins lack processed manifest artifacts.")
        result = ProcessedManagedImagePlan(
            import_id=import_id,
            ownership_token=ownership_token,
            import_root_relative_path=root_relative,
            expected_relative_paths=tuple(sorted(expected)),
            source_to_desktop=ordered_mapping,
            processed_snapshot_id=manifest.processed_snapshot_id,
            package_sha256=package.package_sha256,
            media=tuple(planned),
        )
        result.validate()
        processed_snapshot.validate()
        return result

    def copy_processed(
        self,
        processed_snapshot: ProcessedSnapshotHandle,
        plan: ProcessedManagedImagePlan,
        on_created: CreatedCallback,
        *,
        import_lock: PackageImportLock,
        on_image_verified: ProcessedVerifiedCallback | None = None,
    ) -> dict[str, tuple[ItemPhoto, ...]]:
        """Persist exact processed bytes without opening raw archive media."""

        require_verified_import_lock(import_lock, import_id=plan.import_id)
        plan.validate()
        processed_snapshot.validate()
        if processed_snapshot.manifest.processed_snapshot_id != plan.processed_snapshot_id:
            raise ImageCopyFailed()
        import_root = self._resolve(plan.import_root_relative_path)
        try:
            ensure_plain_directory(self._root / "imports")
            require_verified_import_lock(import_lock, import_id=plan.import_id)
            os.mkdir(import_root, 0o700)
            self._live_root_identities[plan.import_id] = path_object_identity(
                import_root
            )
            self._live_object_identities[plan.import_id] = {
                plan.import_root_relative_path: path_object_identity(import_root)
            }
            on_created(plan.import_root_relative_path)
            marker_path = import_root / OWNER_FILENAME
            marker = {
                "ownership_schema_version": OWNERSHIP_SCHEMA_VERSION,
                "import_id": plan.import_id,
                "random_ownership_token": plan.ownership_token,
            }
            require_verified_import_lock(import_lock, import_id=plan.import_id)
            self._write_exclusive_verified(
                marker_path, canonical_json_bytes(marker)
            )
            self._record_live_identity(
                plan.import_id,
                f"{plan.import_root_relative_path}/{OWNER_FILENAME}",
                marker_path,
            )
            on_created(f"{plan.import_root_relative_path}/{OWNER_FILENAME}")
            directories: set[str] = set()
            by_source: dict[str, list[ItemPhoto]] = {
                source: [] for source, _desktop in plan.source_to_desktop
            }
            for image in plan.media:
                item_relative = str(
                    PurePosixPath(image.managed_relative_path).parent
                )
                if item_relative not in directories:
                    require_verified_import_lock(
                        import_lock, import_id=plan.import_id
                    )
                    item_path = self._resolve(item_relative)
                    os.mkdir(item_path, 0o700)
                    self._record_live_identity(
                        plan.import_id, item_relative, item_path
                    )
                    directories.add(item_relative)
                    on_created(item_relative)
                processed_snapshot.validate()
                descriptor = processed_snapshot.manifest.artifacts[
                    image.artifact_index
                ]
                if (
                    descriptor.source_coin_id != image.source_coin_id
                    or descriptor.role != image.role.value
                    or descriptor.artifact_key != image.source_artifact_key
                    or descriptor.variant != image.variant
                    or descriptor.content_type != image.media_type
                    or descriptor.width != image.width
                    or descriptor.height != image.height
                    or descriptor.byte_length != image.byte_length
                    or descriptor.sha256 != image.sha256
                ):
                    raise ImageCopyFailed()
                with processed_snapshot.open_artifact(
                    image.artifact_index
                ) as source:
                    payload = source.read(image.byte_length + 1)
                    if (
                        len(payload) != image.byte_length
                        or sha256(payload).hexdigest() != image.sha256
                    ):
                        raise ImageCopyFailed()
                processed_snapshot.validate()
                destination = self._resolve(image.managed_relative_path)
                require_verified_import_lock(
                    import_lock, import_id=plan.import_id
                )
                self._write_exclusive_verified(destination, payload)
                self._record_live_identity(
                    plan.import_id,
                    image.managed_relative_path,
                    destination,
                )
                on_created(image.managed_relative_path)
                processed_snapshot.validate()
                evidence = self._verified_processed_image(image)
                if on_image_verified is not None:
                    on_image_verified(evidence)
                by_source[image.source_coin_id].append(
                    ItemPhoto(
                        path=image.collection_path,
                        role=_PHOTO_ROLES[image.role],
                        is_primary=image.role is ImageRole.FRONT,
                        display_order=len(by_source[image.source_coin_id]),
                        capture_import_media=CaptureImportMediaProvenance(
                            schema_version="1.0",
                            import_id=plan.import_id,
                            source_kind="PROCESSED_SNAPSHOT",
                            package_sha256=plan.package_sha256,
                            processed_snapshot_id=plan.processed_snapshot_id,
                            artifact_key=image.source_artifact_key,
                            artifact_sha256=image.sha256,
                            variant=image.variant,
                        ),
                    )
                )
            processed_snapshot.validate()
            self.verify_processed(plan)
            result = {key: tuple(value) for key, value in by_source.items()}
            self.validate_processed_photos(plan, result)
            return result
        except FileExistsError as error:
            try:
                processed_snapshot.validate()
            except Exception as validation_error:
                raise ImageCopyFailed(validation_error) from error
            raise ImageCollision(error) from error
        except (ImageCollision, ImageCopyFailed):
            try:
                processed_snapshot.validate()
            except Exception as validation_error:
                raise ImageCopyFailed(validation_error) from validation_error
            raise
        except Exception as error:
            try:
                processed_snapshot.validate()
            except Exception as validation_error:
                raise ImageCopyFailed(validation_error) from error
            raise ImageCopyFailed(error) from error

    def _verified_processed_image(
        self, image: ProcessedManagedImage
    ) -> VerifiedImageV3:
        path = self._resolve(image.managed_relative_path)
        payload = path.read_bytes()
        if (
            len(payload) != image.byte_length
            or sha256(payload).hexdigest() != image.sha256
        ):
            raise ImageCopyFailed()
        return VerifiedImageV3(
            relative_path=image.managed_relative_path,
            role=image.role.value,
            byte_length=image.byte_length,
            sha256=image.sha256,
            media_type=image.media_type,
            width=image.width,
            height=image.height,
            source_kind="PROCESSED_SNAPSHOT",
            source_snapshot_id=image.source_snapshot_id,
            source_coin_id=image.source_coin_id,
            source_artifact_key=image.source_artifact_key,
            variant=image.variant,
            parent_identity=NativeObjectIdentity.from_native(
                path_object_identity(path.parent), windows=os.name == "nt"
            ),
            object_identity=NativeObjectIdentity.from_native(
                path_object_identity(path), windows=os.name == "nt"
            ),
        )

    def reconcile_processed_copy(
        self,
        plan: ProcessedManagedImagePlan,
        verified_prefix: tuple[VerifiedImageV3, ...],
    ) -> tuple[VerifiedImageV3, ...]:
        """Verify a durable prefix; never resume copying after restart."""

        plan.validate()
        expected = self.expected_evidence_processed(plan)
        if len(verified_prefix) > len(expected):
            raise RecoveryRequired()
        for index, (expected_item, verified) in enumerate(
            zip(expected, verified_prefix, strict=False)
        ):
            verified.validate()
            if any(
                getattr(verified, name) != getattr(expected_item, name)
                for name in expected_item.__dataclass_fields__
            ):
                raise RecoveryRequired()
            actual = self._verified_processed_image(plan.media[index])
            if actual != verified:
                raise RecoveryRequired()
        root = self.root / plan.import_root_relative_path
        if root.exists():
            self._require_owned_tree(plan, require_complete=False)
        return verified_prefix

    def photos_from_processed_plan(
        self, plan: ProcessedManagedImagePlan
    ) -> dict[str, tuple[ItemPhoto, ...]]:
        """Rebuild exact collection photo records from a fully verified plan."""

        self.verify_processed(plan)
        by_source: dict[str, list[ItemPhoto]] = {
            source: [] for source, _desktop in plan.source_to_desktop
        }
        for image in plan.media:
            photos = by_source[image.source_coin_id]
            photos.append(
                ItemPhoto(
                    path=image.collection_path,
                    role=_PHOTO_ROLES[image.role],
                    is_primary=image.role is ImageRole.FRONT,
                    display_order=len(photos),
                    capture_import_media=CaptureImportMediaProvenance(
                        "1.0",
                        plan.import_id,
                        "PROCESSED_SNAPSHOT",
                        plan.package_sha256,
                        plan.processed_snapshot_id,
                        image.source_artifact_key,
                        image.sha256,
                        image.variant,
                    ),
                )
            )
        result = {source: tuple(items) for source, items in by_source.items()}
        self.validate_processed_photos(plan, result)
        return result

    def expected_evidence_processed(
        self, plan: ProcessedManagedImagePlan
    ) -> tuple[ExpectedImageV3, ...]:
        plan.validate()
        return tuple(
            ExpectedImageV3(
                relative_path=image.managed_relative_path,
                role=image.role.value,
                byte_length=image.byte_length,
                sha256=image.sha256,
                media_type=image.media_type,
                width=image.width,
                height=image.height,
                source_kind="PROCESSED_SNAPSHOT",
                source_snapshot_id=image.source_snapshot_id,
                source_coin_id=image.source_coin_id,
                source_artifact_key=image.source_artifact_key,
                variant=image.variant,
            )
            for image in plan.media
        )

    def verified_evidence_processed(
        self, plan: ProcessedManagedImagePlan
    ) -> tuple[VerifiedImageV3, ...]:
        self.verify_processed(plan)
        return tuple(
            VerifiedImageV3(
                **item.to_dict(),
                parent_identity=NativeObjectIdentity.from_native(
                    path_object_identity(
                        self._resolve(item.relative_path).parent
                    ),
                    windows=os.name == "nt",
                ),
                object_identity=NativeObjectIdentity.from_native(
                    path_object_identity(self._resolve(item.relative_path)),
                    windows=os.name == "nt",
                ),
            )
            for item in self.expected_evidence_processed(plan)
        )

    def verify_processed(self, plan: ProcessedManagedImagePlan) -> None:
        """Verify exact processed-plan managed bytes and ownership inventory."""

        plan.validate()
        self.verify(plan)  # The physical managed-tree contract is identical.

    def validate_processed_photos(
        self,
        plan: ProcessedManagedImagePlan,
        photos: Mapping[str, tuple[ItemPhoto, ...]],
    ) -> None:
        """Reject collection provenance that differs from the processed plan."""

        plan.validate()
        expected_sources = tuple(source for source, _desktop in plan.source_to_desktop)
        if set(photos) != set(expected_sources):
            raise ValueError("Processed photo sources do not match the plan.")
        by_source: dict[str, list[ProcessedManagedImage]] = {
            source: [] for source in expected_sources
        }
        for image in plan.media:
            by_source[image.source_coin_id].append(image)
        for source in expected_sources:
            actual = photos[source]
            expected = by_source[source]
            if len(actual) != len(expected):
                raise ValueError("Processed photo inventory does not match the plan.")
            for order, (photo, image) in enumerate(
                zip(actual, expected, strict=True)
            ):
                provenance = photo.capture_import_media
                if (
                    photo.path != image.collection_path
                    or photo.role is not _PHOTO_ROLES[image.role]
                    or photo.display_order != order
                    or provenance is None
                    or provenance.schema_version != "1.0"
                    or provenance.import_id != plan.import_id
                    or provenance.source_kind != "PROCESSED_SNAPSHOT"
                    or provenance.package_sha256 != plan.package_sha256
                    or provenance.processed_snapshot_id
                    != plan.processed_snapshot_id
                    or provenance.artifact_key != image.source_artifact_key
                    or provenance.artifact_sha256 != image.sha256
                    or provenance.variant != image.variant
                ):
                    raise ValueError(
                        "Processed photo provenance does not match its plan."
                    )

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
