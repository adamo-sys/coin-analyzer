"""Pure aggregate orchestration for confirmed-observation field intelligence.

The orchestrator invokes the five existing leaf evaluators over one exact
confirmed-observation set, removes only ``None`` results, and returns the
existing transient assessment contract. It owns no field policy, catalogs,
normalization, persistence, readiness authority, or runtime integration.
"""

from __future__ import annotations

from .workflow_confirmed_observation_certification_context_evaluator import (
    assess_certification_context as _assess_certification_context,
)
from .workflow_confirmed_observation_certification_context_rules import (
    CertificationContextRuleCatalog as _CertificationContextRuleCatalog,
    CertificationEvaluationContext as _CertificationEvaluationContext,
)
from .workflow_confirmed_observation_coin_year_evaluator import (
    assess_coin_specific_year as _assess_coin_specific_year,
)
from .workflow_confirmed_observation_coin_year_rules import (
    CoinYearRuleCatalog as _CoinYearRuleCatalog,
)
from .workflow_confirmed_observation_denomination_country_evaluator import (
    assess_denomination_country_compatibility as _assess_denomination_country_compatibility,
)
from .workflow_confirmed_observation_denomination_country_rules import (
    DenominationCountryRuleCatalog as _DenominationCountryRuleCatalog,
)
from .workflow_confirmed_observation_field_intelligence import (
    ConfirmedObservationFieldIntelligenceAssessment as _ConfirmedObservationFieldIntelligenceAssessment,
    FieldIntelligenceFinding as _FieldIntelligenceFinding,
    InvalidFieldIntelligenceContextError as _InvalidFieldIntelligenceContextError,
)
from .workflow_confirmed_observation_mintmark_evaluator import (
    assess_mintmark as _assess_mintmark,
)
from .workflow_confirmed_observation_mintmark_rules import (
    MintmarkRuleCatalog as _MintmarkRuleCatalog,
)
from .workflow_confirmed_observation_models import (
    ConfirmedObservationSet as _ConfirmedObservationSet,
)
from .workflow_confirmed_observation_monarch_year_evaluator import (
    assess_monarch_year_compatibility as _assess_monarch_year_compatibility,
)


__all__ = ["assess_confirmed_observation_field_intelligence"]


def assess_confirmed_observation_field_intelligence(
    source: _ConfirmedObservationSet,
    coin_year_catalog: _CoinYearRuleCatalog,
    denomination_country_catalog: _DenominationCountryRuleCatalog,
    mintmark_catalog: _MintmarkRuleCatalog,
    certification_context_catalog: _CertificationContextRuleCatalog,
    certification_evaluation_context: _CertificationEvaluationContext | None = None,
) -> _ConfirmedObservationFieldIntelligenceAssessment:
    """Return one deterministic assessment from all five leaf evaluators.

    Every leaf is invoked exactly once in the fixed ADR-009 sequence. Only
    exact ``None`` results are omitted. Existing leaf and assessment exceptions
    propagate unchanged, and no partial assessment is returned.
    """

    results = (
        _assess_coin_specific_year(source, coin_year_catalog),
        _assess_denomination_country_compatibility(
            source,
            denomination_country_catalog,
        ),
        _assess_monarch_year_compatibility(source),
        _assess_mintmark(source, mintmark_catalog),
        _assess_certification_context(
            source,
            certification_context_catalog,
            certification_evaluation_context,
        ),
    )

    findings: list[_FieldIntelligenceFinding] = []
    for result in results:
        if result is None:
            continue
        if not isinstance(result, _FieldIntelligenceFinding):
            raise _InvalidFieldIntelligenceContextError(
                "leaf evaluators must return FieldIntelligenceFinding or None."
            )
        result.validate()
        findings.append(result)

    ordered_findings = tuple(
        sorted(findings, key=lambda finding: finding.rule_id)
    )
    return _ConfirmedObservationFieldIntelligenceAssessment(
        source=source,
        findings=ordered_findings,
    )
