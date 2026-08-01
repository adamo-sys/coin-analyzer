"""Tests for immutable collection mutation command construction."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import inspect
import unittest
from unittest.mock import patch

from tests.frozen_dataclass_compat import (
    assert_frozen_slotted_assignment_rejected,
)

from capture_import.workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedFieldObservation,
    ConfirmedObservationProvenance,
    ConfirmedObservationSource,
)
from collection_management.workflow_collection_change_approval_compatibility import (
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
    validate_collection_freshness_compatibility,
)
from collection_management.workflow_collection_freshness_evidence_models import (
    CURRENT_COLLECTION_FRESHNESS_EVIDENCE_SCHEMA_VERSION,
    CollectionFreshnessFieldAvailability,
    CollectionFreshnessFieldEvidence,
    CollectionRecordFreshnessEvidence,
)
from collection_management.workflow_collection_mutation_command import (
    CollectionMutationCommand,
    CollectionMutationCommandBuilder,
    CollectionMutationCommandError,
    CollectionMutationCommandItem,
    InvalidCollectionMutationCommandContextError,
    InvalidCollectionMutationCommandItemError,
    NonConstructibleCollectionMutationCommandError,
    build_collection_mutation_command,
)
import collection_management.workflow_collection_mutation_command as command_module
from collection_management.workflow_collection_mutation_eligibility import (
    CollectionMutationEligibilityStatus,
    compose_collection_mutation_eligibility,
)


_MODULE = "collection_management.workflow_collection_mutation_command"
_TIME = "2026-07-29T02:00:00Z"
_DEFAULT_VALUES = {
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
_UNSET = object()


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
    proposed_value: str | None | object = _UNSET,
    current_value: str | None | object = _UNSET,
) -> CollectionFieldChangeProposal:
    value = (
        _DEFAULT_VALUES[target_field]
        if proposed_value is _UNSET
        else proposed_value
    )
    if operation is CollectionChangeOperation.CLEAR:
        desired: str | None = None
        source_value = _DEFAULT_VALUES[target_field]
    else:
        desired = value  # type: ignore[assignment]
        source_value = desired
    if current_value is _UNSET:
        if operation is CollectionChangeOperation.ADD:
            current: str | None = None
        elif operation is CollectionChangeOperation.NO_CHANGE:
            current = desired
        else:
            current = f"old-{target_field}"
    else:
        current = current_value  # type: ignore[assignment]
    approval, reason = _STRUCTURE[operation]
    result = CollectionFieldChangeProposal(
        schema_version=CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
        target_record=CollectionRecordReference("record-1"),
        target_field=target_field,
        current_value=current,
        proposed_value=desired,
        operation=operation,
        approval_requirement=approval,
        source_observation=_observation(target_field, source_value),
        reason_code=reason,
        rationale="Reviewed.",
    )
    result.validate()
    return result


def _plan(*proposals: CollectionFieldChangeProposal) -> CollectionChangePlan:
    result = CollectionChangePlan(
        schema_version=CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
        target_record=CollectionRecordReference("record-1"),
        source_coin_id="source-1",
        proposals=tuple(sorted(proposals, key=lambda item: item.target_field)),
        review_session_id="review-1",
        source_fingerprint="fingerprint-1",
    )
    result.validate()
    return result


def _approval(
    plan: CollectionChangePlan,
    decisions: dict[str, CollectionChangeApprovalDecision],
) -> CollectionChangePlanApproval:
    items = tuple(
        CollectionChangeProposalApproval(
            schema_version=CURRENT_COLLECTION_CHANGE_APPROVAL_SCHEMA_VERSION,
            proposal_reference=create_collection_change_proposal_reference(
                plan,
                proposal,
            ),
            decision=decisions[proposal.target_field],
            approver_id="approver-1",
            decided_at=_TIME,
            rationale=None,
        )
        for proposal in plan.proposals
        if proposal.target_field in decisions
    )
    result = CollectionChangePlanApproval(
        schema_version=CURRENT_COLLECTION_CHANGE_APPROVAL_SCHEMA_VERSION,
        target_record=plan.target_record,
        source_coin_id=plan.source_coin_id,
        review_session_id=plan.review_session_id,
        source_fingerprint=plan.source_fingerprint,
        plan_schema_version=plan.schema_version,
        decisions=items,
    )
    result.validate()
    return result


def _freshness_field(
    proposal: CollectionFieldChangeProposal,
    status: str,
) -> CollectionFreshnessFieldEvidence | None:
    if status == "missing":
        return None
    if status == "unavailable":
        return CollectionFreshnessFieldEvidence(
            target_field=proposal.target_field,
            availability=CollectionFreshnessFieldAvailability.UNAVAILABLE,
            value=None,
        )
    if proposal.current_value is None:
        availability = (
            CollectionFreshnessFieldAvailability.ABSENT
            if status == "matched"
            else CollectionFreshnessFieldAvailability.PRESENT
        )
        value = None if status == "matched" else "unexpected"
    else:
        availability = CollectionFreshnessFieldAvailability.PRESENT
        value = (
            proposal.current_value
            if status == "matched"
            else f"changed-{proposal.current_value}"
        )
    return CollectionFreshnessFieldEvidence(
        target_field=proposal.target_field,
        availability=availability,
        value=value,
    )


def _eligibility(
    proposals: tuple[CollectionFieldChangeProposal, ...],
    decisions: dict[str, CollectionChangeApprovalDecision],
    *,
    freshness: dict[str, str] | None = None,
):
    plan = _plan(*proposals)
    approval = validate_collection_change_approval_compatibility(
        assess_collection_change_plan(plan),
        _approval(plan, decisions),
    )
    statuses = freshness or {}
    fields = tuple(
        field
        for proposal in plan.proposals
        if (
            field := _freshness_field(
                proposal,
                statuses.get(proposal.target_field, "matched"),
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
    freshness_result = validate_collection_freshness_compatibility(
        plan,
        evidence,
    )
    return compose_collection_mutation_eligibility(
        approval,
        freshness_result,
    )


def _eligible_update(
    *,
    proposed_value: str = "Canada",
    current_value: str = "old-country",
):
    proposal = _proposal(
        "country",
        CollectionChangeOperation.UPDATE,
        proposed_value=proposed_value,
        current_value=current_value,
    )
    return _eligibility(
        (proposal,),
        {"country": CollectionChangeApprovalDecision.APPROVE},
    )


class PublicApiAndInputTests(unittest.TestCase):
    def test_public_api_is_exact(self) -> None:
        expected = {
            "CollectionMutationCommandError",
            "InvalidCollectionMutationCommandContextError",
            "NonConstructibleCollectionMutationCommandError",
            "InvalidCollectionMutationCommandItemError",
            "CollectionMutationCommandItem",
            "CollectionMutationCommand",
            "CollectionMutationCommandBuilder",
            "build_collection_mutation_command",
        }
        actual = {
            name
            for name, value in vars(command_module).items()
            if not name.startswith("_")
            and getattr(value, "__module__", None) == _MODULE
        }
        self.assertEqual(actual, expected)

    def test_error_hierarchy_is_exact(self) -> None:
        for error in (
            InvalidCollectionMutationCommandContextError,
            NonConstructibleCollectionMutationCommandError,
            InvalidCollectionMutationCommandItemError,
        ):
            self.assertTrue(issubclass(error, CollectionMutationCommandError))

    def test_wrong_input_types_and_raw_contracts_are_rejected(self) -> None:
        proposal = _proposal("country", CollectionChangeOperation.UPDATE)
        raw_plan = _plan(proposal)
        for value in (object(), raw_plan, (proposal,)):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(
                    InvalidCollectionMutationCommandContextError
                ):
                    build_collection_mutation_command(value)  # type: ignore[arg-type]

    def test_malformed_eligibility_is_wrapped_as_command_context(self) -> None:
        eligibility = _eligible_update()
        malformed = replace(eligibility, findings=())
        with self.assertRaises(InvalidCollectionMutationCommandContextError):
            build_collection_mutation_command(malformed)


class SuccessfulConstructionTests(unittest.TestCase):
    def test_add_exposes_expected_absence_and_exact_desired_value(self) -> None:
        add = _proposal("country", CollectionChangeOperation.ADD)
        eligibility = _eligibility(
            (add,),
            {"country": CollectionChangeApprovalDecision.APPROVE},
        )
        command = build_collection_mutation_command(eligibility)
        item = command.items[0]
        self.assertIs(item.operation, CollectionChangeOperation.ADD)
        self.assertIsNone(item.expected_current_value)
        self.assertEqual(item.desired_value, "Canada")

    def test_update_exposes_exact_expected_and_desired_values(self) -> None:
        eligibility = _eligible_update()
        item = build_collection_mutation_command(eligibility).items[0]
        self.assertIs(item.operation, CollectionChangeOperation.UPDATE)
        self.assertEqual(item.expected_current_value, "old-country")
        self.assertEqual(item.desired_value, "Canada")

    def test_mixed_no_change_and_eligible_omits_only_no_change(self) -> None:
        proposals = (
            _proposal("country", CollectionChangeOperation.UPDATE),
            _proposal("denomination", CollectionChangeOperation.NO_CHANGE),
            _proposal("year", CollectionChangeOperation.ADD),
        )
        eligibility = _eligibility(
            proposals,
            {
                "country": CollectionChangeApprovalDecision.APPROVE,
                "year": CollectionChangeApprovalDecision.APPROVE,
            },
        )
        command = build_collection_mutation_command(eligibility)
        self.assertEqual(command.target_fields, ("country", "year"))
        self.assertEqual(
            tuple(item.operation for item in command.items),
            (CollectionChangeOperation.UPDATE, CollectionChangeOperation.ADD),
        )

    def test_plan_order_restricted_to_eligible_findings_is_preserved(self) -> None:
        eligibility = _eligibility(
            (
                _proposal("country", CollectionChangeOperation.ADD),
                _proposal("denomination", CollectionChangeOperation.NO_CHANGE),
                _proposal("year", CollectionChangeOperation.UPDATE),
            ),
            {
                "country": CollectionChangeApprovalDecision.APPROVE,
                "year": CollectionChangeApprovalDecision.APPROVE,
            },
        )
        command = build_collection_mutation_command(eligibility)
        expected = tuple(
            finding
            for finding in eligibility.findings
            if finding.status is CollectionMutationEligibilityStatus.ELIGIBLE
        )
        self.assertEqual(command.target_fields, ("country", "year"))
        self.assertEqual(
            tuple(item.eligibility_finding for item in command.items),
            expected,
        )

    def test_exact_source_identities_and_linkage_are_retained(self) -> None:
        eligibility = _eligible_update()
        command = build_collection_mutation_command(eligibility)
        self.assertIs(command.eligibility, eligibility)
        self.assertIs(command.items[0].eligibility_finding, eligibility.findings[0])
        self.assertIs(command.items[0].proposal, eligibility.findings[0].proposal)
        self.assertIs(
            command.plan,
            eligibility.approval_compatibility.policy_assessment.plan,
        )
        self.assertIs(command.target_record, command.plan.target_record)

    def test_exact_strings_are_not_normalized_or_collapsed(self) -> None:
        cases = (
            ("Canada", ""),
            (" Canada ", " canada "),
            ("001967", "1967"),
            ("Écu", "ECU"),
        )
        for desired, current in cases:
            with self.subTest(desired=desired, current=current):
                item = build_collection_mutation_command(
                    _eligible_update(
                        proposed_value=desired,
                        current_value=current,
                    )
                ).items[0]
                self.assertEqual(item.expected_current_value, current)
                self.assertEqual(item.desired_value, desired)

    def test_clear_and_conflict_remain_blocked_by_current_unit_1e(self) -> None:
        for operation in (
            CollectionChangeOperation.CLEAR,
            CollectionChangeOperation.CONFLICT,
        ):
            proposal = _proposal("country", operation)
            eligibility = _eligibility(
                (proposal,),
                {"country": CollectionChangeApprovalDecision.REJECT},
            )
            with self.assertRaises(
                NonConstructibleCollectionMutationCommandError
            ) as raised:
                build_collection_mutation_command(eligibility)
            self.assertEqual(raised.exception.blocked_fields, ("country",))

    def test_structural_clear_state_is_exact_but_not_currently_constructible(
        self,
    ) -> None:
        clear = _proposal("country", CollectionChangeOperation.CLEAR)
        eligibility = _eligibility(
            (clear,),
            {"country": CollectionChangeApprovalDecision.REJECT},
        )
        item = CollectionMutationCommandItem(eligibility.findings[0])
        self.assertIs(item.operation, CollectionChangeOperation.CLEAR)
        self.assertEqual(item.expected_current_value, "old-country")
        self.assertIsNone(item.desired_value)
        with self.assertRaises(InvalidCollectionMutationCommandItemError):
            item.validate()


class StatusGatingTests(unittest.TestCase):
    def _assert_nonconstructible(
        self,
        decision: CollectionChangeApprovalDecision,
        *,
        freshness: str = "matched",
    ) -> NonConstructibleCollectionMutationCommandError:
        proposal = _proposal("country", CollectionChangeOperation.UPDATE)
        eligibility = _eligibility(
            (proposal,),
            {"country": decision},
            freshness={"country": freshness},
        )
        with self.assertRaises(
            NonConstructibleCollectionMutationCommandError
        ) as raised:
            build_collection_mutation_command(eligibility)
        return raised.exception

    def test_excluded_rejects_entire_command(self) -> None:
        error = self._assert_nonconstructible(
            CollectionChangeApprovalDecision.REJECT
        )
        self.assertEqual(error.excluded_fields, ("country",))
        self.assertTrue(error.no_eligible_items)

    def test_unresolved_rejects_entire_command(self) -> None:
        error = self._assert_nonconstructible(
            CollectionChangeApprovalDecision.DEFER
        )
        self.assertEqual(error.unresolved_fields, ("country",))

    def test_mismatched_or_unavailable_freshness_rejects(self) -> None:
        cases = (
            ("mismatched", "excluded_fields"),
            ("unavailable", "unresolved_fields"),
        )
        for freshness, attribute in cases:
            with self.subTest(freshness=freshness):
                error = self._assert_nonconstructible(
                    CollectionChangeApprovalDecision.APPROVE,
                    freshness=freshness,
                )
                self.assertEqual(getattr(error, attribute), ("country",))

    def test_missing_freshness_rejects_without_partial_command(self) -> None:
        proposals = (
            _proposal("country", CollectionChangeOperation.UPDATE),
            _proposal("year", CollectionChangeOperation.UPDATE),
        )
        eligibility = _eligibility(
            proposals,
            {
                "country": CollectionChangeApprovalDecision.APPROVE,
                "year": CollectionChangeApprovalDecision.APPROVE,
            },
            freshness={"year": "missing"},
        )
        with self.assertRaises(
            NonConstructibleCollectionMutationCommandError
        ) as raised:
            build_collection_mutation_command(eligibility)
        self.assertEqual(raised.exception.unresolved_fields, ("year",))
        self.assertFalse(raised.exception.no_eligible_items)

    def test_mixed_eligible_and_each_prohibited_status_fails_atomically(self) -> None:
        cases = (
            (
                CollectionChangeOperation.UPDATE,
                CollectionChangeApprovalDecision.REJECT,
                "excluded_fields",
            ),
            (
                CollectionChangeOperation.CONFLICT,
                CollectionChangeApprovalDecision.REJECT,
                "blocked_fields",
            ),
            (
                CollectionChangeOperation.UPDATE,
                CollectionChangeApprovalDecision.DEFER,
                "unresolved_fields",
            ),
        )
        for operation, decision, attribute in cases:
            with self.subTest(attribute=attribute):
                eligibility = _eligibility(
                    (
                        _proposal("country", CollectionChangeOperation.UPDATE),
                        _proposal("year", operation),
                    ),
                    {
                        "country": CollectionChangeApprovalDecision.APPROVE,
                        "year": decision,
                    },
                )
                with self.assertRaises(
                    NonConstructibleCollectionMutationCommandError
                ) as raised:
                    build_collection_mutation_command(eligibility)
                self.assertEqual(getattr(raised.exception, attribute), ("year",))

    def test_error_groups_preserve_plan_order_and_categories(self) -> None:
        eligibility = _eligibility(
            (
                _proposal("country", CollectionChangeOperation.UPDATE),
                _proposal("denomination", CollectionChangeOperation.CONFLICT),
                _proposal("year", CollectionChangeOperation.UPDATE),
            ),
            {
                "country": CollectionChangeApprovalDecision.REJECT,
                "denomination": CollectionChangeApprovalDecision.REJECT,
                "year": CollectionChangeApprovalDecision.DEFER,
            },
        )
        with self.assertRaises(
            NonConstructibleCollectionMutationCommandError
        ) as raised:
            build_collection_mutation_command(eligibility)
        self.assertEqual(raised.exception.excluded_fields, ("country",))
        self.assertEqual(raised.exception.blocked_fields, ("denomination",))
        self.assertEqual(raised.exception.unresolved_fields, ("year",))
        self.assertTrue(raised.exception.no_eligible_items)


class ReconstructionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.eligibility = _eligible_update()
        self.command = build_collection_mutation_command(self.eligibility)

    def test_item_rejects_wrong_type_before_attribute_access(self) -> None:
        item = CollectionMutationCommandItem(
            eligibility_finding=object(),  # type: ignore[arg-type]
        )
        with self.assertRaises(InvalidCollectionMutationCommandItemError):
            item.validate()

    def test_command_rejects_wrong_aggregate_and_item_container_types(self) -> None:
        cases = (
            replace(
                self.command,
                eligibility=object(),  # type: ignore[arg-type]
            ),
            replace(
                self.command,
                items=list(self.command.items),  # type: ignore[arg-type]
            ),
            replace(
                self.command,
                items=(object(),),  # type: ignore[arg-type]
            ),
        )
        for command in cases:
            with self.subTest(
                eligibility_type=type(command.eligibility).__name__,
                items_type=type(command.items).__name__,
            ):
                with self.assertRaises(
                    InvalidCollectionMutationCommandContextError
                ):
                    command.validate()

    def test_item_rejects_every_noneligible_status(self) -> None:
        cases = (
            (
                _proposal("country", CollectionChangeOperation.UPDATE),
                CollectionChangeApprovalDecision.REJECT,
            ),
            (
                _proposal("country", CollectionChangeOperation.CONFLICT),
                CollectionChangeApprovalDecision.REJECT,
            ),
            (
                _proposal("country", CollectionChangeOperation.UPDATE),
                CollectionChangeApprovalDecision.DEFER,
            ),
            (
                _proposal("country", CollectionChangeOperation.NO_CHANGE),
                None,
            ),
        )
        for proposal, decision in cases:
            decisions = (
                {"country": decision}
                if decision is not None
                else {
                    "year": CollectionChangeApprovalDecision.APPROVE,
                }
            )
            proposals = (
                (proposal,)
                if decision is not None
                else (
                    proposal,
                    _proposal("year", CollectionChangeOperation.UPDATE),
                )
            )
            eligibility = _eligibility(proposals, decisions)
            finding = next(
                item for item in eligibility.findings
                if item.proposal.target_field == "country"
            )
            with self.assertRaises(InvalidCollectionMutationCommandItemError):
                CollectionMutationCommandItem(finding).validate()

    def test_empty_missing_extra_duplicate_and_reordered_items_fail(self) -> None:
        two = _eligibility(
            (
                _proposal("country", CollectionChangeOperation.UPDATE),
                _proposal("year", CollectionChangeOperation.UPDATE),
            ),
            {
                "country": CollectionChangeApprovalDecision.APPROVE,
                "year": CollectionChangeApprovalDecision.APPROVE,
            },
        )
        command = build_collection_mutation_command(two)
        bad_items = (
            (),
            command.items[:-1],
            command.items + (command.items[-1],),
            (command.items[0], command.items[0]),
            tuple(reversed(command.items)),
        )
        for items in bad_items:
            with self.subTest(length=len(items)):
                with self.assertRaises(
                    InvalidCollectionMutationCommandContextError
                ):
                    replace(command, items=items).validate()

    def test_item_from_equal_but_distinct_aggregate_fails_identity(self) -> None:
        other = build_collection_mutation_command(_eligible_update())
        reconstructed = replace(
            self.command,
            items=(other.items[0],),
        )
        self.assertEqual(
            other.items[0].eligibility_finding,
            self.command.items[0].eligibility_finding,
        )
        self.assertIsNot(
            other.items[0].eligibility_finding,
            self.command.items[0].eligibility_finding,
        )
        with self.assertRaises(InvalidCollectionMutationCommandContextError):
            reconstructed.validate()

    def test_no_change_item_is_never_accepted_as_an_extra(self) -> None:
        no_change = _proposal(
            "denomination",
            CollectionChangeOperation.NO_CHANGE,
        )
        eligibility = _eligibility(
            (
                _proposal("country", CollectionChangeOperation.UPDATE),
                no_change,
            ),
            {"country": CollectionChangeApprovalDecision.APPROVE},
        )
        command = build_collection_mutation_command(eligibility)
        no_change_finding = next(
            item for item in eligibility.findings
            if item.status is CollectionMutationEligibilityStatus.NO_CHANGE
        )
        extra = CollectionMutationCommandItem(no_change_finding)
        with self.assertRaises(InvalidCollectionMutationCommandContextError):
            replace(command, items=command.items + (extra,)).validate()

    def test_malformed_final_item_returns_no_partial_command(self) -> None:
        malformed = replace(
            self.command.items[0],
            eligibility_finding=object(),  # type: ignore[arg-type]
        )
        with self.assertRaises(InvalidCollectionMutationCommandItemError):
            malformed.validate()


class ImmutabilityDeterminismAndArchitectureTests(unittest.TestCase):
    def test_contracts_are_frozen_slotted_and_properties_are_read_only(self) -> None:
        command = build_collection_mutation_command(_eligible_update())
        item = command.items[0]
        with self.assertRaises(FrozenInstanceError):
            command.items = ()  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            item.eligibility_finding = object()  # type: ignore[misc]
        with assert_frozen_slotted_assignment_rejected(self, item):
            item.desired_value = "changed"  # type: ignore[misc]
        self.assertFalse(hasattr(command, "__dict__"))
        self.assertFalse(hasattr(item, "__dict__"))

    def test_repeated_builds_are_equal_and_retain_source_identity(self) -> None:
        eligibility = _eligible_update()
        first = CollectionMutationCommandBuilder().build(eligibility)
        second = CollectionMutationCommandBuilder().build(eligibility)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first.items[0], second.items[0])
        self.assertIs(
            first.items[0].eligibility_finding,
            second.items[0].eligibility_finding,
        )

    def test_builder_does_not_call_upstream_workflow_functions(self) -> None:
        eligibility = _eligible_update()
        targets = (
            "collection_management.workflow_collection_mutation_eligibility."
            "compose_collection_mutation_eligibility",
            "collection_management.workflow_collection_change_approval_compatibility."
            "validate_collection_change_approval_compatibility",
            "collection_management.workflow_collection_freshness_compatibility."
            "validate_collection_freshness_compatibility",
        )
        patches = [
            patch(target, side_effect=AssertionError("must not recompute"))
            for target in targets
        ]
        with patches[0], patches[1], patches[2]:
            command = build_collection_mutation_command(eligibility)
        self.assertEqual(command.target_fields, ("country",))

    def test_import_boundary_has_no_forbidden_dependencies(self) -> None:
        tree = ast.parse(inspect.getsource(command_module))
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
            "environment",
            "network",
            "uuid",
            "datetime",
            "random",
        )
        for name in imports:
            self.assertFalse(any(token in name for token in forbidden), name)

    def test_contracts_are_transient_and_have_no_execution_surface(self) -> None:
        command = build_collection_mutation_command(_eligible_update())
        for value in (command, command.items[0]):
            for name in (
                "to_dict",
                "from_dict",
                "schema_version",
                "authorized",
                "executable",
                "apply",
                "execute",
                "mutate",
                "persist",
                "save",
            ):
                self.assertFalse(hasattr(value, name), name)

    def test_operation_vocabulary_is_exhaustively_guarded(self) -> None:
        self.assertEqual(
            tuple(CollectionChangeOperation),
            (
                CollectionChangeOperation.ADD,
                CollectionChangeOperation.UPDATE,
                CollectionChangeOperation.CLEAR,
                CollectionChangeOperation.NO_CHANGE,
                CollectionChangeOperation.CONFLICT,
            ),
        )
        self.assertEqual(
            command_module._MUTATING_OPERATIONS,
            frozenset(
                {
                    CollectionChangeOperation.ADD,
                    CollectionChangeOperation.UPDATE,
                    CollectionChangeOperation.CLEAR,
                }
            ),
        )


if __name__ == "__main__":
    unittest.main()
