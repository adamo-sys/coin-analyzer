"""Pure evaluation of confirmed certification context.

The evaluator reads exact submitted values from an immutable confirmed
observation set and emits at most one transient field-intelligence finding. It
contains no persistence, readiness integration, default catalog, historical
numbering knowledge, normalization, or runtime side effects.
"""

from __future__ import annotations

from .workflow_confirmed_observation_certification_context_rules import (
    CertificationContextRule as _CertificationContextRule,
    CertificationContextRuleCatalog as _CertificationContextRuleCatalog,
    CertificationEvaluationContext as _CertificationEvaluationContext,
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
    "CertificationContextEvaluationError",
    "InvalidCertificationContextEvaluationContextError",
    "assess_certification_context",
]


_EVALUATOR_RULE_ID = "certification-context.evaluation-v1"
_RELEVANT_FIELDS = frozenset(
    {"country", "denomination", "series_type", "certification_number"}
)
_BASE_FIELDS = frozenset({"country", "denomination", "certification_number"})


class CertificationContextEvaluationError(ValueError):
    """A certification-context evaluation request is malformed."""

    __slots__ = ()

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            "Certification-context evaluation errors are immutable."
        )


class InvalidCertificationContextEvaluationContextError(
    CertificationContextEvaluationError
):
    """The source, catalog, or evaluation context cannot be safely evaluated."""


def assess_certification_context(
    source: _ConfirmedObservationSet,
    catalog: _CertificationContextRuleCatalog,
    evaluation_context: _CertificationEvaluationContext | None = None,
) -> _FieldIntelligenceFinding | None:
    """Assess exact submitted certification context against an exact rule catalog.

    ``None`` means the valid source contains none of the four relevant fields.
    Missing required evidence or explicit grading-company context produces
    conservative ``NOT_EVALUATED`` findings. A matched catalog rule yields
    ``VALID`` solely through the exact caller-supplied grading-company context
    and the exact submitted observation set. The evaluator never mutates the
    source, canonicalizes values, adds built-in grading-company facts, or
    persists anything.
    """

    _require_valid_source(source)
    _require_valid_catalog(catalog)
    if evaluation_context is not None:
        _require_valid_evaluation_context(evaluation_context)

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

    if evaluation_context is None or evaluation_context.grading_company is None:
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
        if rule.grading_company == evaluation_context.grading_company
        and rule.country == country
        and rule.denomination == denomination
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

    generic_rule = next(
        (rule for rule in matching_scope if rule.series_type is None),
        None,
    )
    if generic_rule is not None:
        return _matched_finding(
            rule=generic_rule,
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
            source_fields=_field_names(
                relevant,
                include_series_type=False,
            ),
            status=_FieldIntelligenceStatus.NOT_EVALUATED,
            diagnostic_code="RULE_COVERAGE_UNKNOWN",
        )

    return _matched_finding(
        rule=matched_rule,
        source_fields=_field_names(relevant),
    )


def _require_valid_source(value: object) -> _ConfirmedObservationSet:
    if not isinstance(value, _ConfirmedObservationSet):
        raise InvalidCertificationContextEvaluationContextError(
            "source must be a valid ConfirmedObservationSet."
        )
    try:
        _validate_confirmed_observation_set(value)
    except Exception:
        raise InvalidCertificationContextEvaluationContextError(
            "source must pass confirmed-observation validation."
        ) from None
    return value


def _require_valid_catalog(value: object) -> _CertificationContextRuleCatalog:
    if not isinstance(value, _CertificationContextRuleCatalog):
        raise InvalidCertificationContextEvaluationContextError(
            "catalog must be a valid CertificationContextRuleCatalog."
        )
    try:
        value.validate()
    except Exception:
        raise InvalidCertificationContextEvaluationContextError(
            "catalog must pass certification-context rule validation."
        ) from None
    return value


def _require_valid_evaluation_context(
    value: object,
) -> _CertificationEvaluationContext:
    if not isinstance(value, _CertificationEvaluationContext):
        raise InvalidCertificationContextEvaluationContextError(
            "evaluation_context must be a valid CertificationEvaluationContext."
        )
    try:
        value.validate()
    except Exception:
        raise InvalidCertificationContextEvaluationContextError(
            "evaluation_context must pass certification-context evaluation validation."
        ) from None
    return value


def _field_names(
    observations: tuple[_ConfirmedFieldObservation, ...],
    *,
    include_series_type: bool = True,
) -> tuple[str, ...]:
    if include_series_type:
        return tuple(sorted(observation.field_name for observation in observations))
    return tuple(
        sorted(
            observation.field_name
            for observation in observations
            if observation.field_name != "series_type"
        )
    )


def _matched_finding(
    *,
    rule: _CertificationContextRule,
    source_fields: tuple[str, ...],
) -> _FieldIntelligenceFinding:
    try:
        rule_id = rule.rule_id
    except AttributeError:
        raise InvalidCertificationContextEvaluationContextError(
            "validated certification-context evaluation state is malformed."
        ) from None
    return _finding(
        rule_id=rule_id,
        source_fields=source_fields,
        status=_FieldIntelligenceStatus.VALID,
        diagnostic_code="CERTIFICATION_CONTEXT_MATCH",
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
        raise InvalidCertificationContextEvaluationContextError(
            "validated certification-context finding state is malformed."
        ) from None
    return result
