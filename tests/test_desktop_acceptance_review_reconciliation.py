from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest

from capture_import.desktop_acceptance_authoring import (
    DesktopAcceptanceAuthoringError,
    prepare_for_freeze,
)
from capture_import.desktop_acceptance_review import (
    DesktopAcceptanceReviewError,
    ReviewExecutionRecord,
    build_review_reconciliation_handoff,
    normalized_review_reconciliation_json,
    validate_review_execution_record,
    validated_review_reconciliation_dict,
)
from tests.test_desktop_acceptance_review import authoring_state, valid_record
from tests.test_desktop_acceptance_review_reporting import (
    _TEST_REPOSITORY_ROOT,
    _empty_track,
    _evidence_catalog,
    _ready_payload,
)


def _build(source: object, payload: object):
    execution = validate_review_execution_record(payload, source)
    catalog = _evidence_catalog(source, payload)
    handoff = build_review_reconciliation_handoff(
        source, execution, catalog, _TEST_REPOSITORY_ROOT
    )
    return handoff, execution


def _case(handoff, case_id: str = "case-001"):
    return next(case for case in handoff.cases if case.case_id == case_id)


def _export(handoff, source: object, execution: ReviewExecutionRecord):
    catalog = _evidence_catalog(source, execution.as_dict())
    return validated_review_reconciliation_dict(
        handoff, source, execution, catalog, _TEST_REPOSITORY_ROOT
    )


def _serialize(handoff, source: object, execution: ReviewExecutionRecord) -> str:
    catalog = _evidence_catalog(source, execution.as_dict())
    return normalized_review_reconciliation_json(
        handoff, source, execution, catalog, _TEST_REPOSITORY_ROOT
    )


class DesktopAcceptanceReviewReconciliationTests(unittest.TestCase):
    def test_fully_matching_resolved_reviews_reconcile(self) -> None:
        source = authoring_state()
        handoff, execution = _build(source, _ready_payload(source))
        case = _case(handoff)
        self.assertEqual(case.identity_status, "matched")
        self.assertEqual(case.expected_action_status, "matched")
        self.assertEqual(
            case.resolved_identity.as_dict(), source["cases"][0]["candidate_identity"]
        )
        self.assertEqual(
            case.resolved_expected_action, source["cases"][0]["expected_action"]
        )
        self.assertTrue(case.review_provenance_reconciled)
        self.assertTrue(handoff.review_provenance_reconciled)
        exported = _export(handoff, source, execution)
        self.assertTrue(exported["review_provenance_reconciled"])

    def test_ground_truth_mismatch_preserves_both_values_and_blocks(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        reviewer_identity = deepcopy(source["cases"][0]["candidate_identity"])
        reviewer_identity["year"] = "different reviewed year"
        for submission in payload["cases"][0]["ground_truth_review"]["submissions"]:
            submission["decision"] = deepcopy(reviewer_identity)
        handoff, _ = _build(source, payload)
        case = _case(handoff)
        self.assertEqual(case.identity_status, "mismatched")
        self.assertEqual(
            case.candidate_identity.as_dict(), source["cases"][0]["candidate_identity"]
        )
        self.assertEqual(case.resolved_identity.as_dict(), reviewer_identity)
        self.assertEqual(case.blockers, ("ground_truth_reconciliation_mismatch",))
        self.assertFalse(case.review_provenance_reconciled)

    def test_country_and_denomination_mismatches_independently_block(self) -> None:
        source = authoring_state()
        for field, reviewed_value in (
            ("country", "Different jurisdiction"),
            ("denomination", "Different denomination"),
        ):
            with self.subTest(field=field):
                payload = _ready_payload(source)
                for submission in payload["cases"][0]["ground_truth_review"][
                    "submissions"
                ]:
                    submission["decision"][field] = reviewed_value
                handoff, _ = _build(source, payload)
                case = _case(handoff)
                self.assertEqual(case.identity_status, "mismatched")
                self.assertEqual(
                    getattr(case.resolved_identity, field), reviewed_value
                )
                self.assertIn("ground_truth_reconciliation_mismatch", case.blockers)
                self.assertFalse(handoff.review_provenance_reconciled)

    def test_expected_action_mismatch_preserves_both_values_and_blocks(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        candidate = source["cases"][0]["expected_action"]
        reviewed = "identify" if candidate == "abstain" else "abstain"
        for submission in payload["cases"][0]["action_review"]["submissions"]:
            submission["decision"] = reviewed
        handoff, _ = _build(source, payload)
        case = _case(handoff)
        self.assertEqual(case.expected_action_status, "mismatched")
        self.assertEqual(case.candidate_expected_action, candidate)
        self.assertEqual(case.resolved_expected_action, reviewed)
        self.assertEqual(case.blockers, ("action_reconciliation_mismatch",))

    def test_simultaneous_identity_and_action_mismatch(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        for submission in payload["cases"][0]["ground_truth_review"]["submissions"]:
            submission["decision"]["year"] = "different reviewed year"
        candidate = source["cases"][0]["expected_action"]
        reviewed = "identify" if candidate == "abstain" else "abstain"
        for submission in payload["cases"][0]["action_review"]["submissions"]:
            submission["decision"] = reviewed
        handoff, _ = _build(source, payload)
        self.assertEqual(
            _case(handoff).blockers,
            ("ground_truth_reconciliation_mismatch", "action_reconciliation_mismatch"),
        )

    def test_incomplete_ground_truth_blocks_both_reconciliation_tracks(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        payload["cases"][0]["ground_truth_review"] = _empty_track()
        payload["cases"][0]["action_review"] = _empty_track()
        handoff, _ = _build(source, payload)
        case = _case(handoff)
        self.assertEqual(case.identity_status, "blocked")
        self.assertEqual(case.expected_action_status, "blocked")
        self.assertIsNone(case.resolved_identity)
        self.assertIsNone(case.resolved_expected_action)
        self.assertEqual(
            case.blockers,
            ("ground_truth_unassigned", "action_blocked_by_ground_truth"),
        )

    def test_incomplete_action_blocks_action_reconciliation_only(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        payload["cases"][0]["action_review"] = _empty_track()
        handoff, _ = _build(source, payload)
        case = _case(handoff)
        self.assertEqual(case.identity_status, "matched")
        self.assertEqual(case.expected_action_status, "blocked")
        self.assertEqual(case.blockers, ("action_unassigned",))

    def test_ground_truth_disagreement_awaiting_adjudication_is_not_resolved(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        track = payload["cases"][0]["ground_truth_review"]
        track["state"] = "unresolved"
        track["submissions"][1]["decision"]["year"] = "disputed date"
        track["adjudication"] = None
        payload["cases"][0]["action_review"] = _empty_track()
        handoff, _ = _build(source, payload)
        case = _case(handoff)
        self.assertEqual(case.identity_status, "blocked")
        self.assertIsNone(case.resolved_identity)
        self.assertIn("ground_truth_disagreement_awaiting_adjudication", case.blockers)

    def test_action_disagreement_awaiting_adjudication_is_not_resolved(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        track = payload["cases"][0]["action_review"]
        track["state"] = "unresolved"
        track["submissions"][0]["decision"] = "identify"
        track["submissions"][1]["decision"] = "abstain"
        track["adjudication"] = None
        handoff, _ = _build(source, payload)
        case = _case(handoff)
        self.assertEqual(case.expected_action_status, "blocked")
        self.assertIsNone(case.resolved_expected_action)
        self.assertIn("action_disagreement_awaiting_adjudication", case.blockers)

    def test_unresolved_and_rejected_eligibility_are_one_blocker_short(self) -> None:
        source = authoring_state()
        for field, state in (
            ("privacy", "unresolved"),
            ("licensing", "rejected"),
            ("provider_authorization", "unresolved"),
        ):
            with self.subTest(field=field, state=state):
                payload = _ready_payload(source)
                decision = payload["cases"][0]["provider_eligibility"][field]
                decision["state"] = state
                if state == "unresolved":
                    decision["evidence_references"] = []
                handoff, _ = _build(source, payload)
                case = _case(handoff)
                self.assertFalse(case.review_provenance_reconciled)
                self.assertEqual(case.blockers, (f"{field}_{state}",))

    def test_incomplete_provenance_is_one_blocker_short(self) -> None:
        source = authoring_state()
        for field, blocker in (
            ("ownership_or_source", "provenance_ownership_or_source_unresolved"),
            ("evidence_reference", "provenance_evidence_unresolved"),
        ):
            with self.subTest(field=field):
                altered = deepcopy(source)
                altered["cases"][0]["provenance"][field] = ""
                handoff, _ = _build(altered, _ready_payload(altered))
                case = _case(handoff)
                self.assertEqual(case.blockers, (blocker,))
                self.assertFalse(case.review_provenance_reconciled)

    def test_success_does_not_imply_photography_or_freeze_readiness(self) -> None:
        source = authoring_state()
        handoff, execution = _build(source, _ready_payload(source))
        exported = _export(handoff, source, execution)
        self.assertTrue(exported["review_provenance_reconciled"])
        self.assertFalse(exported["authoring_mutation_applied"])
        self.assertFalse(exported["freeze_preparation_authorized"])
        self.assertFalse(exported["benchmark_execution_approved"])
        self.assertNotIn("capture", json.dumps(exported))
        with self.assertRaises(DesktopAcceptanceAuthoringError):
            prepare_for_freeze(source)

    def test_repeat_cases_are_independent_reconciliation_records(self) -> None:
        source = authoring_state()
        handoff, _ = _build(source, _ready_payload(source))
        repeats = [_case(handoff, case_id) for case_id in ("case-028", "case-029", "case-030")]
        self.assertEqual([case.case_id for case in repeats], ["case-028", "case-029", "case-030"])
        self.assertEqual(len(handoff.cases), 30)
        self.assertTrue(all(case.review_provenance_reconciled for case in repeats))

    def test_unit4_aggregate_cardinality_blocker_is_propagated_unchanged(self) -> None:
        source = authoring_state()
        source["cases"].pop()
        payload = _ready_payload(source)
        execution = validate_review_execution_record(payload, source)
        catalog = _evidence_catalog(source, payload)
        handoff = build_review_reconciliation_handoff(
            source, execution, catalog, _TEST_REPOSITORY_ROOT
        )
        blocker = "corpus_case_count_mismatch:expected=30:actual=29"
        self.assertEqual(handoff.aggregate_blockers, (blocker,))
        self.assertEqual(handoff.blockers[0], blocker)
        self.assertFalse(handoff.unit4_review_provenance_ready)
        self.assertFalse(handoff.review_provenance_reconciled)

    def test_unit4_oversized_cardinality_blocker_is_propagated_unchanged(self) -> None:
        source = authoring_state()
        extra = deepcopy(source["cases"][-1])
        extra["case_id"] = "case-031"
        extra["specimen_id"] = "specimen-031"
        extra["repeated_capture"]["repeated_case_id"] = None
        source["cases"].append(extra)
        payload = _ready_payload(source)
        execution = validate_review_execution_record(payload, source)
        catalog = _evidence_catalog(source, payload)
        handoff = build_review_reconciliation_handoff(
            source, execution, catalog, _TEST_REPOSITORY_ROOT
        )
        blocker = "corpus_case_count_mismatch:expected=30:actual=31"
        self.assertEqual(handoff.aggregate_blockers, (blocker,))
        self.assertEqual(handoff.blockers[0], blocker)
        self.assertFalse(handoff.unit4_review_provenance_ready)
        self.assertFalse(handoff.review_provenance_reconciled)

    def test_unit4_evidence_resolution_result_is_propagated_without_rederivation(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        missing = payload["cases"][0]["ground_truth_review"]["submissions"][0][
            "evidence_references"
        ][0]
        execution = validate_review_execution_record(payload, source)
        catalog = _evidence_catalog(source, payload, omit=(missing,))
        handoff = build_review_reconciliation_handoff(
            source, execution, catalog, _TEST_REPOSITORY_ROOT
        )
        case = _case(handoff)
        self.assertIn("ground_truth_evidence_unresolved", case.blockers)
        self.assertIn(missing, case.unresolved_evidence.ground_truth)
        self.assertEqual(handoff.evidence_catalog_digest, catalog.digest)
        self.assertFalse(handoff.unit4_review_provenance_ready)
        self.assertFalse(handoff.review_provenance_reconciled)

    def test_case_blocker_and_reference_order_is_deterministic(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        track = payload["cases"][0]["ground_truth_review"]
        track["submissions"][0]["evidence_references"] = ["repo:z", "repo:a"]
        track["submissions"][1]["evidence_references"] = ["repo:m"]
        privacy = payload["cases"][0]["provider_eligibility"]["privacy"]
        privacy["state"] = "unresolved"
        privacy["evidence_references"] = []
        handoff, _ = _build(source, payload)
        case = _case(handoff)
        self.assertEqual(case.ground_truth_evidence_references, ("repo:a", "repo:m", "repo:z"))
        self.assertEqual(case.blockers, ("privacy_unresolved",))
        self.assertEqual(
            [item.case_id for item in handoff.cases],
            sorted(item.case_id for item in handoff.cases),
        )

    def test_equivalent_permitted_input_order_produces_identical_bytes(self) -> None:
        source_a = authoring_state()
        payload_a = _ready_payload(source_a)
        handoff_a, execution_a = _build(source_a, payload_a)

        source_b = deepcopy(source_a)
        source_b["cases"].reverse()
        payload_b = deepcopy(payload_a)
        payload_b["cases"].reverse()
        for case in payload_b["cases"]:
            case["ground_truth_review"]["submissions"].reverse()
            case["action_review"]["submissions"].reverse()
            for submission in case["ground_truth_review"]["submissions"]:
                submission["evidence_references"].reverse()
        handoff_b, execution_b = _build(source_b, payload_b)
        self.assertEqual(
            _serialize(handoff_a, source_a, execution_a),
            _serialize(handoff_b, source_b, execution_b),
        )

    def test_malformed_authoring_and_execution_fail_closed(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        execution = validate_review_execution_record(payload, source)
        catalog = _evidence_catalog(source, payload)
        malformed_source = deepcopy(source)
        malformed_source["schema"] = "unsupported"
        with self.assertRaises(DesktopAcceptanceAuthoringError):
            build_review_reconciliation_handoff(
                malformed_source, execution, catalog, _TEST_REPOSITORY_ROOT
            )
        malformed_execution = ReviewExecutionRecord(execution.schema, execution.version, ())
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, "case roster mismatch"):
            build_review_reconciliation_handoff(
                source, malformed_execution, catalog, _TEST_REPOSITORY_ROOT
            )

    def test_directly_constructed_models_cannot_bypass_export_validation(self) -> None:
        source = authoring_state()
        handoff, execution = _build(source, _ready_payload(source))
        self.assertFalse(hasattr(handoff, "as_dict"))
        self.assertFalse(hasattr(handoff.cases[0], "as_dict"))
        malformed_case = replace(
            handoff.cases[0],
            review_provenance_reconciled=True,
            blockers=("fabricated_blocker",),
        )
        malformed = replace(handoff, cases=(malformed_case, *handoff.cases[1:]))
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, "does not match"):
            _export(malformed, source, execution)

    def test_source_objects_remain_unchanged(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        execution = validate_review_execution_record(payload, source)
        catalog = _evidence_catalog(source, payload)
        source_before = deepcopy(source)
        execution_before = execution.as_dict()
        handoff = build_review_reconciliation_handoff(
            source, execution, catalog, _TEST_REPOSITORY_ROOT
        )
        normalized_review_reconciliation_json(
            handoff, source, execution, catalog, _TEST_REPOSITORY_ROOT
        )
        self.assertEqual(source, source_before)
        self.assertEqual(execution.as_dict(), execution_before)

    def test_export_omits_reviewer_identity_rationale_and_private_notes(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        candidate = deepcopy(source["cases"][0]["candidate_identity"])
        track = payload["cases"][0]["ground_truth_review"]
        track["submissions"][0]["decision"] = deepcopy(candidate)
        track["submissions"][1]["decision"] = deepcopy(candidate)
        track["submissions"][1]["decision"]["year"] = "PRIVATE-ALTERNATE-VALUE"
        track["adjudication"] = {
            "reviewer_id": "adjudicator:opaque-omega",
            "decision": candidate,
            "evidence_references": ["repo:adjudication-audit"],
            "rationale": "SENSITIVE HUMAN RATIONALE",
        }
        handoff, execution = _build(source, payload)
        serialized = _serialize(handoff, source, execution)
        for submission in execution.cases[0].ground_truth_review.submissions:
            self.assertNotIn(submission.reviewer_id, serialized)
        self.assertNotIn("adjudicator:opaque-omega", serialized)
        self.assertNotIn("SENSITIVE HUMAN RATIONALE", serialized)
        self.assertNotIn("PRIVATE-ALTERNATE-VALUE", serialized)
        self.assertNotIn(source["cases"][0]["provenance"]["notes"], serialized)
        self.assertIn("repo:adjudication-audit", serialized)


if __name__ == "__main__":
    unittest.main()
