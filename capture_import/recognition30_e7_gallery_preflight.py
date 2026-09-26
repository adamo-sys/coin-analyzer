"""Fail-closed preflight for the private Recognition30 E7 reference gallery."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

E7_SCHEMA = "coin-analyzer-recognition30-e7-gallery-v1"
RECOGNITION30_FINGERPRINT = "5ce59a80db35b58950358eb3441cdd78b350f5bcecf0326678202366ab737a20"
_CASE_IDS = tuple(f"CA-R30-{number:03d}" for number in range(1, 31))
_SIDES = {"obverse", "reverse", "unknown"}


class E7GalleryPreflightError(ValueError):
    """Raised when the private gallery is not safe/complete enough to execute."""


@dataclass(frozen=True, slots=True)
class E7GalleryItem:
    case_id: str
    side: str
    image_path: Path
    sha256: str
    source_url: str
    source_name: str
    rights_or_license: str
    attribution: str
    same_query_image: bool
    derived_from_query: bool
    known_same_specimen: bool


def _nonempty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise E7GalleryPreflightError(f"{field} must be non-empty text")
    return value.strip()


def _bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise E7GalleryPreflightError(f"{field} must be boolean")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_item(raw: Mapping[str, object], root: Path) -> E7GalleryItem:
    case_id = _nonempty(raw.get("case_id"), "case_id")
    side = _nonempty(raw.get("side"), "side").casefold()
    if side not in _SIDES:
        raise E7GalleryPreflightError(f"{case_id}: unsupported side {side!r}")
    relative = Path(_nonempty(raw.get("image_path"), "image_path"))
    if relative.is_absolute() or ".." in relative.parts:
        raise E7GalleryPreflightError(f"{case_id}: image_path must stay inside gallery root")
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise E7GalleryPreflightError(f"{case_id}: image_path escapes gallery root") from exc
    if not path.is_file():
        raise E7GalleryPreflightError(f"{case_id}: reference image missing: {relative}")
    expected_sha = _nonempty(raw.get("sha256"), "sha256").casefold()
    if len(expected_sha) != 64 or any(ch not in "0123456789abcdef" for ch in expected_sha):
        raise E7GalleryPreflightError(f"{case_id}: sha256 is invalid")
    actual_sha = _sha256(path)
    if actual_sha != expected_sha:
        raise E7GalleryPreflightError(f"{case_id}: reference image digest mismatch")

    item = E7GalleryItem(
        case_id=case_id,
        side=side,
        image_path=path,
        sha256=expected_sha,
        source_url=_nonempty(raw.get("source_url"), "source_url"),
        source_name=_nonempty(raw.get("source_name"), "source_name"),
        rights_or_license=_nonempty(raw.get("rights_or_license"), "rights_or_license"),
        attribution=_nonempty(raw.get("attribution"), "attribution"),
        same_query_image=_bool(raw.get("same_query_image"), "same_query_image"),
        derived_from_query=_bool(raw.get("derived_from_query"), "derived_from_query"),
        known_same_specimen=_bool(raw.get("known_same_specimen"), "known_same_specimen"),
    )
    if item.same_query_image or item.derived_from_query or item.known_same_specimen:
        raise E7GalleryPreflightError(f"{case_id}: query/reference leakage declaration is not clean")
    return item


def validate_gallery_manifest(manifest_path: Path) -> tuple[E7GalleryItem, ...]:
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise E7GalleryPreflightError("manifest must be a JSON object")
    if raw.get("schema") != E7_SCHEMA:
        raise E7GalleryPreflightError("unexpected E7 gallery schema")
    if raw.get("dataset_fingerprint") != RECOGNITION30_FINGERPRINT:
        raise E7GalleryPreflightError("Recognition30 dataset fingerprint mismatch")
    rows = raw.get("items")
    if not isinstance(rows, list):
        raise E7GalleryPreflightError("items must be a list")

    root = manifest_path.parent
    items = tuple(_parse_item(row, root) for row in rows if isinstance(row, dict))
    if len(items) != len(rows):
        raise E7GalleryPreflightError("every gallery item must be an object")

    covered = {item.case_id for item in items}
    expected = set(_CASE_IDS)
    missing = sorted(expected - covered)
    unexpected = sorted(covered - expected)
    if missing or unexpected:
        raise E7GalleryPreflightError(
            f"gallery identity coverage mismatch; missing={missing}, unexpected={unexpected}"
        )

    keys = [(item.case_id, item.side, item.sha256) for item in items]
    if len(keys) != len(set(keys)):
        raise E7GalleryPreflightError("duplicate gallery item")
    return items


def preflight_report(manifest_path: Path) -> dict[str, object]:
    items = validate_gallery_manifest(manifest_path)
    return {
        "schema": "coin-analyzer-recognition30-e7-preflight-v1",
        "dataset_fingerprint": RECOGNITION30_FINGERPRINT,
        "candidate_identities": len({item.case_id for item in items}),
        "reference_images": len(items),
        "leakage_blockers": 0,
        "status": "READY_FOR_SEPARATELY_AUTHORIZED_EMBEDDING_RUN",
    }
