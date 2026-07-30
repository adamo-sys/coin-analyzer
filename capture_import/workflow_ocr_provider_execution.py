"""Deterministic multi-provider OCR execution over Unit 1B selections.

The infrastructure here is transient and synchronous.  It invokes only
caller-bound providers, preserves every provider outcome, and performs no
selection, retry, fallback, discovery, persistence, or confidence policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .enums import ImageRole as _ImageRole
from .workflow_ocr_models import (
    OCRFieldCandidate as _OCRFieldCandidate,
    OCRMetadataReport as _OCRMetadataReport,
)
from .workflow_ocr_provider_contracts import (
    OCRProviderCapabilities as _OCRProviderCapabilities,
    OCRProviderCleanupError as _OCRProviderCleanupError,
    OCRProviderError as _OCRProviderError,
    OCRProviderExecutionError as _Unit1AExecutionError,
    OCRProviderInputError as _OCRProviderInputError,
    OCRProviderOutputError as _OCRProviderOutputError,
    OCRProviderUnavailableError as _OCRProviderUnavailableError,
    OCRProviderFieldSupportMode as _OCRProviderFieldSupportMode,
)
from .workflow_ocr_provider_selection import (
    OCRProviderSelectionResult as _OCRProviderSelectionResult,
)
from .workflow_ocr_stage import OCRMetadataProvider as _OCRMetadataProvider


__all__ = [
    "OCRProviderExecutionContractError",
    "InvalidOCRProviderExecutionContextError",
    "OCRProviderBatchError",
    "NoSelectedOCRProvidersError",
    "MissingOCRProviderBindingError",
    "MismatchedOCRProviderBindingError",
    "OCRProviderExecutionStatus",
    "OCRProviderFailureCategory",
    "OCRProviderExecutionBinding",
    "OCRProviderExecutionBindings",
    "OCRProviderExecutionRequest",
    "OCRProviderExecutionOutcome",
    "OCRProviderExecutionBatch",
    "execute_selected_ocr_providers",
]


_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")
_DIAGNOSTIC_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_MEDIA_TYPE = re.compile(
    r"^[a-z][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$"
)
_INVALID_OUTPUT_CODE = "INVALID_PROVIDER_OUTPUT"
_MISMATCHED_ERROR_ID_CODE = "MISMATCHED_PROVIDER_ERROR_ID"
_REPORTED_UNAVAILABLE_CODE = "PROVIDER_REPORTED_UNAVAILABLE"
_UNEXPECTED_FAILURE_CODE = "UNEXPECTED_PROVIDER_FAILURE"


class OCRProviderExecutionContractError(ValueError):
    """A Unit 1C execution value contract is malformed."""


class InvalidOCRProviderExecutionContextError(
    OCRProviderExecutionContractError
):
    """Binding, request, outcome, or batch invariants were violated."""


class OCRProviderBatchError(Exception):
    """A valid selection cannot be executed with the supplied bindings."""

    __slots__ = ("_locked",)

    def __init__(self, message: str) -> None:
        if type(self) is OCRProviderBatchError:
            raise TypeError("OCRProviderBatchError cannot be constructed directly.")
        object.__setattr__(self, "_locked", False)
        super().__init__(message)
        object.__setattr__(self, "_locked", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_locked", False):
            raise AttributeError("OCR provider batch errors are immutable.")
        object.__setattr__(self, name, value)


class NoSelectedOCRProvidersError(OCRProviderBatchError):
    """Execution was requested for a selection with no eligible provider."""

    def __init__(self) -> None:
        super().__init__("OCR provider execution requires an eligible provider.")


class MissingOCRProviderBindingError(OCRProviderBatchError):
    """No execution binding exists for an eligible provider."""

    __slots__ = ("_provider_id",)

    def __init__(self, provider_id: str) -> None:
        value = _validate_provider_id(provider_id)
        object.__setattr__(self, "_provider_id", value)
        super().__init__(f"OCR provider {value!r} has no execution binding.")

    @property
    def provider_id(self) -> str:
        return self._provider_id


class MismatchedOCRProviderBindingError(OCRProviderBatchError):
    """A binding does not retain the selected capability object."""

    __slots__ = ("_provider_id",)

    def __init__(self, provider_id: str) -> None:
        value = _validate_provider_id(provider_id)
        object.__setattr__(self, "_provider_id", value)
        super().__init__(
            f"OCR provider {value!r} binding does not match the selection."
        )

    @property
    def provider_id(self) -> str:
        return self._provider_id


class OCRProviderExecutionStatus(str, Enum):
    """Whether one selected provider produced a valid report."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class OCRProviderFailureCategory(str, Enum):
    """Sanitized category for one provider-specific failure."""

    UNAVAILABLE = "UNAVAILABLE"
    INPUT = "INPUT"
    EXECUTION = "EXECUTION"
    OUTPUT = "OUTPUT"
    CLEANUP = "CLEANUP"
    UNEXPECTED = "UNEXPECTED"


@dataclass(frozen=True, slots=True, eq=False)
class OCRProviderExecutionBinding:
    """Transient exact pairing of capabilities and an analyze-compatible provider."""

    capabilities: _OCRProviderCapabilities
    provider: _OCRMetadataProvider

    def __post_init__(self) -> None:
        self.validate()

    @property
    def provider_id(self) -> str:
        return self.capabilities.provider_id

    def validate(self) -> None:
        _validate_capabilities(self.capabilities)
        if not isinstance(self.provider, _OCRMetadataProvider):
            raise InvalidOCRProviderExecutionContextError(
                "provider must satisfy OCRMetadataProvider."
            )
        if _read_provider_id(self.provider) != self.capabilities.provider_id:
            raise InvalidOCRProviderExecutionContextError(
                "provider ID must exactly match binding capabilities."
            )


@dataclass(frozen=True, slots=True)
class OCRProviderExecutionBindings:
    """Immutable canonical registry of execution bindings."""

    bindings: tuple[OCRProviderExecutionBinding, ...]

    def __post_init__(self) -> None:
        self.validate()

    @property
    def provider_ids(self) -> tuple[str, ...]:
        return tuple(item.provider_id for item in self.bindings)

    def validate(self) -> None:
        if not isinstance(self.bindings, tuple) or not self.bindings:
            raise InvalidOCRProviderExecutionContextError(
                "bindings must be a nonempty immutable tuple."
            )
        for binding in self.bindings:
            if not isinstance(binding, OCRProviderExecutionBinding):
                raise InvalidOCRProviderExecutionContextError(
                    "bindings must contain OCRProviderExecutionBinding values."
                )
            binding.validate()
        provider_ids = self.provider_ids
        if len(set(provider_ids)) != len(provider_ids):
            raise InvalidOCRProviderExecutionContextError(
                "bindings must not contain duplicate provider IDs."
            )
        if provider_ids != tuple(sorted(provider_ids)):
            raise InvalidOCRProviderExecutionContextError(
                "bindings must use lexical provider-ID order."
            )


@dataclass(frozen=True, slots=True)
class OCRProviderExecutionRequest:
    """Exact immutable input passed unchanged to each selected provider."""

    source_coin_id: str
    image_role: _ImageRole
    artifact_key: str
    media_type: str
    image_bytes: bytes

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _validate_text(
            self.source_coin_id,
            "source_coin_id",
            maximum=16_384,
        )
        if not isinstance(self.image_role, _ImageRole):
            raise InvalidOCRProviderExecutionContextError(
                "image_role must be an ImageRole."
            )
        _validate_text(self.artifact_key, "artifact_key", maximum=255)
        if "/" in self.artifact_key or "\\" in self.artifact_key:
            raise InvalidOCRProviderExecutionContextError(
                "artifact_key must be an identifier, not a path."
            )
        if (
            not isinstance(self.media_type, str)
            or _MEDIA_TYPE.fullmatch(self.media_type) is None
        ):
            raise InvalidOCRProviderExecutionContextError(
                "media_type must be a normalized MIME type."
            )
        if not isinstance(self.image_bytes, bytes) or not self.image_bytes:
            raise InvalidOCRProviderExecutionContextError(
                "image_bytes must be nonempty immutable bytes."
            )


@dataclass(frozen=True, slots=True)
class OCRProviderExecutionOutcome:
    """One immutable success or sanitized provider-specific failure."""

    capabilities: _OCRProviderCapabilities
    status: OCRProviderExecutionStatus
    report: _OCRMetadataReport | None
    failure_category: OCRProviderFailureCategory | None
    diagnostic_code: str | None

    def __post_init__(self) -> None:
        self.validate()

    @property
    def provider_id(self) -> str:
        return self.capabilities.provider_id

    def validate(self) -> None:
        _validate_capabilities(self.capabilities)
        if not isinstance(self.status, OCRProviderExecutionStatus):
            raise InvalidOCRProviderExecutionContextError(
                "status must be an OCRProviderExecutionStatus."
            )
        if self.status is OCRProviderExecutionStatus.SUCCEEDED:
            if (
                self.report is None
                or self.failure_category is not None
                or self.diagnostic_code is not None
            ):
                raise InvalidOCRProviderExecutionContextError(
                    "SUCCEEDED requires only a valid report."
                )
            _validate_success_report(
                self.report,
                self.capabilities,
                request=None,
            )
            return
        if (
            self.report is not None
            or not isinstance(
                self.failure_category,
                OCRProviderFailureCategory,
            )
        ):
            raise InvalidOCRProviderExecutionContextError(
                "FAILED requires failure category and no report."
            )
        _validate_diagnostic_code(self.diagnostic_code)


@dataclass(frozen=True, slots=True)
class OCRProviderExecutionBatch:
    """Complete ordered outcomes for one exact Unit 1B selection."""

    selection: _OCRProviderSelectionResult
    request: OCRProviderExecutionRequest
    outcomes: tuple[OCRProviderExecutionOutcome, ...]

    def __post_init__(self) -> None:
        self.validate()

    @property
    def successful_outcomes(self) -> tuple[OCRProviderExecutionOutcome, ...]:
        return tuple(
            item
            for item in self.outcomes
            if item.status is OCRProviderExecutionStatus.SUCCEEDED
        )

    @property
    def failed_outcomes(self) -> tuple[OCRProviderExecutionOutcome, ...]:
        return tuple(
            item
            for item in self.outcomes
            if item.status is OCRProviderExecutionStatus.FAILED
        )

    @property
    def provider_ids(self) -> tuple[str, ...]:
        return tuple(item.provider_id for item in self.outcomes)

    def validate(self) -> None:
        if not isinstance(self.selection, _OCRProviderSelectionResult):
            raise InvalidOCRProviderExecutionContextError(
                "selection must be an OCRProviderSelectionResult."
            )
        self.selection.validate()
        if not self.selection.eligible_providers:
            raise InvalidOCRProviderExecutionContextError(
                "execution batches require an eligible provider."
            )
        if not isinstance(self.request, OCRProviderExecutionRequest):
            raise InvalidOCRProviderExecutionContextError(
                "request must be an OCRProviderExecutionRequest."
            )
        self.request.validate()
        _validate_request_matches_selection(self.request, self.selection)
        if not isinstance(self.outcomes, tuple):
            raise InvalidOCRProviderExecutionContextError(
                "outcomes must be an immutable tuple."
            )
        if len(self.outcomes) != len(self.selection.eligible_providers):
            raise InvalidOCRProviderExecutionContextError(
                "outcomes must cover every eligible provider exactly once."
            )
        for outcome, capabilities in zip(
            self.outcomes,
            self.selection.eligible_providers,
            strict=True,
        ):
            if not isinstance(outcome, OCRProviderExecutionOutcome):
                raise InvalidOCRProviderExecutionContextError(
                    "outcomes must contain OCRProviderExecutionOutcome values."
                )
            outcome.validate()
            if outcome.capabilities is not capabilities:
                raise InvalidOCRProviderExecutionContextError(
                    "outcomes must preserve selected capability identity."
                )
            if outcome.status is OCRProviderExecutionStatus.SUCCEEDED:
                _validate_success_report(
                    outcome.report,
                    capabilities,
                    request=self.request,
                )


def execute_selected_ocr_providers(
    selection: _OCRProviderSelectionResult,
    bindings: OCRProviderExecutionBindings,
    request: OCRProviderExecutionRequest,
) -> OCRProviderExecutionBatch:
    """Invoke every eligible provider once in exact Unit 1B order."""

    resolved = _validate_execution_context(selection, bindings, request)
    outcomes = tuple(
        _execute_one(binding, request)
        for binding in resolved
    )
    return OCRProviderExecutionBatch(
        selection=selection,
        request=request,
        outcomes=outcomes,
    )


def _validate_execution_context(
    selection: object,
    bindings: object,
    request: object,
) -> tuple[OCRProviderExecutionBinding, ...]:
    if not isinstance(selection, _OCRProviderSelectionResult):
        raise InvalidOCRProviderExecutionContextError(
            "selection must be an OCRProviderSelectionResult."
        )
    selection.validate()
    if not selection.eligible_providers:
        raise NoSelectedOCRProvidersError()
    if not isinstance(bindings, OCRProviderExecutionBindings):
        raise InvalidOCRProviderExecutionContextError(
            "bindings must be OCRProviderExecutionBindings."
        )
    bindings.validate()
    if not isinstance(request, OCRProviderExecutionRequest):
        raise InvalidOCRProviderExecutionContextError(
            "request must be an OCRProviderExecutionRequest."
        )
    request.validate()
    _validate_request_matches_selection(request, selection)

    by_id = {item.provider_id: item for item in bindings.bindings}
    resolved: list[OCRProviderExecutionBinding] = []
    for capabilities in selection.eligible_providers:
        binding = by_id.get(capabilities.provider_id)
        if binding is None:
            raise MissingOCRProviderBindingError(capabilities.provider_id)
        if binding.capabilities is not capabilities:
            raise MismatchedOCRProviderBindingError(capabilities.provider_id)
        binding.validate()
        resolved.append(binding)
    return tuple(resolved)


def _execute_one(
    binding: OCRProviderExecutionBinding,
    request: OCRProviderExecutionRequest,
) -> OCRProviderExecutionOutcome:
    try:
        report = binding.provider.analyze(
            source_coin_id=request.source_coin_id,
            image_role=request.image_role.value,
            artifact_key=request.artifact_key,
            image_bytes=request.image_bytes,
        )
    except _OCRProviderError as error:
        return _outcome_from_provider_error(binding.capabilities, error)
    except Exception:
        return _failed_outcome(
            binding.capabilities,
            OCRProviderFailureCategory.UNEXPECTED,
            _UNEXPECTED_FAILURE_CODE,
        )

    if not isinstance(report, _OCRMetadataReport):
        return _failed_outcome(
            binding.capabilities,
            OCRProviderFailureCategory.OUTPUT,
            _INVALID_OUTPUT_CODE,
        )
    try:
        report.validate()
    except Exception:
        return _failed_outcome(
            binding.capabilities,
            OCRProviderFailureCategory.OUTPUT,
            _INVALID_OUTPUT_CODE,
        )
    if not report.provider_available:
        return _failed_outcome(
            binding.capabilities,
            OCRProviderFailureCategory.UNAVAILABLE,
            _REPORTED_UNAVAILABLE_CODE,
        )
    try:
        _validate_success_report(
            report,
            binding.capabilities,
            request=request,
        )
    except OCRProviderExecutionContractError:
        return _failed_outcome(
            binding.capabilities,
            OCRProviderFailureCategory.OUTPUT,
            _INVALID_OUTPUT_CODE,
        )
    return OCRProviderExecutionOutcome(
        capabilities=binding.capabilities,
        status=OCRProviderExecutionStatus.SUCCEEDED,
        report=report,
        failure_category=None,
        diagnostic_code=None,
    )


def _outcome_from_provider_error(
    capabilities: _OCRProviderCapabilities,
    error: _OCRProviderError,
) -> OCRProviderExecutionOutcome:
    if error.provider_id != capabilities.provider_id:
        return _failed_outcome(
            capabilities,
            OCRProviderFailureCategory.OUTPUT,
            _MISMATCHED_ERROR_ID_CODE,
        )
    categories = {
        _OCRProviderUnavailableError: OCRProviderFailureCategory.UNAVAILABLE,
        _OCRProviderInputError: OCRProviderFailureCategory.INPUT,
        _Unit1AExecutionError: OCRProviderFailureCategory.EXECUTION,
        _OCRProviderOutputError: OCRProviderFailureCategory.OUTPUT,
        _OCRProviderCleanupError: OCRProviderFailureCategory.CLEANUP,
    }
    category = next(
        (
            value
            for error_type, value in categories.items()
            if isinstance(error, error_type)
        ),
        OCRProviderFailureCategory.UNEXPECTED,
    )
    code = (
        error.diagnostic_code
        if category is not OCRProviderFailureCategory.UNEXPECTED
        else _UNEXPECTED_FAILURE_CODE
    )
    return _failed_outcome(capabilities, category, code)


def _failed_outcome(
    capabilities: _OCRProviderCapabilities,
    category: OCRProviderFailureCategory,
    diagnostic_code: str,
) -> OCRProviderExecutionOutcome:
    return OCRProviderExecutionOutcome(
        capabilities=capabilities,
        status=OCRProviderExecutionStatus.FAILED,
        report=None,
        failure_category=category,
        diagnostic_code=diagnostic_code,
    )


def _validate_request_matches_selection(
    request: OCRProviderExecutionRequest,
    selection: _OCRProviderSelectionResult,
) -> None:
    if request.image_role is not selection.criteria.required_image_role:
        raise InvalidOCRProviderExecutionContextError(
            "request image role must match selection criteria."
        )
    if request.media_type != selection.criteria.required_media_type:
        raise InvalidOCRProviderExecutionContextError(
            "request media type must match selection criteria."
        )


def _validate_success_report(
    report: object,
    capabilities: _OCRProviderCapabilities,
    *,
    request: OCRProviderExecutionRequest | None,
) -> None:
    if not isinstance(report, _OCRMetadataReport):
        raise InvalidOCRProviderExecutionContextError(
            "successful outcomes require OCRMetadataReport."
        )
    try:
        report.validate()
    except Exception as error:
        raise InvalidOCRProviderExecutionContextError(
            "provider report violates OCRMetadataReport."
        ) from error
    if not report.provider_available:
        raise InvalidOCRProviderExecutionContextError(
            "successful outcomes require an available provider report."
        )

    candidate_values: dict[str, list[str]] = {}
    seen_candidate_values: set[tuple[str, str]] = set()
    for observation in report.observations:
        _validate_report_identity(
            observation.provider_id,
            observation.source_coin_id,
            observation.image_role,
            observation.artifact_key,
            capabilities,
            request,
        )
    for candidate in report.candidates:
        _validate_report_identity(
            candidate.provider_id,
            candidate.source_coin_id,
            candidate.image_role,
            candidate.artifact_key,
            capabilities,
            request,
        )
        _validate_declared_field(candidate.field_name, capabilities)
        key = (candidate.field_name, candidate.normalized_value)
        if key in seen_candidate_values:
            raise InvalidOCRProviderExecutionContextError(
                "provider report contains duplicate field values."
            )
        seen_candidate_values.add(key)
        candidate_values.setdefault(candidate.field_name, []).append(
            candidate.normalized_value
        )

    conflict_fields: set[str] = set()
    for conflict in report.conflicts:
        _validate_declared_field(conflict.field_name, capabilities)
        if request is not None and conflict.source_coin_id != request.source_coin_id:
            raise InvalidOCRProviderExecutionContextError(
                "provider conflict source does not match the request."
            )
        expected = tuple(candidate_values.get(conflict.field_name, ()))
        if conflict.candidate_values != expected or len(expected) < 2:
            raise InvalidOCRProviderExecutionContextError(
                "provider conflict must exactly describe emitted candidates."
            )
        conflict_fields.add(conflict.field_name)
    expected_conflicts = {
        field_name
        for field_name, values in candidate_values.items()
        if len(values) > 1
    }
    if conflict_fields != expected_conflicts:
        raise InvalidOCRProviderExecutionContextError(
            "provider field ambiguity must be represented exactly."
        )


def _validate_report_identity(
    provider_id: str,
    source_coin_id: str,
    image_role: str,
    artifact_key: str,
    capabilities: _OCRProviderCapabilities,
    request: OCRProviderExecutionRequest | None,
) -> None:
    if provider_id != capabilities.provider_id:
        raise InvalidOCRProviderExecutionContextError(
            "provider report identity does not match capabilities."
        )
    if request is not None and (
        source_coin_id != request.source_coin_id
        or image_role != request.image_role.value
        or artifact_key != request.artifact_key
    ):
        raise InvalidOCRProviderExecutionContextError(
            "provider report context does not match the request."
        )


def _validate_declared_field(
    field_name: str,
    capabilities: _OCRProviderCapabilities,
) -> None:
    if (
        capabilities.field_support_mode
        is _OCRProviderFieldSupportMode.DECLARED
        and field_name not in capabilities.supported_fields
    ):
        raise InvalidOCRProviderExecutionContextError(
            "provider report emitted an undeclared field."
        )


def _validate_capabilities(value: object) -> _OCRProviderCapabilities:
    if not isinstance(value, _OCRProviderCapabilities):
        raise InvalidOCRProviderExecutionContextError(
            "capabilities must be OCRProviderCapabilities."
        )
    try:
        value.validate()
    except Exception as error:
        raise InvalidOCRProviderExecutionContextError(
            "capabilities violate OCRProviderCapabilities."
        ) from error
    return value


def _read_provider_id(provider: _OCRMetadataProvider) -> str:
    try:
        provider_id = provider.provider_id
    except Exception as error:
        raise InvalidOCRProviderExecutionContextError(
            "provider_id could not be read."
        ) from error
    return _validate_provider_id(provider_id)


def _validate_provider_id(value: object) -> str:
    if not isinstance(value, str) or _PROVIDER_ID.fullmatch(value) is None:
        raise InvalidOCRProviderExecutionContextError(
            "provider_id violates the Unit 1A provider-ID contract."
        )
    return value


def _validate_diagnostic_code(value: object) -> str:
    if not isinstance(value, str) or _DIAGNOSTIC_CODE.fullmatch(value) is None:
        raise InvalidOCRProviderExecutionContextError(
            "diagnostic_code violates the Unit 1A diagnostic-code contract."
        )
    return value


def _validate_text(value: object, name: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise InvalidOCRProviderExecutionContextError(
            f"{name} must be nonempty bounded text."
        )
    return value
