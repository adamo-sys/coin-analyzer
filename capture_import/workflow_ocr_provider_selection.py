"""Immutable OCR provider registry and deterministic capability selection.

This module selects capability snapshots only.  It never owns or invokes OCR
providers, discovers runtime dependencies, retries work, or changes the
existing OCR execution Protocols.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .enums import ImageRole as _ImageRole
from .workflow_ocr_models import ALLOWED_OCR_FIELDS as _ALLOWED_OCR_FIELDS
from .workflow_ocr_provider_contracts import (
    OCRProviderAvailability as _OCRProviderAvailability,
    OCRProviderCapabilities as _OCRProviderCapabilities,
    OCRProviderFieldSupportMode as _OCRProviderFieldSupportMode,
)


__all__ = [
    "OCRProviderSelectionContractError",
    "InvalidOCRProviderSelectionContextError",
    "OCRProviderSelectionError",
    "UnknownOCRProviderSelectionReferenceError",
    "NoEligibleOCRProviderError",
    "AmbiguousOCRProviderSelectionError",
    "OCRProviderAvailabilityPolicy",
    "OCRProviderSelectionStatus",
    "OCRProviderSelectionReason",
    "OCRProviderRegistry",
    "OCRProviderSelectionCriteria",
    "OCRProviderSelectionFinding",
    "OCRProviderSelectionResult",
    "require_registered_ocr_provider",
    "select_ocr_providers",
    "require_single_selected_ocr_provider",
]


_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")
_MEDIA_TYPE = re.compile(
    r"^[a-z][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$"
)


class OCRProviderSelectionContractError(ValueError):
    """An immutable provider-selection contract is malformed."""


class InvalidOCRProviderSelectionContextError(
    OCRProviderSelectionContractError
):
    """Registry, criteria, finding, or result invariants were violated."""


class OCRProviderSelectionError(Exception):
    """A valid selection request cannot produce the required outcome."""

    __slots__ = ("_locked",)

    def __init__(self, message: str) -> None:
        object.__setattr__(self, "_locked", False)
        super().__init__(message)
        object.__setattr__(self, "_locked", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_locked", False):
            raise AttributeError("OCR provider selection errors are immutable.")
        object.__setattr__(self, name, value)


class UnknownOCRProviderSelectionReferenceError(OCRProviderSelectionError):
    """A requested provider ID is not present in the supplied registry."""

    __slots__ = ("_provider_id",)

    def __init__(self, provider_id: str) -> None:
        validated_provider_id = _validate_provider_id(provider_id)
        object.__setattr__(self, "_provider_id", validated_provider_id)
        super().__init__(
            f"OCR provider {validated_provider_id!r} "
            "is not present in the registry."
        )

    @property
    def provider_id(self) -> str:
        return self._provider_id


class NoEligibleOCRProviderError(OCRProviderSelectionError):
    """Strict selection found no eligible provider."""

    def __init__(self) -> None:
        super().__init__("No OCR provider satisfies the selection criteria.")


class AmbiguousOCRProviderSelectionError(OCRProviderSelectionError):
    """Strict selection found more than one eligible provider."""

    __slots__ = ("_provider_ids",)

    def __init__(self, provider_ids: tuple[str, ...]) -> None:
        _validate_provider_ids(
            provider_ids,
            "provider_ids",
            allow_empty=False,
        )
        if len(provider_ids) < 2:
            raise InvalidOCRProviderSelectionContextError(
                "provider_ids must contain at least two provider IDs."
            )
        object.__setattr__(self, "_provider_ids", provider_ids)
        super().__init__(
            "More than one OCR provider satisfies the selection criteria: "
            + ", ".join(provider_ids)
            + "."
        )

    @property
    def provider_ids(self) -> tuple[str, ...]:
        return self._provider_ids


class OCRProviderAvailabilityPolicy(str, Enum):
    """How a caller-supplied UNKNOWN availability snapshot is treated."""

    REQUIRE_AVAILABLE = "REQUIRE_AVAILABLE"
    ALLOW_UNKNOWN = "ALLOW_UNKNOWN"


class OCRProviderSelectionStatus(str, Enum):
    """Eligibility of one registered capability snapshot."""

    ELIGIBLE = "ELIGIBLE"
    EXCLUDED = "EXCLUDED"


class OCRProviderSelectionReason(str, Enum):
    """Deterministic primary reason for one provider finding."""

    MATCHED = "MATCHED"
    PROVIDER_NOT_ALLOWED = "PROVIDER_NOT_ALLOWED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_AVAILABILITY_UNKNOWN = "PROVIDER_AVAILABILITY_UNKNOWN"
    IMAGE_ROLE_UNSUPPORTED = "IMAGE_ROLE_UNSUPPORTED"
    MEDIA_TYPE_UNSUPPORTED = "MEDIA_TYPE_UNSUPPORTED"
    FIELD_SUPPORT_UNKNOWN = "FIELD_SUPPORT_UNKNOWN"
    REQUIRED_FIELDS_UNSUPPORTED = "REQUIRED_FIELDS_UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class OCRProviderRegistry:
    """Canonical immutable collection of provider capability snapshots."""

    capabilities: tuple[_OCRProviderCapabilities, ...]

    def __post_init__(self) -> None:
        self.validate()

    @property
    def provider_ids(self) -> tuple[str, ...]:
        return tuple(item.provider_id for item in self.capabilities)

    def validate(self) -> None:
        if not isinstance(self.capabilities, tuple):
            raise InvalidOCRProviderSelectionContextError(
                "capabilities must be an immutable tuple."
            )
        if not self.capabilities:
            raise InvalidOCRProviderSelectionContextError(
                "capabilities must not be empty."
            )
        for capability in self.capabilities:
            if not isinstance(capability, _OCRProviderCapabilities):
                raise InvalidOCRProviderSelectionContextError(
                    "capabilities must contain OCRProviderCapabilities."
                )
            capability.validate()
        provider_ids = self.provider_ids
        if len(set(provider_ids)) != len(provider_ids):
            raise InvalidOCRProviderSelectionContextError(
                "capabilities must not contain duplicate provider IDs."
            )
        if provider_ids != tuple(sorted(provider_ids)):
            raise InvalidOCRProviderSelectionContextError(
                "capabilities must use lexical provider-ID order."
            )


@dataclass(frozen=True, slots=True)
class OCRProviderSelectionCriteria:
    """Exact capability requirements for a pure selection pass.

    ``allowed_provider_ids=None`` means no provider-ID restriction.  A supplied
    allowlist is itself canonical and cannot name an unregistered provider;
    registry membership is checked by :func:`select_ocr_providers`.
    """

    required_image_role: _ImageRole
    required_media_type: str
    required_fields: tuple[str, ...]
    availability_policy: OCRProviderAvailabilityPolicy
    allowed_provider_ids: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.required_image_role, _ImageRole):
            raise InvalidOCRProviderSelectionContextError(
                "required_image_role must be an ImageRole."
            )
        if (
            not isinstance(self.required_media_type, str)
            or _MEDIA_TYPE.fullmatch(self.required_media_type) is None
        ):
            raise InvalidOCRProviderSelectionContextError(
                "required_media_type must be a normalized MIME type."
            )
        _validate_required_fields(self.required_fields)
        if not isinstance(
            self.availability_policy,
            OCRProviderAvailabilityPolicy,
        ):
            raise InvalidOCRProviderSelectionContextError(
                "availability_policy must be an OCRProviderAvailabilityPolicy."
            )
        if self.allowed_provider_ids is not None:
            _validate_provider_ids(
                self.allowed_provider_ids,
                "allowed_provider_ids",
                allow_empty=False,
            )


@dataclass(frozen=True, slots=True)
class OCRProviderSelectionFinding:
    """One deterministic selection conclusion for one registry entry."""

    capability: _OCRProviderCapabilities
    status: OCRProviderSelectionStatus
    reason: OCRProviderSelectionReason

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.capability, _OCRProviderCapabilities):
            raise InvalidOCRProviderSelectionContextError(
                "capability must be OCRProviderCapabilities."
            )
        self.capability.validate()
        if not isinstance(self.status, OCRProviderSelectionStatus):
            raise InvalidOCRProviderSelectionContextError(
                "status must be an OCRProviderSelectionStatus."
            )
        if not isinstance(self.reason, OCRProviderSelectionReason):
            raise InvalidOCRProviderSelectionContextError(
                "reason must be an OCRProviderSelectionReason."
            )
        if (
            self.status is OCRProviderSelectionStatus.ELIGIBLE
        ) != (self.reason is OCRProviderSelectionReason.MATCHED):
            raise InvalidOCRProviderSelectionContextError(
                "ELIGIBLE must pair exactly with MATCHED."
            )


@dataclass(frozen=True, slots=True)
class OCRProviderSelectionResult:
    """Complete selection findings and eligible snapshots in registry order."""

    registry: OCRProviderRegistry
    criteria: OCRProviderSelectionCriteria
    findings: tuple[OCRProviderSelectionFinding, ...]
    eligible_providers: tuple[_OCRProviderCapabilities, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.registry, OCRProviderRegistry):
            raise InvalidOCRProviderSelectionContextError(
                "registry must be an OCRProviderRegistry."
            )
        self.registry.validate()
        if not isinstance(self.criteria, OCRProviderSelectionCriteria):
            raise InvalidOCRProviderSelectionContextError(
                "criteria must be OCRProviderSelectionCriteria."
            )
        self.criteria.validate()
        if self.criteria.allowed_provider_ids is not None:
            unknown_ids = set(self.criteria.allowed_provider_ids).difference(
                self.registry.provider_ids
            )
            if unknown_ids:
                raise InvalidOCRProviderSelectionContextError(
                    "criteria cannot reference an unregistered provider."
                )
        if not isinstance(self.findings, tuple):
            raise InvalidOCRProviderSelectionContextError(
                "findings must be an immutable tuple."
            )
        if len(self.findings) != len(self.registry.capabilities):
            raise InvalidOCRProviderSelectionContextError(
                "findings must cover every registry capability exactly once."
            )
        for finding, capability in zip(
            self.findings,
            self.registry.capabilities,
            strict=True,
        ):
            if not isinstance(finding, OCRProviderSelectionFinding):
                raise InvalidOCRProviderSelectionContextError(
                    "findings must contain OCRProviderSelectionFinding values."
                )
            finding.validate()
            if finding.capability is not capability:
                raise InvalidOCRProviderSelectionContextError(
                    "findings must preserve registry capability identity."
                )
            expected_reason = _selection_reason(capability, self.criteria)
            if finding.reason is not expected_reason:
                raise InvalidOCRProviderSelectionContextError(
                    "findings must match the supplied registry and criteria."
                )
        if not isinstance(self.eligible_providers, tuple):
            raise InvalidOCRProviderSelectionContextError(
                "eligible_providers must be an immutable tuple."
            )
        expected = tuple(
            finding.capability
            for finding in self.findings
            if finding.status is OCRProviderSelectionStatus.ELIGIBLE
        )
        if len(self.eligible_providers) != len(expected) or any(
            actual is not wanted
            for actual, wanted in zip(
                self.eligible_providers,
                expected,
                strict=True,
            )
        ):
            raise InvalidOCRProviderSelectionContextError(
                "eligible_providers must exactly match eligible findings."
            )


def require_registered_ocr_provider(
    registry: OCRProviderRegistry,
    provider_id: str,
) -> _OCRProviderCapabilities:
    """Return the exact registered snapshot or raise a typed membership error."""

    _require_registry(registry)
    _validate_provider_id(provider_id)
    for capability in registry.capabilities:
        if capability.provider_id == provider_id:
            return capability
    raise UnknownOCRProviderSelectionReferenceError(provider_id)


def select_ocr_providers(
    registry: OCRProviderRegistry,
    criteria: OCRProviderSelectionCriteria,
) -> OCRProviderSelectionResult:
    """Evaluate every registered capability without invoking a provider."""

    _require_registry(registry)
    _require_criteria(criteria)
    if criteria.allowed_provider_ids is not None:
        for provider_id in criteria.allowed_provider_ids:
            require_registered_ocr_provider(registry, provider_id)

    findings = tuple(
        _select_capability(capability, criteria)
        for capability in registry.capabilities
    )
    eligible = tuple(
        finding.capability
        for finding in findings
        if finding.status is OCRProviderSelectionStatus.ELIGIBLE
    )
    return OCRProviderSelectionResult(
        registry=registry,
        criteria=criteria,
        findings=findings,
        eligible_providers=eligible,
    )


def require_single_selected_ocr_provider(
    result: OCRProviderSelectionResult,
) -> _OCRProviderCapabilities:
    """Require exactly one eligible capability from a validated result."""

    if not isinstance(result, OCRProviderSelectionResult):
        raise InvalidOCRProviderSelectionContextError(
            "result must be an OCRProviderSelectionResult."
        )
    result.validate()
    if not result.eligible_providers:
        raise NoEligibleOCRProviderError()
    if len(result.eligible_providers) > 1:
        raise AmbiguousOCRProviderSelectionError(
            tuple(item.provider_id for item in result.eligible_providers)
        )
    return result.eligible_providers[0]


def _select_capability(
    capability: _OCRProviderCapabilities,
    criteria: OCRProviderSelectionCriteria,
) -> OCRProviderSelectionFinding:
    reason = _selection_reason(capability, criteria)
    status = (
        OCRProviderSelectionStatus.ELIGIBLE
        if reason is OCRProviderSelectionReason.MATCHED
        else OCRProviderSelectionStatus.EXCLUDED
    )
    return OCRProviderSelectionFinding(
        capability=capability,
        status=status,
        reason=reason,
    )


def _selection_reason(
    capability: _OCRProviderCapabilities,
    criteria: OCRProviderSelectionCriteria,
) -> OCRProviderSelectionReason:
    if (
        criteria.allowed_provider_ids is not None
        and capability.provider_id not in criteria.allowed_provider_ids
    ):
        return OCRProviderSelectionReason.PROVIDER_NOT_ALLOWED
    if capability.availability is _OCRProviderAvailability.UNAVAILABLE:
        return OCRProviderSelectionReason.PROVIDER_UNAVAILABLE
    if (
        capability.availability is _OCRProviderAvailability.UNKNOWN
        and criteria.availability_policy
        is OCRProviderAvailabilityPolicy.REQUIRE_AVAILABLE
    ):
        return OCRProviderSelectionReason.PROVIDER_AVAILABILITY_UNKNOWN
    if criteria.required_image_role not in capability.supported_image_roles:
        return OCRProviderSelectionReason.IMAGE_ROLE_UNSUPPORTED
    if criteria.required_media_type not in capability.supported_media_types:
        return OCRProviderSelectionReason.MEDIA_TYPE_UNSUPPORTED
    if criteria.required_fields:
        if (
            capability.field_support_mode
            is _OCRProviderFieldSupportMode.UNKNOWN
        ):
            return OCRProviderSelectionReason.FIELD_SUPPORT_UNKNOWN
        if not set(criteria.required_fields).issubset(
            capability.supported_fields
        ):
            return OCRProviderSelectionReason.REQUIRED_FIELDS_UNSUPPORTED
    return OCRProviderSelectionReason.MATCHED


def _require_registry(value: object) -> OCRProviderRegistry:
    if not isinstance(value, OCRProviderRegistry):
        raise InvalidOCRProviderSelectionContextError(
            "registry must be an OCRProviderRegistry."
        )
    value.validate()
    return value


def _require_criteria(value: object) -> OCRProviderSelectionCriteria:
    if not isinstance(value, OCRProviderSelectionCriteria):
        raise InvalidOCRProviderSelectionContextError(
            "criteria must be OCRProviderSelectionCriteria."
        )
    value.validate()
    return value


def _validate_provider_id(value: object) -> str:
    if not isinstance(value, str) or _PROVIDER_ID.fullmatch(value) is None:
        raise InvalidOCRProviderSelectionContextError(
            "provider_id must match the Unit 1A provider-ID contract."
        )
    return value


def _validate_provider_ids(
    value: object,
    name: str,
    *,
    allow_empty: bool,
) -> None:
    if not isinstance(value, tuple):
        raise InvalidOCRProviderSelectionContextError(
            f"{name} must be an immutable tuple."
        )
    if not allow_empty and not value:
        raise InvalidOCRProviderSelectionContextError(
            f"{name} must not be empty."
        )
    for provider_id in value:
        _validate_provider_id(provider_id)
    if len(set(value)) != len(value):
        raise InvalidOCRProviderSelectionContextError(
            f"{name} must not contain duplicates."
        )
    if value != tuple(sorted(value)):
        raise InvalidOCRProviderSelectionContextError(
            f"{name} must use lexical provider-ID order."
        )


def _validate_required_fields(value: object) -> None:
    if not isinstance(value, tuple):
        raise InvalidOCRProviderSelectionContextError(
            "required_fields must be an immutable tuple."
        )
    if any(
        not isinstance(field, str) or field not in _ALLOWED_OCR_FIELDS
        for field in value
    ):
        raise InvalidOCRProviderSelectionContextError(
            "required_fields contains an unknown OCR field."
        )
    if len(set(value)) != len(value):
        raise InvalidOCRProviderSelectionContextError(
            "required_fields must not contain duplicates."
        )
    if value != tuple(sorted(value)):
        raise InvalidOCRProviderSelectionContextError(
            "required_fields must use lexical order."
        )
