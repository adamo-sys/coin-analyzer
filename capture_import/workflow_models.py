"""Immutable domain models for the deterministic import workflow pipeline.

These models describe preprocessing state before the durable transaction
boundary.  They deliberately contain no journal, collection, or lock
dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from pathlib import PurePosixPath
import threading
from typing import Any, BinaryIO, Dict, List, Mapping, Union
import unicodedata

from ._filesystem import (
    ObjectIdentity,
    PlainDirectoryHandle,
    handle_matches_path,
    handle_object_identity,
)
from .limits import (
    MAX_PROCESSED_ARTIFACTS,
    MAX_PROCESSED_ARTIFACT_BYTES,
    MAX_PROCESSED_ARTIFACT_SIZE,
    MAX_SAFE_RELATIVE_PATH_CHARS,
)
from .models import _require_integer, _require_string, _validate_relative_path

JsonValue = Union[str, int, float, bool, None, List["JsonValue"], Dict[str, "JsonValue"]]


def _validate_json_value(value: Any, field_name: str) -> JsonValue:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not __import__("math").isfinite(value):
            raise ValueError(f"{field_name} contains a non-finite float.")
        return value
    if isinstance(value, list):
        return [_validate_json_value(item, field_name) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError(f"{field_name} dict keys must be strings.")
        return {key: _validate_json_value(item, field_name) for key, item in value.items()}
    raise ValueError(f"{field_name} contains an unsupported JSON value type.")


def _validate_json_mapping(value: Mapping[str, Any], field_name: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{field_name} keys must be strings.")
        _validate_json_value(item, field_name)


@dataclass(frozen=True, slots=True)
class ImportConfiguration:
    """Workflow-scoped import settings (placeholder for future expansion)."""

    def validate(self) -> None:
        pass


@dataclass(frozen=True, slots=True)
class ImportRequest:
    """Immutable request to begin an import workflow."""

    source: Path
    collection_id: str
    configuration: ImportConfiguration

    def validate(self) -> None:
        if not isinstance(self.source, Path):
            raise ValueError("source must be a pathlib.Path.")
        if not self.source.is_absolute():
            raise ValueError("source must be an absolute path.")
        _require_string(self.collection_id, "collection_id", allow_empty=False)
        if not isinstance(self.configuration, ImportConfiguration):
            raise ValueError("configuration must be an ImportConfiguration.")


@dataclass(frozen=True, slots=True)
class StageArtifact:
    """One artifact produced or consumed by a pipeline stage."""

    relative_path: str
    content_type: str = "application/octet-stream"

    def validate(self) -> None:
        _validate_relative_path(self.relative_path, "relative_path")
        _require_string(self.content_type, "content_type", allow_empty=False)


def _validate_artifact_mapping(value: Mapping[str, Any], field_name: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    for key, artifact in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{field_name} keys must be strings.")
        if not isinstance(artifact, StageArtifact):
            raise ValueError(f"{field_name} values must be StageArtifact instances.")
        artifact.validate()


@dataclass(frozen=True, slots=True)
class StageInput:
    """Explicit input to a single processing stage."""

    request: ImportRequest
    workspace: Path
    artifacts: Mapping[str, StageArtifact]

    def validate(self) -> None:
        if not isinstance(self.request, ImportRequest):
            raise ValueError("request must be an ImportRequest.")
        self.request.validate()
        if not isinstance(self.workspace, Path):
            raise ValueError("workspace must be a pathlib.Path.")
        if not self.workspace.is_absolute():
            raise ValueError("workspace must be an absolute path.")
        _validate_artifact_mapping(self.artifacts, "artifacts")


@dataclass(frozen=True, slots=True)
class StageResult:
    """Explicit output from a single processing stage."""

    artifacts: Mapping[str, StageArtifact]
    metadata: Mapping[str, JsonValue]

    def validate(self) -> None:
        _validate_artifact_mapping(self.artifacts, "artifacts")
        _validate_json_mapping(self.metadata, "metadata")


@dataclass(frozen=True, slots=True)
class PreparedFile:
    """One file ready for durable import."""

    relative_path: str
    expected_size: int
    sha256: str | None = None
    artifact_key: str | None = None
    content_type: str = "application/octet-stream"
    producer_stage: str | None = None
    durability_classification: str = "EPHEMERAL"

    def validate(self) -> None:
        _validate_relative_path(self.relative_path, "relative_path")
        _require_integer(self.expected_size, "expected_size", minimum=0)
        if self.sha256 is not None:
            text = _require_string(self.sha256, "sha256", max_chars=64)
            if len(text) != 64 or not all(c in "0123456789abcdef" for c in text):
                raise ValueError("sha256 must be a 64-character lowercase hex string.")
        if self.artifact_key is not None:
            _require_string(self.artifact_key, "artifact_key", allow_empty=False)
        _require_string(self.content_type, "content_type", allow_empty=False)
        if self.producer_stage is not None:
            _require_string(self.producer_stage, "producer_stage", allow_empty=False)
        if self.durability_classification not in {
            "EPHEMERAL",
            "PROCESSED_CANDIDATE",
            "PROCESSED_SELECTED",
        }:
            raise ValueError("durability_classification is unsupported.")


@dataclass(frozen=True, slots=True)
class PreparedArtifactDescriptor:
    """Identity-bound, non-durable description of one selected JPEG."""

    artifact_key: str
    source_coin_id: str
    role: str
    variant: str
    content_type: str
    expected_byte_length: int
    expected_sha256: str
    workspace_relative_path: str
    root_identity: ObjectIdentity
    parent_identity: ObjectIdentity
    file_identity: ObjectIdentity

    def validate(self) -> None:
        _require_nfc_text(self.artifact_key, "artifact_key", maximum=255)
        _require_nfc_text(
            self.source_coin_id, "source_coin_id", maximum=16_384
        )
        if self.role not in {"front", "reverse", "edge"}:
            raise ValueError("role must be front, reverse, or edge.")
        if self.variant not in {"CROPPED", "NORMALIZED"}:
            raise ValueError("variant must be CROPPED or NORMALIZED.")
        if self.content_type != "image/jpeg":
            raise ValueError("content_type must be image/jpeg.")
        _require_integer(
            self.expected_byte_length,
            "expected_byte_length",
            minimum=1,
            maximum=MAX_PROCESSED_ARTIFACT_SIZE,
        )
        text = _require_string(self.expected_sha256, "expected_sha256", max_chars=64)
        if len(text) != 64 or not all(c in "0123456789abcdef" for c in text):
            raise ValueError("expected_sha256 must be lowercase SHA-256.")
        _validate_processed_relative_path(
            self.workspace_relative_path, "workspace_relative_path"
        )
        for value, name in (
            (self.root_identity, "root_identity"),
            (self.parent_identity, "parent_identity"),
            (self.file_identity, "file_identity"),
        ):
            if (
                not isinstance(value, tuple)
                or len(value) != 2
                or any(
                    isinstance(item, bool) or not isinstance(item, int) or item < 0
                    for item in value
                )
            ):
                raise ValueError(f"{name} must be a native object identity.")


def _require_nfc_text(value: Any, name: str, *, maximum: int) -> str:
    text = _require_string(value, name, allow_empty=False, max_chars=maximum)
    if unicodedata.normalize("NFC", text) != text:
        raise ValueError(f"{name} must already be NFC-normalized.")
    if any(unicodedata.category(character) == "Cc" for character in text):
        raise ValueError(f"{name} must not contain control characters.")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in text):
        raise ValueError(f"{name} must not contain surrogate code points.")
    return text


def _validate_processed_relative_path(value: Any, name: str) -> str:
    text = _require_nfc_text(
        value, name, maximum=MAX_SAFE_RELATIVE_PATH_CHARS
    )
    if (
        "\\" in text
        or text.startswith(("/", "//"))
        or (len(text) >= 2 and text[0].isalpha() and text[1] == ":")
    ):
        raise ValueError(f"{name} must be a strict relative path.")
    components = text.split("/")
    if (
        not components
        or any(
            not component
            or component in {".", ".."}
            or component.endswith((".", " "))
            for component in components
        )
        or "/".join(PurePosixPath(text).parts) != text
    ):
        raise ValueError(f"{name} must be a strict relative path.")
    return text


def _windows_safe_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


class PreparedWorkspaceLease:
    """Own held no-follow handles for one verified workflow workspace."""

    def __init__(
        self,
        workspace: Path,
        root_handle: PlainDirectoryHandle,
        handles: tuple[BinaryIO, ...],
        parent_chains: tuple[tuple[PlainDirectoryHandle, ...], ...] | None = None,
    ) -> None:
        self.workspace = workspace.absolute()
        self._root_handle = root_handle
        self._handles = handles
        self._parent_chains = parent_chains or tuple(() for _ in handles)
        if len(self._parent_chains) != len(handles):
            raise ValueError("parent_chains must align with handles.")
        self._closed = False

    @property
    def root_identity(self) -> ObjectIdentity:
        return self._root_handle.identity

    @property
    def is_active(self) -> bool:
        return not self._closed and all(not item.closed for item in self._handles)

    def handles(self) -> tuple[BinaryIO, ...]:
        if not self.is_active:
            raise RuntimeError("prepared workspace lease is closed.")
        return self._handles

    def verify(self, descriptors: tuple[PreparedArtifactDescriptor, ...]) -> None:
        if len(descriptors) != len(self._handles) or not self.is_active:
            raise OSError("The prepared workspace lease is incomplete.")
        if not self._root_handle.verify_path():
            raise OSError("The prepared workspace root identity changed.")
        for index, (descriptor, handle) in enumerate(
            zip(descriptors, self._handles)
        ):
            path = self.workspace / descriptor.workspace_relative_path
            chain = self._parent_chains[index]
            expected_components = PurePosixPath(
                descriptor.workspace_relative_path
            ).parts[:-1]
            if len(chain) != len(expected_components):
                raise OSError("A prepared artifact parent chain is incomplete.")
            previous = self._root_handle
            for component, directory in zip(expected_components, chain):
                if (
                    directory.path != previous.path / component
                    or directory.identity[0] != self.root_identity[0]
                    or not previous.verify_path()
                    or not directory.verify_path()
                ):
                    raise OSError(
                        "A prepared artifact parent identity changed."
                    )
                previous = directory
            if (
                descriptor.root_identity != self.root_identity
                or previous.identity != descriptor.parent_identity
                or descriptor.file_identity[0] != self.root_identity[0]
                or handle_object_identity(handle) != descriptor.file_identity
                or not handle_matches_path(handle, path)
            ):
                raise OSError("A prepared artifact identity changed.")
            before = os.fstat(handle.fileno())
            if before.st_size != descriptor.expected_byte_length:
                raise OSError("A prepared artifact length changed.")
            handle.seek(0)
            digest = hashlib.sha256()
            remaining = descriptor.expected_byte_length
            while remaining:
                chunk = handle.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise OSError("A prepared artifact became incomplete.")
                digest.update(chunk)
                remaining -= len(chunk)
            if handle.read(1) or digest.hexdigest() != descriptor.expected_sha256:
                raise OSError("A prepared artifact digest changed.")
            after = os.fstat(handle.fileno())
            if (
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                or not handle_matches_path(handle, path)
            ):
                raise OSError("A prepared artifact changed while verified.")

    def close(self) -> None:
        if self._closed:
            return
        for handle in self._handles:
            if not handle.closed:
                handle.close()
        for chain in self._parent_chains:
            for directory in reversed(chain):
                directory.close()
        self._root_handle.close()
        self._closed = True


class ClaimedPreparedArtifactSet:
    """Sole post-transfer owner of prepared descriptors and held handles."""

    def __init__(
        self,
        descriptors: tuple[PreparedArtifactDescriptor, ...],
        lease: PreparedWorkspaceLease,
    ) -> None:
        self.descriptors = descriptors
        self._lease = lease
        self._closed = False

    @property
    def is_active(self) -> bool:
        return not self._closed and self._lease.is_active

    def verify(self) -> None:
        if self._closed:
            raise RuntimeError("claimed prepared artifacts are closed.")
        self._lease.verify(self.descriptors)

    def handles(self) -> tuple[BinaryIO, ...]:
        self.verify()
        return self._lease.handles()

    def close(self) -> None:
        if not self._closed:
            self._lease.close()
            self._closed = True


class PreparedArtifactSet:
    """Single-use ownership wrapper for prepared descriptors and their lease."""

    def __init__(
        self,
        descriptors: tuple[PreparedArtifactDescriptor, ...],
        lease: PreparedWorkspaceLease,
    ) -> None:
        if not isinstance(lease, PreparedWorkspaceLease):
            raise ValueError("lease must be a PreparedWorkspaceLease.")
        try:
            if not isinstance(descriptors, tuple) or not descriptors:
                raise ValueError(
                    "descriptors must be a non-empty immutable tuple."
                )
            if len(descriptors) > MAX_PROCESSED_ARTIFACTS:
                raise ValueError("too many processed artifacts.")
            for descriptor in descriptors:
                if not isinstance(descriptor, PreparedArtifactDescriptor):
                    raise ValueError(
                        "descriptors contain an unsupported value."
                    )
                descriptor.validate()
            expected_order = sorted(
                descriptors,
                key=lambda value: (
                    value.source_coin_id,
                    {"front": 0, "reverse": 1, "edge": 2}[value.role],
                    value.variant,
                    value.artifact_key,
                ),
            )
            if list(descriptors) != expected_order:
                raise ValueError("descriptors are not in canonical order.")
            for values, name in (
                (
                    [
                        _windows_safe_key(item.artifact_key)
                        for item in descriptors
                    ],
                    "artifact_key",
                ),
                (
                    [
                        _windows_safe_key(item.workspace_relative_path)
                        for item in descriptors
                    ],
                    "workspace_relative_path",
                ),
                (
                    [
                        (_windows_safe_key(item.source_coin_id), item.role)
                        for item in descriptors
                    ],
                    "source coin/role",
                ),
                (
                    [item.file_identity for item in descriptors],
                    "file_identity",
                ),
            ):
                if len(set(values)) != len(values):
                    raise ValueError(f"duplicate canonical {name}.")
            if (
                sum(item.expected_byte_length for item in descriptors)
                > MAX_PROCESSED_ARTIFACT_BYTES
            ):
                raise ValueError(
                    "processed artifact bytes exceed the aggregate limit."
                )
            lease.verify(descriptors)
        except Exception:
            lease.close()
            raise
        self.descriptors = descriptors
        self._lease: PreparedWorkspaceLease | None = lease
        self._claimed = False
        self._guard = threading.Lock()

    @property
    def is_claimed(self) -> bool:
        with self._guard:
            return self._claimed

    @property
    def is_active(self) -> bool:
        with self._guard:
            return self._lease is not None and self._lease.is_active

    def verify(self) -> None:
        with self._guard:
            if self._claimed or self._lease is None:
                raise RuntimeError("prepared artifacts are no longer caller-owned.")
            self._lease.verify(self.descriptors)

    def claim(self) -> ClaimedPreparedArtifactSet:
        """Transfer ownership exactly once; rejection leaves ownership unchanged."""

        with self._guard:
            if self._claimed or self._lease is None:
                raise RuntimeError("prepared artifacts were already claimed.")
            self._lease.verify(self.descriptors)
            claimed = ClaimedPreparedArtifactSet(self.descriptors, self._lease)
            self._lease = None
            self._claimed = True
            return claimed

    def close_if_unclaimed(self) -> None:
        with self._guard:
            if not self._claimed and self._lease is not None:
                self._lease.close()

    def close(self) -> None:
        self.close_if_unclaimed()


@dataclass(frozen=True, slots=True)
class PreparedImport:
    """The sole output of a successful pipeline, accepted by the transaction layer."""

    request: ImportRequest
    files: tuple[PreparedFile, ...]
    metadata: Mapping[str, JsonValue]
    processed_artifacts: PreparedArtifactSet | None = None

    def validate(self) -> None:
        if not isinstance(self.request, ImportRequest):
            raise ValueError("request must be an ImportRequest.")
        self.request.validate()
        if not isinstance(self.files, tuple):
            raise ValueError("files must be an immutable tuple.")
        for file in self.files:
            if not isinstance(file, PreparedFile):
                raise ValueError("files must contain PreparedFile values.")
            file.validate()
        _validate_json_mapping(self.metadata, "metadata")
        if self.processed_artifacts is not None:
            if not isinstance(self.processed_artifacts, PreparedArtifactSet):
                raise ValueError(
                    "processed_artifacts must be a PreparedArtifactSet or None."
                )
            if not self.processed_artifacts.is_active:
                raise ValueError("processed_artifacts must own an active lease.")
