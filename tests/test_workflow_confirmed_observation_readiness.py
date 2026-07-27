"""Tests for pure confirmed-observation readiness composition."""
from __future__ import annotations

import ast
import inspect
import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from capture_import.workflow_confirmed_observation_canonicalization import (
    ConflictingCanonicalValueError,
)
from capture_import.workflow_confirmed_observation_compatibility import (
    ConfirmedObservationCompatibilityStatus,
    IncompatibleConfirmedObservationError,
)
from capture_import.workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedFieldObservation,
    ConfirmedObservationProvenance,
    ConfirmedObservationSet,
    ConfirmedObservationSource,
)
from capture_import.workflow_confirmed_observation_readiness import (
    ConfirmedObservationReadinessAssessor,
    ConfirmedObservationReadinessResult,
    ConfirmedObservationReadinessStatus,
    assess_confirmed_observation_readiness,
    require_confirmed_observation_readiness,
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


def _observation(field_name, value, *, canonical_value=None):
    return ConfirmedFieldObservation(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id="coin-1",
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


class SuccessfulReadinessTests(unittest.TestCase):
    def setUp(self):
        self.assessor = ConfirmedObservationReadinessAssessor()

    def test_one_valid_noncanonical_field_is_ready(self):
        source = _set(_observation("year", "1967"))
        result = self.assessor.assess(source)
        self.assertIs(result.status, ConfirmedObservationReadinessStatus.READY)
        self.assertTrue(result.is_ready)
        self.assertIsNone(
            result.canonicalized_observation_set.observations[0].canonical_value
        )
        self.assertIs(
            result.compatibility_results[0].status,
            ConfirmedObservationCompatibilityStatus.NOT_EVALUATED,
        )

    def test_silver_true_and_false_become_canonically_ready(self):
        for submitted, expected in (("YES", "true"), ("NON-SILVER", "false")):
            with self.subTest(submitted=submitted):
                source = _set(_observation("silver_indicator", submitted))
                result = self.assessor.assess(source)
                observation = result.canonicalized_observation_set.observations[0]
                self.assertEqual(observation.submitted_value, submitted)
                self.assertEqual(observation.canonical_value, expected)
                self.assertIsNone(source.observations[0].canonical_value)

    def test_mixed_fields_apply_only_explicit_silver_canonical(self):
        source = _set(
            _observation("country", "  Canada  "),
            _observation("denomination", "25 cents"),
            _observation("silver_indicator", "yes"),
            _observation("year", "1967"),
        )
        result = assess_confirmed_observation_readiness(source)
        observations = result.canonicalized_observation_set.observations
        self.assertEqual(
            tuple(x.field_name for x in observations),
            ("country", "denomination", "silver_indicator", "year"),
        )
        self.assertEqual(
            tuple(x.canonical_value for x in observations),
            (None, None, "true", None),
        )
        self.assertEqual(observations[0].submitted_value, "  Canada  ")

    def test_compatible_monarch_year_is_ready(self):
        source = _set(
            _observation("monarch", "George VI"),
            _observation("year", "1945"),
        )
        result = self.assessor.assess(source)
        self.assertIs(
            result.compatibility_results[0].status,
            ConfirmedObservationCompatibilityStatus.COMPATIBLE,
        )
        self.assertTrue(result.is_ready)

    def test_unknown_monarch_not_evaluated_still_is_ready(self):
        source = _set(
            _observation("monarch", "Unknown Sovereign"),
            _observation("year", "1945"),
        )
        result = self.assessor.assess(source)
        self.assertIs(
            result.compatibility_results[0].status,
            ConfirmedObservationCompatibilityStatus.NOT_EVALUATED,
        )
        self.assertTrue(result.is_ready)

    def test_partial_set_still_is_ready(self):
        source = _set(_observation("country", "Canada"))
        result = self.assessor.assess(source)
        self.assertTrue(result.is_ready)
        self.assertIs(
            result.compatibility_results[0].status,
            ConfirmedObservationCompatibilityStatus.NOT_EVALUATED,
        )

    def test_deferred_compatibility_domains_do_not_block_readiness(self):
        source = _set(
            _observation("country", "Canada"),
            _observation("denomination", "1 cent"),
            _observation("year", "1859"),
        )
        result = self.assessor.assess(source)
        self.assertTrue(result.is_ready)
        self.assertIs(
            result.compatibility_results[0].status,
            ConfirmedObservationCompatibilityStatus.NOT_EVALUATED,
        )

    def test_aggregate_metadata_submitted_values_and_provenance_are_preserved(self):
        source = _set(
            _observation("country", "Canada"),
            _observation("silver_indicator", "yes"),
        )
        before = source.to_dict()
        result = self.assessor.assess(source)
        ready = result.canonicalized_observation_set
        self.assertIsNot(ready, source)
        self.assertEqual(ready.schema_version, source.schema_version)
        self.assertEqual(ready.source_coin_id, source.source_coin_id)
        self.assertEqual(ready.reviewer_id, source.reviewer_id)
        self.assertEqual(ready.review_session_id, source.review_session_id)
        self.assertEqual(ready.source_fingerprint, source.source_fingerprint)
        self.assertEqual(result.source_coin_id, source.source_coin_id)
        self.assertEqual(source.to_dict(), before)
        for original, canonicalized in zip(
            source.observations, ready.observations, strict=True
        ):
            self.assertEqual(
                canonicalized.submitted_value,
                original.submitted_value,
            )
            self.assertIs(canonicalized.provenance, original.provenance)
            self.assertEqual(canonicalized.rationale, original.rationale)
            self.assertEqual(canonicalized.reviewer_id, original.reviewer_id)
            self.assertIs(canonicalized.source_type, original.source_type)

    def test_matching_existing_canonical_remains_stable(self):
        source = _set(_observation(
            "silver_indicator", "YES", canonical_value="true"))
        result = self.assessor.assess(source)
        self.assertEqual(
            result.canonicalized_observation_set.observations[0].canonical_value,
            "true",
        )
        self.assertEqual(source.observations[0].canonical_value, "true")

    def test_strict_helper_returns_only_new_canonicalized_set(self):
        source = _set(_observation("silver_indicator", "no"))
        ready = require_confirmed_observation_readiness(source)
        self.assertIsInstance(ready, ConfirmedObservationSet)
        self.assertIsNot(ready, source)
        self.assertEqual(ready.observations[0].canonical_value, "false")
        self.assertIsNone(source.observations[0].canonical_value)


class FailurePropagationTests(unittest.TestCase):
    def setUp(self):
        self.assessor = ConfirmedObservationReadinessAssessor()

    def test_invalid_value_propagates_unit_1c_error(self):
        source = _set(_observation("year", "19A7"))
        with self.assertRaises(InvalidConfirmedObservationValueError):
            self.assessor.assess(source)

    def test_unsupported_field_and_grade_propagate_unit_1c_error(self):
        for field_name in ("future_field", "grade"):
            with self.subTest(field_name=field_name):
                with self.assertRaises(
                    UnsupportedConfirmedObservationFieldError
                ):
                    self.assessor.assess(
                        _set(_observation(field_name, "value"))
                    )

    def test_conflicting_silver_canonical_propagates_unit_1d_error(self):
        source = _set(_observation(
            "silver_indicator", "yes", canonical_value="false"))
        with self.assertRaises(ConflictingCanonicalValueError):
            self.assessor.assess(source)
        self.assertEqual(source.observations[0].canonical_value, "false")

    def test_unverifiable_non_silver_canonical_propagates_unit_1d_error(self):
        source = _set(_observation(
            "country", "Canada", canonical_value="canada"))
        with self.assertRaises(ConflictingCanonicalValueError):
            self.assessor.assess(source)
        self.assertEqual(source.observations[0].canonical_value, "canada")

    def test_incompatible_monarch_year_propagates_unit_1e_error(self):
        source = _set(
            _observation("monarch", "George VI"),
            _observation("year", "1967"),
        )
        with self.assertRaises(IncompatibleConfirmedObservationError):
            self.assessor.assess(source)
        self.assertEqual(source.observations[0].submitted_value, "George VI")
        self.assertEqual(source.observations[1].submitted_value, "1967")

    def test_failure_returns_no_readiness_result_or_source_mutation(self):
        source = _set(
            _observation("country", "Canada"),
            _observation("year", "19A7"),
        )
        before = source
        captured = None
        with self.assertRaises(InvalidConfirmedObservationValueError):
            captured = self.assessor.assess(source)
        self.assertIsNone(captured)
        self.assertIs(source, before)
        self.assertEqual(source.observations[0].canonical_value, None)

    def test_caller_type_errors_propagate(self):
        with self.assertRaises(TypeError):
            self.assessor.assess(object())
        with self.assertRaises(TypeError):
            assess_confirmed_observation_readiness(object())
        with self.assertRaises(TypeError):
            require_confirmed_observation_readiness(object())


class DeterminismAndContractTests(unittest.TestCase):
    def test_assessment_is_idempotent(self):
        source = _set(
            _observation("monarch", "George VI"),
            _observation("silver_indicator", "YES"),
            _observation("year", "1945"),
        )
        once = assess_confirmed_observation_readiness(source)
        twice = assess_confirmed_observation_readiness(
            once.canonicalized_observation_set
        )
        self.assertEqual(once, twice)
        self.assertEqual(once.to_dict(), twice.to_dict())
        self.assertIsNone(source.observations[1].canonical_value)

    def test_equivalent_inputs_serialize_identically(self):
        first = assess_confirmed_observation_readiness(
            _set(_observation("silver_indicator", "TRUE")))
        second = assess_confirmed_observation_readiness(
            _set(_observation("silver_indicator", "TRUE")))
        self.assertEqual(first, second)
        self.assertEqual(
            json.dumps(first.to_dict(), sort_keys=True),
            json.dumps(second.to_dict(), sort_keys=True),
        )

    def test_result_is_frozen_slotted_json_safe_and_minimal(self):
        result = assess_confirmed_observation_readiness(
            _set(_observation("year", "1967")))
        self.assertIsInstance(result, ConfirmedObservationReadinessResult)
        self.assertFalse(hasattr(result, "__dict__"))
        self.assertEqual(
            tuple(ConfirmedObservationReadinessResult.__dataclass_fields__),
            (
                "source_coin_id",
                "status",
                "canonicalized_observation_set",
                "compatibility_results",
            ),
        )
        serialized = json.loads(json.dumps(result.to_dict()))
        self.assertEqual(serialized["status"], "READY")
        self.assertEqual(serialized["source_coin_id"], "coin-1")
        with self.assertRaises(FrozenInstanceError):
            result.source_coin_id = "changed"

    def test_status_has_no_fake_not_ready_state(self):
        self.assertEqual(
            tuple(ConfirmedObservationReadinessStatus),
            (ConfirmedObservationReadinessStatus.READY,),
        )

    def test_assessor_is_stateless(self):
        assessor = ConfirmedObservationReadinessAssessor()
        self.assertEqual(ConfirmedObservationReadinessAssessor.__slots__, ())
        self.assertFalse(hasattr(assessor, "__dict__"))


class ArchitectureTests(unittest.TestCase):
    def test_module_is_composition_only(self):
        path = Path(inspect.getfile(ConfirmedObservationReadinessAssessor))
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {alias.name for node in ast.walk(tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom))
                    for alias in node.names}
        for fragment in (
            "collection", "persistence", "mapper", "desktop", "gui",
            "tkinter", "pathlib", "os", "environment", "requests",
            "urllib", "uuid", "datetime",
        ):
            with self.subTest(fragment=fragment):
                self.assertFalse(any(fragment in name.casefold()
                                     for name in imported), imported)
        self.assertNotIn("ALLOWED_OCR_FIELDS", source)
        self.assertNotIn("MONARCH_YEAR_RANGES", source)
        self.assertNotIn("MappingProxyType", source)
        self.assertNotIn("map_review_session", source)

    def test_only_unit_1d_and_unit_1e_services_are_invoked(self):
        source = inspect.getsource(ConfirmedObservationReadinessAssessor.assess)
        self.assertIn("apply_canonical_values", source)
        self.assertIn("validate_confirmed_observation_compatibility", source)
        self.assertNotIn("validate_confirmed_observation_set", source)


if __name__ == "__main__":
    unittest.main()
