from __future__ import annotations

import ast
from contextlib import ExitStack, contextmanager
import inspect
from pathlib import Path
from typing import Iterator, get_type_hints
import unittest
from unittest.mock import Mock, patch

import capture_import
import capture_import.workflow_confirmed_observation_field_intelligence_orchestrator as module
from capture_import.workflow_confirmed_observation_certification_context_rules import (
    CertificationContextRule,
    CertificationContextRuleCatalog,
    CertificationEvaluationContext,
)
from capture_import.workflow_confirmed_observation_coin_year_evaluator import (
    InvalidCoinYearEvaluationContextError,
)
from capture_import.workflow_confirmed_observation_coin_year_rules import (
    CoinYearRule,
    CoinYearRuleCatalog,
)
from capture_import.workflow_confirmed_observation_denomination_country_rules import (
    DenominationCountryCompatibility,
    DenominationCountryRule,
    DenominationCountryRuleCatalog,
)
from capture_import.workflow_confirmed_observation_field_intelligence import (
    ConfirmedObservationFieldIntelligenceAssessment,
    DuplicateFieldIntelligenceFindingError,
    FieldIntelligenceFinding,
    FieldIntelligenceStatus,
    InvalidFieldIntelligenceContextError,
    MisalignedFieldIntelligenceFindingError,
)
from capture_import.workflow_confirmed_observation_field_intelligence_orchestrator import (
    assess_confirmed_observation_field_intelligence,
)
from capture_import.workflow_confirmed_observation_mintmark_rules import (
    MintmarkRule,
    MintmarkRuleCatalog,
)
from capture_import.workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedFieldObservation,
    ConfirmedObservationSet,
    ConfirmedObservationSource,
)


PUBLIC_API = {"assess_confirmed_observation_field_intelligence"}
LEAF_NAMES = (
    "_assess_coin_specific_year",
    "_assess_denomination_country_compatibility",
    "_assess_monarch_year_compatibility",
    "_assess_mintmark",
    "_assess_certification_context",
)
MODULE_PATH = (
    Path(__file__).parents[1]
    / "capture_import"
    / "workflow_confirmed_observation_field_intelligence_orchestrator.py"
)


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


def source(values: dict[str, str] | None = None) -> ConfirmedObservationSet:
    selected = values or {"country": "Exampleland"}
    return ConfirmedObservationSet(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id="coin-1",
        reviewer_id="reviewer-1",
        observations=tuple(
            sorted(
                (
                    observation(field_name, submitted_value)
                    for field_name, submitted_value in selected.items()
                ),
                key=lambda item: item.field_name,
            )
        ),
        review_session_id="session-1",
        source_fingerprint="opaque fingerprint",
    )


def coin_year_catalog() -> CoinYearRuleCatalog:
    return CoinYearRuleCatalog(
        (
            CoinYearRule(
                rule_id="coin-year.example.generic-v1",
                country="Exampleland",
                denomination="1 Cent",
                series_type=None,
                allowed_years=(1945,),
            ),
        )
    )


def denomination_country_catalog() -> DenominationCountryRuleCatalog:
    return DenominationCountryRuleCatalog(
        (
            DenominationCountryRule(
                rule_id="denomination-country.example.compatible-v1",
                country="Exampleland",
                denomination="1 Cent",
                compatibility=DenominationCountryCompatibility.COMPATIBLE,
            ),
        )
    )


def mintmark_catalog() -> MintmarkRuleCatalog:
    return MintmarkRuleCatalog(
        (
            MintmarkRule(
                rule_id="mintmark.example.generic-v1",
                country="Exampleland",
                denomination="1 Cent",
                series_type=None,
                year=None,
                monarch=None,
                mintmark="P",
            ),
        )
    )


def certification_catalog() -> CertificationContextRuleCatalog:
    return CertificationContextRuleCatalog(
        (
            CertificationContextRule(
                rule_id="certification-context.pcgs.example-v1",
                grading_company="PCGS",
                country="Exampleland",
                denomination="1 Cent",
                series_type=None,
            ),
        )
    )


def empty_catalogs() -> tuple[
    CoinYearRuleCatalog,
    DenominationCountryRuleCatalog,
    MintmarkRuleCatalog,
    CertificationContextRuleCatalog,
]:
    return (
        CoinYearRuleCatalog(()),
        DenominationCountryRuleCatalog(()),
        MintmarkRuleCatalog(()),
        CertificationContextRuleCatalog(()),
    )


def finding(
    rule_id: str,
    *,
    status: FieldIntelligenceStatus = FieldIntelligenceStatus.VALID,
    source_fields: tuple[str, ...] = ("country",),
    diagnostic_code: str = "MATCHED",
) -> FieldIntelligenceFinding:
    return FieldIntelligenceFinding(
        rule_id=rule_id,
        source_fields=source_fields,
        status=status,
        diagnostic_code=diagnostic_code,
    )


@contextmanager
def patched_leaf_results(
    results: tuple[object, object, object, object, object],
) -> Iterator[tuple[Mock, ...]]:
    with ExitStack() as stack:
        mocks = tuple(
            stack.enter_context(patch.object(module, name, return_value=result))
            for name, result in zip(LEAF_NAMES, results)
        )
        yield mocks


def call(
    selected_source: ConfirmedObservationSet | None = None,
    *,
    context: CertificationEvaluationContext | None = None,
) -> ConfirmedObservationFieldIntelligenceAssessment:
    coin, denomination, mintmark, certification = empty_catalogs()
    return assess_confirmed_observation_field_intelligence(
        selected_source or source(),
        coin,
        denomination,
        mintmark,
        certification,
        context,
    )


class PublicAPITests(unittest.TestCase):
    def test_exact_exported_and_module_defined_api(self) -> None:
        self.assertEqual(set(module.__all__), PUBLIC_API)
        defined = {
            name
            for name, value in vars(module).items()
            if not name.startswith("_")
            and (inspect.isclass(value) or inspect.isfunction(value))
            and getattr(value, "__module__", None) == module.__name__
        }
        self.assertEqual(defined, PUBLIC_API)

    def test_exact_function_signature_and_annotations(self) -> None:
        signature = inspect.signature(
            assess_confirmed_observation_field_intelligence
        )
        self.assertEqual(
            tuple(signature.parameters),
            (
                "source",
                "coin_year_catalog",
                "denomination_country_catalog",
                "mintmark_catalog",
                "certification_context_catalog",
                "certification_evaluation_context",
            ),
        )
        self.assertIs(
            signature.parameters["certification_evaluation_context"].default,
            None,
        )
        for name, parameter in signature.parameters.items():
            if name != "certification_evaluation_context":
                self.assertIs(parameter.default, inspect.Parameter.empty)

        hints = get_type_hints(
            assess_confirmed_observation_field_intelligence
        )
        self.assertEqual(
            hints,
            {
                "source": ConfirmedObservationSet,
                "coin_year_catalog": CoinYearRuleCatalog,
                "denomination_country_catalog": (
                    DenominationCountryRuleCatalog
                ),
                "mintmark_catalog": MintmarkRuleCatalog,
                "certification_context_catalog": (
                    CertificationContextRuleCatalog
                ),
                "certification_evaluation_context": (
                    CertificationEvaluationContext | None
                ),
                "return": ConfirmedObservationFieldIntelligenceAssessment,
            },
        )

    def test_no_package_root_export_or_expanded_public_surface(self) -> None:
        self.assertFalse(
            hasattr(
                capture_import,
                "assess_confirmed_observation_field_intelligence",
            )
        )
        prohibited = {
            "AggregateEvaluator",
            "EvaluationContext",
            "default_catalog",
            "registry",
            "to_dict",
            "from_dict",
            "save",
            "load",
            "require_ready",
        }
        self.assertTrue(prohibited.isdisjoint(vars(module)))


class InvocationContractTests(unittest.TestCase):
    def test_invokes_all_leaves_once_with_exact_inputs(self) -> None:
        selected_source = source()
        coin = CoinYearRuleCatalog(())
        denomination = DenominationCountryRuleCatalog(())
        mintmark = MintmarkRuleCatalog(())
        certification = CertificationContextRuleCatalog(())
        context = CertificationEvaluationContext(grading_company="PCGS")

        with patched_leaf_results((None, None, None, None, None)) as mocks:
            result = assess_confirmed_observation_field_intelligence(
                selected_source,
                coin,
                denomination,
                mintmark,
                certification,
                context,
            )

        mocks[0].assert_called_once_with(selected_source, coin)
        mocks[1].assert_called_once_with(selected_source, denomination)
        mocks[2].assert_called_once_with(selected_source)
        mocks[3].assert_called_once_with(selected_source, mintmark)
        mocks[4].assert_called_once_with(
            selected_source,
            certification,
            context,
        )
        self.assertIs(result.source, selected_source)

    def test_invocation_order_is_fixed(self) -> None:
        events: list[str] = []

        def effect(name: str):
            def invoke(*args: object) -> None:
                events.append(name)
                return None

            return invoke

        with ExitStack() as stack:
            for name in LEAF_NAMES:
                stack.enter_context(
                    patch.object(module, name, side_effect=effect(name))
                )
            call()

        self.assertEqual(list(LEAF_NAMES), events)

    def test_none_context_and_empty_catalogs_are_forwarded(self) -> None:
        selected_source = source()
        coin, denomination, mintmark, certification = empty_catalogs()
        with patched_leaf_results((None, None, None, None, None)) as mocks:
            assess_confirmed_observation_field_intelligence(
                selected_source,
                coin,
                denomination,
                mintmark,
                certification,
            )
        mocks[4].assert_called_once_with(
            selected_source,
            certification,
            None,
        )

    def test_absent_relevant_evidence_does_not_skip_leaves(self) -> None:
        selected_source = source({"silver_indicator": "yes"})
        with patched_leaf_results((None, None, None, None, None)) as mocks:
            result = call(selected_source)
        self.assertEqual(result.findings, ())
        self.assertTrue(all(mock.call_count == 1 for mock in mocks))

    def test_leaf_failure_propagates_unchanged_and_stops_later_leaves(self) -> None:
        error = InvalidCoinYearEvaluationContextError("bounded")
        with ExitStack() as stack:
            mocks = tuple(
                stack.enter_context(patch.object(module, name))
                for name in LEAF_NAMES
            )
            mocks[0].side_effect = error
            with self.assertRaises(InvalidCoinYearEvaluationContextError) as raised:
                call()

        self.assertIs(raised.exception, error)
        self.assertEqual(mocks[0].call_count, 1)
        self.assertTrue(all(mock.call_count == 0 for mock in mocks[1:]))


class OmissionOrderingAndIdentityTests(unittest.TestCase):
    def test_all_none_results_produce_empty_assessment(self) -> None:
        selected_source = source()
        with patched_leaf_results((None, None, None, None, None)):
            result = call(selected_source)
        self.assertIs(result.source, selected_source)
        self.assertEqual(result.findings, ())

    def test_every_none_finding_combination_omits_only_none(self) -> None:
        items = tuple(
            finding(f"rule-{index}")
            for index in range(5)
        )
        for mask in range(32):
            with self.subTest(mask=mask):
                results = tuple(
                    item if mask & (1 << index) else None
                    for index, item in enumerate(items)
                )
                with patched_leaf_results(results):
                    assessment = call()
                expected = tuple(
                    item
                    for index, item in enumerate(items)
                    if mask & (1 << index)
                )
                self.assertEqual(assessment.findings, expected)
                self.assertTrue(
                    all(
                        actual is selected
                        for actual, selected in zip(
                            assessment.findings,
                            expected,
                        )
                    )
                )

    def test_findings_are_sorted_only_by_lexical_rule_id(self) -> None:
        zulu = finding(
            "zulu-rule",
            status=FieldIntelligenceStatus.INVALID,
            diagnostic_code="INVALID",
        )
        alpha = finding(
            "alpha-rule",
            status=FieldIntelligenceStatus.NOT_EVALUATED,
            diagnostic_code="UNKNOWN",
        )
        middle = finding("middle-rule")
        with patched_leaf_results((zulu, None, alpha, middle, None)):
            result = call()
        self.assertEqual(
            result.rule_ids,
            ("alpha-rule", "middle-rule", "zulu-rule"),
        )
        self.assertIs(result.findings[0], alpha)
        self.assertIs(result.findings[1], middle)
        self.assertIs(result.findings[2], zulu)

    def test_wrong_leaf_result_type_fails_before_sorting(self) -> None:
        with patched_leaf_results((object(), None, None, None, None)) as mocks:
            with self.assertRaisesRegex(
                InvalidFieldIntelligenceContextError,
                "leaf evaluators must return",
            ):
                call()
        self.assertTrue(all(mock.call_count == 1 for mock in mocks))

    def test_malformed_finding_is_revalidated(self) -> None:
        malformed = finding("malformed-rule")
        object.__setattr__(malformed, "status", "VALID")
        with patched_leaf_results((malformed, None, None, None, None)):
            with self.assertRaises(InvalidFieldIntelligenceContextError):
                call()

    def test_duplicate_rule_ids_fail_without_overwrite(self) -> None:
        first = finding("duplicate-rule")
        second = finding("duplicate-rule", diagnostic_code="ALSO_MATCHED")
        with patched_leaf_results((first, second, None, None, None)):
            with self.assertRaises(DuplicateFieldIntelligenceFindingError):
                call()

    def test_source_field_misalignment_uses_assessment_error(self) -> None:
        selected_source = source({"country": "Exampleland"})
        misaligned = finding(
            "misaligned-rule",
            source_fields=("year",),
        )
        with patched_leaf_results((misaligned, None, None, None, None)):
            with self.assertRaises(MisalignedFieldIntelligenceFindingError):
                call(selected_source)


class SourceAndResultGuaranteeTests(unittest.TestCase):
    def test_inputs_are_not_mutated_and_source_identity_is_retained(self) -> None:
        selected_source = source()
        coin = coin_year_catalog()
        denomination = denomination_country_catalog()
        mintmark = mintmark_catalog()
        certification = certification_catalog()
        context = CertificationEvaluationContext(grading_company="PCGS")
        source_before = selected_source.to_dict()
        identities_before = (
            coin.rules,
            denomination.rules,
            mintmark.rules,
            certification.rules,
            context.grading_company,
        )

        with patched_leaf_results((None, None, None, None, None)):
            result = assess_confirmed_observation_field_intelligence(
                selected_source,
                coin,
                denomination,
                mintmark,
                certification,
                context,
            )

        self.assertIs(result.source, selected_source)
        self.assertEqual(selected_source.to_dict(), source_before)
        self.assertIs(coin.rules, identities_before[0])
        self.assertIs(denomination.rules, identities_before[1])
        self.assertIs(mintmark.rules, identities_before[2])
        self.assertIs(certification.rules, identities_before[3])
        self.assertEqual(context.grading_company, identities_before[4])

    def test_assessment_retains_no_catalog_context_or_value_copies(self) -> None:
        selected_finding = finding("retained-rule")
        with patched_leaf_results(
            (selected_finding, None, None, None, None)
        ):
            result = call()
        self.assertEqual(set(result.__slots__), {"source", "findings"})
        self.assertIs(result.findings[0], selected_finding)
        self.assertEqual(
            set(selected_finding.__slots__),
            {"rule_id", "source_fields", "status", "diagnostic_code"},
        )

    def test_repeated_real_evaluation_is_deterministic(self) -> None:
        selected_source = full_source()
        context = CertificationEvaluationContext(grading_company="PCGS")
        args = (
            selected_source,
            coin_year_catalog(),
            denomination_country_catalog(),
            mintmark_catalog(),
            certification_catalog(),
            context,
        )
        first = assess_confirmed_observation_field_intelligence(*args)
        second = assess_confirmed_observation_field_intelligence(*args)
        self.assertEqual(first, second)
        self.assertIs(first.source, selected_source)
        self.assertIs(second.source, selected_source)


def full_source() -> ConfirmedObservationSet:
    return source(
        {
            "certification_number": "A1B2C3",
            "country": "Exampleland",
            "denomination": "1 Cent",
            "mintmark": "P",
            "monarch": "George VI",
            "series_type": "Series Alpha",
            "year": "1945",
        }
    )


class RealLeafIntegrationTests(unittest.TestCase):
    def test_all_real_leaves_produce_one_lexically_ordered_assessment(self) -> None:
        selected_source = full_source()
        result = assess_confirmed_observation_field_intelligence(
            selected_source,
            coin_year_catalog(),
            denomination_country_catalog(),
            mintmark_catalog(),
            certification_catalog(),
            CertificationEvaluationContext(grading_company="PCGS"),
        )
        self.assertIs(result.source, selected_source)
        self.assertEqual(
            result.rule_ids,
            (
                "certification-context.pcgs.example-v1",
                "coin-year.example.generic-v1",
                "denomination-country.example.compatible-v1",
                "mintmark.example.generic-v1",
                "monarch-year.evaluation-v1",
            ),
        )
        self.assertTrue(
            all(
                item.status is FieldIntelligenceStatus.VALID
                for item in result.findings
            )
        )

    def test_unrelated_only_real_source_produces_empty_assessment(self) -> None:
        selected_source = source({"silver_indicator": "yes"})
        coin, denomination, mintmark, certification = empty_catalogs()
        result = assess_confirmed_observation_field_intelligence(
            selected_source,
            coin,
            denomination,
            mintmark,
            certification,
        )
        self.assertIs(result.source, selected_source)
        self.assertEqual(result.findings, ())

    def test_empty_catalogs_preserve_not_evaluated_outcomes(self) -> None:
        coin, denomination, mintmark, certification = empty_catalogs()
        result = assess_confirmed_observation_field_intelligence(
            full_source(),
            coin,
            denomination,
            mintmark,
            certification,
            CertificationEvaluationContext(grading_company="PCGS"),
        )
        self.assertEqual(len(result.findings), 5)
        self.assertEqual(len(result.not_evaluated_findings), 4)
        self.assertEqual(len(result.valid_findings), 1)
        self.assertEqual(result.invalid_findings, ())

    def test_real_leaf_validation_error_propagates(self) -> None:
        malformed = full_source()
        object.__setattr__(malformed.observations[0], "submitted_value", "")
        coin, denomination, mintmark, certification = empty_catalogs()
        with self.assertRaises(InvalidCoinYearEvaluationContextError):
            assess_confirmed_observation_field_intelligence(
                malformed,
                coin,
                denomination,
                mintmark,
                certification,
            )


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_imports_are_exact_and_bounded(self) -> None:
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        self.assertEqual(
            imports,
            {
                "__future__",
                "workflow_confirmed_observation_certification_context_evaluator",
                "workflow_confirmed_observation_certification_context_rules",
                "workflow_confirmed_observation_coin_year_evaluator",
                "workflow_confirmed_observation_coin_year_rules",
                "workflow_confirmed_observation_denomination_country_evaluator",
                "workflow_confirmed_observation_denomination_country_rules",
                "workflow_confirmed_observation_field_intelligence",
                "workflow_confirmed_observation_mintmark_evaluator",
                "workflow_confirmed_observation_mintmark_rules",
                "workflow_confirmed_observation_models",
                "workflow_confirmed_observation_monarch_year_evaluator",
            },
        )

    def test_no_forbidden_runtime_or_authority_imports(self) -> None:
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported = {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        }
        forbidden = (
            "readiness",
            "collection",
            "mutation",
            "persistence",
            "ocr",
            "gui",
            "desktop",
            "pathlib",
            "os",
            "datetime",
            "uuid",
            "random",
            "logging",
        )
        self.assertFalse(
            any(token in name.casefold() for name in imported for token in forbidden)
        )

    def test_source_contains_no_registry_defaults_io_or_policy_data(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        prohibited = (
            "open(",
            "Path(",
            "default_catalog",
            "registry",
            "requests.",
            "http",
            "to_dict",
            "from_dict",
            "normalize(",
            "casefold(",
        )
        self.assertTrue(all(token not in text for token in prohibited))


if __name__ == "__main__":
    unittest.main()
