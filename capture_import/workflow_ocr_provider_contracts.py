"""Transient OCR provider failure and capability contracts.

These contracts describe what an OCR provider can do and how provider
invocation can fail.  They do not select or invoke providers, inspect runtime
availability, persist capability snapshots, or alter the opt-in OCR pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .enums import ImageRole as _ImageRole
from .workflow_ocr_models import ALLOWED_OCR_FIELDS as _ALLOWED_OCR_FIELDS


__all__ = [
    "OCRProviderContractError",
    "InvalidOCRProviderContractError",
    "OCRProviderError",
    "OCRProviderUnavailableError",
    "OCRProviderInputError",
    "OCRProviderExecutionError",
    "OCRProviderOutputError",
    "OCRProviderCleanupError",
    "OCRProviderAvailability",
    "OCRProviderFieldSupportMode",
    "OCRProviderCapabilities",
]


_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")
_DIAGNOSTIC_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_MEDIA_TYPE = re.compile(
    r"^[a-z][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$"
)
_IMAGE_ROLE_ORDER = tuple(_ImageRole)


class OCRProviderContractError(ValueError):
    """An OCR provider capability contract is malformed."""


class InvalidOCRProviderContractError(OCRProviderContractError):
    """An OCR provider contract value violates the public invariants."""


class OCRProviderError(Exception):
    """Provider-neutral base for sanitized OCR invocation failures."""

    __slots__ = ("_provider_id", "_diagnostic_code", "_locked")

    _failure_description = "failed"

    def __init__(self, provider_id: str, diagnostic_code: str) -> None:
        validated_provider_id = _validate_provider_id(provider_id)
        validated_code = _validate_diagnostic_code(diagnostic_code)
        object.__setattr__(self, "_provider_id", validated_provider_id)
        object.__setattr__(self, "_diagnostic_code", validated_code)
        object.__setattr__(self, "_locked", False)
        super().__init__(
            f"OCR provider {validated_provider_id!r} "
            f"{self._failure_description} ({validated_code})."
        )
        object.__setattr__(self, "_locked", True)

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def diagnostic_code(self) -> str:
        return self._diagnostic_code

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_locked", False):
            raise AttributeError("OCR provider errors are immutable.")
        object.__setattr__(self, name, value)


class OCRProviderUnavailableError(OCRProviderError):
    """The provider cannot currently execute."""

    _failure_description = "is unavailable"


class OCRProviderInputError(OCRProviderError):
    """The provider rejected unsupported or malformed input."""

    _failure_description = "rejected its input"


class OCRProviderExecutionError(OCRProviderError):
    """The provider started but failed during OCR execution."""

    _failure_description = "failed during execution"


class OCRProviderOutputError(OCRProviderError):
    """The provider returned malformed or contradictory output."""

    _failure_description = "returned invalid output"


class OCRProviderCleanupError(OCRProviderError):
    """Cleanup of provider-owned temporary artifacts failed."""

    _failure_description = "failed during cleanup"


class OCRProviderAvailability(str, Enum):
    """Caller-supplied runtime availability snapshot."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class OCRProviderFieldSupportMode(str, Enum):
    """Whether the provider makes an exact supported-field declaration."""

    DECLARED = "DECLARED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class OCRProviderCapabilities:
    """Immutable, descriptive capability snapshot for one OCR provider.

    ``availability`` is supplied by the caller.  Constructing this DTO performs
    no dependency check and the snapshot is neither aged nor persisted.
    ``UNKNOWN`` field support makes no claim of unrestricted or universal
    support.
    """

    provider_id: str
    availability: OCRProviderAvailability
    supported_image_roles: tuple[_ImageRole, ...]
    supported_media_types: tuple[str, ...]
    field_support_mode: OCRProviderFieldSupportMode
    supported_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _validate_provider_id(self.provider_id)
        if not isinstance(self.availability, OCRProviderAvailability):
            raise InvalidOCRProviderContractError(
                "availability must be an OCRProviderAvailability."
            )
        _validate_image_roles(self.supported_image_roles)
        _validate_media_types(self.supported_media_types)
        if not isinstance(
            self.field_support_mode,
            OCRProviderFieldSupportMode,
        ):
            raise InvalidOCRProviderContractError(
                "field_support_mode must be an OCRProviderFieldSupportMode."
            )
        _validate_supported_fields(
            self.field_support_mode,
            self.supported_fields,
        )


def _validate_provider_id(value: object) -> str:
    if not isinstance(value, str) or _PROVIDER_ID.fullmatch(value) is None:
        raise InvalidOCRProviderContractError(
            "provider_id must match [a-z][a-z0-9._-]{0,127}."
        )
    return value


def _validate_diagnostic_code(value: object) -> str:
    if not isinstance(value, str) or _DIAGNOSTIC_CODE.fullmatch(value) is None:
        raise InvalidOCRProviderContractError(
            "diagnostic_code must match [A-Z][A-Z0-9_]{0,63}."
        )
    return value


def _validate_image_roles(value: object) -> None:
    if not isinstance(value, tuple):
        raise InvalidOCRProviderContractError(
            "supported_image_roles must be an immutable tuple."
        )
    if not value:
        raise InvalidOCRProviderContractError(
            "supported_image_roles must not be empty."
        )
    if any(not isinstance(item, _ImageRole) for item in value):
        raise InvalidOCRProviderContractError(
            "supported_image_roles must contain ImageRole values."
        )
    if len(set(value)) != len(value):
        raise InvalidOCRProviderContractError(
            "supported_image_roles must not contain duplicates."
        )
    canonical = tuple(role for role in _IMAGE_ROLE_ORDER if role in value)
    if value != canonical:
        raise InvalidOCRProviderContractError(
            "supported_image_roles must use canonical ImageRole order."
        )


def _validate_media_types(value: object) -> None:
    if not isinstance(value, tuple):
        raise InvalidOCRProviderContractError(
            "supported_media_types must be an immutable tuple."
        )
    if not value:
        raise InvalidOCRProviderContractError(
            "supported_media_types must not be empty."
        )
    if any(
        not isinstance(item, str) or _MEDIA_TYPE.fullmatch(item) is None
        for item in value
    ):
        raise InvalidOCRProviderContractError(
            "supported_media_types must contain normalized MIME types."
        )
    if len(set(value)) != len(value):
        raise InvalidOCRProviderContractError(
            "supported_media_types must not contain duplicates."
        )
    if value != tuple(sorted(value)):
        raise InvalidOCRProviderContractError(
            "supported_media_types must use lexical order."
        )


def _validate_supported_fields(
    mode: OCRProviderFieldSupportMode,
    value: object,
) -> None:
    if not isinstance(value, tuple):
        raise InvalidOCRProviderContractError(
            "supported_fields must be an immutable tuple."
        )
    if any(
        not isinstance(item, str) or item not in _ALLOWED_OCR_FIELDS
        for item in value
    ):
        raise InvalidOCRProviderContractError(
            "supported_fields contains an unknown OCR field."
        )
    if len(set(value)) != len(value):
        raise InvalidOCRProviderContractError(
            "supported_fields must not contain duplicates."
        )
    if value != tuple(sorted(value)):
        raise InvalidOCRProviderContractError(
            "supported_fields must use lexical order."
        )
    if mode is OCRProviderFieldSupportMode.DECLARED and not value:
        raise InvalidOCRProviderContractError(
            "DECLARED field support requires at least one field."
        )
    if mode is OCRProviderFieldSupportMode.UNKNOWN and value:
        raise InvalidOCRProviderContractError(
            "UNKNOWN field support cannot declare supported fields."
        )
