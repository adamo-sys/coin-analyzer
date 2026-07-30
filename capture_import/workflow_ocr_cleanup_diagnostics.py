"""Transient cleanup diagnostics for completed OCR provider executions.

The contracts in this module retain nonfatal cleanup evidence beside an
unchanged Unit 1C execution batch.  They do not execute cleanup, retry work,
alter provider outcomes, persist diagnostics, or retain filesystem paths and
exception text.  Fatal cleanup remains represented by Unit 1C's
``FAILED/CLEANUP`` outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .workflow_ocr_provider_contracts import (
    OCRProviderCapabilities as _OCRProviderCapabilities,
)
from .workflow_ocr_provider_execution import (
    OCRProviderExecutionBatch as _OCRProviderExecutionBatch,
    OCRProviderExecutionStatus as _OCRProviderExecutionStatus,
)


__all__ = [
    "OCRProviderCleanupDiagnosticContractError",
    "InvalidOCRProviderCleanupDiagnosticContextError",
    "OCRProviderCleanupDiagnosticSeverity",
    "OCRProviderCleanupDiagnostic",
    "OCRProviderExecutionWithCleanup",
]


_DIAGNOSTIC_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_MAX_ARTIFACT_KEY_CHARS = 255


class OCRProviderCleanupDiagnosticContractError(ValueError):
    """A cleanup diagnostic value violates the Unit 1E contract."""


class InvalidOCRProviderCleanupDiagnosticContextError(
    OCRProviderCleanupDiagnosticContractError
):
    """Cleanup diagnostic identity or reconstruction is invalid."""


class OCRProviderCleanupDiagnosticSeverity(str, Enum):
    """Provider-neutral severity of one artifact-cleanup diagnostic."""

    WARNING = "WARNING"
    FAILURE = "FAILURE"


@dataclass(frozen=True, slots=True, eq=False)
class OCRProviderCleanupDiagnostic:
    """Sanitized cleanup evidence for one exact provider execution.

    ``artifact_key`` may identify the bounded request artifact.  It is never a
    temporary filesystem path.  ``FAILURE`` is representable as a standalone
    diagnostic value, while fatal cleanup attached to an execution remains
    exclusively represented by Unit 1C's failed outcome.
    """

    provider: _OCRProviderCapabilities
    severity: OCRProviderCleanupDiagnosticSeverity
    diagnostic_code: str
    artifact_key: str | None = None

    def __post_init__(self) -> None:
        self.validate()

    @property
    def provider_id(self) -> str:
        return self.provider.provider_id

    def validate(self) -> None:
        _validate_provider(self.provider)
        if not isinstance(
            self.severity,
            OCRProviderCleanupDiagnosticSeverity,
        ):
            raise InvalidOCRProviderCleanupDiagnosticContextError(
                "severity must be an OCRProviderCleanupDiagnosticSeverity."
            )
        if (
            not isinstance(self.diagnostic_code, str)
            or _DIAGNOSTIC_CODE.fullmatch(self.diagnostic_code) is None
        ):
            raise InvalidOCRProviderCleanupDiagnosticContextError(
                "diagnostic_code must match [A-Z][A-Z0-9_]{0,63}."
            )
        if self.artifact_key is not None:
            _validate_artifact_key(self.artifact_key)


@dataclass(frozen=True, slots=True, eq=False)
class OCRProviderExecutionWithCleanup:
    """One exact Unit 1C batch plus ordered nonfatal cleanup diagnostics."""

    batch: _OCRProviderExecutionBatch
    diagnostics: tuple[OCRProviderCleanupDiagnostic, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.batch, _OCRProviderExecutionBatch):
            raise InvalidOCRProviderCleanupDiagnosticContextError(
                "batch must be an OCRProviderExecutionBatch."
            )
        try:
            self.batch.validate()
        except Exception as error:
            raise InvalidOCRProviderCleanupDiagnosticContextError(
                "batch must satisfy the Unit 1C execution contract."
            ) from error
        if not isinstance(self.diagnostics, tuple):
            raise InvalidOCRProviderCleanupDiagnosticContextError(
                "diagnostics must be an immutable tuple."
            )

        positions = {
            outcome.provider_id: index
            for index, outcome in enumerate(self.batch.outcomes)
        }
        previous_position = -1
        seen_provider_ids: set[str] = set()

        for diagnostic in self.diagnostics:
            if not isinstance(diagnostic, OCRProviderCleanupDiagnostic):
                raise InvalidOCRProviderCleanupDiagnosticContextError(
                    "diagnostics must contain "
                    "OCRProviderCleanupDiagnostic values."
                )
            diagnostic.validate()
            provider_id = diagnostic.provider_id
            position = positions.get(provider_id)
            if position is None:
                raise InvalidOCRProviderCleanupDiagnosticContextError(
                    "diagnostic provider must belong to the execution batch."
                )
            outcome = self.batch.outcomes[position]
            if diagnostic.provider is not outcome.capabilities:
                raise InvalidOCRProviderCleanupDiagnosticContextError(
                    "diagnostics must preserve batch capability identity."
                )
            if provider_id in seen_provider_ids:
                raise InvalidOCRProviderCleanupDiagnosticContextError(
                    "at most one cleanup diagnostic is allowed per provider."
                )
            if position <= previous_position:
                raise InvalidOCRProviderCleanupDiagnosticContextError(
                    "diagnostics must follow execution-batch provider order."
                )
            if (
                diagnostic.severity
                is not OCRProviderCleanupDiagnosticSeverity.WARNING
            ):
                raise InvalidOCRProviderCleanupDiagnosticContextError(
                    "fatal cleanup belongs to the Unit 1C failed outcome."
                )
            if outcome.status is not _OCRProviderExecutionStatus.SUCCEEDED:
                raise InvalidOCRProviderCleanupDiagnosticContextError(
                    "cleanup warnings require a successful provider outcome."
                )
            if (
                diagnostic.artifact_key is not None
                and diagnostic.artifact_key
                != self.batch.request.artifact_key
            ):
                raise InvalidOCRProviderCleanupDiagnosticContextError(
                    "diagnostic artifact_key must match the batch request."
                )
            seen_provider_ids.add(provider_id)
            previous_position = position


def _validate_provider(value: object) -> _OCRProviderCapabilities:
    if not isinstance(value, _OCRProviderCapabilities):
        raise InvalidOCRProviderCleanupDiagnosticContextError(
            "provider must be OCRProviderCapabilities."
        )
    try:
        value.validate()
    except Exception as error:
        raise InvalidOCRProviderCleanupDiagnosticContextError(
            "provider must satisfy the Unit 1A capability contract."
        ) from error
    return value


def _validate_artifact_key(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > _MAX_ARTIFACT_KEY_CHARS
        or value != value.strip()
    ):
        raise InvalidOCRProviderCleanupDiagnosticContextError(
            "artifact_key must be a nonblank identifier of at most 255 characters."
        )
    if "/" in value or "\\" in value:
        raise InvalidOCRProviderCleanupDiagnosticContextError(
            "artifact_key must be an identifier, not a path."
        )
    return value
