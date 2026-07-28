"""Tests for direct durable collection change-plan aggregation."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import importlib
import inspect
import json
import unittest

from capture_import.workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedFieldObservation,
    ConfirmedObservationProvenance,
    ConfirmedObservationSource,
)
from collection_management.workflow_collection_change_plan_builder import (
    CollectionChangePlanBuildError,
    CollectionChangePlanBuilder,
    InvalidCollectionChangePlanBuildContextError,
    build_collection_change_plan,
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
from collection_management.workflow_collection_change_proposal_builder import (
    CollectionChangeProposalBuildResult,
)


_MODULE = "collection_management.workflow_collection_change_plan_builder"
_VALUES = {
    "country": "Canada",
    "denomination": "25 cents",
    "year": "1967",
}
_OPERATION_POLICY = {
    CollectionChangeOperation.ADD: (
        CollectionChangeApprovalRequirement.REQUIRED,
        CollectionChangeReasonCode.NEW_VALUE,
    ),
    CollectionChangeOperation.UPDATE: (
        CollectionChangeApprovalRequirement.REQUIRED,
        CollectionChangeReasonCode.DIFFERENT_VALUE,
    ),
    CollectionChangeOperation.CLEAR: (
        CollectionChangeApprovalRequirement.REQUIRED,
        CollectionChangeReasonCode.EXPLICIT_CLEAR,
    ),
    CollectionChangeOperation.NO_CHANGE: (
        CollectionChangeApprovalRequirement.NOT_REQUIRED,
        CollectionChangeReasonCode.EQUIVALENT_VALUE,
    ),
    CollectionChangeOperation.CONFLICT: (
        CollectionChangeApprovalRequirement.REQUIRED,
        CollectionChangeReasonCode.EXISTING_VALUE_CONFLICT,
    ),
}


def _observation(
    field_name: str,
    value: str,
    *,
    source_coin_id: str = "source-coin-1",
    reviewer_id: str = "collector-1",
) -> ConfirmedFieldObservation:
    return ConfirmedFieldObservation(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id=source_coin_id,
        field_name=field_name,
        submitted_value=value,
        canonical_value=None,
        reviewer_id=reviewer_id,
        provenance=(
            ConfirmedObservationProvenance(
                provider_id="test-ocr",
                image_role="front",
                artifact_key=f"crop-{field_name}",
                source_value=value,
                confidence_score=96.0,
                evidence=("collector confirmed",),
            ),
        ),
        source_type=ConfirmedObservationSource.OCR_REVIEW,
        rationale="Confirmed by collector.",
    )


def _proposal(
    target_field: str,
    operation: CollectionChangeOperation,
    *,
    source_coin_id: str = "source-coin-1",
    reviewer_id: str = "collector-1",
    target_record: CollectionRecordReference | None = None,
) -> CollectionFieldChangeProposal:
    proposed = _VALUES[target_field]
    if operation is CollectionChangeOperation.ADD:
        current_value: str | None = None
        proposed_value: str | None = proposed
    elif operation is CollectionChangeOperation.UPDATE:
        current_value = f"old-{target_field}"
        proposed_value = proposed
    elif operation is CollectionChangeOperation.CLEAR:
        current_value = f"old-{target_field}"
        proposed_value = None
    elif operation is CollectionChangeOperation.NO_CHANGE:
        current_value = proposed
        proposed_value = proposed
    elif operation is CollectionChangeOperation.CONFLICT:
        current_value = f"conflict-{target_field}"
        proposed_value = proposed
    else:
        raise AssertionError(operation)
    approval, reason = _OPERATION_POLICY[operation]
    result = CollectionFieldChangeProposal(
        schema_version=CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
        target_record=(
            target_record or CollectionRecordReference("record-1")
        ),
        target_field=target_field,
        current_value=current_value,
        proposed_value=proposed_value,
        operation=operation,
        approval_requirement=approval,
        source_observation=_observation(
            target_field,
            proposed,
            source_coin_id=source_coin_id,
            reviewer_id=reviewer_id,
        ),
        reason_code=reason,
        rationale="Confirmed by collector.",
    )
    result.validate()
    return result


def _proposal_result(
    *proposals: CollectionFieldChangeProposal,
    target_record: CollectionRecordReference | None = None,
    source_coin_id: str = "source-coin-1",
    reviewer_id: str = "collector-1",
    review_session_id: str | None = "review-session-1",
    source_fingerprint: str | None = "opaque-source-fingerprint",
) -> CollectionChangeProposalBuildResult:
    selected = proposals or (
        _proposal("country", CollectionChangeOperation.ADD),
    )
    result = CollectionChangeProposalBuildResult(
        target_record=(
            target_record or CollectionRecordReference("record-1")
        ),
        source_coin_id=source_coin_id,
        reviewer_id=reviewer_id,
        proposals=tuple(
            sorted(selected, key=lambda item: item.target_field)
        ),
        review_session_id=review_session_id,
        source_fingerprint=source_fingerprint,
    )
    result.validate()
    return result


class BasicConstructionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = CollectionChangePlanBuilder()

    def test_one_add_proposal_builds_plan(self) -> None:
        source = _proposal_result(
            _proposal("country", CollectionChangeOperation.ADD)
        )
        plan = self.builder.build(source)
        self.assertIsInstance(plan, CollectionChangePlan)
        self.assertIs(
            plan.proposals[0].operation,
            CollectionChangeOperation.ADD,
        )

    def test_one_update_proposal_builds_plan(self) -> None:
        plan = self.builder.build(
            _proposal_result(
                _proposal("country", CollectionChangeOperation.UPDATE)
            )
        )
        self.assertIs(
            plan.proposals[0].operation,
            CollectionChangeOperation.UPDATE,
        )

    def test_one_no_change_proposal_is_preserved(self) -> None:
        plan = self.builder.build(
            _proposal_result(
                _proposal(
                    "country",
                    CollectionChangeOperation.NO_CHANGE,
                )
            )
        )
        proposal = plan.proposals[0]
        self.assertIs(
            proposal.operation,
            CollectionChangeOperation.NO_CHANGE,
        )
        self.assertIs(
            proposal.approval_requirement,
            CollectionChangeApprovalRequirement.NOT_REQUIRED,
        )

    def test_mixed_proposals_remain_in_target_order(self) -> None:
        source = _proposal_result(
            _proposal("year", CollectionChangeOperation.UPDATE),
            _proposal("country", CollectionChangeOperation.NO_CHANGE),
            _proposal("denomination", CollectionChangeOperation.ADD),
        )
        plan = self.builder.build(source)
        self.assertEqual(
            tuple(item.target_field for item in plan.proposals),
            ("country", "denomination", "year"),
        )
        self.assertEqual(
            tuple(item.operation for item in plan.proposals),
            (
                CollectionChangeOperation.NO_CHANGE,
                CollectionChangeOperation.ADD,
                CollectionChangeOperation.UPDATE,
            ),
        )

    def test_convenience_function_matches_builder(self) -> None:
        source = _proposal_result()
        self.assertEqual(
            build_collection_change_plan(source),
            self.builder.build(source),
        )

    def test_input_type_is_strict(self) -> None:
        with self.assertRaisesRegex(
            TypeError,
            "CollectionChangeProposalBuildResult",
        ):
            self.builder.build(object())  # type: ignore[arg-type]


class ProposalPreservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.proposals = (
            _proposal("country", CollectionChangeOperation.NO_CHANGE),
            _proposal("denomination", CollectionChangeOperation.ADD),
            _proposal("year", CollectionChangeOperation.UPDATE),
        )
        self.source = _proposal_result(*self.proposals)
        self.plan = CollectionChangePlanBuilder().build(self.source)

    def test_proposal_tuple_is_preserved_by_identity(self) -> None:
        self.assertIs(self.plan.proposals, self.source.proposals)

    def test_every_proposal_object_is_preserved_by_identity(self) -> None:
        for planned, source in zip(
            self.plan.proposals,
            self.source.proposals,
        ):
            self.assertIs(planned, source)

    def test_all_proposal_fields_remain_exact(self) -> None:
        for planned, source in zip(
            self.plan.proposals,
            self.source.proposals,
        ):
            self.assertEqual(planned, source)
            self.assertEqual(planned.current_value, source.current_value)
            self.assertEqual(planned.proposed_value, source.proposed_value)
            self.assertIs(planned.operation, source.operation)
            self.assertIs(
                planned.approval_requirement,
                source.approval_requirement,
            )
            self.assertIs(planned.reason_code, source.reason_code)
            self.assertEqual(planned.rationale, source.rationale)

    def test_source_observation_and_provenance_are_retained(self) -> None:
        for planned, source in zip(
            self.plan.proposals,
            self.source.proposals,
        ):
            self.assertIs(
                planned.source_observation,
                source.source_observation,
            )
            self.assertIs(
                planned.source_observation.provenance,
                source.source_observation.provenance,
            )

    def test_no_change_is_not_omitted(self) -> None:
        self.assertEqual(len(self.plan.proposals), 3)
        self.assertTrue(
            any(
                item.operation is CollectionChangeOperation.NO_CHANGE
                for item in self.plan.proposals
            )
        )


class OperationNeutralityTests(unittest.TestCase):
    def test_structurally_valid_clear_is_not_reinterpreted(self) -> None:
        source = _proposal_result(
            _proposal("country", CollectionChangeOperation.CLEAR)
        )
        plan = build_collection_change_plan(source)
        self.assertIs(
            plan.proposals[0].operation,
            CollectionChangeOperation.CLEAR,
        )
        self.assertIsNone(plan.proposals[0].proposed_value)

    def test_structurally_valid_conflict_is_not_reinterpreted(self) -> None:
        source = _proposal_result(
            _proposal("country", CollectionChangeOperation.CONFLICT)
        )
        plan = build_collection_change_plan(source)
        self.assertIs(
            plan.proposals[0].operation,
            CollectionChangeOperation.CONFLICT,
        )

    def test_builder_contains_no_operation_policy_table(self) -> None:
        module = importlib.import_module(_MODULE)
        module_values = vars(module).values()
        self.assertFalse(
            any(
                isinstance(value, dict)
                and any(
                    isinstance(key, CollectionChangeOperation)
                    for key in value
                )
                for value in module_values
            )
        )


class LinkageAndInvariantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = _proposal_result(
            _proposal("country", CollectionChangeOperation.ADD),
            review_session_id="session/exact",
            source_fingerprint="fingerprint/exact",
        )
        self.builder = CollectionChangePlanBuilder()

    def test_exact_source_to_plan_field_mapping(self) -> None:
        plan = self.builder.build(self.source)
        self.assertEqual(
            plan.schema_version,
            CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
        )
        self.assertIs(plan.target_record, self.source.target_record)
        self.assertEqual(plan.source_coin_id, self.source.source_coin_id)
        self.assertIs(plan.proposals, self.source.proposals)
        self.assertEqual(
            plan.review_session_id,
            self.source.review_session_id,
        )
        self.assertEqual(
            plan.source_fingerprint,
            self.source.source_fingerprint,
        )

    def test_reviewer_remains_nested_and_consistent(self) -> None:
        plan = self.builder.build(self.source)
        self.assertNotIn(
            "reviewer_id",
            CollectionChangePlan.__dataclass_fields__,
        )
        self.assertEqual(
            {
                proposal.source_observation.reviewer_id
                for proposal in plan.proposals
            },
            {"collector-1"},
        )

    def test_record_id_and_source_coin_id_remain_distinct(self) -> None:
        plan = self.builder.build(self.source)
        self.assertEqual(plan.target_record.record_id, "record-1")
        self.assertEqual(plan.source_coin_id, "source-coin-1")
        self.assertNotEqual(
            plan.target_record.record_id,
            plan.source_coin_id,
        )

    def test_none_session_and_fingerprint_remain_none(self) -> None:
        plan = self.builder.build(
            _proposal_result(
                review_session_id=None,
                source_fingerprint=None,
            )
        )
        self.assertIsNone(plan.review_session_id)
        self.assertIsNone(plan.source_fingerprint)

    def test_target_record_mismatch_is_typed_context_error(self) -> None:
        foreign = replace(
            self.source.proposals[0],
            target_record=CollectionRecordReference("other-record"),
        )
        malformed = replace(self.source, proposals=(foreign,))
        with self.assertRaises(
            InvalidCollectionChangePlanBuildContextError
        ):
            self.builder.build(malformed)

    def test_source_coin_mismatch_is_typed_context_error(self) -> None:
        malformed = replace(self.source, source_coin_id="other-source")
        with self.assertRaises(
            InvalidCollectionChangePlanBuildContextError
        ):
            self.builder.build(malformed)

    def test_reviewer_mismatch_is_typed_context_error(self) -> None:
        malformed = replace(self.source, reviewer_id="other-reviewer")
        with self.assertRaises(
            InvalidCollectionChangePlanBuildContextError
        ):
            self.builder.build(malformed)

    def test_duplicate_target_is_typed_context_error(self) -> None:
        duplicate = replace(
            self.source,
            proposals=(
                self.source.proposals[0],
                self.source.proposals[0],
            ),
        )
        with self.assertRaises(
            InvalidCollectionChangePlanBuildContextError
        ):
            self.builder.build(duplicate)

    def test_duplicate_source_field_is_typed_context_error(self) -> None:
        first = _proposal("country", CollectionChangeOperation.ADD)
        second = replace(
            _proposal("year", CollectionChangeOperation.ADD),
            source_observation=_observation("country", "1967"),
        )
        malformed = _proposal_result(first)
        malformed = replace(
            malformed,
            proposals=(first, second),
        )
        with self.assertRaises(
            InvalidCollectionChangePlanBuildContextError
        ):
            self.builder.build(malformed)

    def test_reordered_unit_1d_result_fails_instead_of_being_repaired(
        self,
    ) -> None:
        source = _proposal_result(
            _proposal("country", CollectionChangeOperation.ADD),
            _proposal("year", CollectionChangeOperation.UPDATE),
        )
        malformed = replace(
            source,
            proposals=tuple(reversed(source.proposals)),
        )
        with self.assertRaisesRegex(ValueError, "deterministic"):
            self.builder.build(malformed)


class AtomicityAndErrorTests(unittest.TestCase):
    def test_malformed_final_proposal_returns_no_plan(self) -> None:
        valid = _proposal("country", CollectionChangeOperation.ADD)
        invalid = replace(
            _proposal("year", CollectionChangeOperation.UPDATE),
            proposed_value="not-the-source-value",
        )
        source = _proposal_result(valid)
        malformed = replace(source, proposals=(valid, invalid))
        with self.assertRaisesRegex(
            ValueError,
            "proposed_value must exactly match",
        ):
            CollectionChangePlanBuilder().build(malformed)

    def test_unit_1a_schema_error_propagates_unwrapped(self) -> None:
        invalid = replace(
            _proposal("country", CollectionChangeOperation.ADD),
            schema_version="999",
        )
        source = _proposal_result()
        malformed = replace(source, proposals=(invalid,))
        with self.assertRaises(
            UnsupportedCollectionChangePlanSchemaVersion
        ):
            CollectionChangePlanBuilder().build(malformed)

    def test_empty_result_error_propagates_without_partial_plan(self) -> None:
        malformed = replace(_proposal_result(), proposals=())
        with self.assertRaisesRegex(ValueError, "at least one"):
            CollectionChangePlanBuilder().build(malformed)

    def test_input_remains_unchanged_after_success(self) -> None:
        source = _proposal_result(
            _proposal("country", CollectionChangeOperation.ADD)
        )
        before = repr(source)
        proposals = source.proposals
        observation = proposals[0].source_observation
        provenance = observation.provenance
        CollectionChangePlanBuilder().build(source)
        self.assertEqual(repr(source), before)
        self.assertIs(source.proposals, proposals)
        self.assertIs(source.proposals[0].source_observation, observation)
        self.assertIs(observation.provenance, provenance)

    def test_input_remains_unchanged_after_failure(self) -> None:
        source = _proposal_result()
        malformed = replace(source, proposals=())
        before = repr(malformed)
        with self.assertRaises(ValueError):
            CollectionChangePlanBuilder().build(malformed)
        self.assertEqual(repr(malformed), before)

    def test_error_hierarchy_is_narrow(self) -> None:
        self.assertTrue(
            issubclass(
                InvalidCollectionChangePlanBuildContextError,
                CollectionChangePlanBuildError,
            )
        )


class SerializationAndIdempotenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = _proposal_result(
            _proposal("country", CollectionChangeOperation.NO_CHANGE),
            _proposal("denomination", CollectionChangeOperation.ADD),
            _proposal("year", CollectionChangeOperation.UPDATE),
        )
        self.builder = CollectionChangePlanBuilder()
        self.plan = self.builder.build(self.source)

    def test_plan_serialization_is_json_safe(self) -> None:
        payload = self.plan.to_dict()
        encoded = json.dumps(payload, sort_keys=True)
        self.assertIsInstance(encoded, str)

    def test_plan_round_trip_is_exact(self) -> None:
        restored = CollectionChangePlan.from_dict(self.plan.to_dict())
        self.assertEqual(restored, self.plan)

    def test_serialization_is_deterministic(self) -> None:
        self.assertEqual(
            json.dumps(self.plan.to_dict(), sort_keys=True),
            json.dumps(
                self.builder.build(self.source).to_dict(),
                sort_keys=True,
            ),
        )

    def test_none_and_empty_string_remain_distinct(self) -> None:
        source = _proposal_result(
            _proposal("country", CollectionChangeOperation.ADD),
            replace(
                _proposal(
                    "denomination",
                    CollectionChangeOperation.UPDATE,
                ),
                current_value="",
            ),
        )
        plan = self.builder.build(source)
        payload = plan.to_dict()
        self.assertIsNone(payload["proposals"][0]["current_value"])
        self.assertEqual(payload["proposals"][1]["current_value"], "")
        self.assertEqual(
            CollectionChangePlan.from_dict(payload),
            plan,
        )

    def test_unknown_plan_field_is_rejected_by_unit_1a(self) -> None:
        payload = self.plan.to_dict()
        payload["unknown"] = "value"
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            CollectionChangePlan.from_dict(payload)

    def test_missing_plan_field_is_rejected_by_unit_1a(self) -> None:
        payload = self.plan.to_dict()
        del payload["source_fingerprint"]
        with self.assertRaisesRegex(ValueError, "missing fields"):
            CollectionChangePlan.from_dict(payload)

    def test_unsupported_plan_schema_is_rejected_by_unit_1a(self) -> None:
        payload = self.plan.to_dict()
        payload["schema_version"] = "999"
        with self.assertRaises(
            UnsupportedCollectionChangePlanSchemaVersion
        ):
            CollectionChangePlan.from_dict(payload)

    def test_repeated_builds_are_equal(self) -> None:
        first = self.builder.build(self.source)
        second = self.builder.build(self.source)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)


class ImmutabilityAndBoundaryTests(unittest.TestCase):
    def test_service_is_stateless_and_slotted(self) -> None:
        self.assertFalse(hasattr(CollectionChangePlanBuilder(), "__dict__"))

    def test_returned_plan_is_frozen_and_slotted(self) -> None:
        plan = build_collection_change_plan(_proposal_result())
        self.assertFalse(hasattr(plan, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            plan.extra = "mutation"  # type: ignore[attr-defined]

    def test_no_unit_1e_serializer_or_wrapper_exists(self) -> None:
        module = importlib.import_module(_MODULE)
        self.assertFalse(hasattr(module, "CollectionChangePlanBuildResult"))
        self.assertFalse(hasattr(CollectionChangePlanBuilder, "to_dict"))
        self.assertFalse(hasattr(CollectionChangePlanBuilder, "from_dict"))

    def test_unit_1d_field_mapping_is_guarded(self) -> None:
        self.assertEqual(
            tuple(CollectionChangeProposalBuildResult.__dataclass_fields__),
            (
                "target_record",
                "source_coin_id",
                "reviewer_id",
                "proposals",
                "review_session_id",
                "source_fingerprint",
            ),
        )
        self.assertEqual(
            tuple(CollectionChangePlan.__dataclass_fields__),
            (
                "schema_version",
                "target_record",
                "source_coin_id",
                "proposals",
                "review_session_id",
                "source_fingerprint",
            ),
        )

    def test_import_boundary_has_no_forbidden_dependencies(self) -> None:
        module = importlib.import_module(_MODULE)
        tree = ast.parse(inspect.getsource(module))
        imported: list[str] = []
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
            "pathlib",
            "requests",
            "urllib",
            "uuid",
            "datetime",
        )
        for fragment in forbidden:
            with self.subTest(fragment=fragment):
                self.assertFalse(
                    any(fragment in item.casefold() for item in imported),
                    imported,
                )
        self.assertNotIn("os", imported)

    def test_module_has_no_policy_or_execution_surface(self) -> None:
        module = importlib.import_module(_MODULE)
        source = inspect.getsource(module)
        for fragment in (
            "CollectionChangeOperation",
            "CollectionChangeApprovalRequirement",
            "CollectionChangeReasonCode",
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

    def test_public_api_is_exact(self) -> None:
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
                "CollectionChangePlanBuildError",
                "InvalidCollectionChangePlanBuildContextError",
                "CollectionChangePlanBuilder",
                "build_collection_change_plan",
            },
        )


if __name__ == "__main__":
    unittest.main()
