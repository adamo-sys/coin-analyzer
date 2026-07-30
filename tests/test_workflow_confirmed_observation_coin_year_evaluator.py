from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import inspect
from itertools import combinations
from pathlib import Path
import unicodedata
import unittest

import capture_import.workflow_confirmed_observation_coin_year_evaluator as module
from capture_import.workflow_confirmed_observation_coin_year_evaluator import (
    CoinYearEvaluationError,
    InvalidCoinYearEvaluationContextError,
    assess_coin_specific_year,
)
from capture_import.workflow_confirmed_observation_coin_year_rules import (
    CoinYearRule,
    CoinYearRuleCatalog,
)
from capture_import.workflow_confirmed_observation_field_intelligence import (
    ConfirmedObservationFieldIntelligenceAssessment,
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
    "CoinYearEvaluationError",
    "InvalidCoinYearEvaluationContextError",
    "assess_coin_specific_year",
}
RELEVANT_VALUES = {
    "country": "Exampleland",
    "denomination": "1 Cent",
    "series_type": "Series Alpha",
    "year": "1901",
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


def generic_catalog(
    *,
    country: str = "Exampleland",
    denomination: str = "1 Cent",
    allowed_years: tuple[int, ...] = (1901, 1902, 1904),
) -> CoinYearRuleCatalog:
    return CoinYearRuleCatalog(
        (
            CoinYearRule(
                rule_id="coin-year.example.generic-v1",
                country=country,
                denomination=denomination,
                series_type=None,
                allowed_years=allowed_years,
            ),
        )
    )


def specific_catalog() -> CoinYearRuleCatalog:
    return CoinYearRuleCatalog(
        (
            CoinYearRule(
                rule_id="coin-year.example.alpha-v1",
                country="Exampleland",
                denomination="1 Cent",
                series_type="Series Alpha",
                allowed_years=(1901, 1903, 1904),
            ),
            CoinYearRule(
                rule_id="coin-year.example.beta-v1",
                country="Exampleland",
                denomination="1 Cent",
                series_type="Series Beta",
                allowed_years=(1902, 1905),
            ),
        )
    )


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
            "CoinYearEvaluator",
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
        self.assertIs(CoinYearEvaluationError.__base__, ValueError)
        self.assertIs(
            InvalidCoinYearEvaluationContextError.__base__,
            CoinYearEvaluationError,
        )

    def test_errors_are_immutable(self) -> None:
        error = InvalidCoinYearEvaluationContextError("bounded")
        with self.assertRaises(AttributeError):
            error.detail = "changed"  # type: ignore[attr-defined]
        with self.assertRaises(AttributeError):
            error.args = ("changed",)

    def test_wrong_source_type_is_typed(self) -> None:
        with self.assertRaisesRegex(
            InvalidCoinYearEvaluationContextError,
            "ConfirmedObservationSet",
        ):
            assess_coin_specific_year(object(), generic_catalog())

    def test_wrong_catalog_type_is_typed(self) -> None:
        with self.assertRaisesRegex(
            InvalidCoinYearEvaluationContextError,
            "CoinYearRuleCatalog",
        ):
            assess_coin_specific_year(source(), object())

    def test_source_validation_precedes_catalog_validation(self) -> None:
        cases = (
            (source({"year": "19x1"}), CoinYearRuleCatalog(())),
            (source({"year": "19x1"}), generic_catalog()),
            (source({"year": "19x1"}), object()),
            (
                source({"monarch": "Example\nMonarch"}),
                CoinYearRuleCatalog(()),
            ),
        )
        for malformed, catalog in cases:
            with self.subTest(catalog_type=type(catalog).__name__):
                with self.assertRaisesRegex(
                    InvalidCoinYearEvaluationContextError,
                    "confirmed-observation validation",
                ):
                    assess_coin_specific_year(malformed, catalog)

    def test_nested_validation_text_does_not_leak(self) -> None:
        malformed = source({"year": "private-invalid-value"})
        with self.assertRaises(
            InvalidCoinYearEvaluationContextError
        ) as captured:
            assess_coin_specific_year(malformed, generic_catalog())
        self.assertNotIn("private-invalid-value", str(captured.exception))
        self.assertNotIn("four decimal", str(captured.exception))

    def test_field_invalid_source_values_are_typed(self) -> None:
        cases = (
            {"year": "190A"},
            {"country": unicodedata.normalize("NFD", "Québec")},
            {"denomination": "unsupported token"},
            {"series_type": "Series\nAlpha"},
        )
        for values in cases:
            with self.subTest(values=values):
                selected = dict(RELEVANT_VALUES)
                selected.update(values)
                with self.assertRaises(
                    InvalidCoinYearEvaluationContextError
                ):
                    assess_coin_specific_year(
                        source(selected),
                        generic_catalog(),
                    )

    def test_forged_empty_source_is_typed(self) -> None:
        malformed = source()
        object.__setattr__(malformed, "observations", ())
        with self.assertRaises(InvalidCoinYearEvaluationContextError):
            assess_coin_specific_year(malformed, generic_catalog())

    def test_forged_nested_source_is_typed_without_attribute_error(self) -> None:
        malformed = source()
        object.__setattr__(malformed, "observations", (object(),))
        with self.assertRaises(InvalidCoinYearEvaluationContextError):
            assess_coin_specific_year(malformed, generic_catalog())

    def test_forged_catalog_is_typed(self) -> None:
        malformed = object.__new__(CoinYearRuleCatalog)
        object.__setattr__(malformed, "rules", [])
        with self.assertRaisesRegex(
            InvalidCoinYearEvaluationContextError,
            "coin-year rule validation",
        ):
            assess_coin_specific_year(source(), malformed)


class NoneAndPartialContextTests(unittest.TestCase):
    def test_returns_none_for_only_unrelated_fields(self) -> None:
        value = source(
            {
                "monarch": "Example Monarch",
                "mintmark": "P",
            }
        )
        self.assertIsNone(
            assess_coin_specific_year(value, generic_catalog())
        )

    def test_returns_none_before_catalog_coverage_matters(self) -> None:
        value = source({"monarch": "Example Monarch"})
        self.assertIsNone(
            assess_coin_specific_year(value, CoinYearRuleCatalog(()))
        )

    def test_every_partial_relevant_subset_reports_present_fields(self) -> None:
        relevant = tuple(RELEVANT_VALUES)
        for size in range(1, len(relevant) + 1):
            for names in combinations(relevant, size):
                if {"country", "denomination", "year"}.issubset(names):
                    continue
                values = {
                    name: RELEVANT_VALUES[name]
                    for name in names
                }
                with self.subTest(names=names):
                    result = assess_coin_specific_year(
                        source(values),
                        generic_catalog(),
                    )
                    self.assertIsInstance(
                        result,
                        FieldIntelligenceFinding,
                    )
                    self.assertIs(
                        result.status,
                        FieldIntelligenceStatus.NOT_EVALUATED,
                    )
                    self.assertEqual(
                        result.diagnostic_code,
                        "REQUIRED_CONTEXT_MISSING",
                    )
                    self.assertEqual(
                        result.rule_id,
                        "coin-year.evaluation-v1",
                    )
                    self.assertEqual(
                        result.source_fields,
                        tuple(sorted(names)),
                    )

    def test_partial_context_ignores_unrelated_fields(self) -> None:
        result = assess_coin_specific_year(
            source(
                {
                    "country": "Exampleland",
                    "monarch": "Example Monarch",
                    "silver_indicator": "yes",
                }
            ),
            generic_catalog(),
        )
        self.assertEqual(result.source_fields, ("country",))


class NoCoverageTests(unittest.TestCase):
    def assert_no_coverage(
        self,
        values: dict[str, str],
        catalog: CoinYearRuleCatalog,
    ) -> None:
        result = assess_coin_specific_year(source(values), catalog)
        self.assertIs(result.status, FieldIntelligenceStatus.NOT_EVALUATED)
        self.assertEqual(result.diagnostic_code, "RULE_COVERAGE_UNKNOWN")
        self.assertEqual(result.rule_id, "coin-year.evaluation-v1")
        self.assertEqual(
            result.source_fields,
            ("country", "denomination", "year"),
        )

    def test_empty_catalog_is_unknown_coverage(self) -> None:
        self.assert_no_coverage(
            {
                "country": "Exampleland",
                "denomination": "1 Cent",
                "year": "1901",
            },
            CoinYearRuleCatalog(()),
        )

    def test_unsupported_country_is_unknown_coverage(self) -> None:
        values = dict(RELEVANT_VALUES)
        values["country"] = "Otherland"
        self.assert_no_coverage(values, generic_catalog())

    def test_unsupported_denomination_is_unknown_coverage(self) -> None:
        values = dict(RELEVANT_VALUES)
        values["denomination"] = "5 Cents"
        self.assert_no_coverage(values, generic_catalog())

    def test_exact_case_mismatch_is_unknown_coverage(self) -> None:
        for field_name, replacement in (
            ("country", "exampleland"),
            ("denomination", "1 cent"),
        ):
            values = dict(RELEVANT_VALUES)
            values[field_name] = replacement
            with self.subTest(field_name=field_name):
                self.assert_no_coverage(values, generic_catalog())

    def test_padded_country_is_not_trimmed(self) -> None:
        values = dict(RELEVANT_VALUES)
        values["country"] = " Exampleland"
        self.assert_no_coverage(values, generic_catalog())

    def test_series_is_excluded_when_pair_has_no_coverage(self) -> None:
        values = dict(RELEVANT_VALUES)
        values["country"] = "Otherland"
        self.assert_no_coverage(values, generic_catalog())


class GenericRuleTests(unittest.TestCase):
    def test_allowed_year_is_valid(self) -> None:
        result = assess_coin_specific_year(
            source(
                {
                    "country": "Exampleland",
                    "denomination": "1 Cent",
                    "year": "1901",
                }
            ),
            generic_catalog(),
        )
        self.assertIs(result.status, FieldIntelligenceStatus.VALID)
        self.assertEqual(result.diagnostic_code, "YEAR_ALLOWED")
        self.assertEqual(
            result.rule_id,
            "coin-year.example.generic-v1",
        )
        self.assertEqual(
            result.source_fields,
            ("country", "denomination", "year"),
        )

    def test_source_series_type_is_ignored(self) -> None:
        result = assess_coin_specific_year(
            source(),
            generic_catalog(),
        )
        self.assertIs(result.status, FieldIntelligenceStatus.VALID)
        self.assertNotIn("series_type", result.source_fields)

    def test_unrelated_fields_are_ignored(self) -> None:
        values = dict(RELEVANT_VALUES)
        values["monarch"] = "Example Monarch"
        result = assess_coin_specific_year(
            source(values),
            generic_catalog(),
        )
        self.assertEqual(
            result.source_fields,
            ("country", "denomination", "year"),
        )

    def test_gap_year_is_invalid_without_range_inference(self) -> None:
        values = dict(RELEVANT_VALUES)
        values["year"] = "1903"
        result = assess_coin_specific_year(
            source(values),
            generic_catalog(),
        )
        self.assertIs(result.status, FieldIntelligenceStatus.INVALID)
        self.assertEqual(
            result.diagnostic_code,
            "YEAR_OUTSIDE_DECLARED_SET",
        )

    def test_before_and_after_declared_years_are_invalid(self) -> None:
        for year in ("1900", "1905"):
            values = dict(RELEVANT_VALUES)
            values["year"] = year
            with self.subTest(year=year):
                result = assess_coin_specific_year(
                    source(values),
                    generic_catalog(),
                )
                self.assertIs(
                    result.status,
                    FieldIntelligenceStatus.INVALID,
                )

    def test_each_exact_allowed_year_is_valid(self) -> None:
        for year in ("1901", "1902", "1904"):
            values = dict(RELEVANT_VALUES)
            values["year"] = year
            with self.subTest(year=year):
                result = assess_coin_specific_year(
                    source(values),
                    generic_catalog(),
                )
                self.assertIs(
                    result.status,
                    FieldIntelligenceStatus.VALID,
                )

    def test_structural_year_bounds_use_exact_membership(self) -> None:
        catalog = generic_catalog(allowed_years=(1000, 2999))
        for year in ("1000", "2999"):
            values = dict(RELEVANT_VALUES)
            values["year"] = year
            with self.subTest(year=year):
                self.assertIs(
                    assess_coin_specific_year(
                        source(values),
                        catalog,
                    ).status,
                    FieldIntelligenceStatus.VALID,
                )
        values = dict(RELEVANT_VALUES)
        values["year"] = "2000"
        self.assertIs(
            assess_coin_specific_year(source(values), catalog).status,
            FieldIntelligenceStatus.INVALID,
        )


class SpecificRuleTests(unittest.TestCase):
    def test_exact_series_rule_matches(self) -> None:
        result = assess_coin_specific_year(
            source(),
            specific_catalog(),
        )
        self.assertIs(result.status, FieldIntelligenceStatus.VALID)
        self.assertEqual(result.diagnostic_code, "YEAR_ALLOWED")
        self.assertEqual(
            result.rule_id,
            "coin-year.example.alpha-v1",
        )
        self.assertEqual(
            result.source_fields,
            ("country", "denomination", "series_type", "year"),
        )

    def test_selects_one_of_multiple_specific_rules(self) -> None:
        catalog = CoinYearRuleCatalog(
            (
                CoinYearRule(
                    "coin-year.example.alpha-v1",
                    "Exampleland",
                    "1 Cent",
                    "Series Alpha",
                    (1901,),
                ),
                CoinYearRule(
                    "coin-year.example.beta-v1",
                    "Exampleland",
                    "1 Cent",
                    "Series Beta",
                    (1902,),
                ),
                CoinYearRule(
                    "coin-year.example.gamma-v1",
                    "Exampleland",
                    "1 Cent",
                    "Series Gamma",
                    (1903,),
                ),
            )
        )
        for suffix, year in (
            ("alpha", "1901"),
            ("beta", "1902"),
            ("gamma", "1903"),
        ):
            values = dict(RELEVANT_VALUES)
            values["series_type"] = f"Series {suffix.title()}"
            values["year"] = year
            with self.subTest(suffix=suffix):
                result = assess_coin_specific_year(
                    source(values),
                    catalog,
                )
                self.assertEqual(
                    result.rule_id,
                    f"coin-year.example.{suffix}-v1",
                )
                self.assertIs(
                    result.status,
                    FieldIntelligenceStatus.VALID,
                )

    def test_missing_series_type_is_required_context(self) -> None:
        values = {
            key: value
            for key, value in RELEVANT_VALUES.items()
            if key != "series_type"
        }
        result = assess_coin_specific_year(
            source(values),
            specific_catalog(),
        )
        self.assertIs(
            result.status,
            FieldIntelligenceStatus.NOT_EVALUATED,
        )
        self.assertEqual(
            result.diagnostic_code,
            "REQUIRED_CONTEXT_MISSING",
        )
        self.assertEqual(
            result.source_fields,
            ("country", "denomination", "year"),
        )

    def test_unknown_and_case_mismatched_series_are_not_covered(self) -> None:
        for series_type in ("Series Gamma", "series alpha"):
            values = dict(RELEVANT_VALUES)
            values["series_type"] = series_type
            with self.subTest(series_type=series_type):
                result = assess_coin_specific_year(
                    source(values),
                    specific_catalog(),
                )
                self.assertIs(
                    result.status,
                    FieldIntelligenceStatus.NOT_EVALUATED,
                )
                self.assertEqual(
                    result.diagnostic_code,
                    "RULE_COVERAGE_UNKNOWN",
                )
                self.assertEqual(
                    result.source_fields,
                    (
                        "country",
                        "denomination",
                        "series_type",
                        "year",
                    ),
                )

    def test_specific_gap_and_outside_years_are_invalid(self) -> None:
        for year in ("1900", "1902", "1905"):
            values = dict(RELEVANT_VALUES)
            values["year"] = year
            with self.subTest(year=year):
                result = assess_coin_specific_year(
                    source(values),
                    specific_catalog(),
                )
                self.assertIs(
                    result.status,
                    FieldIntelligenceStatus.INVALID,
                )
                self.assertEqual(
                    result.rule_id,
                    "coin-year.example.alpha-v1",
                )


class ValueAndFindingTests(unittest.TestCase):
    def test_uses_submitted_values_and_ignores_canonical_values(self) -> None:
        result = assess_coin_specific_year(
            source(
                dict(RELEVANT_VALUES),
                canonical_values={
                    "country": "Otherland",
                    "denomination": "5 Cents",
                    "series_type": "Series Beta",
                    "year": "2999",
                },
            ),
            generic_catalog(),
        )
        self.assertIs(result.status, FieldIntelligenceStatus.VALID)
        self.assertEqual(
            result.rule_id,
            "coin-year.example.generic-v1",
        )

    def test_emitted_finding_is_accepted_by_unit_1a_assessment(self) -> None:
        cases = (
            (source(), generic_catalog()),
            (
                source(
                    {
                        **RELEVANT_VALUES,
                        "year": "1903",
                    }
                ),
                generic_catalog(),
            ),
            (source({"country": "Exampleland"}), generic_catalog()),
            (
                source(
                    {
                        **RELEVANT_VALUES,
                        "country": "Otherland",
                    }
                ),
                generic_catalog(),
            ),
        )
        for selected_source, catalog in cases:
            with self.subTest(
                source_fields=tuple(
                    item.field_name
                    for item in selected_source.observations
                )
            ):
                finding = assess_coin_specific_year(
                    selected_source,
                    catalog,
                )
                assessment = (
                    ConfirmedObservationFieldIntelligenceAssessment(
                        source=selected_source,
                        findings=(finding,),
                    )
                )
                self.assertIs(assessment.findings[0], finding)

    def test_repeated_evaluation_is_deterministic(self) -> None:
        selected_source = source()
        catalog = specific_catalog()
        first = assess_coin_specific_year(selected_source, catalog)
        second = assess_coin_specific_year(selected_source, catalog)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)

    def test_evaluation_does_not_mutate_inputs(self) -> None:
        selected_source = source()
        catalog = specific_catalog()
        source_before = selected_source.to_dict()
        catalog_rules = catalog.rules
        rule_ids = catalog.rule_ids
        assess_coin_specific_year(selected_source, catalog)
        self.assertEqual(selected_source.to_dict(), source_before)
        self.assertIs(catalog.rules, catalog_rules)
        self.assertEqual(catalog.rule_ids, rule_ids)
        for actual, expected in zip(
            catalog.rules,
            catalog_rules,
            strict=True,
        ):
            self.assertIs(actual, expected)

    def test_finding_contains_no_values_or_source_objects(self) -> None:
        result = assess_coin_specific_year(source(), generic_catalog())
        self.assertEqual(
            set(result.__slots__),
            {"rule_id", "source_fields", "status", "diagnostic_code"},
        )
        self.assertFalse(hasattr(result, "source"))
        self.assertFalse(hasattr(result, "catalog"))
        self.assertFalse(hasattr(result, "rule"))


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_imports_are_exact_and_bounded(self) -> None:
        source_text = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source_text)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        from_imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        self.assertEqual(imports, set())
        self.assertEqual(
            from_imports,
            {
                "__future__",
                "workflow_confirmed_observation_coin_year_rules",
                "workflow_confirmed_observation_field_intelligence",
                "workflow_confirmed_observation_models",
                "workflow_confirmed_observation_validators",
            },
        )

    def test_no_forbidden_runtime_or_history_imports(self) -> None:
        source_text = Path(module.__file__).read_text(encoding="utf-8")
        prohibited = (
            "compatibility",
            "canonicalization",
            "collection_management",
            "desktop",
            "tkinter",
            "canadian_reference_provider",
            "series_definitions",
            "ocr_validation",
            "numista",
            "pathlib",
            "datetime",
            "uuid",
            "random",
            "logging",
        )
        lower = source_text.casefold()
        for term in prohibited:
            with self.subTest(term=term):
                self.assertNotIn(term, lower)

    def test_no_historical_year_constants(self) -> None:
        source_text = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source_text)
        years = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and type(node.value) is int
            and 1000 <= node.value <= 2999
        }
        self.assertEqual(years, set())

    def test_no_mutable_global_catalog_or_cache(self) -> None:
        for name, value in vars(module).items():
            if name.startswith("__"):
                continue
            self.assertNotIsInstance(
                value,
                (list, dict, set, CoinYearRuleCatalog, CoinYearRule),
            )

    def test_function_signature_is_exact(self) -> None:
        signature = inspect.signature(assess_coin_specific_year)
        self.assertEqual(tuple(signature.parameters), ("source", "catalog"))
        self.assertEqual(
            str(signature.return_annotation),
            "_FieldIntelligenceFinding | None",
        )


if __name__ == "__main__":
    unittest.main()
