"""Tests for immutable collection change-plan contracts."""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import importlib
import inspect
import json
from pathlib import Path
import unittest

from capture_import.workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedFieldObservation,
    ConfirmedObservationProvenance,
    ConfirmedObservationSource,
)
from collection_management.workflow_collection_change_plan_models import (
    CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
    CollectionChangeApprovalRequirement,
    CollectionChangeOperation,
    CollectionChangePlan,
    CollectionChangeReasonCode,
    CollectionFieldChangeProposal,
    CollectionRecordReference,
    UnsupportedCollectionChangePlanSchemaVersion,
)


_SCHEMA = CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION
_MODULE = (
    "collection_management.workflow_collection_change_plan_models"
)


def _provenance(
    *,
    source_value: str = "Canada",
) -> tuple[ConfirmedObservationProvenance, ...]:
    return (
        ConfirmedObservationProvenance(
            provider_id="test-ocr",
            image_role="front",
            artifact_key="crop-front",
            source_value=source_value,
            confidence_score=92.5,
            evidence=("visible legend",),
        ),
    )


def _observation(
    *,
    field_name: str = "country",
    submitted_value: str = "Canada",
    canonical_value: str | None = None,
    source_coin_id: str = "source-coin-1",
    reviewer_id: str = "collector-1",
) -> ConfirmedFieldObservation:
    return ConfirmedFieldObservation(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id=source_coin_id,
        field_name=field_name,
        submitted_value=submitted_value,
        canonical_value=canonical_value,
        reviewer_id=reviewer_id,
        provenance=_provenance(source_value=submitted_value),
        source_type=ConfirmedObservationSource.OCR_REVIEW,
        rationale="Confirmed by collector.",
    )


def _operation_defaults(
    operation: CollectionChangeOperation,
    source_value: str,
) -> dict[str, object]:
    if operation is CollectionChangeOperation.ADD:
        return {
            "current_value": None,
            "proposed_value": source_value,
            "approval_requirement": (
                CollectionChangeApprovalRequirement.REQUIRED
            ),
            "reason_code": CollectionChangeReasonCode.NEW_VALUE,
        }
    if operation is CollectionChangeOperation.UPDATE:
        return {
            "current_value": "Old value",
            "proposed_value": source_value,
            "approval_requirement": (
                CollectionChangeApprovalRequirement.REQUIRED
            ),
            "reason_code": CollectionChangeReasonCode.DIFFERENT_VALUE,
        }
    if operation is CollectionChangeOperation.CLEAR:
        return {
            "current_value": "Old value",
            "proposed_value": None,
            "approval_requirement": (
                CollectionChangeApprovalRequirement.REQUIRED
            ),
            "reason_code": CollectionChangeReasonCode.EXPLICIT_CLEAR,
        }
    if operation is CollectionChangeOperation.NO_CHANGE:
        return {
            "current_value": source_value,
            "proposed_value": source_value,
            "approval_requirement": (
                CollectionChangeApprovalRequirement.NOT_REQUIRED
            ),
            "reason_code": CollectionChangeReasonCode.EQUIVALENT_VALUE,
        }
    return {
        "current_value": "Old value",
        "proposed_value": source_value,
        "approval_requirement": (
            CollectionChangeApprovalRequirement.REQUIRED
        ),
        "reason_code": (
            CollectionChangeReasonCode.EXISTING_VALUE_CONFLICT
        ),
    }


def _proposal(
    operation: CollectionChangeOperation = CollectionChangeOperation.ADD,
    *,
    observation: ConfirmedFieldObservation | None = None,
    target_record: CollectionRecordReference | None = None,
    target_field: str | None = None,
    **overrides,
) -> CollectionFieldChangeProposal:
    source = observation or _observation()
    source_value = source.canonical_value or source.submitted_value
    values = _operation_defaults(operation, source_value)
    values.update(overrides)
    return CollectionFieldChangeProposal(
        schema_version=values.pop("schema_version", _SCHEMA),
        target_record=target_record or CollectionRecordReference("record-1"),
        target_field=(
            source.field_name if target_field is None else target_field
        ),
        operation=operation,
        source_observation=source,
        rationale=values.pop("rationale", "Bounded planning reason."),
        **values,
    )


def _plan(
    proposals: tuple[CollectionFieldChangeProposal, ...] | None = None,
    *,
    target_record: CollectionRecordReference | None = None,
    source_coin_id: str = "source-coin-1",
    review_session_id: str | None = "review-session-1",
    source_fingerprint: str | None = "opaque-source-fingerprint",
    schema_version: str = _SCHEMA,
) -> CollectionChangePlan:
    selected = (_proposal(),) if proposals is None else proposals
    return CollectionChangePlan(
        schema_version=schema_version,
        target_record=target_record or CollectionRecordReference("record-1"),
        source_coin_id=source_coin_id,
        proposals=selected,
        review_session_id=review_session_id,
        source_fingerprint=source_fingerprint,
    )


class CollectionRecordReferenceTests(unittest.TestCase):
    def test_valid_reference_is_exact_and_round_trips(self) -> None:
        reference = CollectionRecordReference("  caller record id  ")

        reference.validate()
        restored = CollectionRecordReference.from_dict(reference.to_dict())

        self.assertEqual(restored, reference)
        self.assertEqual(restored.record_id, "  caller record id  ")

    def test_blank_or_malformed_record_id_is_rejected(self) -> None:
        for value in ("", " ", "\t", "bad\nid", "x" * 16_385, 1):
            with self.subTest(value=repr(value)[:20]):
                with self.assertRaises((TypeError, ValueError)):
                    CollectionRecordReference(value).validate()

    def test_reference_shape_does_not_invent_record_type_or_scope(self) -> None:
        self.assertEqual(
            tuple(CollectionRecordReference.__dataclass_fields__),
            ("record_id",),
        )
        payload = CollectionRecordReference("record-1").to_dict()
        self.assertEqual(payload, {"record_id": "record-1"})

    def test_reference_deserialization_is_closed(self) -> None:
        for payload in (
            {},
            {"record_id": "record-1", "record_type": "coin"},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    CollectionRecordReference.from_dict(payload)


class EnumVocabularyTests(unittest.TestCase):
    def test_operation_vocabulary_is_exact(self) -> None:
        self.assertEqual(
            tuple(item.value for item in CollectionChangeOperation),
            ("ADD", "UPDATE", "CLEAR", "NO_CHANGE", "CONFLICT"),
        )

    def test_approval_vocabulary_cannot_express_approval(self) -> None:
        self.assertEqual(
            tuple(
                item.value
                for item in CollectionChangeApprovalRequirement
            ),
            ("NOT_REQUIRED", "REQUIRED"),
        )

    def test_reason_vocabulary_is_exact(self) -> None:
        self.assertEqual(
            tuple(item.value for item in CollectionChangeReasonCode),
            (
                "NEW_VALUE",
                "DIFFERENT_VALUE",
                "EXPLICIT_CLEAR",
                "EQUIVALENT_VALUE",
                "EXISTING_VALUE_CONFLICT",
            ),
        )


class OperationInvariantTests(unittest.TestCase):
    def test_each_operation_has_one_valid_shape(self) -> None:
        for operation in CollectionChangeOperation:
            with self.subTest(operation=operation):
                proposal = _proposal(operation)
                proposal.validate()
                self.assertIs(proposal.operation, operation)

    def test_add_requires_absent_current_and_present_proposed(self) -> None:
        invalid = (
            {"current_value": ""},
            {"current_value": "existing"},
            {"proposed_value": None},
        )
        for overrides in invalid:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ValueError, "ADD"):
                    _proposal(
                        CollectionChangeOperation.ADD,
                        **overrides,
                    ).validate()

    def test_update_requires_present_exactly_different_values(self) -> None:
        invalid = (
            {"current_value": None},
            {"proposed_value": None},
            {"current_value": "Canada"},
        )
        for overrides in invalid:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ValueError, "UPDATE"):
                    _proposal(
                        CollectionChangeOperation.UPDATE,
                        **overrides,
                    ).validate()

    def test_clear_requires_present_current_and_absent_proposed(self) -> None:
        invalid = (
            {"current_value": None},
            {"proposed_value": "Canada"},
        )
        for overrides in invalid:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ValueError, "CLEAR"):
                    _proposal(
                        CollectionChangeOperation.CLEAR,
                        **overrides,
                    ).validate()

    def test_no_change_requires_present_exact_equality(self) -> None:
        invalid = (
            {"current_value": None},
            {"proposed_value": None},
            {"current_value": "canada"},
            {"current_value": " Canada"},
        )
        for overrides in invalid:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ValueError, "NO_CHANGE"):
                    _proposal(
                        CollectionChangeOperation.NO_CHANGE,
                        **overrides,
                    ).validate()

    def test_conflict_requires_present_exactly_different_values(self) -> None:
        invalid = (
            {"current_value": None},
            {"proposed_value": None},
            {"current_value": "Canada"},
        )
        for overrides in invalid:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ValueError, "CONFLICT"):
                    _proposal(
                        CollectionChangeOperation.CONFLICT,
                        **overrides,
                    ).validate()

    def test_approval_requirement_is_structurally_fixed(self) -> None:
        for operation in CollectionChangeOperation:
            valid = _proposal(operation)
            wrong = (
                CollectionChangeApprovalRequirement.REQUIRED
                if valid.approval_requirement
                is CollectionChangeApprovalRequirement.NOT_REQUIRED
                else CollectionChangeApprovalRequirement.NOT_REQUIRED
            )
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(
                    ValueError,
                    "approval_requirement",
                ):
                    replace(
                        valid,
                        approval_requirement=wrong,
                    ).validate()

    def test_reason_code_is_structurally_fixed(self) -> None:
        for operation in CollectionChangeOperation:
            valid = _proposal(operation)
            wrong = next(
                value
                for value in CollectionChangeReasonCode
                if value is not valid.reason_code
            )
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError, "reason_code"):
                    replace(valid, reason_code=wrong).validate()

    def test_none_and_empty_current_values_are_distinct(self) -> None:
        update = _proposal(
            CollectionChangeOperation.UPDATE,
            current_value="",
        )
        update.validate()
        self.assertEqual(update.current_value, "")
        with self.assertRaisesRegex(ValueError, "ADD"):
            _proposal(
                CollectionChangeOperation.ADD,
                current_value="",
            ).validate()


class ProposalTraceabilityTests(unittest.TestCase):
    def test_full_source_observation_is_retained(self) -> None:
        source = _observation()
        proposal = _proposal(observation=source)

        proposal.validate()

        self.assertIs(proposal.source_observation, source)
        self.assertEqual(proposal.source_observation.reviewer_id, "collector-1")
        self.assertEqual(proposal.source_observation.provenance, source.provenance)
        self.assertIs(
            proposal.source_observation.source_type,
            ConfirmedObservationSource.OCR_REVIEW,
        )

    def test_submitted_value_must_match_proposed_exactly(self) -> None:
        source = _observation(submitted_value="CANADA")
        proposal = _proposal(
            observation=source,
            proposed_value="Canada",
        )

        with self.assertRaisesRegex(ValueError, "exactly match"):
            proposal.validate()

    def test_canonical_value_is_the_allowed_proposed_value(self) -> None:
        source = _observation(
            field_name="silver_indicator",
            submitted_value="YES",
            canonical_value="true",
        )
        accepted = _proposal(
            observation=source,
            target_field="silver_indicator",
        )
        submitted = replace(accepted, proposed_value="YES")

        accepted.validate()
        self.assertEqual(accepted.source_value, "true")
        with self.assertRaisesRegex(ValueError, "canonical value"):
            submitted.validate()

    def test_clear_preserves_source_without_fabricating_a_value(self) -> None:
        source = _observation()
        proposal = _proposal(
            CollectionChangeOperation.CLEAR,
            observation=source,
        )

        proposal.validate()

        self.assertIs(proposal.source_observation, source)
        self.assertIsNone(proposal.proposed_value)

    def test_missing_or_invalid_source_is_rejected(self) -> None:
        proposal = _proposal()
        for source in (None, object()):
            with self.subTest(source=source):
                with self.assertRaises(TypeError):
                    replace(
                        proposal,
                        source_observation=source,
                    ).validate()

    def test_target_field_is_lowercase_bounded_and_grade_free(self) -> None:
        invalid = (
            "",
            " country",
            "Country",
            "series/type",
            "grade",
            "x" * 129,
        )
        for target_field in invalid:
            with self.subTest(target_field=target_field[:20]):
                with self.assertRaises(ValueError):
                    _proposal(target_field=target_field).validate()

    def test_rationale_is_optional_exact_and_nonblank_when_present(self) -> None:
        exact = "  Preserve deliberate rationale spacing.  "
        proposal = _proposal(rationale=exact)
        absent = _proposal(rationale=None)

        proposal.validate()
        absent.validate()

        self.assertEqual(proposal.rationale, exact)
        self.assertIsNone(absent.rationale)
        with self.assertRaisesRegex(ValueError, "rationale"):
            _proposal(rationale=" ").validate()

    def test_values_are_not_trimmed_or_normalized(self) -> None:
        source = _observation(submitted_value="  Canada  ")
        proposal = _proposal(
            CollectionChangeOperation.NO_CHANGE,
            observation=source,
            current_value="  Canada  ",
            proposed_value="  Canada  ",
        )

        proposal.validate()

        self.assertEqual(proposal.current_value, "  Canada  ")
        self.assertEqual(proposal.proposed_value, "  Canada  ")

    def test_control_non_nfc_and_overlong_values_are_rejected(self) -> None:
        for current in ("bad\nvalue", "Cafe\u0301", "x" * 4_097):
            with self.subTest(current=repr(current)[:20]):
                with self.assertRaises(ValueError):
                    _proposal(
                        CollectionChangeOperation.UPDATE,
                        current_value=current,
                    ).validate()


class CollectionChangePlanTests(unittest.TestCase):
    def test_one_proposal_plan_is_valid(self) -> None:
        plan = _plan()

        plan.validate()

        self.assertEqual(plan.target_record.record_id, "record-1")
        self.assertEqual(plan.source_coin_id, "source-coin-1")

    def test_multiple_proposals_require_target_field_order(self) -> None:
        country = _proposal()
        year_source = _observation(
            field_name="year",
            submitted_value="1967",
        )
        year = _proposal(
            observation=year_source,
            target_field="year",
        )
        ordered = _plan((country, year))
        reversed_plan = _plan((year, country))

        ordered.validate()
        with self.assertRaisesRegex(ValueError, "deterministic"):
            reversed_plan.validate()

    def test_duplicate_target_field_is_rejected(self) -> None:
        first = _proposal()
        second = _proposal(
            observation=_observation(
                field_name="monarch",
                submitted_value="George VI",
            ),
            target_field="country",
        )

        with self.assertRaisesRegex(ValueError, "target_field"):
            _plan((first, second)).validate()

    def test_duplicate_source_field_is_rejected(self) -> None:
        first = _proposal(target_field="country")
        second = _proposal(target_field="issuer")

        with self.assertRaisesRegex(ValueError, "source observation"):
            _plan((first, second)).validate()

    def test_mixed_target_records_are_rejected(self) -> None:
        proposal = _proposal(
            target_record=CollectionRecordReference("record-2")
        )

        with self.assertRaisesRegex(ValueError, "target_record"):
            _plan((proposal,)).validate()

    def test_mixed_source_coin_ids_are_rejected(self) -> None:
        proposal = _proposal(
            observation=_observation(source_coin_id="source-coin-2")
        )

        with self.assertRaisesRegex(ValueError, "source_coin_id"):
            _plan((proposal,)).validate()

    def test_mixed_reviewer_ids_are_rejected(self) -> None:
        country = _proposal()
        year = _proposal(
            observation=_observation(
                field_name="year",
                submitted_value="1967",
                reviewer_id="collector-2",
            ),
            target_field="year",
        )

        with self.assertRaisesRegex(ValueError, "reviewer_id"):
            _plan((country, year)).validate()

    def test_empty_and_mutable_proposal_collections_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 300"):
            _plan(()).validate()
        with self.assertRaisesRegex(TypeError, "tuple"):
            replace(_plan(), proposals=[_proposal()]).validate()

    def test_invalid_nested_type_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "proposals"):
            _plan((object(),)).validate()

    def test_optional_aggregate_linkage_is_exact(self) -> None:
        linked = _plan()
        absent = _plan(
            review_session_id=None,
            source_fingerprint=None,
        )

        linked.validate()
        absent.validate()

        self.assertEqual(linked.review_session_id, "review-session-1")
        self.assertEqual(
            linked.source_fingerprint,
            "opaque-source-fingerprint",
        )
        self.assertIsNone(absent.review_session_id)
        self.assertIsNone(absent.source_fingerprint)

    def test_original_proposal_tuple_is_not_changed(self) -> None:
        proposals = (_proposal(),)
        plan = _plan(proposals)

        plan.validate()
        plan.to_dict()

        self.assertIs(plan.proposals, proposals)
        self.assertEqual(proposals, (_proposal(),))


class SerializationTests(unittest.TestCase):
    def test_proposal_round_trip_is_json_safe(self) -> None:
        proposal = _proposal()
        payload = proposal.to_dict()

        json.dumps(payload, allow_nan=False)
        restored = CollectionFieldChangeProposal.from_dict(payload)

        self.assertEqual(restored, proposal)
        self.assertEqual(payload["operation"], "ADD")
        self.assertEqual(payload["approval_requirement"], "REQUIRED")

    def test_plan_round_trip_preserves_exact_nested_traceability(self) -> None:
        plan = _plan()

        restored = CollectionChangePlan.from_dict(plan.to_dict())

        self.assertEqual(restored, plan)
        self.assertEqual(
            restored.proposals[0].source_observation.provenance,
            plan.proposals[0].source_observation.provenance,
        )

    def test_equivalent_plans_serialize_deterministically(self) -> None:
        first = _plan()
        second = deepcopy(first)

        first_json = json.dumps(
            first.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        second_json = json.dumps(
            second.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
        )

        self.assertEqual(first_json, second_json)

    def test_none_and_empty_string_remain_distinct_on_wire(self) -> None:
        add_payload = _proposal().to_dict()
        update_payload = _proposal(
            CollectionChangeOperation.UPDATE,
            current_value="",
        ).to_dict()

        self.assertIsNone(add_payload["current_value"])
        self.assertEqual(update_payload["current_value"], "")
        self.assertIsNone(
            CollectionFieldChangeProposal.from_dict(
                add_payload
            ).current_value
        )
        self.assertEqual(
            CollectionFieldChangeProposal.from_dict(
                update_payload
            ).current_value,
            "",
        )

    def test_unknown_and_missing_fields_fail_at_each_new_level(self) -> None:
        plan = _plan().to_dict()
        locations = (
            (),
            ("target_record",),
            ("proposals", 0),
        )
        for location in locations:
            with self.subTest(location=location):
                unknown = deepcopy(plan)
                target = self._at(unknown, location)
                target["unknown"] = True
                with self.assertRaisesRegex(ValueError, "unknown"):
                    CollectionChangePlan.from_dict(unknown)

                missing = deepcopy(plan)
                target = self._at(missing, location)
                target.pop(next(iter(target)))
                with self.assertRaisesRegex(ValueError, "missing"):
                    CollectionChangePlan.from_dict(missing)

    def test_unsupported_schema_fails_before_nested_repair(self) -> None:
        payload = _plan().to_dict()
        payload["schema_version"] = "2"
        payload["proposals"] = "malformed"

        with self.assertRaises(
            UnsupportedCollectionChangePlanSchemaVersion
        ):
            CollectionChangePlan.from_dict(payload)

        proposal = _proposal().to_dict()
        proposal["schema_version"] = "2"
        proposal["target_record"] = "malformed"
        with self.assertRaises(
            UnsupportedCollectionChangePlanSchemaVersion
        ):
            CollectionFieldChangeProposal.from_dict(proposal)

    def test_invalid_enums_and_malformed_nested_payloads_fail(self) -> None:
        for field in ("operation", "approval_requirement", "reason_code"):
            with self.subTest(field=field):
                payload = _proposal().to_dict()
                payload[field] = "UNKNOWN"
                with self.assertRaises(ValueError):
                    CollectionFieldChangeProposal.from_dict(payload)

        payload = _plan().to_dict()
        payload["proposals"][0]["source_observation"] = "invalid"
        with self.assertRaises(TypeError):
            CollectionChangePlan.from_dict(payload)

    def test_wire_aggregate_requires_list(self) -> None:
        payload = _plan().to_dict()
        payload["proposals"] = tuple(payload["proposals"])

        with self.assertRaisesRegex(TypeError, "list"):
            CollectionChangePlan.from_dict(payload)

    def test_input_mapping_is_not_mutated(self) -> None:
        payload = _plan().to_dict()
        before = deepcopy(payload)

        CollectionChangePlan.from_dict(payload)

        self.assertEqual(payload, before)

    @staticmethod
    def _at(payload, location):
        current = payload
        for item in location:
            current = current[item]
        return current


class ImmutabilityAndArchitectureTests(unittest.TestCase):
    def test_contracts_are_frozen_and_slotted(self) -> None:
        values = (
            CollectionRecordReference("record-1"),
            _proposal(),
            _plan(),
        )
        for value in values:
            with self.subTest(value=type(value).__name__):
                field_name = next(iter(value.__dataclass_fields__))
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, field_name, object())
                with self.assertRaises(AttributeError):
                    value.unexpected = object()

    def test_public_api_is_bounded_to_contracts_and_enums(self) -> None:
        module = importlib.import_module(_MODULE)
        public = {
            name
            for name, value in vars(module).items()
            if (
                not name.startswith("_")
                and getattr(value, "__module__", None) == _MODULE
            )
        }
        self.assertEqual(
            public,
            {
                "UnsupportedCollectionChangePlanSchemaVersion",
                "CollectionChangeOperation",
                "CollectionChangeApprovalRequirement",
                "CollectionChangeReasonCode",
                "CollectionRecordReference",
                "CollectionFieldChangeProposal",
                "CollectionChangePlan",
            },
        )

    def test_import_boundary_is_narrow(self) -> None:
        module = importlib.import_module(_MODULE)
        path = Path(inspect.getfile(module))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        forbidden = (
            "coin_collection",
            "repository",
            "persistence",
            "desktop",
            "gui",
            "tkinter",
            "workflow_ocr",
            "readiness",
            "mapper",
            "comparison",
            "pathlib",
            "os",
            "requests",
            "urllib",
            "uuid",
            "datetime",
        )
        for fragment in forbidden:
            with self.subTest(fragment=fragment):
                self.assertFalse(
                    any(fragment in name.casefold() for name in imported),
                    imported,
                )
        self.assertIn(
            "capture_import.workflow_confirmed_observation_models",
            imported,
        )

    def test_module_has_no_execution_or_approval_surface(self) -> None:
        module = importlib.import_module(_MODULE)
        source = inspect.getsource(module)
        public_functions = {
            name
            for name, value in vars(module).items()
            if (
                inspect.isfunction(value)
                and value.__module__ == _MODULE
                and not name.startswith("_")
            )
        }
        self.assertEqual(public_functions, set())
        for fragment in (
            "approved_by",
            "approved_at",
            "approval_token",
            "execute(",
            "apply(",
            "save(",
            "open(",
            "getenv",
            "uuid4",
            "datetime.now",
        ):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, source)

    def test_plan_contract_does_not_claim_ready_source_proof(self) -> None:
        self.assertNotIn(
            "readiness",
            tuple(CollectionChangePlan.__dataclass_fields__),
        )
        self.assertNotIn(
            "approved",
            " ".join(CollectionChangePlan.__dataclass_fields__).casefold(),
        )


if __name__ == "__main__":
    unittest.main()
