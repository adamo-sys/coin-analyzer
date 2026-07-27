"""Tests for bounded confirmed-observation compatibility rules."""
from __future__ import annotations

import ast
import inspect
import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType

import capture_import.workflow_confirmed_observation_compatibility as module
from capture_import.workflow_confirmed_observation_compatibility import (
    ConfirmedObservationCompatibilityError,
    ConfirmedObservationCompatibilityResult,
    ConfirmedObservationCompatibilityStatus,
    ConfirmedObservationCompatibilityValidator,
    IncompatibleConfirmedObservationError,
    validate_confirmed_observation_compatibility,
)
from capture_import.workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedFieldObservation,
    ConfirmedObservationSet,
    ConfirmedObservationSource,
)
from capture_import.workflow_confirmed_observation_validators import (
    InvalidConfirmedObservationValueError,
    UnsupportedConfirmedObservationFieldError,
)


def _observation(field_name, value, *, canonical_value=None):
    return ConfirmedFieldObservation(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id="coin-1",
        field_name=field_name,
        submitted_value=value,
        canonical_value=canonical_value,
        reviewer_id="collector-1",
        provenance=(),
        source_type=ConfirmedObservationSource.MANUAL_ENTRY,
    )


def _set(*observations):
    return ConfirmedObservationSet(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id="coin-1",
        reviewer_id="collector-1",
        observations=tuple(sorted(observations, key=lambda x: x.field_name)),
        review_session_id="session-1",
        source_fingerprint="opaque fingerprint",
    )


def _monarch_year(monarch, year, *extra):
    return _set(
        _observation("monarch", monarch),
        _observation("year", year),
        *extra,
    )


class MonarchYearCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.validator = ConfirmedObservationCompatibilityValidator()

    def test_repository_fixture_combinations_are_compatible(self):
        cases = (
            ("Edward VII", "1904"),
            ("Edward VII", "1910"),
            ("George V", "1911"),
            ("George VI", "1945"),
            ("Elizabeth II", "1967"),
        )
        for monarch, year in cases:
            with self.subTest(monarch=monarch, year=year):
                result = self.validator.validate(
                    _monarch_year(monarch, year))[0]
                self.assertIs(
                    result.status,
                    ConfirmedObservationCompatibilityStatus.COMPATIBLE,
                )
                self.assertTrue(result.is_compatible)

    def test_accession_boundary_years_overlap_inclusively(self):
        cases = (
            ("Victoria", "1901"),
            ("Edward VII", "1901"),
            ("Edward VII", "1910"),
            ("George V", "1910"),
            ("George V", "1936"),
            ("Edward VIII", "1936"),
            ("George VI", "1936"),
            ("George VI", "1952"),
            ("Elizabeth II", "1952"),
            ("Elizabeth II", "2022"),
            ("Charles III", "2022"),
        )
        for monarch, year in cases:
            with self.subTest(monarch=monarch, year=year):
                result = validate_confirmed_observation_compatibility(
                    _monarch_year(monarch, year))[0]
                self.assertIs(
                    result.status,
                    ConfirmedObservationCompatibilityStatus.COMPATIBLE,
                )

    def test_clear_out_of_range_combinations_raise(self):
        cases = (
            ("Victoria", "1902"),
            ("Edward VII", "1900"),
            ("Edward VII", "1911"),
            ("George V", "1909"),
            ("Edward VIII", "1935"),
            ("Edward VIII", "1937"),
            ("George VI", "1953"),
            ("Elizabeth II", "1951"),
            ("Charles III", "2021"),
        )
        for monarch, year in cases:
            with self.subTest(monarch=monarch, year=year):
                with self.assertRaises(IncompatibleConfirmedObservationError):
                    self.validator.validate(_monarch_year(monarch, year))

    def test_incompatibility_error_exposes_only_rule_fields(self):
        source = _monarch_year(
            "George VI",
            "1967",
            _observation("country", "Canada"),
        )
        with self.assertRaises(IncompatibleConfirmedObservationError) as caught:
            self.validator.validate(source)
        error = caught.exception
        self.assertEqual(error.rule_id, "monarch_year")
        self.assertEqual(error.field_names, ("monarch", "year"))
        self.assertEqual(
            error.field_values,
            (("monarch", "George VI"), ("year", "1967")),
        )
        self.assertNotIn("Canada", str(error))

    def test_unknown_monarch_is_not_evaluated(self):
        for monarch in ("Unknown Sovereign", "Queen Victoria", "victoria"):
            with self.subTest(monarch=monarch):
                result = self.validator.validate(
                    _monarch_year(monarch, "1900"))[0]
                self.assertIs(
                    result.status,
                    ConfirmedObservationCompatibilityStatus.NOT_EVALUATED,
                )
                self.assertFalse(result.is_compatible)

    def test_missing_required_fields_are_not_evaluated(self):
        cases = (
            _set(_observation("country", "Canada")),
            _set(_observation("year", "1967")),
            _set(_observation("monarch", "Elizabeth II")),
        )
        for source in cases:
            with self.subTest(fields=tuple(x.field_name for x in source.observations)):
                result = self.validator.validate(source)[0]
                self.assertIs(
                    result.status,
                    ConfirmedObservationCompatibilityStatus.NOT_EVALUATED,
                )

    def test_exact_submitted_values_are_not_normalized(self):
        source = _monarch_year("victoria", "1900")
        before = source.to_dict()
        result = self.validator.validate(source)[0]
        self.assertIs(
            result.status,
            ConfirmedObservationCompatibilityStatus.NOT_EVALUATED,
        )
        self.assertEqual(source.to_dict(), before)
        self.assertEqual(source.observations[0].submitted_value, "victoria")


class DeferredDomainTests(unittest.TestCase):
    def test_canada_before_confederation_is_not_rejected(self):
        source = _monarch_year(
            "Victoria",
            "1859",
            _observation("country", "Canada"),
            _observation("denomination", "1 cent"),
        )
        result = validate_confirmed_observation_compatibility(source)
        self.assertEqual(len(result), 1)
        self.assertIs(
            result[0].status,
            ConfirmedObservationCompatibilityStatus.COMPATIBLE,
        )

    def test_unknown_country_and_denomination_are_not_guessed(self):
        source = _set(
            _observation("country", "Atlantis"),
            _observation("denomination", "25 cents"),
        )
        result = validate_confirmed_observation_compatibility(source)
        self.assertIs(
            result[0].status,
            ConfirmedObservationCompatibilityStatus.NOT_EVALUATED,
        )

    def test_banknote_and_silver_fields_add_no_hidden_rule(self):
        source = _monarch_year(
            "Elizabeth II",
            "1967",
            _observation("banknote_prefix", "AB12345"),
            _observation("denomination", "25 cents"),
            _observation("silver_indicator", "yes", canonical_value="true"),
        )
        result = validate_confirmed_observation_compatibility(source)
        self.assertEqual(tuple(x.rule_id for x in result), ("monarch_year",))
        self.assertIs(
            result[0].status,
            ConfirmedObservationCompatibilityStatus.COMPATIBLE,
        )


class PrerequisiteAndAtomicityTests(unittest.TestCase):
    def setUp(self):
        self.validator = ConfirmedObservationCompatibilityValidator()

    def test_unit_1c_invalid_value_propagates(self):
        source = _set(
            _observation("monarch", "George VI"),
            _observation("year", "19A7"),
        )
        with self.assertRaises(InvalidConfirmedObservationValueError):
            self.validator.validate(source)

    def test_unit_1c_unsupported_field_and_grade_propagate(self):
        for field_name in ("future_field", "grade"):
            with self.subTest(field_name=field_name):
                source = _set(_observation(field_name, "value"))
                with self.assertRaises(
                    UnsupportedConfirmedObservationFieldError
                ):
                    self.validator.validate(source)

    def test_incompatibility_returns_no_partial_result(self):
        source = _monarch_year("George VI", "1967")
        captured = None
        with self.assertRaises(IncompatibleConfirmedObservationError):
            captured = self.validator.validate(source)
        self.assertIsNone(captured)
        self.assertEqual(source.observations[0].submitted_value, "George VI")
        self.assertEqual(source.observations[1].submitted_value, "1967")

    def test_source_set_and_linkage_remain_unchanged(self):
        source = _monarch_year(
            "George VI",
            "1945",
            _observation("country", "Canada"),
        )
        before = source.to_dict()
        self.validator.validate(source)
        self.assertEqual(source.to_dict(), before)
        self.assertEqual(source.review_session_id, "session-1")
        self.assertEqual(source.source_fingerprint, "opaque fingerprint")

    def test_equivalent_inputs_produce_equivalent_results(self):
        first = validate_confirmed_observation_compatibility(
            _monarch_year("George VI", "1945"))
        second = validate_confirmed_observation_compatibility(
            _monarch_year("George VI", "1945"))
        self.assertEqual(first, second)
        self.assertEqual(
            tuple(item.to_dict() for item in first),
            tuple(item.to_dict() for item in second),
        )

    def test_malformed_input_type_propagates(self):
        with self.assertRaises(TypeError):
            self.validator.validate(object())
        with self.assertRaises(TypeError):
            validate_confirmed_observation_compatibility(object())


class ResultAndArchitectureTests(unittest.TestCase):
    def test_result_is_frozen_slotted_bounded_and_json_safe(self):
        result = validate_confirmed_observation_compatibility(
            _monarch_year("George VI", "1945"))[0]
        self.assertIsInstance(result, ConfirmedObservationCompatibilityResult)
        self.assertFalse(hasattr(result, "__dict__"))
        self.assertEqual(json.loads(json.dumps(result.to_dict())), {
            "rule_id": "monarch_year",
            "fields": ["monarch", "year"],
            "status": "COMPATIBLE",
            "message": "Monarch and year satisfy the inclusive bounded reign rule.",
        })
        with self.assertRaises(FrozenInstanceError):
            result.message = "changed"

    def test_error_hierarchy_is_narrow(self):
        self.assertTrue(issubclass(
            IncompatibleConfirmedObservationError,
            ConfirmedObservationCompatibilityError,
        ))

    def test_rule_table_is_immutable(self):
        self.assertIsInstance(module._MONARCH_YEAR_RANGES, MappingProxyType)
        with self.assertRaises(TypeError):
            module._MONARCH_YEAR_RANGES["Future Monarch"] = (2100, 2200)

    def test_service_is_stateless(self):
        validator = ConfirmedObservationCompatibilityValidator()
        self.assertEqual(
            ConfirmedObservationCompatibilityValidator.__slots__, ())
        self.assertFalse(hasattr(validator, "__dict__"))

    def test_module_has_no_forbidden_integrations_or_automatic_invocation(self):
        path = Path(inspect.getfile(ConfirmedObservationCompatibilityValidator))
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {alias.name for node in ast.walk(tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom))
                    for alias in node.names}
        for fragment in (
            "collection", "persistence", "desktop", "gui", "tkinter",
            "pathlib", "os", "environment", "requests", "urllib", "uuid",
            "datetime", "workflow_confirmed_observation_mapper",
            "workflow_confirmed_observation_canonicalization",
        ):
            with self.subTest(fragment=fragment):
                self.assertFalse(any(fragment in name.casefold()
                                     for name in imported), imported)
        self.assertNotIn("map_review_session", source)
        self.assertNotIn("apply_canonical", source)


if __name__ == "__main__":
    unittest.main()
