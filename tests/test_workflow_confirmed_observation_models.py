"""Tests for collection-independent confirmed-observation contracts."""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError
import importlib
import inspect
import json
import unittest

from tests.frozen_dataclass_compat import (
    assert_frozen_slotted_assignment_rejected,
)

from capture_import.workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedFieldObservation,
    ConfirmedObservationProvenance,
    ConfirmedObservationSet,
    ConfirmedObservationSource,
    UnsupportedConfirmedObservationSchemaVersion,
)


_SCHEMA = CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION
_FINGERPRINT = "a" * 64
_MODULE = "capture_import.workflow_confirmed_observation_models"


def _provenance(
    *,
    provider_id: str = "provider-1",
    image_role: str = "front",
    artifact_key: str = "crop-front",
    source_value: str = "1967",
    confidence_score: float | None = 91.5,
    evidence: tuple[str, ...] = ("date glyphs visible",),
) -> ConfirmedObservationProvenance:
    return ConfirmedObservationProvenance(
        provider_id=provider_id,
        image_role=image_role,
        artifact_key=artifact_key,
        source_value=source_value,
        confidence_score=confidence_score,
        evidence=evidence,
    )


def _observation(
    *,
    field_name: str = "year",
    submitted_value: str = "1967",
    canonical_value: str | None = None,
    source_coin_id: str = "coin-1",
    reviewer_id: str = "reviewer-1",
    provenance: tuple[ConfirmedObservationProvenance, ...] | None = None,
    source_type: ConfirmedObservationSource = (
        ConfirmedObservationSource.OCR_REVIEW
    ),
    rationale: str | None = "Human-confirmed date.",
    schema_version: str = _SCHEMA,
) -> ConfirmedFieldObservation:
    selected = (
        (_provenance(source_value=submitted_value),)
        if provenance is None
        else provenance
    )
    return ConfirmedFieldObservation(
        schema_version=schema_version,
        source_coin_id=source_coin_id,
        field_name=field_name,
        submitted_value=submitted_value,
        canonical_value=canonical_value,
        reviewer_id=reviewer_id,
        provenance=selected,
        source_type=source_type,
        rationale=rationale,
    )


def _set(
    observations: tuple[ConfirmedFieldObservation, ...] | None = None,
    *,
    source_coin_id: str = "coin-1",
    reviewer_id: str = "reviewer-1",
    review_session_id: str | None = "review-session-1",
    source_fingerprint: str | None = _FINGERPRINT,
    schema_version: str = _SCHEMA,
) -> ConfirmedObservationSet:
    return ConfirmedObservationSet(
        schema_version=schema_version,
        source_coin_id=source_coin_id,
        reviewer_id=reviewer_id,
        observations=(
            (_observation(),)
            if observations is None
            else observations
        ),
        review_session_id=review_session_id,
        source_fingerprint=source_fingerprint,
    )


class ConfirmedObservationConstructionTests(unittest.TestCase):
    def test_valid_single_observation_and_aggregate(self) -> None:
        observation = _observation()
        aggregate = _set((observation,))

        observation.validate()
        aggregate.validate()

        self.assertEqual(observation.submitted_value, "1967")
        self.assertEqual(aggregate.observations, (observation,))

    def test_optional_canonical_value_is_not_silently_defaulted(self) -> None:
        absent = _observation(canonical_value=None)
        present = _observation(
            submitted_value="CANADA",
            canonical_value="Canada",
            field_name="country",
        )

        absent.validate()
        present.validate()

        self.assertIsNone(absent.canonical_value)
        self.assertEqual(present.submitted_value, "CANADA")
        self.assertEqual(present.canonical_value, "Canada")

    def test_optional_rationale_preserves_exact_text(self) -> None:
        exact = "  Reviewer retained deliberate spacing.  "
        observation = _observation(rationale=exact)
        without = _observation(rationale=None)

        observation.validate()
        without.validate()

        self.assertEqual(observation.rationale, exact)
        self.assertIsNone(without.rationale)

    def test_provenance_preserves_confidence_and_evidence(self) -> None:
        provenance = _provenance(
            confidence_score=87.25,
            evidence=("first clue", "second clue"),
        )
        observation = _observation(provenance=(provenance,))

        observation.validate()

        self.assertIs(observation.provenance[0], provenance)
        self.assertEqual(observation.provenance[0].confidence_score, 87.25)
        self.assertEqual(
            observation.provenance[0].evidence,
            ("first clue", "second clue"),
        )

    def test_manual_entry_may_have_no_ocr_provenance(self) -> None:
        observation = _observation(
            source_type=ConfirmedObservationSource.MANUAL_ENTRY,
            provenance=(),
        )

        observation.validate()

        self.assertEqual(observation.provenance, ())

    def test_ocr_review_requires_provenance(self) -> None:
        with self.assertRaisesRegex(ValueError, "require provenance"):
            _observation(provenance=()).validate()

    def test_source_linkage_is_optional_and_preserved(self) -> None:
        linked = _set()
        manual = _set(
            review_session_id=None,
            source_fingerprint=None,
        )

        linked.validate()
        manual.validate()

        self.assertEqual(linked.review_session_id, "review-session-1")
        self.assertEqual(linked.source_fingerprint, _FINGERPRINT)
        self.assertIsNone(manual.review_session_id)
        self.assertIsNone(manual.source_fingerprint)

    def test_multiple_observations_require_deterministic_order(self) -> None:
        country = _observation(
            field_name="country",
            submitted_value="Canada",
            provenance=(
                _provenance(
                    artifact_key="country",
                    source_value="Canada",
                ),
            ),
        )
        year = _observation()
        aggregate = _set((country, year))

        aggregate.validate()

        self.assertEqual(
            tuple(item.field_name for item in aggregate.observations),
            ("country", "year"),
        )
        with self.assertRaisesRegex(ValueError, "deterministic"):
            _set((year, country)).validate()

    def test_provenance_requires_deterministic_order(self) -> None:
        first = _provenance(provider_id="a", artifact_key="a")
        second = _provenance(provider_id="b", artifact_key="b")

        _observation(provenance=(first, second)).validate()

        with self.assertRaisesRegex(ValueError, "deterministic"):
            _observation(provenance=(second, first)).validate()

    def test_source_enum_is_narrow_and_explicit(self) -> None:
        self.assertEqual(
            tuple(item.value for item in ConfirmedObservationSource),
            ("OCR_REVIEW", "MANUAL_ENTRY"),
        )


class ConfirmedObservationValidationTests(unittest.TestCase):
    def test_grade_is_rejected_case_and_whitespace_insensitively(self) -> None:
        for value in ("grade", "Grade", " grade "):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "grade"):
                    _observation(field_name=value).validate()

    def test_blank_field_level_values_are_rejected(self) -> None:
        cases = (
            ("source_coin_id", " "),
            ("field_name", "\t"),
            ("submitted_value", ""),
            ("reviewer_id", "  "),
        )
        for name, value in cases:
            with self.subTest(name=name):
                arguments = {name: value}
                with self.assertRaises((TypeError, ValueError)):
                    _observation(**arguments).validate()

    def test_blank_optional_values_are_rejected_when_present(self) -> None:
        with self.assertRaisesRegex(ValueError, "canonical_value"):
            _observation(canonical_value=" ").validate()
        with self.assertRaisesRegex(ValueError, "rationale"):
            _observation(rationale="\t").validate()
        with self.assertRaisesRegex(ValueError, "review_session_id"):
            _set(review_session_id=" ").validate()

    def test_unresolved_and_deferred_markers_cannot_masquerade_as_values(
        self,
    ) -> None:
        for marker in (
            "DEFER",
            " deferred ",
            "missing",
            "UNRESOLVED",
            "reject",
            "REJECTED",
        ):
            with self.subTest(marker=marker):
                with self.assertRaisesRegex(ValueError, "marker"):
                    _observation(submitted_value=marker).validate()
                with self.assertRaisesRegex(ValueError, "marker"):
                    _observation(canonical_value=marker).validate()

    def test_duplicate_fields_are_rejected(self) -> None:
        first = _observation()
        second = _observation(
            provenance=(
                _provenance(provider_id="other", artifact_key="other"),
            )
        )

        with self.assertRaisesRegex(ValueError, "Duplicate"):
            _set((first, second)).validate()

    def test_mixed_source_coin_ids_are_rejected(self) -> None:
        observations = (
            _observation(field_name="country", submitted_value="Canada"),
            _observation(
                field_name="year",
                source_coin_id="coin-2",
            ),
        )

        with self.assertRaisesRegex(ValueError, "source_coin_id"):
            _set(observations).validate()

    def test_mixed_reviewer_ids_are_rejected(self) -> None:
        observations = (
            _observation(field_name="country", submitted_value="Canada"),
            _observation(
                field_name="year",
                reviewer_id="reviewer-2",
            ),
        )

        with self.assertRaisesRegex(ValueError, "reviewer_id"):
            _set(observations).validate()

    def test_empty_aggregate_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            _set(()).validate()

    def test_duplicate_provenance_is_rejected(self) -> None:
        provenance = _provenance()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            _observation(
                provenance=(provenance, provenance)
            ).validate()

    def test_malformed_nested_types_are_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "provenance"):
            _observation(provenance=(object(),)).validate()
        with self.assertRaisesRegex(TypeError, "observations"):
            _set((object(),)).validate()

    def test_invalid_confidence_is_rejected(self) -> None:
        for value in (True, float("nan"), -0.1, 100.1):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    _provenance(confidence_score=value).validate()

    def test_source_fingerprint_is_optional_opaque_and_nonblank(self) -> None:
        for value in (
            "external-fingerprint-v2",
            "A" * 64,
            "provider:opaque/source-identity",
        ):
            with self.subTest(value=value[:12]):
                aggregate = _set(source_fingerprint=value)
                aggregate.validate()
                self.assertEqual(aggregate.source_fingerprint, value)
        with self.assertRaisesRegex(ValueError, "source_fingerprint"):
            _set(source_fingerprint=" ").validate()

    def test_schema_version_is_required_and_unsupported_is_distinct(
        self,
    ) -> None:
        for value in ("", "2", "future"):
            with self.subTest(value=value):
                with self.assertRaises(
                    UnsupportedConfirmedObservationSchemaVersion
                ):
                    _observation(schema_version=value).validate()
                with self.assertRaises(
                    UnsupportedConfirmedObservationSchemaVersion
                ):
                    _set(schema_version=value).validate()


class ConfirmedObservationSerializationTests(unittest.TestCase):
    def test_to_dict_is_json_safe_and_canonical(self) -> None:
        payload = _set().to_dict()

        json.dumps(payload, allow_nan=False)

        self.assertIsInstance(payload["observations"], list)
        nested = payload["observations"][0]
        self.assertIsInstance(nested["provenance"], list)
        self.assertIsInstance(nested["provenance"][0]["evidence"], list)
        self.assertEqual(nested["source_type"], "OCR_REVIEW")
        self.assertEqual(nested["canonical_value"], None)

    def test_round_trip_preserves_exact_values(self) -> None:
        aggregate = _set(
            (
                _observation(
                    submitted_value="CANADA",
                    canonical_value="Canada",
                    field_name="country",
                    rationale="  Exact rationale.  ",
                    provenance=(
                        _provenance(
                            artifact_key="country",
                            source_value="CANADA",
                            evidence=("legend",),
                        ),
                    ),
                ),
            )
        )

        restored = ConfirmedObservationSet.from_dict(
            aggregate.to_dict()
        )

        self.assertEqual(restored, aggregate)
        self.assertEqual(
            restored.observations[0].submitted_value,
            "CANADA",
        )
        self.assertEqual(
            restored.observations[0].canonical_value,
            "Canada",
        )
        self.assertEqual(
            restored.observations[0].rationale,
            "  Exact rationale.  ",
        )

    def test_equivalent_values_serialize_identically(self) -> None:
        first = _set()
        second = deepcopy(first)

        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(
            json.dumps(
                first.to_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            json.dumps(
                second.to_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )

    def test_unknown_and_missing_fields_are_rejected_at_every_level(
        self,
    ) -> None:
        base = _set().to_dict()
        locations = (
            (),
            ("observations", 0),
            ("observations", 0, "provenance", 0),
        )
        for location in locations:
            with self.subTest(location=location):
                unknown = deepcopy(base)
                target = self._at(unknown, location)
                target["unknown"] = True
                with self.assertRaisesRegex(ValueError, "unknown"):
                    ConfirmedObservationSet.from_dict(unknown)

                missing = deepcopy(base)
                target = self._at(missing, location)
                target.pop(next(iter(target)))
                with self.assertRaisesRegex(ValueError, "missing"):
                    ConfirmedObservationSet.from_dict(missing)

    def test_missing_canonical_value_is_not_defaulted(self) -> None:
        payload = _set().to_dict()
        payload["observations"][0].pop("canonical_value")

        with self.assertRaisesRegex(ValueError, "missing"):
            ConfirmedObservationSet.from_dict(payload)

    def test_unsupported_future_schema_fails_before_nested_repair(
        self,
    ) -> None:
        payload = _set().to_dict()
        payload["schema_version"] = "2"
        payload["observations"] = "malformed"

        with self.assertRaises(
            UnsupportedConfirmedObservationSchemaVersion
        ):
            ConfirmedObservationSet.from_dict(payload)

    def test_malformed_nested_payload_is_rejected(self) -> None:
        payload = _set().to_dict()
        payload["observations"][0]["provenance"][0] = "invalid"

        with self.assertRaises(TypeError):
            ConfirmedObservationSet.from_dict(payload)

    def test_tuples_are_required_in_memory_and_lists_on_wire(self) -> None:
        with self.assertRaisesRegex(TypeError, "evidence"):
            _provenance(evidence=["not", "tuple"]).validate()
        with self.assertRaisesRegex(TypeError, "provenance"):
            _observation(provenance=[_provenance()]).validate()
        with self.assertRaisesRegex(TypeError, "observations"):
            _set([_observation()]).validate()

        payload = _set().to_dict()
        payload["observations"] = tuple(payload["observations"])
        with self.assertRaisesRegex(TypeError, "list"):
            ConfirmedObservationSet.from_dict(payload)

    def test_input_mapping_is_not_mutated(self) -> None:
        payload = _set().to_dict()
        before = deepcopy(payload)

        ConfirmedObservationSet.from_dict(payload)

        self.assertEqual(payload, before)

    @staticmethod
    def _at(payload, location):
        current = payload
        for item in location:
            current = current[item]
        return current


class ConfirmedObservationImmutabilityAndArchitectureTests(
    unittest.TestCase
):
    def test_contracts_are_frozen_and_slotted(self) -> None:
        values = (
            _provenance(),
            _observation(),
            _set(),
        )
        for value in values:
            with self.subTest(value=type(value).__name__):
                field_name = next(iter(value.__dataclass_fields__))
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, field_name, object())
                with assert_frozen_slotted_assignment_rejected(self, value):
                    value.unexpected = object()

    def test_caller_owned_inputs_are_not_mutated(self) -> None:
        provenance = (_provenance(),)
        observations = (_observation(provenance=provenance),)
        before = (provenance, observations)

        aggregate = _set(observations)
        aggregate.validate()
        aggregate.to_dict()

        self.assertEqual((provenance, observations), before)
        self.assertIs(aggregate.observations, observations)

    def test_import_boundary_has_no_out_of_scope_dependencies(self) -> None:
        module = importlib.import_module(_MODULE)
        tree = ast.parse(inspect.getsource(module))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        forbidden_fragments = (
            "coin_collection",
            "collection_manager",
            "confirmed_observations",
            "persistence",
            "repository",
            "desktop",
            "tkinter",
            "pathlib",
            "uuid",
            "datetime",
            "workflow_ocr",
        )
        self.assertFalse(
            any(
                fragment in imported
                for imported in imports
                for fragment in forbidden_fragments
            )
        )
        self.assertNotIn("os", imports)

    def test_module_has_no_mapping_storage_or_mutation_commands(self) -> None:
        module = importlib.import_module(_MODULE)
        public_functions = {
            name
            for name, value in vars(module).items()
            if (
                inspect.isfunction(value)
                and value.__module__ == _MODULE
                and not name.startswith("_")
            )
        }
        source = inspect.getsource(module)

        self.assertEqual(public_functions, set())
        for fragment in (
            "collection_record_id",
            "collection_field",
            "overwrite",
            "map_projection",
            "save(",
            "mutate",
            "timestamp",
            "created_at",
            "observation_id",
        ):
            self.assertNotIn(fragment, source)

    def test_grade_has_only_an_explicit_rejection_path(self) -> None:
        source = inspect.getsource(
            ConfirmedFieldObservation.validate
        ).lower()
        self.assertIn('== "grade"', source)
        self.assertNotIn("grade:", source)


if __name__ == "__main__":
    unittest.main()
