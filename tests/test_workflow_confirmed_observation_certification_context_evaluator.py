from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import inspect
from pathlib import Path
import unicodedata
import unittest

import capture_import.workflow_confirmed_observation_certification_context_evaluator as module
from capture_import.workflow_confirmed_observation_certification_context_evaluator import (
    CertificationContextEvaluationError,
    InvalidCertificationContextEvaluationContextError,
    assess_certification_context,
)
from capture_import.workflow_confirmed_observation_certification_context_rules import (
    CertificationContextRule,
    CertificationContextRuleCatalog,
    CertificationEvaluationContext,
)
from capture_import.workflow_confirmed_observation_field_intelligence import (
    FieldIntelligenceFinding,
    FieldIntelligenceStatus,
)
from capture_import.workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedFieldObservation,
    ConfirmedObservationSet,
    ConfirmedObservationSource,
)


PUBLIC_API = {
    "CertificationContextEvaluationError",
    "InvalidCertificationContextEvaluationContextError",
    "assess_certification_context",
}
RELEVANT_VALUES = {
    "country": "Canada",
    "denomination": "1 Cent",
    "series_type": "Series Alpha",
    "certification_number": "A1B2C3",
}


def observation(
    field_name: str,
    submitted_value: str,
    *,
    canonical_value: str | None = None,
) -> ConfirmedFieldObservation:
    return ConfirmedFieldObservation(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id="coin-1",
        field_name=field_name,
        submitted_value=submitted_value,
        canonical_value=canonical_value,
        reviewer_id="reviewer-1",
        provenance=(),
        source_type=ConfirmedObservationSource.MANUAL_ENTRY,
    )


def source(
    values: dict[str, str] | None = None,
    *,
    canonical_values: dict[str, str] | None = None,
) -> ConfirmedObservationSet:
    selected = values if values is not None else dict(RELEVANT_VALUES)
    canonicals = canonical_values or {}
    observations = tuple(
        sorted(
            (
                observation(
                    field_name,
                    submitted_value,
                    canonical_value=canonicals.get(field_name),
                )
                for field_name, submitted_value in selected.items()
            ),
            key=lambda item: item.field_name,
        )
    )
    return ConfirmedObservationSet(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id="coin-1",
        reviewer_id="reviewer-1",
        observations=observations,
        review_session_id="session-1",
        source_fingerprint="opaque fingerprint",
    )


def generic_catalog() -> CertificationContextRuleCatalog:
    return CertificationContextRuleCatalog(
        (
            CertificationContextRule(
                rule_id="certification-context.pcgs.canada.1-cent-v1",
                grading_company="PCGS",
                country="Canada",
                denomination="1 Cent",
                series_type=None,
            ),
        )
    )


def specific_catalog() -> CertificationContextRuleCatalog:
    return CertificationContextRuleCatalog(
        (
            CertificationContextRule(
                rule_id="certification-context.pcgs.canada.1-cent.alpha-v1",
                grading_company="PCGS",
                country="Canada",
                denomination="1 Cent",
                series_type="Series Alpha",
            ),
            CertificationContextRule(
                rule_id="certification-context.pcgs.canada.1-cent.beta-v1",
                grading_company="PCGS",
                country="Canada",
                denomination="1 Cent",
                series_type="Series Beta",
            ),
        )
    )


def evaluation_context(*, grading_company: str | None = "PCGS") -> CertificationEvaluationContext:
    return CertificationEvaluationContext(grading_company=grading_company)


class PublicAPITests(unittest.TestCase):
    def test_exact_exported_api(self) -> None:
        self.assertEqual(set(module.__all__), PUBLIC_API)

    def test_exact_module_defined_public_names(self) -> None:
        defined = {
            name
            for name, value in vars(module).items()
            if not name.startswith("_")
            and (
                inspect.isclass(value)
                or inspect.isfunction(value)
            )
            and getattr(value, "__module__", None) == module.__name__
        }
        self.assertEqual(defined, PUBLIC_API)

    def test_no_service_storage_or_readiness_api(self) -> None:
        prohibited = {
            "CertificationContextEvaluator",
            "default_catalog",
            "find_rule",
            "to_dict",
            "from_dict",
            "save",
            "load",
            "require_ready",
        }
        self.assertTrue(prohibited.isdisjoint(vars(module)))


class ErrorContractTests(unittest.TestCase):
    def test_exact_error_hierarchy(self) -> None:
        self.assertIs(CertificationContextEvaluationError.__base__, ValueError)
        self.assertIs(
            InvalidCertificationContextEvaluationContextError.__base__,
            CertificationContextEvaluationError,
        )

    def test_errors_are_immutable(self) -> None:
        error = InvalidCertificationContextEvaluationContextError("bounded")
        with self.assertRaises(AttributeError):
            error.detail = "changed"  # type: ignore[attr-defined]
        with self.assertRaises(AttributeError):
            error.args = ("changed",)

    def test_wrong_source_type_is_typed(self) -> None:
        with self.assertRaisesRegex(
            InvalidCertificationContextEvaluationContextError,
            "ConfirmedObservationSet",
        ):
            assess_certification_context(object(), generic_catalog())

    def test_wrong_catalog_type_is_typed(self) -> None:
        with self.assertRaisesRegex(
            InvalidCertificationContextEvaluationContextError,
            "CertificationContextRuleCatalog",
        ):
            assess_certification_context(source(), object())

    def test_wrong_evaluation_context_type_is_typed(self) -> None:
        with self.assertRaisesRegex(
            InvalidCertificationContextEvaluationContextError,
            "CertificationEvaluationContext",
        ):
            assess_certification_context(source(), generic_catalog(), object())

    def test_source_validation_precedes_catalog_validation(self) -> None:
        malformed = source({"certification_number": "private-invalid-value"})
        with self.assertRaisesRegex(
            InvalidCertificationContextEvaluationContextError,
            "confirmed-observation validation",
        ):
            assess_certification_context(malformed, object())

    def test_nested_validation_text_does_not_leak(self) -> None:
        malformed = source({"certification_number": "private-invalid-value"})
        with self.assertRaises(
            InvalidCertificationContextEvaluationContextError
        ) as captured:
            assess_certification_context(malformed, generic_catalog())
        self.assertNotIn("private-invalid-value", str(captured.exception))
        self.assertNotIn("grade-like", str(captured.exception))

    def test_field_invalid_source_values_are_typed(self) -> None:
        cases = (
            {"country": unicodedata.normalize("NFD", "Québec")},
            {"denomination": "unsupported token"},
            {"series_type": "Series\nAlpha"},
            {"certification_number": "private-invalid-value"},
        )
        for values in cases:
            with self.subTest(values=values):
                selected = dict(RELEVANT_VALUES)
                selected.update(values)
                with self.assertRaises(
                    InvalidCertificationContextEvaluationContextError
                ):
                    assess_certification_context(
                        source(selected),
                        generic_catalog(),
                        evaluation_context(),
                    )

    def test_forged_empty_source_is_typed(self) -> None:
        malformed = source()
        object.__setattr__(malformed, "observations", ())
        with self.assertRaises(InvalidCertificationContextEvaluationContextError):
            assess_certification_context(malformed, generic_catalog())

    def test_forged_nested_source_is_typed_without_attribute_error(self) -> None:
        malformed = source()
        object.__setattr__(malformed, "observations", (object(),))
        with self.assertRaises(InvalidCertificationContextEvaluationContextError):
            assess_certification_context(malformed, generic_catalog())


class EvaluationTests(unittest.TestCase):
    def test_no_relevant_evidence_returns_none(self) -> None:
        result = assess_certification_context(
            source({"year": "1901"}),
            generic_catalog(),
            evaluation_context(),
        )
        self.assertIsNone(result)

    def test_missing_required_evidence_returns_not_evaluated(self) -> None:
        result = assess_certification_context(
            source({"country": "Canada", "denomination": "1 Cent"}),
            generic_catalog(),
            evaluation_context(),
        )
        self.assertIsInstance(result, FieldIntelligenceFinding)
        self.assertEqual(result.status, FieldIntelligenceStatus.NOT_EVALUATED)
        self.assertEqual(result.diagnostic_code, "REQUIRED_CONTEXT_MISSING")

    def test_missing_evaluation_context_returns_not_evaluated(self) -> None:
        result = assess_certification_context(
            source(),
            generic_catalog(),
            evaluation_context(grading_company=None),
        )
        self.assertIsInstance(result, FieldIntelligenceFinding)
        self.assertEqual(result.status, FieldIntelligenceStatus.NOT_EVALUATED)
        self.assertEqual(result.diagnostic_code, "REQUIRED_CONTEXT_MISSING")

    def test_unknown_catalog_coverage_returns_not_evaluated(self) -> None:
        result = assess_certification_context(
            source(),
            generic_catalog(),
            evaluation_context(grading_company="NGC"),
        )
        self.assertIsInstance(result, FieldIntelligenceFinding)
        self.assertEqual(result.status, FieldIntelligenceStatus.NOT_EVALUATED)
        self.assertEqual(result.diagnostic_code, "RULE_COVERAGE_UNKNOWN")

    def test_generic_catalog_match_returns_valid(self) -> None:
        result = assess_certification_context(
            source(),
            generic_catalog(),
            evaluation_context(),
        )
        self.assertIsInstance(result, FieldIntelligenceFinding)
        self.assertEqual(result.status, FieldIntelligenceStatus.VALID)
        self.assertEqual(result.diagnostic_code, "CERTIFICATION_CONTEXT_MATCH")
        self.assertEqual(result.rule_id, "certification-context.pcgs.canada.1-cent-v1")

    def test_series_specific_catalog_match_returns_valid(self) -> None:
        result = assess_certification_context(
            source(),
            specific_catalog(),
            evaluation_context(),
        )
        self.assertIsInstance(result, FieldIntelligenceFinding)
        self.assertEqual(result.status, FieldIntelligenceStatus.VALID)
        self.assertEqual(result.diagnostic_code, "CERTIFICATION_CONTEXT_MATCH")
        self.assertEqual(
            result.rule_id,
            "certification-context.pcgs.canada.1-cent.alpha-v1",
        )

    def test_specific_catalog_without_series_type_returns_not_evaluated(self) -> None:
        result = assess_certification_context(
            source({
                "country": "Canada",
                "denomination": "1 Cent",
                "certification_number": "A1B2C3",
            }),
            specific_catalog(),
            evaluation_context(),
        )
        self.assertIsInstance(result, FieldIntelligenceFinding)
        self.assertEqual(result.status, FieldIntelligenceStatus.NOT_EVALUATED)
        self.assertEqual(result.diagnostic_code, "REQUIRED_CONTEXT_MISSING")

    def test_specific_catalog_unknown_series_type_returns_not_evaluated(self) -> None:
        result = assess_certification_context(
            source({
                "country": "Canada",
                "denomination": "1 Cent",
                "series_type": "Series Gamma",
                "certification_number": "A1B2C3",
            }),
            specific_catalog(),
            evaluation_context(),
        )
        self.assertIsInstance(result, FieldIntelligenceFinding)
        self.assertEqual(result.status, FieldIntelligenceStatus.NOT_EVALUATED)
        self.assertEqual(result.diagnostic_code, "RULE_COVERAGE_UNKNOWN")


if __name__ == "__main__":
    unittest.main()
