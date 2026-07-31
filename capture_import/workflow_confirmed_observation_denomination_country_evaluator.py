"""Pure evaluation of confirmed denomination-country compatibility.

The evaluator reads exact submitted values from an immutable confirmed
observation set and emits at most one transient field-intelligence finding.  It
contains no persistence, readiness integration, historical denomination facts,
normalization, or runtime side effects.
"""

from __future__ import annotations

from .workflow_confirmed_observation_denomination_country_rules import (
    DenominationCountryRuleCatalog as _DenominationCountryRuleCatalog,
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
    "DenominationCountryEvaluationError",
    "InvalidDenominationCountryEvaluationContextError",
    "assess_denomination_country_compatibility",
]


_EVALUATOR_RULE_ID = "denomination-country.evaluation-v1"
_RELEVANT_FIELDS = frozenset({"country", "denomination"})


class DenominationCountryEvaluationError(ValueError):
    """A denomination-country evaluation request is malformed."""

    __slots__ = ()

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            "Denomination-country evaluation errors are immutable."
        )


class InvalidDenominationCountryEvaluationContextError(
    DenominationCountryEvaluationError
):
    """The source or catalog cannot be safely evaluated."""


def assess_denomination_country_compatibility(
    source: _ConfirmedObservationSet,
    catalog: _DenominationCountryRuleCatalog,
) -> _FieldIntelligenceFinding | None:
    """Assess exact submitted denomination-country compatibility.

    ``None`` means the valid source contains none of the two relevant fields.
    Missing context and absent catalog coverage produce conservative
    ``NOT_EVALUATED`` findings.  A matched catalog rule produces ``VALID`` or
    ``INVALID`` solely through the exact caller-supplied compatibility state.
    """

    _require_valid_source(source)
    _require_valid_catalog(catalog)

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

    country = observations["country"].submitted_value
    denomination = observations["denomination"].submitted_value
    matching_rule = next(
        (
            rule
            for rule in catalog.rules
            if rule.country == country and rule.denomination == denomination
        ),
        None,
    )
    if matching_rule is None:
        return _finding(
            rule_id=_EVALUATOR_RULE_ID,
            source_fields=_field_names(relevant),
            status=_FieldIntelligenceStatus.NOT_EVALUATED,
            diagnostic_code="RULE_COVERAGE_UNKNOWN",
        )

    compatibility = matching_rule.compatibility
    return _finding(
        rule_id=matching_rule.rule_id,
        source_fields=_field_names(relevant),
        status=(
            _FieldIntelligenceStatus.VALID
            if compatibility.value == "COMPATIBLE"
            else _FieldIntelligenceStatus.INVALID
        ),
        diagnostic_code=(
            "DENOMINATION_COUNTRY_COMPATIBLE"
            if compatibility.value == "COMPATIBLE"
            else "DENOMINATION_COUNTRY_INCOMPATIBLE"
        ),
    )


def _require_valid_source(value: object) -> _ConfirmedObservationSet:
    if not isinstance(value, _ConfirmedObservationSet):
        raise InvalidDenominationCountryEvaluationContextError(
            "source must be a valid ConfirmedObservationSet."
        )
    try:
        _validate_confirmed_observation_set(value)
    except Exception:
        raise InvalidDenominationCountryEvaluationContextError(
            "source must pass confirmed-observation validation."
        ) from None
    return value


def _require_valid_catalog(value: object) -> _DenominationCountryRuleCatalog:
    if not isinstance(value, _DenominationCountryRuleCatalog):
        raise InvalidDenominationCountryEvaluationContextError(
            "catalog must be a valid DenominationCountryRuleCatalog."
        )
    try:
        value.validate()
    except Exception:
        raise InvalidDenominationCountryEvaluationContextError(
            "catalog must pass denomination-country rule validation."
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
        raise InvalidDenominationCountryEvaluationContextError(
            "validated denomination-country evaluation state is malformed."
        ) from None
    return result
