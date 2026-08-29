from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import tempfile
import unittest

from capture_import.desktop_acceptance_review import (
    DesktopAcceptanceReviewError,
    IdentityDecision,
    REVIEW_EXECUTION_SCHEMA,
    REVIEW_EXECUTION_VERSION,
    ReviewExecutionRecord,
    load_review_execution_record,
    normalized_review_execution_json,
    validate_review_execution_record,
)
from capture_import.desktop_acceptance_authoring import load_authoring_plan


_AUTHORING_PLAN = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "real-world-desktop-v1"
    / "authoring-plan.json"
)


def authoring_state() -> object:
    return load_authoring_plan(_AUTHORING_PLAN)


def _reviewer(number: int) -> str:
    return f"reviewer:panel-{number:03d}"


def _evidence(number: int) -> str:
    return f"evidence:record-{number:03d}"


def _identity(year: int = 1946) -> dict[str, str]:
    return {"country": "Canada", "denomination": "1 dollar", "year": str(year)}


def _track(
    decision: object,
    reviewer_a: int,
    reviewer_b: int,
    *,
    state: str = "complete",
) -> dict[str, object]:
    return {
        "state": state,
        "submissions": [
            {
                "reviewer_id": _reviewer(reviewer_a),
                "decision": deepcopy(decision),
                "evidence_references": [_evidence(reviewer_a)],
            },
            {
                "reviewer_id": _reviewer(reviewer_b),
                "decision": deepcopy(decision),
                "evidence_references": [_evidence(reviewer_b)],
            },
        ],
        "adjudication": None,
    }


def _eligibility(state: str = "approved") -> dict[str, object]:
    return {
        field: {
            "state": state,
            "evidence_references": [_evidence(900 + index)] if state != "unresolved" else [],
        }
        for index, field in enumerate(("privacy", "licensing", "provider_authorization"), start=1)
    }


def valid_record(authoring: object | None = None) -> dict[str, object]:
    source = authoring if authoring is not None else authoring_state()
    cases: list[dict[str, object]] = []
    for number, authoring_case in enumerate(source["cases"], start=1):
        base = number * 10
        cases.append(
            {
                "case_id": authoring_case["case_id"],
                "specimen_id": authoring_case["specimen_id"],
                "ground_truth_review": _track(_identity(1900 + number), base + 1, base + 2),
                "action_review": _track("identify", base + 1, base + 3),
                "provider_eligibility": _eligibility(),
            }
        )
    return {
        "schema": REVIEW_EXECUTION_SCHEMA,
        "version": REVIEW_EXECUTION_VERSION,
        "cases": cases,
    }


def _validate(payload: object, authoring: object | None = None) -> ReviewExecutionRecord:
    source = authoring if authoring is not None else authoring_state()
    return validate_review_execution_record(payload, source)


class DesktopAcceptanceReviewTests(unittest.TestCase):
    def assert_invalid(
        self, payload: object, text: str, authoring: object | None = None
    ) -> None:
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, text):
            _validate(payload, authoring)

    def test_valid_record_normalizes_to_immutable_models(self) -> None:
        payload = valid_record()
        record = _validate(payload)
        self.assertEqual(len(record.cases), 30)
        self.assertEqual(record.cases[0].case_id, "case-001")
        self.assertIsInstance(
            record.cases[0].ground_truth_review.submissions[0].decision,
            IdentityDecision,
        )
        with self.assertRaises(FrozenInstanceError):
            record.cases[0].case_id = "case-999"  # type: ignore[misc]

    def test_reviewer_can_overlap_across_tracks(self) -> None:
        payload = valid_record()
        case = payload["cases"][0]
        self.assertEqual(
            case["ground_truth_review"]["submissions"][0]["reviewer_id"],
            case["action_review"]["submissions"][0]["reviewer_id"],
        )
        _validate(payload)

    def test_non_hex_opaque_reviewer_ids_are_valid(self) -> None:
        payload = valid_record()
        track = payload["cases"][0]["ground_truth_review"]
        track["submissions"][0]["reviewer_id"] = "reviewer:panel-alpha_7"
        track["submissions"][1]["reviewer_id"] = "rvw-beta.02"
        _validate(payload)

    def test_normalization_orders_cases_submissions_and_evidence(self) -> None:
        payload = valid_record()
        payload["cases"].reverse()
        track = payload["cases"][-1]["ground_truth_review"]
        track["submissions"].reverse()
        track["submissions"][0]["evidence_references"] = [
            "repo:z-last",
            "repo:a-first",
        ]
        record = _validate(payload)
        self.assertEqual(record.cases[0].case_id, "case-001")
        self.assertLess(
            record.cases[0].ground_truth_review.submissions[0].reviewer_id,
            record.cases[0].ground_truth_review.submissions[1].reviewer_id,
        )
        self.assertEqual(
            record.cases[0].ground_truth_review.submissions[1].evidence_references,
            ("repo:a-first", "repo:z-last"),
        )

    def test_normalized_json_is_deterministic(self) -> None:
        first_payload = valid_record()
        second_payload = deepcopy(first_payload)
        second_payload["cases"].reverse()
        source = authoring_state()
        first = normalized_review_execution_json(_validate(first_payload, source), source)
        second = normalized_review_execution_json(_validate(second_payload, source), source)
        self.assertEqual(first, second)
        self.assertEqual(json.loads(first)["cases"][0]["case_id"], "case-001")

    def test_validation_does_not_mutate_input(self) -> None:
        payload = valid_record()
        original = deepcopy(payload)
        _validate(payload)
        self.assertEqual(payload, original)

    def test_unresolved_empty_tracks_are_valid_and_non_approved(self) -> None:
        payload = valid_record()
        case = payload["cases"][0]
        case["ground_truth_review"] = {
            "state": "unresolved",
            "submissions": [],
            "adjudication": None,
        }
        case["action_review"] = {
            "state": "unresolved",
            "submissions": [],
            "adjudication": None,
        }
        case["provider_eligibility"] = _eligibility("unresolved")
        record = _validate(payload)
        self.assertFalse(record.cases[0].provider_eligibility.approved)

    def test_one_submission_keeps_track_unresolved(self) -> None:
        payload = valid_record()
        case = payload["cases"][0]
        track = case["ground_truth_review"]
        track["state"] = "unresolved"
        track["submissions"].pop()
        case["action_review"] = {
            "state": "unresolved",
            "submissions": [],
            "adjudication": None,
        }
        _validate(payload)

    def test_duplicate_reviewer_within_track_is_rejected(self) -> None:
        payload = valid_record()
        track = payload["cases"][0]["ground_truth_review"]
        track["submissions"][1]["reviewer_id"] = track["submissions"][0]["reviewer_id"]
        self.assert_invalid(payload, "distinct reviewer IDs")

    def test_completed_track_requires_exactly_two_submissions(self) -> None:
        payload = valid_record()
        payload["cases"][0]["ground_truth_review"]["submissions"].pop()
        self.assert_invalid(payload, "complete state requires exactly two submissions")

    def test_more_than_two_submissions_is_rejected(self) -> None:
        payload = valid_record()
        track = payload["cases"][0]["ground_truth_review"]
        track["submissions"].append(deepcopy(track["submissions"][0]))
        track["submissions"][2]["reviewer_id"] = _reviewer(999)
        self.assert_invalid(payload, "more than two submissions")

    def test_disagreement_requires_adjudication_and_unresolved_state(self) -> None:
        payload = valid_record()
        track = payload["cases"][0]["action_review"]
        track["submissions"][1]["decision"] = "abstain"
        self.assert_invalid(payload, "complete disagreement requires adjudication")
        track["state"] = "unresolved"
        _validate(payload)

    def test_agreeing_submissions_may_remain_explicitly_unresolved(self) -> None:
        payload = valid_record()
        payload["cases"][0]["action_review"]["state"] = "unresolved"
        record = _validate(payload)
        self.assertEqual(record.cases[0].action_review.state, "unresolved")

    def test_valid_distinct_adjudicator_completes_disagreement(self) -> None:
        payload = valid_record()
        track = payload["cases"][0]["action_review"]
        track["submissions"][1]["decision"] = "abstain"
        track["adjudication"] = {
            "reviewer_id": _reviewer(999),
            "decision": "identify",
            "evidence_references": [_evidence(999)],
            "rationale": "The resolved identity is within the v1 domain.",
        }
        _validate(payload)

    def test_ground_truth_disagreement_with_valid_adjudication(self) -> None:
        payload = valid_record()
        track = payload["cases"][0]["ground_truth_review"]
        track["submissions"][1]["decision"]["year"] = "uncertain-date"
        track["adjudication"] = {
            "reviewer_id": "adjudicator:gt-panel-c",
            "decision": _identity(1901),
            "evidence_references": ["repo:gt-adjudication-case-001"],
            "rationale": "The dated institutional record resolves the issue year.",
        }
        _validate(payload)

    def test_adjudicator_may_overlap_with_other_track_only(self) -> None:
        payload = valid_record()
        case = payload["cases"][0]
        action = case["action_review"]
        action["submissions"][1]["decision"] = "abstain"
        action["adjudication"] = {
            "reviewer_id": case["ground_truth_review"]["submissions"][1]["reviewer_id"],
            "decision": "identify",
            "evidence_references": ["policy:domain-v1:case-001"],
            "rationale": "The resolved identity is in domain.",
        }
        _validate(payload)

    def test_adjudicator_must_be_distinct(self) -> None:
        payload = valid_record()
        track = payload["cases"][0]["action_review"]
        track["submissions"][1]["decision"] = "abstain"
        track["adjudication"] = {
            "reviewer_id": track["submissions"][0]["reviewer_id"],
            "decision": "identify",
            "evidence_references": [_evidence(999)],
            "rationale": "Supported resolution.",
        }
        self.assert_invalid(payload, "distinct reviewer")

    def test_adjudication_is_rejected_when_reviewers_agree(self) -> None:
        payload = valid_record()
        payload["cases"][0]["action_review"]["adjudication"] = {
            "reviewer_id": _reviewer(999),
            "decision": "identify",
            "evidence_references": [_evidence(999)],
            "rationale": "Unnecessary adjudication.",
        }
        self.assert_invalid(payload, "only for two disagreeing")

    def test_adjudication_requires_evidence_and_rationale(self) -> None:
        payload = valid_record()
        track = payload["cases"][0]["action_review"]
        track["submissions"][1]["decision"] = "abstain"
        track["adjudication"] = {
            "reviewer_id": _reviewer(999),
            "decision": "identify",
            "evidence_references": [],
            "rationale": "",
        }
        self.assert_invalid(payload, "requires supporting evidence")
        track["adjudication"]["evidence_references"] = [_evidence(999)]
        self.assert_invalid(payload, "non-empty normalized text")

    def test_malformed_adjudication_decisions_are_rejected(self) -> None:
        payload = valid_record()
        track = payload["cases"][0]["action_review"]
        track["submissions"][1]["decision"] = "abstain"
        track["adjudication"] = {
            "reviewer_id": "adjudicator:action-c",
            "decision": {"unexpected": "object"},
            "evidence_references": [_evidence(999)],
            "rationale": "Synthetic test rationale.",
        }
        self.assert_invalid(payload, "identify or abstain")

        payload = valid_record()
        track = payload["cases"][0]["ground_truth_review"]
        track["submissions"][1]["decision"]["year"] = "date uncertain"
        track["adjudication"] = {
            "reviewer_id": "adjudicator:ground-truth-c",
            "decision": {"country": "Canada", "denomination": "1 dollar"},
            "evidence_references": [_evidence(999)],
            "rationale": "Synthetic test rationale.",
        }
        self.assert_invalid(payload, "missing year")

    def test_action_submission_requires_completed_ground_truth(self) -> None:
        payload = valid_record()
        payload["cases"][0]["ground_truth_review"] = {
            "state": "unresolved",
            "submissions": [],
            "adjudication": None,
        }
        self.assert_invalid(payload, "before ground truth is complete")

    def test_invalid_action_and_incomplete_identity_are_rejected(self) -> None:
        payload = valid_record()
        payload["cases"][0]["action_review"]["submissions"][0]["decision"] = "guess"
        self.assert_invalid(payload, "identify or abstain")
        payload = valid_record()
        payload["cases"][0]["action_review"]["submissions"][0]["decision"] = []
        self.assert_invalid(payload, "identify or abstain")
        payload = valid_record()
        del payload["cases"][0]["ground_truth_review"]["submissions"][0]["decision"]["year"]
        self.assert_invalid(payload, "invalid fields")

    def test_year_uses_authoring_non_empty_text_semantics(self) -> None:
        payload = valid_record()
        for submission in payload["cases"][0]["ground_truth_review"]["submissions"]:
            submission["decision"]["year"] = "date uncertain"
        _validate(payload)

    def test_submission_requires_evidence(self) -> None:
        payload = valid_record()
        payload["cases"][0]["ground_truth_review"]["submissions"][0]["evidence_references"] = []
        self.assert_invalid(payload, "requires supporting evidence")

    def test_duplicate_evidence_reference_is_rejected(self) -> None:
        payload = valid_record()
        references = payload["cases"][0]["ground_truth_review"]["submissions"][0][
            "evidence_references"
        ]
        references.append(references[0])
        self.assert_invalid(payload, "duplicate references")

    def test_architecture_supported_evidence_references_are_valid(self) -> None:
        payload = valid_record()
        references = [
            "benchmarks/real-world-desktop-v1/reviews/case-001-evidence-notes.md#source-a",
            "inventory:S001",
            "https://example.org/catalog/coin?id=123#record",
            "policy:provider-terms:2026-08-28",
        ]
        payload["cases"][0]["ground_truth_review"]["submissions"][0][
            "evidence_references"
        ] = references
        record = _validate(payload)
        self.assertEqual(
            record.cases[0].ground_truth_review.submissions[0].evidence_references,
            tuple(sorted(references)),
        )

    def test_evidence_reference_may_be_reused_explicitly(self) -> None:
        payload = valid_record()
        shared = "repo:shared-specimen-evidence"
        payload["cases"][0]["ground_truth_review"]["submissions"][0][
            "evidence_references"
        ] = [shared]
        payload["cases"][27]["ground_truth_review"]["submissions"][0][
            "evidence_references"
        ] = [shared]
        _validate(payload)

    def test_unsafe_identifiers_and_references_are_rejected(self) -> None:
        unsafe_ids = (
            "",
            " reviewer-id",
            "reviewer id",
            "../reviewer-id",
            "reviewers/reviewer-id",
            "alice@example.com",
            "password=not-an-id",
            "reviewer:secret",
            "reviewer:\ncontrol",
            "C:local-reviewer-file",
        )
        for reviewer_id in unsafe_ids:
            with self.subTest(reviewer_id=reviewer_id):
                payload = valid_record()
                payload["cases"][0]["ground_truth_review"]["submissions"][0][
                    "reviewer_id"
                ] = reviewer_id
                self.assert_invalid(payload, "opaque sanitized reviewer ID")

    def test_unsafe_references_fail_in_submission_adjudication_and_eligibility(self) -> None:
        unsafe_references = (
            "C:/Users/private/coin.jpg",
            "C:relative-private.txt",
            "../private/coin.jpg",
            "https://user:password@example.org/record",
            "file:///tmp/private.jpg",
            "repo:../../private.jpg",
            "repo:password=credential",
            "repo:record\ncontrol",
            "http://example.org/not-https",
            "/absolute/private.jpg",
            "private:collection-photo",
        )
        for reference in unsafe_references:
            with self.subTest(location="submission", reference=reference):
                payload = valid_record()
                payload["cases"][0]["ground_truth_review"]["submissions"][0][
                    "evidence_references"
                ] = [reference]
                self.assert_invalid(payload, "safe durable reference")
            with self.subTest(location="adjudication", reference=reference):
                payload = valid_record()
                track = payload["cases"][0]["action_review"]
                track["submissions"][1]["decision"] = "abstain"
                track["adjudication"] = {
                    "reviewer_id": "adjudicator:action-c",
                    "decision": "identify",
                    "evidence_references": [reference],
                    "rationale": "Synthetic test rationale.",
                }
                self.assert_invalid(payload, "safe durable reference")
            with self.subTest(location="eligibility", reference=reference):
                payload = valid_record()
                payload["cases"][0]["provider_eligibility"]["privacy"][
                    "evidence_references"
                ] = [reference]
                self.assert_invalid(payload, "safe durable reference")

    def test_only_approved_eligibility_requires_evidence(self) -> None:
        payload = valid_record()
        eligibility = payload["cases"][0]["provider_eligibility"]
        eligibility["privacy"] = {"state": "approved", "evidence_references": []}
        self.assert_invalid(payload, "requires supporting evidence")

        payload = valid_record()
        eligibility = payload["cases"][0]["provider_eligibility"]
        eligibility["privacy"] = {"state": "rejected", "evidence_references": []}
        eligibility["licensing"] = {"state": "unresolved", "evidence_references": []}
        record = _validate(payload)
        self.assertFalse(record.cases[0].provider_eligibility.approved)

    def test_rejected_eligibility_is_not_approved(self) -> None:
        payload = valid_record()
        payload["cases"][0]["provider_eligibility"] = _eligibility("rejected")
        record = _validate(payload)
        self.assertFalse(record.cases[0].provider_eligibility.approved)

    def test_missing_eligibility_field_and_unsupported_state_are_rejected(self) -> None:
        payload = valid_record()
        del payload["cases"][0]["provider_eligibility"]["licensing"]
        self.assert_invalid(payload, "missing licensing")
        payload = valid_record()
        payload["cases"][0]["provider_eligibility"]["privacy"]["state"] = "accepted"
        self.assert_invalid(payload, "state is unsupported")
        payload = valid_record()
        payload["cases"][0]["provider_eligibility"]["privacy"]["state"] = []
        self.assert_invalid(payload, "state is unsupported")

    def test_non_string_review_state_is_rejected(self) -> None:
        payload = valid_record()
        payload["cases"][0]["ground_truth_review"]["state"] = []
        self.assert_invalid(payload, "state is unsupported")

    def test_missing_duplicate_and_unsupported_case_records_are_rejected(self) -> None:
        payload = valid_record()
        payload["cases"].pop()
        self.assert_invalid(payload, "missing case-030")
        payload = valid_record()
        payload["cases"][1] = deepcopy(payload["cases"][0])
        self.assert_invalid(payload, "duplicate case record")
        payload = valid_record()
        payload["cases"][-1]["case_id"] = "case-031"
        self.assert_invalid(payload, "unsupported case-031")

    def test_roster_and_specimen_mapping_come_from_supplied_authoring_state(self) -> None:
        source = {
            "cases": [
                {"case_id": "case-101", "specimen_id": "specimen-777"},
                {"case_id": "case-102", "specimen_id": "specimen-777"},
            ]
        }
        payload = valid_record(source)
        record = _validate(payload, source)
        self.assertEqual([case.case_id for case in record.cases], ["case-101", "case-102"])
        self.assertEqual(record.cases[0].specimen_id, record.cases[1].specimen_id)

        payload["cases"][1]["specimen_id"] = "specimen-778"
        self.assert_invalid(
            payload,
            "case-102.specimen_id must be specimen-777",
            source,
        )

    def test_current_repeat_cases_require_separate_execution_records(self) -> None:
        payload = valid_record()
        payload["cases"] = [case for case in payload["cases"] if case["case_id"] != "case-028"]
        self.assert_invalid(payload, "missing case-028")

    def test_malformed_authoring_roster_fails_closed(self) -> None:
        payload = valid_record()
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, "cases must be an array"):
            _validate(payload, {"cases": "invalid"})
        duplicate_source = deepcopy(authoring_state())
        duplicate_source["cases"][1]["case_id"] = duplicate_source["cases"][0]["case_id"]
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, "duplicate authoring case"):
            _validate(payload, duplicate_source)

    def test_extra_fields_are_rejected_at_every_level(self) -> None:
        mutations = [
            lambda payload: payload.update({"generated_at": "never"}),
            lambda payload: payload["cases"][0].update({"candidate_identity": _identity()}),
            lambda payload: payload["cases"][0]["ground_truth_review"].update({"packet": {}}),
            lambda payload: payload["cases"][0]["ground_truth_review"]["submissions"][0].update(
                {"timestamp": "2026-01-01T00:00:00Z"}
            ),
            lambda payload: payload["cases"][0]["provider_eligibility"]["privacy"].update(
                {"reviewer_id": _reviewer(999)}
            ),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                payload = valid_record()
                mutate(payload)
                self.assert_invalid(payload, "invalid fields")

    def test_schema_version_root_and_cases_shape_fail_closed(self) -> None:
        payload = valid_record()
        payload["schema"] = "unsupported-schema"
        self.assert_invalid(payload, "unsupported review execution schema/version")
        payload = valid_record()
        payload["version"] = "2.0.0"
        self.assert_invalid(payload, "unsupported review execution schema/version")
        self.assert_invalid([], "must be an object")
        payload = valid_record()
        payload["cases"] = {}
        self.assert_invalid(payload, "cases must be an array")

    def test_normalized_json_revalidates_directly_constructed_model(self) -> None:
        unchecked = ReviewExecutionRecord(
            schema=REVIEW_EXECUTION_SCHEMA,
            version=REVIEW_EXECUTION_VERSION,
            cases=(),
        )
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, "case roster mismatch"):
            normalized_review_execution_json(unchecked, authoring_state())

    def test_loader_rejects_duplicate_json_keys_and_nonfinite_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "execution.json"
            path.write_text('{"schema":"a","schema":"b"}', encoding="utf-8")
            with self.assertRaisesRegex(DesktopAcceptanceReviewError, "duplicate JSON object key"):
                load_review_execution_record(path, authoring_state())
            path.write_text('{"schema":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(DesktopAcceptanceReviewError, "unsupported JSON constant"):
                load_review_execution_record(path, authoring_state())

    def test_loader_rejects_missing_and_malformed_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            with self.assertRaisesRegex(DesktopAcceptanceReviewError, "cannot read"):
                load_review_execution_record(missing, authoring_state())
            malformed = Path(directory) / "malformed.json"
            malformed.write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(DesktopAcceptanceReviewError, "cannot read"):
                load_review_execution_record(malformed, authoring_state())

    def test_loader_round_trip(self) -> None:
        payload = valid_record()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "execution.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_review_execution_record(path, authoring_state())
        self.assertEqual(loaded, _validate(payload))


if __name__ == "__main__":
    unittest.main()
