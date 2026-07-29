"""Tests for approval-and-freshness mutation eligibility composition."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import inspect
import unittest
from unittest.mock import patch

from capture_import.workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedFieldObservation,
    ConfirmedObservationProvenance,
    ConfirmedObservationSource,
)
from collection_management.workflow_collection_change_approval_compatibility import (
    CollectionChangeApprovalCompatibilityReason,
    CollectionChangePlanApprovalCompatibility,
    validate_collection_change_approval_compatibility,
)
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
    assess_collection_change_plan,
)
from collection_management.workflow_collection_freshness_compatibility import (
    CollectionChangePlanFreshnessCompatibility,
    CollectionFreshnessCompatibilityFinding,
    CollectionFreshnessCompatibilityStatus,
    validate_collection_freshness_compatibility,
)
from collection_management.workflow_collection_freshness_evidence_models import (
    CURRENT_COLLECTION_FRESHNESS_EVIDENCE_SCHEMA_VERSION,
    CollectionFreshnessFieldAvailability,
    CollectionFreshnessFieldEvidence,
    CollectionRecordFreshnessEvidence,
)
from collection_management.workflow_collection_mutation_eligibility import (
    CollectionChangePlanMutationEligibility,
    CollectionMutationEligibilityComposer,
    CollectionMutationEligibilityError,
    CollectionMutationEligibilityFinding,
    CollectionMutationEligibilityReason,
    CollectionMutationEligibilityStatus,
    InvalidCollectionMutationEligibilityContextError,
    MisalignedCollectionMutationEligibilityFindingError,
    MismatchedCollectionMutationEligibilityPlanError,
    compose_collection_mutation_eligibility,
)
import collection_management.workflow_collection_mutation_eligibility as eligibility_module


_MODULE = "collection_management.workflow_collection_mutation_eligibility"
_TIME = "2026-07-29T12:00:00Z"
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


def _observation(field_name: str, value: str) -> ConfirmedFieldObservation:
    return ConfirmedFieldObservation(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id="source-1",
        field_name=field_name,
        submitted_value=value,
        canonical_value=None,
        reviewer_id="reviewer-1",
        provenance=(
            ConfirmedObservationProvenance(
                provider_id="test",
                image_role="front",
                artifact_key=f"crop-{field_name}",
                source_value=value,
                confidence_score=95.0,
                evidence=("reviewed",),
            ),
        ),
        source_type=ConfirmedObservationSource.OCR_REVIEW,
        rationale="Reviewed.",
    )


def _proposal(
    target_field: str,
    operation: CollectionChangeOperation,
    *,
    target_record: CollectionRecordReference | None = None,
) -> CollectionFieldChangeProposal:
    value = _VALUES[target_field]
    if operation is CollectionChangeOperation.ADD:
        current_value: str | None = None
        proposed_value: str | None = value
    elif operation is CollectionChangeOperation.CLEAR:
        current_value = f"old-{value}"
        proposed_value = None
    elif operation is CollectionChangeOperation.NO_CHANGE:
        current_value = value
        proposed_value = value
    else:
        current_value = f"old-{value}"
        proposed_value = value
    approval, reason = _STRUCTURE[operation]
    result = CollectionFieldChangeProposal(
        schema_version=CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
        target_record=target_record or CollectionRecordReference("record-1"),
        target_field=target_field,
        current_value=current_value,
        proposed_value=proposed_value,
        operation=operation,
        approval_requirement=approval,
        source_observation=_observation(target_field, value),
        reason_code=reason,
        rationale="Reviewed.",
    )
    result.validate()
    return result


def _plan(
    *proposals: CollectionFieldChangeProposal,
    record_id: str = "record-1",
) -> CollectionChangePlan:
    result = CollectionChangePlan(
        schema_version=CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
        target_record=CollectionRecordReference(record_id),
        source_coin_id="source-1",
        proposals=tuple(sorted(proposals, key=lambda item: item.target_field)),
        review_session_id="review-1",
        source_fingerprint="fingerprint-1",
    )
    result.validate()
    return result


def _decision(
    plan: CollectionChangePlan,
    proposal: CollectionFieldChangeProposal,
    decision: CollectionChangeApprovalDecision,
) -> CollectionChangeProposalApproval:
    result = CollectionChangeProposalApproval(
        schema_version=CURRENT_COLLECTION_CHANGE_APPROVAL_SCHEMA_VERSION,
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


def _approval_compatibility(
    plan: CollectionChangePlan,
    decisions: dict[str, CollectionChangeApprovalDecision],
) -> CollectionChangePlanApprovalCompatibility:
    approval_decisions = tuple(
        _decision(plan, proposal, decisions[proposal.target_field])
        for proposal in plan.proposals
        if proposal.target_field in decisions
    )
    approval = CollectionChangePlanApproval(
        schema_version=CURRENT_COLLECTION_CHANGE_APPROVAL_SCHEMA_VERSION,
        target_record=plan.target_record,
        source_coin_id=plan.source_coin_id,
        review_session_id=plan.review_session_id,
        source_fingerprint=plan.source_fingerprint,
        plan_schema_version=plan.schema_version,
        decisions=approval_decisions,
    )
    approval.validate()
    return validate_collection_change_approval_compatibility(
        assess_collection_change_plan(plan),
        approval,
    )


def _freshness_field(
    proposal: CollectionFieldChangeProposal,
    status: CollectionFreshnessCompatibilityStatus,
) -> CollectionFreshnessFieldEvidence | None:
    if status is CollectionFreshnessCompatibilityStatus.MISSING:
        return None
    if status is CollectionFreshnessCompatibilityStatus.UNAVAILABLE:
        return CollectionFreshnessFieldEvidence(
            target_field=proposal.target_field,
            availability=CollectionFreshnessFieldAvailability.UNAVAILABLE,
            value=None,
        )
    if proposal.current_value is None:
        availability = (
            CollectionFreshnessFieldAvailability.ABSENT
            if status is CollectionFreshnessCompatibilityStatus.MATCHED
            else CollectionFreshnessFieldAvailability.PRESENT
        )
        value = None if availability is CollectionFreshnessFieldAvailability.ABSENT else "unexpected"
    else:
        availability = CollectionFreshnessFieldAvailability.PRESENT
        value = (
            proposal.current_value
            if status is CollectionFreshnessCompatibilityStatus.MATCHED
            else f"changed-{proposal.current_value}"
        )
    return CollectionFreshnessFieldEvidence(
        target_field=proposal.target_field,
        availability=availability,
        value=value,
    )


def _freshness_compatibility(
    plan: CollectionChangePlan,
    statuses: dict[str, CollectionFreshnessCompatibilityStatus],
) -> CollectionChangePlanFreshnessCompatibility:
    fields = tuple(
        field
        for proposal in plan.proposals
        if (
            field := _freshness_field(
                proposal,
                statuses.get(
                    proposal.target_field,
                    CollectionFreshnessCompatibilityStatus.MATCHED,
                ),
            )
        )
        is not None
    )
    evidence = CollectionRecordFreshnessEvidence(
        schema_version=CURRENT_COLLECTION_FRESHNESS_EVIDENCE_SCHEMA_VERSION,
        target_record=plan.target_record,
        fields=fields,
        observed_at=_TIME,
    )
    evidence.validate()
    return validate_collection_freshness_compatibility(plan, evidence)


def _diagnostics(
    operation: CollectionChangeOperation,
    decision: CollectionChangeApprovalDecision | None,
    freshness_status: CollectionFreshnessCompatibilityStatus,
) -> tuple[
    CollectionChangePlanApprovalCompatibility,
    CollectionChangePlanFreshnessCompatibility,
]:
    primary = _proposal("country", operation)
    proposals = [primary]
    decisions = {} if decision is None else {"country": decision}
    if (
        freshness_status is CollectionFreshnessCompatibilityStatus.MISSING
        or decision is None
    ):
        proposals.append(_proposal("year", CollectionChangeOperation.UPDATE))
        decisions["year"] = CollectionChangeApprovalDecision.APPROVE
    plan = _plan(*proposals)
    return (
        _approval_compatibility(plan, decisions),
        _freshness_compatibility(
            plan,
            {"country": freshness_status},
        ),
    )


def _compose_case(
    operation: CollectionChangeOperation,
    decision: CollectionChangeApprovalDecision | None,
    freshness_status: CollectionFreshnessCompatibilityStatus,
) -> CollectionMutationEligibilityFinding:
    approval, freshness = _diagnostics(
        operation,
        decision,
        freshness_status,
    )
    result = compose_collection_mutation_eligibility(
        approval,
        freshness,
    )
    return next(
        item for item in result.findings
        if item.proposal.target_field == "country"
    )


class VocabularyAndPolicyTests(unittest.TestCase):
    def test_status_vocabulary_is_exact(self) -> None:
        self.assertEqual(
            tuple(item.value for item in CollectionMutationEligibilityStatus),
            ("ELIGIBLE", "NO_CHANGE", "EXCLUDED", "BLOCKED", "UNRESOLVED"),
        )

    def test_reason_vocabulary_is_exact(self) -> None:
        self.assertEqual(
            tuple(item.value for item in CollectionMutationEligibilityReason),
            (
                "SAFE_NO_OP",
                "APPROVED_AND_FRESHNESS_MATCHED",
                "APPROVAL_REJECTED",
                "APPROVAL_DEFERRED",
                "APPROVAL_MISSING",
                "APPROVAL_INCOMPATIBLE",
                "POLICY_BLOCKED",
                "FRESHNESS_MISMATCHED",
                "FRESHNESS_UNAVAILABLE",
                "FRESHNESS_MISSING",
            ),
        )

    def test_approved_and_matched_is_eligible(self) -> None:
        finding = _compose_case(
            CollectionChangeOperation.UPDATE,
            CollectionChangeApprovalDecision.APPROVE,
            CollectionFreshnessCompatibilityStatus.MATCHED,
        )
        self.assertIs(finding.status, CollectionMutationEligibilityStatus.ELIGIBLE)
        self.assertIs(
            finding.reason,
            CollectionMutationEligibilityReason.APPROVED_AND_FRESHNESS_MATCHED,
        )

    def test_approved_freshness_failures_are_classified(self) -> None:
        cases = (
            (
                CollectionFreshnessCompatibilityStatus.MISMATCHED,
                CollectionMutationEligibilityStatus.EXCLUDED,
                CollectionMutationEligibilityReason.FRESHNESS_MISMATCHED,
            ),
            (
                CollectionFreshnessCompatibilityStatus.UNAVAILABLE,
                CollectionMutationEligibilityStatus.UNRESOLVED,
                CollectionMutationEligibilityReason.FRESHNESS_UNAVAILABLE,
            ),
            (
                CollectionFreshnessCompatibilityStatus.MISSING,
                CollectionMutationEligibilityStatus.UNRESOLVED,
                CollectionMutationEligibilityReason.FRESHNESS_MISSING,
            ),
        )
        for freshness, status, reason in cases:
            with self.subTest(freshness=freshness):
                finding = _compose_case(
                    CollectionChangeOperation.UPDATE,
                    CollectionChangeApprovalDecision.APPROVE,
                    freshness,
                )
                self.assertIs(finding.status, status)
                self.assertIs(finding.reason, reason)

    def test_rejection_outranks_every_freshness_status(self) -> None:
        for freshness in CollectionFreshnessCompatibilityStatus:
            with self.subTest(freshness=freshness):
                finding = _compose_case(
                    CollectionChangeOperation.UPDATE,
                    CollectionChangeApprovalDecision.REJECT,
                    freshness,
                )
                self.assertIs(
                    finding.status,
                    CollectionMutationEligibilityStatus.EXCLUDED,
                )
                self.assertIs(
                    finding.reason,
                    CollectionMutationEligibilityReason.APPROVAL_REJECTED,
                )

    def test_deferral_outranks_every_freshness_status(self) -> None:
        for freshness in CollectionFreshnessCompatibilityStatus:
            with self.subTest(freshness=freshness):
                finding = _compose_case(
                    CollectionChangeOperation.UPDATE,
                    CollectionChangeApprovalDecision.DEFER,
                    freshness,
                )
                self.assertIs(
                    finding.status,
                    CollectionMutationEligibilityStatus.UNRESOLVED,
                )
                self.assertIs(
                    finding.reason,
                    CollectionMutationEligibilityReason.APPROVAL_DEFERRED,
                )

    def test_missing_required_approval_is_distinct_and_precedes_freshness(self) -> None:
        for freshness in CollectionFreshnessCompatibilityStatus:
            with self.subTest(freshness=freshness):
                finding = _compose_case(
                    CollectionChangeOperation.UPDATE,
                    None,
                    freshness,
                )
                self.assertIs(
                    finding.status,
                    CollectionMutationEligibilityStatus.UNRESOLVED,
                )
                self.assertIs(
                    finding.reason,
                    CollectionMutationEligibilityReason.APPROVAL_MISSING,
                )

    def test_safe_no_op_requires_matching_freshness(self) -> None:
        cases = (
            (
                CollectionFreshnessCompatibilityStatus.MATCHED,
                CollectionMutationEligibilityStatus.NO_CHANGE,
                CollectionMutationEligibilityReason.SAFE_NO_OP,
            ),
            (
                CollectionFreshnessCompatibilityStatus.MISMATCHED,
                CollectionMutationEligibilityStatus.EXCLUDED,
                CollectionMutationEligibilityReason.FRESHNESS_MISMATCHED,
            ),
            (
                CollectionFreshnessCompatibilityStatus.UNAVAILABLE,
                CollectionMutationEligibilityStatus.UNRESOLVED,
                CollectionMutationEligibilityReason.FRESHNESS_UNAVAILABLE,
            ),
            (
                CollectionFreshnessCompatibilityStatus.MISSING,
                CollectionMutationEligibilityStatus.UNRESOLVED,
                CollectionMutationEligibilityReason.FRESHNESS_MISSING,
            ),
        )
        for freshness, status, reason in cases:
            with self.subTest(freshness=freshness):
                finding = _compose_case(
                    CollectionChangeOperation.NO_CHANGE,
                    None,
                    freshness,
                )
                self.assertIs(finding.status, status)
                self.assertIs(finding.reason, reason)

    def test_incompatible_safe_no_op_decision_outranks_freshness(self) -> None:
        for decision in CollectionChangeApprovalDecision:
            finding = _compose_case(
                CollectionChangeOperation.NO_CHANGE,
                decision,
                CollectionFreshnessCompatibilityStatus.MISMATCHED,
            )
            self.assertIs(
                finding.status,
                CollectionMutationEligibilityStatus.EXCLUDED,
            )
            self.assertIs(
                finding.reason,
                CollectionMutationEligibilityReason.APPROVAL_INCOMPATIBLE,
            )

    def test_policy_block_outranks_decision_and_freshness(self) -> None:
        for operation in (
            CollectionChangeOperation.CLEAR,
            CollectionChangeOperation.CONFLICT,
        ):
            for decision in (None, *tuple(CollectionChangeApprovalDecision)):
                for freshness in CollectionFreshnessCompatibilityStatus:
                    with self.subTest(
                        operation=operation,
                        decision=decision,
                        freshness=freshness,
                    ):
                        finding = _compose_case(
                            operation,
                            decision,
                            freshness,
                        )
                        self.assertIs(
                            finding.status,
                            CollectionMutationEligibilityStatus.BLOCKED,
                        )
                        self.assertIs(
                            finding.reason,
                            CollectionMutationEligibilityReason.POLICY_BLOCKED,
                        )


class AlignmentAndIdentityTests(unittest.TestCase):
    def test_exact_input_and_source_finding_identities_are_retained(self) -> None:
        approval, freshness = _diagnostics(
            CollectionChangeOperation.UPDATE,
            CollectionChangeApprovalDecision.APPROVE,
            CollectionFreshnessCompatibilityStatus.MATCHED,
        )
        result = compose_collection_mutation_eligibility(approval, freshness)
        self.assertIs(result.approval_compatibility, approval)
        self.assertIs(result.freshness_compatibility, freshness)
        self.assertIs(result.findings[0].approval_finding, approval.findings[0])
        self.assertIs(result.findings[0].freshness_finding, freshness.findings[0])
        self.assertIs(
            result.findings[0].proposal,
            approval.findings[0].policy_assessment.proposal,
        )

    def test_independently_reconstructed_equal_plans_compose(self) -> None:
        original = _plan(
            _proposal("country", CollectionChangeOperation.UPDATE),
        )
        reconstructed = CollectionChangePlan.from_dict(original.to_dict())
        self.assertEqual(original, reconstructed)
        self.assertIsNot(original, reconstructed)
        approval = _approval_compatibility(
            original,
            {"country": CollectionChangeApprovalDecision.APPROVE},
        )
        freshness = _freshness_compatibility(reconstructed, {})
        result = compose_collection_mutation_eligibility(approval, freshness)
        self.assertTrue(result.contains_eligible_items)

    def test_different_durable_plans_are_rejected(self) -> None:
        first = _plan(_proposal("country", CollectionChangeOperation.UPDATE))
        second_proposal = _proposal(
            "country",
            CollectionChangeOperation.UPDATE,
            target_record=CollectionRecordReference("record-2"),
        )
        second = _plan(second_proposal, record_id="record-2")
        approval = _approval_compatibility(
            first,
            {"country": CollectionChangeApprovalDecision.APPROVE},
        )
        freshness = _freshness_compatibility(second, {})
        with self.assertRaises(MismatchedCollectionMutationEligibilityPlanError):
            compose_collection_mutation_eligibility(approval, freshness)

    def test_wrong_input_types_raise_typed_context_error(self) -> None:
        approval, freshness = _diagnostics(
            CollectionChangeOperation.UPDATE,
            CollectionChangeApprovalDecision.APPROVE,
            CollectionFreshnessCompatibilityStatus.MATCHED,
        )
        for bad_approval, bad_freshness in (
            (object(), freshness),
            (approval, object()),
        ):
            with self.subTest():
                with self.assertRaises(
                    InvalidCollectionMutationEligibilityContextError
                ):
                    compose_collection_mutation_eligibility(
                        bad_approval,  # type: ignore[arg-type]
                        bad_freshness,  # type: ignore[arg-type]
                    )

    def test_misaligned_direct_finding_is_rejected(self) -> None:
        approval, _ = _diagnostics(
            CollectionChangeOperation.UPDATE,
            CollectionChangeApprovalDecision.APPROVE,
            CollectionFreshnessCompatibilityStatus.MATCHED,
        )
        other_plan = _plan(_proposal("year", CollectionChangeOperation.UPDATE))
        other_freshness = _freshness_compatibility(other_plan, {})
        finding = CollectionMutationEligibilityFinding(
            approval_finding=approval.findings[0],
            freshness_finding=other_freshness.findings[0],
            status=CollectionMutationEligibilityStatus.ELIGIBLE,
            reason=CollectionMutationEligibilityReason.APPROVED_AND_FRESHNESS_MATCHED,
        )
        with self.assertRaises(
            MisalignedCollectionMutationEligibilityFindingError
        ):
            finding.validate()


class ReconstructedContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.approval, self.freshness = _diagnostics(
            CollectionChangeOperation.UPDATE,
            CollectionChangeApprovalDecision.APPROVE,
            CollectionFreshnessCompatibilityStatus.MATCHED,
        )
        self.result = compose_collection_mutation_eligibility(
            self.approval,
            self.freshness,
        )

    def test_finding_rejects_wrong_nested_types_before_attribute_access(self) -> None:
        finding = replace(
            self.result.findings[0],
            approval_finding=object(),  # type: ignore[arg-type]
        )
        with self.assertRaises(
            InvalidCollectionMutationEligibilityContextError
        ):
            finding.validate()

    def test_finding_rejects_wrong_status_or_reason(self) -> None:
        cases = (
            {"status": CollectionMutationEligibilityStatus.EXCLUDED},
            {"reason": CollectionMutationEligibilityReason.APPROVAL_REJECTED},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                with self.assertRaises(
                    InvalidCollectionMutationEligibilityContextError
                ):
                    replace(self.result.findings[0], **changes).validate()

    def test_aggregate_rejects_missing_extra_or_reordered_findings(self) -> None:
        country = _proposal("country", CollectionChangeOperation.UPDATE)
        year = _proposal("year", CollectionChangeOperation.UPDATE)
        plan = _plan(country, year)
        approval = _approval_compatibility(
            plan,
            {
                "country": CollectionChangeApprovalDecision.APPROVE,
                "year": CollectionChangeApprovalDecision.APPROVE,
            },
        )
        freshness = _freshness_compatibility(plan, {})
        result = compose_collection_mutation_eligibility(approval, freshness)
        bad_findings = (
            result.findings[:-1],
            result.findings + (result.findings[0],),
            tuple(reversed(result.findings)),
        )
        for findings in bad_findings:
            with self.subTest(length=len(findings)):
                with self.assertRaises(
                    InvalidCollectionMutationEligibilityContextError
                ):
                    replace(result, findings=findings).validate()

    def test_aggregate_rejects_reconstructed_source_finding(self) -> None:
        copied = replace(self.result.findings[0].approval_finding)
        changed = replace(
            self.result.findings[0],
            approval_finding=copied,
        )
        with self.assertRaises(
            InvalidCollectionMutationEligibilityContextError
        ):
            replace(self.result, findings=(changed,)).validate()

    def test_aggregate_rejects_contradictory_summary(self) -> None:
        cases = (
            (
                CollectionChangeOperation.UPDATE,
                CollectionChangeApprovalDecision.APPROVE,
                "contains_eligible_items",
            ),
            (
                CollectionChangeOperation.NO_CHANGE,
                None,
                "contains_no_change_items",
            ),
            (
                CollectionChangeOperation.UPDATE,
                CollectionChangeApprovalDecision.REJECT,
                "contains_excluded_items",
            ),
            (
                CollectionChangeOperation.CONFLICT,
                None,
                "contains_blocked_items",
            ),
            (
                CollectionChangeOperation.UPDATE,
                CollectionChangeApprovalDecision.DEFER,
                "contains_unresolved_items",
            ),
        )
        for operation, decision, summary in cases:
            with self.subTest(summary=summary):
                approval, freshness = _diagnostics(
                    operation,
                    decision,
                    CollectionFreshnessCompatibilityStatus.MATCHED,
                )
                result = compose_collection_mutation_eligibility(
                    approval,
                    freshness,
                )
                with self.assertRaises(
                    InvalidCollectionMutationEligibilityContextError
                ):
                    replace(result, **{summary: False}).validate()

    def test_non_boolean_summary_is_rejected(self) -> None:
        with self.assertRaises(
            InvalidCollectionMutationEligibilityContextError
        ):
            replace(
                self.result,
                contains_eligible_items=1,  # type: ignore[arg-type]
            ).validate()


class SummaryTests(unittest.TestCase):
    def test_mixed_result_derives_all_present_categories(self) -> None:
        proposals = (
            _proposal("country", CollectionChangeOperation.UPDATE),
            _proposal("denomination", CollectionChangeOperation.NO_CHANGE),
            _proposal("year", CollectionChangeOperation.UPDATE),
        )
        plan = _plan(*proposals)
        approval = _approval_compatibility(
            plan,
            {
                "country": CollectionChangeApprovalDecision.APPROVE,
                "year": CollectionChangeApprovalDecision.REJECT,
            },
        )
        freshness = _freshness_compatibility(plan, {})
        result = compose_collection_mutation_eligibility(approval, freshness)
        self.assertTrue(result.contains_eligible_items)
        self.assertTrue(result.contains_no_change_items)
        self.assertTrue(result.contains_excluded_items)
        self.assertFalse(result.contains_blocked_items)
        self.assertFalse(result.contains_unresolved_items)

    def test_each_negative_summary_is_derived_from_findings(self) -> None:
        cases = (
            (
                CollectionChangeOperation.UPDATE,
                CollectionChangeApprovalDecision.REJECT,
                "contains_excluded_items",
            ),
            (
                CollectionChangeOperation.CONFLICT,
                None,
                "contains_blocked_items",
            ),
            (
                CollectionChangeOperation.UPDATE,
                CollectionChangeApprovalDecision.DEFER,
                "contains_unresolved_items",
            ),
        )
        for operation, decision, summary in cases:
            with self.subTest(summary=summary):
                approval, freshness = _diagnostics(
                    operation,
                    decision,
                    CollectionFreshnessCompatibilityStatus.MATCHED,
                )
                result = compose_collection_mutation_eligibility(
                    approval,
                    freshness,
                )
                self.assertTrue(getattr(result, summary))

class ImmutabilityDeterminismAndArchitectureTests(unittest.TestCase):
    def test_contracts_are_frozen_slotted_and_source_inputs_unchanged(self) -> None:
        approval, freshness = _diagnostics(
            CollectionChangeOperation.UPDATE,
            CollectionChangeApprovalDecision.APPROVE,
            CollectionFreshnessCompatibilityStatus.MATCHED,
        )
        approval_before = approval
        freshness_before = freshness
        result = compose_collection_mutation_eligibility(approval, freshness)
        with self.assertRaises(FrozenInstanceError):
            result.contains_eligible_items = False  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            result.findings[0].status = (  # type: ignore[misc]
                CollectionMutationEligibilityStatus.EXCLUDED
            )
        self.assertEqual(approval, approval_before)
        self.assertEqual(freshness, freshness_before)
        self.assertFalse(hasattr(result, "__dict__"))
        self.assertFalse(hasattr(result.findings[0], "__dict__"))

    def test_composition_is_equal_and_idempotently_recomputable(self) -> None:
        approval, freshness = _diagnostics(
            CollectionChangeOperation.UPDATE,
            CollectionChangeApprovalDecision.APPROVE,
            CollectionFreshnessCompatibilityStatus.MATCHED,
        )
        first = CollectionMutationEligibilityComposer().compose(
            approval,
            freshness,
        )
        second = CollectionMutationEligibilityComposer().compose(
            approval,
            freshness,
        )
        self.assertEqual(first, second)
        self.assertIsNot(first, second)

    def test_composer_does_not_call_upstream_public_validator_functions(self) -> None:
        approval, freshness = _diagnostics(
            CollectionChangeOperation.UPDATE,
            CollectionChangeApprovalDecision.APPROVE,
            CollectionFreshnessCompatibilityStatus.MATCHED,
        )
        with (
            patch(
                "collection_management.workflow_collection_change_approval_compatibility."
                "validate_collection_change_approval_compatibility",
                side_effect=AssertionError("must not recompute approval"),
            ),
            patch(
                "collection_management.workflow_collection_freshness_compatibility."
                "validate_collection_freshness_compatibility",
                side_effect=AssertionError("must not recompute freshness"),
            ),
        ):
            result = compose_collection_mutation_eligibility(
                approval,
                freshness,
            )
        self.assertTrue(result.contains_eligible_items)

    def test_public_api_is_exact(self) -> None:
        expected = {
            "CollectionMutationEligibilityError",
            "InvalidCollectionMutationEligibilityContextError",
            "MismatchedCollectionMutationEligibilityPlanError",
            "MisalignedCollectionMutationEligibilityFindingError",
            "CollectionMutationEligibilityStatus",
            "CollectionMutationEligibilityReason",
            "CollectionMutationEligibilityFinding",
            "CollectionChangePlanMutationEligibility",
            "CollectionMutationEligibilityComposer",
            "compose_collection_mutation_eligibility",
        }
        defined = {
            name
            for name, value in vars(eligibility_module).items()
            if not name.startswith("_")
            and getattr(value, "__module__", None) == _MODULE
        }
        self.assertEqual(defined, expected)

    def test_import_boundary_has_no_forbidden_dependencies(self) -> None:
        source = inspect.getsource(eligibility_module)
        tree = ast.parse(source)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        forbidden = (
            "repository",
            "persistence",
            "desktop",
            "tkinter",
            "sqlite",
            "filesystem",
            "uuid",
            "random",
            "datetime",
            "os",
        )
        for name in imports:
            self.assertFalse(any(token in name for token in forbidden), name)

    def test_result_has_no_serialization_command_or_authorization_api(self) -> None:
        approval, freshness = _diagnostics(
            CollectionChangeOperation.UPDATE,
            CollectionChangeApprovalDecision.APPROVE,
            CollectionFreshnessCompatibilityStatus.MATCHED,
        )
        result = compose_collection_mutation_eligibility(approval, freshness)
        for value in (result, result.findings[0]):
            for name in (
                "to_dict",
                "from_dict",
                "schema_version",
                "command",
                "authorized",
                "executable",
                "apply",
                "execute",
            ):
                self.assertFalse(hasattr(value, name), name)

    def test_error_hierarchy_is_reachable(self) -> None:
        self.assertTrue(
            issubclass(
                InvalidCollectionMutationEligibilityContextError,
                CollectionMutationEligibilityError,
            )
        )
        self.assertTrue(
            issubclass(
                MismatchedCollectionMutationEligibilityPlanError,
                CollectionMutationEligibilityError,
            )
        )
        self.assertTrue(
            issubclass(
                MisalignedCollectionMutationEligibilityFindingError,
                CollectionMutationEligibilityError,
            )
        )
if __name__ == "__main__":
    unittest.main()
