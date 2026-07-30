"""Pure evaluation of confirmed coin context against caller-supplied year rules.

The evaluator reads exact submitted values from an immutable confirmed
observation set and emits at most one transient field-intelligence finding.  It
contains no historical facts, default catalog, normalization, persistence,
readiness integration, or runtime side effects.
"""

from __future__ import annotations

from .workflow_confirmed_observation_coin_year_rules import (
    CoinYearRuleCatalog as _CoinYearRuleCatalog,
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
    "CoinYearEvaluationError",
    "InvalidCoinYearEvaluationContextError",
    "assess_coin_specific_year",
]


_EVALUATOR_RULE_ID = "coin-year.evaluation-v1"
_RELEVANT_FIELDS = frozenset(
    {"country", "denomination", "series_type", "year"}
)
_BASE_FIELDS = frozenset({"country", "denomination", "year"})


class CoinYearEvaluationError(ValueError):
    """A coin-specific year evaluation request is malformed."""

    __slots__ = ()

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Coin-year evaluation errors are immutable.")


class InvalidCoinYearEvaluationContextError(CoinYearEvaluationError):
    """The source or catalog cannot be safely evaluated."""


def assess_coin_specific_year(
    source: _ConfirmedObservationSet,
    catalog: _CoinYearRuleCatalog,
) -> _FieldIntelligenceFinding | None:
    """Assess exact submitted coin context against an exact rule catalog.

    ``None`` means the valid source contains none of the four relevant fields.
    Missing context and absent catalog coverage produce conservative
    ``NOT_EVALUATED`` findings.  A matched rule produces ``VALID`` or
    ``INVALID`` solely through exact allowed-year membership.
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
        observation.field_name: observation
        for observation in relevant
    }
    if not _BASE_FIELDS.issubset(observations):
        return _finding(
            rule_id=_EVALUATOR_RULE_ID,
            source_fields=_field_names(relevant),
            status=_FieldIntelligenceStatus.NOT_EVALUATED,
            diagnostic_code="REQUIRED_CONTEXT_MISSING",
        )

    country = observations["country"].submitted_value
    denomination = observations["denomination"].submitted_value
    matching_scope = tuple(
        rule
        for rule in catalog.rules
        if rule.country == country and rule.denomination == denomination
    )
    if not matching_scope:
        return _finding(
            rule_id=_EVALUATOR_RULE_ID,
            source_fields=_field_names(
                relevant,
                include_series_type=False,
            ),
            status=_FieldIntelligenceStatus.NOT_EVALUATED,
            diagnostic_code="RULE_COVERAGE_UNKNOWN",
        )

    generic_rule = (
        matching_scope[0]
        if len(matching_scope) == 1
        and matching_scope[0].series_type is None
        else None
    )
    if generic_rule is not None:
        return _matched_finding(
            rule=generic_rule,
            year_observation=observations["year"],
            source_fields=_field_names(
                relevant,
                include_series_type=False,
            ),
        )

    series_observation = observations.get("series_type")
    if series_observation is None:
        return _finding(
            rule_id=_EVALUATOR_RULE_ID,
            source_fields=_field_names(relevant),
            status=_FieldIntelligenceStatus.NOT_EVALUATED,
            diagnostic_code="REQUIRED_CONTEXT_MISSING",
        )

    matched_rule = next(
        (
            rule
            for rule in matching_scope
            if rule.series_type == series_observation.submitted_value
        ),
        None,
    )
    if matched_rule is None:
        return _finding(
            rule_id=_EVALUATOR_RULE_ID,
            source_fields=_field_names(relevant),
            status=_FieldIntelligenceStatus.NOT_EVALUATED,
            diagnostic_code="RULE_COVERAGE_UNKNOWN",
        )
    return _matched_finding(
        rule=matched_rule,
        year_observation=observations["year"],
        source_fields=_field_names(relevant),
    )


def _require_valid_source(value: object) -> _ConfirmedObservationSet:
    if not isinstance(value, _ConfirmedObservationSet):
        raise InvalidCoinYearEvaluationContextError(
            "source must be a valid ConfirmedObservationSet."
        )
    try:
        _validate_confirmed_observation_set(value)
    except Exception:
        raise InvalidCoinYearEvaluationContextError(
            "source must pass confirmed-observation validation."
        ) from None
    return value


def _require_valid_catalog(value: object) -> _CoinYearRuleCatalog:
    if not isinstance(value, _CoinYearRuleCatalog):
        raise InvalidCoinYearEvaluationContextError(
            "catalog must be a valid CoinYearRuleCatalog."
        )
    try:
        value.validate()
    except Exception:
        raise InvalidCoinYearEvaluationContextError(
            "catalog must pass coin-year rule validation."
        ) from None
    return value


def _matched_finding(
    *,
    rule: object,
    year_observation: _ConfirmedFieldObservation,
    source_fields: tuple[str, ...],
) -> _FieldIntelligenceFinding:
    try:
        year = int(year_observation.submitted_value)
        allowed_years = rule.allowed_years
        rule_id = rule.rule_id
    except (AttributeError, TypeError, ValueError):
        raise InvalidCoinYearEvaluationContextError(
            "validated coin-year evaluation state is malformed."
        ) from None
    allowed = year in allowed_years
    return _finding(
        rule_id=rule_id,
        source_fields=source_fields,
        status=(
            _FieldIntelligenceStatus.VALID
            if allowed
            else _FieldIntelligenceStatus.INVALID
        ),
        diagnostic_code=(
            "YEAR_ALLOWED"
            if allowed
            else "YEAR_OUTSIDE_DECLARED_SET"
        ),
    )


def _field_names(
    observations: tuple[_ConfirmedFieldObservation, ...],
    *,
    include_series_type: bool = True,
) -> tuple[str, ...]:
    return tuple(
        observation.field_name
        for observation in observations
        if include_series_type or observation.field_name != "series_type"
    )


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
        raise InvalidCoinYearEvaluationContextError(
            "validated coin-year finding state is malformed."
        ) from None
    return result
