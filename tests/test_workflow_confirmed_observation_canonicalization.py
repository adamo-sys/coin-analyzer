"""Tests for explicit canonical-value application."""
from __future__ import annotations

import ast
import inspect
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

from capture_import.workflow_confirmed_observation_canonicalization import (
    ConfirmedObservationCanonicalizationError,
    ConfirmedObservationCanonicalizer,
    ConflictingCanonicalValueError,
    apply_canonical_value,
    apply_canonical_values,
)
from capture_import.workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedFieldObservation,
    ConfirmedObservationProvenance,
    ConfirmedObservationSet,
    ConfirmedObservationSource,
)
from capture_import.workflow_confirmed_observation_validators import (
    InvalidConfirmedObservationValueError,
    UnsupportedConfirmedObservationFieldError,
)


_PROVENANCE = (
    ConfirmedObservationProvenance(
        provider_id="test-ocr",
        image_role="front",
        artifact_key="crop-front",
        source_value="source text",
        confidence_score=92.0,
        evidence=("visible legend",),
    ),
)


def _observation(
    field_name="year",
    value="1967",
    *,
    canonical_value=None,
    source_coin_id="coin-1",
):
    return ConfirmedFieldObservation(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id=source_coin_id,
        field_name=field_name,
        submitted_value=value,
        canonical_value=canonical_value,
        reviewer_id="collector-1",
        provenance=_PROVENANCE,
        source_type=ConfirmedObservationSource.MANUAL_ENTRY,
        rationale="Human-confirmed source text.",
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


class FieldCanonicalizationTests(unittest.TestCase):
    def setUp(self):
        self.service = ConfirmedObservationCanonicalizer()

    def test_silver_true_and_false_are_applied(self):
        expected = {
            "yes": "true",
            "SILVER": "true",
            "no": "false",
            "NON-SILVER": "false",
        }
        for submitted, canonical in expected.items():
            with self.subTest(submitted=submitted):
                original = _observation("silver_indicator", submitted)
                result = self.service.apply_to_observation(original)
                self.assertEqual(result.submitted_value, submitted)
                self.assertEqual(result.canonical_value, canonical)
                self.assertIsNot(result, original)
                self.assertIsNone(original.canonical_value)

    def test_matching_existing_canonical_is_accepted(self):
        original = _observation(
            "silver_indicator", "YES", canonical_value="true")
        result = self.service.apply_to_observation(original)
        self.assertEqual(result, original)
        self.assertIsNot(result, original)

    def test_conflicting_existing_canonical_is_rejected(self):
        original = _observation(
            "silver_indicator", "yes", canonical_value="false")
        with self.assertRaises(ConflictingCanonicalValueError) as caught:
            self.service.apply_to_observation(original)
        self.assertEqual(caught.exception.field_name, "silver_indicator")
        self.assertEqual(caught.exception.existing_value, "false")
        self.assertEqual(caught.exception.validator_value, "true")
        self.assertEqual(original.canonical_value, "false")

    def test_noncanonical_field_remains_none(self):
        original = _observation("country", "  Canada  ")
        result = self.service.apply_to_observation(original)
        self.assertEqual(result.submitted_value, "  Canada  ")
        self.assertIsNone(result.canonical_value)
        self.assertIsNot(result, original)

    def test_unverifiable_existing_canonical_fails_closed(self):
        original = _observation(
            "country", "Canada", canonical_value="canada")
        with self.assertRaises(ConflictingCanonicalValueError) as caught:
            self.service.apply_to_observation(original)
        self.assertEqual(caught.exception.validator_value, None)
        self.assertEqual(original.canonical_value, "canada")

    def test_every_non_silver_field_never_defaults_to_submitted_value(self):
        examples = {
            "year": "1967",
            "denomination": "25 cents",
            "country": "Canada",
            "monarch": "Elizabeth II",
            "mintmark": "H",
            "series_type": "Type II",
            "banknote_prefix": "AB12345",
            "certification_number": "PCGS12345",
            "variety_keyword": "8 over 9",
        }
        for field_name, submitted in examples.items():
            with self.subTest(field_name=field_name):
                result = apply_canonical_value(
                    _observation(field_name, submitted))
                self.assertEqual(result.submitted_value, submitted)
                self.assertIsNone(result.canonical_value)

    def test_all_fields_and_audit_metadata_are_preserved(self):
        original = _observation("silver_indicator", "YES")
        result = self.service.apply_to_observation(original)
        self.assertEqual(result.schema_version, original.schema_version)
        self.assertEqual(result.source_coin_id, original.source_coin_id)
        self.assertEqual(result.field_name, original.field_name)
        self.assertEqual(result.submitted_value, original.submitted_value)
        self.assertEqual(result.reviewer_id, original.reviewer_id)
        self.assertIs(result.provenance, original.provenance)
        self.assertIs(result.source_type, original.source_type)
        self.assertEqual(result.rationale, original.rationale)
        self.assertIsNone(original.canonical_value)

    def test_unit_1c_validation_errors_propagate_unchanged(self):
        with self.assertRaises(InvalidConfirmedObservationValueError):
            self.service.apply_to_observation(_observation("year", "19A7"))
        for field_name in ("future_field", "grade"):
            with self.subTest(field_name=field_name):
                with self.assertRaises(
                    UnsupportedConfirmedObservationFieldError
                ):
                    self.service.apply_to_observation(
                        _observation(field_name, "value"))

    def test_malformed_input_type_propagates_type_error(self):
        with self.assertRaises(TypeError):
            self.service.apply_to_observation(object())
        with self.assertRaises(TypeError):
            apply_canonical_value(object())

    def test_field_application_is_idempotent(self):
        original = _observation("silver_indicator", "YES")
        once = apply_canonical_value(original)
        twice = apply_canonical_value(once)
        self.assertEqual(once, twice)
        self.assertEqual(once.to_dict(), twice.to_dict())
        self.assertEqual(original.submitted_value, "YES")
        self.assertIsNone(original.canonical_value)

    def test_convenience_helper_matches_service(self):
        original = _observation("silver_indicator", "no")
        self.assertEqual(
            apply_canonical_value(original),
            self.service.apply_to_observation(original),
        )


class SetCanonicalizationTests(unittest.TestCase):
    def setUp(self):
        self.service = ConfirmedObservationCanonicalizer()

    def test_one_observation_set_returns_new_frozen_set(self):
        original = _set(_observation("silver_indicator", "yes"))
        result = self.service.apply_to_set(original)
        self.assertIsInstance(result, ConfirmedObservationSet)
        self.assertIsNot(result, original)
        self.assertFalse(hasattr(result, "__dict__"))
        self.assertEqual(result.observations[0].canonical_value, "true")
        with self.assertRaises(FrozenInstanceError):
            result.reviewer_id = "changed"

    def test_mixed_set_is_deterministic_and_preserves_metadata(self):
        original = _set(
            _observation("year", "1967"),
            _observation("country", "Canada"),
            _observation("silver_indicator", "no"),
        )
        before = original.to_dict()
        result = self.service.apply_to_set(original)
        self.assertEqual(
            tuple(x.field_name for x in result.observations),
            ("country", "silver_indicator", "year"),
        )
        self.assertEqual(
            tuple(x.canonical_value for x in result.observations),
            (None, "false", None),
        )
        self.assertEqual(result.schema_version, original.schema_version)
        self.assertEqual(result.source_coin_id, original.source_coin_id)
        self.assertEqual(result.reviewer_id, original.reviewer_id)
        self.assertEqual(result.review_session_id, original.review_session_id)
        self.assertEqual(result.source_fingerprint, original.source_fingerprint)
        self.assertEqual(original.to_dict(), before)
        self.assertTrue(all(
            new is not old
            for new, old in zip(
                result.observations, original.observations, strict=True)
        ))

    def test_invalid_observation_causes_atomic_failure(self):
        original = _set(
            _observation("country", "Canada"),
            _observation("year", "19A7"),
        )
        captured = None
        with self.assertRaises(InvalidConfirmedObservationValueError):
            captured = self.service.apply_to_set(original)
        self.assertIsNone(captured)
        self.assertEqual(original.observations[0].canonical_value, None)

    def test_canonical_conflict_causes_atomic_failure(self):
        original = _set(
            _observation("country", "Canada"),
            _observation(
                "silver_indicator", "yes", canonical_value="false"),
        )
        captured = None
        with self.assertRaises(ConflictingCanonicalValueError):
            captured = self.service.apply_to_set(original)
        self.assertIsNone(captured)
        self.assertIsNone(original.observations[0].canonical_value)
        self.assertEqual(original.observations[1].canonical_value, "false")

    def test_unverifiable_non_silver_canonical_causes_atomic_failure(self):
        original = _set(
            _observation("country", "Canada", canonical_value="canada"),
            _observation("silver_indicator", "yes"),
        )
        with self.assertRaises(ConflictingCanonicalValueError):
            self.service.apply_to_set(original)
        self.assertIsNone(original.observations[1].canonical_value)

    def test_set_application_is_idempotent_and_serially_deterministic(self):
        original = _set(
            _observation("country", "Canada"),
            _observation("silver_indicator", "TRUE"),
        )
        once = apply_canonical_values(original)
        twice = apply_canonical_values(once)
        self.assertEqual(once, twice)
        self.assertEqual(once.to_dict(), twice.to_dict())
        equivalent = apply_canonical_values(_set(
            _observation("country", "Canada"),
            _observation("silver_indicator", "TRUE"),
        ))
        self.assertEqual(once.to_dict(), equivalent.to_dict())

    def test_convenience_helper_matches_service(self):
        original = _set(_observation("silver_indicator", "false"))
        self.assertEqual(
            apply_canonical_values(original),
            self.service.apply_to_set(original),
        )

    def test_malformed_set_type_propagates_type_error(self):
        with self.assertRaises(TypeError):
            self.service.apply_to_set(object())
        with self.assertRaises(TypeError):
            apply_canonical_values(object())


class ErrorAndArchitectureTests(unittest.TestCase):
    def test_error_hierarchy_is_narrow(self):
        self.assertTrue(issubclass(
            ConflictingCanonicalValueError,
            ConfirmedObservationCanonicalizationError,
        ))

    def test_service_is_stateless(self):
        service = ConfirmedObservationCanonicalizer()
        self.assertEqual(ConfirmedObservationCanonicalizer.__slots__, ())
        self.assertFalse(hasattr(service, "__dict__"))

    def test_module_has_no_forbidden_integrations_or_mapper_invocation(self):
        path = Path(inspect.getfile(ConfirmedObservationCanonicalizer))
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
        self.assertNotIn("ALLOWED_OCR_FIELDS", source)


if __name__ == "__main__":
    unittest.main()
