"""Pure field-specific validation for confirmed observation values.

This module validates the canonical OCR field vocabulary without mapping to a
collection, rewriting observations, or performing normalization orchestration.
Submitted values remain exact.  A canonical value is returned only where a
field policy explicitly defines one.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Protocol
import unicodedata

from .workflow_confirmed_observation_models import (
    ConfirmedFieldObservation,
    ConfirmedObservationSet,
)
from .workflow_ocr_models import ALLOWED_OCR_FIELDS


_UNRESOLVED_MARKERS = frozenset(
    {"defer", "deferred", "missing", "reject", "rejected", "unresolved"}
)
_DENOMINATION_PATTERN = re.compile(
    r"(?:"
    r"[1-9][0-9]{0,5}\s?(?:cent|cents|c|¢|dollar|dollars)"
    r"|\$\s?[1-9][0-9]{0,5}"
    r"|penny|nickel|dime|quarter|half dollar|dollar"
    r"|(?:five|ten|twenty|fifty|one hundred)\s?(?:cents|dollars)"
    r")",
    re.IGNORECASE,
)
_MINTMARK_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,15}")
_BANKNOTE_PREFIX_PATTERN = re.compile(r"[A-Za-z]{1,4}[0-9]{5,9}")
_CERTIFICATION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 -]{2,63}")
_GRADE_LIKE_PATTERN = re.compile(
    r"(?:MS|PF|PR|SP|AU|XF|EF|VF|F|VG|G|AG)[ -]?(?:[1-9]|[1-6][0-9]|70)[+-]?",
    re.IGNORECASE,
)
_SILVER_CANONICAL_VALUES = MappingProxyType(
    {
        "true": "true",
        "yes": "true",
        "silver": "true",
        "false": "false",
        "no": "false",
        "non-silver": "false",
    }
)


class ConfirmedObservationValidationError(ValueError):
    """Base error for field-specific confirmed-observation validation."""


class UnsupportedConfirmedObservationFieldError(
    ConfirmedObservationValidationError
):
    """The field is not in the current canonical OCR vocabulary."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(
            f"Unsupported confirmed-observation field: {field_name!r}."
        )


class InvalidConfirmedObservationValueError(
    ConfirmedObservationValidationError
):
    """A submitted value violates its field-specific policy."""

    def __init__(
        self,
        *,
        field_name: str,
        submitted_value: object,
        validation_code: str,
        message: str,
    ) -> None:
        self.field_name = field_name
        self.submitted_value = submitted_value
        self.validation_code = validation_code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ConfirmedObservationValidationResult:
    """Immutable success result; it never rewrites the source observation."""

    field_name: str
    submitted_value: str
    canonical_value: str | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "field_name": self.field_name,
            "submitted_value": self.submitted_value,
            "canonical_value": self.canonical_value,
        }


class ConfirmedObservationValidator(Protocol):
    """Pure callable contract used by the immutable field registry."""

    def __call__(self, submitted_value: str) -> str | None:
        """Validate an exact value and optionally return a canonical value."""
        ...


class ConfirmedObservationValidatorRegistry:
    """Stateless exact-name dispatch over the immutable validator registry."""

    __slots__ = ()

    @property
    def field_names(self) -> frozenset[str]:
        return frozenset(_VALIDATORS)

    def validate_value(
        self,
        *,
        field_name: str,
        submitted_value: str,
    ) -> ConfirmedObservationValidationResult:
        if not isinstance(field_name, str):
            raise TypeError("field_name must be a string.")
        if not isinstance(submitted_value, str):
            raise TypeError("submitted_value must be a string.")

        validator = _VALIDATORS.get(field_name)
        if validator is None:
            raise UnsupportedConfirmedObservationFieldError(field_name)

        canonical_value = validator(submitted_value)
        return ConfirmedObservationValidationResult(
            field_name=field_name,
            submitted_value=submitted_value,
            canonical_value=canonical_value,
        )


def validate_confirmed_observation(
    observation: ConfirmedFieldObservation,
) -> ConfirmedObservationValidationResult:
    """Validate one immutable observation without changing it."""

    if not isinstance(observation, ConfirmedFieldObservation):
        raise TypeError(
            "observation must be a ConfirmedFieldObservation."
        )
    if not isinstance(observation.field_name, str):
        raise TypeError("field_name must be a string.")
    if observation.field_name not in ALLOWED_OCR_FIELDS:
        raise UnsupportedConfirmedObservationFieldError(
            observation.field_name
        )
    result = ConfirmedObservationValidatorRegistry().validate_value(
        field_name=observation.field_name,
        submitted_value=observation.submitted_value,
    )
    observation.validate()
    return result


def validate_confirmed_observation_set(
    observation_set: ConfirmedObservationSet,
) -> tuple[ConfirmedObservationValidationResult, ...]:
    """Atomically validate a deterministically ordered observation set."""

    if not isinstance(observation_set, ConfirmedObservationSet):
        raise TypeError(
            "observation_set must be a ConfirmedObservationSet."
        )
    if not isinstance(observation_set.observations, tuple):
        raise TypeError("observations must be a tuple.")
    results = [
        validate_confirmed_observation(observation)
        for observation in observation_set.observations
    ]
    observation_set.validate()
    return tuple(results)


def _invalid(
    field_name: str,
    submitted_value: object,
    validation_code: str,
    message: str,
) -> InvalidConfirmedObservationValueError:
    return InvalidConfirmedObservationValueError(
        field_name=field_name,
        submitted_value=submitted_value,
        validation_code=validation_code,
        message=message,
    )


def _text(
    value: str,
    *,
    field_name: str,
    maximum: int,
) -> str:
    if not isinstance(value, str):
        raise TypeError("submitted_value must be a string.")
    if not value.strip():
        raise _invalid(
            field_name,
            value,
            "blank",
            f"{field_name} must not be blank.",
        )
    if len(value) > maximum:
        raise _invalid(
            field_name,
            value,
            "too_long",
            f"{field_name} exceeds its {maximum}-character limit.",
        )
    if unicodedata.normalize("NFC", value) != value:
        raise _invalid(
            field_name,
            value,
            "not_nfc",
            f"{field_name} must already be NFC-normalized.",
        )
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise _invalid(
            field_name,
            value,
            "control_character",
            f"{field_name} must not contain control characters.",
        )
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise _invalid(
            field_name,
            value,
            "surrogate",
            f"{field_name} must not contain surrogate code points.",
        )
    if value.strip().casefold() in _UNRESOLVED_MARKERS:
        raise _invalid(
            field_name,
            value,
            "unresolved_marker",
            f"{field_name} must contain a resolved value.",
        )
    return value


def _validate_year(value: str) -> None:
    value = _text(value, field_name="year", maximum=4)
    if re.fullmatch(r"[0-9]{4}", value) is None:
        raise _invalid(
            "year", value, "invalid_format",
            "year must contain exactly four decimal digits.",
        )
    if not 1000 <= int(value) <= 2999:
        raise _invalid(
            "year", value, "out_of_range",
            "year must be between 1000 and 2999.",
        )
    return None


def _validate_denomination(value: str) -> None:
    value = _text(value, field_name="denomination", maximum=64)
    if _DENOMINATION_PATTERN.fullmatch(value) is None:
        raise _invalid(
            "denomination", value, "unsupported_format",
            "denomination does not match the bounded OCR denomination vocabulary.",
        )
    return None


def _validate_country(value: str) -> None:
    _text(value, field_name="country", maximum=128)
    return None


def _validate_monarch(value: str) -> None:
    _text(value, field_name="monarch", maximum=128)
    return None


def _validate_mintmark(value: str) -> None:
    value = _text(value, field_name="mintmark", maximum=16)
    if value.casefold() in {"none", "no mintmark"}:
        raise _invalid(
            "mintmark", value, "unsupported_empty_marker",
            "mintmark must not use an empty-value marker.",
        )
    if _MINTMARK_PATTERN.fullmatch(value) is None:
        raise _invalid(
            "mintmark", value, "invalid_token",
            "mintmark must be one bounded letter, digit, period, or hyphen token.",
        )
    return None


def _validate_series_type(value: str) -> None:
    _text(value, field_name="series_type", maximum=256)
    return None


def _validate_banknote_prefix(value: str) -> None:
    value = _text(value, field_name="banknote_prefix", maximum=13)
    if _BANKNOTE_PREFIX_PATTERN.fullmatch(value) is None:
        raise _invalid(
            "banknote_prefix", value, "invalid_token",
            "banknote_prefix must contain 1-4 letters followed by 5-9 digits.",
        )
    return None


def _validate_certification_number(value: str) -> None:
    value = _text(value, field_name="certification_number", maximum=64)
    if _CERTIFICATION_PATTERN.fullmatch(value) is None or not any(
        character.isdigit() for character in value
    ):
        raise _invalid(
            "certification_number", value, "invalid_token",
            "certification_number must be a bounded alphanumeric identifier.",
        )
    if _GRADE_LIKE_PATTERN.fullmatch(value) is not None:
        raise _invalid(
            "certification_number", value, "grade_like",
            "certification_number must not be a grade-like token.",
        )
    return None


def _validate_silver_indicator(value: str) -> str:
    value = _text(value, field_name="silver_indicator", maximum=16)
    canonical = _SILVER_CANONICAL_VALUES.get(value.casefold())
    if canonical is None:
        raise _invalid(
            "silver_indicator", value, "unsupported_value",
            "silver_indicator must use the explicit confirmed vocabulary.",
        )
    return canonical


def _validate_variety_keyword(value: str) -> None:
    _text(value, field_name="variety_keyword", maximum=256)
    return None


# ALLOWED_OCR_FIELDS owns the canonical vocabulary.  This immutable registry
# supplies semantics for every current key; a drift test prevents divergence.
_VALIDATORS: MappingProxyType[
    str, ConfirmedObservationValidator
] = MappingProxyType(
    {
        "year": _validate_year,
        "denomination": _validate_denomination,
        "country": _validate_country,
        "monarch": _validate_monarch,
        "mintmark": _validate_mintmark,
        "series_type": _validate_series_type,
        "banknote_prefix": _validate_banknote_prefix,
        "certification_number": _validate_certification_number,
        "silver_indicator": _validate_silver_indicator,
        "variety_keyword": _validate_variety_keyword,
    }
)

if frozenset(_VALIDATORS) != ALLOWED_OCR_FIELDS:
    raise RuntimeError(
        "Confirmed-observation validators do not match ALLOWED_OCR_FIELDS."
    )
