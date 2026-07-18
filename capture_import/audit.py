"""Immutable terminal audit DTOs and in-memory JSON serialization."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from .enums import (
    Composition,
    DuplicateDecision,
    ErrorCategory,
    HISTORY_PHASES,
    ImageRole,
    ImportPhase,
    ImportRecordOutcome,
    ImportResult,
)
from .limits import (
    AUDIT_SCHEMA_VERSION,
    MAX_COINS_PER_PACKAGE,
    MAX_JSON_BYTES,
    MAX_QUANTITY,
    SUPPORTED_SCHEMA,
    SUPPORTED_SCHEMA_VERSION,
)
from .models import (
    _parse_decimal_text,
    _enum_value,
    _require_boolean,
    _require_fields,
    _require_integer,
    _require_object,
    _require_optional_string,
    _require_string,
    _validate_basename,
    _validate_date,
    _validate_optional_date,
    _validate_relative_path,
    _validate_sha256,
    _validate_timestamp,
    _validate_uuid,
)

_AUDIT_COIN_FIELDS = frozenset(
    {
        "source_coin_id",
        "desktop_item_id",
        "decision",
        "source_position",
        "mint",
        "composition",
        "is_bullion",
        "actual_silver_weight_oz",
        "source_created_at",
        "source_updated_at",
        "source_quantity",
        "image_role_hashes",
        "managed_image_paths",
    }
)

_AUDIT_SESSION_FIELDS = frozenset(
    {
        "audit_schema_version",
        "import_id",
        "started_at",
        "completed_at",
        "package_filename_basename",
        "package_sha256",
        "schema",
        "package_version",
        "created_by",
        "created_with",
        "exported_at",
        "session_id",
        "session_name",
        "session_description",
        "session_date",
        "session_created_at",
        "session_updated_at",
        "coin_provenance",
        "proposed_count",
        "imported_count",
        "skipped_count",
        "phase",
        "final_status",
        "error_category",
    }
)


def _validate_role_pairs(
    pairs: tuple[tuple[ImageRole, str], ...], field_name: str, *, paths: bool
) -> None:
    if not isinstance(pairs, tuple):
        raise ValueError(f"{field_name} must be an immutable tuple.")
    roles: list[ImageRole] = []
    for pair in pairs:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ValueError(f"{field_name} must contain role/value pairs.")
        role, value = pair
        if not isinstance(role, ImageRole):
            raise ValueError(f"{field_name} keys must be ImageRole values.")
        if paths:
            _validate_relative_path(value, field_name)
        else:
            _validate_sha256(value, field_name)
        roles.append(role)
    if len(set(roles)) != len(roles):
        raise ValueError(f"{field_name} contains duplicate image roles.")
    if pairs != tuple(sorted(pairs, key=lambda item: item[0].value)):
        raise ValueError(f"{field_name} role pairs must use deterministic ordering.")


def _pairs_from_object(
    value: Any, field_name: str, *, paths: bool
) -> tuple[tuple[ImageRole, str], ...]:
    data = _require_object(value, field_name)
    pairs: list[tuple[ImageRole, str]] = []
    for raw_role, raw_value in data.items():
        role = _enum_value(ImageRole, raw_role, field_name)
        text = _require_string(raw_value, field_name)
        pairs.append((role, text))
    result = tuple(sorted(pairs, key=lambda item: item[0].value))
    _validate_role_pairs(result, field_name, paths=paths)
    return result


@dataclass(frozen=True, slots=True)
class AuditCoin:
    """Sanitized provenance for one proposed package coin."""

    source_coin_id: str
    desktop_item_id: str | None
    decision: DuplicateDecision
    source_position: int
    mint: str
    composition: Composition
    is_bullion: bool
    actual_silver_weight_oz: str | None
    source_created_at: str
    source_updated_at: str
    source_quantity: int
    image_role_hashes: tuple[tuple[ImageRole, str], ...]
    managed_image_paths: tuple[tuple[ImageRole, str], ...]

    @property
    def outcome(self) -> ImportRecordOutcome:
        """Derive final outcome without changing the collector's decision."""

        if self.decision is DuplicateDecision.SKIP:
            return ImportRecordOutcome.SKIPPED
        if self.desktop_item_id is None and not self.managed_image_paths:
            return ImportRecordOutcome.NOT_COMMITTED
        return ImportRecordOutcome.COMMITTED

    def validate(self) -> None:
        _require_string(self.source_coin_id, "source_coin_id")
        if not isinstance(self.decision, DuplicateDecision):
            raise ValueError("decision must be a DuplicateDecision.")
        _require_integer(self.source_position, "source_position")
        _require_string(self.mint, "mint", allow_empty=True)
        if not isinstance(self.composition, Composition):
            raise ValueError("composition must be a Composition.")
        _require_boolean(self.is_bullion, "is_bullion")
        if self.actual_silver_weight_oz is not None:
            _parse_decimal_text(
                self.actual_silver_weight_oz, "actual_silver_weight_oz"
            )
        _validate_timestamp(self.source_created_at, "source_created_at")
        _validate_timestamp(self.source_updated_at, "source_updated_at")
        _require_integer(
            self.source_quantity,
            "source_quantity",
            minimum=1,
            maximum=MAX_QUANTITY,
        )
        _validate_role_pairs(
            self.image_role_hashes, "image_role_hashes", paths=False
        )
        hash_roles = {role for role, _ in self.image_role_hashes}
        if not {ImageRole.FRONT, ImageRole.REVERSE}.issubset(hash_roles):
            raise ValueError("image_role_hashes must contain front and reverse.")
        _validate_role_pairs(
            self.managed_image_paths, "managed_image_paths", paths=True
        )
        managed_roles = {role for role, _ in self.managed_image_paths}
        if self.decision is DuplicateDecision.IMPORT_AS_NEW:
            if self.desktop_item_id is None and self.managed_image_paths:
                raise ValueError(
                    "Uncommitted audit coins must not have managed image paths."
                )
            if self.desktop_item_id is not None:
                _validate_uuid(self.desktop_item_id, "desktop_item_id")
            if self.desktop_item_id is not None and managed_roles != hash_roles:
                raise ValueError(
                    "Imported audit coins require one managed path per image hash."
                )
            if self.desktop_item_id is not None and not self.managed_image_paths:
                raise ValueError(
                    "Committed audit coins require managed image paths."
                )
        else:
            if self.desktop_item_id is not None:
                raise ValueError("Skipped audit coins must not have a desktop_item_id.")
            if self.managed_image_paths:
                raise ValueError("Skipped audit coins must not have managed image paths.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "source_coin_id": self.source_coin_id,
            "desktop_item_id": self.desktop_item_id,
            "decision": self.decision.value,
            "source_position": self.source_position,
            "mint": self.mint,
            "composition": self.composition.value,
            "is_bullion": self.is_bullion,
            "actual_silver_weight_oz": self.actual_silver_weight_oz,
            "source_created_at": self.source_created_at,
            "source_updated_at": self.source_updated_at,
            "source_quantity": self.source_quantity,
            "image_role_hashes": {
                role.value: digest for role, digest in self.image_role_hashes
            },
            "managed_image_paths": {
                role.value: path for role, path in self.managed_image_paths
            },
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AuditCoin":
        data = _require_object(value, "AuditCoin")
        _require_fields(data, _AUDIT_COIN_FIELDS, "AuditCoin", allow_extra=False)
        desktop_item_id = _require_optional_string(
            data["desktop_item_id"], "desktop_item_id", max_chars=36
        )
        actual_silver_weight_oz = _require_optional_string(
            data["actual_silver_weight_oz"], "actual_silver_weight_oz", max_chars=64
        )
        result = cls(
            source_coin_id=_require_string(data["source_coin_id"], "source_coin_id"),
            desktop_item_id=desktop_item_id,
            decision=_enum_value(DuplicateDecision, data["decision"], "decision"),
            source_position=_require_integer(data["source_position"], "source_position"),
            mint=_require_string(data["mint"], "mint", allow_empty=True),
            composition=_enum_value(Composition, data["composition"], "composition"),
            is_bullion=_require_boolean(data["is_bullion"], "is_bullion"),
            actual_silver_weight_oz=actual_silver_weight_oz,
            source_created_at=_require_string(
                data["source_created_at"], "source_created_at"
            ),
            source_updated_at=_require_string(
                data["source_updated_at"], "source_updated_at"
            ),
            source_quantity=_require_integer(
                data["source_quantity"],
                "source_quantity",
                minimum=1,
                maximum=MAX_QUANTITY,
            ),
            image_role_hashes=_pairs_from_object(
                data["image_role_hashes"], "image_role_hashes", paths=False
            ),
            managed_image_paths=_pairs_from_object(
                data["managed_image_paths"], "managed_image_paths", paths=True
            ),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class AuditSession:
    """Complete sanitized terminal audit for one import attempt."""

    audit_schema_version: str
    import_id: str
    started_at: str
    completed_at: str
    package_filename_basename: str
    package_sha256: str
    schema: str
    package_version: str
    created_by: str
    created_with: str
    exported_at: str
    session_id: str
    session_name: str
    session_description: str
    session_date: str | None
    session_created_at: str
    session_updated_at: str
    coin_provenance: tuple[AuditCoin, ...]
    proposed_count: int
    imported_count: int
    skipped_count: int
    phase: ImportPhase
    final_status: ImportResult
    error_category: ErrorCategory | None

    def validate(self) -> None:
        if self.audit_schema_version != AUDIT_SCHEMA_VERSION:
            raise ValueError("audit_schema_version is not supported.")
        _validate_uuid(self.import_id, "import_id")
        _validate_timestamp(self.started_at, "started_at")
        _validate_timestamp(self.completed_at, "completed_at")
        _validate_basename(
            self.package_filename_basename, "package_filename_basename"
        )
        if not self.package_filename_basename.lower().endswith(".ca-package"):
            raise ValueError("package_filename_basename must end with .ca-package.")
        _validate_sha256(self.package_sha256, "package_sha256")
        if self.schema != SUPPORTED_SCHEMA:
            raise ValueError("schema is not supported.")
        if self.package_version != SUPPORTED_SCHEMA_VERSION:
            raise ValueError("package_version is not supported.")
        _require_string(self.created_by, "created_by")
        _require_string(self.created_with, "created_with")
        _validate_timestamp(self.exported_at, "exported_at")
        _require_string(self.session_id, "session_id")
        _require_string(self.session_name, "session_name")
        _require_string(
            self.session_description, "session_description", allow_empty=True
        )
        _validate_optional_date(self.session_date, "session_date")
        _validate_timestamp(self.session_created_at, "session_created_at")
        _validate_timestamp(self.session_updated_at, "session_updated_at")
        if not isinstance(self.coin_provenance, tuple):
            raise ValueError("coin_provenance must be an immutable tuple.")
        for coin in self.coin_provenance:
            if not isinstance(coin, AuditCoin):
                raise ValueError("coin_provenance must contain AuditCoin values.")
            coin.validate()
        source_ids = tuple(coin.source_coin_id for coin in self.coin_provenance)
        positions = tuple(coin.source_position for coin in self.coin_provenance)
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("coin_provenance source IDs must be unique.")
        if positions != tuple(range(len(self.coin_provenance))):
            raise ValueError(
                "coin_provenance positions must be contiguous and begin at zero."
            )
        proposed = _require_integer(
            self.proposed_count,
            "proposed_count",
            maximum=MAX_COINS_PER_PACKAGE,
        )
        imported = _require_integer(
            self.imported_count,
            "imported_count",
            maximum=MAX_COINS_PER_PACKAGE,
        )
        skipped = _require_integer(
            self.skipped_count,
            "skipped_count",
            maximum=MAX_COINS_PER_PACKAGE,
        )
        if proposed != len(self.coin_provenance):
            raise ValueError("proposed_count does not agree with coin_provenance.")
        actual_imported = sum(
            coin.outcome is ImportRecordOutcome.COMMITTED
            for coin in self.coin_provenance
        )
        actual_skipped = sum(
            coin.outcome is ImportRecordOutcome.SKIPPED
            for coin in self.coin_provenance
        )
        if actual_imported != imported:
            raise ValueError("Audit decision totals do not agree with imported_count.")
        if actual_skipped != skipped:
            raise ValueError("Audit decision totals do not agree with skipped_count.")
        if not isinstance(self.phase, ImportPhase) or self.phase not in HISTORY_PHASES:
            raise ValueError("phase must be a completed audit-history phase.")
        if self.phase is ImportPhase.SUCCEEDED:
            if any(
                coin.outcome is ImportRecordOutcome.NOT_COMMITTED
                for coin in self.coin_provenance
            ):
                raise ValueError(
                    "Successful audits cannot contain selected, uncommitted records."
                )
            if imported + skipped != proposed:
                raise ValueError("Successful audit counts must total proposed_count.")
        elif imported != 0 or any(
            coin.outcome is ImportRecordOutcome.COMMITTED
            for coin in self.coin_provenance
        ):
            raise ValueError(
                "Rolled-back and cancelled audits cannot retain committed records."
            )
        expected_status = ImportResult(self.phase.value)
        if self.final_status is not expected_status:
            raise ValueError("final_status does not agree with phase.")
        if self.error_category is not None and not isinstance(
            self.error_category, ErrorCategory
        ):
            raise ValueError("error_category must be an ErrorCategory or null.")
        if self.phase is ImportPhase.SUCCEEDED and self.error_category is not None:
            raise ValueError("A successful audit must not contain an error category.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "audit_schema_version": self.audit_schema_version,
            "import_id": self.import_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "package_filename_basename": self.package_filename_basename,
            "package_sha256": self.package_sha256,
            "schema": self.schema,
            "package_version": self.package_version,
            "created_by": self.created_by,
            "created_with": self.created_with,
            "exported_at": self.exported_at,
            "session_id": self.session_id,
            "session_name": self.session_name,
            "session_description": self.session_description,
            "session_date": self.session_date,
            "session_created_at": self.session_created_at,
            "session_updated_at": self.session_updated_at,
            "coin_provenance": [coin.to_dict() for coin in self.coin_provenance],
            "proposed_count": self.proposed_count,
            "imported_count": self.imported_count,
            "skipped_count": self.skipped_count,
            "phase": self.phase.value,
            "final_status": self.final_status.value,
            "error_category": (
                None if self.error_category is None else self.error_category.value
            ),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AuditSession":
        data = _require_object(value, "AuditSession")
        _require_fields(data, _AUDIT_SESSION_FIELDS, "AuditSession", allow_extra=False)
        if not isinstance(data["coin_provenance"], list):
            raise ValueError("coin_provenance must be an array.")
        error_category = (
            None
            if data["error_category"] is None
            else _enum_value(ErrorCategory, data["error_category"], "error_category")
        )
        result = cls(
            audit_schema_version=_require_string(
                data["audit_schema_version"], "audit_schema_version"
            ),
            import_id=_require_string(data["import_id"], "import_id"),
            started_at=_require_string(data["started_at"], "started_at"),
            completed_at=_require_string(data["completed_at"], "completed_at"),
            package_filename_basename=_require_string(
                data["package_filename_basename"], "package_filename_basename"
            ),
            package_sha256=_require_string(data["package_sha256"], "package_sha256"),
            schema=_require_string(data["schema"], "schema"),
            package_version=_require_string(data["package_version"], "package_version"),
            created_by=_require_string(data["created_by"], "created_by"),
            created_with=_require_string(data["created_with"], "created_with"),
            exported_at=_require_string(data["exported_at"], "exported_at"),
            session_id=_require_string(data["session_id"], "session_id"),
            session_name=_require_string(data["session_name"], "session_name"),
            session_description=_require_string(
                data["session_description"], "session_description", allow_empty=True
            ),
            session_date=_validate_optional_date(data["session_date"], "session_date"),
            session_created_at=_require_string(
                data["session_created_at"], "session_created_at"
            ),
            session_updated_at=_require_string(
                data["session_updated_at"], "session_updated_at"
            ),
            coin_provenance=tuple(
                AuditCoin.from_dict(item) for item in data["coin_provenance"]
            ),
            proposed_count=_require_integer(data["proposed_count"], "proposed_count"),
            imported_count=_require_integer(data["imported_count"], "imported_count"),
            skipped_count=_require_integer(data["skipped_count"], "skipped_count"),
            phase=_enum_value(ImportPhase, data["phase"], "phase"),
            final_status=_enum_value(ImportResult, data["final_status"], "final_status"),
            error_category=error_category,
        )
        result.validate()
        return result


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}.")
        result[key] = value
    return result


def serialize(audit: AuditSession) -> str:
    """Serialize a validated audit DTO to deterministic JSON text."""

    if not isinstance(audit, AuditSession):
        raise ValueError("audit must be an AuditSession.")
    text = json.dumps(
        audit.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    if len(text.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("Serialized audit exceeds the JSON byte limit.")
    return text


def deserialize(value: str | bytes) -> AuditSession:
    """Deserialize and validate an audit DTO without performing disk I/O."""

    if isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bytes):
        raw = value
    else:
        raise ValueError("Serialized audit must be text or bytes.")
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("Serialized audit exceeds the JSON byte limit.")
    try:
        text = raw.decode("utf-8", errors="strict")
        data = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Serialized audit is not valid strict UTF-8 JSON.") from exc
    return AuditSession.from_dict(data)
