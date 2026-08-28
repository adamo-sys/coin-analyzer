"""Offline manifest and audit contract for Real-World Desktop Acceptance Set v1."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Mapping

from .evaluation_case_contract import PRIVACY_CLASSIFICATIONS

SCHEMA = "coin-analyzer-real-world-desktop-acceptance-set"
VERSION = "1"
EXPECTED_ACTIONS = frozenset({"identify", "abstain"})
IMAGE_ROLES = ("obverse", "reverse")
RESERVED_ATTRIBUTION_FIELDS = (
    "mint", "mint_mark", "variety", "catalog_reference"
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class DesktopAcceptanceManifestError(ValueError):
    """The desktop acceptance manifest is unsafe, stale, or malformed."""


@dataclass(frozen=True, slots=True)
class DesktopAcceptanceImage:
    role: str
    path: Path
    relative_path: str
    sha256: str
    author: str | None
    license: str | None
    source_reference: str | None


@dataclass(frozen=True, slots=True)
class DesktopAcceptanceCase:
    case_id: str
    specimen_id: str
    expected_action: str
    expected_identity: Mapping[str, str | None]
    reserved_attribution: Mapping[str, None]
    capture_conditions: Mapping[str, str]
    privacy_classification: str
    images: tuple[DesktopAcceptanceImage, DesktopAcceptanceImage]
    notes: str


@dataclass(frozen=True, slots=True)
class DesktopAcceptanceManifest:
    root: Path
    cases: tuple[DesktopAcceptanceCase, ...]
    schema: str = SCHEMA
    version: str = VERSION


def load_desktop_acceptance_manifest(path: str | Path) -> DesktopAcceptanceManifest:
    manifest_path = Path(path).resolve()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DesktopAcceptanceManifestError(
            f"cannot read desktop acceptance manifest: {error}"
        ) from error

    if not isinstance(payload, Mapping):
        raise DesktopAcceptanceManifestError("manifest must be an object.")
    if set(payload) != {"schema", "version", "cases"}:
        raise DesktopAcceptanceManifestError("manifest fields do not match schema.")
    if payload["schema"] != SCHEMA or payload["version"] != VERSION:
        raise DesktopAcceptanceManifestError("manifest schema/version is unsupported.")
    if not isinstance(payload["cases"], list):
        raise DesktopAcceptanceManifestError("cases must be an array.")

    root = manifest_path.parent
    cases = tuple(_case(root, raw, i) for i, raw in enumerate(payload["cases"]))
    ids = tuple(case.case_id for case in cases)

    if len(ids) != len(set(ids)):
        raise DesktopAcceptanceManifestError("case IDs must be unique.")
    if ids != tuple(sorted(ids)):
        raise DesktopAcceptanceManifestError("cases must be sorted by case_id.")

    return DesktopAcceptanceManifest(root=root, cases=cases)


def audit_desktop_acceptance_manifest(
    manifest: DesktopAcceptanceManifest,
) -> dict[str, object]:
    actions = Counter(case.expected_action for case in manifest.cases)
    privacy = Counter(case.privacy_classification for case in manifest.cases)
    conditions: dict[str, Counter[str]] = {}
    hashes: dict[str, list[str]] = {}

    for case in manifest.cases:
        for key, value in case.capture_conditions.items():
            conditions.setdefault(key, Counter())[value] += 1
        for image in case.images:
            hashes.setdefault(image.sha256, []).append(
                f"{case.case_id}:{image.role}"
            )

    duplicates = {
        digest: sorted(locations)
        for digest, locations in sorted(hashes.items())
        if len(locations) > 1
    }

    return {
        "schema": manifest.schema,
        "version": manifest.version,
        "cases": len(manifest.cases),
        "images": sum(len(case.images) for case in manifest.cases),
        "expected_actions": {
            key: actions[key] for key in sorted(EXPECTED_ACTIONS)
        },
        "privacy_classifications": dict(sorted(privacy.items())),
        "capture_conditions": {
            key: dict(sorted(counter.items()))
            for key, counter in sorted(conditions.items())
        },
        "duplicate_image_hashes": duplicates,
    }


def _case(root: Path, raw: object, index: int) -> DesktopAcceptanceCase:
    name = f"cases[{index}]"
    if not isinstance(raw, Mapping):
        raise DesktopAcceptanceManifestError(f"{name} must be an object.")

    required = {
        "case_id", "specimen_id", "expected_action", "expected_identity",
        "reserved_attribution", "capture_conditions",
        "privacy_classification", "images", "notes"
    }
    if set(raw) != required:
        raise DesktopAcceptanceManifestError(f"{name} fields do not match schema.")

    case_id = _identifier(raw["case_id"], f"{name}.case_id")
    specimen_id = _identifier(raw["specimen_id"], f"{name}.specimen_id")

    action = raw["expected_action"]
    if action not in EXPECTED_ACTIONS:
        raise DesktopAcceptanceManifestError(
            f"{name}.expected_action is unsupported."
        )

    identity = _identity(raw["expected_identity"], name, action)
    attribution = _attribution(raw["reserved_attribution"], name)
    capture = _capture(raw["capture_conditions"], name)

    privacy = raw["privacy_classification"]
    if privacy not in PRIVACY_CLASSIFICATIONS:
        raise DesktopAcceptanceManifestError(
            f"{name}.privacy_classification is unsupported."
        )

    images_raw = raw["images"]
    if not isinstance(images_raw, list) or len(images_raw) != 2:
        raise DesktopAcceptanceManifestError(
            f"{name}.images must contain two entries."
        )

    images = tuple(_image(root, item, name) for item in images_raw)
    if tuple(image.role for image in images) != IMAGE_ROLES:
        raise DesktopAcceptanceManifestError(
            f"{name}.images must be ordered obverse then reverse."
        )

    notes = raw["notes"]
    if not isinstance(notes, str):
        raise DesktopAcceptanceManifestError(f"{name}.notes must be a string.")

    return DesktopAcceptanceCase(
        case_id=case_id,
        specimen_id=specimen_id,
        expected_action=action,
        expected_identity=identity,
        reserved_attribution=attribution,
        capture_conditions=capture,
        privacy_classification=privacy,
        images=images,
        notes=notes,
    )


def _identity(raw: object, name: str, action: str) -> Mapping[str, str | None]:
    if not isinstance(raw, Mapping):
        raise DesktopAcceptanceManifestError(
            f"{name}.expected_identity must be an object."
        )

    fields = ("country", "denomination", "year")
    if set(raw) != set(fields):
        raise DesktopAcceptanceManifestError(
            f"{name}.expected_identity fields do not match schema."
        )

    result = {}
    for field in fields:
        value = raw[field]
        if value is not None and (
            not isinstance(value, str) or not value.strip()
        ):
            raise DesktopAcceptanceManifestError(
                f"{name}.expected_identity.{field} must be text or null."
            )
        result[field] = value.strip() if isinstance(value, str) else None

    if action == "identify" and any(result[field] is None for field in fields):
        raise DesktopAcceptanceManifestError(
            f"{name} identify cases require complete country/denomination/year identity."
        )

    return result


def _attribution(raw: object, name: str) -> Mapping[str, None]:
    if not isinstance(raw, Mapping):
        raise DesktopAcceptanceManifestError(
            f"{name}.reserved_attribution must be an object."
        )
    if set(raw) != set(RESERVED_ATTRIBUTION_FIELDS):
        raise DesktopAcceptanceManifestError(
            f"{name}.reserved_attribution fields do not match schema."
        )
    if any(raw[field] is not None for field in RESERVED_ATTRIBUTION_FIELDS):
        raise DesktopAcceptanceManifestError(
            f"{name}.reserved_attribution fields must remain null."
        )
    return {field: None for field in RESERVED_ATTRIBUTION_FIELDS}


def _capture(raw: object, name: str) -> Mapping[str, str]:
    if not isinstance(raw, Mapping):
        raise DesktopAcceptanceManifestError(
            f"{name}.capture_conditions must be an object."
        )
    if not raw:
        raise DesktopAcceptanceManifestError(
            f"{name}.capture_conditions must not be empty."
        )

    result = {}
    for key, value in raw.items():
        if (
            not isinstance(key, str)
            or not key
            or not isinstance(value, str)
            or not value.strip()
        ):
            raise DesktopAcceptanceManifestError(
                f"{name}.capture_conditions must contain non-empty text pairs."
            )
        result[key] = value.strip()

    return dict(sorted(result.items()))


def _image(root: Path, raw: object, name: str) -> DesktopAcceptanceImage:
    if not isinstance(raw, Mapping):
        raise DesktopAcceptanceManifestError(
            f"{name}.images entries must be objects."
        )

    required = {
        "role", "path", "sha256", "author", "license", "source_reference"
    }
    if set(raw) != required:
        raise DesktopAcceptanceManifestError(
            f"{name}.images entry fields do not match schema."
        )

    role = raw["role"]
    if role not in IMAGE_ROLES:
        raise DesktopAcceptanceManifestError(
            f"{name}.image role is unsupported."
        )

    relative = _safe_path(raw["path"], f"{name}.images.{role}.path")
    digest = raw["sha256"]
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise DesktopAcceptanceManifestError(
            f"{name}.images.{role}.sha256 must be lowercase SHA-256."
        )

    path = (root / Path(*PurePosixPath(relative).parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise DesktopAcceptanceManifestError(
            f"{name}.images.{role}.path escapes the manifest root."
        ) from error

    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise DesktopAcceptanceManifestError(
            f"{name}.images.{role} cannot be read: {error}"
        ) from error

    if actual != digest:
        raise DesktopAcceptanceManifestError(
            f"{name}.images.{role} SHA-256 does not match frozen bytes."
        )

    return DesktopAcceptanceImage(
        role=role,
        path=path,
        relative_path=relative,
        sha256=digest,
        author=_nullable(raw["author"], f"{name}.author"),
        license=_nullable(raw["license"], f"{name}.license"),
        source_reference=_nullable(
            raw["source_reference"], f"{name}.source_reference"
        ),
    )


def _identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise DesktopAcceptanceManifestError(
            f"{name} is not a safe identifier."
        )
    return value


def _safe_path(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise DesktopAcceptanceManifestError(
            f"{name} must be a POSIX relative path."
        )
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ":" in path.parts[0]
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise DesktopAcceptanceManifestError(f"{name} is unsafe.")
    return path.as_posix()


def _nullable(value: object, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise DesktopAcceptanceManifestError(
            f"{name} must be non-empty text or null."
        )
    return value.strip()
