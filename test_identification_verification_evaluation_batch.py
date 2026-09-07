import unittest

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
    EvaluationAggregate,
    EvaluationCase,
    EvaluationOutcomeClassification,
)
from identification_specialist import (
    IdentificationSpecialistRequest,
    IdentificationSpecialistResult,
    run_identification_specialist,
)
from identification_verification_evaluation_batch import (
    IdentificationVerificationEvaluationBatchReport,
    compare_identification_batch,
)


def _request(
    case_id: str,
    *,
    eligible: tuple[str, ...] = ("candidate:alpha",),
    evidence: tuple[str, ...] = ("ref:001",),
) -> IdentificationSpecialistRequest:
    return IdentificationSpecialistRequest(
        schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
        case_id=case_id,
        candidate_ids=(
            "candidate:alpha",
            "candidate:beta",
        ),
        eligible_candidate_ids=eligible,
        evidence_refs=evidence,
    )


def _evaluation_case(
    case_id: str,
    *,
    allowed: tuple[str, ...] = ("candidate:alpha",),
    require_abstention: bool = False,
    evidence: tuple[str, ...] = ("ref:001",),
) -> EvaluationCase:
    return EvaluationCase(
        schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
        case_id=case_id,
        allowed_candidate_ids=allowed,
        require_abstention=require_abstention,
        evidence_refs=evidence,
    )


def _normal_item(
    case_id: str,
    *,
    eligible: tuple[str, ...] = ("candidate:alpha",),
    allowed: tuple[str, ...] = ("candidate:alpha",),
    require_abstention: bool = False,
    evidence: tuple[str, ...] = ("ref:001",),
):
    request = _request(
        case_id,
        eligible=eligible,
        evidence=evidence,
    )
    result = run_identification_specialist(request)
    evaluation_case = _evaluation_case(
        case_id,
        allowed=allowed,
        require_abstention=require_abstention,
        evidence=evidence,
    )
    return request, result, evaluation_case


class IdentificationVerificationEvaluationBatchTests(unittest.TestCase):
    def test_mixed_batch_preserves_independent_semantics(self) -> None:
        case_1 = _normal_item(
            "case:001",
            allowed=("candidate:alpha",),
        )

        case_2 = _normal_item(
            "case:002",
            allowed=("candidate:beta",),
        )

        request_3 = _request(
            "case:003",
            eligible=("candidate:alpha",),
        )
        result_3 = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:003",
            candidate_id="candidate:beta",
            abstained=False,
            evidence_refs=("ref:001",),
        )
        evaluation_3 = _evaluation_case(
            "case:003",
            allowed=("candidate:beta",),
        )

        case_4 = _normal_item(
            "case:004",
            eligible=(),
            allowed=(),
            require_abstention=True,
        )

        batch = compare_identification_batch(
            (
                case_1,
                case_2,
                (request_3, result_3, evaluation_3),
                case_4,
            )
        )

        self.assertEqual(len(batch.reports), 4)

        self.assertEqual(
            batch.verifier_accepted,
            3,
        )
        self.assertEqual(
            batch.verifier_rejected,
            1,
        )

        self.assertEqual(
            batch.evaluation_aggregate,
            EvaluationAggregate(
                total=4,
                correct=2,
                incorrect=1,
                abstained=1,
                invalid_or_missing=0,
            ),
        )

        self.assertTrue(
            batch.reports[0].verification.accepted
        )
        self.assertEqual(
            batch.reports[0].evaluation_outcome.classification,
            EvaluationOutcomeClassification.CORRECT,
        )

        self.assertTrue(
            batch.reports[1].verification.accepted
        )
        self.assertEqual(
            batch.reports[1].evaluation_outcome.classification,
            EvaluationOutcomeClassification.INCORRECT,
        )

        self.assertFalse(
            batch.reports[2].verification.accepted
        )
        self.assertEqual(
            batch.reports[2].evaluation_outcome.classification,
            EvaluationOutcomeClassification.CORRECT,
        )

        self.assertTrue(
            batch.reports[3].verification.accepted
        )
        self.assertEqual(
            batch.reports[3].evaluation_outcome.classification,
            EvaluationOutcomeClassification.ABSTAINED,
        )

    def test_input_order_is_preserved_exactly(self) -> None:
        items = (
            _normal_item("case:z"),
            _normal_item("case:a"),
            _normal_item("case:m"),
        )

        batch = compare_identification_batch(items)

        self.assertEqual(
            tuple(
                report.specialist_result.case_id
                for report in batch.reports
            ),
            (
                "case:z",
                "case:a",
                "case:m",
            ),
        )

    def test_empty_batch_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "must not be empty",
        ):
            compare_identification_batch(())

    def test_non_tuple_batch_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            compare_identification_batch(
                []  # type: ignore[arg-type]
            )

    def test_non_tuple_item_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            TypeError,
            r"items\[0\]",
        ):
            compare_identification_batch(
                (
                    object(),  # type: ignore[arg-type]
                )
            )

    def test_wrong_item_length_is_rejected(self) -> None:
        request = _request("case:001")
        result = run_identification_specialist(request)

        with self.assertRaisesRegex(
            ValueError,
            "exactly 3",
        ):
            compare_identification_batch(
                (
                    (request, result),  # type: ignore[arg-type]
                )
            )

    def test_wrong_request_type_is_rejected_cleanly(self) -> None:
        request = _request("case:001")
        result = run_identification_specialist(request)
        evaluation_case = _evaluation_case("case:001")

        with self.assertRaisesRegex(
            TypeError,
            r"items\[0\]\[0\]",
        ):
            compare_identification_batch(
                (
                    (
                        object(),  # type: ignore[arg-type]
                        result,
                        evaluation_case,
                    ),
                )
            )

    def test_wrong_result_type_is_rejected_cleanly(self) -> None:
        request = _request("case:001")
        evaluation_case = _evaluation_case("case:001")

        with self.assertRaisesRegex(
            TypeError,
            r"items\[0\]\[1\]",
        ):
            compare_identification_batch(
                (
                    (
                        request,
                        object(),  # type: ignore[arg-type]
                        evaluation_case,
                    ),
                )
            )

    def test_wrong_evaluation_case_type_is_rejected_cleanly(
        self,
    ) -> None:
        request = _request("case:001")
        result = run_identification_specialist(request)

        with self.assertRaisesRegex(
            TypeError,
            r"items\[0\]\[2\]",
        ):
            compare_identification_batch(
                (
                    (
                        request,
                        result,
                        object(),  # type: ignore[arg-type]
                    ),
                )
            )

    def test_duplicate_case_ids_are_rejected(self) -> None:
        first = _normal_item("case:duplicate")
        second = _normal_item("case:duplicate")

        with self.assertRaisesRegex(
            ValueError,
            "Duplicate batch case_id",
        ):
            compare_identification_batch(
                (
                    first,
                    second,
                )
            )

    def test_request_result_case_mismatch_fails_closed(self) -> None:
        request = _request("case:request")
        result = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id="case:result",
            candidate_id="candidate:alpha",
            abstained=False,
            evidence_refs=("ref:001",),
        )
        evaluation_case = _evaluation_case("case:request")

        with self.assertRaises(ValueError):
            compare_identification_batch(
                (
                    (
                        request,
                        result,
                        evaluation_case,
                    ),
                )
            )

    def test_request_evaluation_case_mismatch_fails_closed(
        self,
    ) -> None:
        request = _request("case:request")
        result = run_identification_specialist(request)
        evaluation_case = _evaluation_case("case:evaluation")

        with self.assertRaises(ValueError):
            compare_identification_batch(
                (
                    (
                        request,
                        result,
                        evaluation_case,
                    ),
                )
            )

    def test_evidence_refs_are_preserved_per_case(self) -> None:
        first_evidence = (
            "ref:a:001",
            "ref:a:002",
        )
        second_evidence = (
            "ref:b:001",
            "ref:b:002",
        )

        batch = compare_identification_batch(
            (
                _normal_item(
                    "case:001",
                    evidence=first_evidence,
                ),
                _normal_item(
                    "case:002",
                    evidence=second_evidence,
                ),
            )
        )

        self.assertEqual(
            batch.reports[0].specialist_result.evidence_refs,
            first_evidence,
        )
        self.assertEqual(
            batch.reports[1].specialist_result.evidence_refs,
            second_evidence,
        )

    def test_authoritative_and_observed_ids_remain_separate(
        self,
    ) -> None:
        batch = compare_identification_batch(
            (
                _normal_item(
                    "case:001",
                    eligible=("candidate:alpha",),
                    allowed=("candidate:beta",),
                ),
            )
        )

        report = batch.reports[0]

        self.assertEqual(
            report.specialist_result.candidate_id,
            "candidate:alpha",
        )
        self.assertEqual(
            report.evaluation_outcome.classification,
            EvaluationOutcomeClassification.INCORRECT,
        )

    def test_verifier_counts_are_not_evaluation_counts(self) -> None:
        batch = compare_identification_batch(
            (
                _normal_item(
                    "case:001",
                    allowed=("candidate:beta",),
                ),
            )
        )

        self.assertEqual(batch.verifier_accepted, 1)
        self.assertEqual(batch.verifier_rejected, 0)

        self.assertEqual(
            batch.evaluation_aggregate.correct,
            0,
        )
        self.assertEqual(
            batch.evaluation_aggregate.incorrect,
            1,
        )

    def test_batch_is_deterministic(self) -> None:
        items = (
            _normal_item("case:001"),
            _normal_item(
                "case:002",
                allowed=("candidate:beta",),
            ),
        )

        first = compare_identification_batch(items)
        second = compare_identification_batch(items)

        self.assertEqual(first, second)

    def test_batch_does_not_mutate_inputs(self) -> None:
        items = (
            _normal_item("case:001"),
            _normal_item("case:002"),
        )

        before = items

        compare_identification_batch(items)

        self.assertEqual(items, before)

    def test_batch_report_validation_rejects_wrong_report_type(
        self,
    ) -> None:
        valid = compare_identification_batch(
            (
                _normal_item("case:001"),
            )
        )

        invalid = IdentificationVerificationEvaluationBatchReport(
            reports=(
                object(),  # type: ignore[arg-type]
            ),
            verifier_accepted=valid.verifier_accepted,
            verifier_rejected=valid.verifier_rejected,
            evaluation_aggregate=valid.evaluation_aggregate,
        )

        with self.assertRaises(TypeError):
            invalid.validate()

    def test_batch_report_validation_rejects_bad_verifier_counts(
        self,
    ) -> None:
        valid = compare_identification_batch(
            (
                _normal_item("case:001"),
            )
        )

        invalid = IdentificationVerificationEvaluationBatchReport(
            reports=valid.reports,
            verifier_accepted=0,
            verifier_rejected=0,
            evaluation_aggregate=valid.evaluation_aggregate,
        )

        with self.assertRaisesRegex(
            ValueError,
            "sum exactly",
        ):
            invalid.validate()

    def test_batch_report_validation_rejects_bad_evaluation_aggregate(
        self,
    ) -> None:
        valid = compare_identification_batch(
            (
                _normal_item("case:001"),
            )
        )

        invalid = IdentificationVerificationEvaluationBatchReport(
            reports=valid.reports,
            verifier_accepted=valid.verifier_accepted,
            verifier_rejected=valid.verifier_rejected,
            evaluation_aggregate=EvaluationAggregate(
                total=1,
                correct=0,
                incorrect=1,
                abstained=0,
                invalid_or_missing=0,
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "does not match",
        ):
            invalid.validate()


if __name__ == "__main__":
    unittest.main()
