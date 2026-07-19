"""Strict, bounded capture-package manifest parsing."""

from __future__ import annotations

import json
import math
from typing import Any

from .errors import EmptyPackage, InvalidManifest, PackageTooLarge, UnsupportedVersion
from .limits import SUPPORTED_SCHEMA, SUPPORTED_SCHEMA_VERSION
from .models import PackageManifest
from .validation_limits import ValidationLimits


class CapturePackageManifestParser:
    """Parse format 1.0 JSON without permissive decoder behavior."""

    def __init__(self, limits: ValidationLimits | None = None) -> None:
        self.limits = limits or ValidationLimits()

    def parse(self, payload: bytes) -> PackageManifest:
        if not isinstance(payload, bytes) or len(payload) > self.limits.manifest_bytes:
            raise PackageTooLarge()
        try:
            text = payload.decode("utf-8", errors="strict")
            if text.startswith("\ufeff"):
                raise ValueError("BOM is not accepted")
            value = json.loads(
                text,
                object_pairs_hook=self._object_without_duplicates,
                parse_constant=self._reject_constant,
            )
            if not isinstance(value, dict):
                raise ValueError("root must be an object")
            self._validate_budget(value)
            if not isinstance(value.get("schema"), str) or not isinstance(
                value.get("package_version"), str
            ):
                raise ValueError("schema and package_version must be strings")
            if value["schema"] != SUPPORTED_SCHEMA or value["package_version"] != SUPPORTED_SCHEMA_VERSION:
                raise UnsupportedVersion()
            coins = value.get("coins")
            if isinstance(coins, list) and not coins:
                raise EmptyPackage()
            if isinstance(coins, list) and len(coins) > self.limits.coins:
                raise PackageTooLarge()
            return PackageManifest.from_dict(value)
        except (EmptyPackage, PackageTooLarge, UnsupportedVersion):
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise InvalidManifest(error) from error

    @staticmethod
    def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = value
        return result

    @staticmethod
    def _reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON number: {value}")

    def _validate_budget(self, root: Any) -> None:
        aggregate_strings = 0

        def visit(value: Any, depth: int) -> None:
            nonlocal aggregate_strings
            if depth > self.limits.json_nesting:
                raise ValueError("JSON nesting exceeds limit")
            if isinstance(value, dict):
                if len(value) > self.limits.keys_per_object:
                    raise ValueError("JSON object key count exceeds limit")
                for key, child in value.items():
                    count_string(key)
                    visit(child, depth + 1)
            elif isinstance(value, list):
                for child in value:
                    visit(child, depth + 1)
            elif isinstance(value, str):
                count_string(value)
            elif isinstance(value, int) and not isinstance(value, bool):
                if abs(value) > (2**53) - 1:
                    raise ValueError("JSON integer exceeds exact range")
            elif isinstance(value, float) and not math.isfinite(value):
                raise ValueError("JSON number must be finite")

        def count_string(value: str) -> None:
            nonlocal aggregate_strings
            if len(value) > self.limits.string_chars:
                raise ValueError("JSON string exceeds limit")
            aggregate_strings += len(value)
            if aggregate_strings > self.limits.aggregate_string_chars:
                raise ValueError("aggregate JSON strings exceed limit")

        visit(root, 1)
