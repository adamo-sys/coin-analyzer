import unittest
from dataclasses import replace

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
)
from identification_specialist import (
    IdentificationSpecialistRequest,
    IdentificationSpecialistResult,
    run_identification_specialist,
)
from identification_specialist_verifier import (
    IdentificationSpecialistVerification,
    verify_identification_specialist_result,
)


def _request(
    *,
    candidates: tuple[str, ...] = (
        "candidate:alpha",
        "candidate:beta",
    ),
    eligible: tuple[str, ...] = ("candidate:alpha",),
    evidence: tuple[str, ...] = (
        "ref:001",
        "ref:002",
    ),
) -> IdentificationSpecialistRequest:
    return IdentificationSpecialistRequest(
        schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
        case_id="case:specialist:001",
        candidate_ids=candidates,
        eligible_candidate_ids=eligible,
        evidence_refs=evidence,
    )


class IdentificationSpecialistVerifierTests(unittest.TestCase):
    def test_valid_single_candidate_selection_is_accepted(self) -> None:
        request = _request()
        result = run_identification_specialist(request)

        verification = verify_identification_specialist_result(
            request,
            result,
        )

        self.assertTrue(verification.accepted)
        self.assertEqual(verification.reason_codes, ())

    def test_valid_zero_candidate_abstention_is_accepted(self) -> None:
        request = _request(eligible=())
        result = run_identification_specialist(request)

        verification = verify_identification_specialist_result(
            request,
            result,
        )

        self.assertTrue(verification.accepted)
        self.assertEqual(verification.reason_codes, ())

    def test_valid_ambiguous_candidate_abstention_is_accepted(self) -> None:
        request = _request(
            eligible=(
                "candidate:alpha",
                "candidate:beta",
            )
        )
        result = run_identification_specialist(request)

        verification = verify_identification_specialist_result(
            request,
            result,
        )

        self.assertTrue(verification.accepted)

    def test_case_id_mismatch_is_rejected(self) -> None:
        request = _request()
        result = run_identification_specialist(request)
        tampered = replace(
            result,
            case_id="case:specialist:999",
        )

        verification = verify_identification_specialist_result(
            request,
            tampered,
        )

        self.assertFalse(verification.accepted)
        self.assertIn(
            "case_id_mismatch",
            verification.reason_codes,
        )

    def test_evidence_ref_mismatch_is_rejected(self) -> None:
        request = _request()
        result = run_identification_specialist(request)
        tampered = replace(
            result,
            evidence_refs=("ref:999",),
        )

        verification = verify_identification_specialist_result(
            request,
            tampered,
        )

        self.assertFalse(verification.accepted)
        self.assertEqual(
            verification.reason_codes,
            ("evidence_refs_mismatch",),
        )

    def test_unauthorized_candidate_is_rejected(self) -> None:
        request = _request()
        tampered = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=request.case_id,
            candidate_id="candidate:gamma",
            abstained=False,
            evidence_refs=request.evidence_refs,
        )

        verification = verify_identification_specialist_result(
            request,
            tampered,
        )

        self.assertFalse(verification.accepted)
        self.assertIn(
            "candidate_not_authorized",
            verification.reason_codes,
        )
        self.assertIn(
            "candidate_does_not_match_sole_eligible",
            verification.reason_codes,
        )

    def test_wrong_authorized_candidate_is_rejected(self) -> None:
        request = _request()
        tampered = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=request.case_id,
            candidate_id="candidate:beta",
            abstained=False,
            evidence_refs=request.evidence_refs,
        )

        verification = verify_identification_specialist_result(
            request,
            tampered,
        )

        self.assertFalse(verification.accepted)
        self.assertEqual(
            verification.reason_codes,
            ("candidate_does_not_match_sole_eligible",),
        )

    def test_abstention_with_one_eligible_candidate_is_rejected(self) -> None:
        request = _request()
        tampered = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=request.case_id,
            candidate_id=None,
            abstained=True,
            evidence_refs=request.evidence_refs,
        )

        verification = verify_identification_specialist_result(
            request,
            tampered,
        )

        self.assertFalse(verification.accepted)
        self.assertEqual(
            verification.reason_codes,
            ("unexpected_abstention",),
        )

    def test_selection_with_zero_eligible_candidates_is_rejected(self) -> None:
        request = _request(eligible=())
        tampered = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=request.case_id,
            candidate_id="candidate:alpha",
            abstained=False,
            evidence_refs=request.evidence_refs,
        )

        verification = verify_identification_specialist_result(
            request,
            tampered,
        )

        self.assertFalse(verification.accepted)
        self.assertEqual(
            verification.reason_codes,
            ("selection_when_abstention_required",),
        )

    def test_selection_with_multiple_eligible_candidates_is_rejected(
        self,
    ) -> None:
        request = _request(
            eligible=(
                "candidate:alpha",
                "candidate:beta",
            )
        )
        tampered = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=request.case_id,
            candidate_id="candidate:alpha",
            abstained=False,
            evidence_refs=request.evidence_refs,
        )

        verification = verify_identification_specialist_result(
            request,
            tampered,
        )

        self.assertFalse(verification.accepted)
        self.assertEqual(
            verification.reason_codes,
            ("selection_when_abstention_required",),
        )

    def test_multiple_rejection_reasons_are_sorted_and_unique(self) -> None:
        request = _request()
        tampered = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:specialist:999",
            candidate_id="candidate:gamma",
            abstained=False,
            evidence_refs=("ref:999",),
        )

        verification = verify_identification_specialist_result(
            request,
            tampered,
        )

        self.assertFalse(verification.accepted)
        self.assertEqual(
            verification.reason_codes,
            tuple(sorted(set(verification.reason_codes))),
        )
        self.assertEqual(
            verification.reason_codes,
            (
                "candidate_does_not_match_sole_eligible",
                "candidate_not_authorized",
                "case_id_mismatch",
                "evidence_refs_mismatch",
            ),
        )

    def test_verifier_does_not_mutate_request_or_result(self) -> None:
        request = _request()
        result = run_identification_specialist(request)

        request_before = request
        result_before = result

        verify_identification_specialist_result(
            request,
            result,
        )

        self.assertEqual(request, request_before)
        self.assertEqual(result, result_before)

    def test_verifier_is_deterministic(self) -> None:
        request = _request()
        result = run_identification_specialist(request)

        first = verify_identification_specialist_result(
            request,
            result,
        )
        second = verify_identification_specialist_result(
            request,
            result,
        )

        self.assertEqual(first, second)

    def test_wrong_request_type_fails_closed(self) -> None:
        request = _request()
        result = run_identification_specialist(request)

        with self.assertRaises(TypeError):
            verify_identification_specialist_result(
                object(),  # type: ignore[arg-type]
                result,
            )

    def test_wrong_result_type_fails_closed(self) -> None:
        request = _request()

        with self.assertRaises(TypeError):
            verify_identification_specialist_result(
                request,
                object(),  # type: ignore[arg-type]
            )

    def test_invalid_request_fails_closed_before_verification(self) -> None:
        request = _request(
            candidates=(
                "candidate:beta",
                "candidate:alpha",
            ),
            eligible=("candidate:alpha",),
        )
        result = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:specialist:001",
            candidate_id="candidate:alpha",
            abstained=False,
            evidence_refs=(
                "ref:001",
                "ref:002",
            ),
        )

        with self.assertRaises(ValueError):
            verify_identification_specialist_result(
                request,
                result,
            )

    def test_invalid_result_fails_closed_before_verification(self) -> None:
        request = _request()
        invalid = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=request.case_id,
            candidate_id="candidate:alpha",
            abstained=True,
            evidence_refs=request.evidence_refs,
        )

        with self.assertRaises(ValueError):
            verify_identification_specialist_result(
                request,
                invalid,
            )

    def test_verification_contract_rejects_reasons_on_accept(self) -> None:
        verification = IdentificationSpecialistVerification(
            accepted=True,
            reason_codes=("unexpected_abstention",),
        )

        with self.assertRaises(ValueError):
            verification.validate()

    def test_verification_contract_requires_reason_on_reject(self) -> None:
        verification = IdentificationSpecialistVerification(
            accepted=False,
            reason_codes=(),
        )

        with self.assertRaises(ValueError):
            verification.validate()

    def test_verification_contract_requires_sorted_reasons(self) -> None:
        verification = IdentificationSpecialistVerification(
            accepted=False,
            reason_codes=(
                "z_reason",
                "a_reason",
            ),
        )

        with self.assertRaisesRegex(ValueError, "sorted"):
            verification.validate()

    def test_verification_contract_rejects_duplicate_reasons(self) -> None:
        verification = IdentificationSpecialistVerification(
            accepted=False,
            reason_codes=(
                "reason",
                "reason",
            ),
        )

        with self.assertRaisesRegex(ValueError, "unique"):
            verification.validate()


if __name__ == "__main__":
    unittest.main()
