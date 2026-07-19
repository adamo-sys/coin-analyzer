"""Injectable, never-expanded limits for read-only package validation."""

from __future__ import annotations

from dataclasses import dataclass

from . import limits as normative


@dataclass(frozen=True, slots=True)
class ValidationLimits:
    """Resource ceilings that tests may reduce but callers may never raise."""

    package_size: int = normative.MAX_PACKAGE_SIZE
    archive_entries: int = normative.MAX_ARCHIVE_ENTRIES
    coins: int = normative.MAX_COINS_PER_PACKAGE
    manifest_bytes: int = normative.MAX_MANIFEST_SIZE
    compressed_entry_bytes: int = normative.MAX_COMPRESSED_ENTRY_SIZE
    image_bytes: int = normative.MAX_IMAGE_SIZE
    total_uncompressed_bytes: int = normative.MAX_TOTAL_UNCOMPRESSED_SIZE
    compression_ratio: int = normative.MAX_COMPRESSION_RATIO
    image_dimension: int = normative.MAX_IMAGE_DIMENSION
    image_pixels: int = normative.MAX_IMAGE_PIXELS
    json_nesting: int = normative.MAX_JSON_NESTING
    keys_per_object: int = normative.MAX_KEYS_PER_OBJECT
    string_chars: int = normative.MAX_STRING_CHARS
    aggregate_string_chars: int = normative.MAX_AGGREGATE_STRING_CHARS

    def __post_init__(self) -> None:
        maxima = {
            "package_size": normative.MAX_PACKAGE_SIZE,
            "archive_entries": normative.MAX_ARCHIVE_ENTRIES,
            "coins": normative.MAX_COINS_PER_PACKAGE,
            "manifest_bytes": normative.MAX_MANIFEST_SIZE,
            "compressed_entry_bytes": normative.MAX_COMPRESSED_ENTRY_SIZE,
            "image_bytes": normative.MAX_IMAGE_SIZE,
            "total_uncompressed_bytes": normative.MAX_TOTAL_UNCOMPRESSED_SIZE,
            "compression_ratio": normative.MAX_COMPRESSION_RATIO,
            "image_dimension": normative.MAX_IMAGE_DIMENSION,
            "image_pixels": normative.MAX_IMAGE_PIXELS,
            "json_nesting": normative.MAX_JSON_NESTING,
            "keys_per_object": normative.MAX_KEYS_PER_OBJECT,
            "string_chars": normative.MAX_STRING_CHARS,
            "aggregate_string_chars": normative.MAX_AGGREGATE_STRING_CHARS,
        }
        for name, maximum in maxima.items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
                raise ValueError(f"{name} must be a positive normative-or-lower limit.")
