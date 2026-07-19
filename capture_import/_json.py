"""Bounded canonical JSON helpers for importer-owned metadata."""

from __future__ import annotations

import json
from typing import Any

from .limits import MAX_JSON_BYTES


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize one value as deterministic UTF-8 JSON."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > MAX_JSON_BYTES:
        raise ValueError("Importer metadata exceeds its byte limit.")
    return encoded


def parse_bounded_json_object(raw: bytes, context: str) -> dict[str, Any]:
    """Parse a bounded UTF-8 JSON object while rejecting duplicate keys."""

    if len(raw) > MAX_JSON_BYTES:
        raise ValueError(f"{context} exceeds its byte limit.")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{context} contains duplicate fields.")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{context} is not valid UTF-8 JSON.") from error
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a JSON object.")
    return value
