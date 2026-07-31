from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import inspect
from pathlib import Path
import unicodedata
import unittest

import capture_import.workflow_confirmed_observation_mintmark_evaluator as module
from capture_import.workflow_confirmed_observation_mintmark_evaluator import (
    InvalidMintmarkEvaluationContextError,
    MintmarkEvaluationError,
    assess_mintmark,
)
from capture_import.workflow_confirmed_observation_field_intelligence import (
    FieldIntelligenceFinding,
    FieldIntelligenceStatus,
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


PUBLIC_API = {
    "MintmarkEvaluationError",
    "InvalidMintmarkEvaluationContextError",
    "assess_mintmark",
}
RELEVANT_VALUES = {
    "country": "Exampleland",
    "denomination": "1 Cent",
    "series_type": "Series Alpha",
    "year": "1901",
    "monarch": "Example Monarch",
    "mintmark": "P",
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
    mintmark: str = "P",
) -> MintmarkRuleCatalog:
    return MintmarkRuleCatalog(
        (
            MintmarkRule(
                rule_id="mintmark.example.generic-v1",
                country=country,
                denomination=denomination,
                series_type=None,
                year=None,
                monarch=None,
                mintmark=mintmark,
            ),
        )
    )


def specific_catalog() -> MintmarkRuleCatalog:
    return MintmarkRuleCatalog(
        (
            MintmarkRule(
                rule_id="mintmark.example.alpha-v1",
                country="Exampleland",
                denomination="1 Cent",
                series_type="Series Alpha",
                year=1901,
                monarch="Example Monarch",
                mintmark="P",
            ),
            MintmarkRule(
                rule_id="mintmark.example.beta-v1",
                country="Exampleland",
                denomination="1 Cent",
                series_type="Series Beta",
                year=1902,
                monarch="Example Monarch",
                mintmark="R",
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
            "MintmarkEvaluator",
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
        self.assertIs(MintmarkEvaluationError.__base__, ValueError)
        self.assertIs(
            InvalidMintmarkEvaluationContextError.__base__,
            MintmarkEvaluationError,
        )

    def test_errors_are_immutable(self) -> None:
        error = InvalidMintmarkEvaluationContextError("bounded")
        with self.assertRaises(AttributeError):
            error.detail = "changed"  # type: ignore[attr-defined]
        with self.assertRaises(AttributeError):
            error.args = ("changed",)

    def test_wrong_source_type_is_typed(self) -> None:
        with self.assertRaisesRegex(
            InvalidMintmarkEvaluationContextError,
            "ConfirmedObservationSet",
        ):
            assess_mintmark(object(), generic_catalog())

    def test_wrong_catalog_type_is_typed(self) -> None:
        with self.assertRaisesRegex(
            InvalidMintmarkEvaluationContextError,
            "MintmarkRuleCatalog",
        ):
            assess_mintmark(source(), object())

    def test_source_validation_precedes_catalog_validation(self) -> None:
        cases = (
            (source({"mintmark": "invalid value"}), MintmarkRuleCatalog(())),
            (source({"mintmark": "invalid value"}), generic_catalog()),
            (source({"mintmark": "invalid value"}), object()),
        )
        for malformed, catalog in cases:
            with self.subTest(catalog_type=type(catalog).__name__):
                with self.assertRaisesRegex(
                    InvalidMintmarkEvaluationContextError,
                    "confirmed-observation validation",
                ):
                    assess_mintmark(malformed, catalog)

    def test_forged_empty_source_is_typed(self) -> None:
        malformed = source()
        object.__setattr__(malformed, "observations", ())
        with self.assertRaises(InvalidMintmarkEvaluationContextError):
            assess_mintmark(malformed, generic_catalog())

    def test_forged_nested_source_is_typed_without_attribute_error(self) -> None:
        malformed = source()
        object.__setattr__(malformed, "observations", (object(),))
        with self.assertRaises(InvalidMintmarkEvaluationContextError):
            assess_mintmark(malformed, generic_catalog())

    def test_forged_catalog_is_typed(self) -> None:
        malformed = object.__new__(MintmarkRuleCatalog)
        object.__setattr__(malformed, "rules", [])
        with self.assertRaisesRegex(
            InvalidMintmarkEvaluationContextError,
            "mintmark rule validation",
        ):
            assess_mintmark(source(), malformed)


class MatchingAndContextTests(unittest.TestCase):
    def test_generic_rule_is_valid_when_mintmark_matches(self) -> None:
        result = assess_mintmark(
            source({
                "country": "Exampleland",
                "denomination": "1 Cent",
                "mintmark": "P",
            }),
            generic_catalog(),
        )
        self.assertIsInstance(result, FieldIntelligenceFinding)
        self.assertIs(result.status, FieldIntelligenceStatus.VALID)
        self.assertEqual(result.diagnostic_code, "MINTMARK_MATCH")
        self.assertEqual(result.rule_id, "mintmark.example.generic-v1")
        self.assertEqual(result.source_fields, ("country", "denomination", "mintmark"))

    def test_generic_rule_is_invalid_when_mintmark_conflicts(self) -> None:
        result = assess_mintmark(
            source({
                "country": "Exampleland",
                "denomination": "1 Cent",
                "mintmark": "R",
            }),
            generic_catalog(),
        )
        self.assertIs(result.status, FieldIntelligenceStatus.INVALID)
        self.assertEqual(result.diagnostic_code, "MINTMARK_CONFLICT")
        self.assertEqual(result.rule_id, "mintmark.example.generic-v1")

    def test_specific_rule_matches_exact_scope_and_uses_submitted_values(self) -> None:
        result = assess_mintmark(source(), specific_catalog())
        self.assertIs(result.status, FieldIntelligenceStatus.VALID)
        self.assertEqual(result.diagnostic_code, "MINTMARK_MATCH")
        self.assertEqual(result.rule_id, "mintmark.example.alpha-v1")
        self.assertEqual(
            result.source_fields,
            ("country", "denomination", "mintmark", "monarch", "series_type", "year"),
        )

    def test_specific_rule_conflict_is_invalid(self) -> None:
        result = assess_mintmark(
            source({
                "country": "Exampleland",
                "denomination": "1 Cent",
                "series_type": "Series Alpha",
                "year": "1901",
                "monarch": "Example Monarch",
                "mintmark": "R",
            }),
            specific_catalog(),
        )
        self.assertIs(result.status, FieldIntelligenceStatus.INVALID)
        self.assertEqual(result.diagnostic_code, "MINTMARK_CONFLICT")
        self.assertEqual(result.rule_id, "mintmark.example.alpha-v1")

    def test_missing_mintmark_is_required_context(self) -> None:
        result = assess_mintmark(
            source({
                "country": "Exampleland",
                "denomination": "1 Cent",
                "series_type": "Series Alpha",
                "year": "1901",
                "monarch": "Example Monarch",
            }),
            specific_catalog(),
        )
        self.assertIs(result.status, FieldIntelligenceStatus.NOT_EVALUATED)
        self.assertEqual(result.diagnostic_code, "REQUIRED_CONTEXT_MISSING")
        self.assertEqual(result.rule_id, "mintmark.evaluation-v1")
        self.assertEqual(
            result.source_fields,
            ("country", "denomination", "monarch", "series_type", "year"),
        )

    def test_missing_specific_scope_fields_are_required_context(self) -> None:
        result = assess_mintmark(
            source({
                "country": "Exampleland",
                "denomination": "1 Cent",
                "mintmark": "P",
            }),
            specific_catalog(),
        )
        self.assertIs(result.status, FieldIntelligenceStatus.NOT_EVALUATED)
        self.assertEqual(result.diagnostic_code, "REQUIRED_CONTEXT_MISSING")
        self.assertEqual(result.rule_id, "mintmark.evaluation-v1")
        self.assertEqual(result.source_fields, ("country", "denomination", "mintmark"))

    def test_unknown_pair_is_not_evaluated(self) -> None:
        result = assess_mintmark(
            source({
                "country": "Exampleland",
                "denomination": "5 Cents",
                "mintmark": "P",
            }),
            generic_catalog(),
        )
        self.assertIs(result.status, FieldIntelligenceStatus.NOT_EVALUATED)
        self.assertEqual(result.diagnostic_code, "RULE_COVERAGE_UNKNOWN")
        self.assertEqual(result.rule_id, "mintmark.evaluation-v1")
        self.assertEqual(result.source_fields, ("country", "denomination", "mintmark"))

    def test_neither_relevant_field_present_returns_none(self) -> None:
        value = source({"silver_indicator": "true"})
        self.assertIsNone(assess_mintmark(value, generic_catalog()))


class ExactValueAndDeterminismTests(unittest.TestCase):
    def test_exact_submitted_values_are_used_and_canonical_values_are_ignored(self) -> None:
        result = assess_mintmark(
            source(
                {
                    "country": "Exampleland",
                    "denomination": "1 Cent",
                    "series_type": "Series Alpha",
                    "year": "1901",
                    "monarch": "Example Monarch",
                    "mintmark": "P",
                },
                canonical_values={
                    "country": "Otherland",
                    "denomination": "5 Cents",
                    "series_type": "Series Beta",
                    "year": "1902",
                    "monarch": "Different Monarch",
                    "mintmark": "R",
                },
            ),
            specific_catalog(),
        )
        self.assertIs(result.status, FieldIntelligenceStatus.VALID)
        self.assertEqual(result.rule_id, "mintmark.example.alpha-v1")

    def test_exact_case_mismatch_is_invalid_conflict(self) -> None:
        values = dict(RELEVANT_VALUES)
        values["mintmark"] = "p"
        result = assess_mintmark(source(values), generic_catalog())
        self.assertIs(result.status, FieldIntelligenceStatus.INVALID)
        self.assertEqual(result.diagnostic_code, "MINTMARK_CONFLICT")
        self.assertEqual(result.rule_id, "mintmark.example.generic-v1")

    def test_padded_scope_text_is_not_trimmed(self) -> None:
        values = dict(RELEVANT_VALUES)
        values["country"] = " Exampleland"
        result = assess_mintmark(source(values), generic_catalog())
        self.assertIs(result.status, FieldIntelligenceStatus.NOT_EVALUATED)
        self.assertEqual(result.diagnostic_code, "RULE_COVERAGE_UNKNOWN")

    def test_normalization_is_not_applied_to_scope_text(self) -> None:
        values = dict(RELEVANT_VALUES)
        values["country"] = unicodedata.normalize("NFD", "Côte d'Ivoire")
        with self.assertRaises(InvalidMintmarkEvaluationContextError):
            assess_mintmark(source(values), generic_catalog())

    def test_repeated_evaluation_is_deterministic(self) -> None:
        selected_source = source()
        selected_catalog = generic_catalog(mintmark="R")
        first = assess_mintmark(selected_source, selected_catalog)
        second = assess_mintmark(selected_source, selected_catalog)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)

    def test_evaluation_does_not_mutate_inputs(self) -> None:
        selected_source = source()
        selected_catalog = generic_catalog()
        source_before = selected_source.to_dict()
        catalog_rules = selected_catalog.rules
        rule_ids = selected_catalog.rule_ids
        assess_mintmark(selected_source, selected_catalog)
        self.assertEqual(selected_source.to_dict(), source_before)
        self.assertIs(selected_catalog.rules, catalog_rules)
        self.assertEqual(selected_catalog.rule_ids, rule_ids)
        for actual, expected in zip(
            selected_catalog.rules,
            catalog_rules,
            strict=True,
        ):
            self.assertIs(actual, expected)

    def test_finding_contains_no_values_or_source_objects(self) -> None:
        result = assess_mintmark(source(), specific_catalog())
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
                "workflow_confirmed_observation_field_intelligence",
                "workflow_confirmed_observation_mintmark_rules",
                "workflow_confirmed_observation_models",
                "workflow_confirmed_observation_validators",
            },
        )

    def test_no_forbidden_runtime_or_history_imports(self) -> None:
        source_text = Path(module.__file__).read_text(encoding="utf-8")
        prohibited = (
            "canonicalization",
            "collection_management",
            "desktop",
            "tkinter",
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

    def test_function_signature_is_exact(self) -> None:
        signature = inspect.signature(assess_mintmark)
        self.assertEqual(tuple(signature.parameters), ("source", "catalog"))
        self.assertEqual(
            str(signature.return_annotation),
            "_FieldIntelligenceFinding | None",
        )


if __name__ == "__main__":
    unittest.main()
