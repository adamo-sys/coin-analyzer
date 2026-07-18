"""Immutable domain models for capture-package import planning.

This module contains validation and value conversion only.  It deliberately has
no filesystem, archive, collection, or GUI dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import PurePosixPath
import re
from typing import Any, Mapping
from uuid import UUID

from .enums import Composition, DuplicateDecision, ImageRole
from .limits import (
    MAX_COINS_PER_PACKAGE,
    MAX_DECIMAL_CHARS,
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_SIZE,
    MAX_IMAGES_PER_COIN,
    MAX_PACKAGE_SIZE,
    MAX_QUANTITY,
    MAX_SAFE_INTEGER,
    MAX_STRING_CHARS,
    MISSING_COLLECTION_SENTINEL,
    SUPPORTED_IMAGE_TYPES,
    SUPPORTED_SCHEMA,
    SUPPORTED_SCHEMA_VERSION,
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_DECIMAL_RE = re.compile(r"(?:0|[0-9]+)(?:\.[0-9]+)?\Z")
_CURRENCY_RE = re.compile(r"[A-Z]{3}\Z")
_UTC_TIMESTAMP_RE = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:Z|\+00:00)\Z"
)
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)


def _require_object(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must be a JSON object.")
    if not all(isinstance(key, str) for key in value):
        raise ValueError(f"{context} keys must be strings.")
    return value


def _require_fields(
    value: Mapping[str, Any],
    required: frozenset[str],
    context: str,
    *,
    allow_extra: bool,
) -> None:
    missing = required.difference(value)
    if missing:
        raise ValueError(f"{context} is missing fields: {', '.join(sorted(missing))}.")
    if not allow_extra:
        unknown = set(value).difference(required)
        if unknown:
            raise ValueError(
                f"{context} contains unknown fields: {', '.join(sorted(unknown))}."
            )


def _require_string(
    value: Any,
    field_name: str,
    *,
    allow_empty: bool = False,
    max_chars: int = MAX_STRING_CHARS,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    if not allow_empty and not value:
        raise ValueError(f"{field_name} must not be empty.")
    if len(value) > max_chars:
        raise ValueError(f"{field_name} exceeds its character limit.")
    return value


def _require_optional_string(
    value: Any, field_name: str, *, max_chars: int = MAX_STRING_CHARS
) -> str | None:
    if value is None:
        return None
    return _require_string(value, field_name, allow_empty=True, max_chars=max_chars)


def _require_integer(
    value: Any,
    field_name: str,
    *,
    minimum: int = 0,
    maximum: int = MAX_SAFE_INTEGER,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")
    if not minimum <= value <= maximum:
        raise ValueError(f"{field_name} is outside its supported range.")
    return value


def _require_boolean(value: Any, field_name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{field_name} must be a boolean.")
    return value


def _enum_value(enum_type: type[Enum], value: Any, field_name: str) -> Enum:
    """Convert one serialized enum value with a stable validation error."""

    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} contains an unsupported value.") from exc


def _validate_uuid(value: Any, field_name: str) -> str:
    text = _require_string(value, field_name, max_chars=36)
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"{field_name} must be a UUID.") from exc
    if str(parsed) != text:
        raise ValueError(f"{field_name} must use canonical lowercase UUID form.")
    return text


def _validate_sha256(value: Any, field_name: str) -> str:
    text = _require_string(value, field_name, max_chars=64)
    if _SHA256_RE.fullmatch(text) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest.")
    return text


def _validate_timestamp(value: Any, field_name: str) -> str:
    text = _require_string(value, field_name)
    if _UTC_TIMESTAMP_RE.fullmatch(text) is None:
        raise ValueError(f"{field_name} must be a UTC RFC 3339 timestamp.")
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an RFC 3339 timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be a UTC RFC 3339 timestamp.")
    return text


def _validate_date(value: Any, field_name: str) -> str:
    text = _require_string(value, field_name)
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO calendar date.") from exc
    return text


def _validate_optional_date(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _validate_date(value, field_name)


def _validate_relative_path(value: Any, field_name: str) -> str:
    text = _require_string(value, field_name)
    if "\\" in text or ":" in text or text.startswith("/") or "\x00" in text:
        raise ValueError(f"{field_name} must be a safe relative POSIX path.")
    if "//" in text or text.endswith("/"):
        raise ValueError(f"{field_name} must be a canonical relative POSIX path.")
    parts = text.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{field_name} must be a safe relative POSIX path.")
    for part in parts:
        if part.endswith((".", " ")):
            raise ValueError(f"{field_name} must be a canonical relative POSIX path.")
        reserved_candidate = part.split(".", 1)[0].upper()
        if reserved_candidate in _WINDOWS_RESERVED_NAMES:
            raise ValueError(f"{field_name} contains a reserved path component.")
    return text


def _validate_basename(value: Any, field_name: str) -> str:
    text = _require_string(value, field_name)
    if (
        "/" in text
        or "\\" in text
        or ":" in text
        or "\x00" in text
        or text in {".", ".."}
    ):
        raise ValueError(f"{field_name} must contain only a filename basename.")
    return text


def _parse_decimal_text(value: Any, field_name: str) -> Decimal:
    text = _require_string(value, field_name, max_chars=MAX_DECIMAL_CHARS)
    if _DECIMAL_RE.fullmatch(text) is None:
        raise ValueError(f"{field_name} must be a plain non-negative decimal string.")
    try:
        parsed = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"{field_name} is not a valid decimal.") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{field_name} must be finite and non-negative.")
    return parsed


def _parse_currency(value: Any, field_name: str) -> str:
    text = _require_string(value, field_name)
    normalized = text.upper()
    if _CURRENCY_RE.fullmatch(normalized) is None:
        raise ValueError(f"{field_name} must contain three ASCII letters.")
    return normalized


def _validate_decimal(value: Any, field_name: str) -> Decimal:
    if not isinstance(value, Decimal):
        raise ValueError(f"{field_name} must be a Decimal.")
    if not value.is_finite() or value < 0:
        raise ValueError(f"{field_name} must be finite and non-negative.")
    if len(format(value, "f")) > MAX_DECIMAL_CHARS:
        raise ValueError(f"{field_name} exceeds its character limit.")
    return value


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _require_unique_strings(values: tuple[str, ...], field_name: str) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{field_name} must be an immutable tuple.")
    for value in values:
        _require_string(value, field_name)
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must contain unique values.")


@dataclass(frozen=True, slots=True)
class PackageImage:
    """One declared image in a capture-package manifest."""

    role: ImageRole
    path: str
    original_name: str
    mime_type: str
    byte_length: int
    width: int
    height: int
    captured_at: str

    def validate(self) -> None:
        if not isinstance(self.role, ImageRole):
            raise ValueError("role must be an ImageRole.")
        path = _validate_relative_path(self.path, "path")
        _require_string(self.original_name, "original_name")
        if self.mime_type not in SUPPORTED_IMAGE_TYPES:
            raise ValueError("mime_type is not supported by package format 1.0.")
        _require_integer(self.byte_length, "byte_length", minimum=1, maximum=MAX_IMAGE_SIZE)
        width = _require_integer(
            self.width, "width", minimum=1, maximum=MAX_IMAGE_DIMENSION
        )
        height = _require_integer(
            self.height, "height", minimum=1, maximum=MAX_IMAGE_DIMENSION
        )
        if width * height > MAX_IMAGE_PIXELS:
            raise ValueError("image dimensions exceed the decoded-pixel limit.")
        _validate_timestamp(self.captured_at, "captured_at")
        suffix = PurePosixPath(path).suffix
        expected = ".jpg" if self.mime_type == "image/jpeg" else ".png"
        if suffix != expected:
            raise ValueError("path extension and mime_type do not agree.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "path": self.path,
            "original_name": self.original_name,
            "mime_type": self.mime_type,
            "byte_length": self.byte_length,
            "width": self.width,
            "height": self.height,
            "captured_at": self.captured_at,
        }

    @classmethod
    def from_dict(
        cls, role: ImageRole, value: Mapping[str, Any]
    ) -> "PackageImage":
        data = _require_object(value, "PackageImage")
        required = frozenset(
            {
                "path",
                "original_name",
                "mime_type",
                "byte_length",
                "width",
                "height",
                "captured_at",
            }
        )
        _require_fields(data, required, "PackageImage", allow_extra=True)
        if not isinstance(role, ImageRole):
            raise ValueError("role must be an ImageRole.")
        result = cls(
            role=role,
            path=_require_string(data["path"], "path"),
            original_name=_require_string(data["original_name"], "original_name"),
            mime_type=_require_string(data["mime_type"], "mime_type"),
            byte_length=_require_integer(data["byte_length"], "byte_length", minimum=1),
            width=_require_integer(data["width"], "width", minimum=1),
            height=_require_integer(data["height"], "height", minimum=1),
            captured_at=_require_string(data["captured_at"], "captured_at"),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class PackageCoin:
    """One immutable coin record declared by package format 1.0."""

    id: str
    position: int
    country: str
    denomination: str
    year: str
    mint: str
    purchase_price: Decimal
    purchase_currency: str
    seller: str
    purchase_date: str | None
    notes: str
    quantity: int
    composition: Composition
    is_bullion: bool
    asw_troy_ounces: Decimal | None
    photos: tuple[PackageImage, ...]
    created_at: str
    updated_at: str

    def validate(self) -> None:
        _require_string(self.id, "coin.id")
        _require_integer(self.position, "coin.position")
        _require_string(self.country, "coin.country")
        _require_string(self.denomination, "coin.denomination")
        _require_string(self.year, "coin.year")
        _require_string(self.mint, "coin.mint", allow_empty=True)
        _validate_decimal(self.purchase_price, "coin.purchase_price")
        if not isinstance(self.purchase_currency, str) or _CURRENCY_RE.fullmatch(
            self.purchase_currency
        ) is None:
            raise ValueError("coin.purchase_currency must be three uppercase letters.")
        _require_string(self.seller, "coin.seller", allow_empty=True)
        _validate_optional_date(self.purchase_date, "coin.purchase_date")
        _require_string(self.notes, "coin.notes", allow_empty=True)
        _require_integer(
            self.quantity, "coin.quantity", minimum=1, maximum=MAX_QUANTITY
        )
        if not isinstance(self.composition, Composition):
            raise ValueError("coin.composition must be a Composition.")
        _require_boolean(self.is_bullion, "coin.is_bullion")
        if self.asw_troy_ounces is not None:
            _validate_decimal(self.asw_troy_ounces, "coin.asw_troy_ounces")
        if not isinstance(self.photos, tuple):
            raise ValueError("coin.photos must be an immutable tuple.")
        if not 1 <= len(self.photos) <= MAX_IMAGES_PER_COIN:
            raise ValueError("coin.photos has an unsupported number of records.")
        for image in self.photos:
            if not isinstance(image, PackageImage):
                raise ValueError("coin.photos must contain PackageImage values.")
            image.validate()
        roles = tuple(image.role for image in self.photos)
        if len(set(roles)) != len(roles):
            raise ValueError("coin.photos contains duplicate roles.")
        if ImageRole.FRONT not in roles or ImageRole.REVERSE not in roles:
            raise ValueError("coin.photos must contain front and reverse photos.")
        paths = tuple(image.path for image in self.photos)
        if len(set(paths)) != len(paths):
            raise ValueError("coin.photos must contain unique paths.")
        _validate_timestamp(self.created_at, "coin.created_at")
        _validate_timestamp(self.updated_at, "coin.updated_at")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "id": self.id,
            "position": self.position,
            "country": self.country,
            "denomination": self.denomination,
            "year": self.year,
            "mint": self.mint,
            "purchase_price": _decimal_text(self.purchase_price),
            "purchase_currency": self.purchase_currency,
            "seller": self.seller,
            "purchase_date": self.purchase_date,
            "notes": self.notes,
            "quantity": self.quantity,
            "composition": self.composition.value,
            "is_bullion": self.is_bullion,
            "asw_troy_ounces": (
                None
                if self.asw_troy_ounces is None
                else _decimal_text(self.asw_troy_ounces)
            ),
            "photos": {
                image.role.value: image.to_dict()
                for image in sorted(self.photos, key=lambda item: item.role.value)
            },
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PackageCoin":
        data = _require_object(value, "PackageCoin")
        required = frozenset(
            {
                "id",
                "position",
                "country",
                "denomination",
                "year",
                "mint",
                "purchase_price",
                "purchase_currency",
                "seller",
                "purchase_date",
                "notes",
                "quantity",
                "composition",
                "is_bullion",
                "asw_troy_ounces",
                "photos",
                "created_at",
                "updated_at",
            }
        )
        _require_fields(data, required, "PackageCoin", allow_extra=True)
        photos = _require_object(data["photos"], "coin.photos")
        unknown_roles = set(photos).difference(role.value for role in ImageRole)
        if unknown_roles:
            raise ValueError("coin.photos contains an unsupported photo role.")
        try:
            composition = Composition(data["composition"])
        except (TypeError, ValueError) as exc:
            raise ValueError("coin.composition is not supported.") from exc
        asw = (
            None
            if data["asw_troy_ounces"] is None
            else _parse_decimal_text(data["asw_troy_ounces"], "coin.asw_troy_ounces")
        )
        result = cls(
            id=_require_string(data["id"], "coin.id"),
            position=_require_integer(data["position"], "coin.position"),
            country=_require_string(data["country"], "coin.country"),
            denomination=_require_string(data["denomination"], "coin.denomination"),
            year=_require_string(data["year"], "coin.year"),
            mint=_require_string(data["mint"], "coin.mint", allow_empty=True),
            purchase_price=_parse_decimal_text(
                data["purchase_price"], "coin.purchase_price"
            ),
            purchase_currency=_parse_currency(
                data["purchase_currency"], "coin.purchase_currency"
            ),
            seller=_require_string(data["seller"], "coin.seller", allow_empty=True),
            purchase_date=_validate_optional_date(
                data["purchase_date"], "coin.purchase_date"
            ),
            notes=_require_string(data["notes"], "coin.notes", allow_empty=True),
            quantity=_require_integer(
                data["quantity"], "coin.quantity", minimum=1, maximum=MAX_QUANTITY
            ),
            composition=composition,
            is_bullion=_require_boolean(data["is_bullion"], "coin.is_bullion"),
            asw_troy_ounces=asw,
            photos=tuple(
                PackageImage.from_dict(ImageRole(role), photo)
                for role, photo in sorted(photos.items())
            ),
            created_at=_require_string(data["created_at"], "coin.created_at"),
            updated_at=_require_string(data["updated_at"], "coin.updated_at"),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class PackageSession:
    """Capture-session metadata retained as package provenance."""

    id: str
    name: str
    description: str
    session_date: str | None
    created_at: str
    updated_at: str

    def validate(self) -> None:
        _require_string(self.id, "session.id")
        _require_string(self.name, "session.name")
        _require_string(self.description, "session.description", allow_empty=True)
        _validate_optional_date(self.session_date, "session.session_date")
        _validate_timestamp(self.created_at, "session.created_at")
        _validate_timestamp(self.updated_at, "session.updated_at")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "session_date": self.session_date,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PackageSession":
        data = _require_object(value, "PackageSession")
        required = frozenset(
            {"id", "name", "description", "session_date", "created_at", "updated_at"}
        )
        _require_fields(data, required, "PackageSession", allow_extra=True)
        result = cls(
            id=_require_string(data["id"], "session.id"),
            name=_require_string(data["name"], "session.name"),
            description=_require_string(
                data["description"], "session.description", allow_empty=True
            ),
            session_date=_validate_optional_date(
                data["session_date"], "session.session_date"
            ),
            created_at=_require_string(data["created_at"], "session.created_at"),
            updated_at=_require_string(data["updated_at"], "session.updated_at"),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class PackageManifest:
    """Validated, immutable capture-package manifest."""

    schema: str
    package_version: str
    created_by: str
    created_with: str
    exported_at: str
    session: PackageSession
    coins: tuple[PackageCoin, ...]

    def validate(self) -> None:
        if self.schema != SUPPORTED_SCHEMA:
            raise ValueError("schema is not supported.")
        if self.package_version != SUPPORTED_SCHEMA_VERSION:
            raise ValueError("package_version is not supported.")
        _require_string(self.created_by, "created_by")
        _require_string(self.created_with, "created_with")
        _validate_timestamp(self.exported_at, "exported_at")
        if not isinstance(self.session, PackageSession):
            raise ValueError("session must be a PackageSession.")
        self.session.validate()
        if not isinstance(self.coins, tuple):
            raise ValueError("coins must be an immutable tuple.")
        if not 1 <= len(self.coins) <= MAX_COINS_PER_PACKAGE:
            raise ValueError("coins must contain between 1 and 100 records.")
        for coin in self.coins:
            if not isinstance(coin, PackageCoin):
                raise ValueError("coins must contain PackageCoin values.")
            coin.validate()
        ids = tuple(coin.id for coin in self.coins)
        positions = tuple(coin.position for coin in self.coins)
        if len(set(ids)) != len(ids):
            raise ValueError("coin IDs must be unique.")
        if positions != tuple(range(len(self.coins))):
            raise ValueError("coin positions must be contiguous and begin at zero.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema": self.schema,
            "package_version": self.package_version,
            "created_by": self.created_by,
            "created_with": self.created_with,
            "exported_at": self.exported_at,
            "session": self.session.to_dict(),
            "coins": [coin.to_dict() for coin in self.coins],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PackageManifest":
        data = _require_object(value, "PackageManifest")
        required = frozenset(
            {
                "schema",
                "package_version",
                "created_by",
                "created_with",
                "exported_at",
                "session",
                "coins",
            }
        )
        _require_fields(data, required, "PackageManifest", allow_extra=True)
        if not isinstance(data["coins"], list):
            raise ValueError("coins must be an array.")
        result = cls(
            schema=_require_string(data["schema"], "schema"),
            package_version=_require_string(data["package_version"], "package_version"),
            created_by=_require_string(data["created_by"], "created_by"),
            created_with=_require_string(data["created_with"], "created_with"),
            exported_at=_require_string(data["exported_at"], "exported_at"),
            session=PackageSession.from_dict(data["session"]),
            coins=tuple(PackageCoin.from_dict(item) for item in data["coins"]),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class CollectionBaseline:
    """Exact-byte identity of the collection observed during preview."""

    sha256_or_sentinel: str
    byte_length: int

    def validate(self) -> None:
        if self.sha256_or_sentinel == MISSING_COLLECTION_SENTINEL:
            if self.byte_length != 0:
                raise ValueError("A missing collection baseline must have zero bytes.")
            return
        _validate_sha256(self.sha256_or_sentinel, "collection baseline SHA-256")
        _require_integer(self.byte_length, "collection baseline byte_length")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "sha256_or_sentinel": self.sha256_or_sentinel,
            "byte_length": self.byte_length,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CollectionBaseline":
        data = _require_object(value, "CollectionBaseline")
        required = frozenset({"sha256_or_sentinel", "byte_length"})
        _require_fields(data, required, "CollectionBaseline", allow_extra=False)
        result = cls(
            sha256_or_sentinel=_require_string(
                data["sha256_or_sentinel"], "sha256_or_sentinel"
            ),
            byte_length=_require_integer(data["byte_length"], "byte_length"),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class PreviewCoin:
    """Read-only proposal for one package coin."""

    source_coin: PackageCoin
    duplicate_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def validate(self) -> None:
        if not isinstance(self.source_coin, PackageCoin):
            raise ValueError("source_coin must be a PackageCoin.")
        self.source_coin.validate()
        _require_unique_strings(self.duplicate_reasons, "duplicate_reasons")
        _require_unique_strings(self.warnings, "warnings")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "source_coin": self.source_coin.to_dict(),
            "duplicate_reasons": list(self.duplicate_reasons),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PreviewCoin":
        data = _require_object(value, "PreviewCoin")
        required = frozenset({"source_coin", "duplicate_reasons", "warnings"})
        _require_fields(data, required, "PreviewCoin", allow_extra=False)
        if not isinstance(data["duplicate_reasons"], list) or not isinstance(
            data["warnings"], list
        ):
            raise ValueError("PreviewCoin reasons and warnings must be arrays.")
        result = cls(
            source_coin=PackageCoin.from_dict(data["source_coin"]),
            duplicate_reasons=tuple(data["duplicate_reasons"]),
            warnings=tuple(data["warnings"]),
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class ImportDecision:
    """Explicit collector decision for one proposed source coin."""

    source_coin_id: str
    decision: DuplicateDecision

    def validate(self) -> None:
        _require_string(self.source_coin_id, "source_coin_id")
        if not isinstance(self.decision, DuplicateDecision):
            raise ValueError("decision must be a DuplicateDecision.")

    def to_dict(self) -> dict[str, str]:
        self.validate()
        return {"source_coin_id": self.source_coin_id, "decision": self.decision.value}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ImportDecision":
        data = _require_object(value, "ImportDecision")
        required = frozenset({"source_coin_id", "decision"})
        _require_fields(data, required, "ImportDecision", allow_extra=False)
        try:
            decision = DuplicateDecision(data["decision"])
        except (TypeError, ValueError) as exc:
            raise ValueError("decision is not supported.") from exc
        result = cls(
            source_coin_id=_require_string(data["source_coin_id"], "source_coin_id"),
            decision=decision,
        )
        result.validate()
        return result


@dataclass(frozen=True, slots=True)
class ImportSession:
    """Read-only import proposal bound to package and collection identities."""

    package_basename: str
    package_sha256: str
    package_byte_length: int
    collection_baseline: CollectionBaseline
    preview_coins: tuple[PreviewCoin, ...]
    decisions: tuple[ImportDecision, ...]

    def validate(self) -> None:
        basename = _validate_basename(self.package_basename, "package_basename")
        if not basename.lower().endswith(".ca-package"):
            raise ValueError("package_basename must end with .ca-package.")
        _validate_sha256(self.package_sha256, "package_sha256")
        _require_integer(
            self.package_byte_length,
            "package_byte_length",
            minimum=1,
            maximum=MAX_PACKAGE_SIZE,
        )
        if not isinstance(self.collection_baseline, CollectionBaseline):
            raise ValueError("collection_baseline must be a CollectionBaseline.")
        self.collection_baseline.validate()
        if not isinstance(self.preview_coins, tuple) or not isinstance(
            self.decisions, tuple
        ):
            raise ValueError("preview_coins and decisions must be immutable tuples.")
        for preview in self.preview_coins:
            if not isinstance(preview, PreviewCoin):
                raise ValueError("preview_coins must contain PreviewCoin values.")
            preview.validate()
        for decision in self.decisions:
            if not isinstance(decision, ImportDecision):
                raise ValueError("decisions must contain ImportDecision values.")
            decision.validate()
        preview_ids = tuple(item.source_coin.id for item in self.preview_coins)
        decision_ids = tuple(item.source_coin_id for item in self.decisions)
        if len(set(preview_ids)) != len(preview_ids):
            raise ValueError("preview_coins must have unique source IDs.")
        if len(set(decision_ids)) != len(decision_ids):
            raise ValueError("decisions must have unique source IDs.")
        if decision_ids != preview_ids:
            raise ValueError(
                "Decisions must match preview coin IDs exactly and in order."
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "package_basename": self.package_basename,
            "package_sha256": self.package_sha256,
            "package_byte_length": self.package_byte_length,
            "collection_baseline": self.collection_baseline.to_dict(),
            "preview_coins": [item.to_dict() for item in self.preview_coins],
            "decisions": [item.to_dict() for item in self.decisions],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ImportSession":
        data = _require_object(value, "ImportSession")
        required = frozenset(
            {
                "package_basename",
                "package_sha256",
                "package_byte_length",
                "collection_baseline",
                "preview_coins",
                "decisions",
            }
        )
        _require_fields(data, required, "ImportSession", allow_extra=False)
        if not isinstance(data["preview_coins"], list) or not isinstance(
            data["decisions"], list
        ):
            raise ValueError("ImportSession collections must be arrays.")
        result = cls(
            package_basename=_require_string(data["package_basename"], "package_basename"),
            package_sha256=_require_string(data["package_sha256"], "package_sha256"),
            package_byte_length=_require_integer(
                data["package_byte_length"],
                "package_byte_length",
                minimum=1,
                maximum=MAX_PACKAGE_SIZE,
            ),
            collection_baseline=CollectionBaseline.from_dict(
                data["collection_baseline"]
            ),
            preview_coins=tuple(PreviewCoin.from_dict(item) for item in data["preview_coins"]),
            decisions=tuple(ImportDecision.from_dict(item) for item in data["decisions"]),
        )
        result.validate()
        return result
