"""Immutable domain models for the deterministic import workflow pipeline.

These models describe preprocessing state before the durable transaction
boundary.  They deliberately contain no journal, collection, or lock
dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Union

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
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dict mapping.")
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
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dict mapping.")
    for key, artifact in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{field_name} keys must be strings.")
        if not isinstance(artifact, StageArtifact):
            raise ValueError(f"{field_name} values must be StageArtifact instances.")


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

    def validate(self) -> None:
        _validate_relative_path(self.relative_path, "relative_path")
        _require_integer(self.expected_size, "expected_size", minimum=0)
        if self.sha256 is not None:
            text = _require_string(self.sha256, "sha256", max_chars=64)
            if len(text) != 64 or not all(c in "0123456789abcdef" for c in text):
                raise ValueError("sha256 must be a 64-character lowercase hex string.")


@dataclass(frozen=True, slots=True)
class PreparedImport:
    """The sole output of a successful pipeline, accepted by the transaction layer."""

    request: ImportRequest
    files: tuple[PreparedFile, ...]
    metadata: Mapping[str, JsonValue]

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
