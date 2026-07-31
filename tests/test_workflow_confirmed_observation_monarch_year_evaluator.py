from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import inspect
from pathlib import Path
import unittest

import capture_import.workflow_confirmed_observation_monarch_year_evaluator as module
from capture_import.workflow_confirmed_observation_monarch_year_evaluator import (
    InvalidMonarchYearEvaluationContextError,
    MonarchYearEvaluationError,
    assess_monarch_year_compatibility,
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
    "MonarchYearEvaluationError",
    "InvalidMonarchYearEvaluationContextError",
    "assess_monarch_year_compatibility",
}
RELEVANT_VALUES = {
    "monarch": "George VI",
    "year": "1945",
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
            "MonarchYearEvaluator",
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
        self.assertIs(MonarchYearEvaluationError.__base__, ValueError)
        self.assertIs(
            InvalidMonarchYearEvaluationContextError.__base__,
            MonarchYearEvaluationError,
        )

    def test_errors_are_immutable(self) -> None:
        error = InvalidMonarchYearEvaluationContextError("bounded")
        with self.assertRaises(AttributeError):
            error.detail = "changed"  # type: ignore[attr-defined]
        with self.assertRaises(AttributeError):
            error.args = ("changed",)

    def test_wrong_source_type_is_typed(self) -> None:
        with self.assertRaisesRegex(
            InvalidMonarchYearEvaluationContextError,
            "ConfirmedObservationSet",
        ):
            assess_monarch_year_compatibility(object())

    def test_source_validation_precedes_evaluation(self) -> None:
        malformed = source({"monarch": "George VI", "year": "19A5"})
        with self.assertRaisesRegex(
            InvalidMonarchYearEvaluationContextError,
            "confirmed-observation validation",
        ):
            assess_monarch_year_compatibility(malformed)

    def test_forged_empty_source_is_typed(self) -> None:
        malformed = source()
        object.__setattr__(malformed, "observations", ())
        with self.assertRaises(InvalidMonarchYearEvaluationContextError):
            assess_monarch_year_compatibility(malformed)

    def test_forged_nested_source_is_typed_without_attribute_error(self) -> None:
        malformed = source()
        object.__setattr__(malformed, "observations", (object(),))
        with self.assertRaises(InvalidMonarchYearEvaluationContextError):
            assess_monarch_year_compatibility(malformed)


class MatchingAndContextTests(unittest.TestCase):
    def test_compatible_monarch_year_is_valid(self) -> None:
        result = assess_monarch_year_compatibility(source())
        self.assertIsInstance(result, FieldIntelligenceFinding)
        self.assertIs(result.status, FieldIntelligenceStatus.VALID)
        self.assertEqual(result.diagnostic_code, "MONARCH_YEAR_COMPATIBLE")
        self.assertEqual(result.rule_id, "monarch-year.evaluation-v1")
        self.assertEqual(result.source_fields, ("monarch", "year"))

    def test_incompatible_monarch_year_is_invalid(self) -> None:
        result = assess_monarch_year_compatibility(
            source({"monarch": "George VI", "year": "1953"})
        )
        self.assertIs(result.status, FieldIntelligenceStatus.INVALID)
        self.assertEqual(result.diagnostic_code, "MONARCH_YEAR_INCOMPATIBLE")
        self.assertEqual(result.rule_id, "monarch-year.evaluation-v1")
        self.assertEqual(result.source_fields, ("monarch", "year"))

    def test_unknown_monarch_is_not_evaluated(self) -> None:
        result = assess_monarch_year_compatibility(
            source({"monarch": "Unknown Sovereign", "year": "1945"})
        )
        self.assertIs(result.status, FieldIntelligenceStatus.NOT_EVALUATED)
        self.assertEqual(result.diagnostic_code, "MONARCH_YEAR_UNKNOWN")
        self.assertEqual(result.rule_id, "monarch-year.evaluation-v1")
        self.assertEqual(result.source_fields, ("monarch", "year"))

    def test_missing_monarch_is_required_context(self) -> None:
        result = assess_monarch_year_compatibility(
            source({"year": "1945"})
        )
        self.assertIs(result.status, FieldIntelligenceStatus.NOT_EVALUATED)
        self.assertEqual(result.diagnostic_code, "REQUIRED_CONTEXT_MISSING")
        self.assertEqual(result.rule_id, "monarch-year.evaluation-v1")
        self.assertEqual(result.source_fields, ("year",))

    def test_missing_year_is_required_context(self) -> None:
        result = assess_monarch_year_compatibility(
            source({"monarch": "George VI"})
        )
        self.assertIs(result.status, FieldIntelligenceStatus.NOT_EVALUATED)
        self.assertEqual(result.diagnostic_code, "REQUIRED_CONTEXT_MISSING")
        self.assertEqual(result.rule_id, "monarch-year.evaluation-v1")
        self.assertEqual(result.source_fields, ("monarch",))

    def test_neither_field_present_returns_none(self) -> None:
        self.assertIsNone(assess_monarch_year_compatibility(source({"country": "Canada"})))


class ExactValueAndDeterminismTests(unittest.TestCase):
    def test_exact_submitted_values_are_used_and_canonical_values_are_ignored(self) -> None:
        result = assess_monarch_year_compatibility(
            source(
                {"monarch": "George VI", "year": "1945"},
                canonical_values={
                    "monarch": "Elizabeth II",
                    "year": "2022",
                },
            )
        )
        self.assertIs(result.status, FieldIntelligenceStatus.VALID)
        self.assertEqual(result.rule_id, "monarch-year.evaluation-v1")

    def test_repeated_evaluation_is_deterministic(self) -> None:
        selected_source = source()
        first = assess_monarch_year_compatibility(selected_source)
        second = assess_monarch_year_compatibility(selected_source)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)

    def test_evaluation_does_not_mutate_inputs(self) -> None:
        selected_source = source()
        before = selected_source.to_dict()
        assess_monarch_year_compatibility(selected_source)
        self.assertEqual(selected_source.to_dict(), before)

    def test_finding_contains_no_values_or_source_objects(self) -> None:
        result = assess_monarch_year_compatibility(source())
        self.assertEqual(
            set(result.__slots__),
            {"rule_id", "source_fields", "status", "diagnostic_code"},
        )
        self.assertFalse(hasattr(result, "source"))


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
                "workflow_confirmed_observation_compatibility",
                "workflow_confirmed_observation_field_intelligence",
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
        signature = inspect.signature(assess_monarch_year_compatibility)
        self.assertEqual(tuple(signature.parameters), ("source",))
        self.assertEqual(
            str(signature.return_annotation),
            "_FieldIntelligenceFinding | None",
        )


if __name__ == "__main__":
    unittest.main()
