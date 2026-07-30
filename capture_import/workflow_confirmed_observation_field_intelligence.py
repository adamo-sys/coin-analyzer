"""Transient contracts for field-intelligence findings.

These contracts describe determinate validity, determinate invalidity, and
non-evaluation over an exact human-confirmed observation set.  They contain no
historical or catalog policy, do not alter readiness, and have no persistence
or runtime authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .workflow_confirmed_observation_models import (
    ConfirmedObservationSet as _ConfirmedObservationSet,
)
from .workflow_ocr_models import ALLOWED_OCR_FIELDS as _ALLOWED_OCR_FIELDS


__all__ = [
    "FieldIntelligenceContractError",
    "InvalidFieldIntelligenceContextError",
    "DuplicateFieldIntelligenceFindingError",
    "MisalignedFieldIntelligenceFindingError",
    "FieldIntelligenceStatus",
    "FieldIntelligenceFinding",
    "ConfirmedObservationFieldIntelligenceAssessment",
]


_RULE_ID = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")
_DIAGNOSTIC_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_CANONICAL_FIELD_ORDER = tuple(sorted(_ALLOWED_OCR_FIELDS))


class FieldIntelligenceContractError(ValueError):
    """A field-intelligence assessment contract is malformed."""

    __slots__ = ()

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Field-intelligence contract errors are immutable.")


class InvalidFieldIntelligenceContextError(
    FieldIntelligenceContractError
):
    """A finding or assessment contains malformed contract data."""


class DuplicateFieldIntelligenceFindingError(
    FieldIntelligenceContractError
):
    """An assessment contains more than one finding for one rule."""


class MisalignedFieldIntelligenceFindingError(
    FieldIntelligenceContractError
):
    """A finding references a field absent from its assessment source."""


class FieldIntelligenceStatus(str, Enum):
    """Bounded outcome of one explicitly named field-intelligence rule."""

    VALID = "VALID"
    INVALID = "INVALID"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class FieldIntelligenceFinding:
    """One transient rule outcome linked by canonical source-field names.

    ``VALID`` means only that this rule evaluated its declared evidence and
    accepted it.  ``INVALID`` records a determinate rule violation but grants
    no blocking or mutation authority.  ``NOT_EVALUATED`` records that the
    rule did not reach a determination and must never be treated as valid.
    """

    rule_id: str
    source_fields: tuple[str, ...]
    status: FieldIntelligenceStatus
    diagnostic_code: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate syntax and deterministic field ordering."""

        _validate_rule_id(self.rule_id)
        _validate_source_fields(self.source_fields)
        if not isinstance(self.status, FieldIntelligenceStatus):
            raise InvalidFieldIntelligenceContextError(
                "status must be a FieldIntelligenceStatus."
            )
        _validate_diagnostic_code(self.diagnostic_code)


@dataclass(frozen=True, slots=True)
class ConfirmedObservationFieldIntelligenceAssessment:
    """Ordered transient findings over one exact confirmed-observation set.

    An empty ``findings`` tuple means that no field-intelligence rules were
    evaluated or reported.  It makes no validity or readiness claim.
    """

    source: _ConfirmedObservationSet
    findings: tuple[FieldIntelligenceFinding, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate source, nested findings, linkage, uniqueness, and order."""

        if not isinstance(self.source, _ConfirmedObservationSet):
            raise InvalidFieldIntelligenceContextError(
                "source must be a ConfirmedObservationSet."
            )
        try:
            self.source.validate()
        except (TypeError, ValueError):
            raise InvalidFieldIntelligenceContextError(
                "source must be a valid ConfirmedObservationSet."
            ) from None

        if not isinstance(self.findings, tuple):
            raise InvalidFieldIntelligenceContextError(
                "findings must be an immutable tuple."
            )
        if any(
            not isinstance(item, FieldIntelligenceFinding)
            for item in self.findings
        ):
            raise InvalidFieldIntelligenceContextError(
                "findings must contain FieldIntelligenceFinding values."
            )

        source_field_names = frozenset(
            observation.field_name
            for observation in self.source.observations
        )
        rule_ids: set[str] = set()
        for finding in self.findings:
            finding.validate()
            if finding.rule_id in rule_ids:
                raise DuplicateFieldIntelligenceFindingError(
                    "findings must not contain duplicate rule IDs."
                )
            rule_ids.add(finding.rule_id)
            if any(
                field_name not in source_field_names
                for field_name in finding.source_fields
            ):
                raise MisalignedFieldIntelligenceFindingError(
                    "finding source_fields must exist in assessment source."
                )

        expected_order = tuple(
            sorted(self.findings, key=lambda item: item.rule_id)
        )
        if self.findings != expected_order:
            raise InvalidFieldIntelligenceContextError(
                "findings must be in lexical rule_id order."
            )

    @property
    def rule_ids(self) -> tuple[str, ...]:
        """Return rule IDs in the assessment's validated order."""

        return tuple(finding.rule_id for finding in self.findings)

    @property
    def valid_findings(self) -> tuple[FieldIntelligenceFinding, ...]:
        """Return exact findings that reached a valid determination."""

        return self._with_status(FieldIntelligenceStatus.VALID)

    @property
    def invalid_findings(self) -> tuple[FieldIntelligenceFinding, ...]:
        """Return exact findings that reached an invalid determination."""

        return self._with_status(FieldIntelligenceStatus.INVALID)

    @property
    def not_evaluated_findings(
        self,
    ) -> tuple[FieldIntelligenceFinding, ...]:
        """Return exact findings that did not reach a determination."""

        return self._with_status(FieldIntelligenceStatus.NOT_EVALUATED)

    @property
    def evaluated_findings(self) -> tuple[FieldIntelligenceFinding, ...]:
        """Return exact findings with either determinate outcome."""

        return tuple(
            finding
            for finding in self.findings
            if finding.status is not FieldIntelligenceStatus.NOT_EVALUATED
        )

    @property
    def has_invalid_findings(self) -> bool:
        """Whether at least one supplied finding is determinately invalid."""

        return any(
            finding.status is FieldIntelligenceStatus.INVALID
            for finding in self.findings
        )

    @property
    def has_not_evaluated_findings(self) -> bool:
        """Whether at least one supplied finding was not evaluated."""

        return any(
            finding.status is FieldIntelligenceStatus.NOT_EVALUATED
            for finding in self.findings
        )

    def _with_status(
        self,
        status: FieldIntelligenceStatus,
    ) -> tuple[FieldIntelligenceFinding, ...]:
        return tuple(
            finding
            for finding in self.findings
            if finding.status is status
        )


def _validate_rule_id(value: object) -> str:
    if not isinstance(value, str) or _RULE_ID.fullmatch(value) is None:
        raise InvalidFieldIntelligenceContextError(
            "rule_id must match [a-z][a-z0-9._-]{0,127}."
        )
    return value


def _validate_diagnostic_code(value: object) -> str:
    if (
        not isinstance(value, str)
        or _DIAGNOSTIC_CODE.fullmatch(value) is None
    ):
        raise InvalidFieldIntelligenceContextError(
            "diagnostic_code must match [A-Z][A-Z0-9_]{0,63}."
        )
    return value


def _validate_source_fields(value: object) -> None:
    if not isinstance(value, tuple):
        raise InvalidFieldIntelligenceContextError(
            "source_fields must be an immutable tuple."
        )
    if not value:
        raise InvalidFieldIntelligenceContextError(
            "source_fields must contain at least one canonical field."
        )
    if any(not isinstance(item, str) for item in value):
        raise InvalidFieldIntelligenceContextError(
            "source_fields must contain canonical field-name strings."
        )
    if any(item not in _ALLOWED_OCR_FIELDS for item in value):
        raise InvalidFieldIntelligenceContextError(
            "source_fields must contain only canonical OCR fields."
        )
    if len(set(value)) != len(value):
        raise InvalidFieldIntelligenceContextError(
            "source_fields must not contain duplicates."
        )
    field_names = frozenset(value)
    expected_order = tuple(
        item for item in _CANONICAL_FIELD_ORDER if item in field_names
    )
    if value != expected_order:
        raise InvalidFieldIntelligenceContextError(
            "source_fields must use canonical lexical field order."
        )
