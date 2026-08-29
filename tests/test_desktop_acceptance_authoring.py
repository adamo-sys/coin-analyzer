from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from capture_import.desktop_acceptance_authoring import (
    AUTHORING_SCHEMA,
    AUTHORING_VERSION,
    DESKTOP_ACCEPTANCE_V1_CASE_COUNT,
    DesktopAcceptanceAuthoringError,
    evaluate_readiness,
    prepare_for_freeze,
    readiness_json,
    validate_authoring_plan,
)
from capture_import.desktop_acceptance_set import (
    DesktopAcceptanceManifestError,
    load_desktop_acceptance_manifest,
)


def _identity(case_number: int) -> dict[str, str]:
    return {
        "country": "CAN",
        "denomination": "5 cents",
        "year": str(1900 + case_number),
    }


def _review(decision: object, prefix: str) -> dict[str, object]:
    return {
        "state": "complete",
        "reviewers": [
            {
                "reviewer_id": f"{prefix}-reviewer-a",
                "decision": deepcopy(decision),
                "evidence_reference": f"evidence:{prefix}:a",
            },
            {
                "reviewer_id": f"{prefix}-reviewer-b",
                "decision": deepcopy(decision),
                "evidence_reference": f"evidence:{prefix}:b",
            },
        ],
        "adjudication": None,
    }


def _capture(case_number: int) -> dict[str, object]:
    return {
        "status": "complete",
        "obverse_path": f"authoring/case-{case_number:03d}-obverse.jpg",
        "reverse_path": f"authoring/case-{case_number:03d}-reverse.jpg",
        "capture_conditions": {
            "background": "neutral-mat",
            "device": "test-camera",
            "distance": "20cm",
            "lighting": "diffuse",
            "orientation": f"rotation-{case_number}",
        },
    }


def ready_plan() -> dict[str, object]:
    cases: list[dict[str, object]] = []
    # 24 distinct specimens. Cases 25-30 are second captures of specimens 1-6.
    for number in range(1, 31):
        specimen_number = number if number <= 24 else number - 24
        action = "identify" if number <= 24 else "abstain"
        identity = _identity(specimen_number)
        stability = 7 <= number <= 15 or number == 25
        cohorts = ["baseline"]
        if action == "abstain":
            cohorts.append("abstain")
        case = {
            "case_id": f"case-{number:03d}",
            "specimen_id": f"specimen-{specimen_number:03d}",
            "expected_action": action,
            "candidate_identity": identity,
            "cohorts": cohorts,
            "provenance": {
                "ownership_or_source": "synthetic-test-fixture",
                "evidence_reference": f"fixture:provenance:{number}",
                "notes": "synthetic only",
            },
            "provider_eligibility": {
                "privacy": "approved",
                "licensing": "approved",
                "provider_authorization": "approved",
            },
            "ground_truth_review": _review(identity, f"gt-{number}"),
            "action_review": _review(action, f"action-{number}"),
            "capture": _capture(number),
            "repeated_capture": {
                "repeated_case_id": (
                    f"case-{number + 24:03d}" if number <= 6
                    else f"case-{number - 24:03d}" if number >= 25
                    else None
                ),
                "capture_difference_fields": ["orientation"] if number <= 6 or number >= 25 else [],
                "capture_difference_rationale": (
                    "Independent recapture with changed orientation."
                    if number <= 6 or number >= 25 else ""
                ),
            },
            "near_duplicate_review": {
                "status": "complete",
                "evidence_reference": f"fixture:near-duplicate:{number}",
            },
            "stability": stability,
            "notes": "synthetic test case",
        }
        cases.append(case)
    return {
        "schema": AUTHORING_SCHEMA,
        "version": AUTHORING_VERSION,
        "stability_relevant_cohorts": ["baseline", "abstain"],
        "cases": cases,
    }


class DesktopAcceptanceAuthoringTests(unittest.TestCase):
    def test_in_memory_validation_reuses_shape_contract_without_mutation(self) -> None:
        payload = ready_plan()
        before = deepcopy(payload)
        self.assertIs(validate_authoring_plan(payload), payload)
        self.assertEqual(payload, before)

        malformed = deepcopy(payload)
        malformed["schema"] = "unsupported"
        with self.assertRaisesRegex(DesktopAcceptanceAuthoringError, "schema/version"):
            validate_authoring_plan(malformed)

    def test_empty_authoring_state_is_not_ready(self) -> None:
        payload = {
            "schema": AUTHORING_SCHEMA,
            "version": AUTHORING_VERSION,
            "stability_relevant_cohorts": ["baseline"],
            "cases": [],
        }
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertEqual(report.summary["cases"], 0)
        self.assertTrue(
            any(
                f"exactly {DESKTOP_ACCEPTANCE_V1_CASE_COUNT}" in item
                for item in report.blockers
            )
        )

    def test_unresolved_provider_authorization_fails_closed(self) -> None:
        payload = ready_plan()
        payload["cases"][0]["provider_eligibility"]["provider_authorization"] = "unresolved"
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("provider_authorization is not approved" in item for item in report.blockers))

    def test_unresolved_privacy_and_licensing_fail_closed(self) -> None:
        payload = ready_plan()
        payload["cases"][0]["provider_eligibility"]["privacy"] = "unresolved"
        payload["cases"][1]["provider_eligibility"]["licensing"] = "unresolved"
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("privacy is not approved" in item for item in report.blockers))
        self.assertTrue(any("licensing is not approved" in item for item in report.blockers))

    def test_missing_reviews_fail_closed(self) -> None:
        payload = ready_plan()
        payload["cases"][0]["ground_truth_review"]["state"] = "unresolved"
        payload["cases"][1]["action_review"]["state"] = "unresolved"
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("ground_truth_review is incomplete" in item for item in report.blockers))
        self.assertTrue(any("action_review is incomplete" in item for item in report.blockers))

    def test_disagreement_without_adjudication_fails_closed(self) -> None:
        payload = ready_plan()
        payload["cases"][0]["action_review"]["reviewers"][1]["decision"] = "abstain"
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("disagreement requires adjudication" in item for item in report.blockers))

    def test_missing_photography_fails_closed(self) -> None:
        payload = ready_plan()
        payload["cases"][0]["capture"]["status"] = "incomplete"
        payload["cases"][0]["capture"]["reverse_path"] = None
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("case-001.capture is incomplete" in item for item in report.blockers))

    def test_invalid_24_6_composition_fails(self) -> None:
        payload = ready_plan()
        payload["cases"][23]["expected_action"] = "abstain"
        payload["cases"][23]["action_review"] = _review("abstain", "changed-action")
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("24 identify and 6 abstain" in item for item in report.blockers))

    def test_too_few_specimens_fails(self) -> None:
        payload = ready_plan()
        payload["cases"][23]["specimen_id"] = "specimen-023"
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("at least 24 specimens" in item for item in report.blockers))

    def test_more_than_two_cases_per_specimen_fails(self) -> None:
        payload = ready_plan()
        payload["cases"][23]["specimen_id"] = "specimen-001"
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("specimen-001 appears in 3 cases" in item for item in report.blockers))

    def test_invalid_stability_subset_fails(self) -> None:
        payload = ready_plan()
        payload["cases"][6]["stability"] = False
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("exactly 10 cases" in item for item in report.blockers))

    def test_stability_subset_requires_distinct_specimens(self) -> None:
        payload = ready_plan()
        payload["cases"][24]["specimen_id"] = "specimen-007"
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("stability subset must use distinct specimens" in item for item in report.blockers))

    def test_repeated_specimen_requires_different_capture_conditions(self) -> None:
        payload = ready_plan()
        payload["cases"][24]["capture"]["capture_conditions"] = deepcopy(
            payload["cases"][0]["capture"]["capture_conditions"]
        )
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("materially different capture conditions" in item for item in report.blockers))

    def test_singleton_case_cannot_declare_repetition(self) -> None:
        payload = ready_plan()
        payload["cases"][6]["repeated_capture"]["repeated_case_id"] = "case-008"
        payload["cases"][6]["repeated_capture"]["capture_difference_fields"] = ["orientation"]
        payload["cases"][6]["repeated_capture"]["capture_difference_rationale"] = "Invalid singleton declaration."
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("singleton case cannot declare repetition" in item for item in report.blockers))

    def test_repeated_specimen_requires_reciprocal_case_ids(self) -> None:
        payload = ready_plan()
        payload["cases"][24]["repeated_capture"]["repeated_case_id"] = "case-002"
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("reciprocal repeated_case_id" in item for item in report.blockers))

    def test_repeated_specimen_requires_exact_difference_fields(self) -> None:
        payload = ready_plan()
        payload["cases"][24]["repeated_capture"]["capture_difference_fields"] = ["lighting"]
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("must exactly match differing capture conditions" in item for item in report.blockers))

    def test_repeated_specimen_requires_difference_fields_in_contract_order(self) -> None:
        payload = ready_plan()
        payload["cases"][0]["capture"]["capture_conditions"]["lighting"] = "hard"
        payload["cases"][24]["repeated_capture"]["capture_difference_fields"] = ["orientation", "lighting"]
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("must exactly match differing capture conditions" in item for item in report.blockers))

    def test_repeated_specimen_requires_difference_rationale(self) -> None:
        payload = ready_plan()
        payload["cases"][24]["repeated_capture"]["capture_difference_rationale"] = ""
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("capture difference rationale" in item for item in report.blockers))

    def test_incomplete_abstain_ground_truth_fails(self) -> None:
        payload = ready_plan()
        payload["cases"][24]["candidate_identity"]["year"] = None
        report = evaluate_readiness(payload)
        self.assertFalse(report.ready_for_freeze)
        self.assertTrue(any("abstain case requires complete known identity" in item for item in report.blockers))

    def test_fully_ready_synthetic_plan(self) -> None:
        report = evaluate_readiness(ready_plan())
        self.assertTrue(report.ready_for_freeze, report.blockers)
        self.assertEqual(report.blockers, ())
        self.assertEqual(report.summary["cases"], 30)
        self.assertEqual(report.summary["specimens"], 24)
        self.assertEqual(report.summary["stability_cases"], 10)

    def test_readiness_json_is_deterministic(self) -> None:
        payload = ready_plan()
        first = readiness_json(payload)
        second = readiness_json(deepcopy(payload))
        self.assertEqual(first, second)
        decoded = json.loads(first)
        self.assertTrue(decoded["ready_for_freeze"])

    def test_export_rejected_when_not_ready(self) -> None:
        payload = ready_plan()
        payload["cases"][0]["provider_eligibility"]["licensing"] = "unresolved"
        with self.assertRaises(DesktopAcceptanceAuthoringError):
            prepare_for_freeze(payload)

    def test_export_succeeds_only_for_ready_plan_without_fabricated_digests(self) -> None:
        prepared = prepare_for_freeze(ready_plan())
        self.assertEqual(prepared["schema"], "coin-analyzer-desktop-acceptance-freeze-preparation")
        self.assertFalse(prepared["benchmark_execution_approved"])
        self.assertEqual(len(prepared["cases"]), 30)
        text = json.dumps(prepared, sort_keys=True)
        self.assertNotIn("sha256\"", text)
        self.assertTrue(any("SHA-256" in step for step in prepared["required_next_steps"]))

    def test_authoring_object_is_rejected_by_strict_frozen_loader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authoring.json"
            path.write_text(json.dumps(ready_plan()), encoding="utf-8")
            with self.assertRaises(DesktopAcceptanceManifestError):
                load_desktop_acceptance_manifest(path)


if __name__ == "__main__":
    unittest.main()
