"""Tests for pure collection freshness compatibility diagnostics."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
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
    CollectionChangePlan,
    CollectionChangeReasonCode,
    CollectionFieldChangeProposal,
    CollectionRecordReference,
)
from collection_management.workflow_collection_freshness_compatibility import (
    CollectionChangePlanFreshnessCompatibility,
    CollectionFreshnessCompatibilityError,
    CollectionFreshnessCompatibilityFinding,
    CollectionFreshnessCompatibilityReason,
    CollectionFreshnessCompatibilityStatus,
    CollectionFreshnessCompatibilityValidator,
    InvalidCollectionFreshnessCompatibilityContextError,
    MismatchedCollectionFreshnessRecordError,
    NonMatchingCollectionFreshnessEvidenceError,
    UnmatchedCollectionFreshnessEvidenceFieldError,
    require_matching_collection_freshness_evidence,
    validate_collection_freshness_compatibility,
)
import collection_management.workflow_collection_freshness_compatibility as compatibility_module
from collection_management.workflow_collection_freshness_evidence_models import (
    CURRENT_COLLECTION_FRESHNESS_EVIDENCE_SCHEMA_VERSION,
    CollectionFreshnessFieldAvailability,
    CollectionFreshnessFieldEvidence,
    CollectionRecordFreshnessEvidence,
)


_MODULE = "collection_management.workflow_collection_freshness_compatibility"
_TIME = "2000-01-01T00:00:00Z"
_VALUES = {
    "country": "Canada",
    "denomination": "25 cents",
    "year": "1967",
}
_APPROVAL = {
    CollectionChangeOperation.ADD: CollectionChangeApprovalRequirement.REQUIRED,
    CollectionChangeOperation.UPDATE: CollectionChangeApprovalRequirement.REQUIRED,
    CollectionChangeOperation.CLEAR: CollectionChangeApprovalRequirement.REQUIRED,
    CollectionChangeOperation.NO_CHANGE: CollectionChangeApprovalRequirement.NOT_REQUIRED,
    CollectionChangeOperation.CONFLICT: CollectionChangeApprovalRequirement.REQUIRED,
}
_REASON = {
    CollectionChangeOperation.ADD: CollectionChangeReasonCode.NEW_VALUE,
    CollectionChangeOperation.UPDATE: CollectionChangeReasonCode.DIFFERENT_VALUE,
    CollectionChangeOperation.CLEAR: CollectionChangeReasonCode.EXPLICIT_CLEAR,
    CollectionChangeOperation.NO_CHANGE: CollectionChangeReasonCode.EQUIVALENT_VALUE,
    CollectionChangeOperation.CONFLICT: CollectionChangeReasonCode.EXISTING_VALUE_CONFLICT,
}


def _record(record_id: str = "coin-001") -> CollectionRecordReference:
    return CollectionRecordReference(record_id=record_id)


def _observation(
    field_name: str,
    value: str,
) -> ConfirmedFieldObservation:
    return ConfirmedFieldObservation(
        schema_version=CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
        source_coin_id="source-001",
        field_name=field_name,
        submitted_value=value,
        canonical_value=None,
        reviewer_id="reviewer",
        rationale="confirmed",
        provenance=(
            ConfirmedObservationProvenance(
                provider_id="test-ocr",
                image_role="front",
                artifact_key=f"crop-{field_name}",
                source_value=value,
                confidence_score=95.0,
                evidence=("visible field",),
            ),
        ),
        source_type=ConfirmedObservationSource.OCR_REVIEW,
    )


def _proposal(
    target_field: str,
    operation: CollectionChangeOperation,
    *,
    current_value: str | None | object = ...,
    target_record: CollectionRecordReference | None = None,
) -> CollectionFieldChangeProposal:
    source_value = _VALUES[target_field]
    if current_value is ...:
        if operation is CollectionChangeOperation.ADD:
            current = None
        elif operation is CollectionChangeOperation.NO_CHANGE:
            current = source_value
        else:
            current = f"old-{source_value}"
    else:
        current = current_value
    proposed = (
        None
        if operation is CollectionChangeOperation.CLEAR
        else source_value
    )
    return CollectionFieldChangeProposal(
        schema_version=CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
        target_record=target_record or _record(),
        target_field=target_field,
        current_value=current,  # type: ignore[arg-type]
        proposed_value=proposed,
        operation=operation,
        approval_requirement=_APPROVAL[operation],
        source_observation=_observation(target_field, source_value),
        reason_code=_REASON[operation],
        rationale=None,
    )


def _plan(
    *proposals: CollectionFieldChangeProposal,
    target_record: CollectionRecordReference | None = None,
) -> CollectionChangePlan:
    target = target_record or _record()
    return CollectionChangePlan(
        schema_version=CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION,
        target_record=target,
        source_coin_id="source-001",
        proposals=proposals
        or (_proposal("country", CollectionChangeOperation.UPDATE),),
        review_session_id="review-001",
        source_fingerprint="fingerprint",
    )


def _field(
    target_field: str,
    availability: CollectionFreshnessFieldAvailability,
    value: str | None,
) -> CollectionFreshnessFieldEvidence:
    return CollectionFreshnessFieldEvidence(
        target_field=target_field,
        availability=availability,
        value=value,
    )


def _evidence(
    *fields: CollectionFreshnessFieldEvidence,
    target_record: CollectionRecordReference | None = None,
    observed_at: str = _TIME,
) -> CollectionRecordFreshnessEvidence:
    return CollectionRecordFreshnessEvidence(
        schema_version=(
            CURRENT_COLLECTION_FRESHNESS_EVIDENCE_SCHEMA_VERSION
        ),
        target_record=target_record or _record(),
        fields=fields
        or (
            _field(
                "country",
                CollectionFreshnessFieldAvailability.PRESENT,
                "old-Canada",
            ),
        ),
        observed_at=observed_at,
    )


def _finding_for(
    *,
    expected_current: str | None,
    availability: CollectionFreshnessFieldAvailability | None,
    observed_value: str | None = None,
) -> CollectionFreshnessCompatibilityFinding:
    country = _proposal(
        "country",
        (
            CollectionChangeOperation.ADD
            if expected_current is None
            else CollectionChangeOperation.UPDATE
        ),
        current_value=expected_current,
    )
    year = _proposal("year", CollectionChangeOperation.UPDATE)
    plan = _plan(country, year)
    fields = [
        _field(
            "year",
            CollectionFreshnessFieldAvailability.PRESENT,
            "old-1967",
        )
    ]
    if availability is not None:
        fields.insert(
            0,
            _field("country", availability, observed_value),
        )
    result = validate_collection_freshness_compatibility(
        plan,
        _evidence(*fields),
    )
    return result.findings[0]


class VocabularyAndMatrixTests(unittest.TestCase):
    def test_status_and_reason_vocabularies_are_exact(self) -> None:
        self.assertEqual(
            tuple(item.value for item in CollectionFreshnessCompatibilityStatus),
            ("MATCHED", "MISMATCHED", "UNAVAILABLE", "MISSING"),
        )
        self.assertEqual(
            tuple(item.value for item in CollectionFreshnessCompatibilityReason),
            (
                "EXPECTED_PRESENT_VALUE_MATCHED",
                "EXPECTED_ABSENT_STATE_MATCHED",
                "EXPECTED_PRESENT_VALUE_DIFFERED",
                "EXPECTED_PRESENT_BUT_OBSERVED_ABSENT",
                "EXPECTED_ABSENT_BUT_OBSERVED_PRESENT",
                "EVIDENCE_UNAVAILABLE",
                "EVIDENCE_MISSING",
            ),
        )

    def test_matrix_is_immutable_and_has_all_nine_cells(self) -> None:
        self.assertIsInstance(
            compatibility_module._COMPARISON_MATRIX,
            MappingProxyType,
        )
        A = CollectionFreshnessFieldAvailability
        self.assertEqual(
            set(compatibility_module._COMPARISON_MATRIX),
            {
                (True, A.PRESENT, True),
                (True, A.PRESENT, False),
                (True, A.ABSENT, None),
                (True, A.UNAVAILABLE, None),
                (True, None, None),
                (False, A.ABSENT, None),
                (False, A.PRESENT, None),
                (False, A.UNAVAILABLE, None),
                (False, None, None),
            },
        )
        with self.assertRaises(TypeError):
            compatibility_module._COMPARISON_MATRIX[
                (True, None, None)
            ] = (  # type: ignore[index]
                CollectionFreshnessCompatibilityStatus.MATCHED,
                CollectionFreshnessCompatibilityReason.EVIDENCE_MISSING,
            )

    def test_exact_comparison_matrix(self) -> None:
        S = CollectionFreshnessCompatibilityStatus
        R = CollectionFreshnessCompatibilityReason
        A = CollectionFreshnessFieldAvailability
        cases = (
            ("expected", A.PRESENT, "expected", S.MATCHED, R.EXPECTED_PRESENT_VALUE_MATCHED),
            ("expected", A.PRESENT, "different", S.MISMATCHED, R.EXPECTED_PRESENT_VALUE_DIFFERED),
            ("expected", A.ABSENT, None, S.MISMATCHED, R.EXPECTED_PRESENT_BUT_OBSERVED_ABSENT),
            ("expected", A.UNAVAILABLE, None, S.UNAVAILABLE, R.EVIDENCE_UNAVAILABLE),
            ("expected", None, None, S.MISSING, R.EVIDENCE_MISSING),
            (None, A.ABSENT, None, S.MATCHED, R.EXPECTED_ABSENT_STATE_MATCHED),
            (None, A.PRESENT, "anything", S.MISMATCHED, R.EXPECTED_ABSENT_BUT_OBSERVED_PRESENT),
            (None, A.UNAVAILABLE, None, S.UNAVAILABLE, R.EVIDENCE_UNAVAILABLE),
            (None, None, None, S.MISSING, R.EVIDENCE_MISSING),
        )
        for expected, availability, observed, status, reason in cases:
            with self.subTest(
                expected=expected,
                availability=availability,
                observed=observed,
            ):
                finding = _finding_for(
                    expected_current=expected,
                    availability=availability,
                    observed_value=observed,
                )
                self.assertIs(finding.status, status)
                self.assertIs(finding.reason, reason)

    def test_present_empty_and_absent_are_exactly_distinct(self) -> None:
        A = CollectionFreshnessFieldAvailability
        S = CollectionFreshnessCompatibilityStatus
        self.assertIs(
            _finding_for(
                expected_current="",
                availability=A.PRESENT,
                observed_value="",
            ).status,
            S.MATCHED,
        )
        self.assertIs(
            _finding_for(
                expected_current="",
                availability=A.ABSENT,
            ).status,
            S.MISMATCHED,
        )
        self.assertIs(
            _finding_for(
                expected_current=None,
                availability=A.PRESENT,
                observed_value="",
            ).status,
            S.MISMATCHED,
        )


class InputAndBindingTests(unittest.TestCase):
    def test_exact_record_binding_is_accepted(self) -> None:
        plan = _plan()
        evidence = _evidence()
        result = validate_collection_freshness_compatibility(plan, evidence)
        self.assertIs(result.plan, plan)
        self.assertIs(result.evidence, evidence)

    def test_record_mismatch_is_typed_before_findings(self) -> None:
        with self.assertRaises(MismatchedCollectionFreshnessRecordError):
            validate_collection_freshness_compatibility(
                _plan(),
                _evidence(target_record=_record("other-record")),
            )

    def test_input_types_are_typed_context_errors(self) -> None:
        for plan, evidence in (
            (object(), _evidence()),
            (_plan(), object()),
        ):
            with self.subTest(plan=plan, evidence=evidence):
                with self.assertRaises(
                    InvalidCollectionFreshnessCompatibilityContextError
                ):
                    validate_collection_freshness_compatibility(  # type: ignore[arg-type]
                        plan,
                        evidence,
                    )

    def test_malformed_nested_plan_and_evidence_are_wrapped(self) -> None:
        malformed_plan = replace(_plan(), proposals=(object(),))
        malformed_evidence = replace(_evidence(), fields=(object(),))
        for plan, evidence in (
            (malformed_plan, _evidence()),
            (_plan(), malformed_evidence),
        ):
            with self.subTest(plan=plan, evidence=evidence):
                with self.assertRaises(
                    InvalidCollectionFreshnessCompatibilityContextError
                ):
                    validate_collection_freshness_compatibility(
                        plan,
                        evidence,
                    )

    def test_independently_deserialized_equal_inputs_bind(self) -> None:
        original_plan = _plan()
        original_evidence = _evidence()
        plan = CollectionChangePlan.from_dict(original_plan.to_dict())
        evidence = CollectionRecordFreshnessEvidence.from_dict(
            original_evidence.to_dict()
        )
        self.assertIsNot(plan.target_record, evidence.target_record)
        result = validate_collection_freshness_compatibility(plan, evidence)
        self.assertTrue(result.all_fields_matched)
        self.assertIs(result.plan, plan)
        self.assertIs(result.evidence, evidence)


class OperationNeutralityTests(unittest.TestCase):
    def test_all_current_operations_are_supported_by_expected_state(self) -> None:
        A = CollectionFreshnessFieldAvailability
        for operation in CollectionChangeOperation:
            with self.subTest(operation=operation):
                proposal = _proposal("country", operation)
                if proposal.current_value is None:
                    field = _field("country", A.ABSENT, None)
                else:
                    field = _field(
                        "country",
                        A.PRESENT,
                        proposal.current_value,
                    )
                result = validate_collection_freshness_compatibility(
                    _plan(proposal),
                    _evidence(field),
                )
                self.assertTrue(result.all_fields_matched)
                self.assertIs(
                    result.findings[0].status,
                    CollectionFreshnessCompatibilityStatus.MATCHED,
                )

    def test_same_expected_state_classifies_identically_across_operations(
        self,
    ) -> None:
        A = CollectionFreshnessFieldAvailability
        statuses = []
        for operation in (
            CollectionChangeOperation.UPDATE,
            CollectionChangeOperation.CLEAR,
            CollectionChangeOperation.CONFLICT,
        ):
            proposal = _proposal(
                "country",
                operation,
                current_value="same-current",
            )
            result = validate_collection_freshness_compatibility(
                _plan(proposal),
                _evidence(_field("country", A.PRESENT, "changed")),
            )
            statuses.append(result.findings[0].status)
        self.assertEqual(
            statuses,
            [CollectionFreshnessCompatibilityStatus.MISMATCHED] * 3,
        )


class ExtraEvidenceAndDuplicateTests(unittest.TestCase):
    def test_extra_evidence_is_rejected_without_silent_ignore(self) -> None:
        with self.assertRaises(
            UnmatchedCollectionFreshnessEvidenceFieldError
        ) as captured:
            validate_collection_freshness_compatibility(
                _plan(),
                _evidence(
                    _field(
                        "country",
                        CollectionFreshnessFieldAvailability.PRESENT,
                        "old-Canada",
                    ),
                    _field(
                        "year",
                        CollectionFreshnessFieldAvailability.PRESENT,
                        "1967",
                    ),
                ),
            )
        self.assertEqual(captured.exception.target_field, "year")

    def test_malformed_duplicate_evidence_fails_before_lookup_overwrite(
        self,
    ) -> None:
        field = _field(
            "country",
            CollectionFreshnessFieldAvailability.PRESENT,
            "old-Canada",
        )
        evidence = replace(_evidence(), fields=(field, field))
        with self.assertRaises(
            InvalidCollectionFreshnessCompatibilityContextError
        ):
            validate_collection_freshness_compatibility(_plan(), evidence)

    def test_malformed_duplicate_plan_fields_fail_closed(self) -> None:
        proposal = _proposal("country", CollectionChangeOperation.UPDATE)
        plan = replace(_plan(), proposals=(proposal, proposal))
        with self.assertRaises(
            InvalidCollectionFreshnessCompatibilityContextError
        ):
            validate_collection_freshness_compatibility(plan, _evidence())


class FindingAndAggregateTests(unittest.TestCase):
    def test_findings_retain_exact_identities_and_plan_order(self) -> None:
        proposals = (
            _proposal("country", CollectionChangeOperation.UPDATE),
            _proposal("year", CollectionChangeOperation.UPDATE),
        )
        fields = (
            _field(
                "country",
                CollectionFreshnessFieldAvailability.PRESENT,
                "old-Canada",
            ),
            _field(
                "year",
                CollectionFreshnessFieldAvailability.PRESENT,
                "old-1967",
            ),
        )
        plan = _plan(*proposals)
        evidence = _evidence(*fields)
        result = validate_collection_freshness_compatibility(plan, evidence)
        for finding, proposal, field in zip(
            result.findings,
            proposals,
            fields,
        ):
            self.assertIs(finding.proposal, proposal)
            self.assertIs(finding.evidence, field)

    def test_missing_finding_retains_none(self) -> None:
        plan = _plan(
            _proposal("country", CollectionChangeOperation.UPDATE),
            _proposal("year", CollectionChangeOperation.UPDATE),
        )
        result = validate_collection_freshness_compatibility(
            plan,
            _evidence(
                _field(
                    "year",
                    CollectionFreshnessFieldAvailability.PRESENT,
                    "old-1967",
                )
            ),
        )
        self.assertIsNone(result.findings[0].evidence)
        self.assertIs(
            result.findings[0].status,
            CollectionFreshnessCompatibilityStatus.MISSING,
        )

    def test_reconstructed_finding_rejects_contradictions(self) -> None:
        result = validate_collection_freshness_compatibility(
            _plan(),
            _evidence(),
        )
        finding = result.findings[0]
        cases = (
            replace(
                finding,
                status=CollectionFreshnessCompatibilityStatus.MISSING,
            ),
            replace(finding, evidence=None),
            replace(
                finding,
                evidence=_field(
                    "year",
                    CollectionFreshnessFieldAvailability.PRESENT,
                    "old-1967",
                ),
            ),
        )
        for changed in cases:
            with self.subTest(changed=changed):
                with self.assertRaises(
                    InvalidCollectionFreshnessCompatibilityContextError
                ):
                    changed.validate()

    def test_reconstructed_finding_rejects_malformed_nested_types(
        self,
    ) -> None:
        finding = validate_collection_freshness_compatibility(
            _plan(),
            _evidence(),
        ).findings[0]
        cases = (
            replace(finding, proposal=object()),
            replace(finding, evidence=object()),
            replace(finding, status="MATCHED"),
            replace(
                finding,
                reason="EXPECTED_PRESENT_VALUE_MATCHED",
            ),
        )
        for changed in cases:
            with self.subTest(changed=changed):
                with self.assertRaises(
                    InvalidCollectionFreshnessCompatibilityContextError
                ):
                    changed.validate()

    def test_reconstructed_aggregate_rejects_order_identity_and_count_drift(
        self,
    ) -> None:
        plan = _plan(
            _proposal("country", CollectionChangeOperation.UPDATE),
            _proposal("year", CollectionChangeOperation.UPDATE),
        )
        evidence = _evidence(
            _field(
                "country",
                CollectionFreshnessFieldAvailability.PRESENT,
                "old-Canada",
            ),
            _field(
                "year",
                CollectionFreshnessFieldAvailability.PRESENT,
                "old-1967",
            ),
        )
        result = validate_collection_freshness_compatibility(plan, evidence)
        cases = (
            replace(result, findings=tuple(reversed(result.findings))),
            replace(result, findings=result.findings[:-1]),
            replace(
                result,
                findings=(
                    replace(
                        result.findings[0],
                        proposal=replace(plan.proposals[0]),
                    ),
                    result.findings[1],
                ),
            ),
            replace(
                result,
                findings=(
                    replace(
                        result.findings[0],
                        evidence=replace(evidence.fields[0]),
                    ),
                    result.findings[1],
                ),
            ),
        )
        for changed in cases:
            with self.subTest(changed=changed):
                with self.assertRaises(
                    InvalidCollectionFreshnessCompatibilityContextError
                ):
                    changed.validate()

    def test_summary_drift_is_rejected(self) -> None:
        result = validate_collection_freshness_compatibility(
            _plan(),
            _evidence(),
        )
        for field_name in (
            "all_fields_matched",
            "contains_mismatched_items",
            "contains_unavailable_items",
            "contains_missing_items",
        ):
            with self.subTest(field_name=field_name):
                with self.assertRaises(
                    InvalidCollectionFreshnessCompatibilityContextError
                ):
                    replace(
                        result,
                        **{
                            field_name: not getattr(result, field_name)
                        },
                    ).validate()

    def test_reconstructed_aggregate_rejects_types_and_duplicate_findings(
        self,
    ) -> None:
        plan = _plan(
            _proposal("country", CollectionChangeOperation.UPDATE),
            _proposal("year", CollectionChangeOperation.UPDATE),
        )
        evidence = _evidence(
            _field(
                "country",
                CollectionFreshnessFieldAvailability.PRESENT,
                "old-Canada",
            ),
            _field(
                "year",
                CollectionFreshnessFieldAvailability.PRESENT,
                "old-1967",
            ),
        )
        result = validate_collection_freshness_compatibility(plan, evidence)
        cases = (
            replace(result, plan=object()),
            replace(result, evidence=object()),
            replace(result, findings=(object(), object())),
            replace(
                result,
                findings=(
                    result.findings[0],
                    result.findings[0],
                ),
            ),
        )
        for changed in cases:
            with self.subTest(changed=changed):
                with self.assertRaises(
                    InvalidCollectionFreshnessCompatibilityContextError
                ):
                    changed.validate()


class SummaryAndStrictHelperTests(unittest.TestCase):
    def _mixed_result(self) -> CollectionChangePlanFreshnessCompatibility:
        plan = _plan(
            _proposal("country", CollectionChangeOperation.UPDATE),
            _proposal("denomination", CollectionChangeOperation.UPDATE),
            _proposal("year", CollectionChangeOperation.UPDATE),
        )
        return validate_collection_freshness_compatibility(
            plan,
            _evidence(
                _field(
                    "country",
                    CollectionFreshnessFieldAvailability.PRESENT,
                    "changed",
                ),
                _field(
                    "denomination",
                    CollectionFreshnessFieldAvailability.UNAVAILABLE,
                    None,
                ),
            ),
        )

    def test_all_matched_summary_and_strict_return(self) -> None:
        plan = _plan()
        evidence = _evidence()
        result = require_matching_collection_freshness_evidence(
            plan,
            evidence,
        )
        self.assertTrue(result.all_fields_matched)
        self.assertFalse(result.contains_mismatched_items)
        self.assertFalse(result.contains_unavailable_items)
        self.assertFalse(result.contains_missing_items)

    def test_individual_summary_axes(self) -> None:
        mixed = self._mixed_result()
        self.assertFalse(mixed.all_fields_matched)
        self.assertTrue(mixed.contains_mismatched_items)
        self.assertTrue(mixed.contains_unavailable_items)
        self.assertTrue(mixed.contains_missing_items)

    def test_strict_error_groups_fields_in_plan_order(self) -> None:
        result = self._mixed_result()
        with self.assertRaises(
            NonMatchingCollectionFreshnessEvidenceError
        ) as captured:
            require_matching_collection_freshness_evidence(
                result.plan,
                result.evidence,
            )
        self.assertEqual(captured.exception.mismatched_fields, ("country",))
        self.assertEqual(
            captured.exception.unavailable_fields,
            ("denomination",),
        )
        self.assertEqual(captured.exception.missing_fields, ("year",))

    def test_old_observation_can_match_without_age_policy(self) -> None:
        result = validate_collection_freshness_compatibility(
            _plan(),
            _evidence(observed_at="1900-01-01T00:00:00Z"),
        )
        self.assertTrue(result.all_fields_matched)
        self.assertEqual(
            result.evidence.observed_at,
            "1900-01-01T00:00:00Z",
        )


class ExactValueTests(unittest.TestCase):
    def test_values_compare_exactly_without_normalization(self) -> None:
        values = (
            "",
            " Canada ",
            "CANADA",
            "10.00",
            "001967",
            "Montréal",
            "C$ 1.00 / proof-like",
        )
        for exact in values:
            with self.subTest(exact=exact):
                proposal = _proposal(
                    "country",
                    CollectionChangeOperation.UPDATE,
                    current_value=exact,
                )
                result = validate_collection_freshness_compatibility(
                    _plan(proposal),
                    _evidence(
                        _field(
                            "country",
                            CollectionFreshnessFieldAvailability.PRESENT,
                            exact,
                        )
                    ),
                )
                self.assertTrue(result.all_fields_matched)

    def test_case_and_whitespace_differences_mismatch(self) -> None:
        proposal = _proposal(
            "country",
            CollectionChangeOperation.UPDATE,
            current_value="Canada original",
        )
        for observed in (
            "canada original",
            " Canada original",
            "Canada original ",
        ):
            with self.subTest(observed=observed):
                result = validate_collection_freshness_compatibility(
                    _plan(proposal),
                    _evidence(
                        _field(
                            "country",
                            CollectionFreshnessFieldAvailability.PRESENT,
                            observed,
                        )
                    ),
                )
                self.assertTrue(result.contains_mismatched_items)


class ImmutabilityAndArchitectureTests(unittest.TestCase):
    def test_results_are_frozen_slotted_and_transient(self) -> None:
        result = validate_collection_freshness_compatibility(
            _plan(),
            _evidence(),
        )
        for value in (result.findings[0], result):
            with self.subTest(value=value):
                self.assertFalse(hasattr(value, "__dict__"))
                with assert_frozen_slotted_assignment_rejected(self, value):
                    value.extra = True  # type: ignore[attr-defined]
                self.assertFalse(hasattr(type(value), "to_dict"))
                self.assertFalse(hasattr(type(value), "from_dict"))
        finding = result.findings[0]
        for value, name, changed in (
            (finding, "proposal", replace(finding.proposal)),
            (finding, "evidence", None),
            (
                finding,
                "status",
                CollectionFreshnessCompatibilityStatus.MISSING,
            ),
            (
                finding,
                "reason",
                CollectionFreshnessCompatibilityReason.EVIDENCE_MISSING,
            ),
            (result, "plan", replace(result.plan)),
            (result, "evidence", replace(result.evidence)),
            (result, "findings", ()),
            (result, "all_fields_matched", False),
            (result, "contains_mismatched_items", True),
            (result, "contains_unavailable_items", True),
            (result, "contains_missing_items", True),
        ):
            with self.subTest(value=value, name=name):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, name, changed)

    def test_public_error_hierarchy_is_exactly_shared(self) -> None:
        for error_type in (
            InvalidCollectionFreshnessCompatibilityContextError,
            MismatchedCollectionFreshnessRecordError,
            UnmatchedCollectionFreshnessEvidenceFieldError,
            NonMatchingCollectionFreshnessEvidenceError,
        ):
            with self.subTest(error_type=error_type):
                self.assertTrue(
                    issubclass(
                        error_type,
                        CollectionFreshnessCompatibilityError,
                    )
                )

    def test_repeated_validation_is_equivalent_and_inputs_unchanged(
        self,
    ) -> None:
        plan = _plan()
        evidence = _evidence()
        before = (repr(plan), repr(evidence))
        first = validate_collection_freshness_compatibility(plan, evidence)
        second = validate_collection_freshness_compatibility(plan, evidence)
        self.assertEqual(first, second)
        self.assertEqual((repr(plan), repr(evidence)), before)

    def test_future_matrix_gap_fails_closed(self) -> None:
        with patch.object(
            compatibility_module,
            "_COMPARISON_MATRIX",
            MappingProxyType({}),
        ):
            with self.assertRaises(
                InvalidCollectionFreshnessCompatibilityContextError
            ):
                validate_collection_freshness_compatibility(
                    _plan(),
                    _evidence(),
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
            "approval",
            "policy",
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
            "random",
        )
        for fragment in forbidden:
            with self.subTest(fragment=fragment):
                self.assertFalse(
                    any(fragment in name.casefold() for name in imported),
                    imported,
                )
        self.assertNotIn("os", imported)

    def test_module_has_no_authority_or_automatic_surface(self) -> None:
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
            "mutation_ready",
            "is_fresh",
            "is_stale",
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
                "CollectionFreshnessCompatibilityError",
                "InvalidCollectionFreshnessCompatibilityContextError",
                "MismatchedCollectionFreshnessRecordError",
                "UnmatchedCollectionFreshnessEvidenceFieldError",
                "NonMatchingCollectionFreshnessEvidenceError",
                "CollectionFreshnessCompatibilityStatus",
                "CollectionFreshnessCompatibilityReason",
                "CollectionFreshnessCompatibilityFinding",
                "CollectionChangePlanFreshnessCompatibility",
                "CollectionFreshnessCompatibilityValidator",
                "validate_collection_freshness_compatibility",
                "require_matching_collection_freshness_evidence",
            },
        )


if __name__ == "__main__":
    unittest.main()
