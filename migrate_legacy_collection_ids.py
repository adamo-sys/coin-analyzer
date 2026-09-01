"""Explicit plan/apply/verify migration for legacy duplicate collection IDs.

This module is deliberately separate from normal application startup.  It is
safe to import in tests and operates only on paths explicitly supplied by the
caller (plus documented production-reference defaults adjacent to that path).
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
from typing import Any, Iterable
from uuid import uuid4

from atomic_json import write_json_atomically
from backup_manager import BackupManager
from capture_import.lock import PackageImportLock
from capture_import._filesystem import (
    delete_open_file,
    ensure_plain_directory,
    handle_matches_path,
    handle_object_identity,
    is_link_or_reparse,
    open_existing_binary_for_delete,
    open_exclusive_binary,
    path_object_identity,
    require_plain_directory,
)
from coin_collection import (
    COLLECTION_SCHEMA_VERSION,
    CoinCollection,
    CoinItem,
    CollectionFormat,
    CollectionLoadState,
    deserialize_collection_payload,
    promote_collection_records_to_v1,
)


TOOL_VERSION = "8M-B.2"
PLAN_VERSION = 2
REPORT_VERSION = 2
INVENTORY_VERSION = 1
LEGACY_DUPLICATE_ID = re.compile(r"numista_[0-9]+")
CURRENT_ITEM_ID = re.compile(r"coin_[0-9a-f]{32}")


class MigrationRefused(RuntimeError):
    """The source is not eligible for this narrowly authorized migration."""

    def __init__(self, message: str, *, evidence: dict[str, Any] | None = None):
        super().__init__(message)
        self.evidence = evidence or {}


class MigrationRecoveryRequired(RuntimeError):
    """Authoritative publication occurred but final verification failed."""

    def __init__(self, message: str, *, evidence: dict[str, Any] | None = None):
        super().__init__(message)
        self.evidence = evidence or {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def _read_stable_file(path: Path, label: str) -> tuple[bytes, os.stat_result]:
    try:
        before = os.lstat(path)
        if not stat.S_ISREG(before.st_mode) or is_link_or_reparse(path):
            raise MigrationRefused(f"{label} is not a plain regular file: {path}")
        with path.open("rb") as handle:
            data = handle.read()
        after = os.stat(path, follow_symlinks=False)
    except OSError as error:
        raise MigrationRefused(f"{label} could not be read safely: {path}: {error}") from error
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ) or len(data) != after.st_size:
        raise MigrationRefused(f"{label} changed while it was read: {path}")
    return data, after


def _load_json_bytes(data: bytes, label: str) -> Any:
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MigrationRefused(f"{label} is not valid UTF-8 JSON: {error}") from error


def _records_without_unique_check(document: Any) -> tuple[CollectionFormat, list[dict[str, Any]]]:
    if isinstance(document, list):
        collection_format = CollectionFormat.LEGACY_V0
        records = document
    elif isinstance(document, dict):
        if set(document) != {"schema_version", "items"}:
            raise MigrationRefused("V1 collection root is not closed")
        version = document["schema_version"]
        if type(version) is not int or version != COLLECTION_SCHEMA_VERSION:
            raise MigrationRefused("collection schema_version is unsupported")
        records = document["items"]
        if not isinstance(records, list):
            raise MigrationRefused("V1 collection items must be an array")
        collection_format = CollectionFormat.V1
    else:
        raise MigrationRefused("collection root is not supported V0 or V1")

    required_v1 = {"item_type", "disposition", "identification_status"}
    validated: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise MigrationRefused(f"collection record {index} is not an object")
        item_id = record.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            raise MigrationRefused(f"collection record {index} has no stable ID")
        if collection_format is CollectionFormat.V1:
            missing = required_v1.difference(record)
            if missing:
                raise MigrationRefused(
                    f"V1 collection record {index} is missing required fields {sorted(missing)!r}"
                )
        try:
            CoinItem.from_dict(record)
        except Exception as error:
            raise MigrationRefused(
                f"collection record {index} is otherwise invalid: {error}"
            ) from error
        validated.append(record)
    return collection_format, validated


def _duplicate_groups(records: list[dict[str, Any]]) -> dict[str, list[int]]:
    indexes: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        indexes.setdefault(record["id"], []).append(index)
    return {key: value for key, value in indexes.items() if len(value) > 1}


def _project_root(collection: Path) -> Path:
    parent = collection.absolute().parent
    return parent.parent if parent.name.casefold() == "data" else parent


def _resolve_reference(reference: str, collection: Path) -> Path:
    path = Path(reference)
    return path.absolute() if path.is_absolute() else (_project_root(collection) / path).absolute()


def _is_beneath(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _require_managed_path(
    root: Path, path: Path, label: str, *, leaf_exists: bool, create_parents: bool = False
) -> None:
    """Prove lexical and physical containment beneath a plain ownership root."""

    root = root.absolute()
    path = path.absolute()
    if not _is_beneath(path, root):
        raise MigrationRefused(f"{label} is outside its managed ownership root: {path}")
    try:
        require_plain_directory(root)
        parent = path.parent
        current = root
        if leaf_exists:
            require_plain_directory(parent)
            info = os.lstat(path)
            if not stat.S_ISREG(info.st_mode) or is_link_or_reparse(path):
                raise OSError("managed media leaf is not a plain regular file")
        else:
            if create_parents:
                ensure_plain_directory(parent)
                require_plain_directory(parent)
            else:
                current = root
                for part in parent.relative_to(root).parts:
                    candidate = current / part
                    if not candidate.exists():
                        break
                    require_plain_directory(candidate)
                    current = candidate
        resolved_root = root.resolve(strict=True)
        resolved_parent = (parent if parent.exists() else current).resolve(strict=True)
        resolved_parent.relative_to(resolved_root)
    except (OSError, ValueError) as error:
        raise MigrationRefused(
            f"{label} traverses an unsafe link/reparse path or escapes ownership: {path}"
        ) from error


def _plain_directory_inventory(path: Path, label: str) -> list[Path]:
    """Enumerate JSON leaves without following redirected directory entries."""

    try:
        require_plain_directory(path)
    except OSError as error:
        raise MigrationRefused(f"{label} is not a plain directory: {path}") from error
    result: list[Path] = []
    for current, directories, files in os.walk(path, followlinks=False):
        current_path = Path(current)
        for name in list(directories):
            child = current_path / name
            try:
                require_plain_directory(child)
            except OSError as error:
                raise MigrationRefused(
                    f"{label} contains a link/reparse directory: {child}"
                ) from error
        for name in files:
            child = current_path / name
            if child.suffix.casefold() == ".json":
                result.append(child)
    return sorted(result)


def _safe_suffix(path: Path) -> str:
    suffix = path.suffix.lower()
    return suffix if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix) else ".bin"


def _record_media_plan(
    record: dict[str, Any], source_index: int, new_id: str, collection: Path
) -> tuple[list[dict[str, Any]], str]:
    old_id = record["id"]
    ordinary_root = (collection.absolute().parent / "managed_media" / "ordinary" / old_id)
    destinations: dict[str, str] = {}
    entries: list[dict[str, Any]] = []
    classifications: set[str] = set()

    def add(reference: str, target: dict[str, Any], provenance: Any = None) -> None:
        if not reference:
            return
        resolved = _resolve_reference(reference, collection)
        if provenance is not None:
            raise MigrationRefused(
                f"collision record {source_index} has capture-import lineage"
            )
        if _is_beneath(resolved, ordinary_root):
            _require_managed_path(ordinary_root, resolved, "ordinary migration media source", leaf_exists=True)
            classification = "ORDINARY_MANAGED_COPY"
            destination = destinations.get(str(resolved))
            if destination is None:
                destination = str(
                    collection.absolute().parent
                    / "managed_media"
                    / "ordinary"
                    / new_id
                    / f"{uuid4().hex}{_safe_suffix(resolved)}"
                )
                destinations[str(resolved)] = destination
        elif "imports" in {part.casefold() for part in resolved.parts}:
            raise MigrationRefused(
                f"collision record {source_index} has an ambiguous capture-import path"
            )
        else:
            classification = "EXTERNAL_PRESERVED"
            destination = reference
        classifications.add(classification)
        entries.append({
            "source_reference": reference,
            "source_path": str(resolved),
            "planned_reference": destination,
            "classification": classification,
            "target": target,
        })

    photos = record.get("photos")
    if isinstance(photos, list):
        for photo_index, photo in enumerate(photos):
            if isinstance(photo, str):
                add(photo, {"kind": "photo_string", "index": photo_index})
            elif isinstance(photo, dict):
                reference = str(photo.get("path") or photo.get("file_path") or "").strip()
                add(
                    reference,
                    {"kind": "photo_dict", "index": photo_index},
                    photo.get("capture_import_media"),
                )
    image_path = str(record.get("image_path") or "").strip()
    if image_path:
        add(image_path, {"kind": "image_path"})
    media_classification = "+".join(sorted(classifications)) if classifications else "NO_MEDIA"
    return entries, media_classification


def _iter_scalar_matches(value: Any, targets: set[str], location: str = "$") -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _iter_scalar_matches(child, targets, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_scalar_matches(child, targets, f"{location}[{index}]")
    elif isinstance(value, str) and value in targets:
        yield location


_REQUIRED_INVENTORY_KINDS = {
    "PHOTO_INBOX", "APP_STATE_PHOTO_VAULT", "CONFIRMED_OBSERVATIONS",
    "CAPTURE_WORKSPACE_ROOTS",
}


def _default_inventory_descriptor(collection: Path) -> dict[str, Any]:
    """Return a review template; callers must explicitly acknowledge it."""

    root = _project_root(collection)
    return {
        "inventory_version": INVENTORY_VERSION,
        "operator_declared_complete": True,
        "stores": [
            {"kind": "PHOTO_INBOX", "path": str(root / "data" / "photo_inbox_state.json"), "required": False},
            {"kind": "APP_STATE_PHOTO_VAULT", "path": str(root / "collection_data" / "app_state" / "app_state.json"), "required": False},
            {"kind": "CONFIRMED_OBSERVATIONS", "path": str(root / "collection_data" / "app_state" / "confirmed_observations.json"), "required": False},
            {"kind": "CAPTURE_WORKSPACE_ROOTS", "path": str(root / "coin_photos" / "collection" / "imports"), "required": False},
        ],
    }


def _load_inventory_descriptor(value: Any) -> dict[str, Any]:
    if isinstance(value, (str, os.PathLike)):
        raw, _ = _read_stable_file(Path(value).absolute(), "reference inventory")
        value = _load_json_bytes(raw, "reference inventory")
    required = {"inventory_version", "operator_declared_complete", "stores"}
    if not isinstance(value, dict) or set(value) != required:
        raise MigrationRefused("active-reference inventory structure is not closed")
    if value["inventory_version"] != INVENTORY_VERSION or value["operator_declared_complete"] is not True:
        raise MigrationRefused("active-reference inventory was not explicitly reviewed as complete")
    stores = value["stores"]
    if not isinstance(stores, list) or not stores:
        raise MigrationRefused("active-reference inventory has no declared stores")
    kinds: set[str] = set()
    paths: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    for store in stores:
        if not isinstance(store, dict) or set(store) != {"kind", "path", "required"}:
            raise MigrationRefused("active-reference store structure is not closed")
        kind, path, required_store = store["kind"], store["path"], store["required"]
        if not isinstance(kind, str) or not kind or not isinstance(path, str) or not path:
            raise MigrationRefused("active-reference store kind/path is invalid")
        if type(required_store) is not bool:
            raise MigrationRefused("active-reference required flag is invalid")
        absolute = str(Path(path).absolute())
        if absolute in paths:
            raise MigrationRefused("active-reference inventory repeats a path")
        paths.add(absolute)
        kinds.add(kind)
        cleaned.append({"kind": kind, "path": absolute, "required": required_store})
    missing = _REQUIRED_INVENTORY_KINDS - kinds
    if missing:
        raise MigrationRefused(f"active-reference inventory omits required categories: {sorted(missing)!r}")
    return {
        "inventory_version": INVENTORY_VERSION,
        "operator_declared_complete": True,
        "stores": cleaned,
    }


def _audit_active_references(
    duplicate_ids: set[str], inventory: dict[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for store_index, store in enumerate(inventory["stores"]):
        kind = store["kind"]
        path = Path(store["path"])
        if not path.exists():
            if store["required"]:
                raise MigrationRefused(f"required active reference store is absent: {path}")
            rows.append({"store_index": store_index, "kind": kind, "path": str(path), "required": False, "existence": "ABSENT", "members": []})
            continue
        if path.is_dir():
            children = _plain_directory_inventory(path, kind)
            members = []
            for child in children:
                data, _ = _read_stable_file(child, kind)
                payload = _load_json_bytes(data, kind)
                matches = sorted(_iter_scalar_matches(payload, duplicate_ids))
                members.append({"relative_path": child.relative_to(path).as_posix(), "sha256": _digest(data), "byte_length": len(data), "matches": matches})
                if matches:
                    raise MigrationRefused(
                        f"active {kind} contains an ambiguous shared legacy ID at {matches[0]}"
                    )
            rows.append({"store_index": store_index, "kind": kind, "path": str(path), "required": store["required"], "existence": "DIRECTORY", "members": members})
            continue
        try:
            require_plain_directory(path.parent)
        except OSError as error:
            raise MigrationRefused(f"active {kind} traverses a link/reparse ancestor: {path}") from error
        data, _ = _read_stable_file(path, kind)
        payload = _load_json_bytes(data, kind)
        matches = sorted(_iter_scalar_matches(payload, duplicate_ids))
        rows.append({"store_index": store_index, "kind": kind, "path": str(path), "required": store["required"], "existence": "FILE", "members": [{"relative_path": ".", "sha256": _digest(data), "byte_length": len(data), "matches": matches}]})
        if matches:
            raise MigrationRefused(
                f"active {kind} contains an ambiguous shared legacy ID at {matches[0]}"
            )
    return rows


def _revalidate_reference_audit(plan: dict[str, Any]) -> None:
    """Prove every planned active-reference observation is unchanged."""

    current = _audit_active_references(
        {row["old_id"] for row in plan["duplicate_groups"]}, plan["reference_inventory"]
    )
    if current != plan["active_reference_audit"]:
        raise MigrationRefused("active-reference inventory changed after planning")
    for row in plan["active_reference_audit"]:
        path = Path(row["path"])
        if row["existence"] == "ABSENT":
            if path.exists():
                raise MigrationRefused(f"active reference appeared after planning: {path}")


def _write_json_exclusively(path: Path, payload: Any) -> None:
    path = path.absolute()
    ensure_plain_directory(path.parent)
    parent_identity = path_object_identity(path.parent)
    encoded = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    handle = None
    identity = None
    try:
        handle = open_exclusive_binary(path)
        identity = handle_object_identity(handle)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
        if not handle_matches_path(handle, path):
            raise OSError("exclusive JSON artifact identity changed")
        handle.close()
        handle = None
    except Exception as error:
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
        if identity is not None:
            try:
                current, _ = _read_stable_file(path, "partial private JSON artifact")
                _cleanup_created([{
                    "path": str(path), "created": True, "identity": list(identity),
                    "parent_identity": list(parent_identity), "byte_length": len(current),
                    "sha256": _digest(current),
                }])
            except (OSError, MigrationRefused):
                pass
        raise


def create_plan(
    collection_path: str,
    plan_path: str,
    *,
    reference_inventory: Any = None,
    reference_paths: Iterable[str | os.PathLike[str]] = (),
) -> dict[str, Any]:
    """Create one immutable, non-mutating duplicate-ID migration plan."""

    collection = Path(collection_path).absolute()
    plan_destination = Path(plan_path).absolute()
    if plan_destination.exists():
        raise MigrationRefused(f"migration plan already exists: {plan_destination}")
    source_bytes, _ = _read_stable_file(collection, "source collection")
    document = _load_json_bytes(source_bytes, "source collection")
    collection_format, records = _records_without_unique_check(document)
    groups = _duplicate_groups(records)
    if not groups:
        # A valid collection is deliberately a non-writing not-applicable result.
        deserialize_collection_payload(document)
        return {
            "status": "NOT_APPLICABLE",
            "source_path": str(collection),
            "source_sha256": _digest(source_bytes),
            "source_byte_length": len(source_bytes),
        }
    invalid_patterns = sorted(key for key in groups if LEGACY_DUPLICATE_ID.fullmatch(key) is None)
    if invalid_patterns:
        raise MigrationRefused(
            f"duplicate ID is outside the authorized legacy pattern: {invalid_patterns[0]!r}"
        )

    all_existing = {record["id"] for record in records}
    occurrences: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    for old_id, indexes in groups.items():
        group_rows.append({"old_id": old_id, "source_indexes": list(indexes)})
        for occurrence_index, source_index in enumerate(indexes):
            while True:
                new_id = f"coin_{uuid4().hex}"
                if new_id not in all_existing:
                    all_existing.add(new_id)
                    break
            record = records[source_index]
            media, media_classification = _record_media_plan(
                record, source_index, new_id, collection
            )
            occurrences.append({
                "old_id": old_id,
                "occurrence_index": occurrence_index,
                "source_index": source_index,
                "new_id": new_id,
                "numista_n": str(record.get("numista_n") or ""),
                "summary": {
                    name: str(record.get(name) or "")
                    for name in ("country", "denomination", "year", "grade")
                },
                "photo_count": len(record.get("photos") or []) or (1 if record.get("image_path") else 0),
                "media_classification": media_classification,
                "media": media,
                "capture_provenance_changed": False,
                "reference_classifications": [],
                "original_record_sha256": _digest(_canonical_bytes(record)),
            })

    if reference_inventory is None:
        raise MigrationRefused(
            "an explicitly reviewed, operator-declared complete active-reference inventory is required"
        )
    inventory = _load_inventory_descriptor(reference_inventory)
    for path in reference_paths:
        inventory["stores"].append({
            "kind": "ADDITIONAL_ACTIVE_PRODUCTION_STORE",
            "path": str(Path(path).absolute()),
            "required": True,
        })
    reference_audit = _audit_active_references(set(groups), inventory)
    migration_id = str(uuid4())
    plan = {
        "plan_version": PLAN_VERSION,
        "tool_version": TOOL_VERSION,
        "migration_id": migration_id,
        "created_at": _utc_now(),
        "source_path": str(collection),
        "source_sha256": _digest(source_bytes),
        "source_byte_length": len(source_bytes),
        "source_format": collection_format.value,
        "record_count": len(records),
        "duplicate_groups": group_rows,
        "occurrences": occurrences,
        "unchanged_record_count": len(records) - len(occurrences),
        "reference_inventory": inventory,
        "active_reference_audit": reference_audit,
    }
    _write_json_exclusively(plan_destination, plan)
    return plan


def _load_plan(plan_path: Path) -> dict[str, Any]:
    data, _ = _read_stable_file(plan_path, "migration plan")
    value = _load_json_bytes(data, "migration plan")
    required = {
        "plan_version", "tool_version", "migration_id", "created_at", "source_path",
        "source_sha256", "source_byte_length", "source_format", "record_count",
        "duplicate_groups", "occurrences", "unchanged_record_count", "reference_inventory",
        "active_reference_audit",
    }
    if not isinstance(value, dict) or set(value) != required or value["plan_version"] != PLAN_VERSION:
        raise MigrationRefused("migration plan structure or version is unsupported")
    if not isinstance(value["occurrences"], list) or not value["occurrences"]:
        raise MigrationRefused("migration plan has no collision occurrences")
    if _load_inventory_descriptor(value["reference_inventory"]) != value["reference_inventory"]:
        raise MigrationRefused("migration plan reference inventory is not canonical")
    if not isinstance(value["active_reference_audit"], list):
        raise MigrationRefused("migration plan reference audit is invalid")
    for row in value["duplicate_groups"]:
        if (
            not isinstance(row, dict) or set(row) != {"old_id", "source_indexes"}
            or not isinstance(row["old_id"], str)
            or not isinstance(row["source_indexes"], list)
            or any(type(index) is not int for index in row["source_indexes"])
        ):
            raise MigrationRefused("migration plan duplicate-group structure is invalid")
    for row in value["active_reference_audit"]:
        if not isinstance(row, dict) or set(row) != {
            "store_index", "kind", "path", "required", "existence", "members"
        } or row["existence"] not in {"ABSENT", "FILE", "DIRECTORY"}:
            raise MigrationRefused("migration plan reference-audit structure is invalid")
        if not isinstance(row["members"], list):
            raise MigrationRefused("migration plan reference member inventory is invalid")
        for member in row["members"]:
            if not isinstance(member, dict) or set(member) != {
                "relative_path", "sha256", "byte_length", "matches"
            }:
                raise MigrationRefused("migration plan reference member structure is invalid")
    ids = [row.get("new_id") for row in value["occurrences"] if isinstance(row, dict)]
    if len(ids) != len(value["occurrences"]) or len(set(ids)) != len(ids) or any(
        not isinstance(item_id, str) or CURRENT_ITEM_ID.fullmatch(item_id) is None for item_id in ids
    ):
        raise MigrationRefused("migration plan contains invalid planned IDs")
    return value


def _target_reference(record: dict[str, Any], target: dict[str, Any]) -> tuple[str, Any]:
    kind = target.get("kind")
    if kind == "image_path" and set(target) == {"kind"}:
        return str(record.get("image_path") or "").strip(), None
    if kind not in {"photo_string", "photo_dict"} or set(target) != {"kind", "index"}:
        raise MigrationRefused("migration plan contains an invalid media target")
    index = target["index"]
    photos = record.get("photos")
    if type(index) is not int or not isinstance(photos, list) or not 0 <= index < len(photos):
        raise MigrationRefused("migration plan media target is outside the record")
    photo = photos[index]
    if kind == "photo_string" and isinstance(photo, str):
        return photo.strip(), None
    if kind == "photo_dict" and isinstance(photo, dict):
        return str(photo.get("path") or photo.get("file_path") or "").strip(), photo.get("capture_import_media")
    raise MigrationRefused("migration plan media target type does not match the record")


def _validate_plan_against_records(
    plan: dict[str, Any], records: list[dict[str, Any]], collection: Path
) -> None:
    groups = _duplicate_groups(records)
    expected_pairs = {
        (old_id, source_index)
        for old_id, indexes in groups.items()
        for source_index in indexes
    }
    seen_pairs: set[tuple[str, int]] = set()
    unchanged_ids = {
        record["id"] for index, record in enumerate(records)
        if (record["id"], index) not in expected_pairs
    }
    planned_ids = [row.get("new_id") for row in plan["occurrences"]]
    if any(item_id in unchanged_ids for item_id in planned_ids):
        raise MigrationRefused("planned new ID collides with an unchanged source ID")
    for occurrence in plan["occurrences"]:
        required = {
            "old_id", "occurrence_index", "source_index", "new_id", "numista_n",
            "summary", "photo_count", "media_classification", "media",
            "capture_provenance_changed", "reference_classifications",
            "original_record_sha256",
        }
        if not isinstance(occurrence, dict) or set(occurrence) != required:
            raise MigrationRefused("migration plan occurrence structure is not closed")
        index = occurrence["source_index"]
        if type(index) is not int or not 0 <= index < len(records):
            raise MigrationRefused("migration plan source index is invalid")
        record = records[index]
        pair = (occurrence["old_id"], index)
        if pair not in expected_pairs or pair in seen_pairs or record["id"] != occurrence["old_id"]:
            raise MigrationRefused("migration plan occurrence mapping is not exact")
        seen_pairs.add(pair)
        if occurrence["capture_provenance_changed"] is not False:
            raise MigrationRefused("migration plan attempts to change capture provenance")
        if str(record.get("numista_n") or "") != occurrence["numista_n"]:
            raise MigrationRefused("migration plan changes numista_n")
        old_root = collection.parent / "managed_media" / "ordinary" / occurrence["old_id"]
        new_root = collection.parent / "managed_media" / "ordinary" / occurrence["new_id"]
        seen_targets: set[tuple[str, int | None]] = set()
        for media in occurrence["media"]:
            if not isinstance(media, dict) or set(media) != {
                "source_reference", "source_path", "planned_reference", "classification", "target"
            }:
                raise MigrationRefused("migration plan media structure is not closed")
            reference, provenance = _target_reference(record, media["target"])
            if reference != media["source_reference"]:
                raise MigrationRefused("migration plan media source reference changed")
            resolved = _resolve_reference(reference, collection)
            if str(resolved) != media["source_path"]:
                raise MigrationRefused("migration plan media source path changed")
            target_key = (media["target"]["kind"], media["target"].get("index"))
            if target_key in seen_targets:
                raise MigrationRefused("migration plan repeats a media target")
            seen_targets.add(target_key)
            if provenance is not None:
                raise MigrationRefused(f"collision record {index} has capture-import lineage")
            if media["classification"] == "ORDINARY_MANAGED_COPY":
                destination = Path(media["planned_reference"])
                if not _is_beneath(resolved, old_root) or destination.parent != new_root:
                    raise MigrationRefused("migration plan ordinary-media ownership is invalid")
                _require_managed_path(old_root, resolved, "ordinary migration media source", leaf_exists=True)
                ordinary_base = collection.parent / "managed_media" / "ordinary"
                if new_root.exists():
                    try:
                        require_plain_directory(new_root)
                    except OSError as error:
                        raise MigrationRefused("planned new-ID media directory is redirected") from error
                _require_managed_path(ordinary_base, destination, "planned migration media", leaf_exists=False)
                if not destination.name or destination.name in {".", ".."}:
                    raise MigrationRefused("migration plan ordinary-media filename is invalid")
            elif media["classification"] == "EXTERNAL_PRESERVED":
                if _is_beneath(resolved, old_root) or media["planned_reference"] != reference:
                    raise MigrationRefused("migration plan external-media classification is invalid")
            else:
                raise MigrationRefused("migration plan media classification is unsupported")
    if seen_pairs != expected_pairs:
        raise MigrationRefused("migration plan does not map every collision occurrence exactly once")


def _exclusive_copy(source: Path, destination: Path) -> dict[str, Any]:
    data, _ = _read_stable_file(source, "migration media source")
    ordinary_base = destination.parent.parent
    _require_managed_path(
        ordinary_base, destination, "planned migration media",
        leaf_exists=False, create_parents=True,
    )
    parent_identity = path_object_identity(destination.parent)
    handle = None
    created_identity = None
    try:
        handle = open_exclusive_binary(destination)
        created_identity = handle_object_identity(handle)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
        if not handle_matches_path(handle, destination):
            raise MigrationRefused("staged migration media identity changed during copy")
        handle.close()
        handle = None
        copied, identity = _read_stable_file(destination, "staged migration media")
        if copied != data or path_object_identity(destination) != created_identity:
            raise MigrationRefused(f"staged migration media did not verify: {destination}")
        return {
            "path": str(destination), "created": True,
            "identity": list(created_identity), "parent_identity": list(parent_identity),
            "byte_length": len(copied), "sha256": _digest(copied),
        }
    except FileExistsError as error:
        raise MigrationRefused(f"planned media destination already exists: {destination}") from error
    except Exception as error:
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
        if created_identity is not None:
            retained = [str(destination)]
            try:
                partial, _ = _read_stable_file(destination, "partial migration media")
                receipt = {
                    "path": str(destination), "created": True,
                    "identity": list(created_identity), "parent_identity": list(parent_identity),
                    "byte_length": len(partial), "sha256": _digest(partial),
                }
                retained = _cleanup_created([receipt])
            except (OSError, MigrationRefused):
                pass
            if retained:
                raise MigrationRefused(
                    "exceptional copy cleanup retained identity-ambiguous attempt media",
                    evidence={"cleanup_refusals": retained},
                ) from error
        raise


def _cleanup_created(receipts: Iterable[dict[str, Any]]) -> list[str]:
    retained: list[str] = []
    for receipt in reversed(list(receipts)):
        if not receipt.get("created"):
            continue
        path = Path(receipt["path"])
        handle = None
        try:
            require_plain_directory(path.parent)
            if list(path_object_identity(path.parent)) != receipt["parent_identity"]:
                raise OSError("created object's parent identity changed")
            handle = open_existing_binary_for_delete(path)
            identity = handle_object_identity(handle)
            digest = sha256()
            length = 0
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                length += len(chunk)
                digest.update(chunk)
            if (
                list(identity) == receipt["identity"]
                and length == receipt["byte_length"]
                and digest.hexdigest() == receipt["sha256"]
                and handle_matches_path(handle, path)
            ):
                delete_open_file(handle, path)
                try:
                    path.parent.rmdir()
                except OSError:
                    pass
            else:
                retained.append(str(path))
        except OSError:
            retained.append(str(path))
        finally:
            if handle is not None:
                handle.close()
    return retained


def _verify_receipts(receipts: Iterable[dict[str, Any]]) -> None:
    for receipt in receipts:
        path = Path(receipt["path"])
        data, identity = _read_stable_file(path, "planned migration media")
        if (
            list(path_object_identity(path)) != receipt["identity"]
            or len(data) != receipt["byte_length"]
            or _digest(data) != receipt["sha256"]
        ):
            raise MigrationRefused(f"planned migration media changed before publication: {path}")


def _create_raw_safety_copy(source: Path, safety_dir: Path, plan: dict[str, Any]) -> dict[str, Any]:
    ensure_plain_directory(safety_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    destination = safety_dir / f"{source.name}.pre-id-migration-{stamp}-{uuid4().hex}.json"
    source_bytes, _ = _read_stable_file(source, "source collection")
    with open_exclusive_binary(destination) as handle:
        handle.write(source_bytes)
        handle.flush()
        os.fsync(handle.fileno())
    copy_bytes, _ = _read_stable_file(destination, "raw migration safety copy")
    if copy_bytes != source_bytes:
        raise MigrationRefused("raw migration safety copy did not verify")
    return {
        "source_path": str(source),
        "source_byte_length": len(source_bytes),
        "source_sha256": _digest(source_bytes),
        "copy_path": str(destination),
        "copy_byte_length": len(copy_bytes),
        "copy_sha256": _digest(copy_bytes),
        "created_at": _utc_now(),
        "tool_version": TOOL_VERSION,
        "migration_id": plan["migration_id"],
    }


def _apply_media_reference(record: dict[str, Any], target: dict[str, Any], new_reference: str) -> None:
    kind = target["kind"]
    if kind == "image_path":
        record["image_path"] = new_reference
    elif kind == "photo_string":
        record["photos"][target["index"]] = new_reference
    elif kind == "photo_dict":
        photo = record["photos"][target["index"]]
        if "path" in photo or "file_path" not in photo:
            photo["path"] = new_reference
        else:
            photo["file_path"] = new_reference
    else:
        raise MigrationRefused(f"unsupported planned media target: {kind!r}")


def _equivalent_except_authorized(original: dict[str, Any], migrated: dict[str, Any]) -> bool:
    def normalized(value: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(value)
        result.pop("id", None)
        if "image_path" in result:
            result["image_path"] = "<AUTHORIZED_PATH>"
        photos = result.get("photos")
        if isinstance(photos, list):
            for index, photo in enumerate(photos):
                if isinstance(photo, str):
                    photos[index] = "<AUTHORIZED_PATH>"
                elif isinstance(photo, dict):
                    if "path" in photo:
                        photo["path"] = "<AUTHORIZED_PATH>"
                    if "file_path" in photo:
                        photo["file_path"] = "<AUTHORIZED_PATH>"
        return result

    left = normalized(original)
    right = normalized(migrated)
    # V0-to-V1 promotion materializes only the frozen compatibility fields.
    for key in ("item_type", "disposition", "identification_status", "updated_at"):
        if key not in left:
            right.pop(key, None)
    return left == right


def apply_plan(
    plan_path: str,
    report_path: str,
    *,
    safety_dir: str | None = None,
    portable_backup_path: str | None = None,
) -> dict[str, Any]:
    """Apply one immutable plan and return its private completion report."""

    plan_file = Path(plan_path).absolute()
    report_file = Path(report_path).absolute()
    if report_file.exists():
        raise MigrationRefused(f"migration report already exists: {report_file}")
    plan = _load_plan(plan_file)
    collection = Path(plan["source_path"]).absolute()
    safety_root = Path(safety_dir).absolute() if safety_dir else plan_file.parent
    portable_path = (
        Path(portable_backup_path).absolute()
        if portable_backup_path
        else plan_file.parent / f"{plan['migration_id']}-portable.zip"
    )
    lock_path = collection.parent / "imports" / "package_import.lock"
    started_at = _utc_now()
    receipts: list[dict[str, Any]] = []
    authoritative_published = False
    safety: dict[str, Any] | None = None

    if portable_path.exists():
        raise MigrationRefused(f"portable backup destination already exists: {portable_path}")

    with PackageImportLock.acquire(lock_path) as migration_lock:
        migration_lock.verify_ownership()
        source_bytes, _ = _read_stable_file(collection, "source collection")
        if len(source_bytes) != plan["source_byte_length"] or _digest(source_bytes) != plan["source_sha256"]:
            raise MigrationRefused("source collection does not match the immutable migration plan")
        document = _load_json_bytes(source_bytes, "source collection")
        source_format, records = _records_without_unique_check(document)
        if source_format.value != plan["source_format"] or len(records) != plan["record_count"]:
            raise MigrationRefused("source collection no longer matches planned structure")
        groups = _duplicate_groups(records)
        planned_groups = {
            row["old_id"]: list(row["source_indexes"]) for row in plan["duplicate_groups"]
        }
        if groups != planned_groups:
            raise MigrationRefused("source duplicate groups do not match the plan")
        _validate_plan_against_records(plan, records, collection)
        _revalidate_reference_audit(plan)
        safety = _create_raw_safety_copy(collection, safety_root, plan)

        migrated = deepcopy(records)
        try:
            for occurrence in plan["occurrences"]:
                index = occurrence["source_index"]
                original = records[index]
                if (
                    original["id"] != occurrence["old_id"]
                    or _digest(_canonical_bytes(original)) != occurrence["original_record_sha256"]
                ):
                    raise MigrationRefused(f"record {index} no longer matches the plan")
                target_record = migrated[index]
                target_record["id"] = occurrence["new_id"]
                copied_by_source: dict[str, str] = {}
                for media in occurrence["media"]:
                    if media["classification"] == "ORDINARY_MANAGED_COPY":
                        source = Path(media["source_path"])
                        destination = Path(media["planned_reference"])
                        if str(source) not in copied_by_source:
                            receipt = _exclusive_copy(source, destination)
                            receipts.append(receipt)
                            copied_by_source[str(source)] = str(destination)
                        new_reference = copied_by_source[str(source)]
                    else:
                        new_reference = media["source_reference"]
                    _apply_media_reference(target_record, media["target"], new_reference)

            final_ids = [record.get("id") for record in migrated]
            if (
                len(migrated) != len(records)
                or any(not isinstance(item_id, str) or not item_id.strip() for item_id in final_ids)
                or len(set(final_ids)) != len(final_ids)
            ):
                raise MigrationRefused("migrated stable-ID roster is invalid")
            if any(
                not _equivalent_except_authorized(original, changed)
                for original, changed in zip(records, migrated)
            ):
                raise MigrationRefused("migration changed unapproved factual data")

            _verify_receipts(receipts)
            payload = promote_collection_records_to_v1(migrated)
            _, _, parsed_items = deserialize_collection_payload(payload)
            migration_lock.verify_ownership()
            current_bytes, _ = _read_stable_file(collection, "source collection baseline")
            if current_bytes != source_bytes:
                raise MigrationRefused("source changed before authoritative publication")
            write_json_atomically(str(collection), payload, indent=2, ensure_ascii=False)
            authoritative_published = True

            reloaded = CoinCollection(str(collection))
            if reloaded.load_state is not CollectionLoadState.VALID or len(reloaded.items) != len(records):
                raise MigrationRecoveryRequired(
                    "authoritative migration published but normal reload verification failed"
                )
            if [item.id for item in reloaded.items] != final_ids:
                raise MigrationRecoveryRequired(
                    "authoritative migration published but stable-ID roster changed"
                )

            manager = BackupManager(
                backup_dir=str(portable_path.parent), collection_json_path=str(collection)
            )
            created = manager.create_portable_backup_package(str(portable_path))
            verified = manager.verify_backup_package(str(portable_path)) if created.success else created
            portable_ok = bool(created.success and verified.success)
            final_bytes, _ = _read_stable_file(collection, "migrated collection")
            report = {
                "report_version": REPORT_VERSION,
                "tool_version": TOOL_VERSION,
                "migration_id": plan["migration_id"],
                "status": "SUCCEEDED" if portable_ok else "MIGRATED_WITH_PORTABILITY_BLOCKER",
                "recovery_required": False,
                "source_path": str(collection),
                "source_sha256": plan["source_sha256"],
                "source_byte_length": plan["source_byte_length"],
                "safety_copy": safety,
                "source_format": plan["source_format"],
                "source_record_count": len(records),
                "duplicate_group_count": len(groups),
                "rekeyed_record_count": len(plan["occurrences"]),
                "unchanged_record_count": plan["unchanged_record_count"],
                "started_at": started_at,
                "completed_at": _utc_now(),
                "final_collection_sha256": _digest(final_bytes),
                "portable_backup_path": str(portable_path),
                "portable_backup_verified": portable_ok,
                "portable_backup_errors": list(verified.errors),
                "occurrences": [
                    {
                        key: deepcopy(row[key])
                        for key in (
                            "old_id", "occurrence_index", "source_index", "new_id",
                            "numista_n", "summary", "photo_count", "media_classification",
                            "media", "capture_provenance_changed", "reference_classifications",
                        )
                    }
                    for row in plan["occurrences"]
                ],
                "retained_attempt_media": [],
            }
            _write_json_exclusively(report_file, report)
            return report
        except Exception as error:
            if not authoritative_published:
                retained = _cleanup_created(receipts)
                if retained:
                    raise MigrationRefused(
                        "migration failed before publication and cleanup retained identity-ambiguous attempt media",
                        evidence={"cleanup_refusals": retained},
                    ) from error
                raise
            try:
                final_bytes, _ = _read_stable_file(collection, "published migrated collection")
                final_hash = _digest(final_bytes)
            except Exception:
                final_hash = "UNAVAILABLE"
            recovery_report = {
                "report_version": REPORT_VERSION,
                "tool_version": TOOL_VERSION,
                "migration_id": plan["migration_id"],
                "status": "RECOVERY_REQUIRED",
                "recovery_required": True,
                "source_path": str(collection),
                "source_sha256": plan["source_sha256"],
                "source_byte_length": plan["source_byte_length"],
                "safety_copy": safety,
                "source_format": plan["source_format"],
                "source_record_count": len(records),
                "duplicate_group_count": len(groups),
                "rekeyed_record_count": len(plan["occurrences"]),
                "unchanged_record_count": plan["unchanged_record_count"],
                "started_at": started_at,
                "completed_at": _utc_now(),
                "final_collection_sha256": final_hash,
                "portable_backup_path": str(portable_path),
                "portable_backup_verified": False,
                "portable_backup_errors": [str(error) or type(error).__name__],
                "occurrences": [
                    {
                        key: deepcopy(row[key])
                        for key in (
                            "old_id", "occurrence_index", "source_index", "new_id",
                            "numista_n", "summary", "photo_count", "media_classification",
                            "media", "capture_provenance_changed", "reference_classifications",
                        )
                    }
                    for row in plan["occurrences"]
                ],
                "retained_attempt_media": [receipt["path"] for receipt in receipts],
            }
            persisted_paths: list[str] = []
            persistence_errors: list[str] = []
            try:
                _write_json_exclusively(report_file, recovery_report)
                persisted_paths.append(str(report_file))
            except Exception as report_error:
                persistence_errors.append(type(report_error).__name__)
                fallback = safety_root / f"{plan['migration_id']}-RECOVERY_REQUIRED.json"
                try:
                    _write_json_exclusively(fallback, {
                        "status": "RECOVERY_REQUIRED",
                        "migration_id": plan["migration_id"],
                        "source_path": str(collection),
                        "safety_copy_path": safety["copy_path"] if safety else "UNAVAILABLE",
                    })
                    persisted_paths.append(str(fallback))
                except Exception as fallback_error:
                    persistence_errors.append(type(fallback_error).__name__)
            raise MigrationRecoveryRequired(
                "AUTHORITATIVE COLLECTION MAY ALREADY BE MIGRATED / RECOVERY REQUIRED",
                evidence={
                    "source_path": str(collection),
                    "safety_copy_path": safety["copy_path"] if safety else "UNAVAILABLE",
                    "report_paths_written": persisted_paths,
                    "report_persistence_errors": persistence_errors,
                },
            ) from error


def verify_report(report_path: str) -> dict[str, Any]:
    """Verify the closed report and all still-present completion artifacts."""

    report_file = Path(report_path).absolute()
    data, _ = _read_stable_file(report_file, "migration report")
    report = _load_json_bytes(data, "migration report")
    required = {
        "report_version", "tool_version", "migration_id", "status", "recovery_required",
        "source_path", "source_sha256", "source_byte_length", "safety_copy", "source_format",
        "source_record_count", "duplicate_group_count", "rekeyed_record_count",
        "unchanged_record_count", "started_at", "completed_at", "final_collection_sha256",
        "portable_backup_path", "portable_backup_verified", "portable_backup_errors",
        "occurrences", "retained_attempt_media",
    }
    if not isinstance(report, dict) or set(report) != required or report["report_version"] != REPORT_VERSION:
        raise MigrationRefused("migration report structure or version is unsupported")
    gate_status = (
        report.get("status") == "SUCCEEDED"
        and report.get("recovery_required") is False
        and report.get("portable_backup_verified") is True
    )
    safety = report["safety_copy"]
    safety_keys = {
        "source_path", "source_byte_length", "source_sha256", "copy_path",
        "copy_byte_length", "copy_sha256", "created_at", "tool_version", "migration_id",
    }
    if not isinstance(safety, dict) or set(safety) != safety_keys:
        raise MigrationRefused("migration report has no safety-copy evidence")
    safety_bytes, _ = _read_stable_file(Path(safety["copy_path"]), "raw safety copy")
    if len(safety_bytes) != safety["copy_byte_length"] or _digest(safety_bytes) != safety["copy_sha256"]:
        raise MigrationRefused("raw safety copy no longer verifies")
    if (
        safety["source_byte_length"] != report["source_byte_length"]
        or safety["source_sha256"] != report["source_sha256"]
        or safety["copy_byte_length"] != report["source_byte_length"]
        or safety["copy_sha256"] != report["source_sha256"]
    ):
        raise MigrationRefused("safety-copy evidence does not cross-check the planned source")
    collection = CoinCollection(report["source_path"])
    if collection.load_state is not CollectionLoadState.VALID:
        raise MigrationRefused("migrated collection is not VALID")
    if len(collection.items) != report["source_record_count"]:
        raise MigrationRefused("migrated record count does not match report")
    ids = [item.id for item in collection.items]
    if any(not isinstance(item_id, str) or not item_id.strip() for item_id in ids) or len(ids) != len(set(ids)):
        raise MigrationRefused("migrated collection has duplicate IDs")
    occurrences = report["occurrences"]
    if not isinstance(occurrences, list) or len(occurrences) != report["rekeyed_record_count"]:
        raise MigrationRefused("migration report occurrence roster is invalid")
    planned_new: set[str] = set()
    old_ids: set[str] = set()
    occurrence_keys = {
        "old_id", "occurrence_index", "source_index", "new_id", "numista_n",
        "summary", "photo_count", "media_classification", "media",
        "capture_provenance_changed", "reference_classifications",
    }
    for row in occurrences:
        if not isinstance(row, dict) or set(row) != occurrence_keys:
            raise MigrationRefused("migration report occurrence is invalid")
        if (
            not isinstance(row["summary"], dict)
            or set(row["summary"]) != {"country", "denomination", "year", "grade"}
            or not isinstance(row["media"], list)
            or not isinstance(row["reference_classifications"], list)
            or row["capture_provenance_changed"] is not False
        ):
            raise MigrationRefused("migration report occurrence details are invalid")
        index = row.get("source_index")
        new_id = row.get("new_id")
        old_id = row.get("old_id")
        if type(index) is not int or not 0 <= index < len(ids) or ids[index] != new_id:
            raise MigrationRefused("planned occurrence IDs do not match migrated collection roster")
        planned_new.add(new_id)
        old_ids.add(old_id)
    if len(planned_new) != len(occurrences) or old_ids.intersection(ids):
        raise MigrationRefused("rekeyed ambiguous old IDs remain authoritative")
    current_bytes, _ = _read_stable_file(Path(report["source_path"]), "migrated collection")
    if _digest(current_bytes) != report["final_collection_sha256"]:
        raise MigrationRefused("migrated collection hash does not match report")
    if gate_status:
        if not Path(report["portable_backup_path"]).is_file():
            raise MigrationRefused("reported portable backup is missing")
        manager = BackupManager(collection_json_path=report["source_path"])
        verified = manager.verify_backup_package(report["portable_backup_path"])
        if not verified.success:
            raise MigrationRefused("reported portable backup no longer verifies")
    return {"success": gate_status, "status": report["status"], "record_count": len(ids)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="create a private immutable migration plan")
    plan.add_argument("--collection", required=True)
    plan.add_argument("--plan", required=True)
    plan.add_argument("--reference-inventory", required=True)
    plan.add_argument("--reference", action="append", default=[])
    apply = commands.add_parser("apply", help="apply one unchanged migration plan")
    apply.add_argument("--plan", required=True)
    apply.add_argument("--report", required=True)
    apply.add_argument("--safety-dir")
    apply.add_argument("--portable-backup")
    verify = commands.add_parser("verify", help="verify a completed private report")
    verify.add_argument("--report", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "plan":
            result = create_plan(
                args.collection, args.plan, reference_inventory=args.reference_inventory,
                reference_paths=args.reference,
            )
        elif args.command == "apply":
            result = apply_plan(
                args.plan, args.report, safety_dir=args.safety_dir,
                portable_backup_path=args.portable_backup,
            )
        else:
            result = verify_report(args.report)
        summary = {
            key: result[key] for key in (
                "status", "record_count", "source_record_count",
                "rekeyed_record_count", "unchanged_record_count",
            ) if key in result
        }
        if args.command == "plan":
            summary["plan_path"] = str(Path(args.plan).absolute())
        elif args.command == "apply":
            summary["report_path"] = str(Path(args.report).absolute())
            summary["portable_backup_path"] = result.get("portable_backup_path")
        else:
            summary["report_path"] = str(Path(args.report).absolute())
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0 if result.get("success", True) and result.get("status") not in {
            "RECOVERY_REQUIRED", "MIGRATED_WITH_PORTABILITY_BLOCKER"
        } else 4
    except MigrationRecoveryRequired as error:
        safety = error.evidence.get("safety_copy_path", "UNAVAILABLE")
        print(f"RECOVERY_REQUIRED: {error}; safety_copy={safety}", file=sys.stderr)
        return 3
    except Exception as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
