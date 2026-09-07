import unittest

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
)
from identification_specialist import (
    IdentificationSpecialistRequest,
    IdentificationSpecialistResult,
    run_identification_specialist,
)


def _request(
    *,
    candidates: tuple[str, ...] = (
        "candidate:alpha",
        "candidate:beta",
    ),
    eligible: tuple[str, ...] = ("candidate:alpha",),
    evidence: tuple[str, ...] = ("ref:001",),
) -> IdentificationSpecialistRequest:
    return IdentificationSpecialistRequest(
        schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
        case_id="case:specialist:001",
        candidate_ids=candidates,
        eligible_candidate_ids=eligible,
        evidence_refs=evidence,
    )


class IdentificationSpecialistTests(unittest.TestCase):
    def test_exactly_one_eligible_candidate_is_selected(self) -> None:
        result = run_identification_specialist(_request())

        self.assertEqual(result.candidate_id, "candidate:alpha")
        self.assertFalse(result.abstained)

    def test_zero_eligible_candidates_abstains(self) -> None:
        result = run_identification_specialist(
            _request(eligible=())
        )

        self.assertIsNone(result.candidate_id)
        self.assertTrue(result.abstained)

    def test_multiple_eligible_candidates_abstain(self) -> None:
        result = run_identification_specialist(
            _request(
                eligible=(
                    "candidate:alpha",
                    "candidate:beta",
                )
            )
        )

        self.assertIsNone(result.candidate_id)
        self.assertTrue(result.abstained)

    def test_selected_candidate_identity_is_preserved_verbatim(self) -> None:
        candidate = "candidate:explicit-authority-009"

        result = run_identification_specialist(
            _request(
                candidates=(candidate,),
                eligible=(candidate,),
            )
        )

        self.assertEqual(result.candidate_id, candidate)

    def test_evidence_refs_are_preserved_verbatim(self) -> None:
        evidence = (
            "ref:ocr:001",
            "ref:photo:002",
        )

        result = run_identification_specialist(
            _request(evidence=evidence)
        )

        self.assertEqual(result.evidence_refs, evidence)

    def test_abstention_preserves_evidence_refs(self) -> None:
        evidence = (
            "ref:ocr:001",
            "ref:photo:002",
        )

        result = run_identification_specialist(
            _request(
                eligible=(),
                evidence=evidence,
            )
        )

        self.assertTrue(result.abstained)
        self.assertEqual(result.evidence_refs, evidence)

    def test_candidate_ids_must_not_be_empty(self) -> None:
        with self.assertRaises(ValueError):
            run_identification_specialist(
                _request(
                    candidates=(),
                    eligible=(),
                )
            )

    def test_candidate_ids_must_be_sorted(self) -> None:
        with self.assertRaisesRegex(ValueError, "sorted"):
            run_identification_specialist(
                _request(
                    candidates=(
                        "candidate:beta",
                        "candidate:alpha",
                    ),
                    eligible=("candidate:alpha",),
                )
            )

    def test_candidate_ids_must_be_unique(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicates"):
            run_identification_specialist(
                _request(
                    candidates=(
                        "candidate:alpha",
                        "candidate:alpha",
                    ),
                    eligible=("candidate:alpha",),
                )
            )

    def test_eligible_candidate_ids_must_be_sorted(self) -> None:
        with self.assertRaisesRegex(ValueError, "eligible.*sorted"):
            run_identification_specialist(
                _request(
                    eligible=(
                        "candidate:beta",
                        "candidate:alpha",
                    )
                )
            )

    def test_eligible_candidate_ids_must_be_unique(self) -> None:
        with self.assertRaisesRegex(ValueError, "eligible.*unique"):
            run_identification_specialist(
                _request(
                    eligible=(
                        "candidate:alpha",
                        "candidate:alpha",
                    )
                )
            )

    def test_eligible_candidate_must_be_authorized_candidate(self) -> None:
        with self.assertRaisesRegex(ValueError, "subset"):
            run_identification_specialist(
                _request(
                    eligible=("candidate:unknown",)
                )
            )

    def test_evidence_refs_must_be_sorted(self) -> None:
        with self.assertRaisesRegex(ValueError, "sorted"):
            run_identification_specialist(
                _request(
                    evidence=(
                        "ref:002",
                        "ref:001",
                    )
                )
            )

    def test_evidence_refs_must_be_unique(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicates"):
            run_identification_specialist(
                _request(
                    evidence=(
                        "ref:001",
                        "ref:001",
                    )
                )
            )

    def test_invalid_schema_version_fails_closed(self) -> None:
        request = IdentificationSpecialistRequest(
            schema_version="unsupported",
            case_id="case:specialist:001",
            candidate_ids=("candidate:alpha",),
            eligible_candidate_ids=("candidate:alpha",),
        )

        with self.assertRaises(ValueError):
            run_identification_specialist(request)

    def test_invalid_request_type_fails_closed(self) -> None:
        with self.assertRaises(TypeError):
            run_identification_specialist(object())  # type: ignore[arg-type]

    def test_result_rejects_candidate_and_abstention_together(self) -> None:
        result = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:specialist:001",
            candidate_id="candidate:alpha",
            abstained=True,
        )

        with self.assertRaises(ValueError):
            result.validate()

    def test_result_rejects_missing_candidate_without_abstention(self) -> None:
        result = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:specialist:001",
            candidate_id=None,
            abstained=False,
        )

        with self.assertRaises(ValueError):
            result.validate()

    def test_policy_is_deterministic(self) -> None:
        request = _request(
            evidence=(
                "ref:001",
                "ref:002",
            )
        )

        first = run_identification_specialist(request)
        second = run_identification_specialist(request)

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
