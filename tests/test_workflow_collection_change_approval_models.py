"""Tests for durable, non-authorizing collection-change approval evidence."""

from __future__ import annotations

import ast
from dataclasses import replace
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
    ConfirmedObservationSource,
)
from collection_management.workflow_collection_change_approval_models import (
    CURRENT_COLLECTION_CHANGE_APPROVAL_SCHEMA_VERSION,
    CollectionChangeApprovalDecision,
    CollectionChangeApprovalError,
    CollectionChangePlanApproval,
    CollectionChangeProposalApproval,
    CollectionChangeProposalReference,
    DuplicateCollectionChangeApprovalDecisionError,
    InvalidCollectionChangeApprovalContextError,
    InvalidCollectionChangeApprovalTimestampError,
    MismatchedCollectionChangeApprovalLinkageError,
    UnsupportedCollectionChangeApprovalSchemaVersion,
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


_MODULE = (
    "collection_management.workflow_collection_change_approval_models"
)
_DECIDED_AT = "2026-07-28T16:05:04.123456Z"
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
    target_field: str = "country",
    operation: CollectionChangeOperation = CollectionChangeOperation.UPDATE,
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
        rationale="Human reviewed.",
    )
    result.validate()
    return result


def _plan(
    *proposals: CollectionFieldChangeProposal,
    review_session_id: str | None = "review-session-1",
    source_fingerprint: str | None = "source-fingerprint-1",
) -> CollectionChangePlan:
    selected = proposals or (_proposal(),)
    result = CollectionChangePlan(
        schema_version=CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
        target_record=CollectionRecordReference("record-1"),
        source_coin_id="source-coin-1",
        proposals=tuple(
            sorted(selected, key=lambda item: item.target_field)
        ),
        review_session_id=review_session_id,
        source_fingerprint=source_fingerprint,
    )
    result.validate()
    return result


def _reference(
    plan: CollectionChangePlan | None = None,
    proposal: CollectionFieldChangeProposal | None = None,
) -> CollectionChangeProposalReference:
    selected_plan = plan or _plan()
    selected_proposal = proposal or selected_plan.proposals[0]
    return create_collection_change_proposal_reference(
        selected_plan,
        selected_proposal,
    )


def _decision(
    reference: CollectionChangeProposalReference | None = None,
    *,
    decision: CollectionChangeApprovalDecision = (
        CollectionChangeApprovalDecision.APPROVE
    ),
    approver_id: str = "approver-1",
    decided_at: str = _DECIDED_AT,
    rationale: str | None = None,
) -> CollectionChangeProposalApproval:
    result = CollectionChangeProposalApproval(
        schema_version=(
            CURRENT_COLLECTION_CHANGE_APPROVAL_SCHEMA_VERSION
        ),
        proposal_reference=reference or _reference(),
        decision=decision,
        approver_id=approver_id,
        decided_at=decided_at,
        rationale=rationale,
    )
    result.validate()
    return result


def _approval(
    plan: CollectionChangePlan | None = None,
    decisions: tuple[CollectionChangeProposalApproval, ...] | None = None,
) -> CollectionChangePlanApproval:
    selected_plan = plan or _plan()
    selected_decisions = decisions or (
        _decision(_reference(selected_plan, selected_plan.proposals[0])),
    )
    result = CollectionChangePlanApproval(
        schema_version=(
            CURRENT_COLLECTION_CHANGE_APPROVAL_SCHEMA_VERSION
        ),
        target_record=selected_plan.target_record,
        source_coin_id=selected_plan.source_coin_id,
        review_session_id=selected_plan.review_session_id,
        source_fingerprint=selected_plan.source_fingerprint,
        plan_schema_version=selected_plan.schema_version,
        decisions=selected_decisions,
    )
    result.validate()
    return result


class SchemaAndVocabularyTests(unittest.TestCase):
    def test_current_schema_version_is_explicit(self) -> None:
        self.assertEqual(
            CURRENT_COLLECTION_CHANGE_APPROVAL_SCHEMA_VERSION,
            "1",
        )

    def test_decision_vocabulary_is_exact(self) -> None:
        self.assertEqual(
            tuple(item.value for item in CollectionChangeApprovalDecision),
            ("APPROVE", "REJECT", "DEFER"),
        )

    def test_decision_vocabulary_has_no_execution_or_policy_state(
        self,
    ) -> None:
        forbidden = {
            "AUTO_APPROVE",
            "EXECUTE",
            "AUTHORIZE",
            "APPLY",
            "APPLIED",
            "READY",
            "SAFE",
            "BLOCK",
            "CONFLICT_RESOLVED",
            "SKIP",
        }
        self.assertTrue(
            forbidden.isdisjoint(CollectionChangeApprovalDecision.__members__)
        )

    def test_wrong_approval_schema_is_typed(self) -> None:
        for value in ("0", "2"):
            with self.subTest(value=value):
                with self.assertRaises(
                    UnsupportedCollectionChangeApprovalSchemaVersion
                ):
                    replace(_decision(), schema_version=value).validate()

    def test_non_string_approval_schema_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            replace(_decision(), schema_version=1).validate()  # type: ignore[arg-type]


class ProposalReferenceTests(unittest.TestCase):
    def test_factory_preserves_exact_plan_and_proposal_linkage(self) -> None:
        plan = _plan()
        proposal = plan.proposals[0]
        result = _reference(plan, proposal)
        self.assertIs(result.target_record, plan.target_record)
        self.assertEqual(result.target_field, proposal.target_field)
        self.assertEqual(result.source_coin_id, plan.source_coin_id)
        self.assertEqual(result.review_session_id, plan.review_session_id)
        self.assertEqual(
            result.source_fingerprint,
            plan.source_fingerprint,
        )
        self.assertEqual(result.plan_schema_version, plan.schema_version)
        self.assertEqual(
            result.proposal_schema_version,
            proposal.schema_version,
        )
        self.assertIs(result.operation, proposal.operation)
        self.assertEqual(result.current_value, proposal.current_value)
        self.assertEqual(result.proposed_value, proposal.proposed_value)
        self.assertEqual(
            result.source_field_name,
            proposal.source_observation.field_name,
        )
        self.assertNotEqual(
            result.target_record.record_id,
            result.source_coin_id,
        )

    def test_factory_rejects_equivalent_but_nonmember_proposal(self) -> None:
        plan = _plan()
        outsider = replace(plan.proposals[0])
        self.assertEqual(outsider, plan.proposals[0])
        with self.assertRaises(
            MismatchedCollectionChangeApprovalLinkageError
        ):
            _reference(plan, outsider)

    def test_factory_rejects_proposal_from_different_plan(self) -> None:
        plan = _plan()
        other = _plan(_proposal("year"))
        with self.assertRaises(
            MismatchedCollectionChangeApprovalLinkageError
        ):
            _reference(plan, other.proposals[0])

    def test_factory_argument_types_are_strict(self) -> None:
        plan = _plan()
        with self.assertRaises(TypeError):
            create_collection_change_proposal_reference(
                object(),  # type: ignore[arg-type]
                plan.proposals[0],
            )
        with self.assertRaises(TypeError):
            create_collection_change_proposal_reference(
                plan,
                object(),  # type: ignore[arg-type]
            )

    def test_none_plan_linkage_is_preserved(self) -> None:
        plan = _plan(review_session_id=None, source_fingerprint=None)
        result = _reference(plan, plan.proposals[0])
        self.assertIsNone(result.review_session_id)
        self.assertIsNone(result.source_fingerprint)
        self.assertIsNone(
            CollectionChangeProposalReference.from_dict(
                result.to_dict()
            ).review_session_id
        )

    def test_reference_rejects_noncurrent_plan_schema(self) -> None:
        with self.assertRaises(
            InvalidCollectionChangeApprovalContextError
        ):
            replace(_reference(), plan_schema_version="2").validate()
        with self.assertRaises(
            InvalidCollectionChangeApprovalContextError
        ):
            replace(_reference(), proposal_schema_version="2").validate()

    def test_reference_round_trip_is_exact_and_json_safe(self) -> None:
        reference = _reference()
        payload = reference.to_dict()
        self.assertEqual(
            tuple(payload),
            (
                "target_record",
                "target_field",
                "source_coin_id",
                "review_session_id",
                "source_fingerprint",
                "plan_schema_version",
                "proposal_schema_version",
                "operation",
                "current_value",
                "proposed_value",
                "source_field_name",
            ),
        )
        self.assertEqual(
            CollectionChangeProposalReference.from_dict(payload),
            reference,
        )
        json.dumps(payload)

    def test_reference_wire_shape_is_closed(self) -> None:
        payload = _reference().to_dict()
        for mutation in (
            {**payload, "extra": "forbidden"},
            {key: value for key, value in payload.items() if key != "operation"},
        ):
            with self.subTest(fields=tuple(mutation)):
                with self.assertRaises(ValueError):
                    CollectionChangeProposalReference.from_dict(mutation)

    def test_reference_rejects_invalid_operation_on_wire(self) -> None:
        payload = _reference().to_dict()
        payload["operation"] = "FUTURE"
        with self.assertRaises(ValueError):
            CollectionChangeProposalReference.from_dict(payload)

    def test_exact_current_value_forms_are_preserved(self) -> None:
        for current in ("", "  OLD value  ", "001", "Écu — 25¢"):
            with self.subTest(current=current):
                proposal = replace(_proposal(), current_value=current)
                proposal.validate()
                plan = _plan(proposal)
                reference = _reference(plan, plan.proposals[0])
                self.assertEqual(reference.current_value, current)
                self.assertEqual(
                    CollectionChangeProposalReference.from_dict(
                        reference.to_dict()
                    ).current_value,
                    current,
                )


class ProposalApprovalTests(unittest.TestCase):
    def test_all_decisions_are_structurally_valid(self) -> None:
        for value in CollectionChangeApprovalDecision:
            with self.subTest(decision=value):
                result = _decision(
                    decision=value,
                    rationale="Exact rationale.",
                )
                self.assertIs(result.decision, value)
                self.assertEqual(result.approver_id, "approver-1")
                self.assertEqual(result.decided_at, _DECIDED_AT)
                self.assertEqual(result.rationale, "Exact rationale.")

    def test_approver_is_required_exact_and_not_inferred(self) -> None:
        for value in ("", "   "):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    replace(_decision(), approver_id=value).validate()
        exact = "Approver CASE  "
        self.assertEqual(
            _decision(approver_id=exact).approver_id,
            exact,
        )
        self.assertNotEqual(
            _decision().approver_id,
            _proposal().source_observation.reviewer_id,
        )

    def test_timestamp_is_required_strict_utc_and_exact(self) -> None:
        self.assertEqual(_decision().decided_at, _DECIDED_AT)
        invalid = (
            "",
            "2026-07-28",
            "2026-07-28T16:05:04",
            "2026-07-28T16:05:04+00:00",
            "2026-07-28T12:05:04-04:00",
            "2026-02-30T16:05:04Z",
            "2026-07-28T16:05:04z",
            "2026-07-28T16:05:60Z",
            "2026-07-28T16:05:04Z ",
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(
                    InvalidCollectionChangeApprovalTimestampError
                ):
                    replace(_decision(), decided_at=value).validate()

    def test_timestamp_accepts_whole_and_fractional_utc_seconds(
        self,
    ) -> None:
        accepted = (
            "2026-07-28T16:05:04Z",
            "2026-07-28T16:05:04.1Z",
            "2026-07-28T16:05:04.123456Z",
        )
        for value in accepted:
            with self.subTest(value=value):
                result = _decision(decided_at=value)
                self.assertEqual(result.decided_at, value)
                self.assertEqual(
                    CollectionChangeProposalApproval.from_dict(
                        result.to_dict()
                    ).decided_at,
                    value,
                )

    def test_timestamp_type_is_strict(self) -> None:
        with self.assertRaises(TypeError):
            replace(_decision(), decided_at=None).validate()  # type: ignore[arg-type]

    def test_rationale_is_optional_exact_and_nonblank(self) -> None:
        self.assertIsNone(_decision().rationale)
        exact = "  Human reason.  "
        self.assertEqual(_decision(rationale=exact).rationale, exact)
        for value in ("", "  "):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    replace(_decision(), rationale=value).validate()
        unicode_rationale = "  Décision explicite — conservée.  "
        self.assertEqual(
            _decision(rationale=unicode_rationale).rationale,
            unicode_rationale,
        )
        with self.assertRaises(ValueError):
            replace(_decision(), rationale="\t\n").validate()

    def test_decision_round_trip_is_exact_and_deterministic(self) -> None:
        decision = _decision(
            decision=CollectionChangeApprovalDecision.REJECT,
            rationale="Rejected explicitly.",
        )
        first = decision.to_dict()
        second = decision.to_dict()
        self.assertEqual(
            tuple(first),
            (
                "schema_version",
                "proposal_reference",
                "decision",
                "approver_id",
                "decided_at",
                "rationale",
            ),
        )
        self.assertEqual(first, second)
        self.assertEqual(
            CollectionChangeProposalApproval.from_dict(first),
            decision,
        )
        self.assertEqual(
            json.dumps(first, sort_keys=True),
            json.dumps(second, sort_keys=True),
        )

    def test_decision_wire_shape_and_enum_are_strict(self) -> None:
        payload = _decision().to_dict()
        with self.assertRaises(ValueError):
            CollectionChangeProposalApproval.from_dict(
                {**payload, "extra": True}
            )
        missing = dict(payload)
        del missing["schema_version"]
        with self.assertRaises(ValueError):
            CollectionChangeProposalApproval.from_dict(missing)
        invalid = dict(payload)
        invalid["decision"] = "EXECUTE"
        with self.assertRaises(ValueError):
            CollectionChangeProposalApproval.from_dict(invalid)


class PlanApprovalTests(unittest.TestCase):
    def test_one_decision_and_partial_subset_are_valid(self) -> None:
        plan = _plan(_proposal("country"), _proposal("year"))
        one = _decision(_reference(plan, plan.proposals[0]))
        result = _approval(plan, (one,))
        self.assertEqual(result.decisions, (one,))
        self.assertEqual(len(result.decisions), 1)
        self.assertEqual(len(plan.proposals), 2)

    def test_multiple_decisions_require_target_order(self) -> None:
        plan = _plan(
            _proposal("year"),
            _proposal("country"),
            _proposal("denomination"),
        )
        decisions = tuple(
            _decision(
                _reference(plan, proposal),
                decision=CollectionChangeApprovalDecision.DEFER,
            )
            for proposal in plan.proposals
        )
        result = _approval(plan, decisions)
        self.assertEqual(
            tuple(
                item.proposal_reference.target_field
                for item in result.decisions
            ),
            ("country", "denomination", "year"),
        )
        with self.assertRaises(
            InvalidCollectionChangeApprovalContextError
        ):
            replace(result, decisions=tuple(reversed(decisions))).validate()

    def test_duplicate_target_reference_is_rejected(self) -> None:
        decision = _decision()
        duplicate = replace(
            decision,
            decided_at="2026-07-28T16:06:00Z",
        )
        with self.assertRaises(
            DuplicateCollectionChangeApprovalDecisionError
        ):
            replace(
                _approval(),
                decisions=(decision, duplicate),
            ).validate()

    def test_mixed_plan_linkage_is_rejected(self) -> None:
        baseline = _approval()
        reference = baseline.decisions[0].proposal_reference
        fields = (
            ("target_record", CollectionRecordReference("record-2")),
            ("source_coin_id", "source-coin-2"),
            ("review_session_id", "review-session-2"),
            ("source_fingerprint", "source-fingerprint-2"),
        )
        for field_name, value in fields:
            with self.subTest(field=field_name):
                foreign = _decision(
                    replace(reference, **{field_name: value})
                )
                with self.assertRaises(
                    MismatchedCollectionChangeApprovalLinkageError
                ):
                    replace(baseline, decisions=(foreign,)).validate()

    def test_mixed_approvers_are_rejected(self) -> None:
        plan = _plan(_proposal("country"), _proposal("year"))
        decisions = tuple(
            _decision(
                _reference(plan, proposal),
                approver_id=f"approver-{index}",
            )
            for index, proposal in enumerate(plan.proposals, start=1)
        )
        with self.assertRaises(
            MismatchedCollectionChangeApprovalLinkageError
        ):
            _approval(plan, decisions)

    def test_empty_or_mutable_decisions_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            replace(_approval(), decisions=()).validate()
        with self.assertRaises(TypeError):
            replace(_approval(), decisions=[]).validate()  # type: ignore[arg-type]

    def test_malformed_nested_reference_fails_before_ordering(self) -> None:
        malformed = replace(
            _decision(),
            proposal_reference=object(),  # type: ignore[arg-type]
        )
        with self.assertRaisesRegex(TypeError, "proposal_reference"):
            replace(_approval(), decisions=(malformed,)).validate()

    def test_plan_approval_round_trip_is_exact_and_json_safe(self) -> None:
        plan = _plan(_proposal("country"), _proposal("year"))
        decisions = tuple(
            _decision(
                _reference(plan, proposal),
                decision=CollectionChangeApprovalDecision.REJECT,
                rationale=f"Decision for {proposal.target_field}.",
            )
            for proposal in plan.proposals
        )
        approval = _approval(plan, decisions)
        payload = approval.to_dict()
        self.assertEqual(
            CollectionChangePlanApproval.from_dict(payload),
            approval,
        )
        json.dumps(payload)

    def test_plan_wire_shape_and_decision_list_are_strict(self) -> None:
        payload = _approval().to_dict()
        with self.assertRaises(ValueError):
            CollectionChangePlanApproval.from_dict(
                {**payload, "approved": True}
            )
        missing = dict(payload)
        del missing["source_coin_id"]
        with self.assertRaises(ValueError):
            CollectionChangePlanApproval.from_dict(missing)
        wrong = dict(payload)
        wrong["decisions"] = tuple(payload["decisions"])
        with self.assertRaises(TypeError):
            CollectionChangePlanApproval.from_dict(wrong)

    def test_serialized_order_is_stable(self) -> None:
        approval = _approval()
        self.assertEqual(approval.to_dict(), approval.to_dict())
        self.assertEqual(
            list(approval.to_dict()),
            [
                "schema_version",
                "target_record",
                "source_coin_id",
                "review_session_id",
                "source_fingerprint",
                "plan_schema_version",
                "decisions",
            ],
        )


class OperationNeutralityTests(unittest.TestCase):
    def test_every_plan_operation_can_be_referenced_and_decided(self) -> None:
        for operation in CollectionChangeOperation:
            with self.subTest(operation=operation):
                plan = _plan(_proposal("country", operation))
                reference = _reference(plan, plan.proposals[0])
                approval = _approval(
                    plan,
                    (
                        _decision(
                            reference,
                            decision=(
                                CollectionChangeApprovalDecision.APPROVE
                            ),
                        ),
                    ),
                )
                self.assertIs(reference.operation, operation)
                self.assertEqual(
                    reference.current_value,
                    plan.proposals[0].current_value,
                )
                self.assertEqual(
                    reference.proposed_value,
                    plan.proposals[0].proposed_value,
                )
                self.assertIs(
                    approval.decisions[0].decision,
                    CollectionChangeApprovalDecision.APPROVE,
                )

    def test_blocked_operation_intent_has_no_authority_field(self) -> None:
        plan = _plan(
            _proposal("country", CollectionChangeOperation.CLEAR)
        )
        result = _approval(
            plan,
            (
                _decision(
                    _reference(plan, plan.proposals[0]),
                    decision=CollectionChangeApprovalDecision.APPROVE,
                ),
            ),
        )
        fields = set(result.__dataclass_fields__)
        self.assertTrue(
            {
                "authorized",
                "executable",
                "policy_compatible",
                "approved_plan",
            }.isdisjoint(fields)
        )


class ImmutabilityAndAtomicityTests(unittest.TestCase):
    def test_contracts_are_frozen_and_slotted(self) -> None:
        values = (_reference(), _decision(), _approval())
        for value in values:
            with self.subTest(contract=type(value).__name__):
                self.assertFalse(hasattr(value, "__dict__"))
                with assert_frozen_slotted_assignment_rejected(self, value):
                    value.extra = True  # type: ignore[attr-defined]

    def test_source_plan_and_proposal_remain_unchanged(self) -> None:
        plan = _plan()
        proposal = plan.proposals[0]
        before = repr(plan)
        _reference(plan, proposal)
        self.assertEqual(repr(plan), before)
        self.assertIs(plan.proposals[0], proposal)

    def test_repeated_construction_and_serialization_are_equivalent(
        self,
    ) -> None:
        plan = _plan()
        first = _approval(
            plan,
            (_decision(_reference(plan, plan.proposals[0])),),
        )
        second = _approval(
            plan,
            (_decision(_reference(plan, plan.proposals[0])),),
        )
        self.assertEqual(first, second)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_invalid_final_decision_returns_no_repaired_record(self) -> None:
        plan = _plan(_proposal("country"), _proposal("year"))
        valid = _decision(_reference(plan, plan.proposals[0]))
        invalid = replace(
            _decision(_reference(plan, plan.proposals[1])),
            approver_id="other-approver",
        )
        original = (valid, invalid)
        with self.assertRaises(
            MismatchedCollectionChangeApprovalLinkageError
        ):
            _approval(plan, original)
        self.assertEqual(original, (valid, invalid))


class ErrorAndArchitectureTests(unittest.TestCase):
    def test_error_hierarchy_is_narrow_and_reachable(self) -> None:
        errors = (
            UnsupportedCollectionChangeApprovalSchemaVersion,
            InvalidCollectionChangeApprovalContextError,
            DuplicateCollectionChangeApprovalDecisionError,
            MismatchedCollectionChangeApprovalLinkageError,
            InvalidCollectionChangeApprovalTimestampError,
        )
        for error_type in errors:
            with self.subTest(error=error_type.__name__):
                self.assertTrue(
                    issubclass(error_type, CollectionChangeApprovalError)
                )

    def test_import_boundary_is_narrow(self) -> None:
        module = importlib.import_module(_MODULE)
        tree = ast.parse(inspect.getsource(module))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        forbidden = (
            "workflow_collection_change_policy",
            "workflow_collection_change_plan_builder",
            "workflow_collection_change_proposal_builder",
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
        )
        for fragment in forbidden:
            with self.subTest(fragment=fragment):
                self.assertFalse(
                    any(fragment in item.casefold() for item in imported),
                    imported,
                )
        self.assertNotIn("os", imported)

    def test_module_has_no_clock_policy_or_mutation_surface(self) -> None:
        source = inspect.getsource(importlib.import_module(_MODULE))
        for fragment in (
            "datetime.now",
            "uuid4",
            "getenv",
            "open(",
            "save(",
            "execute(",
            "apply(",
            "approve_all",
            "reject_all",
            "policy_status",
            "stale",
            "repository",
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
        public.add("CURRENT_COLLECTION_CHANGE_APPROVAL_SCHEMA_VERSION")
        self.assertEqual(
            public,
            {
                "CURRENT_COLLECTION_CHANGE_APPROVAL_SCHEMA_VERSION",
                "CollectionChangeApprovalError",
                "UnsupportedCollectionChangeApprovalSchemaVersion",
                "InvalidCollectionChangeApprovalContextError",
                "DuplicateCollectionChangeApprovalDecisionError",
                "MismatchedCollectionChangeApprovalLinkageError",
                "InvalidCollectionChangeApprovalTimestampError",
                "CollectionChangeApprovalDecision",
                "CollectionChangeProposalReference",
                "CollectionChangeProposalApproval",
                "CollectionChangePlanApproval",
                "create_collection_change_proposal_reference",
            },
        )


if __name__ == "__main__":
    unittest.main()
