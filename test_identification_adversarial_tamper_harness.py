import unittest

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
    EvaluationCase,
    EvaluationOutcomeClassification,
)
from identification_adversarial_tamper_harness import (
    IdentificationTamperDefinition,
    IdentificationTamperHarnessReport,
    IdentificationTamperKind,
    run_identification_tamper_harness,
)
from identification_specialist import (
    IdentificationSpecialistRequest,
    run_identification_specialist,
)


CASE_ID = "case:tamper:001"


def _request(
    *,
    eligible: tuple[str, ...] = ("candidate:alpha",),
    evidence: tuple[str, ...] = ("ref:001",),
) -> IdentificationSpecialistRequest:
    return IdentificationSpecialistRequest(
        schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
        case_id=CASE_ID,
        candidate_ids=(
            "candidate:alpha",
            "candidate:beta",
        ),
        eligible_candidate_ids=eligible,
        evidence_refs=evidence,
    )


def _case(
    *,
    allowed: tuple[str, ...] = ("candidate:alpha",),
    require_abstention: bool = False,
    evidence: tuple[str, ...] = ("ref:001",),
) -> EvaluationCase:
    return EvaluationCase(
        schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
        case_id=CASE_ID,
        allowed_candidate_ids=allowed,
        require_abstention=require_abstention,
        evidence_refs=evidence,
    )


class IdentificationAdversarialTamperHarnessTests(
    unittest.TestCase
):
    def test_wrong_authorized_candidate_is_rejected_by_verifier(
        self,
    ) -> None:
        request = _request()
        base = run_identification_specialist(request)

        report = run_identification_tamper_harness(
            request,
            base,
            _case(allowed=("candidate:beta",)),
            (
                IdentificationTamperDefinition(
                    name="wrong-authorized",
                    kind=IdentificationTamperKind.CANDIDATE,
                    candidate_id="candidate:beta",
                ),
            ),
        )

        observation = report.observations[0]

        self.assertFalse(
            observation.verification.accepted
        )
        self.assertEqual(
            observation.verification.reason_codes,
            (
                "candidate_does_not_match_sole_eligible",
            ),
        )

        self.assertFalse(
            observation.comparison_rejected
        )
        self.assertEqual(
            observation.evaluation_outcome.classification,
            EvaluationOutcomeClassification.CORRECT,
        )

    def test_unauthorized_candidate_is_rejected_by_verifier(
        self,
    ) -> None:
        request = _request()
        base = run_identification_specialist(request)

        report = run_identification_tamper_harness(
            request,
            base,
            _case(allowed=("candidate:alpha",)),
            (
                IdentificationTamperDefinition(
                    name="unauthorized",
                    kind=IdentificationTamperKind.CANDIDATE,
                    candidate_id="candidate:gamma",
                ),
            ),
        )

        observation = report.observations[0]

        self.assertFalse(
            observation.verification.accepted
        )
        self.assertEqual(
            observation.verification.reason_codes,
            (
                "candidate_does_not_match_sole_eligible",
                "candidate_not_authorized",
            ),
        )

        self.assertEqual(
            observation.evaluation_outcome.classification,
            EvaluationOutcomeClassification.INCORRECT,
        )

    def test_evidence_tamper_is_rejected_by_verifier(
        self,
    ) -> None:
        request = _request(
            evidence=("ref:001",)
        )
        base = run_identification_specialist(request)

        report = run_identification_tamper_harness(
            request,
            base,
            _case(
                allowed=("candidate:alpha",),
                evidence=("ref:001",),
            ),
            (
                IdentificationTamperDefinition(
                    name="evidence-tamper",
                    kind=IdentificationTamperKind.EVIDENCE_REFS,
                    evidence_refs=("ref:999",),
                ),
            ),
        )

        observation = report.observations[0]

        self.assertFalse(
            observation.verification.accepted
        )
        self.assertEqual(
            observation.verification.reason_codes,
            ("evidence_refs_mismatch",),
        )

        self.assertFalse(
            observation.comparison_rejected
        )
        self.assertEqual(
            observation.evaluation_outcome.classification,
            EvaluationOutcomeClassification.CORRECT,
        )
        self.assertEqual(
            observation.evaluation_outcome.evidence_refs,
            ("ref:999",),
        )

    def test_case_id_tamper_fails_closed_at_comparison_seam(
        self,
    ) -> None:
        request = _request()
        base = run_identification_specialist(request)

        report = run_identification_tamper_harness(
            request,
            base,
            _case(),
            (
                IdentificationTamperDefinition(
                    name="case-id-tamper",
                    kind=IdentificationTamperKind.CASE_ID,
                    case_id="case:tamper:999",
                ),
            ),
        )

        observation = report.observations[0]

        self.assertFalse(
            observation.verification.accepted
        )
        self.assertEqual(
            observation.verification.reason_codes,
            ("case_id_mismatch",),
        )

        self.assertTrue(
            observation.comparison_rejected
        )
        self.assertIsNone(
            observation.evaluation_outcome
        )
        self.assertEqual(
            observation.comparison_rejection_code,
            "evaluation_case_result_case_id_mismatch",
        )

    def test_forced_abstention_is_rejected_when_one_is_eligible(
        self,
    ) -> None:
        request = _request(
            eligible=("candidate:alpha",)
        )
        base = run_identification_specialist(request)

        report = run_identification_tamper_harness(
            request,
            base,
            _case(
                allowed=("candidate:alpha",),
            ),
            (
                IdentificationTamperDefinition(
                    name="forced-abstention",
                    kind=IdentificationTamperKind.ABSTAIN,
                ),
            ),
        )

        observation = report.observations[0]

        self.assertFalse(
            observation.verification.accepted
        )
        self.assertEqual(
            observation.verification.reason_codes,
            ("unexpected_abstention",),
        )
        self.assertEqual(
            observation.evaluation_outcome.classification,
            EvaluationOutcomeClassification.ABSTAINED,
        )

    def test_forced_selection_is_rejected_when_abstention_required(
        self,
    ) -> None:
        request = _request(
            eligible=()
        )
        base = run_identification_specialist(request)

        evaluation_case = _case(
            allowed=(),
            require_abstention=True,
        )

        report = run_identification_tamper_harness(
            request,
            base,
            evaluation_case,
            (
                IdentificationTamperDefinition(
                    name="forced-selection",
                    kind=IdentificationTamperKind.SELECT,
                    candidate_id="candidate:alpha",
                ),
            ),
        )

        observation = report.observations[0]

        self.assertFalse(
            observation.verification.accepted
        )
        self.assertEqual(
            observation.verification.reason_codes,
            ("selection_when_abstention_required",),
        )
        self.assertEqual(
            observation.evaluation_outcome.classification,
            EvaluationOutcomeClassification.INCORRECT,
        )

    def test_order_is_preserved_exactly(self) -> None:
        request = _request()
        base = run_identification_specialist(request)

        definitions = (
            IdentificationTamperDefinition(
                name="first",
                kind=IdentificationTamperKind.CANDIDATE,
                candidate_id="candidate:beta",
            ),
            IdentificationTamperDefinition(
                name="second",
                kind=IdentificationTamperKind.EVIDENCE_REFS,
                evidence_refs=("ref:999",),
            ),
            IdentificationTamperDefinition(
                name="third",
                kind=IdentificationTamperKind.ABSTAIN,
            ),
        )

        report = run_identification_tamper_harness(
            request,
            base,
            _case(),
            definitions,
        )

        self.assertEqual(
            tuple(
                observation.name
                for observation in report.observations
            ),
            ("first", "second", "third"),
        )

    def test_reason_codes_remain_sorted_and_deterministic(
        self,
    ) -> None:
        request = _request()
        base = run_identification_specialist(request)

        definition = IdentificationTamperDefinition(
            name="unauthorized",
            kind=IdentificationTamperKind.CANDIDATE,
            candidate_id="candidate:gamma",
        )

        first = run_identification_tamper_harness(
            request,
            base,
            _case(),
            (definition,),
        )
        second = run_identification_tamper_harness(
            request,
            base,
            _case(),
            (definition,),
        )

        self.assertEqual(first, second)

        reasons = (
            first.observations[0]
            .verification.reason_codes
        )

        self.assertEqual(
            reasons,
            tuple(sorted(reasons)),
        )
        self.assertEqual(
            len(reasons),
            len(set(reasons)),
        )

    def test_harness_does_not_mutate_inputs(self) -> None:
        request = _request()
        base = run_identification_specialist(request)
        evaluation_case = _case()
        definitions = (
            IdentificationTamperDefinition(
                name="tamper",
                kind=IdentificationTamperKind.ABSTAIN,
            ),
        )

        before = (
            request,
            base,
            evaluation_case,
            definitions,
        )

        run_identification_tamper_harness(
            request,
            base,
            evaluation_case,
            definitions,
        )

        self.assertEqual(
            (
                request,
                base,
                evaluation_case,
                definitions,
            ),
            before,
        )

    def test_empty_definitions_are_rejected(self) -> None:
        request = _request()
        base = run_identification_specialist(request)

        with self.assertRaisesRegex(
            ValueError,
            "definitions must not be empty",
        ):
            run_identification_tamper_harness(
                request,
                base,
                _case(),
                (),
            )

    def test_non_tuple_definitions_are_rejected(self) -> None:
        request = _request()
        base = run_identification_specialist(request)

        with self.assertRaises(TypeError):
            run_identification_tamper_harness(
                request,
                base,
                _case(),
                [],  # type: ignore[arg-type]
            )

    def test_duplicate_tamper_names_are_rejected(self) -> None:
        request = _request()
        base = run_identification_specialist(request)

        definitions = (
            IdentificationTamperDefinition(
                name="duplicate",
                kind=IdentificationTamperKind.ABSTAIN,
            ),
            IdentificationTamperDefinition(
                name="duplicate",
                kind=IdentificationTamperKind.CANDIDATE,
                candidate_id="candidate:beta",
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "Duplicate tamper name",
        ):
            run_identification_tamper_harness(
                request,
                base,
                _case(),
                definitions,
            )

    def test_wrong_definition_type_is_rejected_cleanly(
        self,
    ) -> None:
        request = _request()
        base = run_identification_specialist(request)

        with self.assertRaisesRegex(
            TypeError,
            r"definitions\[0\]",
        ):
            run_identification_tamper_harness(
                request,
                base,
                _case(),
                (
                    object(),  # type: ignore[arg-type]
                ),
            )

    def test_candidate_tamper_requires_candidate_id(self) -> None:
        definition = IdentificationTamperDefinition(
            name="invalid",
            kind=IdentificationTamperKind.CANDIDATE,
        )

        with self.assertRaisesRegex(
            ValueError,
            "requires candidate_id",
        ):
            definition.validate()

    def test_case_tamper_requires_case_id(self) -> None:
        definition = IdentificationTamperDefinition(
            name="invalid",
            kind=IdentificationTamperKind.CASE_ID,
        )

        with self.assertRaisesRegex(
            ValueError,
            "requires case_id",
        ):
            definition.validate()

    def test_evidence_tamper_requires_sorted_refs(self) -> None:
        definition = IdentificationTamperDefinition(
            name="invalid",
            kind=IdentificationTamperKind.EVIDENCE_REFS,
            evidence_refs=(
                "ref:z",
                "ref:a",
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "sorted",
        ):
            definition.validate()

    def test_malformed_base_request_fails_closed(self) -> None:
        request = IdentificationSpecialistRequest(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=CASE_ID,
            candidate_ids=(
                "candidate:beta",
                "candidate:alpha",
            ),
            eligible_candidate_ids=("candidate:alpha",),
            evidence_refs=("ref:001",),
        )

        valid_request = _request()
        base = run_identification_specialist(valid_request)

        with self.assertRaises(ValueError):
            run_identification_tamper_harness(
                request,
                base,
                _case(),
                (
                    IdentificationTamperDefinition(
                        name="tamper",
                        kind=IdentificationTamperKind.ABSTAIN,
                    ),
                ),
            )

    def test_base_triple_must_be_valid_before_tampering(
        self,
    ) -> None:
        request = _request()
        base = run_identification_specialist(request)

        wrong_case = EvaluationCase(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:wrong",
            allowed_candidate_ids=("candidate:alpha",),
            require_abstention=False,
            evidence_refs=("ref:001",),
        )

        with self.assertRaises(ValueError):
            run_identification_tamper_harness(
                request,
                base,
                wrong_case,
                (
                    IdentificationTamperDefinition(
                        name="tamper",
                        kind=IdentificationTamperKind.ABSTAIN,
                    ),
                ),
            )

    def test_report_contract_rejects_empty_observations(
        self,
    ) -> None:
        report = IdentificationTamperHarnessReport(
            observations=(),
        )

        with self.assertRaisesRegex(
            ValueError,
            "must not be empty",
        ):
            report.validate()


if __name__ == "__main__":
    unittest.main()
