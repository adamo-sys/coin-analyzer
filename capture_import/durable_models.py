"""Closed schema-2 durability contracts for capture-package imports.

Durable Persistence §§159–416, RM-03 and RM-16–RM-28.
This module contains validation and canonical serialization only; filesystem
mutation belongs to the repository and transaction services.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Mapping
from uuid import UUID

from .enums import (
    CleanupStatus,
    CollectionPublicationState,
    ImportPhase,
    ImportResult,
    TerminalCompactionStatus,
)
from .limits import MAX_JSON_BYTES, MAX_JOURNAL_GENERATIONS

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ASCII_BASENAME = re.compile(r"^[\x21-\x7e]{1,255}$")


def _uuid4(value: str, name: str) -> None:
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError(f"{name} must be a canonical UUIDv4.") from error
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError(f"{name} must be a canonical UUIDv4.")


def _sha(value: str, name: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256.")


def _basename(value: str, name: str) -> None:
    if (
        not isinstance(value, str)
        or _ASCII_BASENAME.fullmatch(value) is None
        or "/" in value
        or "\\" in value
        or value in {".", ".."}
    ):
        raise ValueError(f"{name} must be a strict ASCII basename.")


def _integer(value: int, name: str, minimum: int, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer.")
    if value < minimum or value > maximum:
        raise ValueError(f"{name} is outside its allowed range.")


def _timestamp(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{name} must be normalized UTC RFC 3339.")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError(f"{name} must be normalized UTC RFC 3339.") from error


def _closed(value: Mapping[str, Any], keys: frozenset[str], name: str) -> None:
    if not isinstance(value, Mapping) or frozenset(value) != keys:
        raise ValueError(f"{name} must contain exactly its closed schema fields.")


@dataclass(frozen=True, slots=True)
class NativeObjectIdentity:
    """Portable canonical form of a held native filesystem identity."""

    platform: str
    volume_id: str
    object_id: str

    def validate(self) -> None:
        if self.platform == "WINDOWS":
            if re.fullmatch(r"[0-9a-f]{16}", self.volume_id) is None:
                raise ValueError("Windows volume_id must be 16 lowercase hex digits.")
            if re.fullmatch(r"[0-9a-f]{32}", self.object_id) is None:
                raise ValueError("Windows object_id must be 32 lowercase hex digits.")
        elif self.platform == "POSIX":
            for value, name in ((self.volume_id, "volume_id"), (self.object_id, "object_id")):
                if re.fullmatch(r"0|[1-9][0-9]{0,19}", value) is None:
                    raise ValueError(f"POSIX {name} must be canonical unsigned decimal.")
        else:
            raise ValueError("platform must be WINDOWS or POSIX.")

    def to_dict(self) -> dict[str, str]:
        self.validate()
        return {"platform": self.platform, "volume_id": self.volume_id, "object_id": self.object_id}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "NativeObjectIdentity":
        _closed(value, frozenset({"platform", "volume_id", "object_id"}), "ObjectIdentity")
        result = cls(str(value["platform"]), str(value["volume_id"]), str(value["object_id"]))
        result.validate()
        return result

    @classmethod
    def from_native(cls, value: tuple[int, int], *, windows: bool = False) -> "NativeObjectIdentity":
        if windows:
            result = cls("WINDOWS", f"{value[0]:016x}", f"{value[1]:032x}")
        else:
            result = cls("POSIX", str(value[0]), str(value[1]))
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class CollectionPublicationArtifact:
    """Planned, verified, or published collection relationship."""

    kind: str
    relative_name: str
    token: str
    relationship: str
    expected_byte_length: int
    expected_sha256: str
    expected_parent_identity: NativeObjectIdentity
    state: CollectionPublicationState
    object_identity: NativeObjectIdentity | None = None
    verified_byte_length: int | None = None
    verified_sha256: str | None = None
    verified_generation: int | None = None
    current_relative_name: str | None = None
    exchange_generation: int | None = None
    published_relative_name: str | None = None
    publication_generation: int | None = None
    cleanup_operation_id: str | None = None

    FIELDS = frozenset(
        {
            "kind", "relative_name", "token", "relationship",
            "expected_byte_length", "expected_sha256", "expected_parent_identity",
            "state", "object_identity", "verified_byte_length", "verified_sha256",
            "verified_generation", "current_relative_name", "exchange_generation",
            "published_relative_name", "publication_generation", "cleanup_operation_id",
        }
    )

    def validate(self) -> None:
        if (self.kind, self.relationship) not in {
            ("TEMPORARY", "PROSPECTIVE_BYTES"),
            ("BACKUP", "BASELINE_BYTES"),
        }:
            raise ValueError("Artifact kind and relationship disagree.")
        _basename(self.relative_name, "relative_name")
        _uuid4(self.token, "token")
        _integer(self.expected_byte_length, "expected_byte_length", 0, MAX_JSON_BYTES)
        if self.kind == "TEMPORARY" and self.expected_byte_length == 0:
            raise ValueError("Prospective collection bytes must not be empty.")
        _sha(self.expected_sha256, "expected_sha256")
        self.expected_parent_identity.validate()
        if not isinstance(self.state, CollectionPublicationState):
            raise ValueError("state must be CollectionPublicationState.")
        if self.current_relative_name is not None:
            _basename(self.current_relative_name, "current_relative_name")
        if self.published_relative_name is not None:
            _basename(self.published_relative_name, "published_relative_name")
        for value, name in (
            (self.verified_generation, "verified_generation"),
            (self.exchange_generation, "exchange_generation"),
            (self.publication_generation, "publication_generation"),
        ):
            if value is not None:
                _integer(value, name, 0, MAX_JOURNAL_GENERATIONS - 1)
        if self.cleanup_operation_id is not None:
            _uuid4(self.cleanup_operation_id, "cleanup_operation_id")
        verified = self.state in {
            CollectionPublicationState.VERIFIED,
            CollectionPublicationState.EXCHANGED,
            CollectionPublicationState.PUBLISHED,
            CollectionPublicationState.RETAINED,
            CollectionPublicationState.CLEANED,
        }
        created = self.state is not CollectionPublicationState.PLANNED
        if created != (self.object_identity is not None):
            raise ValueError("Artifact identity nullability disagrees with state.")
        if self.object_identity is not None:
            self.object_identity.validate()
        if verified:
            if (
                self.verified_byte_length != self.expected_byte_length
                or self.verified_sha256 != self.expected_sha256
                or self.verified_generation is None
            ):
                raise ValueError("Verified artifact proof must equal its commitment.")
        elif any(value is not None for value in (self.verified_byte_length, self.verified_sha256, self.verified_generation)):
            raise ValueError("Unverified artifact cannot contain verified proof.")
        if self.state is CollectionPublicationState.PLANNED and any(
            value is not None
            for value in (
                self.current_relative_name, self.exchange_generation,
                self.published_relative_name, self.publication_generation,
                self.cleanup_operation_id,
            )
        ):
            raise ValueError("Planned artifact contains outcome fields.")
        if self.state is CollectionPublicationState.CREATED:
            if self.current_relative_name != self.relative_name:
                raise ValueError("Created artifact must occupy its planned name.")
        if self.state is CollectionPublicationState.EXCHANGED:
            if self.exchange_generation is None or self.kind not in {"TEMPORARY", "BACKUP"}:
                raise ValueError("Exchanged artifact requires exchange generation.")
        if self.state is CollectionPublicationState.PUBLISHED:
            if self.kind != "TEMPORARY" or self.publication_generation is None or self.published_relative_name is None:
                raise ValueError("Only a temporary artifact may become published.")
        if self.state in {CollectionPublicationState.RETAINED, CollectionPublicationState.CLEANED}:
            if self.kind != "BACKUP" or self.publication_generation is None:
                raise ValueError("Only a backup may be retained or cleaned.")
            if self.state is CollectionPublicationState.CLEANED and self.cleanup_operation_id is None:
                raise ValueError("Cleaned backup requires cleanup operation ID.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "kind": self.kind,
            "relative_name": self.relative_name,
            "token": self.token,
            "relationship": self.relationship,
            "expected_byte_length": self.expected_byte_length,
            "expected_sha256": self.expected_sha256,
            "expected_parent_identity": self.expected_parent_identity.to_dict(),
            "state": self.state.value,
            "object_identity": None if self.object_identity is None else self.object_identity.to_dict(),
            "verified_byte_length": self.verified_byte_length,
            "verified_sha256": self.verified_sha256,
            "verified_generation": self.verified_generation,
            "current_relative_name": self.current_relative_name,
            "exchange_generation": self.exchange_generation,
            "published_relative_name": self.published_relative_name,
            "publication_generation": self.publication_generation,
            "cleanup_operation_id": self.cleanup_operation_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CollectionPublicationArtifact":
        _closed(value, cls.FIELDS, "CollectionPublicationArtifact")
        result = cls(
            kind=value["kind"], relative_name=value["relative_name"], token=value["token"],
            relationship=value["relationship"], expected_byte_length=value["expected_byte_length"],
            expected_sha256=value["expected_sha256"],
            expected_parent_identity=NativeObjectIdentity.from_dict(value["expected_parent_identity"]),
            state=CollectionPublicationState(value["state"]),
            object_identity=None if value["object_identity"] is None else NativeObjectIdentity.from_dict(value["object_identity"]),
            verified_byte_length=value["verified_byte_length"], verified_sha256=value["verified_sha256"],
            verified_generation=value["verified_generation"], current_relative_name=value["current_relative_name"],
            exchange_generation=value["exchange_generation"], published_relative_name=value["published_relative_name"],
            publication_generation=value["publication_generation"], cleanup_operation_id=value["cleanup_operation_id"],
        )
        result.validate()
        return result


def validate_collection_publication_pair(
    temporary: CollectionPublicationArtifact,
    backup: CollectionPublicationArtifact | None,
    *,
    platform: str,
) -> None:
    """Validate the platform-specific pre/post-publication relationship.

    Durable Persistence §§258–345, RM-16–RM-18.
    """

    temporary.validate()
    if temporary.kind != "TEMPORARY":
        raise ValueError("The prospective descriptor must be TEMPORARY.")
    if backup is None:
        return
    backup.validate()
    if backup.kind != "BACKUP" or temporary.token == backup.token:
        raise ValueError("The baseline descriptor must be a distinct BACKUP.")
    if platform == "POSIX":
        if temporary.relative_name != backup.relative_name:
            raise ValueError("POSIX exchange relationships must share one planned name.")
        if backup.state in {CollectionPublicationState.CREATED, CollectionPublicationState.VERIFIED}:
            raise ValueError("POSIX backup identity cannot exist before exchange.")
        if temporary.state is CollectionPublicationState.EXCHANGED or backup.state is CollectionPublicationState.EXCHANGED:
            if temporary.state is not CollectionPublicationState.EXCHANGED or backup.state is not CollectionPublicationState.EXCHANGED:
                raise ValueError("POSIX relationships must advance to EXCHANGED together.")
    elif platform == "WINDOWS":
        if temporary.relative_name == backup.relative_name:
            raise ValueError("Windows backup requires an independent basename.")
        if CollectionPublicationState.EXCHANGED in {temporary.state, backup.state}:
            raise ValueError("Windows publication does not use EXCHANGED state.")
    else:
        raise ValueError("Unsupported publication platform.")


@dataclass(frozen=True, slots=True)
class CleanupReceipt:
    target_relative_path: str
    removed_object_identity: NativeObjectIdentity
    removal_generation: int

    def validate(self) -> None:
        if not isinstance(self.target_relative_path, str) or not self.target_relative_path:
            raise ValueError("target_relative_path is required.")
        self.removed_object_identity.validate()
        _integer(self.removal_generation, "removal_generation", 0, MAX_JOURNAL_GENERATIONS - 1)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {"target_relative_path": self.target_relative_path, "removed_object_identity": self.removed_object_identity.to_dict(), "removal_generation": self.removal_generation}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CleanupReceipt":
        _closed(value, frozenset({"target_relative_path", "removed_object_identity", "removal_generation"}), "CleanupReceipt")
        result = cls(value["target_relative_path"], NativeObjectIdentity.from_dict(value["removed_object_identity"]), value["removal_generation"])
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class OwnershipDescriptor:
    root: str
    relative_path: str
    object_kind: str
    ownership_token: str
    expected_byte_length: int | None
    expected_sha256: str | None
    parent_identity: NativeObjectIdentity
    object_identity: NativeObjectIdentity

    def validate(self) -> None:
        if self.root not in {"JOURNAL", "SNAPSHOT", "MANAGED_IMAGE", "COLLECTION"}:
            raise ValueError("Ownership root is invalid.")
        if not isinstance(self.relative_path, str) or not self.relative_path or self.relative_path.startswith(("/", "\\")) or ".." in self.relative_path.replace("\\", "/").split("/"):
            raise ValueError("Ownership relative path is invalid.")
        if self.object_kind not in {"FILE", "DIRECTORY"}:
            raise ValueError("Ownership object kind is invalid.")
        _uuid4(self.ownership_token, "ownership_token")
        if self.object_kind == "DIRECTORY":
            if self.expected_byte_length is not None or self.expected_sha256 is not None:
                raise ValueError("Directory descriptor cannot contain byte proof.")
        else:
            if self.expected_byte_length is None or self.expected_sha256 is None:
                raise ValueError("File descriptor requires byte proof.")
            _integer(self.expected_byte_length, "expected_byte_length", 0, (2**53) - 1)
            _sha(self.expected_sha256, "expected_sha256")
        self.parent_identity.validate()
        self.object_identity.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "root": self.root, "relative_path": self.relative_path,
            "object_kind": self.object_kind, "ownership_token": self.ownership_token,
            "expected_byte_length": self.expected_byte_length,
            "expected_sha256": self.expected_sha256,
            "parent_identity": self.parent_identity.to_dict(),
            "object_identity": self.object_identity.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OwnershipDescriptor":
        keys = frozenset({"root", "relative_path", "object_kind", "ownership_token", "expected_byte_length", "expected_sha256", "parent_identity", "object_identity"})
        _closed(value, keys, "OwnershipDescriptor")
        result = cls(
            value["root"], value["relative_path"], value["object_kind"], value["ownership_token"],
            value["expected_byte_length"], value["expected_sha256"],
            NativeObjectIdentity.from_dict(value["parent_identity"]),
            NativeObjectIdentity.from_dict(value["object_identity"]),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class CleanupOperation:
    kind: str
    intent_id: str
    intent_generation: int
    targets: tuple[OwnershipDescriptor, ...]
    receipts: tuple[CleanupReceipt, ...]
    status: CleanupStatus
    completed_generation: int | None

    def validate(self) -> None:
        if self.kind not in {"BASELINE_BACKUP", "SUCCESS_SNAPSHOT", "ROLLBACK_ALL"}:
            raise ValueError("Cleanup operation kind is invalid.")
        _uuid4(self.intent_id, "intent_id")
        _integer(self.intent_generation, "intent_generation", 0, 4095)
        if not 1 <= len(self.targets) <= 301:
            raise ValueError("Cleanup targets are outside bounds.")
        for target in self.targets:
            target.validate()
        if len({target.relative_path for target in self.targets}) != len(self.targets):
            raise ValueError("Cleanup targets must be unique.")
        if len(self.receipts) > len(self.targets):
            raise ValueError("Cleanup receipts cannot exceed targets.")
        for index, receipt in enumerate(self.receipts):
            receipt.validate()
            if receipt.target_relative_path != self.targets[index].relative_path or receipt.removal_generation <= self.intent_generation:
                raise ValueError("Cleanup receipts must be a strict target prefix.")
        if self.status is CleanupStatus.INTENT:
            if self.completed_generation is not None:
                raise ValueError("Cleanup intent cannot have a completion generation.")
        elif self.status is CleanupStatus.COMPLETE:
            if len(self.receipts) != len(self.targets) or self.completed_generation is None:
                raise ValueError("Completed cleanup requires every receipt.")
            _integer(self.completed_generation, "completed_generation", self.receipts[-1].removal_generation, 4095)
        else:
            raise ValueError("Cleanup status is invalid.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "kind": self.kind, "intent_id": self.intent_id,
            "intent_generation": self.intent_generation,
            "targets": [target.to_dict() for target in self.targets],
            "receipts": [receipt.to_dict() for receipt in self.receipts],
            "status": self.status.value,
            "completed_generation": self.completed_generation,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CleanupOperation":
        keys = frozenset({"kind", "intent_id", "intent_generation", "targets", "receipts", "status", "completed_generation"})
        _closed(value, keys, "CleanupOperation")
        if not isinstance(value["targets"], list) or not isinstance(value["receipts"], list):
            raise ValueError("Cleanup targets and receipts must be arrays.")
        result = cls(
            kind=value["kind"], intent_id=value["intent_id"], intent_generation=value["intent_generation"],
            targets=tuple(OwnershipDescriptor.from_dict(item) for item in value["targets"]),
            receipts=tuple(CleanupReceipt.from_dict(item) for item in value["receipts"]),
            status=CleanupStatus(value["status"]), completed_generation=value["completed_generation"],
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class ExpectedImageEvidence:
    relative_path: str
    role: str
    byte_length: int
    sha256: str
    media_type: str
    width: int
    height: int

    def validate(self) -> None:
        if not self.relative_path or self.relative_path.startswith(("/", "\\")) or ".." in self.relative_path.replace("\\", "/").split("/"):
            raise ValueError("Expected image path is invalid.")
        if self.role not in {"front", "reverse", "edge"} or self.media_type not in {"image/jpeg", "image/png"}:
            raise ValueError("Expected image role or media type is invalid.")
        _integer(self.byte_length, "image byte_length", 1, 40 * 1024 * 1024)
        _sha(self.sha256, "image sha256")
        _integer(self.width, "image width", 1, 12000)
        _integer(self.height, "image height", 1, 12000)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExpectedImageEvidence":
        _closed(value, frozenset(cls.__dataclass_fields__), "ExpectedImage")
        result = cls(**value)
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class VerifiedImageEvidence(ExpectedImageEvidence):
    parent_identity: NativeObjectIdentity
    object_identity: NativeObjectIdentity

    def validate(self) -> None:
        ExpectedImageEvidence.validate(self)
        self.parent_identity.validate()
        self.object_identity.validate()

    def to_dict(self) -> dict[str, Any]:
        ExpectedImageEvidence.validate(self)
        return {
            "relative_path": self.relative_path, "role": self.role,
            "byte_length": self.byte_length, "sha256": self.sha256,
            "media_type": self.media_type, "width": self.width, "height": self.height,
            "parent_identity": self.parent_identity.to_dict(),
            "object_identity": self.object_identity.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "VerifiedImageEvidence":
        _closed(value, frozenset(cls.__dataclass_fields__), "VerifiedImage")
        result = cls(
            relative_path=value["relative_path"], role=value["role"], byte_length=value["byte_length"],
            sha256=value["sha256"], media_type=value["media_type"], width=value["width"], height=value["height"],
            parent_identity=NativeObjectIdentity.from_dict(value["parent_identity"]),
            object_identity=NativeObjectIdentity.from_dict(value["object_identity"]),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class TerminalCompaction:
    """Closed G/H compaction evidence without a terminal hash cycle."""

    schema_version: str
    status: TerminalCompactionStatus
    final_phase: ImportResult
    result: ImportResult
    completed_at: str
    terminal_pending_name: str
    terminal_temporary_name: str
    terminal_token: str
    retirement_directory_name: str
    retirement_manifest_name: str
    retirement_manifest_temporary_name: str
    retirement_token: str
    manifest_generation_first: int
    manifest_generation_last: int
    manifest_generation_count: int
    compaction_commit_generation: int
    compaction_commit_transition_id: str
    compaction_commit_filename: str
    owner_record_sha256: str
    history_parent_identity: NativeObjectIdentity
    journal_parent_identity: NativeObjectIdentity
    operational_directory_identity: NativeObjectIdentity
    manifest_byte_length: int | None = None
    manifest_sha256: str | None = None
    manifest_object_identity: NativeObjectIdentity | None = None
    outcome_payload_sha256: str | None = None

    def validate(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError("TerminalCompaction schema is unsupported.")
        if self.final_phase not in {ImportResult.SUCCEEDED, ImportResult.ROLLED_BACK, ImportResult.CANCELLED} or self.result is not self.final_phase:
            raise ValueError("Terminal compaction outcome is invalid.")
        for value in (self.terminal_pending_name, self.terminal_temporary_name, self.retirement_directory_name, self.retirement_manifest_name, self.retirement_manifest_temporary_name, self.compaction_commit_filename):
            _basename(value, "compaction basename")
        _uuid4(self.terminal_token, "terminal_token")
        _uuid4(self.retirement_token, "retirement_token")
        _uuid4(self.compaction_commit_transition_id, "compaction_commit_transition_id")
        if self.terminal_token == self.retirement_token:
            raise ValueError("Compaction tokens must be distinct.")
        _integer(self.manifest_generation_first, "manifest_generation_first", 0, 0)
        _integer(self.manifest_generation_last, "manifest_generation_last", 0, 4094)
        if self.manifest_generation_count != self.manifest_generation_last + 1:
            raise ValueError("Manifest generation count is inconsistent.")
        if self.compaction_commit_generation != self.manifest_generation_last + 1:
            raise ValueError("H must immediately follow G.")
        _sha(self.owner_record_sha256, "owner_record_sha256")
        for identity in (self.history_parent_identity, self.journal_parent_identity, self.operational_directory_identity):
            identity.validate()
        manifest_values = (self.manifest_byte_length, self.manifest_sha256, self.manifest_object_identity)
        if self.status is TerminalCompactionStatus.PLANNING_MANIFEST:
            if any(value is not None for value in manifest_values) or self.outcome_payload_sha256 is not None:
                raise ValueError("Planning compaction cannot contain verified commitments.")
        elif self.status is TerminalCompactionStatus.READY_FOR_TERMINAL:
            if any(value is None for value in manifest_values) or self.outcome_payload_sha256 is None:
                raise ValueError("Ready compaction requires manifest and payload commitments.")
            _integer(self.manifest_byte_length, "manifest_byte_length", 1, MAX_JSON_BYTES)
            _sha(self.manifest_sha256, "manifest_sha256")
            self.manifest_object_identity.validate()
            _sha(self.outcome_payload_sha256, "outcome_payload_sha256")
        else:
            raise ValueError("Unknown compaction status.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "status": self.status.value,
            "final_phase": self.final_phase.value,
            "result": self.result.value,
            "completed_at": self.completed_at,
            "terminal_pending_name": self.terminal_pending_name,
            "terminal_temporary_name": self.terminal_temporary_name,
            "terminal_token": self.terminal_token,
            "retirement_directory_name": self.retirement_directory_name,
            "retirement_manifest_name": self.retirement_manifest_name,
            "retirement_manifest_temporary_name": self.retirement_manifest_temporary_name,
            "retirement_token": self.retirement_token,
            "manifest_generation_first": self.manifest_generation_first,
            "manifest_generation_last": self.manifest_generation_last,
            "manifest_generation_count": self.manifest_generation_count,
            "compaction_commit_generation": self.compaction_commit_generation,
            "compaction_commit_transition_id": self.compaction_commit_transition_id,
            "compaction_commit_filename": self.compaction_commit_filename,
            "owner_record_sha256": self.owner_record_sha256,
            "history_parent_identity": self.history_parent_identity.to_dict(),
            "journal_parent_identity": self.journal_parent_identity.to_dict(),
            "operational_directory_identity": self.operational_directory_identity.to_dict(),
            "manifest_byte_length": self.manifest_byte_length,
            "manifest_sha256": self.manifest_sha256,
            "manifest_object_identity": None if self.manifest_object_identity is None else self.manifest_object_identity.to_dict(),
            "outcome_payload_sha256": self.outcome_payload_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TerminalCompaction":
        _closed(value, frozenset(cls.__dataclass_fields__), "TerminalCompaction")
        result = cls(
            **{
                **dict(value),
                "status": TerminalCompactionStatus(value["status"]),
                "final_phase": ImportResult(value["final_phase"]),
                "result": ImportResult(value["result"]),
                "history_parent_identity": NativeObjectIdentity.from_dict(value["history_parent_identity"]),
                "journal_parent_identity": NativeObjectIdentity.from_dict(value["journal_parent_identity"]),
                "operational_directory_identity": NativeObjectIdentity.from_dict(value["operational_directory_identity"]),
                "manifest_object_identity": None if value["manifest_object_identity"] is None else NativeObjectIdentity.from_dict(value["manifest_object_identity"]),
            }
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class ManifestObjectEntry:
    basename: str
    byte_length: int
    sha256: str
    object_identity: NativeObjectIdentity
    generation: int | None = None
    transition_id: str | None = None

    def validate(self, *, generation_entry: bool) -> None:
        _basename(self.basename, "manifest basename")
        _integer(self.byte_length, "manifest byte_length", 1, MAX_JSON_BYTES)
        _sha(self.sha256, "manifest sha256")
        self.object_identity.validate()
        if generation_entry:
            if self.generation is None or self.transition_id is None:
                raise ValueError("Generation manifest entry is incomplete.")
            _integer(self.generation, "generation", 0, 4094)
            _uuid4(self.transition_id, "transition_id")
        elif self.generation is not None or self.transition_id is not None:
            raise ValueError("Owner manifest entry cannot contain generation fields.")

    def to_dict(self, *, generation_entry: bool) -> dict[str, Any]:
        self.validate(generation_entry=generation_entry)
        result = {
            "basename": self.basename,
            "byte_length": self.byte_length,
            "sha256": self.sha256,
            "object_identity": self.object_identity.to_dict(),
        }
        if generation_entry:
            result = {
                "generation": self.generation,
                "transition_id": self.transition_id,
                **result,
            }
        return result

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any], *, generation_entry: bool
    ) -> "ManifestObjectEntry":
        common = frozenset({"basename", "byte_length", "sha256", "object_identity"})
        keys = common | ({"generation", "transition_id"} if generation_entry else set())
        _closed(value, frozenset(keys), "ManifestObjectEntry")
        result = cls(
            basename=value["basename"],
            byte_length=value["byte_length"],
            sha256=value["sha256"],
            object_identity=NativeObjectIdentity.from_dict(value["object_identity"]),
            generation=value.get("generation"),
            transition_id=value.get("transition_id"),
        )
        result.validate(generation_entry=generation_entry)
        return result


@dataclass(frozen=True, slots=True)
class CompactionCommitPlan:
    generation: int
    transition_id: str
    basename: str

    def validate(self, *, expected_generation: int) -> None:
        _integer(self.generation, "compaction generation", 1, 4095)
        if self.generation != expected_generation:
            raise ValueError("Compaction commit generation is not contiguous.")
        _uuid4(self.transition_id, "compaction transition_id")
        _basename(self.basename, "compaction basename")

    def to_dict(self) -> dict[str, Any]:
        return {"generation": self.generation, "transition_id": self.transition_id, "basename": self.basename}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CompactionCommitPlan":
        _closed(value, frozenset(cls.__dataclass_fields__), "CompactionCommitPlan")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class RetirementManifest:
    schema_version: str
    import_id: str
    random_ownership_token_sha256: str
    operational_directory_identity: NativeObjectIdentity
    owner_record: ManifestObjectEntry
    generations: tuple[ManifestObjectEntry, ...]
    compaction_commit: CompactionCommitPlan

    def validate(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError("Retirement manifest schema is unsupported.")
        _uuid4(self.import_id, "import_id")
        _sha(self.random_ownership_token_sha256, "random_ownership_token_sha256")
        self.operational_directory_identity.validate()
        self.owner_record.validate(generation_entry=False)
        if self.owner_record.basename != "owner.json":
            raise ValueError("Owner manifest basename is invalid.")
        if not self.generations or len(self.generations) > 4095:
            raise ValueError("Retirement generation inventory is outside bounds.")
        for expected, entry in enumerate(self.generations):
            entry.validate(generation_entry=True)
            if entry.generation != expected:
                raise ValueError("Retirement generations must be contiguous from zero.")
        self.compaction_commit.validate(expected_generation=len(self.generations))

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "import_id": self.import_id,
            "random_ownership_token_sha256": self.random_ownership_token_sha256,
            "operational_directory_identity": self.operational_directory_identity.to_dict(),
            "owner_record": self.owner_record.to_dict(generation_entry=False),
            "generations": [entry.to_dict(generation_entry=True) for entry in self.generations],
            "compaction_commit": self.compaction_commit.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RetirementManifest":
        _closed(value, frozenset(cls.__dataclass_fields__), "RetirementManifest")
        if not isinstance(value["generations"], list):
            raise ValueError("Retirement generations must be an array.")
        result = cls(
            schema_version=value["schema_version"],
            import_id=value["import_id"],
            random_ownership_token_sha256=value["random_ownership_token_sha256"],
            operational_directory_identity=NativeObjectIdentity.from_dict(
                value["operational_directory_identity"]
            ),
            owner_record=ManifestObjectEntry.from_dict(
                value["owner_record"], generation_entry=False
            ),
            generations=tuple(
                ManifestObjectEntry.from_dict(item, generation_entry=True)
                for item in value["generations"]
            ),
            compaction_commit=CompactionCommitPlan.from_dict(
                value["compaction_commit"]
            ),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class TerminalCollectionProof:
    outcome: str
    baseline_sha256_or_sentinel: str
    baseline_byte_length: int
    final_sha256_or_sentinel: str
    final_byte_length: int
    committed_item_count: int
    committed_item_ids_sha256: str

    def validate(self) -> None:
        if self.outcome not in {"PUBLISHED", "UNCHANGED"}:
            raise ValueError("Unknown terminal collection outcome.")
        for value, length_name, length in (
            (self.baseline_sha256_or_sentinel, "baseline_byte_length", self.baseline_byte_length),
            (self.final_sha256_or_sentinel, "final_byte_length", self.final_byte_length),
        ):
            if value == "MISSING_COLLECTION_V1":
                if length != 0:
                    raise ValueError("Missing collection proof must have zero bytes.")
            else:
                _sha(value, "collection proof")
                _integer(length, length_name, 0, (2**53) - 1)
        _integer(self.committed_item_count, "committed_item_count", 0, 100)
        _sha(self.committed_item_ids_sha256, "committed_item_ids_sha256")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "outcome": self.outcome,
            "baseline_sha256_or_sentinel": self.baseline_sha256_or_sentinel,
            "baseline_byte_length": self.baseline_byte_length,
            "final_sha256_or_sentinel": self.final_sha256_or_sentinel,
            "final_byte_length": self.final_byte_length,
            "committed_item_count": self.committed_item_count,
            "committed_item_ids_sha256": self.committed_item_ids_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TerminalCollectionProof":
        _closed(value, frozenset(cls.__dataclass_fields__), "TerminalCollectionProof")
        result = cls(**value)
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class TerminalManagedImageProof:
    outcome: str
    image_count: int
    aggregate_sha256: str

    def validate(self) -> None:
        if self.outcome not in {"RETAINED", "REMOVED", "NONE"}:
            raise ValueError("Unknown managed-image outcome.")
        _integer(self.image_count, "image_count", 0, 300)
        _sha(self.aggregate_sha256, "aggregate_sha256")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {"outcome": self.outcome, "image_count": self.image_count, "aggregate_sha256": self.aggregate_sha256}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TerminalManagedImageProof":
        _closed(value, frozenset(cls.__dataclass_fields__), "TerminalManagedImageProof")
        result = cls(**value)
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class TerminalCleanupSummary:
    category: str
    result: str
    target_count: int
    receipt_count: int
    intent_generation: int
    completed_generation: int
    aggregate_sha256: str

    def validate(self) -> None:
        if self.category not in {"BASELINE_BACKUP", "SUCCESS_SNAPSHOT", "ROLLBACK_ALL"} or self.result != "COMPLETED":
            raise ValueError("Terminal cleanup summary is invalid.")
        _integer(self.target_count, "target_count", 1, 301)
        if self.receipt_count != self.target_count:
            raise ValueError("Completed cleanup summary must receipt every target.")
        _integer(self.intent_generation, "intent_generation", 0, 4095)
        _integer(self.completed_generation, "completed_generation", self.intent_generation, 4095)
        _sha(self.aggregate_sha256, "aggregate_sha256")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "category": self.category, "result": self.result,
            "target_count": self.target_count, "receipt_count": self.receipt_count,
            "intent_generation": self.intent_generation,
            "completed_generation": self.completed_generation,
            "aggregate_sha256": self.aggregate_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TerminalCleanupSummary":
        _closed(value, frozenset(cls.__dataclass_fields__), "TerminalCleanupSummary")
        result = cls(**value)
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class OperationalChainProof:
    manifest_generation_count: int
    manifest_head_sha256: str
    compaction_commit_generation: int
    compaction_commit_transition_id: str
    compaction_commit_byte_length: int
    compaction_commit_sha256: str
    compaction_commit_object_identity_sha256: str
    owner_record_sha256: str
    owner_token_sha256: str
    operational_directory_identity_sha256: str
    terminal_object_identity_sha256: str
    retirement_manifest_identity_sha256: str
    retirement_manifest_byte_length: int
    retirement_manifest_sha256: str

    def validate(self) -> None:
        _integer(self.manifest_generation_count, "manifest_generation_count", 1, 4095)
        if self.compaction_commit_generation != self.manifest_generation_count:
            raise ValueError("Compaction commit must follow the manifest range.")
        _uuid4(self.compaction_commit_transition_id, "compaction_commit_transition_id")
        _integer(self.compaction_commit_byte_length, "compaction_commit_byte_length", 1, MAX_JSON_BYTES)
        _integer(self.retirement_manifest_byte_length, "retirement_manifest_byte_length", 1, MAX_JSON_BYTES)
        for value in (
            self.manifest_head_sha256, self.compaction_commit_sha256,
            self.compaction_commit_object_identity_sha256, self.owner_record_sha256,
            self.owner_token_sha256, self.operational_directory_identity_sha256,
            self.terminal_object_identity_sha256, self.retirement_manifest_identity_sha256,
            self.retirement_manifest_sha256,
        ):
            _sha(value, "operational chain digest")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OperationalChainProof":
        _closed(value, frozenset(cls.__dataclass_fields__), "OperationalChainProof")
        result = cls(**value)
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class JournalOwnerRecord:
    owner_schema_version: str
    journal_schema_version: str
    import_id: str
    random_ownership_token: str
    created_at: str
    genesis_filename: str
    genesis_sha256: str
    genesis_temporary_token: str
    genesis_temporary_name: str

    def validate(self) -> None:
        if self.owner_schema_version != "1.0":
            raise ValueError("Owner schema is unsupported.")
        if self.journal_schema_version != "2.0":
            raise ValueError("Owner journal schema is unsupported.")
        for value, name in (
            (self.import_id, "import_id"), (self.random_ownership_token, "random_ownership_token"),
            (self.genesis_temporary_token, "genesis_temporary_token"),
        ):
            _uuid4(value, name)
        _timestamp(self.created_at, "created_at")
        _basename(self.genesis_filename, "genesis_filename")
        _sha(self.genesis_sha256, "genesis_sha256")
        _basename(self.genesis_temporary_name, "genesis_temporary_name")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "JournalOwnerRecord":
        _closed(value, frozenset(cls.__dataclass_fields__), "JournalOwnerRecord")
        result = cls(**value)
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class OperationalJournalGeneration:
    """One immutable schema-2 journal generation."""

    journal_schema_version: str
    import_id: str
    random_ownership_token: str
    generation: int
    previous_generation_sha256: str | None
    transition_id: str
    next_generation_token: str | None
    phase: ImportPhase
    resume_phase: ImportPhase | None
    created_at: str
    updated_at: str
    package_sha256: str
    package_version: str
    package_basename: str
    snapshot_byte_length: int
    snapshot_relative_path: str | None
    collection_baseline_sha256_or_sentinel: str
    collection_baseline_byte_length: int
    prospective_collection_byte_length: int | None
    prospective_collection_sha256: str | None
    selected_source_coin_ids: tuple[str, ...]
    desktop_item_ids: tuple[str, ...]
    import_root_relative_path: str
    expected_image_inventory: tuple[ExpectedImageEvidence, ...]
    verified_image_inventory: tuple[VerifiedImageEvidence, ...]
    committed_collection_item_ids: tuple[str, ...]
    proposed_count: int
    imported_count: int
    skipped_count: int
    collection_publication: str
    collection_temporary_artifact: CollectionPublicationArtifact | None
    collection_backup_artifact: CollectionPublicationArtifact | None
    cleanup_operations: tuple[CleanupOperation, ...]
    pending_terminal_audit: Mapping[str, Any] | None
    compaction: TerminalCompaction | None
    error_category: str | None
    recovery_attempt_count: int

    def validate(self) -> None:
        if self.journal_schema_version != "2.0":
            raise ValueError("Operational journal schema is unsupported.")
        _uuid4(self.import_id, "import_id")
        _uuid4(self.random_ownership_token, "random_ownership_token")
        _integer(self.generation, "generation", 0, 4095)
        if self.generation == 0:
            if self.previous_generation_sha256 is not None:
                raise ValueError("Genesis cannot have a previous hash.")
        else:
            _sha(self.previous_generation_sha256, "previous_generation_sha256")
        _uuid4(self.transition_id, "transition_id")
        if self.next_generation_token is not None:
            _uuid4(self.next_generation_token, "next_generation_token")
        if self.phase in {ImportPhase.SUCCEEDED, ImportPhase.ROLLED_BACK, ImportPhase.CANCELLED}:
            raise ValueError("Terminal outcomes are not operational phases in schema 2.")
        if self.phase is ImportPhase.COMPACTING and self.compaction is not None and self.compaction.status is TerminalCompactionStatus.READY_FOR_TERMINAL:
            if self.next_generation_token is not None:
                raise ValueError("Final H must have a null next-generation token.")
        elif self.next_generation_token is None:
            raise ValueError("Every non-final operational generation requires a next token.")
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        _sha(self.package_sha256, "package_sha256")
        if self.package_version != "1.0":
            raise ValueError("Package version is unsupported.")
        _basename(self.package_basename, "package_basename")
        _integer(self.snapshot_byte_length, "snapshot_byte_length", 1, 256 * 1024 * 1024)
        if self.snapshot_relative_path is not None and (not self.snapshot_relative_path or self.snapshot_relative_path.startswith(("/", "\\"))):
            raise ValueError("Snapshot path must be relative.")
        if self.collection_baseline_sha256_or_sentinel == "MISSING_COLLECTION_V1":
            if self.collection_baseline_byte_length != 0:
                raise ValueError("Missing baseline must have zero bytes.")
        else:
            _sha(self.collection_baseline_sha256_or_sentinel, "collection baseline")
        _integer(self.collection_baseline_byte_length, "collection_baseline_byte_length", 0, (2**53) - 1)
        if (self.prospective_collection_byte_length is None) != (self.prospective_collection_sha256 is None):
            raise ValueError("Prospective collection commitment is an atomic pair.")
        if self.prospective_collection_byte_length is not None:
            _integer(self.prospective_collection_byte_length, "prospective_collection_byte_length", 0, (2**53) - 1)
            _sha(self.prospective_collection_sha256, "prospective_collection_sha256")
        if not 1 <= len(self.selected_source_coin_ids) <= 100 or len(set(self.selected_source_coin_ids)) != len(self.selected_source_coin_ids):
            raise ValueError("Selected source IDs are invalid.")
        if len(self.desktop_item_ids) != len(self.selected_source_coin_ids) or len(set(self.desktop_item_ids)) != len(self.desktop_item_ids):
            raise ValueError("Desktop IDs are invalid.")
        for identifier in self.desktop_item_ids:
            _uuid4(identifier, "desktop_item_id")
        if not self.expected_image_inventory or len(self.expected_image_inventory) > 300:
            raise ValueError("Expected image inventory is outside bounds.")
        for image in self.expected_image_inventory:
            image.validate()
        for image in self.verified_image_inventory:
            image.validate()
        expected_paths = tuple(image.relative_path for image in self.expected_image_inventory)
        verified_paths = tuple(image.relative_path for image in self.verified_image_inventory)
        if verified_paths != expected_paths[: len(verified_paths)]:
            raise ValueError("Verified image inventory must be an ordered prefix.")
        if self.committed_collection_item_ids not in ((), self.desktop_item_ids):
            raise ValueError("Committed IDs must be empty or complete.")
        for value, name in ((self.proposed_count, "proposed_count"), (self.imported_count, "imported_count"), (self.skipped_count, "skipped_count")):
            _integer(value, name, 0, 100)
        if self.proposed_count < 1 or self.skipped_count != self.proposed_count - len(self.selected_source_coin_ids) or self.imported_count != len(self.committed_collection_item_ids):
            raise ValueError("Import counts are inconsistent.")
        if self.collection_publication not in {"NONE", "INTENT", "VERIFIED"}:
            raise ValueError("Collection publication state is invalid.")
        for artifact in (self.collection_temporary_artifact, self.collection_backup_artifact):
            if artifact is not None:
                artifact.validate()
        if len(self.cleanup_operations) > 3:
            raise ValueError("Too many cleanup operations.")
        for operation in self.cleanup_operations:
            operation.validate()
            if (
                operation.intent_generation > self.generation
                or any(
                    receipt.removal_generation > self.generation
                    for receipt in operation.receipts
                )
                or (
                    operation.completed_generation is not None
                    and operation.completed_generation > self.generation
                )
            ):
                raise ValueError("Cleanup evidence cannot reference a future generation.")
        if any(
            operation.status is not CleanupStatus.COMPLETE
            for operation in self.cleanup_operations[:-1]
        ):
            raise ValueError("Only the final cleanup operation may be incomplete.")
        if self.pending_terminal_audit is not None and not isinstance(
            self.pending_terminal_audit, Mapping
        ):
            raise ValueError("Pending terminal audit must be an object or null.")
        verified_complete = len(self.verified_image_inventory) == len(
            self.expected_image_inventory
        ) and all(
            (
                verified.relative_path,
                verified.role,
                verified.byte_length,
                verified.sha256,
                verified.media_type,
                verified.width,
                verified.height,
            )
            == (
                expected.relative_path,
                expected.role,
                expected.byte_length,
                expected.sha256,
                expected.media_type,
                expected.width,
                expected.height,
            )
            for expected, verified in zip(
                self.expected_image_inventory,
                self.verified_image_inventory,
                strict=True,
            )
        )
        if self.phase is ImportPhase.PREPARED:
            if (
                self.verified_image_inventory
                or self.prospective_collection_sha256 is not None
                or self.collection_publication != "NONE"
                or self.collection_temporary_artifact is not None
                or self.collection_backup_artifact is not None
                or self.cleanup_operations
                or self.pending_terminal_audit is not None
                or self.committed_collection_item_ids
            ):
                raise ValueError("PREPARED contains later-phase evidence.")
        elif self.phase is ImportPhase.COPYING_IMAGES:
            if (
                self.prospective_collection_sha256 is not None
                or self.collection_publication != "NONE"
                or self.collection_temporary_artifact is not None
                or self.collection_backup_artifact is not None
                or self.cleanup_operations
                or self.pending_terminal_audit is not None
                or self.committed_collection_item_ids
            ):
                raise ValueError("COPYING_IMAGES contains later-phase evidence.")
        elif self.phase is ImportPhase.FILES_READY:
            if (
                not verified_complete
                or self.prospective_collection_sha256 is not None
                or self.collection_publication != "NONE"
                or self.collection_temporary_artifact is not None
                or self.collection_backup_artifact is not None
                or self.cleanup_operations
                or self.pending_terminal_audit is not None
                or self.committed_collection_item_ids
            ):
                raise ValueError("FILES_READY evidence is incomplete or invalid.")
        elif self.phase is ImportPhase.COMMITTING_COLLECTION:
            if (
                not verified_complete
                or self.prospective_collection_sha256 is None
                or self.collection_publication != "INTENT"
                or self.collection_temporary_artifact is None
                or self.committed_collection_item_ids
                or self.cleanup_operations
                or self.pending_terminal_audit is not None
            ):
                raise ValueError("COMMITTING_COLLECTION evidence is incomplete.")
        elif self.phase is ImportPhase.COLLECTION_COMMITTED:
            if (
                not verified_complete
                or self.prospective_collection_sha256 is None
                or self.collection_publication != "VERIFIED"
                or self.collection_temporary_artifact is None
                or self.collection_temporary_artifact.state
                is not CollectionPublicationState.PUBLISHED
                or self.committed_collection_item_ids != self.desktop_item_ids
                or self.pending_terminal_audit is None
            ):
                raise ValueError("COLLECTION_COMMITTED evidence is incomplete.")
        if self.phase in {
            ImportPhase.RECOVERY_REQUIRED,
            ImportPhase.ROLLBACK_FAILED,
        }:
            if self.resume_phase is None:
                raise ValueError("Recovery failure requires a resume phase.")
        elif self.resume_phase is not None:
            raise ValueError("Normal progress cannot contain a resume phase.")
        if self.compaction is not None:
            self.compaction.validate()
        if self.phase is ImportPhase.COMPACTING:
            if self.compaction is None or self.snapshot_relative_path is not None or self.collection_temporary_artifact is not None or self.collection_backup_artifact is not None:
                raise ValueError("Compacting phase contains operational artifact paths.")
            if (
                not self.cleanup_operations
                or any(
                    operation.status is not CleanupStatus.COMPLETE
                    for operation in self.cleanup_operations
                )
                or self.pending_terminal_audit is None
            ):
                raise ValueError("Compaction requires complete cleanup and audit evidence.")
        elif self.compaction is not None:
            raise ValueError("Compaction evidence is valid only while compacting.")
        if self.phase in {ImportPhase.RECOVERY_REQUIRED, ImportPhase.ROLLBACK_FAILED}:
            if self.error_category is None:
                raise ValueError("Recovery failure requires an error category.")
        elif self.error_category is not None:
            raise ValueError("Normal operational progress cannot contain an error.")
        _integer(self.recovery_attempt_count, "recovery_attempt_count", 0, (2**53) - 1)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "journal_schema_version": self.journal_schema_version,
            "import_id": self.import_id, "random_ownership_token": self.random_ownership_token,
            "generation": self.generation, "previous_generation_sha256": self.previous_generation_sha256,
            "transition_id": self.transition_id, "next_generation_token": self.next_generation_token,
            "phase": self.phase.value, "resume_phase": None if self.resume_phase is None else self.resume_phase.value,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "package_sha256": self.package_sha256, "package_version": self.package_version,
            "package_basename": self.package_basename, "snapshot_byte_length": self.snapshot_byte_length,
            "snapshot_relative_path": self.snapshot_relative_path,
            "collection_baseline_sha256_or_sentinel": self.collection_baseline_sha256_or_sentinel,
            "collection_baseline_byte_length": self.collection_baseline_byte_length,
            "prospective_collection_byte_length": self.prospective_collection_byte_length,
            "prospective_collection_sha256": self.prospective_collection_sha256,
            "selected_source_coin_ids": list(self.selected_source_coin_ids),
            "desktop_item_ids": list(self.desktop_item_ids),
            "import_root_relative_path": self.import_root_relative_path,
            "expected_image_inventory": [item.to_dict() for item in self.expected_image_inventory],
            "verified_image_inventory": [item.to_dict() for item in self.verified_image_inventory],
            "committed_collection_item_ids": list(self.committed_collection_item_ids),
            "proposed_count": self.proposed_count, "imported_count": self.imported_count,
            "skipped_count": self.skipped_count, "collection_publication": self.collection_publication,
            "collection_temporary_artifact": None if self.collection_temporary_artifact is None else self.collection_temporary_artifact.to_dict(),
            "collection_backup_artifact": None if self.collection_backup_artifact is None else self.collection_backup_artifact.to_dict(),
            "cleanup_operations": [operation.to_dict() for operation in self.cleanup_operations],
            "pending_terminal_audit": None if self.pending_terminal_audit is None else dict(self.pending_terminal_audit),
            "compaction": None if self.compaction is None else self.compaction.to_dict(),
            "error_category": self.error_category,
            "recovery_attempt_count": self.recovery_attempt_count,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OperationalJournalGeneration":
        _closed(value, frozenset(cls.__dataclass_fields__), "OperationalJournalGeneration")
        for key in ("selected_source_coin_ids", "desktop_item_ids", "expected_image_inventory", "verified_image_inventory", "committed_collection_item_ids", "cleanup_operations"):
            if not isinstance(value[key], list):
                raise ValueError(f"{key} must be an array.")
        result = cls(
            journal_schema_version=value["journal_schema_version"], import_id=value["import_id"],
            random_ownership_token=value["random_ownership_token"], generation=value["generation"],
            previous_generation_sha256=value["previous_generation_sha256"], transition_id=value["transition_id"],
            next_generation_token=value["next_generation_token"], phase=ImportPhase(value["phase"]),
            resume_phase=None if value["resume_phase"] is None else ImportPhase(value["resume_phase"]),
            created_at=value["created_at"], updated_at=value["updated_at"], package_sha256=value["package_sha256"],
            package_version=value["package_version"], package_basename=value["package_basename"],
            snapshot_byte_length=value["snapshot_byte_length"], snapshot_relative_path=value["snapshot_relative_path"],
            collection_baseline_sha256_or_sentinel=value["collection_baseline_sha256_or_sentinel"],
            collection_baseline_byte_length=value["collection_baseline_byte_length"],
            prospective_collection_byte_length=value["prospective_collection_byte_length"],
            prospective_collection_sha256=value["prospective_collection_sha256"],
            selected_source_coin_ids=tuple(value["selected_source_coin_ids"]), desktop_item_ids=tuple(value["desktop_item_ids"]),
            import_root_relative_path=value["import_root_relative_path"],
            expected_image_inventory=tuple(ExpectedImageEvidence.from_dict(item) for item in value["expected_image_inventory"]),
            verified_image_inventory=tuple(VerifiedImageEvidence.from_dict(item) for item in value["verified_image_inventory"]),
            committed_collection_item_ids=tuple(value["committed_collection_item_ids"]),
            proposed_count=value["proposed_count"], imported_count=value["imported_count"], skipped_count=value["skipped_count"],
            collection_publication=value["collection_publication"],
            collection_temporary_artifact=None if value["collection_temporary_artifact"] is None else CollectionPublicationArtifact.from_dict(value["collection_temporary_artifact"]),
            collection_backup_artifact=None if value["collection_backup_artifact"] is None else CollectionPublicationArtifact.from_dict(value["collection_backup_artifact"]),
            cleanup_operations=tuple(CleanupOperation.from_dict(item) for item in value["cleanup_operations"]),
            pending_terminal_audit=value["pending_terminal_audit"],
            compaction=None if value["compaction"] is None else TerminalCompaction.from_dict(value["compaction"]),
            error_category=value["error_category"], recovery_attempt_count=value["recovery_attempt_count"],
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class TerminalHistoryRecord:
    """Privacy-complete terminal authority published after operational cleanup."""

    terminal_schema_version: str
    import_id: str
    final_phase: ImportResult
    result: ImportResult
    transaction_created_at: str
    completed_at: str
    package_sha256: str
    package_version: str
    package_basename: str
    proposed_count: int
    imported_count: int
    skipped_count: int
    collection_proof: TerminalCollectionProof
    managed_image_proof: TerminalManagedImageProof
    cleanup_summaries: tuple[TerminalCleanupSummary, ...]
    outcome_payload_sha256: str
    operational_chain_proof: OperationalChainProof
    audit: Mapping[str, Any]
    error_category: str | None

    def outcome_payload(self) -> dict[str, Any]:
        """Return the exact path-free field set committed by H."""

        return {
            "terminal_schema_version": self.terminal_schema_version,
            "import_id": self.import_id,
            "final_phase": self.final_phase.value,
            "result": self.result.value,
            "transaction_created_at": self.transaction_created_at,
            "completed_at": self.completed_at,
            "package_sha256": self.package_sha256,
            "package_version": self.package_version,
            "package_basename": self.package_basename,
            "proposed_count": self.proposed_count,
            "imported_count": self.imported_count,
            "skipped_count": self.skipped_count,
            "collection_proof": self.collection_proof.to_dict(),
            "managed_image_proof": self.managed_image_proof.to_dict(),
            "cleanup_summaries": [summary.to_dict() for summary in self.cleanup_summaries],
            "audit": dict(self.audit),
            "error_category": self.error_category,
        }

    def validate(self) -> None:
        from hashlib import sha256
        from ._json import canonical_json_bytes

        if self.terminal_schema_version != "1.0":
            raise ValueError("Terminal history schema is unsupported.")
        _uuid4(self.import_id, "import_id")
        if self.final_phase not in {ImportResult.SUCCEEDED, ImportResult.ROLLED_BACK, ImportResult.CANCELLED} or self.result is not self.final_phase:
            raise ValueError("Terminal history outcome is invalid.")
        _sha(self.package_sha256, "package_sha256")
        if self.package_version != "1.0":
            raise ValueError("Terminal package version is unsupported.")
        _basename(self.package_basename, "package_basename")
        for value, name in ((self.proposed_count, "proposed_count"), (self.imported_count, "imported_count"), (self.skipped_count, "skipped_count")):
            _integer(value, name, 0, 100)
        if self.final_phase is ImportResult.SUCCEEDED:
            if self.imported_count + self.skipped_count != self.proposed_count:
                raise ValueError("Successful terminal counts are inconsistent.")
        elif self.imported_count != 0 or self.skipped_count > self.proposed_count:
            raise ValueError("Non-success terminal counts are inconsistent.")
        self.collection_proof.validate()
        self.managed_image_proof.validate()
        if not 1 <= len(self.cleanup_summaries) <= 3:
            raise ValueError("Terminal cleanup summaries are outside bounds.")
        for summary in self.cleanup_summaries:
            summary.validate()
        self.operational_chain_proof.validate()
        if not isinstance(self.audit, Mapping):
            raise ValueError("Sanitized terminal audit must be an object.")
        audit_keys = frozenset(
            {
                "audit_schema_version", "import_id", "started_at", "completed_at",
                "package_filename_basename", "package_sha256", "schema",
                "package_version", "created_by", "created_with", "exported_at",
                "session_id", "session_name", "session_description", "session_date",
                "session_created_at", "session_updated_at", "coin_provenance",
                "proposed_count", "imported_count", "skipped_count", "phase",
                "final_status", "error_category",
            }
        )
        _closed(self.audit, audit_keys, "SanitizedTerminalAudit")
        if self.audit["audit_schema_version"] != "2.0":
            raise ValueError("Sanitized terminal audit schema is unsupported.")
        if (
            self.audit["import_id"] != self.import_id
            or self.audit["package_filename_basename"] != self.package_basename
            or self.audit["package_sha256"] != self.package_sha256
            or self.audit["package_version"] != self.package_version
            or self.audit["proposed_count"] != self.proposed_count
            or self.audit["imported_count"] != self.imported_count
            or self.audit["skipped_count"] != self.skipped_count
            or self.audit["phase"] != self.final_phase.value
            or self.audit["final_status"] != self.result.value
            or self.audit["error_category"] != self.error_category
        ):
            raise ValueError("Sanitized terminal audit does not match its record.")
        _timestamp(self.audit["started_at"], "audit started_at")
        _timestamp(self.audit["completed_at"], "audit completed_at")
        provenance = self.audit["coin_provenance"]
        if not isinstance(provenance, list) or len(provenance) != self.proposed_count:
            raise ValueError("Sanitized coin provenance is inconsistent.")
        coin_keys = frozenset(
            {
                "source_coin_id", "desktop_item_id", "decision", "source_position",
                "mint", "composition", "is_bullion", "actual_silver_weight_oz",
                "source_created_at", "source_updated_at", "source_quantity",
                "image_role_hashes",
            }
        )
        for position, coin in enumerate(provenance):
            if not isinstance(coin, Mapping):
                raise ValueError("Sanitized coin provenance must contain objects.")
            _closed(coin, coin_keys, "SanitizedTerminalCoin")
            if coin["source_position"] != position:
                raise ValueError("Sanitized coin positions must be contiguous.")
        prohibited = {
            "managed_image_paths", "snapshot_relative_path", "temporary_path",
            "backup_path", "recovery_path", "ownership_token", "lock_path",
        }
        stack: list[Any] = [self.audit]
        while stack:
            value = stack.pop()
            if isinstance(value, Mapping):
                if prohibited.intersection(value):
                    raise ValueError("Sanitized terminal audit contains operational paths.")
                stack.extend(value.values())
            elif isinstance(value, (list, tuple)):
                stack.extend(value)
        expected_payload = sha256(canonical_json_bytes(self.outcome_payload())).hexdigest()
        if self.outcome_payload_sha256 != expected_payload:
            raise ValueError("Terminal outcome payload commitment is invalid.")
        if self.final_phase is ImportResult.SUCCEEDED:
            if self.error_category is not None or self.collection_proof.outcome != "PUBLISHED" or self.managed_image_proof.outcome != "RETAINED":
                raise ValueError("Successful terminal proof is inconsistent.")
        elif self.collection_proof.outcome != "UNCHANGED" or self.managed_image_proof.outcome not in {"REMOVED", "NONE"}:
            raise ValueError("Non-success terminal proof is inconsistent.")
        if self.final_phase is ImportResult.CANCELLED and self.error_category is not None:
            raise ValueError("Cancelled terminal history cannot contain an error.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            **self.outcome_payload(),
            "outcome_payload_sha256": self.outcome_payload_sha256,
            "operational_chain_proof": self.operational_chain_proof.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TerminalHistoryRecord":
        _closed(value, frozenset(cls.__dataclass_fields__), "TerminalHistoryRecord")
        if not isinstance(value["cleanup_summaries"], list):
            raise ValueError("Terminal cleanup summaries must be an array.")
        if not isinstance(value["audit"], Mapping):
            raise ValueError("Sanitized terminal audit must be an object.")
        result = cls(
            terminal_schema_version=value["terminal_schema_version"],
            import_id=value["import_id"],
            final_phase=ImportResult(value["final_phase"]),
            result=ImportResult(value["result"]),
            transaction_created_at=value["transaction_created_at"],
            completed_at=value["completed_at"],
            package_sha256=value["package_sha256"],
            package_version=value["package_version"],
            package_basename=value["package_basename"],
            proposed_count=value["proposed_count"],
            imported_count=value["imported_count"],
            skipped_count=value["skipped_count"],
            collection_proof=TerminalCollectionProof.from_dict(
                value["collection_proof"]
            ),
            managed_image_proof=TerminalManagedImageProof.from_dict(
                value["managed_image_proof"]
            ),
            cleanup_summaries=tuple(
                TerminalCleanupSummary.from_dict(item)
                for item in value["cleanup_summaries"]
            ),
            outcome_payload_sha256=value["outcome_payload_sha256"],
            operational_chain_proof=OperationalChainProof.from_dict(
                value["operational_chain_proof"]
            ),
            audit=dict(value["audit"]),
            error_category=value["error_category"],
        )
        result.validate()
        return result
