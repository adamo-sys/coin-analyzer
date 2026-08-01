"""Tests for immutable collection change-proposal construction."""

from __future__ import annotations

import ast
from dataclasses import replace
import importlib
import inspect
from types import MappingProxyType
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
from collection_management.workflow_collection_change_plan_models import (
    CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
    CollectionChangeApprovalRequirement,
    CollectionChangeOperation,
    CollectionChangeReasonCode,
    CollectionFieldChangeProposal,
    CollectionRecordReference,
)
import collection_management.workflow_collection_change_proposal_builder as builder_module
from collection_management.workflow_collection_change_proposal_builder import (
    CollectionChangeProposalBuildError,
    CollectionChangeProposalBuilder,
    CollectionChangeProposalBuildResult,
    DuplicateCollectionChangeProposalFieldError,
    InvalidCollectionChangeProposalContextError,
    UnavailableCollectionProposalSourceError,
    UnsupportedCollectionComparisonOutcomeError,
    build_collection_change_proposals,
)
from collection_management.workflow_collection_record_comparison import (
    CollectionFieldComparisonOutcome,
    CollectionRecordComparisonResult,
    CollectionRecordComparisonService,
    CollectionRecordFieldAvailability,
    CollectionRecordFieldSnapshot,
    CollectionRecordSnapshot,
)
from collection_management.workflow_confirmed_collection_field_mapper import (
    CollectionTargetField,
    ConfirmedCollectionFieldMapping,
    ConfirmedCollectionFieldMappingResult,
)


_MODULE = (
    "collection_management.workflow_collection_change_proposal_builder"
)
_VALUES = {
    CollectionTargetField.COUNTRY: "Canada",
    CollectionTargetField.DENOMINATION: "25 cents",
    CollectionTargetField.YEAR: "1967",
}


def _observation(
    target: CollectionTargetField,
    value: str | None = None,
    *,
    source_coin_id: str = "source-coin-1",
    reviewer_id: str = "collector-1",
) -> ConfirmedFieldObservation:
    submitted = _VALUES[target] if value is None else value
    return ConfirmedFieldObservation(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id=source_coin_id,
        field_name=target.value,
        submitted_value=submitted,
        canonical_value=None,
        reviewer_id=reviewer_id,
        provenance=(
            ConfirmedObservationProvenance(
                provider_id="test-ocr",
                image_role="front",
                artifact_key=f"crop-{target.value}",
                source_value=submitted,
                confidence_score=94.0,
                evidence=("collector confirmed",),
            ),
        ),
        source_type=ConfirmedObservationSource.OCR_REVIEW,
        rationale="Confirmed by collector.",
    )


def _mapping(
    target: CollectionTargetField,
    value: str | None = None,
) -> ConfirmedCollectionFieldMapping:
    observation = _observation(target, value)
    mapping = ConfirmedCollectionFieldMapping(
        source_observation=observation,
        target_field=target,
        mapped_value=observation.submitted_value,
    )
    mapping.validate()
    return mapping


def _mapping_result(
    *targets: CollectionTargetField,
) -> ConfirmedCollectionFieldMappingResult:
    selected = targets or (CollectionTargetField.COUNTRY,)
    mappings = tuple(
        sorted(
            (_mapping(target) for target in selected),
            key=lambda item: item.target_field.value,
        )
    )
    result = ConfirmedCollectionFieldMappingResult(
        source_coin_id="source-coin-1",
        reviewer_id="collector-1",
        mappings=mappings,
        review_session_id="review-session-1",
        source_fingerprint="opaque-source-fingerprint",
    )
    result.validate()
    return result


def _field_for_outcome(
    target: CollectionTargetField,
    outcome: CollectionFieldComparisonOutcome,
) -> CollectionRecordFieldSnapshot:
    if outcome is CollectionFieldComparisonOutcome.ABSENT:
        return CollectionRecordFieldSnapshot(
            target,
            CollectionRecordFieldAvailability.ABSENT,
            None,
        )
    if outcome is CollectionFieldComparisonOutcome.UNAVAILABLE:
        return CollectionRecordFieldSnapshot(
            target,
            CollectionRecordFieldAvailability.UNAVAILABLE,
            None,
        )
    if outcome is CollectionFieldComparisonOutcome.EMPTY:
        current = ""
    elif outcome is CollectionFieldComparisonOutcome.EXACT_MATCH:
        current = _VALUES[target]
    elif outcome is CollectionFieldComparisonOutcome.DIFFERENT:
        current = f"different-{target.value}"
    else:
        raise AssertionError(f"Unhandled test outcome: {outcome!r}")
    return CollectionRecordFieldSnapshot(
        target,
        CollectionRecordFieldAvailability.PRESENT,
        current,
    )


def _comparison_result(
    *items: tuple[
        CollectionTargetField,
        CollectionFieldComparisonOutcome,
    ],
    record_id: str = "record-1",
) -> CollectionRecordComparisonResult:
    selected = items or (
        (
            CollectionTargetField.COUNTRY,
            CollectionFieldComparisonOutcome.EXACT_MATCH,
        ),
    )
    mapping_result = _mapping_result(*(target for target, _ in selected))
    snapshot = CollectionRecordSnapshot(
        target_record=CollectionRecordReference(record_id),
        fields=tuple(
            sorted(
                (
                    _field_for_outcome(target, outcome)
                    for target, outcome in selected
                ),
                key=lambda item: item.target_field.value,
            )
        ),
    )
    return CollectionRecordComparisonService().compare(
        mapping_result,
        snapshot,
    )


class PolicyTableTests(unittest.TestCase):
    def test_policy_table_is_exact_and_immutable(self) -> None:
        self.assertIsInstance(
            builder_module._OUTCOME_POLICY,
            MappingProxyType,
        )
        self.assertEqual(
            builder_module._OUTCOME_POLICY,
            {
                CollectionFieldComparisonOutcome.ABSENT: (
                    CollectionChangeOperation.ADD,
                    CollectionChangeApprovalRequirement.REQUIRED,
                    CollectionChangeReasonCode.NEW_VALUE,
                ),
                CollectionFieldComparisonOutcome.EMPTY: (
                    CollectionChangeOperation.UPDATE,
                    CollectionChangeApprovalRequirement.REQUIRED,
                    CollectionChangeReasonCode.DIFFERENT_VALUE,
                ),
                CollectionFieldComparisonOutcome.EXACT_MATCH: (
                    CollectionChangeOperation.NO_CHANGE,
                    CollectionChangeApprovalRequirement.NOT_REQUIRED,
                    CollectionChangeReasonCode.EQUIVALENT_VALUE,
                ),
                CollectionFieldComparisonOutcome.DIFFERENT: (
                    CollectionChangeOperation.UPDATE,
                    CollectionChangeApprovalRequirement.REQUIRED,
                    CollectionChangeReasonCode.DIFFERENT_VALUE,
                ),
            },
        )
        with self.assertRaises(TypeError):
            builder_module._OUTCOME_POLICY[
                CollectionFieldComparisonOutcome.UNAVAILABLE
            ] = (  # type: ignore[index]
                CollectionChangeOperation.CONFLICT,
                CollectionChangeApprovalRequirement.REQUIRED,
                CollectionChangeReasonCode.EXISTING_VALUE_CONFLICT,
            )

    def test_every_current_outcome_has_explicit_policy_or_error(self) -> None:
        covered = set(builder_module._OUTCOME_POLICY) | {
            CollectionFieldComparisonOutcome.UNAVAILABLE
        }
        self.assertEqual(
            covered,
            set(CollectionFieldComparisonOutcome),
        )

    def test_clear_and_conflict_are_not_emitted_policies(self) -> None:
        operations = {
            policy[0] for policy in builder_module._OUTCOME_POLICY.values()
        }
        self.assertNotIn(CollectionChangeOperation.CLEAR, operations)
        self.assertNotIn(CollectionChangeOperation.CONFLICT, operations)


class OutcomeProposalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = CollectionChangeProposalBuilder()

    def _proposal(
        self,
        outcome: CollectionFieldComparisonOutcome,
    ) -> CollectionFieldChangeProposal:
        result = self.builder.build(
            _comparison_result(
                (CollectionTargetField.COUNTRY, outcome)
            )
        )
        return result.proposals[0]

    def test_absent_produces_add(self) -> None:
        proposal = self._proposal(CollectionFieldComparisonOutcome.ABSENT)
        self.assertIs(proposal.operation, CollectionChangeOperation.ADD)
        self.assertIsNone(proposal.current_value)
        self.assertEqual(proposal.proposed_value, "Canada")
        self.assertIs(
            proposal.approval_requirement,
            CollectionChangeApprovalRequirement.REQUIRED,
        )
        self.assertIs(
            proposal.reason_code,
            CollectionChangeReasonCode.NEW_VALUE,
        )

    def test_empty_produces_update_without_none_coercion(self) -> None:
        proposal = self._proposal(CollectionFieldComparisonOutcome.EMPTY)
        self.assertIs(proposal.operation, CollectionChangeOperation.UPDATE)
        self.assertEqual(proposal.current_value, "")
        self.assertEqual(proposal.proposed_value, "Canada")
        self.assertIs(
            proposal.approval_requirement,
            CollectionChangeApprovalRequirement.REQUIRED,
        )
        self.assertIs(
            proposal.reason_code,
            CollectionChangeReasonCode.DIFFERENT_VALUE,
        )

    def test_exact_match_produces_no_change(self) -> None:
        proposal = self._proposal(
            CollectionFieldComparisonOutcome.EXACT_MATCH
        )
        self.assertIs(
            proposal.operation,
            CollectionChangeOperation.NO_CHANGE,
        )
        self.assertEqual(proposal.current_value, "Canada")
        self.assertEqual(proposal.proposed_value, "Canada")
        self.assertIs(
            proposal.approval_requirement,
            CollectionChangeApprovalRequirement.NOT_REQUIRED,
        )
        self.assertIs(
            proposal.reason_code,
            CollectionChangeReasonCode.EQUIVALENT_VALUE,
        )

    def test_different_produces_update_not_conflict(self) -> None:
        proposal = self._proposal(
            CollectionFieldComparisonOutcome.DIFFERENT
        )
        self.assertIs(proposal.operation, CollectionChangeOperation.UPDATE)
        self.assertEqual(proposal.current_value, "different-country")
        self.assertEqual(proposal.proposed_value, "Canada")
        self.assertIs(
            proposal.approval_requirement,
            CollectionChangeApprovalRequirement.REQUIRED,
        )
        self.assertIs(
            proposal.reason_code,
            CollectionChangeReasonCode.DIFFERENT_VALUE,
        )

    def test_unavailable_fails_without_inventing_current_value(self) -> None:
        comparison = _comparison_result(
            (
                CollectionTargetField.COUNTRY,
                CollectionFieldComparisonOutcome.UNAVAILABLE,
            )
        )
        with self.assertRaises(
            UnavailableCollectionProposalSourceError
        ) as captured:
            self.builder.build(comparison)
        self.assertEqual(captured.exception.target_field, "country")

    def test_unit_1a_schema_version_is_used(self) -> None:
        proposal = self._proposal(
            CollectionFieldComparisonOutcome.EXACT_MATCH
        )
        self.assertEqual(
            proposal.schema_version,
            CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
        )
        proposal.validate()

    def test_source_rationale_is_preserved_not_generated(self) -> None:
        proposal = self._proposal(
            CollectionFieldComparisonOutcome.DIFFERENT
        )
        self.assertEqual(proposal.rationale, "Confirmed by collector.")

    def test_future_unmapped_policy_fails_closed(self) -> None:
        comparison_result = _comparison_result(
            (
                CollectionTargetField.COUNTRY,
                CollectionFieldComparisonOutcome.DIFFERENT,
            )
        )
        empty_policy: MappingProxyType[
            CollectionFieldComparisonOutcome,
            tuple[
                CollectionChangeOperation,
                CollectionChangeApprovalRequirement,
                CollectionChangeReasonCode,
            ],
        ] = MappingProxyType({})
        with patch.object(
            builder_module,
            "_OUTCOME_POLICY",
            empty_policy,
        ):
            with self.assertRaises(
                UnsupportedCollectionComparisonOutcomeError
            ):
                self.builder.build(comparison_result)


class ExactValueAndTraceabilityTests(unittest.TestCase):
    def test_case_whitespace_punctuation_and_unicode_are_preserved(
        self,
    ) -> None:
        target = CollectionTargetField.COUNTRY
        observation = _observation(target, "  Caf\u00e9!  ")
        mapping = ConfirmedCollectionFieldMapping(
            source_observation=observation,
            target_field=target,
            mapped_value="  Caf\u00e9!  ",
        )
        mapping_result = ConfirmedCollectionFieldMappingResult(
            source_coin_id="source-coin-1",
            reviewer_id="collector-1",
            mappings=(mapping,),
            review_session_id="review-session-1",
            source_fingerprint="opaque-source-fingerprint",
        )
        snapshot = CollectionRecordSnapshot(
            target_record=CollectionRecordReference("record-1"),
            fields=(
                CollectionRecordFieldSnapshot(
                    target,
                    CollectionRecordFieldAvailability.PRESENT,
                    "  CAF\u00c9?  ",
                ),
            ),
        )
        comparison = CollectionRecordComparisonService().compare(
            mapping_result,
            snapshot,
        )
        proposal = CollectionChangeProposalBuilder().build(
            comparison
        ).proposals[0]
        self.assertEqual(proposal.current_value, "  CAF\u00c9?  ")
        self.assertEqual(proposal.proposed_value, "  Caf\u00e9!  ")

    def test_unit_1a_non_nfc_error_propagates_without_normalization(
        self,
    ) -> None:
        target = CollectionTargetField.COUNTRY
        mapping_result = _mapping_result(target)
        snapshot = CollectionRecordSnapshot(
            target_record=CollectionRecordReference("record-1"),
            fields=(
                CollectionRecordFieldSnapshot(
                    target,
                    CollectionRecordFieldAvailability.PRESENT,
                    "Cafe\u0301",
                ),
            ),
        )
        comparison = CollectionRecordComparisonService().compare(
            mapping_result,
            snapshot,
        )
        with self.assertRaisesRegex(
            ValueError,
            "current_value must already be NFC-normalized",
        ):
            CollectionChangeProposalBuilder().build(comparison)

    def test_numeric_looking_values_remain_strings(self) -> None:
        target = CollectionTargetField.YEAR
        observation = _observation(target, "01967")
        mapping = ConfirmedCollectionFieldMapping(
            observation,
            target,
            "01967",
        )
        mapping_result = ConfirmedCollectionFieldMappingResult(
            source_coin_id="source-coin-1",
            reviewer_id="collector-1",
            mappings=(mapping,),
        )
        snapshot = CollectionRecordSnapshot(
            CollectionRecordReference("record-1"),
            (
                CollectionRecordFieldSnapshot(
                    target,
                    CollectionRecordFieldAvailability.PRESENT,
                    "1967",
                ),
            ),
        )
        proposal = CollectionChangeProposalBuilder().build(
            CollectionRecordComparisonService().compare(
                mapping_result,
                snapshot,
            )
        ).proposals[0]
        self.assertEqual(proposal.current_value, "1967")
        self.assertEqual(proposal.proposed_value, "01967")
        self.assertIsInstance(proposal.proposed_value, str)

    def test_full_source_observation_is_retained_by_identity(self) -> None:
        comparison = _comparison_result(
            (
                CollectionTargetField.COUNTRY,
                CollectionFieldComparisonOutcome.DIFFERENT,
            )
        )
        source = comparison.comparisons[0].mapping.source_observation
        proposal = CollectionChangeProposalBuilder().build(
            comparison
        ).proposals[0]
        self.assertIs(proposal.source_observation, source)
        self.assertEqual(proposal.source_observation.reviewer_id, "collector-1")
        self.assertEqual(
            proposal.source_observation.provenance,
            source.provenance,
        )
        self.assertEqual(
            proposal.source_observation.rationale,
            source.rationale,
        )
        self.assertIs(
            proposal.source_observation.source_type,
            ConfirmedObservationSource.OCR_REVIEW,
        )
        self.assertEqual(
            proposal.source_observation.schema_version,
            CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        )


class AggregateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = CollectionChangeProposalBuilder()
        self.comparison = _comparison_result(
            (
                CollectionTargetField.YEAR,
                CollectionFieldComparisonOutcome.DIFFERENT,
            ),
            (
                CollectionTargetField.COUNTRY,
                CollectionFieldComparisonOutcome.EXACT_MATCH,
            ),
            (
                CollectionTargetField.DENOMINATION,
                CollectionFieldComparisonOutcome.ABSENT,
            ),
            record_id="target-record-9",
        )

    def test_multiple_proposals_are_deterministically_ordered(self) -> None:
        result = self.builder.build(self.comparison)
        self.assertEqual(
            tuple(item.target_field for item in result.proposals),
            ("country", "denomination", "year"),
        )
        self.assertEqual(
            tuple(item.operation for item in result.proposals),
            (
                CollectionChangeOperation.NO_CHANGE,
                CollectionChangeOperation.ADD,
                CollectionChangeOperation.UPDATE,
            ),
        )

    def test_aggregate_linkage_is_preserved_exactly(self) -> None:
        result = self.builder.build(self.comparison)
        self.assertIs(
            result.target_record,
            self.comparison.target_record,
        )
        self.assertEqual(result.target_record.record_id, "target-record-9")
        self.assertEqual(result.source_coin_id, "source-coin-1")
        self.assertEqual(result.reviewer_id, "collector-1")
        self.assertEqual(result.review_session_id, "review-session-1")
        self.assertEqual(
            result.source_fingerprint,
            "opaque-source-fingerprint",
        )
        self.assertNotEqual(
            result.target_record.record_id,
            result.source_coin_id,
        )

    def test_one_proposal_per_comparison(self) -> None:
        result = self.builder.build(self.comparison)
        self.assertEqual(
            len(result.proposals),
            len(self.comparison.comparisons),
        )

    def test_later_unavailable_prevents_complete_result(self) -> None:
        comparison = _comparison_result(
            (
                CollectionTargetField.COUNTRY,
                CollectionFieldComparisonOutcome.EXACT_MATCH,
            ),
            (
                CollectionTargetField.YEAR,
                CollectionFieldComparisonOutcome.UNAVAILABLE,
            ),
        )
        with self.assertRaises(
            UnavailableCollectionProposalSourceError
        ):
            self.builder.build(comparison)

    def test_result_requires_nonempty_tuple(self) -> None:
        result = self.builder.build(self.comparison)
        with self.assertRaisesRegex(ValueError, "at least one"):
            replace(result, proposals=()).validate()
        with self.assertRaisesRegex(TypeError, "tuple"):
            replace(result, proposals=[]).validate()  # type: ignore[arg-type]

    def test_result_rejects_nondeterministic_order(self) -> None:
        result = self.builder.build(self.comparison)
        with self.assertRaisesRegex(ValueError, "deterministic"):
            replace(
                result,
                proposals=tuple(reversed(result.proposals)),
            ).validate()

    def test_result_rejects_duplicate_target(self) -> None:
        result = self.builder.build(self.comparison)
        duplicate = replace(
            result,
            proposals=(result.proposals[0], result.proposals[0]),
        )
        with self.assertRaises(
            DuplicateCollectionChangeProposalFieldError
        ):
            duplicate.validate()

    def test_result_rejects_mixed_target_record(self) -> None:
        result = self.builder.build(self.comparison)
        foreign = replace(
            result.proposals[0],
            target_record=CollectionRecordReference("other-record"),
        )
        invalid = replace(
            result,
            proposals=(foreign,) + result.proposals[1:],
        )
        with self.assertRaises(
            InvalidCollectionChangeProposalContextError
        ):
            invalid.validate()

    def test_result_rejects_mixed_source_identity(self) -> None:
        result = self.builder.build(self.comparison)
        invalid = replace(result, source_coin_id="other-source")
        with self.assertRaises(
            InvalidCollectionChangeProposalContextError
        ):
            invalid.validate()

    def test_malformed_comparison_context_is_typed(self) -> None:
        malformed = replace(
            self.comparison,
            comparisons=tuple(reversed(self.comparison.comparisons)),
        )
        with self.assertRaises(
            InvalidCollectionChangeProposalContextError
        ):
            self.builder.build(malformed)

    def test_equivalent_inputs_produce_equivalent_outputs(self) -> None:
        self.assertEqual(
            self.builder.build(self.comparison),
            self.builder.build(self.comparison),
        )

    def test_convenience_function_matches_service(self) -> None:
        self.assertEqual(
            build_collection_change_proposals(self.comparison),
            self.builder.build(self.comparison),
        )


class ImmutabilityAndBoundaryTests(unittest.TestCase):
    def test_result_and_nested_proposals_are_frozen_and_slotted(self) -> None:
        result = build_collection_change_proposals(
            _comparison_result()
        )
        for value in (result, result.proposals[0]):
            with self.subTest(contract=type(value).__name__):
                self.assertFalse(hasattr(value, "__dict__"))
                with assert_frozen_slotted_assignment_rejected(self, value):
                    value.extra = "mutation"  # type: ignore[attr-defined]

    def test_builder_is_stateless_and_slotted(self) -> None:
        self.assertFalse(
            hasattr(CollectionChangeProposalBuilder(), "__dict__")
        )

    def test_inputs_and_nested_evidence_remain_unchanged(self) -> None:
        comparison = _comparison_result(
            (
                CollectionTargetField.COUNTRY,
                CollectionFieldComparisonOutcome.DIFFERENT,
            )
        )
        before = repr(comparison)
        observation = comparison.comparisons[0].mapping.source_observation
        provenance = observation.provenance
        CollectionChangeProposalBuilder().build(comparison)
        self.assertEqual(repr(comparison), before)
        self.assertIs(
            comparison.comparisons[0].mapping.source_observation,
            observation,
        )
        self.assertIs(observation.provenance, provenance)

    def test_error_hierarchy_is_narrow(self) -> None:
        for error_type in (
            UnsupportedCollectionComparisonOutcomeError,
            UnavailableCollectionProposalSourceError,
            InvalidCollectionChangeProposalContextError,
            DuplicateCollectionChangeProposalFieldError,
        ):
            with self.subTest(error=error_type.__name__):
                self.assertTrue(
                    issubclass(
                        error_type,
                        CollectionChangeProposalBuildError,
                    )
                )

    def test_no_builder_result_serialization(self) -> None:
        self.assertFalse(
            hasattr(CollectionChangeProposalBuildResult, "to_dict")
        )
        self.assertFalse(
            hasattr(CollectionChangeProposalBuildResult, "from_dict")
        )

    def test_result_is_not_a_change_plan(self) -> None:
        self.assertEqual(
            tuple(
                CollectionChangeProposalBuildResult.__dataclass_fields__
            ),
            (
                "target_record",
                "source_coin_id",
                "reviewer_id",
                "proposals",
                "review_session_id",
                "source_fingerprint",
            ),
        )
        self.assertNotIn(
            "schema_version",
            CollectionChangeProposalBuildResult.__dataclass_fields__,
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
            "os",
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

    def test_module_has_no_plan_approval_or_mutation_surface(self) -> None:
        module = importlib.import_module(_MODULE)
        source = inspect.getsource(module)
        for fragment in (
            "CollectionChangePlan(",
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

    def test_public_api_is_bounded(self) -> None:
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
                "CollectionChangeProposalBuildError",
                "UnsupportedCollectionComparisonOutcomeError",
                "UnavailableCollectionProposalSourceError",
                "InvalidCollectionChangeProposalContextError",
                "DuplicateCollectionChangeProposalFieldError",
                "CollectionChangeProposalBuildResult",
                "CollectionChangeProposalBuilder",
                "build_collection_change_proposals",
            },
        )


if __name__ == "__main__":
    unittest.main()
