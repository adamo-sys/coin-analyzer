"""Pure evaluation of confirmed monarch/year compatibility.

The evaluator reads exact submitted values from an immutable confirmed
observation set and emits at most one transient field-intelligence finding.  It
contains no historical facts, default catalog, normalization, persistence,
readiness integration, or runtime side effects.
"""

from __future__ import annotations

from .workflow_confirmed_observation_compatibility import (
    ConfirmedObservationCompatibilityStatus as _ConfirmedObservationCompatibilityStatus,
    IncompatibleConfirmedObservationError as _IncompatibleConfirmedObservationError,
    _assess_monarch_year_compatibility as _assess_monarch_year_compatibility,
)
from .workflow_confirmed_observation_field_intelligence import (
    FieldIntelligenceFinding as _FieldIntelligenceFinding,
    FieldIntelligenceStatus as _FieldIntelligenceStatus,
)
from .workflow_confirmed_observation_models import (
    ConfirmedFieldObservation as _ConfirmedFieldObservation,
    ConfirmedObservationSet as _ConfirmedObservationSet,
)
from .workflow_confirmed_observation_validators import (
    validate_confirmed_observation_set as _validate_confirmed_observation_set,
)


__all__ = [
    "MonarchYearEvaluationError",
    "InvalidMonarchYearEvaluationContextError",
    "assess_monarch_year_compatibility",
]


_EVALUATOR_RULE_ID = "monarch-year.evaluation-v1"
_RELEVANT_FIELDS = frozenset({"monarch", "year"})


class MonarchYearEvaluationError(ValueError):
    """A monarch-year evaluation request is malformed."""

    __slots__ = ()

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Monarch-year evaluation errors are immutable.")


class InvalidMonarchYearEvaluationContextError(MonarchYearEvaluationError):
    """The source or evaluation context cannot be safely evaluated."""


def assess_monarch_year_compatibility(
    source: _ConfirmedObservationSet,
) -> _FieldIntelligenceFinding | None:
    """Assess exact submitted monarch/year compatibility.

    ``None`` means the valid source contains none of the two relevant fields.
    Missing context and unknown monarch coverage produce conservative
    ``NOT_EVALUATED`` findings.  The shared private helper determines the exact
    compatibility answer and the evaluator only maps that to a transient field
    intelligence finding.
    """

    _require_valid_source(source)

    relevant = tuple(
        observation
        for observation in source.observations
        if observation.field_name in _RELEVANT_FIELDS
    )
    if not relevant:
        return None

    observations = {
        observation.field_name: observation for observation in relevant
    }
    if set(observations) != _RELEVANT_FIELDS:
        return _finding(
            rule_id=_EVALUATOR_RULE_ID,
            source_fields=_field_names(relevant),
            status=_FieldIntelligenceStatus.NOT_EVALUATED,
            diagnostic_code="REQUIRED_CONTEXT_MISSING",
        )

    try:
        result = _assess_monarch_year_compatibility(observations)
    except _IncompatibleConfirmedObservationError:
        return _finding(
            rule_id=_EVALUATOR_RULE_ID,
            source_fields=_field_names(relevant),
            status=_FieldIntelligenceStatus.INVALID,
            diagnostic_code="MONARCH_YEAR_INCOMPATIBLE",
        )

    if result.status is _ConfirmedObservationCompatibilityStatus.COMPATIBLE:
        return _finding(
            rule_id=_EVALUATOR_RULE_ID,
            source_fields=_field_names(relevant),
            status=_FieldIntelligenceStatus.VALID,
            diagnostic_code="MONARCH_YEAR_COMPATIBLE",
        )

    return _finding(
        rule_id=_EVALUATOR_RULE_ID,
        source_fields=_field_names(relevant),
        status=_FieldIntelligenceStatus.NOT_EVALUATED,
        diagnostic_code="MONARCH_YEAR_UNKNOWN",
    )


def _require_valid_source(value: object) -> _ConfirmedObservationSet:
    if not isinstance(value, _ConfirmedObservationSet):
        raise InvalidMonarchYearEvaluationContextError(
            "source must be a valid ConfirmedObservationSet."
        )
    try:
        _validate_confirmed_observation_set(value)
    except Exception:
        raise InvalidMonarchYearEvaluationContextError(
            "source must pass confirmed-observation validation."
        ) from None
    return value


def _field_names(
    observations: tuple[_ConfirmedFieldObservation, ...],
) -> tuple[str, ...]:
    return tuple(sorted(observation.field_name for observation in observations))


def _finding(
    *,
    rule_id: str,
    source_fields: tuple[str, ...],
    status: _FieldIntelligenceStatus,
    diagnostic_code: str,
) -> _FieldIntelligenceFinding:
    try:
        result = _FieldIntelligenceFinding(
            rule_id=rule_id,
            source_fields=source_fields,
            status=status,
            diagnostic_code=diagnostic_code,
        )
        result.validate()
    except Exception:
        raise InvalidMonarchYearEvaluationContextError(
            "validated monarch-year finding state is malformed."
        ) from None
    return result
