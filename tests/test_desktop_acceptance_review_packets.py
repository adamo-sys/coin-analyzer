from __future__ import annotations

from copy import deepcopy
import json
import unittest

from capture_import.desktop_acceptance_review import (
    ACTION_TRACK,
    GROUND_TRUTH_INSTRUCTIONS,
    GROUND_TRUTH_TRACK,
    IDENTITY_FIELDS,
    REVIEW_PACKET_SCHEMA,
    REVIEW_PACKET_VERSION,
    DesktopAcceptanceReviewError,
    GroundTruthReviewerPacket,
    generate_action_packet,
    generate_ground_truth_packet,
    normalized_reviewer_packet_json,
    validate_review_execution_record,
    validate_reviewer_packet,
)
from tests.test_desktop_acceptance_review import authoring_state, valid_record


def _execution(source: object | None = None, payload: object | None = None):
    authoring = source if source is not None else authoring_state()
    execution_payload = payload if payload is not None else valid_record(authoring)
    return validate_review_execution_record(execution_payload, authoring)


def _gt_packet(source: object | None = None, case_id: str = "case-001"):
    authoring = source if source is not None else authoring_state()
    return generate_ground_truth_packet(
        authoring,
        case_id,
        "reviewer:gt-alpha",
        [
            f"inventory:S{case_id[-3:]}",
            f"benchmarks/real-world-desktop-v1/reviews/{case_id}-evidence.md",
        ],
    )


def _action_packet(source: object | None = None, execution=None, case_id: str = "case-001"):
    authoring = source if source is not None else authoring_state()
    record = execution if execution is not None else _execution(authoring)
    return generate_action_packet(
        authoring,
        record,
        case_id,
        "reviewer:action-alpha",
        [
            "benchmarks/real-world-desktop-v1/canonicalization-policy-v1.json",
            "policy:frozen-v1-domain",
        ],
    )


class DesktopAcceptanceReviewPacketTests(unittest.TestCase):
    def test_ground_truth_packet_is_deterministic_and_minimal(self) -> None:
        source = authoring_state()
        first = _gt_packet(source)
        second = _gt_packet(deepcopy(source))
        first_json = normalized_reviewer_packet_json(first, source)
        second_json = normalized_reviewer_packet_json(second, deepcopy(source))
        self.assertEqual(first_json, second_json)
        decoded = json.loads(first_json)
        self.assertEqual(
            set(decoded),
            {
                "schema",
                "version",
                "track",
                "case_id",
                "specimen_id",
                "reviewer_id",
                "evidence_references",
                "identity_fields",
                "instructions",
            },
        )
        self.assertEqual(decoded["track"], GROUND_TRUTH_TRACK)
        self.assertEqual(decoded["identity_fields"], list(IDENTITY_FIELDS))

    def test_entire_ground_truth_serialization_has_no_answer_or_peer_fields(self) -> None:
        source = authoring_state()
        packet = _gt_packet(source)
        serialized = normalized_reviewer_packet_json(packet, source)
        decoded = json.loads(serialized)
        for forbidden_field in (
            "candidate_identity",
            "expected_action",
            "peer_reviewer",
            "submission",
            "adjudication",
        ):
            self.assertNotIn(forbidden_field, decoded)

    def test_ground_truth_accepts_candidate_like_text_in_opaque_references(self) -> None:
        source = authoring_state()
        candidate = source["cases"][0]["candidate_identity"]
        compact_denomination = candidate["denomination"].replace(" ", "")
        references = [
            f"policy:provider-terms-{candidate['year']}-review",
            f"https://example.test/{candidate['country']}/provider-terms",
            f"inventory:S001-{compact_denomination}-reference",
        ]
        packet = generate_ground_truth_packet(
            source,
            "case-001",
            "reviewer:gt-alpha",
            references,
        )
        self.assertEqual(packet.evidence_references, tuple(sorted(references)))

    def test_ground_truth_packet_cannot_accept_peer_or_adjudication_fields(self) -> None:
        source = authoring_state()
        payload = _gt_packet(source).as_dict()
        for field, value in (
            ("candidate_identity", {"country": "hidden"}),
            ("expected_action", "hidden"),
            ("peer_submission", {"decision": "hidden"}),
            ("adjudication", {"decision": "hidden"}),
        ):
            with self.subTest(field=field):
                malformed = deepcopy(payload)
                malformed[field] = value
                with self.assertRaisesRegex(DesktopAcceptanceReviewError, "invalid fields"):
                    validate_reviewer_packet(malformed, source)

    def test_action_packet_is_deterministic_after_completed_ground_truth(self) -> None:
        source = authoring_state()
        execution = _execution(source)
        first = _action_packet(source, execution)
        second = generate_action_packet(
            deepcopy(source),
            execution,
            "case-001",
            "reviewer:action-alpha",
            [
                "policy:frozen-v1-domain",
                "benchmarks/real-world-desktop-v1/canonicalization-policy-v1.json",
            ],
        )
        first_json = normalized_reviewer_packet_json(first, source, execution)
        second_json = normalized_reviewer_packet_json(second, deepcopy(source), execution)
        self.assertEqual(first_json, second_json)
        decoded = json.loads(first_json)
        self.assertEqual(decoded["track"], ACTION_TRACK)
        self.assertEqual(
            decoded["resolved_identity"],
            execution.cases[0].ground_truth_review.submissions[0].decision.as_dict(),
        )

    def test_action_packet_rejected_before_ground_truth_is_complete(self) -> None:
        source = authoring_state()
        payload = valid_record(source)
        case = payload["cases"][0]
        case["ground_truth_review"]["state"] = "unresolved"
        case["action_review"] = {
            "state": "unresolved",
            "submissions": [],
            "adjudication": None,
        }
        execution = _execution(source, payload)
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, "must be complete"):
            _action_packet(source, execution)

    def test_action_packet_uses_resolved_gt_not_roster_candidate(self) -> None:
        source = authoring_state()
        payload = valid_record(source)
        resolved = {
            "country": "Independent jurisdiction",
            "denomination": "7 units",
            "year": "date uncertain",
        }
        for submission in payload["cases"][0]["ground_truth_review"]["submissions"]:
            submission["decision"] = deepcopy(resolved)
        execution = _execution(source, payload)
        packet = _action_packet(source, execution)
        self.assertEqual(packet.resolved_identity.as_dict(), resolved)
        decoded = json.loads(normalized_reviewer_packet_json(packet, source, execution))
        self.assertNotIn("expected_action", decoded)
        self.assertNotEqual(
            decoded["resolved_identity"], source["cases"][0]["candidate_identity"]
        )

    def test_action_packet_uses_ground_truth_adjudication_resolution(self) -> None:
        source = authoring_state()
        payload = valid_record(source)
        track = payload["cases"][0]["ground_truth_review"]
        track["submissions"][1]["decision"]["year"] = "date uncertain"
        adjudicated = {
            "country": "Adjudicated jurisdiction",
            "denomination": "3 units",
            "year": "resolved date",
        }
        track["adjudication"] = {
            "reviewer_id": "adjudicator:gt-c",
            "decision": adjudicated,
            "evidence_references": ["repo:adjudication-evidence"],
            "rationale": "The durable record resolves the disagreement.",
        }
        execution = _execution(source, payload)
        packet = _action_packet(source, execution)
        self.assertEqual(packet.resolved_identity.as_dict(), adjudicated)

    def test_action_serialization_excludes_peer_and_adjudication_data(self) -> None:
        source = authoring_state()
        payload = valid_record(source)
        track = payload["cases"][0]["action_review"]
        track["submissions"][1]["decision"] = "abstain"
        track["adjudication"] = {
            "reviewer_id": "adjudicator:action-omega",
            "decision": "identify",
            "evidence_references": ["repo:action-peer-evidence"],
            "rationale": "SECRET ACTION RATIONALE",
        }
        execution = _execution(source, payload)
        packet = _action_packet(source, execution)
        serialized = normalized_reviewer_packet_json(packet, source, execution)
        for submission in execution.cases[0].action_review.submissions:
            self.assertNotIn(submission.reviewer_id, serialized)
        self.assertNotIn("adjudicator:action-omega", serialized)
        self.assertNotIn("SECRET ACTION RATIONALE", serialized)
        self.assertNotIn("repo:action-peer-evidence", serialized)

    def test_action_accepts_domain_reference_with_action_vocabulary(self) -> None:
        source = authoring_state()
        execution = _execution(source)
        packet = generate_action_packet(
            source,
            execution,
            "case-001",
            "reviewer:action-alpha",
            ["policy:identify-abstain-v1"],
        )
        self.assertEqual(packet.domain_references, ("policy:identify-abstain-v1",))

    def test_action_packet_cannot_accept_candidate_or_peer_fields(self) -> None:
        source = authoring_state()
        execution = _execution(source)
        payload = _action_packet(source, execution).as_dict()
        for field, value in (
            ("expected_action", source["cases"][0]["expected_action"]),
            ("peer_submission", {"decision": "identify"}),
            ("adjudication", {"decision": "abstain"}),
        ):
            with self.subTest(field=field):
                malformed = deepcopy(payload)
                malformed[field] = value
                with self.assertRaisesRegex(DesktopAcceptanceReviewError, "invalid fields"):
                    validate_reviewer_packet(malformed, source, execution)

    def test_reference_order_does_not_change_packet_bytes(self) -> None:
        source = authoring_state()
        refs = ["inventory:S001", "repo:evidence-alpha", "repo:evidence-beta"]
        first = generate_ground_truth_packet(source, "case-001", "reviewer:gt-alpha", refs)
        second = generate_ground_truth_packet(
            deepcopy(source), "case-001", "reviewer:gt-alpha", list(reversed(refs))
        )
        self.assertEqual(
            normalized_reviewer_packet_json(first, source),
            normalized_reviewer_packet_json(second, source),
        )

    def test_evidence_reuse_does_not_reuse_case_or_decision_state(self) -> None:
        source = authoring_state()
        shared = ["inventory:S006", "repo:shared-specimen-evidence"]
        original = generate_ground_truth_packet(
            source, "case-006", "reviewer:gt-alpha", shared
        )
        repeat = generate_ground_truth_packet(
            source, "case-028", "reviewer:gt-alpha", shared
        )
        self.assertEqual(original.specimen_id, repeat.specimen_id)
        self.assertNotEqual(original.case_id, repeat.case_id)
        self.assertEqual(original.evidence_references, repeat.evidence_references)
        self.assertNotEqual(
            normalized_reviewer_packet_json(original, source),
            normalized_reviewer_packet_json(repeat, source),
        )

    def test_cases_028_to_030_each_receive_independent_case_packet(self) -> None:
        source = authoring_state()
        packets = [
            generate_ground_truth_packet(
                source,
                f"case-{number:03d}",
                "reviewer:repeat-alpha",
                [f"inventory:S{specimen:03d}"],
            )
            for number, specimen in ((28, 6), (29, 11), (30, 12))
        ]
        self.assertEqual([packet.case_id for packet in packets], ["case-028", "case-029", "case-030"])
        self.assertEqual(
            [packet.specimen_id for packet in packets],
            ["specimen-006", "specimen-011", "specimen-012"],
        )
        serialized = {normalized_reviewer_packet_json(packet, source) for packet in packets}
        self.assertEqual(len(serialized), 3)

    def test_unsafe_and_malformed_packet_inputs_fail_closed(self) -> None:
        source = authoring_state()
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, "safe durable reference"):
            generate_ground_truth_packet(
                source, "case-001", "reviewer:gt-alpha", ["C:/private/coin.jpg"]
            )
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, "opaque sanitized reviewer ID"):
            generate_ground_truth_packet(
                source, "case-001", "alice@example.com", ["inventory:S001"]
            )
        payload = _gt_packet(source).as_dict()
        payload["specimen_id"] = "specimen-999"
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, "does not match authoring"):
            validate_reviewer_packet(payload, source)

    def test_directly_constructed_packet_is_revalidated_before_serialization(self) -> None:
        source = authoring_state()
        malformed = GroundTruthReviewerPacket(
            REVIEW_PACKET_SCHEMA,
            REVIEW_PACKET_VERSION,
            GROUND_TRUTH_TRACK,
            "case-001",
            "specimen-999",
            "reviewer:gt-alpha",
            ("inventory:S001",),
            IDENTITY_FIELDS,
            GROUND_TRUTH_INSTRUCTIONS,
        )
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, "does not match authoring"):
            normalized_reviewer_packet_json(malformed, source)

    def test_inputs_remain_unchanged(self) -> None:
        source = authoring_state()
        source_before = deepcopy(source)
        execution = _execution(source)
        execution_before = execution.as_dict()
        refs = ["repo:evidence-beta", "repo:evidence-alpha"]
        refs_before = list(refs)
        generate_ground_truth_packet(source, "case-001", "reviewer:gt-alpha", refs)
        generate_action_packet(
            source,
            execution,
            "case-001",
            "reviewer:action-alpha",
            ["policy:frozen-v1-domain"],
        )
        self.assertEqual(source, source_before)
        self.assertEqual(execution.as_dict(), execution_before)
        self.assertEqual(refs, refs_before)


if __name__ == "__main__":
    unittest.main()
