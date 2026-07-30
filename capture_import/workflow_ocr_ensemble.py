"""Pure deterministic comparison of Unit 1C OCR provider outcomes.

Comparison preserves exact provider, report, and candidate evidence.  It does
not invoke providers, normalize values, rank evidence, calibrate confidence,
select a winner, retry work, persist results, or map into collection state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .workflow_ocr_models import (
    ALLOWED_OCR_FIELDS as _ALLOWED_OCR_FIELDS,
    OCRFieldCandidate as _OCRFieldCandidate,
)
from .workflow_ocr_provider_contracts import (
    OCRProviderCapabilities as _OCRProviderCapabilities,
)
from .workflow_ocr_provider_execution import (
    OCRProviderExecutionBatch as _OCRProviderExecutionBatch,
    OCRProviderExecutionOutcome as _OCRProviderExecutionOutcome,
    OCRProviderExecutionStatus as _OCRProviderExecutionStatus,
    OCRProviderFailureCategory,
)


__all__ = [
    "OCRProviderEnsembleContractError",
    "InvalidOCRProviderEnsembleContextError",
    "OCRProviderFieldEvidenceStatus",
    "OCRProviderEnsembleFieldStatus",
    "OCRProviderFieldEvidence",
    "OCRProviderEnsembleValueGroup",
    "OCRProviderEnsembleFieldFinding",
    "OCRProviderEnsembleResult",
    "compare_ocr_provider_outcomes",
]


_DIAGNOSTIC_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class OCRProviderEnsembleContractError(ValueError):
    """A Unit 1C ensemble value contract is malformed."""


class InvalidOCRProviderEnsembleContextError(
    OCRProviderEnsembleContractError
):
    """Evidence, value-group, field, or result invariants were violated."""


class OCRProviderFieldEvidenceStatus(str, Enum):
    """Per-provider evidence state for one canonical OCR field."""

    OBSERVED = "OBSERVED"
    MISSING = "MISSING"
    PROVIDER_FAILED = "PROVIDER_FAILED"


class OCRProviderEnsembleFieldStatus(str, Enum):
    """Exact comparison result for one canonical OCR field."""

    CONSENSUS = "CONSENSUS"
    SINGLE_SOURCE = "SINGLE_SOURCE"
    CONFLICT = "CONFLICT"
    NO_OBSERVATION = "NO_OBSERVATION"
    ALL_PROVIDERS_FAILED = "ALL_PROVIDERS_FAILED"


@dataclass(frozen=True, slots=True)
class OCRProviderFieldEvidence:
    """Exact candidate or failure evidence from one eligible provider."""

    provider: _OCRProviderCapabilities
    status: OCRProviderFieldEvidenceStatus
    candidates: tuple[_OCRFieldCandidate, ...]
    failure_category: OCRProviderFailureCategory | None
    diagnostic_code: str | None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _validate_provider(self.provider)
        if not isinstance(self.status, OCRProviderFieldEvidenceStatus):
            raise InvalidOCRProviderEnsembleContextError(
                "status must be an OCRProviderFieldEvidenceStatus."
            )
        if not isinstance(self.candidates, tuple):
            raise InvalidOCRProviderEnsembleContextError(
                "candidates must be an immutable tuple."
            )
        for candidate in self.candidates:
            if not isinstance(candidate, _OCRFieldCandidate):
                raise InvalidOCRProviderEnsembleContextError(
                    "candidates must contain OCRFieldCandidate values."
                )
            try:
                candidate.validate()
            except Exception as error:
                raise InvalidOCRProviderEnsembleContextError(
                    "candidate violates OCRFieldCandidate."
                ) from error
            if candidate.provider_id != self.provider.provider_id:
                raise InvalidOCRProviderEnsembleContextError(
                    "candidate provider does not match evidence provider."
                )
        if self.status is OCRProviderFieldEvidenceStatus.OBSERVED:
            if (
                not self.candidates
                or self.failure_category is not None
                or self.diagnostic_code is not None
            ):
                raise InvalidOCRProviderEnsembleContextError(
                    "OBSERVED requires candidates and no failure."
                )
            return
        if self.status is OCRProviderFieldEvidenceStatus.MISSING:
            if (
                self.candidates
                or self.failure_category is not None
                or self.diagnostic_code is not None
            ):
                raise InvalidOCRProviderEnsembleContextError(
                    "MISSING cannot retain candidates or failure evidence."
                )
            return
        if (
            self.candidates
            or not isinstance(
                self.failure_category,
                OCRProviderFailureCategory,
            )
        ):
            raise InvalidOCRProviderEnsembleContextError(
                "PROVIDER_FAILED requires only failure evidence."
            )
        _validate_diagnostic_code(self.diagnostic_code)


@dataclass(frozen=True, slots=True)
class OCRProviderEnsembleValueGroup:
    """One exact value and its supporting providers/candidates."""

    value: str
    providers: tuple[_OCRProviderCapabilities, ...]
    candidates: tuple[_OCRFieldCandidate, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.value, str) or not self.value:
            raise InvalidOCRProviderEnsembleContextError(
                "value must be a nonempty exact string."
            )
        if not isinstance(self.providers, tuple) or not self.providers:
            raise InvalidOCRProviderEnsembleContextError(
                "providers must be a nonempty immutable tuple."
            )
        if not isinstance(self.candidates, tuple):
            raise InvalidOCRProviderEnsembleContextError(
                "candidates must be an immutable tuple."
            )
        if len(self.candidates) != len(self.providers):
            raise InvalidOCRProviderEnsembleContextError(
                "value groups require one candidate per provider."
            )
        provider_ids: list[str] = []
        for provider, candidate in zip(
            self.providers,
            self.candidates,
            strict=True,
        ):
            _validate_provider(provider)
            if not isinstance(candidate, _OCRFieldCandidate):
                raise InvalidOCRProviderEnsembleContextError(
                    "value-group candidates must be OCRFieldCandidate values."
                )
            try:
                candidate.validate()
            except Exception as error:
                raise InvalidOCRProviderEnsembleContextError(
                    "value-group candidate is malformed."
                ) from error
            if (
                candidate.provider_id != provider.provider_id
                or candidate.normalized_value != self.value
            ):
                raise InvalidOCRProviderEnsembleContextError(
                    "value-group candidate does not match its provider/value."
                )
            provider_ids.append(provider.provider_id)
        if len(set(provider_ids)) != len(provider_ids):
            raise InvalidOCRProviderEnsembleContextError(
                "value-group providers must be unique."
            )
        if tuple(provider_ids) != tuple(sorted(provider_ids)):
            raise InvalidOCRProviderEnsembleContextError(
                "value-group providers must retain canonical provider order."
            )


@dataclass(frozen=True, slots=True)
class OCRProviderEnsembleFieldFinding:
    """Complete exact evidence and comparison formula for one field."""

    field_name: str
    status: OCRProviderEnsembleFieldStatus
    evidence: tuple[OCRProviderFieldEvidence, ...]
    value_groups: tuple[OCRProviderEnsembleValueGroup, ...]
    consensus_value: str | None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _validate_field_name(self.field_name)
        if not isinstance(self.status, OCRProviderEnsembleFieldStatus):
            raise InvalidOCRProviderEnsembleContextError(
                "status must be an OCRProviderEnsembleFieldStatus."
            )
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise InvalidOCRProviderEnsembleContextError(
                "evidence must be a nonempty immutable tuple."
            )
        provider_ids: list[str] = []
        for item in self.evidence:
            if not isinstance(item, OCRProviderFieldEvidence):
                raise InvalidOCRProviderEnsembleContextError(
                    "evidence must contain OCRProviderFieldEvidence values."
                )
            item.validate()
            if any(
                candidate.field_name != self.field_name
                for candidate in item.candidates
            ):
                raise InvalidOCRProviderEnsembleContextError(
                    "evidence candidates must match the finding field."
                )
            provider_ids.append(item.provider.provider_id)
        if (
            len(set(provider_ids)) != len(provider_ids)
            or tuple(provider_ids) != tuple(sorted(provider_ids))
        ):
            raise InvalidOCRProviderEnsembleContextError(
                "evidence must use unique canonical provider order."
            )
        if not isinstance(self.value_groups, tuple):
            raise InvalidOCRProviderEnsembleContextError(
                "value_groups must be an immutable tuple."
            )
        for group in self.value_groups:
            if not isinstance(group, OCRProviderEnsembleValueGroup):
                raise InvalidOCRProviderEnsembleContextError(
                    "value_groups contains an unsupported value."
                )
            group.validate()
        expected_groups = _derive_value_groups(self.evidence)
        if not _groups_match_identity(self.value_groups, expected_groups):
            raise InvalidOCRProviderEnsembleContextError(
                "value_groups must exactly derive from field evidence."
            )
        expected_status = _derive_field_status(self.evidence, expected_groups)
        if self.status is not expected_status:
            raise InvalidOCRProviderEnsembleContextError(
                "field status does not match its evidence."
            )
        expected_consensus = (
            expected_groups[0].value
            if expected_status is OCRProviderEnsembleFieldStatus.CONSENSUS
            else None
        )
        if self.consensus_value != expected_consensus:
            raise InvalidOCRProviderEnsembleContextError(
                "consensus_value does not match field status/evidence."
            )


@dataclass(frozen=True, slots=True)
class OCRProviderEnsembleResult:
    """Complete canonical field comparison for one exact execution batch."""

    batch: _OCRProviderExecutionBatch
    fields: tuple[OCRProviderEnsembleFieldFinding, ...]

    def __post_init__(self) -> None:
        self.validate()

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(item.field_name for item in self.fields)

    @property
    def consensus_fields(self) -> tuple[OCRProviderEnsembleFieldFinding, ...]:
        return self._with_status(OCRProviderEnsembleFieldStatus.CONSENSUS)

    @property
    def conflict_fields(self) -> tuple[OCRProviderEnsembleFieldFinding, ...]:
        return self._with_status(OCRProviderEnsembleFieldStatus.CONFLICT)

    @property
    def single_source_fields(
        self,
    ) -> tuple[OCRProviderEnsembleFieldFinding, ...]:
        return self._with_status(OCRProviderEnsembleFieldStatus.SINGLE_SOURCE)

    @property
    def unavailable_fields(
        self,
    ) -> tuple[OCRProviderEnsembleFieldFinding, ...]:
        return self._with_status(
            OCRProviderEnsembleFieldStatus.ALL_PROVIDERS_FAILED
        )

    def _with_status(
        self,
        status: OCRProviderEnsembleFieldStatus,
    ) -> tuple[OCRProviderEnsembleFieldFinding, ...]:
        return tuple(item for item in self.fields if item.status is status)

    def validate(self) -> None:
        if not isinstance(self.batch, _OCRProviderExecutionBatch):
            raise InvalidOCRProviderEnsembleContextError(
                "batch must be an OCRProviderExecutionBatch."
            )
        try:
            self.batch.validate()
        except Exception as error:
            raise InvalidOCRProviderEnsembleContextError(
                "batch violates OCRProviderExecutionBatch."
            ) from error
        if not isinstance(self.fields, tuple):
            raise InvalidOCRProviderEnsembleContextError(
                "fields must be an immutable tuple."
            )
        expected = _build_field_findings(self.batch)
        if len(self.fields) != len(expected):
            raise InvalidOCRProviderEnsembleContextError(
                "fields must cover the exact comparison field universe."
            )
        for actual, wanted in zip(self.fields, expected, strict=True):
            if not isinstance(actual, OCRProviderEnsembleFieldFinding):
                raise InvalidOCRProviderEnsembleContextError(
                    "fields must contain OCRProviderEnsembleFieldFinding values."
                )
            actual.validate()
            if not _findings_match_identity(actual, wanted):
                raise InvalidOCRProviderEnsembleContextError(
                    "field finding does not match the execution batch."
                )


def compare_ocr_provider_outcomes(
    batch: _OCRProviderExecutionBatch,
) -> OCRProviderEnsembleResult:
    """Compare exact successful field values without selecting a winner."""

    if not isinstance(batch, _OCRProviderExecutionBatch):
        raise InvalidOCRProviderEnsembleContextError(
            "batch must be an OCRProviderExecutionBatch."
        )
    try:
        batch.validate()
    except Exception as error:
        raise InvalidOCRProviderEnsembleContextError(
            "batch violates OCRProviderExecutionBatch."
        ) from error
    return OCRProviderEnsembleResult(
        batch=batch,
        fields=_build_field_findings(batch),
    )


def _build_field_findings(
    batch: _OCRProviderExecutionBatch,
) -> tuple[OCRProviderEnsembleFieldFinding, ...]:
    field_names = _field_universe(batch)
    return tuple(
        _build_field_finding(batch, field_name)
        for field_name in field_names
    )


def _field_universe(
    batch: _OCRProviderExecutionBatch,
) -> tuple[str, ...]:
    names = set(batch.selection.criteria.required_fields)
    for outcome in batch.successful_outcomes:
        names.update(
            candidate.field_name
            for candidate in outcome.report.candidates
        )
    return tuple(sorted(names))


def _build_field_finding(
    batch: _OCRProviderExecutionBatch,
    field_name: str,
) -> OCRProviderEnsembleFieldFinding:
    evidence: list[OCRProviderFieldEvidence] = []
    for outcome in batch.outcomes:
        if outcome.status is _OCRProviderExecutionStatus.FAILED:
            evidence.append(
                OCRProviderFieldEvidence(
                    provider=outcome.capabilities,
                    status=OCRProviderFieldEvidenceStatus.PROVIDER_FAILED,
                    candidates=(),
                    failure_category=outcome.failure_category,
                    diagnostic_code=outcome.diagnostic_code,
                )
            )
            continue
        candidates = tuple(
            candidate
            for candidate in outcome.report.candidates
            if candidate.field_name == field_name
        )
        evidence.append(
            OCRProviderFieldEvidence(
                provider=outcome.capabilities,
                status=(
                    OCRProviderFieldEvidenceStatus.OBSERVED
                    if candidates
                    else OCRProviderFieldEvidenceStatus.MISSING
                ),
                candidates=candidates,
                failure_category=None,
                diagnostic_code=None,
            )
        )
    evidence_tuple = tuple(evidence)
    groups = _derive_value_groups(evidence_tuple)
    status = _derive_field_status(evidence_tuple, groups)
    return OCRProviderEnsembleFieldFinding(
        field_name=field_name,
        status=status,
        evidence=evidence_tuple,
        value_groups=groups,
        consensus_value=(
            groups[0].value
            if status is OCRProviderEnsembleFieldStatus.CONSENSUS
            else None
        ),
    )


def _derive_value_groups(
    evidence: tuple[OCRProviderFieldEvidence, ...],
) -> tuple[OCRProviderEnsembleValueGroup, ...]:
    values: dict[
        str,
        tuple[
            list[_OCRProviderCapabilities],
            list[_OCRFieldCandidate],
        ],
    ] = {}
    for item in evidence:
        for candidate in item.candidates:
            providers, candidates = values.setdefault(
                candidate.normalized_value,
                ([], []),
            )
            providers.append(item.provider)
            candidates.append(candidate)
    return tuple(
        OCRProviderEnsembleValueGroup(
            value=value,
            providers=tuple(providers),
            candidates=tuple(candidates),
        )
        for value, (providers, candidates) in values.items()
    )


def _derive_field_status(
    evidence: tuple[OCRProviderFieldEvidence, ...],
    groups: tuple[OCRProviderEnsembleValueGroup, ...],
) -> OCRProviderEnsembleFieldStatus:
    if len(groups) > 1:
        return OCRProviderEnsembleFieldStatus.CONFLICT
    if len(groups) == 1:
        if len(groups[0].providers) >= 2:
            return OCRProviderEnsembleFieldStatus.CONSENSUS
        return OCRProviderEnsembleFieldStatus.SINGLE_SOURCE
    if all(
        item.status is OCRProviderFieldEvidenceStatus.PROVIDER_FAILED
        for item in evidence
    ):
        return OCRProviderEnsembleFieldStatus.ALL_PROVIDERS_FAILED
    return OCRProviderEnsembleFieldStatus.NO_OBSERVATION


def _groups_match_identity(
    actual: tuple[OCRProviderEnsembleValueGroup, ...],
    expected: tuple[OCRProviderEnsembleValueGroup, ...],
) -> bool:
    if len(actual) != len(expected):
        return False
    for left, right in zip(actual, expected, strict=True):
        if left.value != right.value:
            return False
        if not _identity_tuple_equal(left.providers, right.providers):
            return False
        if not _identity_tuple_equal(left.candidates, right.candidates):
            return False
    return True


def _findings_match_identity(
    actual: OCRProviderEnsembleFieldFinding,
    expected: OCRProviderEnsembleFieldFinding,
) -> bool:
    if (
        actual.field_name != expected.field_name
        or actual.status is not expected.status
        or actual.consensus_value != expected.consensus_value
        or len(actual.evidence) != len(expected.evidence)
    ):
        return False
    for left, right in zip(actual.evidence, expected.evidence, strict=True):
        if (
            left.provider is not right.provider
            or left.status is not right.status
            or left.failure_category is not right.failure_category
            or left.diagnostic_code != right.diagnostic_code
            or not _identity_tuple_equal(left.candidates, right.candidates)
        ):
            return False
    return _groups_match_identity(actual.value_groups, expected.value_groups)


def _identity_tuple_equal(left: tuple[object, ...], right: tuple[object, ...]) -> bool:
    return len(left) == len(right) and all(
        one is two for one, two in zip(left, right, strict=True)
    )


def _validate_provider(value: object) -> _OCRProviderCapabilities:
    if not isinstance(value, _OCRProviderCapabilities):
        raise InvalidOCRProviderEnsembleContextError(
            "provider must be OCRProviderCapabilities."
        )
    try:
        value.validate()
    except Exception as error:
        raise InvalidOCRProviderEnsembleContextError(
            "provider capabilities are malformed."
        ) from error
    return value


def _validate_field_name(value: object) -> str:
    if not isinstance(value, str) or value not in _ALLOWED_OCR_FIELDS:
        raise InvalidOCRProviderEnsembleContextError(
            "field_name must be a canonical OCR field."
        )
    return value


def _validate_diagnostic_code(value: object) -> str:
    if not isinstance(value, str) or _DIAGNOSTIC_CODE.fullmatch(value) is None:
        raise InvalidOCRProviderEnsembleContextError(
            "diagnostic_code violates the Unit 1A contract."
        )
    return value
