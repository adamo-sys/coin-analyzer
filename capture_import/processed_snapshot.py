"""Identity-bound sealing for selected workflow image artifacts.

This module implements only Sprint 8 Unit 7B.  It creates and verifies the
standalone processed-artifact snapshot; coordinator ownership, journals,
transactions, recovery, and managed-image persistence remain later units.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import os
import math
from pathlib import Path, PurePosixPath
import re
import time
import unicodedata
from typing import Any, BinaryIO, Callable, Iterator, Mapping
from uuid import UUID, uuid4

from PIL import Image, UnidentifiedImageError

from ._filesystem import (
    PlainDirectoryHandle,
    create_plain_child_directory,
    delete_open_file,
    ensure_plain_directory,
    handle_matches_path,
    handle_object_identity,
    is_link_or_reparse,
    open_exclusive_child_binary,
    open_plain_child_directory,
    open_plain_child_file_readonly,
    open_plain_directory_handle,
    require_dense_regular_handle,
    sync_directory,
)
from ._json import canonical_json_bytes, parse_bounded_json_object
from .durable_models import NativeObjectIdentity
from .errors import SnapshotFailed, SnapshotRecoveryRequired
from .image_validation import require_complete_jpeg
from .limits import (
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
    MAX_JSON_BYTES,
    MAX_LOCK_WAIT_SECONDS,
    MAX_PROCESSED_ARTIFACT_BYTES,
    MAX_PROCESSED_ARTIFACT_SIZE,
    MAX_PROCESSED_ARTIFACTS,
    MAX_SAFE_RELATIVE_PATH_CHARS,
    PROCESSED_SNAPSHOT_COMPLETION_SCHEMA_VERSION,
    PROCESSED_SNAPSHOT_MANIFEST_SCHEMA_VERSION,
    PROCESSED_SNAPSHOT_OWNER_SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSION,
)
from .lock import PackageImportLock, require_verified_import_lock
from .package import ValidatedCapturePackage
from .workflow_models import PreparedArtifactDescriptor, PreparedArtifactSet

Clock = Callable[[], str]
IdentifierFactory = Callable[[], str]
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ROLE_ORDER = {"front": 0, "reverse": 1, "edge": 2}
_VARIANT_ORDER = {"CROPPED": 0, "NORMALIZED": 1}
_INVENTORY_DOMAIN = b"coin-analyzer.processed-artifact-inventory.v1\0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _identifier() -> str:
    return str(uuid4())


def _uuid4(value: str, name: str) -> None:
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError(f"{name} must be a canonical UUIDv4.") from error
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError(f"{name} must be a canonical UUIDv4.")


def _sha(value: str, name: str) -> None:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase SHA-256.")


def _timestamp(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{name} must be normalized UTC RFC 3339.")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError(f"{name} must be normalized UTC RFC 3339.") from error
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{name} must be normalized UTC RFC 3339.")


def _integer(value: int, name: str, minimum: int, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer.")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} is outside its supported range.")


def _nfc(value: str, name: str, maximum: int) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or unicodedata.normalize("NFC", value) != value
        or any(
            unicodedata.category(character) == "Cc"
            or 0xD800 <= ord(character) <= 0xDFFF
            for character in value
        )
    ):
        raise ValueError(f"{name} must be a bounded NFC string.")


def _relative_path(value: str, name: str) -> None:
    _nfc(value, name, MAX_SAFE_RELATIVE_PATH_CHARS)
    if "\\" in value or value.startswith(("/", "//")) or re.match(r"^[A-Za-z]:", value):
        raise ValueError(f"{name} must be a strict relative path.")
    parts = PurePosixPath(value).parts
    if (
        not parts
        or any(part in {"", ".", ".."} or part.endswith((".", " ")) for part in parts)
        or "/".join(parts) != value
    ):
        raise ValueError(f"{name} must be a strict relative path.")


def _closed(value: Mapping[str, Any], fields: frozenset[str], name: str) -> None:
    if not isinstance(value, Mapping) or frozenset(value) != fields:
        raise ValueError(f"{name} must contain exactly its closed schema fields.")


def _exact_string(value: Any, name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{name} must be a string.")
    return value


def _identity_from(value: Any, name: str) -> NativeObjectIdentity:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object.")
    _closed(
        value,
        frozenset({"platform", "volume_id", "object_id"}),
        name,
    )
    for field in ("platform", "volume_id", "object_id"):
        _exact_string(value[field], f"{name}.{field}")
    return NativeObjectIdentity.from_dict(value)


def _native(value: tuple[int, int]) -> NativeObjectIdentity:
    return NativeObjectIdentity.from_native(value, windows=os.name == "nt")


@dataclass(frozen=True, slots=True)
class SourceArtifactLink:
    package_media_relative_path: str
    package_media_sha256: str

    FIELDS = frozenset({"package_media_relative_path", "package_media_sha256"})

    def validate(self) -> None:
        _relative_path(
            self.package_media_relative_path, "package_media_relative_path"
        )
        _sha(self.package_media_sha256, "package_media_sha256")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "package_media_relative_path": self.package_media_relative_path,
            "package_media_sha256": self.package_media_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SourceArtifactLink":
        _closed(value, cls.FIELDS, "SourceArtifactLink")
        result = cls(
            _exact_string(
                value["package_media_relative_path"],
                "package_media_relative_path",
            ),
            _exact_string(value["package_media_sha256"], "package_media_sha256"),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class ProcessedArtifactDescriptor:
    artifact_key: str
    source_coin_id: str
    role: str
    variant: str
    relative_path: str
    content_type: str
    byte_length: int
    sha256: str
    width: int
    height: int
    source_artifact: SourceArtifactLink

    FIELDS = frozenset(
        {
            "artifact_key",
            "source_coin_id",
            "role",
            "variant",
            "relative_path",
            "content_type",
            "byte_length",
            "sha256",
            "width",
            "height",
            "source_artifact",
        }
    )

    def validate(self) -> None:
        _nfc(self.artifact_key, "artifact_key", 255)
        _nfc(self.source_coin_id, "source_coin_id", 16_384)
        if self.role not in _ROLE_ORDER:
            raise ValueError("role is unsupported.")
        if self.variant not in _VARIANT_ORDER:
            raise ValueError("variant is unsupported.")
        if self.content_type != "image/jpeg":
            raise ValueError("content_type must be image/jpeg.")
        _integer(
            self.byte_length,
            "byte_length",
            1,
            MAX_PROCESSED_ARTIFACT_SIZE,
        )
        _sha(self.sha256, "sha256")
        _integer(self.width, "width", 1, MAX_IMAGE_DIMENSION)
        _integer(self.height, "height", 1, MAX_IMAGE_DIMENSION)
        if self.width * self.height > MAX_IMAGE_PIXELS:
            raise ValueError("artifact pixel count exceeds its limit.")
        _relative_path(self.relative_path, "relative_path")
        if not re.fullmatch(
            rf"artifacts/[0-9]{{3}}-{self.sha256}\.jpg", self.relative_path
        ):
            raise ValueError("relative_path is not the canonical artifact path.")
        if not isinstance(self.source_artifact, SourceArtifactLink):
            raise ValueError("source_artifact must be a SourceArtifactLink.")
        self.source_artifact.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "artifact_key": self.artifact_key,
            "source_coin_id": self.source_coin_id,
            "role": self.role,
            "variant": self.variant,
            "relative_path": self.relative_path,
            "content_type": self.content_type,
            "byte_length": self.byte_length,
            "sha256": self.sha256,
            "width": self.width,
            "height": self.height,
            "source_artifact": self.source_artifact.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProcessedArtifactDescriptor":
        _closed(value, cls.FIELDS, "ProcessedArtifactDescriptor")
        result = cls(
            artifact_key=_exact_string(value["artifact_key"], "artifact_key"),
            source_coin_id=_exact_string(
                value["source_coin_id"], "source_coin_id"
            ),
            role=_exact_string(value["role"], "role"),
            variant=_exact_string(value["variant"], "variant"),
            relative_path=_exact_string(value["relative_path"], "relative_path"),
            content_type=_exact_string(value["content_type"], "content_type"),
            byte_length=value["byte_length"],
            sha256=_exact_string(value["sha256"], "sha256"),
            width=value["width"],
            height=value["height"],
            source_artifact=SourceArtifactLink.from_dict(value["source_artifact"]),
        )
        result.validate()
        return result


def _descriptor_order(value: ProcessedArtifactDescriptor) -> tuple[Any, ...]:
    return (
        value.source_coin_id,
        _ROLE_ORDER[value.role],
        _VARIANT_ORDER[value.variant],
        value.artifact_key,
    )


def artifact_inventory_sha256(
    artifacts: tuple[ProcessedArtifactDescriptor, ...],
) -> str:
    payload = canonical_json_bytes([item.to_dict() for item in artifacts])
    return hashlib.sha256(_INVENTORY_DOMAIN + payload).hexdigest()


@dataclass(frozen=True, slots=True)
class ProcessedSnapshotManifest:
    manifest_schema_version: str
    processed_snapshot_id: str
    workflow_execution_id: str
    ownership_token_sha256: str
    created_at: str
    source_package_sha256: str
    source_package_byte_length: int
    source_package_version: str
    artifact_count: int
    aggregate_byte_length: int
    artifact_inventory_sha256: str
    artifacts: tuple[ProcessedArtifactDescriptor, ...]

    FIELDS = frozenset(
        {
            "manifest_schema_version",
            "processed_snapshot_id",
            "workflow_execution_id",
            "ownership_token_sha256",
            "created_at",
            "source_package_sha256",
            "source_package_byte_length",
            "source_package_version",
            "artifact_count",
            "aggregate_byte_length",
            "artifact_inventory_sha256",
            "artifacts",
        }
    )

    def validate(self) -> None:
        if self.manifest_schema_version != PROCESSED_SNAPSHOT_MANIFEST_SCHEMA_VERSION:
            raise ValueError("processed manifest schema version is unsupported.")
        _uuid4(self.processed_snapshot_id, "processed_snapshot_id")
        _uuid4(self.workflow_execution_id, "workflow_execution_id")
        if self.processed_snapshot_id == self.workflow_execution_id:
            raise ValueError("operational identifiers must be distinct.")
        _sha(self.ownership_token_sha256, "ownership_token_sha256")
        _timestamp(self.created_at, "created_at")
        _sha(self.source_package_sha256, "source_package_sha256")
        _integer(
            self.source_package_byte_length,
            "source_package_byte_length",
            1,
            MAX_PROCESSED_ARTIFACT_BYTES,
        )
        if self.source_package_version != SUPPORTED_SCHEMA_VERSION:
            raise ValueError("source package version is unsupported.")
        if not isinstance(self.artifacts, tuple) or not self.artifacts:
            raise ValueError("artifacts must be a non-empty immutable tuple.")
        for artifact in self.artifacts:
            artifact.validate()
        if tuple(sorted(self.artifacts, key=_descriptor_order)) != self.artifacts:
            raise ValueError("artifacts are not in canonical order.")
        _integer(self.artifact_count, "artifact_count", 1, MAX_PROCESSED_ARTIFACTS)
        if self.artifact_count != len(self.artifacts):
            raise ValueError("artifact_count does not match artifacts.")
        total = sum(item.byte_length for item in self.artifacts)
        if self.aggregate_byte_length != total or total > MAX_PROCESSED_ARTIFACT_BYTES:
            raise ValueError("aggregate_byte_length does not match artifacts.")
        if self.artifact_inventory_sha256 != artifact_inventory_sha256(self.artifacts):
            raise ValueError("artifact_inventory_sha256 does not match artifacts.")
        if len({item.artifact_key.casefold() for item in self.artifacts}) != len(
            self.artifacts
        ):
            raise ValueError("artifact keys collide.")
        if len({item.relative_path.casefold() for item in self.artifacts}) != len(
            self.artifacts
        ):
            raise ValueError("artifact paths collide.")
        if len({(item.source_coin_id.casefold(), item.role) for item in self.artifacts}) != len(
            self.artifacts
        ):
            raise ValueError("source coin/role pairs collide.")
        for index, item in enumerate(self.artifacts):
            expected = f"artifacts/{index:03d}-{item.sha256}.jpg"
            if item.relative_path != expected:
                raise ValueError("artifact index path is not canonical.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "manifest_schema_version": self.manifest_schema_version,
            "processed_snapshot_id": self.processed_snapshot_id,
            "workflow_execution_id": self.workflow_execution_id,
            "ownership_token_sha256": self.ownership_token_sha256,
            "created_at": self.created_at,
            "source_package_sha256": self.source_package_sha256,
            "source_package_byte_length": self.source_package_byte_length,
            "source_package_version": self.source_package_version,
            "artifact_count": self.artifact_count,
            "aggregate_byte_length": self.aggregate_byte_length,
            "artifact_inventory_sha256": self.artifact_inventory_sha256,
            "artifacts": [item.to_dict() for item in self.artifacts],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProcessedSnapshotManifest":
        _closed(value, cls.FIELDS, "ProcessedSnapshotManifest")
        raw_artifacts = value["artifacts"]
        if not isinstance(raw_artifacts, list):
            raise ValueError("artifacts must be a JSON array.")
        result = cls(
            _exact_string(
                value["manifest_schema_version"], "manifest_schema_version"
            ),
            _exact_string(value["processed_snapshot_id"], "processed_snapshot_id"),
            _exact_string(value["workflow_execution_id"], "workflow_execution_id"),
            _exact_string(
                value["ownership_token_sha256"], "ownership_token_sha256"
            ),
            _exact_string(value["created_at"], "created_at"),
            _exact_string(value["source_package_sha256"], "source_package_sha256"),
            value["source_package_byte_length"],
            _exact_string(value["source_package_version"], "source_package_version"),
            value["artifact_count"],
            value["aggregate_byte_length"],
            _exact_string(
                value["artifact_inventory_sha256"],
                "artifact_inventory_sha256",
            ),
            tuple(ProcessedArtifactDescriptor.from_dict(item) for item in raw_artifacts),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class ProcessedArtifactObject:
    relative_path: str
    byte_length: int
    sha256: str
    parent_identity: NativeObjectIdentity
    object_identity: NativeObjectIdentity

    FIELDS = frozenset(
        {
            "relative_path",
            "byte_length",
            "sha256",
            "parent_identity",
            "object_identity",
        }
    )

    def validate(self) -> None:
        _relative_path(self.relative_path, "relative_path")
        _integer(self.byte_length, "byte_length", 1, MAX_PROCESSED_ARTIFACT_SIZE)
        _sha(self.sha256, "sha256")
        self.parent_identity.validate()
        self.object_identity.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "relative_path": self.relative_path,
            "byte_length": self.byte_length,
            "sha256": self.sha256,
            "parent_identity": self.parent_identity.to_dict(),
            "object_identity": self.object_identity.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProcessedArtifactObject":
        _closed(value, cls.FIELDS, "ProcessedArtifactObject")
        result = cls(
            _exact_string(value["relative_path"], "relative_path"),
            value["byte_length"],
            _exact_string(value["sha256"], "sha256"),
            _identity_from(value["parent_identity"], "parent_identity"),
            _identity_from(value["object_identity"], "object_identity"),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class ProcessedSnapshotOwner:
    owner_schema_version: str
    processed_snapshot_id: str
    workflow_execution_id: str
    ownership_token: str
    root_identity: NativeObjectIdentity
    created_at: str
    creation_state: str
    manifest_name: str
    completion_name: str
    lease_name: str
    source_package_sha256: str
    source_package_byte_length: int
    source_package_version: str
    planned_manifest_byte_length: int
    planned_manifest_sha256: str
    artifact_count: int
    aggregate_byte_length: int
    artifact_inventory_sha256: str
    planned_artifacts: tuple[ProcessedArtifactDescriptor, ...]

    FIELDS = frozenset(
        {
            "owner_schema_version",
            "processed_snapshot_id",
            "workflow_execution_id",
            "ownership_token",
            "root_identity",
            "created_at",
            "creation_state",
            "manifest_name",
            "completion_name",
            "lease_name",
            "source_package_sha256",
            "source_package_byte_length",
            "source_package_version",
            "planned_manifest_byte_length",
            "planned_manifest_sha256",
            "artifact_count",
            "aggregate_byte_length",
            "artifact_inventory_sha256",
            "planned_artifacts",
        }
    )

    def validate(self) -> None:
        if self.owner_schema_version != PROCESSED_SNAPSHOT_OWNER_SCHEMA_VERSION:
            raise ValueError("processed owner schema version is unsupported.")
        for value, name in (
            (self.processed_snapshot_id, "processed_snapshot_id"),
            (self.workflow_execution_id, "workflow_execution_id"),
            (self.ownership_token, "ownership_token"),
        ):
            _uuid4(value, name)
        if len(
            {
                self.processed_snapshot_id,
                self.workflow_execution_id,
                self.ownership_token,
            }
        ) != 3:
            raise ValueError("operational identifiers must be distinct.")
        self.root_identity.validate()
        _timestamp(self.created_at, "created_at")
        if self.creation_state != "COPYING":
            raise ValueError("creation_state must be COPYING.")
        if (self.manifest_name, self.completion_name, self.lease_name) != (
            "manifest.json",
            "complete.json",
            "lease.lock",
        ):
            raise ValueError("snapshot filenames are not canonical.")
        _sha(self.source_package_sha256, "source_package_sha256")
        _integer(
            self.source_package_byte_length,
            "source_package_byte_length",
            1,
            MAX_PROCESSED_ARTIFACT_BYTES,
        )
        if self.source_package_version != SUPPORTED_SCHEMA_VERSION:
            raise ValueError("source package version is unsupported.")
        _integer(
            self.planned_manifest_byte_length,
            "planned_manifest_byte_length",
            1,
            MAX_JSON_BYTES,
        )
        _sha(self.planned_manifest_sha256, "planned_manifest_sha256")
        manifest = ProcessedSnapshotManifest(
            PROCESSED_SNAPSHOT_MANIFEST_SCHEMA_VERSION,
            self.processed_snapshot_id,
            self.workflow_execution_id,
            hashlib.sha256(self.ownership_token.encode("utf-8")).hexdigest(),
            self.created_at,
            self.source_package_sha256,
            self.source_package_byte_length,
            self.source_package_version,
            self.artifact_count,
            self.aggregate_byte_length,
            self.artifact_inventory_sha256,
            self.planned_artifacts,
        )
        manifest.validate()
        manifest_bytes = canonical_json_bytes(manifest.to_dict())
        if (
            self.planned_manifest_byte_length != len(manifest_bytes)
            or self.planned_manifest_sha256
            != hashlib.sha256(manifest_bytes).hexdigest()
        ):
            raise ValueError("planned manifest commitment does not match.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "owner_schema_version": self.owner_schema_version,
            "processed_snapshot_id": self.processed_snapshot_id,
            "workflow_execution_id": self.workflow_execution_id,
            "ownership_token": self.ownership_token,
            "root_identity": self.root_identity.to_dict(),
            "created_at": self.created_at,
            "creation_state": self.creation_state,
            "manifest_name": self.manifest_name,
            "completion_name": self.completion_name,
            "lease_name": self.lease_name,
            "source_package_sha256": self.source_package_sha256,
            "source_package_byte_length": self.source_package_byte_length,
            "source_package_version": self.source_package_version,
            "planned_manifest_byte_length": self.planned_manifest_byte_length,
            "planned_manifest_sha256": self.planned_manifest_sha256,
            "artifact_count": self.artifact_count,
            "aggregate_byte_length": self.aggregate_byte_length,
            "artifact_inventory_sha256": self.artifact_inventory_sha256,
            "planned_artifacts": [item.to_dict() for item in self.planned_artifacts],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProcessedSnapshotOwner":
        _closed(value, cls.FIELDS, "ProcessedSnapshotOwner")
        raw_artifacts = value["planned_artifacts"]
        if not isinstance(raw_artifacts, list):
            raise ValueError("planned_artifacts must be a JSON array.")
        result = cls(
            _exact_string(value["owner_schema_version"], "owner_schema_version"),
            _exact_string(value["processed_snapshot_id"], "processed_snapshot_id"),
            _exact_string(value["workflow_execution_id"], "workflow_execution_id"),
            _exact_string(value["ownership_token"], "ownership_token"),
            _identity_from(value["root_identity"], "root_identity"),
            _exact_string(value["created_at"], "created_at"),
            _exact_string(value["creation_state"], "creation_state"),
            _exact_string(value["manifest_name"], "manifest_name"),
            _exact_string(value["completion_name"], "completion_name"),
            _exact_string(value["lease_name"], "lease_name"),
            _exact_string(value["source_package_sha256"], "source_package_sha256"),
            value["source_package_byte_length"],
            _exact_string(value["source_package_version"], "source_package_version"),
            value["planned_manifest_byte_length"],
            _exact_string(
                value["planned_manifest_sha256"], "planned_manifest_sha256"
            ),
            value["artifact_count"],
            value["aggregate_byte_length"],
            _exact_string(
                value["artifact_inventory_sha256"],
                "artifact_inventory_sha256",
            ),
            tuple(
                ProcessedArtifactDescriptor.from_dict(item)
                for item in raw_artifacts
            ),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class ProcessedSnapshotCompletion:
    completion_schema_version: str
    processed_snapshot_id: str
    workflow_execution_id: str
    ownership_token_sha256: str
    root_identity: NativeObjectIdentity
    owner_identity: NativeObjectIdentity
    lease_identity: NativeObjectIdentity
    artifacts_directory_identity: NativeObjectIdentity
    manifest_identity: NativeObjectIdentity
    owner_byte_length: int
    owner_sha256: str
    manifest_byte_length: int
    manifest_sha256: str
    artifact_count: int
    aggregate_byte_length: int
    artifact_inventory_sha256: str
    artifact_objects: tuple[ProcessedArtifactObject, ...]
    sealed_at: str

    FIELDS = frozenset(
        {
            "completion_schema_version",
            "processed_snapshot_id",
            "workflow_execution_id",
            "ownership_token_sha256",
            "root_identity",
            "owner_identity",
            "lease_identity",
            "artifacts_directory_identity",
            "manifest_identity",
            "owner_byte_length",
            "owner_sha256",
            "manifest_byte_length",
            "manifest_sha256",
            "artifact_count",
            "aggregate_byte_length",
            "artifact_inventory_sha256",
            "artifact_objects",
            "sealed_at",
        }
    )

    def validate(self) -> None:
        if (
            self.completion_schema_version
            != PROCESSED_SNAPSHOT_COMPLETION_SCHEMA_VERSION
        ):
            raise ValueError("processed completion schema version is unsupported.")
        _uuid4(self.processed_snapshot_id, "processed_snapshot_id")
        _uuid4(self.workflow_execution_id, "workflow_execution_id")
        _sha(self.ownership_token_sha256, "ownership_token_sha256")
        for identity in (
            self.root_identity,
            self.owner_identity,
            self.lease_identity,
            self.artifacts_directory_identity,
            self.manifest_identity,
        ):
            identity.validate()
        _integer(self.owner_byte_length, "owner_byte_length", 1, MAX_JSON_BYTES)
        _sha(self.owner_sha256, "owner_sha256")
        _integer(
            self.manifest_byte_length, "manifest_byte_length", 1, MAX_JSON_BYTES
        )
        _sha(self.manifest_sha256, "manifest_sha256")
        _integer(self.artifact_count, "artifact_count", 1, MAX_PROCESSED_ARTIFACTS)
        _integer(
            self.aggregate_byte_length,
            "aggregate_byte_length",
            1,
            MAX_PROCESSED_ARTIFACT_BYTES,
        )
        if (
            not isinstance(self.artifact_objects, tuple)
            or len(self.artifact_objects) != self.artifact_count
        ):
            raise ValueError("artifact_objects do not match artifact_count.")
        for artifact in self.artifact_objects:
            artifact.validate()
        if sum(item.byte_length for item in self.artifact_objects) != self.aggregate_byte_length:
            raise ValueError("aggregate_byte_length does not match artifact objects.")
        _sha(self.artifact_inventory_sha256, "artifact_inventory_sha256")
        _timestamp(self.sealed_at, "sealed_at")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "completion_schema_version": self.completion_schema_version,
            "processed_snapshot_id": self.processed_snapshot_id,
            "workflow_execution_id": self.workflow_execution_id,
            "ownership_token_sha256": self.ownership_token_sha256,
            "root_identity": self.root_identity.to_dict(),
            "owner_identity": self.owner_identity.to_dict(),
            "lease_identity": self.lease_identity.to_dict(),
            "artifacts_directory_identity": self.artifacts_directory_identity.to_dict(),
            "manifest_identity": self.manifest_identity.to_dict(),
            "owner_byte_length": self.owner_byte_length,
            "owner_sha256": self.owner_sha256,
            "manifest_byte_length": self.manifest_byte_length,
            "manifest_sha256": self.manifest_sha256,
            "artifact_count": self.artifact_count,
            "aggregate_byte_length": self.aggregate_byte_length,
            "artifact_inventory_sha256": self.artifact_inventory_sha256,
            "artifact_objects": [item.to_dict() for item in self.artifact_objects],
            "sealed_at": self.sealed_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProcessedSnapshotCompletion":
        _closed(value, cls.FIELDS, "ProcessedSnapshotCompletion")
        raw_objects = value["artifact_objects"]
        if not isinstance(raw_objects, list):
            raise ValueError("artifact_objects must be a JSON array.")
        result = cls(
            _exact_string(
                value["completion_schema_version"], "completion_schema_version"
            ),
            _exact_string(value["processed_snapshot_id"], "processed_snapshot_id"),
            _exact_string(value["workflow_execution_id"], "workflow_execution_id"),
            _exact_string(
                value["ownership_token_sha256"], "ownership_token_sha256"
            ),
            _identity_from(value["root_identity"], "root_identity"),
            _identity_from(value["owner_identity"], "owner_identity"),
            _identity_from(value["lease_identity"], "lease_identity"),
            _identity_from(
                value["artifacts_directory_identity"],
                "artifacts_directory_identity",
            ),
            _identity_from(value["manifest_identity"], "manifest_identity"),
            value["owner_byte_length"],
            _exact_string(value["owner_sha256"], "owner_sha256"),
            value["manifest_byte_length"],
            _exact_string(value["manifest_sha256"], "manifest_sha256"),
            value["artifact_count"],
            value["aggregate_byte_length"],
            _exact_string(
                value["artifact_inventory_sha256"],
                "artifact_inventory_sha256",
            ),
            tuple(ProcessedArtifactObject.from_dict(item) for item in raw_objects),
            _exact_string(value["sealed_at"], "sealed_at"),
        )
        result.validate()
        return result


class ProcessedSnapshotHandle:
    """One active advisory lease over an independently verifiable snapshot."""

    def __init__(
        self,
        service: "ProcessedArtifactSnapshotService",
        manifest: ProcessedSnapshotManifest,
        owner: ProcessedSnapshotOwner,
        completion: ProcessedSnapshotCompletion,
        root_handle: PlainDirectoryHandle,
        artifacts_handle: PlainDirectoryHandle,
        owner_handle: BinaryIO,
        lease_handle: BinaryIO,
        artifact_handles: tuple[BinaryIO, ...],
        manifest_handle: BinaryIO,
        completion_handle: BinaryIO,
        snapshots_parent_handle: PlainDirectoryHandle,
    ) -> None:
        self._service = service
        self.manifest = manifest
        self.owner = owner
        self.completion = completion
        self._root_handle = root_handle
        self._artifacts_handle = artifacts_handle
        self._owner_handle = owner_handle
        self._lease_handle = lease_handle
        self._artifact_handles = artifact_handles
        self._manifest_handle = manifest_handle
        self._completion_handle = completion_handle
        self._snapshots_parent_handle = snapshots_parent_handle
        self._closed = False
        self._cleaned = False

    @property
    def is_active(self) -> bool:
        return not self._closed and not self._cleaned

    def validate(self) -> None:
        self._service.validate_snapshot(self)

    @contextmanager
    def open_artifact(self, index: int) -> Iterator[BinaryIO]:
        self.validate()
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(
            self._artifact_handles
        ):
            raise IndexError("processed artifact index is invalid.")
        handle = self._artifact_handles[index]
        handle.seek(0)
        try:
            yield handle
        finally:
            self.validate()

    def cleanup(self) -> None:
        self._service.cleanup_snapshot(self)

    def close(self) -> None:
        self._service.preserve_snapshot(self)


class ProcessedArtifactSnapshotService:
    """Seal selected workflow bytes into a separate immutable snapshot."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        clock: Clock = _now,
        identifier_factory: IdentifierFactory = _identifier,
        chunk_size: int = 1024 * 1024,
    ) -> None:
        if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size < 1:
            raise ValueError("chunk_size must be a positive integer.")
        self._root = Path(root).absolute()
        self._clock = clock
        self._identifier_factory = identifier_factory
        self._chunk_size = chunk_size

    @property
    def root(self) -> Path:
        return self._root

    def seal(
        self,
        prepared: PreparedArtifactSet,
        package: ValidatedCapturePackage,
        *,
        import_lock: PackageImportLock,
        workflow_execution_id: str | None = None,
    ) -> ProcessedSnapshotHandle:
        """Accept the handoff once and durably seal its exact selected bytes."""

        require_verified_import_lock(import_lock)
        if not isinstance(prepared, PreparedArtifactSet):
            raise ValueError("prepared must be a PreparedArtifactSet.")
        if not isinstance(package, ValidatedCapturePackage):
            raise ValueError("package must be a ValidatedCapturePackage.")
        try:
            prepared.verify()
        except (OSError, RuntimeError, ValueError) as error:
            raise SnapshotFailed(error) from error
        if {
            (item.source_coin_id, item.role)
            for item in prepared.descriptors
        } != {(item.coin_id, item.role.value) for item in package.media}:
            raise ValueError(
                "Prepared artifacts do not map one-to-one to package media."
            )
        claimed = prepared.claim()
        snapshot_path: Path | None = None
        state: dict[str, Any] = {"created": False, "handles": []}
        try:
            snapshot_id = self._identifier_factory()
            execution_id = workflow_execution_id or self._identifier_factory()
            ownership_token = self._identifier_factory()
            for value, name in (
                (snapshot_id, "processed_snapshot_id"),
                (execution_id, "workflow_execution_id"),
                (ownership_token, "ownership_token"),
            ):
                _uuid4(value, name)
            if len({snapshot_id, execution_id, ownership_token}) != 3:
                raise ValueError("operational identifiers must be distinct.")
            created_at = self._clock()
            _timestamp(created_at, "created_at")
            snapshot_path = self._root / snapshot_id
            claimed.verify()
            descriptors, source_payloads = self._build_descriptors(
                claimed.descriptors, claimed, package
            )
            ownership_digest = hashlib.sha256(
                ownership_token.encode("utf-8")
            ).hexdigest()
            manifest = ProcessedSnapshotManifest(
                PROCESSED_SNAPSHOT_MANIFEST_SCHEMA_VERSION,
                snapshot_id,
                execution_id,
                ownership_digest,
                created_at,
                package.package_sha256,
                package.package_byte_length,
                package.manifest.package_version,
                len(descriptors),
                sum(item.byte_length for item in descriptors),
                artifact_inventory_sha256(descriptors),
                descriptors,
            )
            manifest_bytes = canonical_json_bytes(manifest.to_dict())
            ensure_plain_directory(self._root)
            snapshots_parent_handle = open_plain_directory_handle(self._root)
            state["snapshots_parent_handle"] = snapshots_parent_handle
            require_verified_import_lock(import_lock)
            root_handle = create_plain_child_directory(
                snapshots_parent_handle, snapshot_id
            )
            state["created"] = True
            state["root_handle"] = root_handle
            sync_directory(snapshots_parent_handle)
            owner = ProcessedSnapshotOwner(
                PROCESSED_SNAPSHOT_OWNER_SCHEMA_VERSION,
                snapshot_id,
                execution_id,
                ownership_token,
                _native(root_handle.identity),
                created_at,
                "COPYING",
                "manifest.json",
                "complete.json",
                "lease.lock",
                package.package_sha256,
                package.package_byte_length,
                package.manifest.package_version,
                len(manifest_bytes),
                hashlib.sha256(manifest_bytes).hexdigest(),
                manifest.artifact_count,
                manifest.aggregate_byte_length,
                manifest.artifact_inventory_sha256,
                manifest.artifacts,
            )
            owner_bytes = canonical_json_bytes(owner.to_dict())
            owner_handle = self._write_exact(
                snapshot_path / "owner.json",
                owner_bytes,
                state,
                root_handle,
            )
            sync_directory(root_handle)
            lease_path = snapshot_path / "lease.lock"
            lease_writable = open_exclusive_child_binary(
                root_handle, "lease.lock"
            )
            state["handles"].append((lease_writable, lease_path))
            lease_writable.flush()
            os.fsync(lease_writable.fileno())
            lease_handle = self._reopen_readonly(
                root_handle, lease_writable, lease_path, state
            )
            sync_directory(root_handle)
            self._acquire_zero_byte_lease(lease_handle)
            state["lease_locked"] = True
            require_verified_import_lock(import_lock)
            artifacts_path = snapshot_path / "artifacts"
            artifacts_handle = create_plain_child_directory(
                root_handle, "artifacts"
            )
            state["artifacts_handle"] = artifacts_handle
            sync_directory(root_handle)
            artifact_handles = []
            artifact_objects = []
            for descriptor, source_handle in zip(descriptors, source_payloads):
                target_path = snapshot_path / Path(descriptor.relative_path)
                target = open_exclusive_child_binary(
                    artifacts_handle, target_path.name
                )
                state["handles"].append((target, target_path))
                digest = hashlib.sha256()
                total = 0
                source_handle.seek(0)
                while True:
                    chunk = source_handle.read(self._chunk_size)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > descriptor.byte_length:
                        raise SnapshotFailed()
                    target.write(chunk)
                    digest.update(chunk)
                target.flush()
                os.fsync(target.fileno())
                if total != descriptor.byte_length or digest.hexdigest() != descriptor.sha256:
                    raise SnapshotFailed()
                if not handle_matches_path(target, target_path):
                    raise SnapshotFailed()
                target = self._reopen_readonly(
                    artifacts_handle, target, target_path, state
                )
                artifact_handles.append(target)
                artifact_objects.append(
                    ProcessedArtifactObject(
                        descriptor.relative_path,
                        descriptor.byte_length,
                        descriptor.sha256,
                        _native(artifacts_handle.identity),
                        _native(handle_object_identity(target)),
                    )
                )
                claimed.verify()
            sync_directory(artifacts_handle)
            manifest_handle = self._write_exact(
                snapshot_path / "manifest.json",
                manifest_bytes,
                state,
                root_handle,
            )
            sync_directory(root_handle)
            self._verify_precompletion(
                snapshot_path,
                snapshots_parent_handle,
                root_handle,
                artifacts_handle,
                owner,
                manifest,
                owner_bytes,
                manifest_bytes,
                owner_handle,
                lease_handle,
                tuple(artifact_handles),
                manifest_handle,
                tuple(artifact_objects),
            )
            completion = ProcessedSnapshotCompletion(
                PROCESSED_SNAPSHOT_COMPLETION_SCHEMA_VERSION,
                snapshot_id,
                execution_id,
                ownership_digest,
                _native(root_handle.identity),
                _native(handle_object_identity(owner_handle)),
                _native(handle_object_identity(lease_handle)),
                _native(artifacts_handle.identity),
                _native(handle_object_identity(manifest_handle)),
                len(owner_bytes),
                hashlib.sha256(owner_bytes).hexdigest(),
                len(manifest_bytes),
                hashlib.sha256(manifest_bytes).hexdigest(),
                manifest.artifact_count,
                manifest.aggregate_byte_length,
                manifest.artifact_inventory_sha256,
                tuple(artifact_objects),
                self._clock(),
            )
            completion_bytes = canonical_json_bytes(completion.to_dict())
            completion_handle = self._write_exact(
                snapshot_path / "complete.json",
                completion_bytes,
                state,
                root_handle,
            )
            sync_directory(root_handle)
            handle = ProcessedSnapshotHandle(
                self,
                manifest,
                owner,
                completion,
                root_handle,
                artifacts_handle,
                owner_handle,
                lease_handle,
                tuple(artifact_handles),
                manifest_handle,
                completion_handle,
                snapshots_parent_handle,
            )
            self.validate_snapshot(handle)
            state["transferred"] = True
            return handle
        except Exception as error:
            try:
                if snapshot_path is not None:
                    self._cleanup_failed(snapshot_path, state)
            except SnapshotRecoveryRequired:
                raise
            if isinstance(error, SnapshotFailed):
                raise
            raise SnapshotFailed(error) from error
        finally:
            claimed.close()

    def open_snapshot(
        self,
        processed_snapshot_id: str,
        *,
        import_lock: PackageImportLock,
        wait_seconds: float = 0.0,
    ) -> ProcessedSnapshotHandle:
        """Open and verify one complete snapshot through held identities."""

        require_verified_import_lock(import_lock)
        _uuid4(processed_snapshot_id, "processed_snapshot_id")
        wait = self._validate_wait(wait_seconds)
        handles: list[BinaryIO] = []
        directories: list[PlainDirectoryHandle] = []
        try:
            parent = open_plain_directory_handle(self._root)
            directories.append(parent)
            root = open_plain_child_directory(parent, processed_snapshot_id)
            directories.append(root)
            owner_handle = open_plain_child_file_readonly(root, "owner.json")
            handles.append(owner_handle)
            owner = self._read_owner(owner_handle)
            if (
                owner.processed_snapshot_id != processed_snapshot_id
                or owner.root_identity != _native(root.identity)
            ):
                raise SnapshotRecoveryRequired()
            lease_handle = open_plain_child_file_readonly(root, "lease.lock")
            handles.append(lease_handle)
            if os.fstat(lease_handle.fileno()).st_size != 0:
                raise SnapshotRecoveryRequired()
            self._acquire_zero_byte_lease_bounded(lease_handle, wait)
            artifacts = open_plain_child_directory(root, "artifacts")
            directories.append(artifacts)
            manifest_handle = open_plain_child_file_readonly(root, "manifest.json")
            handles.append(manifest_handle)
            manifest = self._read_manifest(manifest_handle)
            completion_handle = open_plain_child_file_readonly(root, "complete.json")
            handles.append(completion_handle)
            completion = self._read_completion(completion_handle)
            artifact_handles = []
            for descriptor in manifest.artifacts:
                artifact = open_plain_child_file_readonly(
                    artifacts, Path(descriptor.relative_path).name
                )
                handles.append(artifact)
                artifact_handles.append(artifact)
            result = ProcessedSnapshotHandle(
                self,
                manifest,
                owner,
                completion,
                root,
                artifacts,
                owner_handle,
                lease_handle,
                tuple(artifact_handles),
                manifest_handle,
                completion_handle,
                parent,
            )
            result.validate()
            handles.clear()
            directories.clear()
            return result
        except SnapshotRecoveryRequired:
            raise
        except Exception as error:
            raise SnapshotRecoveryRequired(error) from error
        finally:
            for handle in handles:
                if not handle.closed:
                    handle.close()
            for directory in reversed(directories):
                directory.close()

    def cleanup_orphaned_snapshots(
        self,
        referenced_snapshot_ids: tuple[str, ...],
        *,
        import_lock: PackageImportLock,
        wait_seconds: float = 0.0,
    ) -> tuple[str, ...]:
        """Remove only proven pre-journal processed snapshots."""

        require_verified_import_lock(import_lock)
        wait = self._validate_wait(wait_seconds)
        if not isinstance(referenced_snapshot_ids, tuple):
            raise ValueError("referenced_snapshot_ids must be an immutable tuple.")
        references = set(referenced_snapshot_ids)
        for value in references:
            _uuid4(value, "referenced_snapshot_id")
        if not self._root.exists():
            return ()
        parent = open_plain_directory_handle(self._root)
        removed = []
        try:
            names = sorted(item.name for item in self._root.iterdir())
            if not parent.verify_path():
                raise SnapshotRecoveryRequired()
            for name in names:
                require_verified_import_lock(import_lock)
                _uuid4(name, "processed_snapshot_id")
                if name in references:
                    continue
                path = self._root / name
                if is_link_or_reparse(path) or not path.is_dir():
                    raise SnapshotRecoveryRequired()
                try:
                    complete = self.open_snapshot(
                        name,
                        import_lock=import_lock,
                        wait_seconds=wait,
                    )
                except SnapshotRecoveryRequired:
                    self._cleanup_incomplete_orphan(
                        parent, name, wait_seconds=wait
                    )
                else:
                    complete.cleanup()
                removed.append(name)
            return tuple(removed)
        except SnapshotRecoveryRequired:
            raise
        except (OSError, ValueError) as error:
            raise SnapshotRecoveryRequired(error) from error
        finally:
            parent.close()

    def _cleanup_incomplete_orphan(
        self,
        parent: PlainDirectoryHandle,
        snapshot_id: str,
        *,
        wait_seconds: float,
    ) -> None:
        root = open_plain_child_directory(parent, snapshot_id)
        handles: list[tuple[BinaryIO, Path]] = []
        artifacts: PlainDirectoryHandle | None = None
        try:
            root_path = root.path
            names = {item.name for item in root_path.iterdir()}
            allowed = {
                "owner.json",
                "lease.lock",
                "artifacts",
                "manifest.json",
                "complete.json",
            }
            if "owner.json" not in names or not names <= allowed:
                raise SnapshotRecoveryRequired()
            owner_handle = open_plain_child_file_readonly(root, "owner.json")
            handles.append((owner_handle, root_path / "owner.json"))
            owner = self._read_owner(owner_handle)
            if (
                owner.processed_snapshot_id != snapshot_id
                or owner.root_identity != _native(root.identity)
            ):
                raise SnapshotRecoveryRequired()
            lease_handle = None
            if "lease.lock" in names:
                lease_handle = open_plain_child_file_readonly(root, "lease.lock")
                handles.append((lease_handle, root_path / "lease.lock"))
                if os.fstat(lease_handle.fileno()).st_size != 0:
                    raise SnapshotRecoveryRequired()
                self._acquire_zero_byte_lease_bounded(
                    lease_handle, wait_seconds
                )
            if "artifacts" in names:
                artifacts = open_plain_child_directory(root, "artifacts")
                planned = {
                    Path(item.relative_path).name
                    for item in owner.planned_artifacts
                }
                actual = {item.name for item in artifacts.path.iterdir()}
                if not actual <= planned:
                    raise SnapshotRecoveryRequired()
                for name in sorted(actual):
                    artifact = open_plain_child_file_readonly(artifacts, name)
                    handles.append((artifact, artifacts.path / name))
            for name in ("manifest.json", "complete.json"):
                if name in names:
                    candidate = open_plain_child_file_readonly(root, name)
                    handles.append((candidate, root_path / name))
                    if name == "manifest.json":
                        try:
                            manifest = self._read_manifest(candidate)
                        except SnapshotRecoveryRequired:
                            pass
                        else:
                            manifest_bytes = canonical_json_bytes(
                                manifest.to_dict()
                            )
                            if (
                                len(manifest_bytes)
                                != owner.planned_manifest_byte_length
                                or hashlib.sha256(manifest_bytes).hexdigest()
                                != owner.planned_manifest_sha256
                                or manifest.artifacts
                                != owner.planned_artifacts
                            ):
                                raise SnapshotRecoveryRequired()
                    else:
                        try:
                            self._read_completion(candidate)
                        except SnapshotRecoveryRequired:
                            pass
                        else:
                            raise SnapshotRecoveryRequired()
            for handle, path in reversed(handles):
                if not handle_matches_path(handle, path):
                    raise SnapshotRecoveryRequired()
                delete_open_file(handle, path)
                handle.close()
                sync_directory(
                    artifacts
                    if artifacts is not None and path.parent == artifacts.path
                    else root
                )
            if artifacts is not None:
                if any(artifacts.path.iterdir()) or not artifacts.verify_path():
                    raise SnapshotRecoveryRequired()
                artifacts.path.rmdir()
                artifacts.close()
                sync_directory(root)
            if any(root.path.iterdir()) or not root.verify_path():
                raise SnapshotRecoveryRequired()
            root.path.rmdir()
            root.close()
            sync_directory(parent)
        except SnapshotRecoveryRequired:
            raise
        except Exception as error:
            raise SnapshotRecoveryRequired(error) from error
        finally:
            for handle, _path in handles:
                if not handle.closed:
                    handle.close()
            if artifacts is not None:
                artifacts.close()
            root.close()

    @staticmethod
    def _validate_wait(value: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("wait_seconds must be numeric.")
        try:
            result = float(value)
        except OverflowError as error:
            raise ValueError("wait_seconds is outside its supported range.") from error
        if not math.isfinite(result) or not 0 <= result <= MAX_LOCK_WAIT_SECONDS:
            raise ValueError("wait_seconds is outside its supported range.")
        return result

    def _acquire_zero_byte_lease_bounded(
        self, handle: BinaryIO, wait_seconds: float
    ) -> None:
        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                self._acquire_zero_byte_lease(handle)
                return
            except BlockingIOError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SnapshotRecoveryRequired()
                time.sleep(min(0.05, remaining))

    @staticmethod
    def _read_control_object(handle: BinaryIO, context: str) -> tuple[bytes, dict[str, Any]]:
        handle.seek(0)
        payload = handle.read(MAX_JSON_BYTES + 1)
        if not payload or len(payload) > MAX_JSON_BYTES:
            raise SnapshotRecoveryRequired()
        return payload, parse_bounded_json_object(payload, context)

    def _read_owner(self, handle: BinaryIO) -> ProcessedSnapshotOwner:
        try:
            payload, value = self._read_control_object(handle, "processed owner")
            result = ProcessedSnapshotOwner.from_dict(value)
            if canonical_json_bytes(result.to_dict()) != payload:
                raise SnapshotRecoveryRequired()
            return result
        except SnapshotRecoveryRequired:
            raise
        except (OSError, ValueError) as error:
            raise SnapshotRecoveryRequired(error) from error

    def _read_manifest(self, handle: BinaryIO) -> ProcessedSnapshotManifest:
        try:
            payload, value = self._read_control_object(handle, "processed manifest")
            result = ProcessedSnapshotManifest.from_dict(value)
            if canonical_json_bytes(result.to_dict()) != payload:
                raise SnapshotRecoveryRequired()
            return result
        except SnapshotRecoveryRequired:
            raise
        except (OSError, ValueError) as error:
            raise SnapshotRecoveryRequired(error) from error

    def _read_completion(self, handle: BinaryIO) -> ProcessedSnapshotCompletion:
        try:
            payload, value = self._read_control_object(
                handle, "processed completion"
            )
            result = ProcessedSnapshotCompletion.from_dict(value)
            if canonical_json_bytes(result.to_dict()) != payload:
                raise SnapshotRecoveryRequired()
            return result
        except SnapshotRecoveryRequired:
            raise
        except (OSError, ValueError) as error:
            raise SnapshotRecoveryRequired(error) from error

    def validate_snapshot(self, handle: ProcessedSnapshotHandle) -> None:
        if not isinstance(handle, ProcessedSnapshotHandle) or handle._service is not self:
            raise SnapshotRecoveryRequired()
        if not handle.is_active:
            raise SnapshotRecoveryRequired()
        try:
            root = self._root / handle.manifest.processed_snapshot_id
            if (
                not handle._snapshots_parent_handle.verify_path()
                or handle._snapshots_parent_handle.path != self._root
                or not handle._root_handle.verify_path()
                or handle._root_handle.path != root
                or handle._root_handle.identity[0]
                != handle._snapshots_parent_handle.identity[0]
            ):
                raise SnapshotRecoveryRequired()
            expected_root_names = {
                "owner.json",
                "lease.lock",
                "artifacts",
                "manifest.json",
                "complete.json",
            }
            expected_artifact_names = {
                Path(item.relative_path).name
                for item in handle.manifest.artifacts
            }
            self._verify_inventory(
                root,
                expected_root_names,
                root / "artifacts",
                expected_artifact_names,
            )
            if (
                os.fstat(handle._lease_handle.fileno()).st_size != 0
                or os.fstat(handle._lease_handle.fileno()).st_nlink != 1
            ):
                raise SnapshotRecoveryRequired()
            bindings = (
                (handle._owner_handle, root / "owner.json"),
                (handle._lease_handle, root / "lease.lock"),
                (handle._manifest_handle, root / "manifest.json"),
                (handle._completion_handle, root / "complete.json"),
            )
            if any(not handle_matches_path(item, path) for item, path in bindings):
                raise SnapshotRecoveryRequired()
            for item, _path in bindings:
                require_dense_regular_handle(item)
                if os.fstat(item.fileno()).st_nlink != 1:
                    raise SnapshotRecoveryRequired()
            if not handle._artifacts_handle.verify_path():
                raise SnapshotRecoveryRequired()
            owner_bytes = self._read_exact(
                handle._owner_handle, handle.completion.owner_byte_length
            )
            manifest_bytes = self._read_exact(
                handle._manifest_handle, handle.completion.manifest_byte_length
            )
            expected_completion_bytes = canonical_json_bytes(
                handle.completion.to_dict()
            )
            completion_bytes = self._read_exact(
                handle._completion_handle, len(expected_completion_bytes)
            )
            if (
                hashlib.sha256(owner_bytes).hexdigest() != handle.completion.owner_sha256
                or hashlib.sha256(manifest_bytes).hexdigest()
                != handle.completion.manifest_sha256
                or canonical_json_bytes(handle.owner.to_dict()) != owner_bytes
                or canonical_json_bytes(handle.manifest.to_dict()) != manifest_bytes
                or completion_bytes != expected_completion_bytes
            ):
                raise SnapshotRecoveryRequired()
            if (
                handle.owner.processed_snapshot_id
                != handle.manifest.processed_snapshot_id
                or handle.owner.workflow_execution_id
                != handle.manifest.workflow_execution_id
                or handle.completion.processed_snapshot_id
                != handle.manifest.processed_snapshot_id
                or handle.completion.workflow_execution_id
                != handle.manifest.workflow_execution_id
                or handle.completion.root_identity
                != _native(handle._root_handle.identity)
                or handle.completion.owner_identity
                != _native(handle_object_identity(handle._owner_handle))
                or handle.completion.lease_identity
                != _native(handle_object_identity(handle._lease_handle))
                or handle.completion.artifacts_directory_identity
                != _native(handle._artifacts_handle.identity)
                or handle.completion.manifest_identity
                != _native(handle_object_identity(handle._manifest_handle))
                or handle.owner.root_identity
                != _native(handle._root_handle.identity)
                or handle.owner.planned_manifest_byte_length
                != len(manifest_bytes)
                or handle.owner.planned_manifest_sha256
                != hashlib.sha256(manifest_bytes).hexdigest()
                or handle.owner.planned_artifacts != handle.manifest.artifacts
                or handle.owner.artifact_count
                != handle.manifest.artifact_count
                or handle.owner.aggregate_byte_length
                != handle.manifest.aggregate_byte_length
                or handle.owner.artifact_inventory_sha256
                != handle.manifest.artifact_inventory_sha256
                or handle.completion.ownership_token_sha256
                != hashlib.sha256(
                    handle.owner.ownership_token.encode("utf-8")
                ).hexdigest()
                or handle.completion.artifact_count
                != handle.manifest.artifact_count
                or handle.completion.aggregate_byte_length
                != handle.manifest.aggregate_byte_length
                or handle.completion.artifact_inventory_sha256
                != handle.manifest.artifact_inventory_sha256
            ):
                raise SnapshotRecoveryRequired()
            for descriptor, receipt, artifact_handle in zip(
                handle.manifest.artifacts,
                handle.completion.artifact_objects,
                handle._artifact_handles,
            ):
                path = root / Path(descriptor.relative_path)
                if (
                    receipt.relative_path != descriptor.relative_path
                    or receipt.byte_length != descriptor.byte_length
                    or receipt.sha256 != descriptor.sha256
                    or receipt.parent_identity
                    != _native(handle._artifacts_handle.identity)
                    or receipt.object_identity
                    != _native(handle_object_identity(artifact_handle))
                    or not handle_matches_path(artifact_handle, path)
                ):
                    raise SnapshotRecoveryRequired()
                require_dense_regular_handle(artifact_handle)
                if os.fstat(artifact_handle.fileno()).st_nlink != 1:
                    raise SnapshotRecoveryRequired()
                payload = self._read_exact(artifact_handle, descriptor.byte_length)
                if hashlib.sha256(payload).hexdigest() != descriptor.sha256:
                    raise SnapshotRecoveryRequired()
                width, height = self._jpeg_dimensions(payload)
                if (width, height) != (descriptor.width, descriptor.height):
                    raise SnapshotRecoveryRequired()
            handle.manifest.validate()
            handle.completion.validate()
            self._verify_inventory(
                root,
                expected_root_names,
                root / "artifacts",
                expected_artifact_names,
            )
            if (
                not handle._snapshots_parent_handle.verify_path()
                or not handle._root_handle.verify_path()
                or not handle._artifacts_handle.verify_path()
            ):
                raise SnapshotRecoveryRequired()
        except SnapshotRecoveryRequired:
            raise
        except (OSError, ValueError) as error:
            raise SnapshotRecoveryRequired(error) from error

    def _verify_precompletion(
        self,
        root: Path,
        snapshots_parent: PlainDirectoryHandle,
        root_handle: PlainDirectoryHandle,
        artifacts_handle: PlainDirectoryHandle,
        owner: ProcessedSnapshotOwner,
        manifest: ProcessedSnapshotManifest,
        owner_bytes: bytes,
        manifest_bytes: bytes,
        owner_handle: BinaryIO,
        lease_handle: BinaryIO,
        artifact_handles: tuple[BinaryIO, ...],
        manifest_handle: BinaryIO,
        artifact_objects: tuple[ProcessedArtifactObject, ...],
    ) -> None:
        """Prove the exact sealed inventory before publishing completion."""

        try:
            expected_root_names = {
                "owner.json",
                "lease.lock",
                "artifacts",
                "manifest.json",
            }
            expected_artifact_names = {
                Path(item.relative_path).name for item in manifest.artifacts
            }
            self._verify_inventory(
                root,
                expected_root_names,
                root / "artifacts",
                expected_artifact_names,
            )
            if (
                not snapshots_parent.verify_path()
                or snapshots_parent.path != self._root
                or not root_handle.verify_path()
                or root_handle.path != root
                or not artifacts_handle.verify_path()
                or root_handle.identity[0] != snapshots_parent.identity[0]
                or artifacts_handle.identity[0] != root_handle.identity[0]
                or os.fstat(lease_handle.fileno()).st_size != 0
                or os.fstat(lease_handle.fileno()).st_nlink != 1
            ):
                raise SnapshotRecoveryRequired()
            for item, path in (
                (owner_handle, root / "owner.json"),
                (lease_handle, root / "lease.lock"),
                (manifest_handle, root / "manifest.json"),
            ):
                require_dense_regular_handle(item)
                if (
                    os.fstat(item.fileno()).st_nlink != 1
                    or not handle_matches_path(item, path)
                ):
                    raise SnapshotRecoveryRequired()
            actual_owner = self._read_exact(owner_handle, len(owner_bytes))
            actual_manifest = self._read_exact(
                manifest_handle, len(manifest_bytes)
            )
            if (
                actual_owner != owner_bytes
                or actual_manifest != manifest_bytes
                or canonical_json_bytes(owner.to_dict()) != owner_bytes
                or canonical_json_bytes(manifest.to_dict()) != manifest_bytes
                or owner.root_identity != _native(root_handle.identity)
                or owner.planned_manifest_byte_length != len(manifest_bytes)
                or owner.planned_manifest_sha256
                != hashlib.sha256(manifest_bytes).hexdigest()
                or owner.planned_artifacts != manifest.artifacts
                or owner.artifact_count != manifest.artifact_count
                or owner.aggregate_byte_length != manifest.aggregate_byte_length
                or owner.artifact_inventory_sha256
                != manifest.artifact_inventory_sha256
                or len(artifact_handles) != manifest.artifact_count
                or len(artifact_objects) != manifest.artifact_count
            ):
                raise SnapshotRecoveryRequired()
            for descriptor, receipt, artifact_handle in zip(
                manifest.artifacts,
                artifact_objects,
                artifact_handles,
            ):
                path = root / descriptor.relative_path
                if (
                    receipt.relative_path != descriptor.relative_path
                    or receipt.byte_length != descriptor.byte_length
                    or receipt.sha256 != descriptor.sha256
                    or receipt.parent_identity
                    != _native(artifacts_handle.identity)
                    or receipt.object_identity
                    != _native(handle_object_identity(artifact_handle))
                    or not handle_matches_path(artifact_handle, path)
                ):
                    raise SnapshotRecoveryRequired()
                require_dense_regular_handle(artifact_handle)
                if os.fstat(artifact_handle.fileno()).st_nlink != 1:
                    raise SnapshotRecoveryRequired()
                payload = self._read_exact(
                    artifact_handle, descriptor.byte_length
                )
                if (
                    hashlib.sha256(payload).hexdigest() != descriptor.sha256
                    or self._jpeg_dimensions(payload)
                    != (descriptor.width, descriptor.height)
                ):
                    raise SnapshotRecoveryRequired()
            self._verify_inventory(
                root,
                expected_root_names,
                root / "artifacts",
                expected_artifact_names,
            )
            if (
                not snapshots_parent.verify_path()
                or not root_handle.verify_path()
                or not artifacts_handle.verify_path()
            ):
                raise SnapshotRecoveryRequired()
        except SnapshotRecoveryRequired:
            raise
        except (OSError, ValueError) as error:
            raise SnapshotRecoveryRequired(error) from error

    @staticmethod
    def _verify_inventory(
        root: Path,
        expected_root_names: set[str],
        artifacts_root: Path,
        expected_artifact_names: set[str],
    ) -> None:
        if {item.name for item in root.iterdir()} != expected_root_names:
            raise SnapshotRecoveryRequired()
        if {item.name for item in artifacts_root.iterdir()} != expected_artifact_names:
            raise SnapshotRecoveryRequired()

    def cleanup_snapshot(self, handle: ProcessedSnapshotHandle) -> None:
        if handle._cleaned:
            return
        self.validate_snapshot(handle)
        root = self._root / handle.manifest.processed_snapshot_id
        try:
            for artifact_handle, descriptor in reversed(
                list(zip(handle._artifact_handles, handle.manifest.artifacts))
            ):
                delete_open_file(
                    artifact_handle, root / Path(descriptor.relative_path)
                )
                artifact_handle.close()
                sync_directory(handle._artifacts_handle)
            delete_open_file(handle._manifest_handle, root / "manifest.json")
            handle._manifest_handle.close()
            sync_directory(handle._root_handle)
            if not handle._artifacts_handle.verify_path():
                raise SnapshotRecoveryRequired()
            (root / "artifacts").rmdir()
            handle._artifacts_handle.close()
            sync_directory(handle._root_handle)
            for file_handle, name in (
                (handle._owner_handle, "owner.json"),
                (handle._completion_handle, "complete.json"),
                (handle._lease_handle, "lease.lock"),
            ):
                delete_open_file(file_handle, root / name)
                file_handle.close()
                sync_directory(handle._root_handle)
            if not handle._root_handle.verify_path():
                raise SnapshotRecoveryRequired()
            root.rmdir()
            handle._root_handle.close()
            sync_directory(handle._snapshots_parent_handle)
            handle._snapshots_parent_handle.close()
            handle._closed = True
            handle._cleaned = True
        except SnapshotRecoveryRequired:
            raise
        except OSError as error:
            raise SnapshotRecoveryRequired(error) from error

    def preserve_snapshot(self, handle: ProcessedSnapshotHandle) -> None:
        if handle._closed:
            return
        for item in handle._artifact_handles + (
            handle._completion_handle,
            handle._manifest_handle,
            handle._lease_handle,
            handle._owner_handle,
        ):
            if not item.closed:
                item.close()
        handle._artifacts_handle.close()
        handle._root_handle.close()
        handle._snapshots_parent_handle.close()
        handle._closed = True

    def _build_descriptors(
        self,
        prepared: tuple[PreparedArtifactDescriptor, ...],
        lease,
        package: ValidatedCapturePackage,
    ) -> tuple[tuple[ProcessedArtifactDescriptor, ...], tuple[BinaryIO, ...]]:
        media = {
            (item.coin_id, item.role.value): item
            for item in package.media
        }
        prepared_pairs = {
            (item.source_coin_id, item.role) for item in prepared
        }
        if prepared_pairs != set(media):
            raise ValueError(
                "Prepared artifacts do not map one-to-one to package media."
            )
        result = []
        handles = lease.handles()
        for descriptor, handle in zip(prepared, handles):
            source = media.get((descriptor.source_coin_id, descriptor.role))
            if source is None:
                raise ValueError("A selected artifact has no package-media source.")
            payload = self._read_exact(handle, descriptor.expected_byte_length)
            digest = hashlib.sha256(payload).hexdigest()
            if digest != descriptor.expected_sha256:
                raise ValueError("A prepared artifact digest changed.")
            width, height = self._jpeg_dimensions(payload)
            result.append(
                ProcessedArtifactDescriptor(
                    descriptor.artifact_key,
                    descriptor.source_coin_id,
                    descriptor.role,
                    descriptor.variant,
                    "",
                    "image/jpeg",
                    len(payload),
                    digest,
                    width,
                    height,
                    SourceArtifactLink(source.archive_path, source.sha256),
                )
            )
        result.sort(key=_descriptor_order)
        by_key = {descriptor.artifact_key: handle for descriptor, handle in zip(prepared, handles)}
        final = tuple(
            ProcessedArtifactDescriptor(
                item.artifact_key,
                item.source_coin_id,
                item.role,
                item.variant,
                f"artifacts/{index:03d}-{item.sha256}.jpg",
                item.content_type,
                item.byte_length,
                item.sha256,
                item.width,
                item.height,
                item.source_artifact,
            )
            for index, item in enumerate(result)
        )
        for item in final:
            item.validate()
        return final, tuple(by_key[item.artifact_key] for item in final)

    @staticmethod
    def _jpeg_dimensions(payload: bytes) -> tuple[int, int]:
        require_complete_jpeg(payload)
        try:
            with Image.open(BytesIO(payload)) as probe:
                probe.verify()
            with Image.open(BytesIO(payload)) as image:
                if image.format != "JPEG" or image.info.get("progressive"):
                    raise ValueError("processed artifacts must be baseline JPEG.")
                size = image.size
                image.load()
        except (OSError, UnidentifiedImageError) as error:
            raise ValueError("processed artifact is not a valid JPEG.") from error
        if (
            not 1 <= size[0] <= MAX_IMAGE_DIMENSION
            or not 1 <= size[1] <= MAX_IMAGE_DIMENSION
            or size[0] * size[1] > MAX_IMAGE_PIXELS
        ):
            raise ValueError("processed artifact dimensions exceed their limits.")
        return size

    @staticmethod
    def _read_exact(handle: BinaryIO, expected: int) -> bytes:
        handle.seek(0)
        payload = handle.read(expected + 1)
        if len(payload) != expected:
            raise ValueError("an artifact does not have its exact expected length.")
        return payload

    @staticmethod
    def _write_exact(
        path: Path,
        payload: bytes,
        state: dict[str, Any],
        parent: PlainDirectoryHandle,
    ) -> BinaryIO:
        handle = open_exclusive_child_binary(parent, path.name)
        state["handles"].append((handle, path))
        try:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            if not handle_matches_path(handle, path):
                raise OSError("a snapshot file identity changed during publication.")
            return ProcessedArtifactSnapshotService._reopen_readonly(
                parent, handle, path, state
            )
        except Exception:
            raise

    @staticmethod
    def _reopen_readonly(
        parent: PlainDirectoryHandle,
        writable: BinaryIO,
        path: Path,
        state: dict[str, Any],
    ) -> BinaryIO:
        identity = handle_object_identity(writable)
        readonly = open_plain_child_file_readonly(parent, path.name)
        try:
            if handle_object_identity(readonly) != identity:
                raise OSError("a snapshot file identity changed while sealing.")
            state["handles"].remove((writable, path))
            state["handles"].append((readonly, path))
            writable.close()
            return readonly
        except Exception:
            readonly.close()
            raise

    @staticmethod
    def _acquire_zero_byte_lease(handle: BinaryIO) -> None:
        if os.fstat(handle.fileno()).st_size != 0:
            raise OSError("the processed snapshot lease must remain empty.")
        if os.name != "nt":
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        import ctypes
        import msvcrt

        class Overlapped(ctypes.Structure):
            _fields_ = (
                ("Internal", ctypes.c_void_p),
                ("InternalHigh", ctypes.c_void_p),
                ("Offset", ctypes.c_uint32),
                ("OffsetHigh", ctypes.c_uint32),
                ("hEvent", ctypes.c_void_p),
            )

        operation = ctypes.WinDLL("kernel32", use_last_error=True).LockFileEx
        operation.argtypes = (
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.POINTER(Overlapped),
        )
        operation.restype = ctypes.c_int
        overlap = Overlapped()
        if not operation(
            msvcrt.get_osfhandle(handle.fileno()),
            0x00000002 | 0x00000001,
            0,
            1,
            0,
            ctypes.byref(overlap),
        ):
            raise BlockingIOError("the processed snapshot lease is already held.")

    def _cleanup_failed(self, path: Path, state: Mapping[str, Any]) -> None:
        if not state.get("created"):
            parent_handle = state.get("snapshots_parent_handle")
            if parent_handle is not None:
                parent_handle.close()
            return
        try:
            for handle, object_path in reversed(state.get("handles", [])):
                if handle.closed:
                    continue
                if not object_path.exists():
                    raise SnapshotRecoveryRequired()
                if not handle_matches_path(handle, object_path):
                    raise SnapshotRecoveryRequired()
                delete_open_file(handle, object_path)
                handle.close()
                artifacts_handle = state.get("artifacts_handle")
                root_handle = state.get("root_handle")
                if (
                    artifacts_handle is not None
                    and object_path.parent == path / "artifacts"
                ):
                    sync_directory(artifacts_handle)
                elif root_handle is not None:
                    sync_directory(root_handle)
            artifacts_handle = state.get("artifacts_handle")
            artifacts_path = path / "artifacts"
            if artifacts_handle is not None:
                if artifacts_path.exists():
                    if not artifacts_handle.verify_path() or any(artifacts_path.iterdir()):
                        raise SnapshotRecoveryRequired()
                    artifacts_path.rmdir()
                    sync_directory(state["root_handle"])
                artifacts_handle.close()
            root_handle = state.get("root_handle")
            if root_handle is not None:
                if not root_handle.verify_path() or any(path.iterdir()):
                    raise SnapshotRecoveryRequired()
                path.rmdir()
                root_handle.close()
                parent_handle = state.get("snapshots_parent_handle")
                if parent_handle is None:
                    raise SnapshotRecoveryRequired()
                sync_directory(parent_handle)
                parent_handle.close()
        except (OSError, ValueError, SnapshotRecoveryRequired) as error:
            self._close_failed_state(state)
            if isinstance(error, SnapshotRecoveryRequired):
                raise
            raise SnapshotRecoveryRequired(error) from error

    @staticmethod
    def _close_failed_state(state: Mapping[str, Any]) -> None:
        for handle, _path in state.get("handles", []):
            if not handle.closed:
                handle.close()
        for name in (
            "artifacts_handle",
            "root_handle",
            "snapshots_parent_handle",
        ):
            handle = state.get(name)
            if handle is not None:
                handle.close()
