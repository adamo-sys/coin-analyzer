"""Pure evaluation of confirmed mintmark assertions.

The evaluator reads exact submitted values from an immutable confirmed
observation set and emits at most one transient field-intelligence finding.  It
contains no historical mintmark facts, default catalog, normalization,
persistence, readiness integration, or runtime side effects.
"""

from __future__ import annotations

from .workflow_confirmed_observation_field_intelligence import (
    FieldIntelligenceFinding as _FieldIntelligenceFinding,
    FieldIntelligenceStatus as _FieldIntelligenceStatus,
)
from .workflow_confirmed_observation_mintmark_rules import (
    MintmarkRule as _MintmarkRule,
    MintmarkRuleCatalog as _MintmarkRuleCatalog,
)
from .workflow_confirmed_observation_models import (
    ConfirmedFieldObservation as _ConfirmedFieldObservation,
    ConfirmedObservationSet as _ConfirmedObservationSet,
)
from .workflow_confirmed_observation_validators import (
    validate_confirmed_observation_set as _validate_confirmed_observation_set,
)


__all__ = [
    "MintmarkEvaluationError",
    "InvalidMintmarkEvaluationContextError",
    "assess_mintmark",
]


_EVALUATOR_RULE_ID = "mintmark.evaluation-v1"
_RELEVANT_FIELDS = frozenset(
    {
        "country",
        "denomination",
        "series_type",
        "year",
        "monarch",
        "mintmark",
    }
)
_BASE_FIELDS = frozenset({"country", "denomination", "mintmark"})
_GENERIC_SCOPE_FIELDS = frozenset({"country", "denomination", "mintmark"})
_SPECIFIC_SCOPE_FIELDS = frozenset(
    {"country", "denomination", "series_type", "year", "monarch", "mintmark"}
)


class MintmarkEvaluationError(ValueError):
    """A mintmark evaluation request is malformed."""

    __slots__ = ()

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Mintmark evaluation errors are immutable.")


class InvalidMintmarkEvaluationContextError(MintmarkEvaluationError):
    """The source or catalog cannot be safely evaluated."""


def assess_mintmark(
    source: _ConfirmedObservationSet,
    catalog: _MintmarkRuleCatalog,
) -> _FieldIntelligenceFinding | None:
    """Assess exact submitted mintmark assertions against an exact rule catalog.

    ``None`` means the valid source contains none of the six relevant fields.
    Missing required context and absent catalog coverage produce conservative
    ``NOT_EVALUATED`` findings. A matched catalog rule yields ``VALID`` or
    ``INVALID`` solely through exact caller-supplied mintmark matching.
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
    if not _BASE_FIELDS.issubset(observations):
        return _finding(
            rule_id=_EVALUATOR_RULE_ID,
            source_fields=_field_names(relevant),
            status=_FieldIntelligenceStatus.NOT_EVALUATED,
            diagnostic_code="REQUIRED_CONTEXT_MISSING",
        )

    country = observations["country"].submitted_value
    denomination = observations["denomination"].submitted_value
    mintmark = observations["mintmark"].submitted_value
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
                include_optional_specific=False,
            ),
            status=_FieldIntelligenceStatus.NOT_EVALUATED,
            diagnostic_code="RULE_COVERAGE_UNKNOWN",
        )

    generic_rule = next(
        (
            rule
            for rule in matching_scope
            if _is_generic(rule)
        ),
        None,
    )
    if generic_rule is not None:
        return _matched_finding(
            rule=generic_rule,
            mintmark_observation=observations["mintmark"],
            submitted_mintmark=mintmark,
            source_fields=_field_names(
                relevant,
                include_optional_specific=False,
            ),
        )

    if not _SPECIFIC_SCOPE_FIELDS.issubset(observations):
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
            if rule.series_type == observations["series_type"].submitted_value
            and rule.year == _coerce_year(observations["year"])
            and rule.monarch == observations["monarch"].submitted_value
        ),
        None,
    )
    if matched_rule is None:
        return _finding(
            rule_id=_EVALUATOR_RULE_ID,
            source_fields=_field_names(
                relevant,
                include_optional_specific=False,
            ),
            status=_FieldIntelligenceStatus.NOT_EVALUATED,
            diagnostic_code="RULE_COVERAGE_UNKNOWN",
        )

    return _matched_finding(
        rule=matched_rule,
        mintmark_observation=observations["mintmark"],
        submitted_mintmark=mintmark,
        source_fields=_field_names(relevant),
    )


def _require_valid_source(value: object) -> _ConfirmedObservationSet:
    if not isinstance(value, _ConfirmedObservationSet):
        raise InvalidMintmarkEvaluationContextError(
            "source must be a valid ConfirmedObservationSet."
        )
    try:
        _validate_confirmed_observation_set(value)
    except Exception:
        raise InvalidMintmarkEvaluationContextError(
            "source must pass confirmed-observation validation."
        ) from None
    return value


def _require_valid_catalog(value: object) -> _MintmarkRuleCatalog:
    if not isinstance(value, _MintmarkRuleCatalog):
        raise InvalidMintmarkEvaluationContextError(
            "catalog must be a valid MintmarkRuleCatalog."
        )
    try:
        value.validate()
    except Exception:
        raise InvalidMintmarkEvaluationContextError(
            "catalog must pass mintmark rule validation."
        ) from None
    return value


def _is_generic(rule: _MintmarkRule) -> bool:
    return (
        rule.series_type is None
        and rule.year is None
        and rule.monarch is None
    )


def _coerce_year(observation: _ConfirmedFieldObservation) -> int:
    try:
        return int(observation.submitted_value)
    except (TypeError, ValueError):
        raise InvalidMintmarkEvaluationContextError(
            "validated mintmark evaluation state is malformed."
        ) from None


def _field_names(
    observations: tuple[_ConfirmedFieldObservation, ...],
    *,
    include_optional_specific: bool = True,
) -> tuple[str, ...]:
    if include_optional_specific:
        return tuple(sorted(observation.field_name for observation in observations))
    return tuple(
        sorted(
            observation.field_name
            for observation in observations
            if observation.field_name in _GENERIC_SCOPE_FIELDS
        )
    )


def _matched_finding(
    *,
    rule: _MintmarkRule,
    mintmark_observation: _ConfirmedFieldObservation,
    submitted_mintmark: str,
    source_fields: tuple[str, ...],
) -> _FieldIntelligenceFinding:
    try:
        declared = rule.mintmark
        observed = mintmark_observation.submitted_value
    except AttributeError:
        raise InvalidMintmarkEvaluationContextError(
            "validated mintmark evaluation state is malformed."
        ) from None
    allowed = declared == observed
    return _finding(
        rule_id=rule.rule_id,
        source_fields=source_fields,
        status=(
            _FieldIntelligenceStatus.VALID
            if allowed
            else _FieldIntelligenceStatus.INVALID
        ),
        diagnostic_code=(
            "MINTMARK_MATCH"
            if allowed
            else "MINTMARK_CONFLICT"
        ),
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
        raise InvalidMintmarkEvaluationContextError(
            "validated mintmark finding state is malformed."
        ) from None
    return result
