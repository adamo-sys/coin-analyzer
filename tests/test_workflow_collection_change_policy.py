"""Tests for conservative, non-authorizing change-plan assessment."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import importlib
import inspect
from types import MappingProxyType
import unittest
from unittest.mock import patch

from capture_import.workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedFieldObservation,
    ConfirmedObservationProvenance,
    ConfirmedObservationSource,
)
import collection_management.workflow_collection_change_policy as policy_module
from collection_management.workflow_collection_change_policy import (
    BlockedCollectionChangePlanError,
    CollectionChangePlanPolicyAssessment,
    CollectionChangePolicyAssessment,
    CollectionChangePolicyAssessor,
    CollectionChangePolicyError,
    CollectionChangePolicyStatus,
    InvalidCollectionChangePolicyContextError,
    UnsupportedCollectionChangePolicyOperationError,
    assess_collection_change_plan,
    require_unblocked_collection_change_plan,
)
from collection_management.workflow_collection_change_plan_models import (
    CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
    CollectionChangeApprovalRequirement,
    CollectionChangeOperation,
    CollectionChangePlan,
    CollectionChangeReasonCode,
    CollectionFieldChangeProposal,
    CollectionRecordReference,
)


_MODULE = "collection_management.workflow_collection_change_policy"
_VALUES = {
    "country": "Canada",
    "denomination": "25 cents",
    "year": "1967",
    "issuer": "Royal Canadian Mint",
    "reference": "KM-68",
}
_STRUCTURE = {
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
) -> ConfirmedFieldObservation:
    return ConfirmedFieldObservation(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id="source-coin-1",
        field_name=field_name,
        submitted_value=value,
        canonical_value=None,
        reviewer_id="collector-1",
        provenance=(
            ConfirmedObservationProvenance(
                provider_id="test-ocr",
                image_role="front",
                artifact_key=f"crop-{field_name}",
                source_value=value,
                confidence_score=92.0,
                evidence=("collector confirmed",),
            ),
        ),
        source_type=ConfirmedObservationSource.OCR_REVIEW,
        rationale="Confirmed by collector.",
    )


def _proposal(
    target_field: str,
    operation: CollectionChangeOperation,
) -> CollectionFieldChangeProposal:
    proposed = _VALUES[target_field]
    if operation is CollectionChangeOperation.ADD:
        current: str | None = None
        proposed_value: str | None = proposed
    elif operation is CollectionChangeOperation.UPDATE:
        current = f"old-{target_field}"
        proposed_value = proposed
    elif operation is CollectionChangeOperation.CLEAR:
        current = f"old-{target_field}"
        proposed_value = None
    elif operation is CollectionChangeOperation.NO_CHANGE:
        current = proposed
        proposed_value = proposed
    elif operation is CollectionChangeOperation.CONFLICT:
        current = f"conflict-{target_field}"
        proposed_value = proposed
    else:
        raise AssertionError(operation)
    approval, reason = _STRUCTURE[operation]
    result = CollectionFieldChangeProposal(
        schema_version=CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
        target_record=CollectionRecordReference("record-1"),
        target_field=target_field,
        current_value=current,
        proposed_value=proposed_value,
        operation=operation,
        approval_requirement=approval,
        source_observation=_observation(target_field, proposed),
        reason_code=reason,
        rationale="Confirmed by collector.",
    )
    result.validate()
    return result


def _plan(
    *proposals: CollectionFieldChangeProposal,
) -> CollectionChangePlan:
    selected = proposals or (
        _proposal("country", CollectionChangeOperation.NO_CHANGE),
    )
    result = CollectionChangePlan(
        schema_version=CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
        target_record=CollectionRecordReference("record-1"),
        source_coin_id="source-coin-1",
        proposals=tuple(
            sorted(selected, key=lambda item: item.target_field)
        ),
        review_session_id="review-session-1",
        source_fingerprint="opaque-source-fingerprint",
    )
    result.validate()
    return result


class PolicyTableTests(unittest.TestCase):
    def test_status_vocabulary_is_exact(self) -> None:
        self.assertEqual(
            tuple(item.value for item in CollectionChangePolicyStatus),
            (
                "SAFE_NO_OP",
                "REQUIRES_APPROVAL",
                "BLOCKED_CONFLICT",
            ),
        )

    def test_operation_policy_is_exact_and_immutable(self) -> None:
        self.assertIsInstance(
            policy_module._OPERATION_POLICY,
            MappingProxyType,
        )
        self.assertEqual(
            policy_module._OPERATION_POLICY,
            {
                CollectionChangeOperation.ADD: (
                    CollectionChangePolicyStatus.REQUIRES_APPROVAL
                ),
                CollectionChangeOperation.UPDATE: (
                    CollectionChangePolicyStatus.REQUIRES_APPROVAL
                ),
                CollectionChangeOperation.CLEAR: (
                    CollectionChangePolicyStatus.BLOCKED_CONFLICT
                ),
                CollectionChangeOperation.NO_CHANGE: (
                    CollectionChangePolicyStatus.SAFE_NO_OP
                ),
                CollectionChangeOperation.CONFLICT: (
                    CollectionChangePolicyStatus.BLOCKED_CONFLICT
                ),
            },
        )
        with self.assertRaises(TypeError):
            policy_module._OPERATION_POLICY[
                CollectionChangeOperation.ADD
            ] = CollectionChangePolicyStatus.SAFE_NO_OP  # type: ignore[index]

    def test_every_current_operation_has_policy(self) -> None:
        self.assertEqual(
            set(policy_module._OPERATION_POLICY),
            set(CollectionChangeOperation),
        )


class OperationAssessmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assessor = CollectionChangePolicyAssessor()

    def _assessment(
        self,
        operation: CollectionChangeOperation,
    ) -> CollectionChangePolicyAssessment:
        return self.assessor.assess(
            _plan(_proposal("country", operation))
        ).assessments[0]

    def test_no_change_is_safe_no_op(self) -> None:
        assessment = self._assessment(
            CollectionChangeOperation.NO_CHANGE
        )
        self.assertIs(
            assessment.status,
            CollectionChangePolicyStatus.SAFE_NO_OP,
        )
        self.assertIs(
            assessment.proposal.approval_requirement,
            CollectionChangeApprovalRequirement.NOT_REQUIRED,
        )
        self.assertIs(
            assessment.proposal.reason_code,
            CollectionChangeReasonCode.EQUIVALENT_VALUE,
        )

    def test_add_requires_approval(self) -> None:
        assessment = self._assessment(CollectionChangeOperation.ADD)
        self.assertIs(
            assessment.status,
            CollectionChangePolicyStatus.REQUIRES_APPROVAL,
        )
        self.assertIsNone(assessment.proposal.current_value)
        self.assertIs(
            assessment.proposal.reason_code,
            CollectionChangeReasonCode.NEW_VALUE,
        )

    def test_update_requires_approval_without_conflict_escalation(
        self,
    ) -> None:
        assessment = self._assessment(CollectionChangeOperation.UPDATE)
        self.assertIs(
            assessment.status,
            CollectionChangePolicyStatus.REQUIRES_APPROVAL,
        )
        self.assertIs(
            assessment.proposal.reason_code,
            CollectionChangeReasonCode.DIFFERENT_VALUE,
        )

    def test_clear_is_blocked_conservatively(self) -> None:
        assessment = self._assessment(CollectionChangeOperation.CLEAR)
        self.assertIs(
            assessment.status,
            CollectionChangePolicyStatus.BLOCKED_CONFLICT,
        )
        self.assertIsNone(assessment.proposal.proposed_value)
        self.assertEqual(
            assessment.proposal.current_value,
            "old-country",
        )

    def test_conflict_is_blocked_without_resolution(self) -> None:
        assessment = self._assessment(
            CollectionChangeOperation.CONFLICT
        )
        self.assertIs(
            assessment.status,
            CollectionChangePolicyStatus.BLOCKED_CONFLICT,
        )
        self.assertIs(
            assessment.proposal.reason_code,
            CollectionChangeReasonCode.EXISTING_VALUE_CONFLICT,
        )

    def test_proposal_identity_is_preserved(self) -> None:
        plan = _plan(_proposal("country", CollectionChangeOperation.ADD))
        result = self.assessor.assess(plan)
        self.assertIs(result.plan, plan)
        self.assertIs(
            result.assessments[0].proposal,
            plan.proposals[0],
        )


class SummaryTests(unittest.TestCase):
    def test_single_operation_summaries_are_exact(self) -> None:
        cases = (
            (CollectionChangeOperation.NO_CHANGE, False, False, True),
            (CollectionChangeOperation.ADD, False, True, False),
            (CollectionChangeOperation.UPDATE, False, True, False),
            (CollectionChangeOperation.CLEAR, True, False, False),
            (CollectionChangeOperation.CONFLICT, True, False, False),
        )
        for operation, blocked, approval, safe_only in cases:
            with self.subTest(operation=operation):
                result = assess_collection_change_plan(
                    _plan(_proposal("country", operation))
                )
                self.assertIs(result.contains_blocked_items, blocked)
                self.assertIs(
                    result.contains_approval_required_items,
                    approval,
                )
                self.assertIs(
                    result.contains_only_safe_no_ops,
                    safe_only,
                )

    def test_no_change_only_summary(self) -> None:
        result = assess_collection_change_plan(
            _plan(
                _proposal(
                    "country",
                    CollectionChangeOperation.NO_CHANGE,
                )
            )
        )
        self.assertFalse(result.contains_blocked_items)
        self.assertFalse(result.contains_approval_required_items)
        self.assertTrue(result.contains_only_safe_no_ops)

    def test_add_and_no_change_summary(self) -> None:
        result = assess_collection_change_plan(
            _plan(
                _proposal("country", CollectionChangeOperation.ADD),
                _proposal(
                    "year",
                    CollectionChangeOperation.NO_CHANGE,
                ),
            )
        )
        self.assertFalse(result.contains_blocked_items)
        self.assertTrue(result.contains_approval_required_items)
        self.assertFalse(result.contains_only_safe_no_ops)

    def test_update_and_no_change_summary(self) -> None:
        result = assess_collection_change_plan(
            _plan(
                _proposal(
                    "country",
                    CollectionChangeOperation.UPDATE,
                ),
                _proposal(
                    "year",
                    CollectionChangeOperation.NO_CHANGE,
                ),
            )
        )
        self.assertFalse(result.contains_blocked_items)
        self.assertTrue(result.contains_approval_required_items)
        self.assertFalse(result.contains_only_safe_no_ops)

    def test_add_and_update_summary(self) -> None:
        result = assess_collection_change_plan(
            _plan(
                _proposal("country", CollectionChangeOperation.ADD),
                _proposal(
                    "year",
                    CollectionChangeOperation.UPDATE,
                ),
            )
        )
        self.assertFalse(result.contains_blocked_items)
        self.assertTrue(result.contains_approval_required_items)

    def test_update_and_conflict_summary(self) -> None:
        result = assess_collection_change_plan(
            _plan(
                _proposal(
                    "country",
                    CollectionChangeOperation.UPDATE,
                ),
                _proposal(
                    "year",
                    CollectionChangeOperation.CONFLICT,
                ),
            )
        )
        self.assertTrue(result.contains_blocked_items)
        self.assertTrue(result.contains_approval_required_items)
        self.assertFalse(result.contains_only_safe_no_ops)

    def test_clear_and_no_change_summary(self) -> None:
        result = assess_collection_change_plan(
            _plan(
                _proposal(
                    "country",
                    CollectionChangeOperation.CLEAR,
                ),
                _proposal(
                    "year",
                    CollectionChangeOperation.NO_CHANGE,
                ),
            )
        )
        self.assertTrue(result.contains_blocked_items)
        self.assertFalse(result.contains_approval_required_items)
        self.assertFalse(result.contains_only_safe_no_ops)

    def test_add_clear_and_no_change_summary(self) -> None:
        result = assess_collection_change_plan(
            _plan(
                _proposal("country", CollectionChangeOperation.ADD),
                _proposal("year", CollectionChangeOperation.CLEAR),
                _proposal(
                    "denomination",
                    CollectionChangeOperation.NO_CHANGE,
                ),
            )
        )
        self.assertTrue(result.contains_blocked_items)
        self.assertTrue(result.contains_approval_required_items)
        self.assertFalse(result.contains_only_safe_no_ops)

    def test_assessment_order_matches_plan_order(self) -> None:
        plan = _plan(
            _proposal("year", CollectionChangeOperation.UPDATE),
            _proposal("country", CollectionChangeOperation.ADD),
            _proposal(
                "denomination",
                CollectionChangeOperation.NO_CHANGE,
            ),
        )
        result = assess_collection_change_plan(plan)
        self.assertEqual(
            tuple(
                item.proposal.target_field
                for item in result.assessments
            ),
            tuple(item.target_field for item in plan.proposals),
        )
        for assessment, proposal in zip(
            result.assessments,
            plan.proposals,
        ):
            self.assertIs(assessment.proposal, proposal)


class StrictHelperTests(unittest.TestCase):
    def test_safe_no_op_plan_returns_same_diagnostic_shape(self) -> None:
        plan = _plan()
        self.assertEqual(
            require_unblocked_collection_change_plan(plan),
            assess_collection_change_plan(plan),
        )

    def test_approval_required_plan_returns_still_unapproved(self) -> None:
        plan = _plan(
            _proposal("country", CollectionChangeOperation.ADD)
        )
        result = require_unblocked_collection_change_plan(plan)
        self.assertTrue(result.contains_approval_required_items)
        self.assertFalse(result.contains_blocked_items)
        self.assertFalse(
            any(
                "approved" in field
                or "authorized" in field
                or "executable" in field
                for field in result.__dataclass_fields__
            )
        )

    def test_update_only_plan_is_unblocked_but_still_unapproved(
        self,
    ) -> None:
        plan = _plan(
            _proposal("country", CollectionChangeOperation.UPDATE)
        )
        result = require_unblocked_collection_change_plan(plan)
        self.assertFalse(result.contains_blocked_items)
        self.assertTrue(result.contains_approval_required_items)

    def test_each_blocked_operation_fails_strict_assessment(self) -> None:
        for operation in (
            CollectionChangeOperation.CLEAR,
            CollectionChangeOperation.CONFLICT,
        ):
            with self.subTest(operation=operation):
                with self.assertRaises(BlockedCollectionChangePlanError):
                    require_unblocked_collection_change_plan(
                        _plan(_proposal("country", operation))
                    )

    def test_mixed_blocked_and_approval_required_plan_is_blocked(
        self,
    ) -> None:
        plan = _plan(
            _proposal("country", CollectionChangeOperation.UPDATE),
            _proposal("year", CollectionChangeOperation.CONFLICT),
        )
        diagnostic = assess_collection_change_plan(plan)
        self.assertTrue(diagnostic.contains_blocked_items)
        self.assertTrue(diagnostic.contains_approval_required_items)
        with self.assertRaises(BlockedCollectionChangePlanError):
            require_unblocked_collection_change_plan(plan)

    def test_conflict_plan_raises_with_blocked_fields(self) -> None:
        plan = _plan(
            _proposal(
                "country",
                CollectionChangeOperation.CONFLICT,
            ),
            _proposal("year", CollectionChangeOperation.CLEAR),
        )
        with self.assertRaises(
            BlockedCollectionChangePlanError
        ) as captured:
            require_unblocked_collection_change_plan(plan)
        self.assertEqual(captured.exception.record_id, "record-1")
        self.assertEqual(
            captured.exception.target_fields,
            ("country", "year"),
        )

    def test_blocked_plan_and_proposals_remain_unchanged(self) -> None:
        plan = _plan(
            _proposal(
                "country",
                CollectionChangeOperation.CONFLICT,
            )
        )
        before = repr(plan)
        proposal = plan.proposals[0]
        with self.assertRaises(BlockedCollectionChangePlanError):
            require_unblocked_collection_change_plan(plan)
        self.assertEqual(repr(plan), before)
        self.assertIs(plan.proposals[0], proposal)


class ValidationAndDriftTests(unittest.TestCase):
    def test_assessment_rejects_false_status(self) -> None:
        proposal = _proposal(
            "country",
            CollectionChangeOperation.ADD,
        )
        assessment = CollectionChangePolicyAssessment(
            proposal,
            CollectionChangePolicyStatus.SAFE_NO_OP,
        )
        with self.assertRaises(
            InvalidCollectionChangePolicyContextError
        ):
            assessment.validate()

    def test_summary_flags_are_structurally_validated(self) -> None:
        result = assess_collection_change_plan(_plan())
        for field_name in (
            "contains_blocked_items",
            "contains_approval_required_items",
            "contains_only_safe_no_ops",
        ):
            with self.subTest(field=field_name):
                invalid = replace(
                    result,
                    **{
                        field_name: not getattr(result, field_name),
                    },
                )
                with self.assertRaises(
                    InvalidCollectionChangePolicyContextError
                ):
                    invalid.validate()

    def test_assessment_count_must_equal_proposal_count(self) -> None:
        result = assess_collection_change_plan(_plan())
        with self.assertRaises(
            InvalidCollectionChangePolicyContextError
        ):
            replace(result, assessments=()).validate()

    def test_assessment_requires_exact_proposal_identity(self) -> None:
        result = assess_collection_change_plan(_plan())
        equivalent = replace(result.assessments[0].proposal)
        invalid_entry = replace(
            result.assessments[0],
            proposal=equivalent,
        )
        with self.assertRaises(
            InvalidCollectionChangePolicyContextError
        ):
            replace(result, assessments=(invalid_entry,)).validate()

    def test_missing_future_policy_fails_closed(self) -> None:
        plan = _plan(
            _proposal("country", CollectionChangeOperation.ADD)
        )
        empty_policy: MappingProxyType[
            CollectionChangeOperation,
            CollectionChangePolicyStatus,
        ] = MappingProxyType({})
        with patch.object(
            policy_module,
            "_OPERATION_POLICY",
            empty_policy,
        ):
            with self.assertRaises(
                UnsupportedCollectionChangePolicyOperationError
            ):
                assess_collection_change_plan(plan)

    def test_unit_1a_approval_mismatch_fails_before_assessment(self) -> None:
        proposal = replace(
            _proposal("country", CollectionChangeOperation.ADD),
            approval_requirement=(
                CollectionChangeApprovalRequirement.NOT_REQUIRED
            ),
        )
        plan = replace(_plan(), proposals=(proposal,))
        with self.assertRaisesRegex(ValueError, "requires"):
            assess_collection_change_plan(plan)

    def test_unit_1a_reason_mismatch_fails_before_assessment(self) -> None:
        proposal = replace(
            _proposal("country", CollectionChangeOperation.ADD),
            reason_code=CollectionChangeReasonCode.DIFFERENT_VALUE,
        )
        plan = replace(_plan(), proposals=(proposal,))
        with self.assertRaisesRegex(ValueError, "requires"):
            assess_collection_change_plan(plan)

    def test_input_type_is_strict(self) -> None:
        with self.assertRaisesRegex(TypeError, "CollectionChangePlan"):
            assess_collection_change_plan(object())  # type: ignore[arg-type]


class TraceabilityAndImmutabilityTests(unittest.TestCase):
    def test_complete_plan_and_source_traceability_is_retained(self) -> None:
        plan = _plan(
            _proposal("country", CollectionChangeOperation.UPDATE)
        )
        result = assess_collection_change_plan(plan)
        proposal = result.assessments[0].proposal
        self.assertIs(result.plan, plan)
        self.assertIs(proposal, plan.proposals[0])
        self.assertIs(
            proposal.source_observation,
            plan.proposals[0].source_observation,
        )
        self.assertIs(
            proposal.source_observation.provenance,
            plan.proposals[0].source_observation.provenance,
        )
        self.assertEqual(result.plan.review_session_id, "review-session-1")
        self.assertEqual(
            result.plan.source_fingerprint,
            "opaque-source-fingerprint",
        )

    def test_source_plan_and_nested_objects_remain_unchanged(self) -> None:
        plan = _plan(
            _proposal("country", CollectionChangeOperation.UPDATE)
        )
        before = repr(plan)
        proposal = plan.proposals[0]
        observation = proposal.source_observation
        provenance = observation.provenance
        assess_collection_change_plan(plan)
        self.assertEqual(repr(plan), before)
        self.assertIs(plan.proposals[0], proposal)
        self.assertIs(proposal.source_observation, observation)
        self.assertIs(observation.provenance, provenance)

    def test_dtos_are_frozen_and_slotted(self) -> None:
        result = assess_collection_change_plan(_plan())
        for value in (result, result.assessments[0]):
            with self.subTest(contract=type(value).__name__):
                self.assertFalse(hasattr(value, "__dict__"))
                with self.assertRaises(FrozenInstanceError):
                    value.extra = "mutation"  # type: ignore[attr-defined]

    def test_assessor_is_stateless_and_slotted(self) -> None:
        self.assertFalse(
            hasattr(CollectionChangePolicyAssessor(), "__dict__")
        )

    def test_repeated_assessments_are_equivalent(self) -> None:
        plan = _plan(
            _proposal("country", CollectionChangeOperation.ADD)
        )
        first = assess_collection_change_plan(plan)
        second = assess_collection_change_plan(plan)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIs(first.plan, second.plan)

    def test_repeated_strict_assessment_is_deterministic(self) -> None:
        unblocked = _plan(
            _proposal("country", CollectionChangeOperation.ADD)
        )
        self.assertEqual(
            require_unblocked_collection_change_plan(unblocked),
            require_unblocked_collection_change_plan(unblocked),
        )

        blocked = _plan(
            _proposal("country", CollectionChangeOperation.CONFLICT)
        )
        errors: list[BlockedCollectionChangePlanError] = []
        for _ in range(2):
            with self.assertRaises(
                BlockedCollectionChangePlanError
            ) as captured:
                require_unblocked_collection_change_plan(blocked)
            errors.append(captured.exception)
        self.assertEqual(
            tuple(error.target_fields for error in errors),
            (("country",), ("country",)),
        )

    def test_no_assessment_serialization_surface(self) -> None:
        for contract in (
            CollectionChangePolicyAssessment,
            CollectionChangePlanPolicyAssessment,
        ):
            self.assertFalse(hasattr(contract, "to_dict"))
            self.assertFalse(hasattr(contract, "from_dict"))


class ErrorAndArchitectureTests(unittest.TestCase):
    def test_error_hierarchy_is_narrow(self) -> None:
        for error_type in (
            UnsupportedCollectionChangePolicyOperationError,
            InvalidCollectionChangePolicyContextError,
            BlockedCollectionChangePlanError,
        ):
            with self.subTest(error=error_type.__name__):
                self.assertTrue(
                    issubclass(error_type, CollectionChangePolicyError)
                )

    def test_output_fields_are_non_authorizing(self) -> None:
        fields = (
            tuple(CollectionChangePolicyAssessment.__dataclass_fields__)
            + tuple(
                CollectionChangePlanPolicyAssessment.__dataclass_fields__
            )
        )
        for fragment in (
            "approved",
            "authorized",
            "executable",
            "applied",
            "persisted",
            "decision",
            "token",
        ):
            self.assertFalse(
                any(fragment in field for field in fields),
                fields,
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
            "workflow_collection_change_plan_builder",
            "workflow_collection_change_proposal_builder",
            "workflow_collection_record_comparison",
            "workflow_confirmed_collection_field_mapper",
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

    def test_module_has_no_approval_execution_or_mutation_surface(
        self,
    ) -> None:
        module = importlib.import_module(_MODULE)
        source = inspect.getsource(module)
        for fragment in (
            "approved_by",
            "approved_at",
            "approval_token",
            "executable",
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
                "CollectionChangePolicyStatus",
                "CollectionChangePolicyError",
                "UnsupportedCollectionChangePolicyOperationError",
                "InvalidCollectionChangePolicyContextError",
                "BlockedCollectionChangePlanError",
                "CollectionChangePolicyAssessment",
                "CollectionChangePlanPolicyAssessment",
                "CollectionChangePolicyAssessor",
                "assess_collection_change_plan",
                "require_unblocked_collection_change_plan",
            },
        )


if __name__ == "__main__":
    unittest.main()
