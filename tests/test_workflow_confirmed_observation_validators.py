"""Tests for pure confirmed-observation field validators."""
from __future__ import annotations

import ast
import inspect
import json
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import MappingProxyType

import capture_import.workflow_confirmed_observation_validators as validator_module

from capture_import.workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedFieldObservation,
    ConfirmedObservationSet,
    ConfirmedObservationSource,
)
from capture_import.workflow_confirmed_observation_validators import (
    ConfirmedObservationValidationError,
    ConfirmedObservationValidationResult,
    ConfirmedObservationValidatorRegistry,
    InvalidConfirmedObservationValueError,
    UnsupportedConfirmedObservationFieldError,
    validate_confirmed_observation,
    validate_confirmed_observation_set,
)
from capture_import.workflow_ocr_models import ALLOWED_OCR_FIELDS


def _observation(field_name="year", value="1967"):
    return ConfirmedFieldObservation(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id="coin-1",
        field_name=field_name,
        submitted_value=value,
        canonical_value=None,
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


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = ConfirmedObservationValidatorRegistry()

    def test_registry_exactly_matches_mapper_allowlist(self):
        self.assertEqual(self.registry.field_names, ALLOWED_OCR_FIELDS)
        self.assertNotIn("grade", self.registry.field_names)
        self.assertEqual(
            self.registry.field_names,
            frozenset({
                "year", "denomination", "country", "monarch", "mintmark",
                "series_type", "banknote_prefix", "certification_number",
                "silver_indicator", "variety_keyword",
            }),
        )

    def test_unknown_grade_and_noncanonical_aliases_fail_closed(self):
        for field_name in ("grade", "material", "series", "type", "variety",
                           "Year", " country"):
            with self.subTest(field_name=field_name):
                with self.assertRaises(UnsupportedConfirmedObservationFieldError):
                    self.registry.validate_value(
                        field_name=field_name, submitted_value="value")

    def test_malformed_dispatch_input_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.registry.validate_value(field_name=1, submitted_value="1967")
        with self.assertRaises(TypeError):
            self.registry.validate_value(field_name="year", submitted_value=1967)

    def test_registry_storage_is_immutable(self):
        self.assertIsInstance(validator_module._VALIDATORS, MappingProxyType)
        with self.assertRaises(TypeError):
            validator_module._VALIDATORS["year"] = lambda value: None

    def test_error_types_share_the_explicit_validation_hierarchy(self):
        self.assertTrue(issubclass(
            UnsupportedConfirmedObservationFieldError,
            ConfirmedObservationValidationError,
        ))
        self.assertTrue(issubclass(
            InvalidConfirmedObservationValueError,
            ConfirmedObservationValidationError,
        ))
    def test_registry_is_stateless(self):
        self.assertEqual(ConfirmedObservationValidatorRegistry.__slots__, ())
        self.assertFalse(hasattr(self.registry, "__dict__"))


class YearValidatorTests(unittest.TestCase):
    def test_valid_year_and_static_bounds(self):
        for value in ("1000", "1967", "2026", "2999"):
            with self.subTest(value=value):
                result = validate_confirmed_observation(_observation("year", value))
                self.assertEqual(result.submitted_value, value)
                self.assertIsNone(result.canonical_value)

    def test_invalid_year_forms(self):
        for value in ("", " ", "999", "0999", "3000", "+1967", "1967.0",
                      "19A7", "196 7", " 1967", "1967 ", "missing"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidConfirmedObservationValueError):
                    validate_confirmed_observation(_observation("year", value))


class DenominationValidatorTests(unittest.TestCase):
    def test_current_ocr_vocabulary_examples(self):
        values = (
            "1 cent", "5 cents", "10 cents", "25 cents", "50 cents",
            "1 dollar", "2 dollars", "dime", "quarter", "half dollar",
            "$5", "five cents",
        )
        for value in values:
            with self.subTest(value=value):
                result = validate_confirmed_observation(
                    _observation("denomination", value))
                self.assertEqual(result.submitted_value, value)
                self.assertIsNone(result.canonical_value)

    def test_invalid_denomination_forms(self):
        for value in ("", "token", "zero cents", "0 dollars", "missing",
                      "1\ncent", "x" * 65):
            with self.subTest(value=value):
                with self.assertRaises(InvalidConfirmedObservationValueError):
                    validate_confirmed_observation(
                        _observation("denomination", value))


class TextFieldValidatorTests(unittest.TestCase):
    def test_country_preserves_exact_text(self):
        value = "  United Kingdom  "
        result = validate_confirmed_observation(_observation("country", value))
        self.assertEqual(result.submitted_value, value)
        self.assertIsNone(result.canonical_value)

    def test_country_invalid_values(self):
        for value in ("", "missing", "Canada\n", "x" * 129):
            with self.subTest(value=value):
                with self.assertRaises(InvalidConfirmedObservationValueError):
                    validate_confirmed_observation(_observation("country", value))

    def test_monarch_preserves_unicode_and_punctuation(self):
        value = "Élisabeth II (1952–2022)"
        result = validate_confirmed_observation(_observation("monarch", value))
        self.assertEqual(result.submitted_value, value)

    def test_monarch_invalid_values(self):
        for value in ("", "unresolved", "x" * 129):
            with self.subTest(value=value):
                with self.assertRaises(InvalidConfirmedObservationValueError):
                    validate_confirmed_observation(_observation("monarch", value))

    def test_series_type_preserves_exact_text(self):
        value = "Newfoundland coinage / Type II"
        result = validate_confirmed_observation(
            _observation("series_type", value))
        self.assertEqual(result.submitted_value, value)
        self.assertIsNone(result.canonical_value)

    def test_series_type_invalid_values(self):
        for value in ("", "deferred", "x" * 257):
            with self.subTest(value=value):
                with self.assertRaises(InvalidConfirmedObservationValueError):
                    validate_confirmed_observation(
                        _observation("series_type", value))

    def test_variety_preserves_case_and_punctuation(self):
        value = "8 over 9 — Proof-Like"
        result = validate_confirmed_observation(
            _observation("variety_keyword", value))
        self.assertEqual(result.submitted_value, value)
        self.assertIsNone(result.canonical_value)

    def test_variety_invalid_values(self):
        for value in ("", "rejected", "x" * 257):
            with self.subTest(value=value):
                with self.assertRaises(InvalidConfirmedObservationValueError):
                    validate_confirmed_observation(
                        _observation("variety_keyword", value))

    def test_all_text_fields_reject_controls_and_non_nfc(self):
        for field_name in ("country", "monarch", "series_type",
                           "variety_keyword"):
            for value in ("bad\tvalue", "Cafe\u0301"):
                with self.subTest(field_name=field_name, value=value):
                    with self.assertRaises(InvalidConfirmedObservationValueError):
                        validate_confirmed_observation(
                            _observation(field_name, value))


class TokenFieldValidatorTests(unittest.TestCase):
    def test_valid_mintmarks_preserve_case(self):
        for value in ("H", "P", "W", "H-1", "P.2"):
            with self.subTest(value=value):
                result = validate_confirmed_observation(
                    _observation("mintmark", value))
                self.assertEqual(result.submitted_value, value)

    def test_invalid_mintmarks(self):
        for value in ("", "none", "missing", "H M", "H/M", "H\\M",
                      "-H", "x" * 17, "H\n"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidConfirmedObservationValueError):
                    validate_confirmed_observation(_observation("mintmark", value))

    def test_valid_banknote_prefixes_preserve_case(self):
        for value in ("A12345", "AB1234567", "abcd123456789"):
            with self.subTest(value=value):
                result = validate_confirmed_observation(
                    _observation("banknote_prefix", value))
                self.assertEqual(result.submitted_value, value)
                self.assertIsNone(result.canonical_value)

    def test_invalid_banknote_prefixes(self):
        for value in ("", "missing", "A 12345", "A-12345", "123456",
                      "ABCDE12345", "A1234", "A1234567890"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidConfirmedObservationValueError):
                    validate_confirmed_observation(
                        _observation("banknote_prefix", value))

    def test_valid_certification_numbers_preserve_exact_text(self):
        for value in ("PCGS12345", "XSZ431", "12345678", "AB-123 456"):
            with self.subTest(value=value):
                result = validate_confirmed_observation(
                    _observation("certification_number", value))
                self.assertEqual(result.submitted_value, value)
                self.assertIsNone(result.canonical_value)

    def test_invalid_certification_numbers_and_grade_like_tokens(self):
        for value in ("", "missing", "ABC", "MS65", "VF-20", "A#1234",
                      "A/1234", "A\n1234", "x" * 65):
            with self.subTest(value=value):
                with self.assertRaises(InvalidConfirmedObservationValueError):
                    validate_confirmed_observation(
                        _observation("certification_number", value))


class SilverIndicatorValidatorTests(unittest.TestCase):
    def test_supported_values_have_explicit_boolean_canonical_value(self):
        expected = {
            "true": "true", "TRUE": "true", "yes": "true",
            "silver": "true", "false": "false", "FALSE": "false",
            "no": "false", "non-silver": "false",
        }
        for submitted, canonical in expected.items():
            with self.subTest(submitted=submitted):
                result = validate_confirmed_observation(
                    _observation("silver_indicator", submitted))
                self.assertEqual(result.submitted_value, submitted)
                self.assertEqual(result.canonical_value, canonical)

    def test_unsupported_or_inferred_silver_values_fail(self):
        for value in ("", "maybe", "Possible silver", ".925", "1", "0",
                      " true", "true ", "missing"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidConfirmedObservationValueError):
                    validate_confirmed_observation(
                        _observation("silver_indicator", value))


class ResultAndSetValidationTests(unittest.TestCase):
    def test_result_is_frozen_slotted_and_json_safe(self):
        result = validate_confirmed_observation(_observation())
        self.assertIsInstance(result, ConfirmedObservationValidationResult)
        self.assertFalse(hasattr(result, "__dict__"))
        self.assertEqual(json.loads(json.dumps(result.to_dict())), {
            "field_name": "year",
            "submitted_value": "1967",
            "canonical_value": None,
        })
        with self.assertRaises(FrozenInstanceError):
            result.submitted_value = "1968"

    def test_one_and_multiple_observation_sets(self):
        single = _set(_observation())
        self.assertEqual(len(validate_confirmed_observation_set(single)), 1)
        source = _set(
            _observation("year", "1967"),
            _observation("country", "Canada"),
            _observation("silver_indicator", "yes"),
        )
        before = source.to_dict()
        results = validate_confirmed_observation_set(source)
        self.assertIsInstance(results, tuple)
        self.assertEqual(tuple(x.field_name for x in results),
                         ("country", "silver_indicator", "year"))
        self.assertEqual(results[1].canonical_value, "true")
        self.assertEqual(source.to_dict(), before)
        self.assertEqual(source.review_session_id, "session-1")
        self.assertEqual(source.source_fingerprint, "opaque fingerprint")

    def test_set_failure_is_atomic_and_returns_no_collection_object(self):
        source = _set(
            _observation("country", "Canada"),
            _observation("year", "19A7"),
        )
        captured = None
        with self.assertRaises(InvalidConfirmedObservationValueError):
            captured = validate_confirmed_observation_set(source)
        self.assertIsNone(captured)
        self.assertEqual(source.observations[0].submitted_value, "Canada")

    def test_unknown_and_grade_observations_use_explicit_error(self):
        for field_name in ("grade", "future_field"):
            with self.subTest(field_name=field_name):
                with self.assertRaises(UnsupportedConfirmedObservationFieldError):
                    validate_confirmed_observation(
                        _observation(field_name, "value"))

    def test_malformed_objects_raise_type_error(self):
        with self.assertRaises(TypeError):
            validate_confirmed_observation(object())
        with self.assertRaises(TypeError):
            validate_confirmed_observation_set(object())
        malformed = replace(_set(_observation()), observations=[])
        with self.assertRaises(TypeError):
            validate_confirmed_observation_set(malformed)


class ArchitectureTests(unittest.TestCase):
    def test_module_has_no_forbidden_imports_or_automatic_mapper_use(self):
        path = Path(inspect.getfile(ConfirmedObservationValidatorRegistry))
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {alias.name for node in ast.walk(tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom))
                    for alias in node.names}
        for fragment in (
            "collection", "persistence", "desktop", "gui", "tkinter",
            "pathlib", "os", "environment", "requests", "urllib", "uuid",
            "datetime", "workflow_confirmed_observation_mapper",
        ):
            with self.subTest(fragment=fragment):
                self.assertFalse(any(fragment in name.casefold()
                                     for name in imported), imported)
        self.assertNotIn("map_review_session", source)

    def test_validation_does_not_return_confirmed_or_collection_objects(self):
        annotation = inspect.signature(
            validate_confirmed_observation_set).return_annotation
        self.assertIn("ConfirmedObservationValidationResult", str(annotation))
        self.assertNotIn("ConfirmedObservationSet", str(annotation))


if __name__ == "__main__":
    unittest.main()
