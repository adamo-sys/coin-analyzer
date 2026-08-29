from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from capture_import.desktop_acceptance_review import (
    DesktopAcceptanceReviewError,
    EVIDENCE_RESOLUTION_SCHEMA,
    EVIDENCE_RESOLUTION_VERSION,
    ReviewExecutionRecord,
    build_review_progress_report,
    normalized_review_progress_json,
    render_review_progress_report,
    validated_review_progress_dict,
    validate_evidence_resolution_catalog,
    validate_review_execution_record,
)
from capture_import.desktop_acceptance_authoring import DesktopAcceptanceAuthoringError
from tests.test_desktop_acceptance_review import authoring_state, valid_record


_TEST_REPOSITORY = tempfile.TemporaryDirectory()
_TEST_REPOSITORY_ROOT = Path(_TEST_REPOSITORY.name)
_TEST_ATTESTATION = Path(
    "benchmarks/real-world-desktop-v1/reviews/synthetic-attestation.md"
)
(_TEST_REPOSITORY_ROOT / _TEST_ATTESTATION).parent.mkdir(parents=True)
(_TEST_REPOSITORY_ROOT / _TEST_ATTESTATION).write_text(
    "sanitized synthetic attestation\n", encoding="utf-8"
)


def _validated(source: object, payload: object) -> ReviewExecutionRecord:
    return validate_review_execution_record(payload, source)


def _empty_track() -> dict[str, object]:
    return {"state": "unresolved", "submissions": [], "adjudication": None}


def _unresolved_payload(source: object) -> dict[str, object]:
    payload = valid_record(source)
    for case in payload["cases"]:
        case["ground_truth_review"] = _empty_track()
        case["action_review"] = _empty_track()
        for decision in case["provider_eligibility"].values():
            decision["state"] = "unresolved"
            decision["evidence_references"] = []
    return payload


def _ready_payload(source: object) -> dict[str, object]:
    payload = valid_record(source)
    for case, authoring_case in zip(payload["cases"], source["cases"], strict=True):
        for submission in case["ground_truth_review"]["submissions"]:
            submission["decision"] = deepcopy(authoring_case["candidate_identity"])
        for submission in case["action_review"]["submissions"]:
            submission["decision"] = authoring_case["expected_action"]
    return payload


def _all_required_evidence_references(
    source: object, payload: object
) -> tuple[str, ...]:
    references: set[str] = set()
    for authoring_case, execution_case in zip(
        source["cases"], payload["cases"], strict=True
    ):
        provenance = authoring_case["provenance"]["evidence_reference"]
        if isinstance(provenance, str) and provenance.strip():
            references.add(provenance)
        for track_name in ("ground_truth_review", "action_review"):
            track = execution_case[track_name]
            if track["state"] != "complete":
                continue
            for submission in track["submissions"]:
                references.update(submission["evidence_references"])
            if track["adjudication"] is not None:
                references.update(track["adjudication"]["evidence_references"])
        for decision in execution_case["provider_eligibility"].values():
            if decision["state"] == "approved":
                references.update(decision["evidence_references"])
    return tuple(sorted(references))


def _evidence_catalog(source: object, payload: object, *, omit: tuple[str, ...] = ()):
    omitted = set(omit)
    catalog_payload = {
        "schema": EVIDENCE_RESOLUTION_SCHEMA,
        "version": EVIDENCE_RESOLUTION_VERSION,
        "entries": [
            {
                "evidence_reference": reference,
                "resolution_record": _TEST_ATTESTATION.as_posix(),
            }
            for reference in _all_required_evidence_references(source, payload)
            if reference not in omitted
        ],
    }
    return validate_evidence_resolution_catalog(
        catalog_payload, _TEST_REPOSITORY_ROOT
    )


def _report(source: object, payload: object):
    execution = _validated(source, payload)
    catalog = _evidence_catalog(source, payload)
    return (
        build_review_progress_report(
            source, execution, catalog, _TEST_REPOSITORY_ROOT
        ),
        execution,
    )


def _case(report, case_id: str = "case-001"):
    return next(case for case in report.cases if case.case_id == case_id)


def _data(report, source: object, execution: ReviewExecutionRecord):
    catalog = _evidence_catalog(source, execution.as_dict())
    return validated_review_progress_dict(
        report, source, execution, catalog, _TEST_REPOSITORY_ROOT
    )


class DesktopAcceptanceReviewReportingTests(unittest.TestCase):
    def test_all_unresolved_initial_state(self) -> None:
        source = authoring_state()
        report, execution = _report(source, _unresolved_payload(source))
        data = _data(report, source, execution)
        self.assertFalse(report.review_provenance_ready)
        self.assertEqual(data["total_cases"], 30)
        self.assertEqual(data["ground_truth_status_counts"]["unassigned"], 30)
        self.assertEqual(
            data["expected_action_status_counts"]["blocked_by_ground_truth"], 30
        )
        self.assertEqual(
            _case(report).blockers,
            (
                "ground_truth_unassigned",
                "action_blocked_by_ground_truth",
                "privacy_unresolved",
                "licensing_unresolved",
                "provider_authorization_unresolved",
            ),
        )

    def test_partially_completed_ground_truth_awaits_submission(self) -> None:
        source = authoring_state()
        complete = valid_record(source)
        payload = _unresolved_payload(source)
        payload["cases"][0]["ground_truth_review"]["submissions"] = [
            deepcopy(complete["cases"][0]["ground_truth_review"]["submissions"][0])
        ]
        report, execution = _report(source, payload)
        case = _case(report)
        self.assertEqual(case.ground_truth_status, "awaiting_submissions")
        self.assertEqual(case.action_status, "blocked_by_ground_truth")

    def test_ground_truth_disagreement_awaits_adjudication(self) -> None:
        source = authoring_state()
        payload = _unresolved_payload(source)
        submissions = deepcopy(
            valid_record(source)["cases"][0]["ground_truth_review"]["submissions"]
        )
        submissions[1]["decision"]["year"] = "date disputed"
        payload["cases"][0]["ground_truth_review"]["submissions"] = submissions
        report, execution = _report(source, payload)
        case = _case(report)
        self.assertEqual(case.ground_truth_status, "disagreement_awaiting_adjudication")
        self.assertIn("ground_truth_disagreement_awaiting_adjudication", case.blockers)
        self.assertEqual(
            _data(report, source, execution)["adjudication_needed_counts"]["ground_truth"],
            1,
        )

    def test_agreeing_ground_truth_may_remain_explicitly_unresolved(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        payload["cases"][0]["ground_truth_review"]["state"] = "unresolved"
        payload["cases"][0]["action_review"] = _empty_track()
        report, execution = _report(source, payload)
        case = _case(report)
        self.assertEqual(case.ground_truth_status, "unresolved")
        self.assertEqual(case.action_status, "blocked_by_ground_truth")

    def test_completed_ground_truth_leaves_unstarted_action_unassigned(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        payload["cases"][0]["action_review"] = _empty_track()
        report, execution = _report(source, payload)
        case = _case(report)
        self.assertEqual(case.ground_truth_status, "complete")
        self.assertEqual(case.action_status, "unassigned")
        self.assertIn("action_unassigned", case.blockers)

    def test_completed_action_is_reported_complete(self) -> None:
        source = authoring_state()
        report, _ = _report(source, _ready_payload(source))
        self.assertEqual(_case(report).action_status, "complete")

    def test_action_disagreement_awaits_adjudication(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        action = payload["cases"][0]["action_review"]
        action["state"] = "unresolved"
        action["submissions"][0]["decision"] = "identify"
        action["submissions"][1]["decision"] = "abstain"
        action["adjudication"] = None
        report, execution = _report(source, payload)
        case = _case(report)
        self.assertEqual(case.action_status, "disagreement_awaiting_adjudication")
        self.assertEqual(
            _data(report, source, execution)["adjudication_needed_counts"][
                "expected_action"
            ],
            1,
        )

    def test_agreeing_action_may_remain_explicitly_unresolved(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        payload["cases"][0]["action_review"]["state"] = "unresolved"
        report, _ = _report(source, payload)
        self.assertEqual(_case(report).action_status, "unresolved")

    def test_mixed_provider_eligibility_states_are_counted(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        privacy = payload["cases"][0]["provider_eligibility"]["privacy"]
        privacy["state"] = "unresolved"
        privacy["evidence_references"] = []
        licensing = payload["cases"][1]["provider_eligibility"]["licensing"]
        licensing["state"] = "rejected"
        authorization = payload["cases"][2]["provider_eligibility"][
            "provider_authorization"
        ]
        authorization["state"] = "unresolved"
        authorization["evidence_references"] = []
        report, execution = _report(source, payload)
        counts = _data(report, source, execution)["provider_eligibility_state_counts"]
        self.assertEqual(counts["privacy"], {"approved": 29, "rejected": 0, "unresolved": 1})
        self.assertEqual(counts["licensing"], {"approved": 29, "rejected": 1, "unresolved": 0})
        self.assertEqual(
            counts["provider_authorization"],
            {"approved": 29, "rejected": 0, "unresolved": 1},
        )

    def test_rejected_eligibility_remains_blocking(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        privacy = payload["cases"][0]["provider_eligibility"]["privacy"]
        privacy["state"] = "rejected"
        report, _ = _report(source, payload)
        case = _case(report)
        self.assertFalse(case.review_provenance_ready)
        self.assertIn("privacy_rejected", case.blockers)

    def test_each_missing_eligibility_approval_blocks_independently(self) -> None:
        source = authoring_state()
        for field in ("licensing", "provider_authorization"):
            with self.subTest(field=field):
                payload = _ready_payload(source)
                decision = payload["cases"][0]["provider_eligibility"][field]
                decision["state"] = "unresolved"
                decision["evidence_references"] = []
                report, _ = _report(source, payload)
                case = _case(report)
                self.assertFalse(case.review_provenance_ready)
                self.assertEqual(case.blockers, (f"{field}_unresolved",))

    def test_fully_review_provenance_ready_case(self) -> None:
        source = authoring_state()
        report, _ = _report(source, _ready_payload(source))
        case = _case(report)
        self.assertTrue(case.provenance_ready)
        self.assertTrue(case.review_provenance_ready)
        self.assertEqual(case.blockers, ())

    def test_unresolved_provenance_fields_are_named_blockers(self) -> None:
        source = authoring_state()
        source["cases"][0]["provenance"]["ownership_or_source"] = ""
        source["cases"][0]["provenance"]["evidence_reference"] = ""
        report, _ = _report(source, _ready_payload(source))
        case = _case(report)
        self.assertFalse(case.provenance_ready)
        self.assertIn("provenance_ownership_or_source_unresolved", case.blockers)
        self.assertIn("provenance_evidence_unresolved", case.blockers)

    def test_each_missing_provenance_requirement_blocks_independently(self) -> None:
        source = authoring_state()
        for field, blocker in (
            ("ownership_or_source", "provenance_ownership_or_source_unresolved"),
            ("evidence_reference", "provenance_evidence_unresolved"),
        ):
            with self.subTest(field=field):
                altered = deepcopy(source)
                altered["cases"][0]["provenance"][field] = ""
                report, _ = _report(altered, _ready_payload(altered))
                case = _case(report)
                self.assertFalse(case.review_provenance_ready)
                self.assertEqual(case.blockers, (blocker,))

    def test_overall_ready_false_when_any_case_is_blocked(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        payload["cases"][0]["action_review"] = _empty_track()
        report, _ = _report(source, payload)
        self.assertFalse(report.review_provenance_ready)

    def test_overall_ready_true_only_when_every_case_is_ready(self) -> None:
        source = authoring_state()
        report, execution = _report(source, _ready_payload(source))
        self.assertTrue(report.review_provenance_ready)
        data = _data(report, source, execution)
        self.assertEqual(data["ground_truth_status_counts"]["complete"], 30)
        self.assertEqual(data["expected_action_status_counts"]["complete"], 30)
        self.assertEqual(report.aggregate_blockers, ())

    def test_exact_v1_cardinality_is_an_aggregate_readiness_gate(self) -> None:
        for actual in (0, 1, 29, 31):
            with self.subTest(actual=actual):
                source = authoring_state()
                if actual <= 29:
                    source["cases"] = source["cases"][:actual]
                if actual == 31:
                    extra = deepcopy(source["cases"][-1])
                    extra["case_id"] = "case-031"
                    extra["specimen_id"] = "specimen-031"
                    extra["repeated_capture"]["repeated_case_id"] = None
                    source["cases"].append(extra)
                payload = _ready_payload(source)
                report, execution = _report(source, payload)
                data = _data(report, source, execution)
                blocker = f"corpus_case_count_mismatch:expected=30:actual={actual}"
                self.assertEqual(report.aggregate_blockers, (blocker,))
                self.assertEqual(data["aggregate_blockers"], [blocker])
                self.assertFalse(report.review_provenance_ready)

    def test_missing_ground_truth_adjudication_evidence_blocks_readiness(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        track = payload["cases"][0]["ground_truth_review"]
        track["submissions"][1]["decision"]["year"] = "disputed"
        track["adjudication"] = {
            "reviewer_id": "adjudicator:gt-independent",
            "decision": deepcopy(source["cases"][0]["candidate_identity"]),
            "evidence_references": ["repo:gt-adjudication-only"],
            "rationale": "Synthetic adjudication rationale.",
        }
        execution = _validated(source, payload)
        catalog = _evidence_catalog(
            source, payload, omit=("repo:gt-adjudication-only",)
        )
        report = build_review_progress_report(
            source, execution, catalog, _TEST_REPOSITORY_ROOT
        )
        case = _case(report)
        self.assertEqual(case.ground_truth_status, "complete")
        self.assertEqual(
            case.unresolved_evidence.ground_truth,
            ("repo:gt-adjudication-only",),
        )
        self.assertIn("ground_truth_evidence_unresolved", case.blockers)

    def test_missing_action_adjudication_evidence_blocks_readiness(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        track = payload["cases"][0]["action_review"]
        candidate = source["cases"][0]["expected_action"]
        track["submissions"][1]["decision"] = (
            "identify" if candidate == "abstain" else "abstain"
        )
        track["adjudication"] = {
            "reviewer_id": "adjudicator:action-independent",
            "decision": candidate,
            "evidence_references": ["repo:action-adjudication-only"],
            "rationale": "Synthetic adjudication rationale.",
        }
        execution = _validated(source, payload)
        catalog = _evidence_catalog(
            source, payload, omit=("repo:action-adjudication-only",)
        )
        report = build_review_progress_report(
            source, execution, catalog, _TEST_REPOSITORY_ROOT
        )
        case = _case(report)
        self.assertEqual(case.action_status, "complete")
        self.assertEqual(
            case.unresolved_evidence.expected_action,
            ("repo:action-adjudication-only",),
        )
        self.assertIn("expected_action_evidence_unresolved", case.blockers)

    def test_nonapproved_eligibility_evidence_has_no_promotion_authority(self) -> None:
        source = authoring_state()
        for state in ("unresolved", "rejected"):
            with self.subTest(state=state):
                payload = _ready_payload(source)
                decision = payload["cases"][0]["provider_eligibility"]["privacy"]
                retained_reference = "evidence:nonapproved-only"
                decision["evidence_references"] = [retained_reference]
                decision["state"] = state
                report, _ = _report(source, payload)
                case = _case(report)
                self.assertIn(f"privacy_{state}", case.blockers)
                self.assertNotIn("privacy_evidence_unresolved", case.blockers)
                self.assertEqual(case.unresolved_evidence.privacy, ())
                self.assertNotIn(
                    retained_reference,
                    _all_required_evidence_references(source, payload),
                )

    def test_evidence_reuse_does_not_inherit_case_completion(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        reused_reference = payload["cases"][1]["ground_truth_review"][
            "submissions"
        ][0]["evidence_references"][0]
        first_track = payload["cases"][0]["ground_truth_review"]
        first_track["state"] = "unresolved"
        for submission in first_track["submissions"]:
            submission["evidence_references"] = [reused_reference]
        payload["cases"][0]["action_review"] = _empty_track()
        report, _ = _report(source, payload)
        self.assertEqual(_case(report, "case-001").ground_truth_status, "unresolved")
        self.assertFalse(_case(report, "case-001").review_provenance_ready)
        self.assertEqual(_case(report, "case-002").ground_truth_status, "complete")

    def test_missing_resolutions_are_category_diagnostics_and_blockers(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        execution = _validated(source, payload)
        first = payload["cases"][0]
        references = {
            "ground_truth": first["ground_truth_review"]["submissions"][0][
                "evidence_references"
            ][0],
            "expected_action": first["action_review"]["submissions"][0][
                "evidence_references"
            ][0],
            "provenance": source["cases"][0]["provenance"]["evidence_reference"],
            "privacy": first["provider_eligibility"]["privacy"][
                "evidence_references"
            ][0],
            "licensing": first["provider_eligibility"]["licensing"][
                "evidence_references"
            ][0],
            "provider_authorization": first["provider_eligibility"][
                "provider_authorization"
            ]["evidence_references"][0],
        }
        for category, reference in references.items():
            with self.subTest(category=category):
                catalog = _evidence_catalog(source, payload, omit=(reference,))
                report = build_review_progress_report(
                    source, execution, catalog, _TEST_REPOSITORY_ROOT
                )
                case = _case(report)
                self.assertIn(f"{category}_evidence_unresolved", case.blockers)
                self.assertIn(reference, getattr(case.unresolved_evidence, category))
                self.assertFalse(case.review_provenance_ready)
                self.assertFalse(report.review_provenance_ready)

    def test_report_carries_validated_catalog_digest(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        execution = _validated(source, payload)
        catalog = _evidence_catalog(source, payload)
        report = build_review_progress_report(
            source, execution, catalog, _TEST_REPOSITORY_ROOT
        )
        data = validated_review_progress_dict(
            report, source, execution, catalog, _TEST_REPOSITORY_ROOT
        )
        self.assertEqual(report.evidence_catalog_digest, catalog.digest)
        self.assertEqual(data["evidence_catalog_digest"], catalog.digest)

    def test_reconciliation_mismatches_are_named_blockers(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        payload["cases"][0]["ground_truth_review"]["submissions"][0]["decision"]["year"] = "1900"
        payload["cases"][0]["ground_truth_review"]["submissions"][1]["decision"]["year"] = "1900"
        opposite = "identify" if source["cases"][0]["expected_action"] == "abstain" else "abstain"
        for submission in payload["cases"][0]["action_review"]["submissions"]:
            submission["decision"] = opposite
        report, _ = _report(source, payload)
        self.assertEqual(
            _case(report).blockers,
            ("ground_truth_reconciliation_mismatch", "action_reconciliation_mismatch"),
        )

    def test_repeated_cases_are_counted_independently(self) -> None:
        source = authoring_state()
        report, execution = _report(source, _ready_payload(source))
        repeated = [_case(report, case_id) for case_id in ("case-028", "case-029", "case-030")]
        self.assertEqual([case.case_id for case in repeated], ["case-028", "case-029", "case-030"])
        self.assertEqual(_data(report, source, execution)["total_cases"], 30)

    def test_equivalent_input_order_produces_byte_identical_json(self) -> None:
        source_a = authoring_state()
        payload_a = _ready_payload(source_a)
        report_a, execution_a = _report(source_a, payload_a)

        source_b = deepcopy(source_a)
        source_b["cases"].reverse()
        payload_b = deepcopy(payload_a)
        payload_b["cases"].reverse()
        for case in payload_b["cases"]:
            case["ground_truth_review"]["submissions"].reverse()
            case["action_review"]["submissions"].reverse()
        report_b, execution_b = _report(source_b, payload_b)
        catalog_a = _evidence_catalog(source_a, payload_a)
        catalog_b = _evidence_catalog(source_b, payload_b)
        self.assertEqual(
            normalized_review_progress_json(
                report_a, source_a, execution_a, catalog_a, _TEST_REPOSITORY_ROOT
            ),
            normalized_review_progress_json(
                report_b, source_b, execution_b, catalog_b, _TEST_REPOSITORY_ROOT
            ),
        )
        self.assertEqual(
            render_review_progress_report(
                report_a, source_a, execution_a, catalog_a, _TEST_REPOSITORY_ROOT
            ),
            render_review_progress_report(
                report_b, source_b, execution_b, catalog_b, _TEST_REPOSITORY_ROOT
            ),
        )
        self.assertEqual(
            [case.case_id for case in report_b.cases],
            sorted(case.case_id for case in report_b.cases),
        )

    def test_human_report_reflects_the_same_derived_state_as_json(self) -> None:
        source = authoring_state()
        payload = _unresolved_payload(source)
        report, execution = _report(source, payload)
        catalog = _evidence_catalog(source, payload)
        machine = json.loads(
            normalized_review_progress_json(
                report, source, execution, catalog, _TEST_REPOSITORY_ROOT
            )
        )
        human = render_review_progress_report(
            report, source, execution, catalog, _TEST_REPOSITORY_ROOT
        )
        self.assertIn("Overall ready: no", human)
        self.assertIn(f"Total cases: {machine['total_cases']}", human)
        for case in machine["cases"]:
            blockers = ",".join(case["blockers"]) if case["blockers"] else "none"
            readiness = "ready" if case["review_provenance_ready"] else "blocked"
            expected = (
                f"- {case['case_id']} {case['specimen_id']}: {readiness}; "
                f"gt={case['ground_truth_status']}; action={case['action_status']}; "
                f"blockers={blockers}"
            )
            self.assertIn(expected, human)

    def test_malformed_inputs_and_unchecked_report_fail_closed(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        execution = _validated(source, payload)
        catalog = _evidence_catalog(source, payload)
        unchecked_execution = ReviewExecutionRecord(execution.schema, execution.version, ())
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, "case roster mismatch"):
            build_review_progress_report(
                source, unchecked_execution, catalog, _TEST_REPOSITORY_ROOT
            )

        report = build_review_progress_report(
            source, execution, catalog, _TEST_REPOSITORY_ROOT
        )
        self.assertFalse(hasattr(report, "as_dict"))
        self.assertFalse(hasattr(report.cases[0], "as_dict"))
        unchecked_report = replace(report, cases=())
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, "does not match"):
            validated_review_progress_dict(
                unchecked_report,
                source,
                execution,
                catalog,
                _TEST_REPOSITORY_ROOT,
            )
        unchecked_digest = replace(report, evidence_catalog_digest="0" * 64)
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, "does not match"):
            validated_review_progress_dict(
                unchecked_digest,
                source,
                execution,
                catalog,
                _TEST_REPOSITORY_ROOT,
            )

        malformed_source = deepcopy(source)
        del malformed_source["cases"][0]["provenance"]
        with self.assertRaisesRegex(DesktopAcceptanceAuthoringError, "missing fields"):
            build_review_progress_report(
                malformed_source, execution, catalog, _TEST_REPOSITORY_ROOT
            )

    def test_authoring_contract_is_fully_revalidated_before_reporting(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        execution = _validated(source, payload)
        catalog = _evidence_catalog(source, payload)
        mutations = (
            lambda value: value.update({"schema": "unsupported"}),
            lambda value: value.update({"version": "2.0.0"}),
            lambda value: value.pop("stability_relevant_cohorts"),
            lambda value: value["cases"][0].update({"capture": "malformed"}),
            lambda value: value["cases"][0]["candidate_identity"].pop("year"),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                malformed = deepcopy(source)
                mutate(malformed)
                with self.assertRaises(DesktopAcceptanceAuthoringError):
                    build_review_progress_report(
                        malformed, execution, catalog, _TEST_REPOSITORY_ROOT
                    )

        with self.assertRaises(DesktopAcceptanceAuthoringError):
            build_review_progress_report(
                [], execution, catalog, _TEST_REPOSITORY_ROOT
            )

        duplicate = deepcopy(source)
        duplicate["cases"][1]["case_id"] = duplicate["cases"][0]["case_id"]
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, "duplicate authoring case"):
            build_review_progress_report(
                duplicate, execution, catalog, _TEST_REPOSITORY_ROOT
            )

    def test_reporting_does_not_mutate_inputs(self) -> None:
        source = authoring_state()
        payload = _ready_payload(source)
        execution = _validated(source, payload)
        catalog = _evidence_catalog(source, payload)
        source_before = deepcopy(source)
        execution_before = execution.as_dict()
        report = build_review_progress_report(
            source, execution, catalog, _TEST_REPOSITORY_ROOT
        )
        normalized_review_progress_json(
            report, source, execution, catalog, _TEST_REPOSITORY_ROOT
        )
        render_review_progress_report(
            report, source, execution, catalog, _TEST_REPOSITORY_ROOT
        )
        self.assertEqual(source, source_before)
        self.assertEqual(execution.as_dict(), execution_before)


if __name__ == "__main__":
    unittest.main()
