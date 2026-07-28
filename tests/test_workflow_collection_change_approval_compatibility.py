"""Tests for pure collection-change approval compatibility validation."""

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
from collection_management.workflow_collection_change_approval_compatibility import (
    CollectionChangeApprovalCompatibilityError,
    CollectionChangeApprovalCompatibilityFinding,
    CollectionChangeApprovalCompatibilityReason,
    CollectionChangeApprovalCompatibilityStatus,
    CollectionChangeApprovalCompatibilityValidator,
    CollectionChangePlanApprovalCompatibility,
    IncompatibleCollectionChangeApprovalError,
    InvalidCollectionChangeApprovalCompatibilityContextError,
    MismatchedCollectionChangeApprovalPlanError,
    UnmatchedCollectionChangeApprovalDecisionError,
    UnresolvedCollectionChangeApprovalError,
    require_compatible_collection_change_approval,
    require_resolved_collection_change_approval,
    validate_collection_change_approval_compatibility,
)
import collection_management.workflow_collection_change_approval_compatibility as compatibility_module
from collection_management.workflow_collection_change_approval_models import (
    CURRENT_COLLECTION_CHANGE_APPROVAL_SCHEMA_VERSION,
    CollectionChangeApprovalDecision,
    CollectionChangePlanApproval,
    CollectionChangeProposalApproval,
    create_collection_change_proposal_reference,
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
from collection_management.workflow_collection_change_policy import (
    CollectionChangePolicyStatus,
    assess_collection_change_plan,
)


_MODULE = (
    "collection_management.workflow_collection_change_approval_compatibility"
)
_TIME = "2026-07-28T18:00:00Z"
_VALUES = {
    "country": "Canada",
    "denomination": "25 cents",
    "year": "1967",
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
    *,
    source_coin_id: str = "source-coin-1",
) -> ConfirmedFieldObservation:
    return ConfirmedFieldObservation(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id=source_coin_id,
        field_name=field_name,
        submitted_value=value,
        canonical_value=None,
        reviewer_id="reviewer-1",
        provenance=(
            ConfirmedObservationProvenance(
                provider_id="test-ocr",
                image_role="front",
                artifact_key=f"crop-{field_name}",
                source_value=value,
                confidence_score=95.0,
                evidence=("human reviewed",),
            ),
        ),
        source_type=ConfirmedObservationSource.OCR_REVIEW,
        rationale="Human reviewed.",
    )


def _proposal(
    target_field: str,
    operation: CollectionChangeOperation,
    *,
    record_id: str = "record-1",
    source_coin_id: str = "source-coin-1",
) -> CollectionFieldChangeProposal:
    value = _VALUES[target_field]
    if operation is CollectionChangeOperation.ADD:
        current: str | None = None
        proposed: str | None = value
    elif operation is CollectionChangeOperation.UPDATE:
        current = f"old-{target_field}"
        proposed = value
    elif operation is CollectionChangeOperation.CLEAR:
        current = f"old-{target_field}"
        proposed = None
    elif operation is CollectionChangeOperation.NO_CHANGE:
        current = value
        proposed = value
    elif operation is CollectionChangeOperation.CONFLICT:
        current = f"conflict-{target_field}"
        proposed = value
    else:
        raise AssertionError(operation)
    approval, reason = _STRUCTURE[operation]
    result = CollectionFieldChangeProposal(
        schema_version=CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
        target_record=CollectionRecordReference(record_id),
        target_field=target_field,
        current_value=current,
        proposed_value=proposed,
        operation=operation,
        approval_requirement=approval,
        source_observation=_observation(
            target_field,
            value,
            source_coin_id=source_coin_id,
        ),
        reason_code=reason,
        rationale="Human reviewed.",
    )
    result.validate()
    return result


def _plan(
    *proposals: CollectionFieldChangeProposal,
    record_id: str = "record-1",
    source_coin_id: str = "source-coin-1",
    review_session_id: str | None = "review-session-1",
    source_fingerprint: str | None = "source-fingerprint-1",
) -> CollectionChangePlan:
    result = CollectionChangePlan(
        schema_version=CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
        target_record=CollectionRecordReference(record_id),
        source_coin_id=source_coin_id,
        proposals=tuple(
            sorted(proposals, key=lambda item: item.target_field)
        ),
        review_session_id=review_session_id,
        source_fingerprint=source_fingerprint,
    )
    result.validate()
    return result


def _decision(
    plan: CollectionChangePlan,
    proposal: CollectionFieldChangeProposal,
    decision: CollectionChangeApprovalDecision,
) -> CollectionChangeProposalApproval:
    result = CollectionChangeProposalApproval(
        schema_version=(
            CURRENT_COLLECTION_CHANGE_APPROVAL_SCHEMA_VERSION
        ),
        proposal_reference=create_collection_change_proposal_reference(
            plan,
            proposal,
        ),
        decision=decision,
        approver_id="approver-1",
        decided_at=_TIME,
        rationale=None,
    )
    result.validate()
    return result


def _approval(
    plan: CollectionChangePlan,
    decisions: tuple[CollectionChangeProposalApproval, ...],
) -> CollectionChangePlanApproval:
    result = CollectionChangePlanApproval(
        schema_version=(
            CURRENT_COLLECTION_CHANGE_APPROVAL_SCHEMA_VERSION
        ),
        target_record=plan.target_record,
        source_coin_id=plan.source_coin_id,
        review_session_id=plan.review_session_id,
        source_fingerprint=plan.source_fingerprint,
        plan_schema_version=plan.schema_version,
        decisions=decisions,
    )
    result.validate()
    return result


def _matrix_finding(
    operation: CollectionChangeOperation,
    decision: CollectionChangeApprovalDecision | None,
) -> CollectionChangeApprovalCompatibilityFinding:
    target = _proposal("country", operation)
    if decision is None:
        anchor = _proposal("year", CollectionChangeOperation.UPDATE)
        plan = _plan(target, anchor)
        record = _approval(
            plan,
            (
                _decision(
                    plan,
                    next(
                        item
                        for item in plan.proposals
                        if item.target_field == "year"
                    ),
                    CollectionChangeApprovalDecision.APPROVE,
                ),
            ),
        )
    else:
        plan = _plan(target)
        record = _approval(
            plan,
            (_decision(plan, plan.proposals[0], decision),),
        )
    result = validate_collection_change_approval_compatibility(
        assess_collection_change_plan(plan),
        record,
    )
    return next(
        item
        for item in result.findings
        if item.policy_assessment.proposal.target_field == "country"
    )


class MatrixTests(unittest.TestCase):
    def test_vocabularies_are_exact(self) -> None:
        self.assertEqual(
            tuple(
                item.value
                for item in CollectionChangeApprovalCompatibilityStatus
            ),
            (
                "COMPATIBLE_RESOLVED",
                "COMPATIBLE_UNRESOLVED",
                "INCOMPATIBLE",
            ),
        )
        self.assertEqual(
            tuple(
                item.value
                for item in CollectionChangeApprovalCompatibilityReason
            ),
            (
                "SAFE_NO_OP_WITHOUT_DECISION",
                "UNEXPECTED_APPROVAL_FOR_SAFE_NO_OP",
                "UNEXPECTED_REJECTION_FOR_SAFE_NO_OP",
                "UNEXPECTED_DEFERRAL_FOR_SAFE_NO_OP",
                "APPROVAL_REQUIRED_APPROVED",
                "APPROVAL_REQUIRED_REJECTED",
                "APPROVAL_REQUIRED_DEFERRED",
                "MISSING_REQUIRED_DECISION",
                "BLOCKED_WITHOUT_DECISION",
                "BLOCKED_REJECTED",
                "BLOCKED_DEFERRED",
                "FORBIDDEN_APPROVAL_FOR_BLOCKED",
            ),
        )

    def test_policy_matrix_is_exact_immutable_and_exhaustive(self) -> None:
        self.assertIsInstance(
            compatibility_module._POLICY_MATRIX,
            MappingProxyType,
        )
        self.assertEqual(
            set(compatibility_module._POLICY_MATRIX),
            {
                (status, decision)
                for status in CollectionChangePolicyStatus
                for decision in (
                    None,
                    *tuple(CollectionChangeApprovalDecision),
                )
            },
        )
        with self.assertRaises(TypeError):
            compatibility_module._POLICY_MATRIX[
                (CollectionChangePolicyStatus.SAFE_NO_OP, None)
            ] = (  # type: ignore[index]
                CollectionChangeApprovalCompatibilityStatus.INCOMPATIBLE,
                CollectionChangeApprovalCompatibilityReason.MISSING_REQUIRED_DECISION,
            )

    def test_all_twelve_policy_combinations(self) -> None:
        S = CollectionChangeApprovalCompatibilityStatus
        R = CollectionChangeApprovalCompatibilityReason
        D = CollectionChangeApprovalDecision
        cases = (
            (CollectionChangeOperation.NO_CHANGE, None, S.COMPATIBLE_RESOLVED, R.SAFE_NO_OP_WITHOUT_DECISION),
            (CollectionChangeOperation.NO_CHANGE, D.APPROVE, S.INCOMPATIBLE, R.UNEXPECTED_APPROVAL_FOR_SAFE_NO_OP),
            (CollectionChangeOperation.NO_CHANGE, D.REJECT, S.INCOMPATIBLE, R.UNEXPECTED_REJECTION_FOR_SAFE_NO_OP),
            (CollectionChangeOperation.NO_CHANGE, D.DEFER, S.INCOMPATIBLE, R.UNEXPECTED_DEFERRAL_FOR_SAFE_NO_OP),
            (CollectionChangeOperation.UPDATE, None, S.INCOMPATIBLE, R.MISSING_REQUIRED_DECISION),
            (CollectionChangeOperation.UPDATE, D.APPROVE, S.COMPATIBLE_RESOLVED, R.APPROVAL_REQUIRED_APPROVED),
            (CollectionChangeOperation.UPDATE, D.REJECT, S.COMPATIBLE_RESOLVED, R.APPROVAL_REQUIRED_REJECTED),
            (CollectionChangeOperation.UPDATE, D.DEFER, S.COMPATIBLE_UNRESOLVED, R.APPROVAL_REQUIRED_DEFERRED),
            (CollectionChangeOperation.CONFLICT, None, S.COMPATIBLE_UNRESOLVED, R.BLOCKED_WITHOUT_DECISION),
            (CollectionChangeOperation.CONFLICT, D.APPROVE, S.INCOMPATIBLE, R.FORBIDDEN_APPROVAL_FOR_BLOCKED),
            (CollectionChangeOperation.CONFLICT, D.REJECT, S.COMPATIBLE_RESOLVED, R.BLOCKED_REJECTED),
            (CollectionChangeOperation.CONFLICT, D.DEFER, S.COMPATIBLE_UNRESOLVED, R.BLOCKED_DEFERRED),
        )
        for operation, decision, status, reason in cases:
            with self.subTest(operation=operation, decision=decision):
                finding = _matrix_finding(operation, decision)
                self.assertIs(finding.status, status)
                self.assertIs(finding.reason, reason)


class BindingTests(unittest.TestCase):
    def test_exact_plan_and_proposal_binding_is_accepted(self) -> None:
        plan = _plan(_proposal("country", CollectionChangeOperation.UPDATE))
        policy = assess_collection_change_plan(plan)
        decision = _decision(
            plan,
            plan.proposals[0],
            CollectionChangeApprovalDecision.APPROVE,
        )
        record = _approval(plan, (decision,))
        result = validate_collection_change_approval_compatibility(
            policy,
            record,
        )
        self.assertIs(result.policy_assessment, policy)
        self.assertIs(result.approval_record, record)
        self.assertIs(result.findings[0].policy_assessment, policy.assessments[0])
        self.assertIs(result.findings[0].approval_decision, decision)

    def test_independently_deserialized_inputs_bind_by_durable_value(
        self,
    ) -> None:
        original_plan = _plan(
            _proposal("country", CollectionChangeOperation.UPDATE)
        )
        original_record = _approval(
            original_plan,
            (
                _decision(
                    original_plan,
                    original_plan.proposals[0],
                    CollectionChangeApprovalDecision.APPROVE,
                ),
            ),
        )
        plan = CollectionChangePlan.from_dict(original_plan.to_dict())
        record = CollectionChangePlanApproval.from_dict(
            original_record.to_dict()
        )
        policy = assess_collection_change_plan(plan)

        self.assertIsNot(plan, original_plan)
        self.assertIsNot(record, original_record)
        result = validate_collection_change_approval_compatibility(
            policy,
            record,
        )
        self.assertIs(result.policy_assessment, policy)
        self.assertIs(result.approval_record, record)
        self.assertIs(
            result.findings[0].approval_decision,
            record.decisions[0],
        )

    def test_plan_linkage_mismatches_are_typed(self) -> None:
        plan = _plan(_proposal("country", CollectionChangeOperation.UPDATE))
        policy = assess_collection_change_plan(plan)
        variants = (
            dict(record_id="record-2", source_coin_id="source-coin-2"),
            dict(source_coin_id="source-coin-2", record_id="record-2"),
            dict(review_session_id="review-session-2"),
            dict(source_fingerprint="source-fingerprint-2"),
            dict(review_session_id=None, source_fingerprint=None),
        )
        for kwargs in variants:
            with self.subTest(kwargs=kwargs):
                record_id = kwargs.get("record_id", "record-1")
                source_id = kwargs.get("source_coin_id", "source-coin-1")
                other = _plan(
                    _proposal(
                        "country",
                        CollectionChangeOperation.UPDATE,
                        record_id=record_id,
                        source_coin_id=source_id,
                    ),
                    record_id=record_id,
                    source_coin_id=source_id,
                    review_session_id=kwargs.get(
                        "review_session_id",
                        "review-session-1",
                    ),
                    source_fingerprint=kwargs.get(
                        "source_fingerprint",
                        "source-fingerprint-1",
                    ),
                )
                record = _approval(
                    other,
                    (
                        _decision(
                            other,
                            other.proposals[0],
                            CollectionChangeApprovalDecision.APPROVE,
                        ),
                    ),
                )
                with self.assertRaises(
                    MismatchedCollectionChangeApprovalPlanError
                ):
                    validate_collection_change_approval_compatibility(
                        policy,
                        record,
                    )

    def test_changed_proposal_reference_is_unmatched(self) -> None:
        plan = _plan(_proposal("country", CollectionChangeOperation.UPDATE))
        policy = assess_collection_change_plan(plan)
        decision = _decision(
            plan,
            plan.proposals[0],
            CollectionChangeApprovalDecision.APPROVE,
        )
        reference = decision.proposal_reference
        variants = (
            replace(reference, operation=CollectionChangeOperation.CONFLICT),
            replace(reference, current_value="changed-current"),
            replace(reference, proposed_value="changed-proposed"),
            replace(reference, source_field_name="year"),
        )
        for changed in variants:
            with self.subTest(reference=changed):
                record = _approval(
                    plan,
                    (replace(decision, proposal_reference=changed),),
                )
                with self.assertRaises(
                    UnmatchedCollectionChangeApprovalDecisionError
                ):
                    validate_collection_change_approval_compatibility(
                        policy,
                        record,
                    )

    def test_input_types_are_strict(self) -> None:
        plan = _plan(_proposal("country", CollectionChangeOperation.UPDATE))
        policy = assess_collection_change_plan(plan)
        record = _approval(
            plan,
            (
                _decision(
                    plan,
                    plan.proposals[0],
                    CollectionChangeApprovalDecision.APPROVE,
                ),
            ),
        )
        with self.assertRaises(TypeError):
            validate_collection_change_approval_compatibility(
                object(),  # type: ignore[arg-type]
                record,
            )
        with self.assertRaises(TypeError):
            validate_collection_change_approval_compatibility(
                policy,
                object(),  # type: ignore[arg-type]
            )


class SummaryAndCompletenessTests(unittest.TestCase):
    def _result(
        self,
        operations: tuple[CollectionChangeOperation, ...],
        decisions: dict[str, CollectionChangeApprovalDecision],
    ) -> CollectionChangePlanApprovalCompatibility:
        fields = ("country", "denomination", "year")
        proposals = tuple(
            _proposal(field, operation)
            for field, operation in zip(fields, operations)
        )
        plan = _plan(*proposals)
        entries = tuple(
            _decision(plan, proposal, decisions[proposal.target_field])
            for proposal in plan.proposals
            if proposal.target_field in decisions
        )
        return validate_collection_change_approval_compatibility(
            assess_collection_change_plan(plan),
            _approval(plan, entries),
        )

    def test_approved_required_decisions_are_complete(self) -> None:
        result = self._result(
            (CollectionChangeOperation.UPDATE,),
            {"country": CollectionChangeApprovalDecision.APPROVE},
        )
        self.assertTrue(result.required_decisions_complete)
        self.assertTrue(result.contains_approve_decisions)
        self.assertFalse(result.contains_incompatible_items)
        self.assertFalse(result.contains_unresolved_items)

    def test_rejected_required_decisions_are_complete_but_rejected(self) -> None:
        result = self._result(
            (CollectionChangeOperation.UPDATE,),
            {"country": CollectionChangeApprovalDecision.REJECT},
        )
        self.assertTrue(result.required_decisions_complete)
        self.assertTrue(result.contains_reject_decisions)
        self.assertFalse(result.contains_incompatible_items)

    def test_deferred_required_decisions_are_incomplete_and_unresolved(
        self,
    ) -> None:
        result = self._result(
            (CollectionChangeOperation.UPDATE,),
            {"country": CollectionChangeApprovalDecision.DEFER},
        )
        self.assertFalse(result.required_decisions_complete)
        self.assertTrue(result.contains_unresolved_items)
        self.assertTrue(result.contains_defer_decisions)
        self.assertFalse(result.contains_incompatible_items)

    def test_missing_required_decision_is_incomplete_and_incompatible(
        self,
    ) -> None:
        result = self._result(
            (
                CollectionChangeOperation.UPDATE,
                CollectionChangeOperation.UPDATE,
            ),
            {"denomination": CollectionChangeApprovalDecision.APPROVE},
        )
        self.assertFalse(result.required_decisions_complete)
        self.assertTrue(result.contains_incompatible_items)

    def test_mixed_approve_reject_is_complete(self) -> None:
        result = self._result(
            (
                CollectionChangeOperation.UPDATE,
                CollectionChangeOperation.UPDATE,
            ),
            {
                "country": CollectionChangeApprovalDecision.APPROVE,
                "denomination": CollectionChangeApprovalDecision.REJECT,
            },
        )
        self.assertTrue(result.required_decisions_complete)
        self.assertTrue(result.contains_approve_decisions)
        self.assertTrue(result.contains_reject_decisions)

    def test_blocked_and_safe_entries_do_not_affect_required_completeness(
        self,
    ) -> None:
        result = self._result(
            (
                CollectionChangeOperation.CONFLICT,
                CollectionChangeOperation.NO_CHANGE,
                CollectionChangeOperation.UPDATE,
            ),
            {"year": CollectionChangeApprovalDecision.APPROVE},
        )
        self.assertTrue(result.required_decisions_complete)
        self.assertTrue(result.contains_blocked_items)
        self.assertTrue(result.contains_unresolved_items)

    def test_summary_flags_cannot_drift(self) -> None:
        result = self._result(
            (CollectionChangeOperation.UPDATE,),
            {"country": CollectionChangeApprovalDecision.APPROVE},
        )
        fields = (
            "contains_incompatible_items",
            "contains_unresolved_items",
            "contains_blocked_items",
            "required_decisions_complete",
            "contains_approve_decisions",
            "contains_reject_decisions",
            "contains_defer_decisions",
        )
        for field_name in fields:
            with self.subTest(field=field_name):
                with self.assertRaises(
                    InvalidCollectionChangeApprovalCompatibilityContextError
                ):
                    replace(
                        result,
                        **{
                            field_name: not getattr(result, field_name),
                        },
                    ).validate()


class StrictHelperTests(unittest.TestCase):
    def test_compatible_resolved_returns_diagnostic_result(self) -> None:
        plan = _plan(_proposal("country", CollectionChangeOperation.UPDATE))
        policy = assess_collection_change_plan(plan)
        record = _approval(
            plan,
            (
                _decision(
                    plan,
                    plan.proposals[0],
                    CollectionChangeApprovalDecision.APPROVE,
                ),
            ),
        )
        self.assertEqual(
            require_resolved_collection_change_approval(policy, record),
            validate_collection_change_approval_compatibility(
                policy,
                record,
            ),
        )

    def test_compatible_unresolved_returns_from_compatible_helper(self) -> None:
        plan = _plan(_proposal("country", CollectionChangeOperation.UPDATE))
        policy = assess_collection_change_plan(plan)
        record = _approval(
            plan,
            (
                _decision(
                    plan,
                    plan.proposals[0],
                    CollectionChangeApprovalDecision.DEFER,
                ),
            ),
        )
        result = require_compatible_collection_change_approval(policy, record)
        self.assertTrue(result.contains_unresolved_items)
        with self.assertRaises(UnresolvedCollectionChangeApprovalError):
            require_resolved_collection_change_approval(policy, record)

    def test_incompatible_helper_identifies_fields_in_plan_order(self) -> None:
        plan = _plan(
            _proposal("country", CollectionChangeOperation.NO_CHANGE),
            _proposal("year", CollectionChangeOperation.NO_CHANGE),
        )
        policy = assess_collection_change_plan(plan)
        record = _approval(
            plan,
            tuple(
                _decision(
                    plan,
                    proposal,
                    CollectionChangeApprovalDecision.APPROVE,
                )
                for proposal in plan.proposals
            ),
        )
        with self.assertRaises(
            IncompatibleCollectionChangeApprovalError
        ) as captured:
            require_compatible_collection_change_approval(policy, record)
        self.assertEqual(
            captured.exception.target_fields,
            ("country", "year"),
        )

    def test_blocked_reject_is_resolved_but_remains_blocked(self) -> None:
        plan = _plan(
            _proposal("country", CollectionChangeOperation.CONFLICT)
        )
        policy = assess_collection_change_plan(plan)
        record = _approval(
            plan,
            (
                _decision(
                    plan,
                    plan.proposals[0],
                    CollectionChangeApprovalDecision.REJECT,
                ),
            ),
        )
        result = require_resolved_collection_change_approval(policy, record)
        self.assertTrue(result.contains_blocked_items)
        self.assertFalse(result.contains_unresolved_items)
        self.assertFalse(
            any(
                fragment in field
                for field in result.__dataclass_fields__
                for fragment in ("authorized", "executable", "mutation")
            )
        )


class ImmutabilityAndArchitectureTests(unittest.TestCase):
    def test_findings_preserve_plan_order_and_exact_identities(self) -> None:
        plan = _plan(
            _proposal("year", CollectionChangeOperation.UPDATE),
            _proposal("country", CollectionChangeOperation.UPDATE),
        )
        policy = assess_collection_change_plan(plan)
        decisions = tuple(
            _decision(
                plan,
                proposal,
                CollectionChangeApprovalDecision.APPROVE,
            )
            for proposal in plan.proposals
        )
        record = _approval(plan, decisions)
        result = validate_collection_change_approval_compatibility(
            policy,
            record,
        )
        for finding, assessment, decision in zip(
            result.findings,
            policy.assessments,
            decisions,
        ):
            self.assertIs(finding.policy_assessment, assessment)
            self.assertIs(finding.approval_decision, decision)

    def test_reconstructed_result_rejects_misbound_finding_decision(
        self,
    ) -> None:
        plan = _plan(
            _proposal("country", CollectionChangeOperation.UPDATE),
            _proposal("year", CollectionChangeOperation.UPDATE),
        )
        policy = assess_collection_change_plan(plan)
        decisions = tuple(
            _decision(
                plan,
                proposal,
                CollectionChangeApprovalDecision.APPROVE,
            )
            for proposal in plan.proposals
        )
        record = _approval(plan, decisions)
        result = validate_collection_change_approval_compatibility(
            policy,
            record,
        )
        changed_findings = (
            replace(
                result.findings[0],
                approval_decision=decisions[1],
            ),
            replace(
                result.findings[1],
                approval_decision=decisions[0],
            ),
        )
        changed = replace(result, findings=changed_findings)
        with self.assertRaises(
            InvalidCollectionChangeApprovalCompatibilityContextError
        ):
            changed.validate()

    def test_reconstructed_finding_rejects_proposal_reference_drift(
        self,
    ) -> None:
        finding = _matrix_finding(
            CollectionChangeOperation.UPDATE,
            CollectionChangeApprovalDecision.APPROVE,
        )
        assert finding.approval_decision is not None
        changed_reference = replace(
            finding.approval_decision.proposal_reference,
            current_value="different-current",
        )
        changed_decision = replace(
            finding.approval_decision,
            proposal_reference=changed_reference,
        )
        changed = replace(
            finding,
            approval_decision=changed_decision,
        )
        with self.assertRaises(
            InvalidCollectionChangeApprovalCompatibilityContextError
        ):
            changed.validate()

    def test_results_are_frozen_slotted_and_transient(self) -> None:
        finding = _matrix_finding(
            CollectionChangeOperation.UPDATE,
            CollectionChangeApprovalDecision.APPROVE,
        )
        plan = _plan(_proposal("country", CollectionChangeOperation.UPDATE))
        policy = assess_collection_change_plan(plan)
        record = _approval(
            plan,
            (
                _decision(
                    plan,
                    plan.proposals[0],
                    CollectionChangeApprovalDecision.APPROVE,
                ),
            ),
        )
        result = validate_collection_change_approval_compatibility(
            policy,
            record,
        )
        for value in (finding, result):
            self.assertFalse(hasattr(value, "__dict__"))
            with self.assertRaises(FrozenInstanceError):
                value.extra = True  # type: ignore[attr-defined]
            self.assertFalse(hasattr(type(value), "to_dict"))
            self.assertFalse(hasattr(type(value), "from_dict"))

    def test_repeated_validation_is_equivalent_and_inputs_unchanged(
        self,
    ) -> None:
        plan = _plan(_proposal("country", CollectionChangeOperation.UPDATE))
        policy = assess_collection_change_plan(plan)
        record = _approval(
            plan,
            (
                _decision(
                    plan,
                    plan.proposals[0],
                    CollectionChangeApprovalDecision.APPROVE,
                ),
            ),
        )
        before = (repr(policy), repr(record))
        first = validate_collection_change_approval_compatibility(
            policy,
            record,
        )
        second = validate_collection_change_approval_compatibility(
            policy,
            record,
        )
        self.assertEqual(first, second)
        self.assertEqual((repr(policy), repr(record)), before)

    def test_future_matrix_gap_fails_closed(self) -> None:
        plan = _plan(_proposal("country", CollectionChangeOperation.UPDATE))
        policy = assess_collection_change_plan(plan)
        record = _approval(
            plan,
            (
                _decision(
                    plan,
                    plan.proposals[0],
                    CollectionChangeApprovalDecision.APPROVE,
                ),
            ),
        )
        with patch.object(
            compatibility_module,
            "_POLICY_MATRIX",
            MappingProxyType({}),
        ):
            with self.assertRaises(
                InvalidCollectionChangeApprovalCompatibilityContextError
            ):
                validate_collection_change_approval_compatibility(
                    policy,
                    record,
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
            "repository",
            "persistence",
            "mutation",
            "execution",
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
                    any(fragment in name.casefold() for name in imported),
                    imported,
                )
        self.assertNotIn("os", imported)

    def test_module_has_no_authorization_or_automatic_surface(self) -> None:
        source = inspect.getsource(importlib.import_module(_MODULE))
        for fragment in (
            "datetime.now",
            "uuid4",
            "getenv",
            "open(",
            "save(",
            "execute(",
            "apply(",
            "authorized",
            "executable",
            "ready_to_mutate",
            "mutation_allowed",
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
                "CollectionChangeApprovalCompatibilityError",
                "MismatchedCollectionChangeApprovalPlanError",
                "UnmatchedCollectionChangeApprovalDecisionError",
                "InvalidCollectionChangeApprovalCompatibilityContextError",
                "IncompatibleCollectionChangeApprovalError",
                "UnresolvedCollectionChangeApprovalError",
                "CollectionChangeApprovalCompatibilityStatus",
                "CollectionChangeApprovalCompatibilityReason",
                "CollectionChangeApprovalCompatibilityFinding",
                "CollectionChangePlanApprovalCompatibility",
                "CollectionChangeApprovalCompatibilityValidator",
                "validate_collection_change_approval_compatibility",
                "require_compatible_collection_change_approval",
                "require_resolved_collection_change_approval",
            },
        )


if __name__ == "__main__":
    unittest.main()
