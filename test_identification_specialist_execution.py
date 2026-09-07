"""Synthetic-only contract and composition tests for specialist execution."""

import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from unittest.mock import Mock, patch

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
    EvaluationCase,
    EvaluationOutcomeClassification as Classification,
)
from identification_specialist import (
    IdentificationSpecialistRequest,
    run_identification_specialist,
)
from identification_specialist_execution import (
    DETERMINISTIC_IDENTIFICATION_EXECUTOR as DETERMINISTIC,
    IdentificationSpecialistExecutor,
    execute_and_compare_identification,
    execute_identification_specialist,
)
from identification_specialist_verifier import IdentificationSpecialistVerification
from identification_verification_evaluation_report import (
    compare_identification_verification_and_evaluation,
)
from identification_verification_evaluation_batch import compare_identification_batch


class IdentificationSpecialistExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = IdentificationSpecialistRequest(
            CURRENT_AI_EVALUATION_SCHEMA_VERSION, "case:synthetic:1",
            ("candidate:a", "candidate:b"), ("candidate:a",),
            ("ref:synthetic:1", "ref:synthetic:2"),
        )
        self.case = EvaluationCase(
            CURRENT_AI_EVALUATION_SCHEMA_VERSION, self.request.case_id,
            ("candidate:a",), evidence_refs=("ref:independent:truth",),
        )
        self.result = run_identification_specialist(self.request)

    def report(self, result=None, case=None, request=None):
        return execute_and_compare_identification(
            self.request if request is None else request,
            IdentificationSpecialistExecutor(
                "synthetic-v1", Mock(return_value=self.result if result is None else result),
            ),
            self.case if case is None else case,
        )

    def assert_rejected_before_comparison(self, output, exception):
        callback = Mock(return_value=output)
        with patch(
            "identification_specialist_execution.compare_identification_verification_and_evaluation"
        ) as comparison:
            with self.assertRaises(exception):
                execute_and_compare_identification(
                    self.request,
                    IdentificationSpecialistExecutor("synthetic-v1", callback),
                    self.case,
                )
            comparison.assert_not_called()
        callback.assert_called_once_with(self.request)

    def test_deterministic_adapter_reuses_existing_function(self):
        self.assertIs(DETERMINISTIC.execute, run_identification_specialist)
        for eligible in ((), ("candidate:a",), self.request.candidate_ids):
            with self.subTest(eligible=eligible):
                request = replace(self.request, eligible_candidate_ids=eligible)
                record = execute_identification_specialist(request, DETERMINISTIC)
                self.assertEqual(record.specialist_result, run_identification_specialist(request))
                record.validate(request)

    def test_stable_explicit_provenance(self):
        record = execute_identification_specialist(self.request, DETERMINISTIC)
        self.assertEqual(record.executor_id, "deterministic-identification-v1")
        self.assertEqual(
            set(record.__dataclass_fields__), {"executor_id", "specialist_result"},
        )

    def test_repeated_records_and_reports_are_equal(self):
        self.assertEqual(
            execute_identification_specialist(self.request, DETERMINISTIC),
            execute_identification_specialist(self.request, DETERMINISTIC),
        )
        self.assertEqual(
            execute_and_compare_identification(self.request, DETERMINISTIC, self.case),
            execute_and_compare_identification(self.request, DETERMINISTIC, self.case),
        )

    def test_records_reports_and_descriptor_are_frozen_and_slotted(self):
        report = self.report()
        for value, field in (
            (report, "execution"), (report.execution, "executor_id"),
            (report.execution.specialist_result, "candidate_id"),
            (DETERMINISTIC, "executor_id"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, field, None)
                self.assertFalse(hasattr(value, "__dict__"))

    def test_inputs_not_mutated_and_exact_result_preserved(self):
        before = deepcopy((self.request, self.case, self.result))
        report = self.report()
        report.validate(self.request, self.case)
        self.assertEqual((self.request, self.case, self.result), before)
        self.assertIs(report.execution.specialist_result, self.result)
        self.assertIs(report.comparison.specialist_result, self.result)
        self.assertIs(report.execution.specialist_result.evidence_refs, self.request.evidence_refs)

    def test_injected_callable_used_once_with_original_request_only(self):
        callback = Mock(return_value=self.result)
        report = execute_and_compare_identification(
            self.request, IdentificationSpecialistExecutor("custom-v2", callback), self.case,
        )
        report.validate(self.request, self.case)
        callback.assert_called_once_with(self.request)
        self.assertIs(callback.call_args.args[0], self.request)
        self.assertEqual(report.execution.executor_id, "custom-v2")

    def test_policy_valid_correct(self):
        report = self.report()
        self.assertTrue(report.comparison.verification.accepted)
        self.assertEqual(report.comparison.evaluation_outcome.classification, Classification.CORRECT)

    def test_policy_valid_incorrect_and_truth_remains_separate(self):
        case = replace(self.case, allowed_candidate_ids=("candidate:b",))
        report = self.report(case=case)
        self.assertTrue(report.comparison.verification.accepted)
        self.assertEqual(report.comparison.evaluation_outcome.classification, Classification.INCORRECT)
        self.assertEqual(case.allowed_candidate_ids, ("candidate:b",))
        self.assertEqual(report.execution.specialist_result.candidate_id, "candidate:a")

    def test_wrong_authorized_candidate_reaches_verifier_and_can_be_correct(self):
        result = replace(self.result, candidate_id="candidate:b")
        case = replace(self.case, allowed_candidate_ids=("candidate:b",))
        report = self.report(result=result, case=case)
        self.assertIs(report.execution.specialist_result, result)
        self.assertEqual(report.comparison.verification.reason_codes,
                         ("candidate_does_not_match_sole_eligible",))
        self.assertEqual(report.comparison.evaluation_outcome.classification, Classification.CORRECT)

    def test_policy_invalid_can_be_incorrect(self):
        report = self.report(result=replace(self.result, candidate_id="candidate:b"))
        self.assertFalse(report.comparison.verification.accepted)
        self.assertEqual(report.comparison.evaluation_outcome.classification, Classification.INCORRECT)

    def test_unauthorized_candidate_is_not_repaired_or_manufactured(self):
        result = replace(self.result, candidate_id="candidate:caller-supplied-outsider")
        case = replace(self.case, allowed_candidate_ids=(result.candidate_id,))
        report = self.report(result=result, case=case)
        self.assertIs(report.execution.specialist_result, result)
        self.assertIn("candidate_not_authorized", report.comparison.verification.reason_codes)
        self.assertEqual(report.comparison.evaluation_outcome.classification, Classification.CORRECT)

    def test_forced_abstention_remains_explicit_and_is_policy_rejected(self):
        result = replace(self.result, candidate_id=None, abstained=True)
        report = self.report(result=result)
        self.assertEqual(report.comparison.verification.reason_codes, ("unexpected_abstention",))
        self.assertEqual(report.comparison.evaluation_outcome.classification, Classification.ABSTAINED)
        self.assertIsNone(report.execution.specialist_result.candidate_id)

    def test_forced_selection_reaches_verifier(self):
        for eligible in ((), self.request.candidate_ids):
            with self.subTest(eligible=eligible):
                request = replace(self.request, eligible_candidate_ids=eligible)
                report = self.report(request=request)
                self.assertEqual(report.comparison.verification.reason_codes,
                                 ("selection_when_abstention_required",))
                self.assertEqual(report.comparison.evaluation_outcome.classification, Classification.CORRECT)

    def test_deterministic_abstention_never_infers_truth_candidate(self):
        for eligible in ((), self.request.candidate_ids):
            with self.subTest(eligible=eligible):
                request = replace(self.request, eligible_candidate_ids=eligible)
                report = execute_and_compare_identification(request, DETERMINISTIC, self.case)
                self.assertTrue(report.comparison.verification.accepted)
                self.assertIsNone(report.execution.specialist_result.candidate_id)
                self.assertEqual(report.comparison.evaluation_outcome.classification, Classification.ABSTAINED)

    def test_wrong_return_types_fail_before_comparison(self):
        for output in (None, {}, self.request, "candidate:a", object()):
            with self.subTest(output=type(output)):
                self.assert_rejected_before_comparison(output, TypeError)

    def test_malformed_results_fail_before_comparison(self):
        for changes in (
            {"schema_version": "unsupported"}, {"case_id": " "},
            {"candidate_id": None}, {"candidate_id": " "}, {"candidate_id": 42},
            {"abstained": True}, {"abstained": 1},
            {"evidence_refs": ["ref:1"]}, {"evidence_refs": ("",)},
            {"evidence_refs": ("ref:z", "ref:a")},
            {"evidence_refs": ("ref:a", "ref:a")},
        ):
            with self.subTest(changes=changes):
                self.assert_rejected_before_comparison(replace(self.result, **changes), (TypeError, ValueError))

    def test_case_identity_mismatch_fails_before_comparison(self):
        self.assert_rejected_before_comparison(replace(self.result, case_id="case:other"), ValueError)

    def test_valid_but_incompatible_evidence_fails_before_comparison(self):
        for refs in ((), ("ref:other",), ("ref:synthetic:1",),
                     self.request.evidence_refs + ("ref:synthetic:3",)):
            with self.subTest(refs=refs):
                self.assert_rejected_before_comparison(replace(self.result, evidence_refs=refs), ValueError)

    def test_matching_empty_evidence_is_valid(self):
        request = replace(self.request, evidence_refs=())
        record = execute_identification_specialist(request, DETERMINISTIC)
        self.assertEqual(record.specialist_result.evidence_refs, ())

    def test_invalid_requests_do_not_invoke_executor(self):
        for request in (object(), replace(self.request, eligible_candidate_ids=("unknown",)),
                        replace(self.request, candidate_ids=())):
            callback = Mock()
            with self.subTest(request=request), self.assertRaises((TypeError, ValueError)):
                execute_identification_specialist(request, IdentificationSpecialistExecutor("test", callback))
            callback.assert_not_called()

    def test_invalid_evaluation_inputs_do_not_invoke_executor(self):
        for case in (object(), replace(self.case, case_id="other"),
                     replace(self.case, allowed_candidate_ids=())):
            callback = Mock()
            with self.subTest(case=case), self.assertRaises((TypeError, ValueError)):
                execute_and_compare_identification(
                    self.request, IdentificationSpecialistExecutor("test", callback), case,
                )
            callback.assert_not_called()

    def test_invalid_descriptors_fail_before_invocation(self):
        with self.assertRaises(TypeError):
            execute_identification_specialist(self.request, object())
        with self.assertRaises(TypeError):
            execute_identification_specialist(self.request, IdentificationSpecialistExecutor("test", None))
        for identifier in (None, 1, "", " ", "has space", "path/label", "unicode-é", "x" * 129):
            callback = Mock()
            with self.subTest(identifier=identifier), self.assertRaises((TypeError, ValueError)):
                execute_identification_specialist(
                    self.request, IdentificationSpecialistExecutor(identifier, callback),
                )
            callback.assert_not_called()

    def test_identifier_length_boundary_preserved_without_normalization(self):
        identifier = "A_.-" + "x" * 124
        record = execute_identification_specialist(
            self.request, IdentificationSpecialistExecutor(identifier, Mock(return_value=self.result)),
        )
        self.assertEqual(record.executor_id, identifier)

    def test_executor_failure_propagates_without_retry_or_comparison(self):
        error = RuntimeError("synthetic failure")
        callback = Mock(side_effect=error)
        with patch("identification_specialist_execution.compare_identification_verification_and_evaluation") as compare:
            with self.assertRaises(RuntimeError) as caught:
                execute_and_compare_identification(
                    self.request, IdentificationSpecialistExecutor("test", callback), self.case,
                )
            self.assertIs(caught.exception, error)
            compare.assert_not_called()
        callback.assert_called_once()

    def test_existing_comparison_and_batch_semantics_unchanged(self):
        report = self.report()
        expected = compare_identification_verification_and_evaluation(self.request, self.result, self.case)
        self.assertEqual(report.comparison, expected)
        batch = compare_identification_batch(((self.request, report.execution.specialist_result, self.case),))
        self.assertEqual(batch.reports, (expected,))
        self.assertEqual(batch.verifier_accepted, 1)
        self.assertEqual(batch.evaluation_aggregate.correct, 1)

    def test_report_validator_rejects_forged_verifier(self):
        report = self.report()
        forged = replace(report.comparison, verification=IdentificationSpecialistVerification(False, ("fabricated",)))
        with self.assertRaisesRegex(ValueError, "comparison does not match"):
            replace(report, comparison=forged).validate(self.request, self.case)

    def test_report_validator_rejects_forged_evaluation(self):
        report = self.report()
        outcome = replace(report.comparison.evaluation_outcome,
                          classification=Classification.INCORRECT, reason_codes=("candidate_not_allowed",))
        forged = replace(report.comparison, evaluation_outcome=outcome)
        with self.assertRaisesRegex(ValueError, "comparison does not match"):
            replace(report, comparison=forged).validate(self.request, self.case)

    def test_report_validator_rejects_different_stored_result(self):
        report = self.report()
        forged = replace(report.comparison, specialist_result=replace(self.result, candidate_id="candidate:b"))
        with self.assertRaisesRegex(ValueError, "comparison does not match"):
            replace(report, comparison=forged).validate(self.request, self.case)

    def test_report_validator_rejects_malformed_components(self):
        report = self.report()
        for field in ("execution", "comparison"):
            with self.subTest(field=field), self.assertRaises(TypeError):
                replace(report, **{field: object()}).validate(self.request, self.case)
        for changes in ({"executor_id": ""}, {"specialist_result": object()},
                        {"specialist_result": replace(self.result, evidence_refs=())}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(report.execution, **changes).validate(self.request)

    def test_report_validator_uses_supplied_authoritative_truth(self):
        report = self.report()
        with self.assertRaisesRegex(ValueError, "comparison does not match"):
            report.validate(self.request, replace(self.case, allowed_candidate_ids=("candidate:b",)))


if __name__ == "__main__":
    unittest.main()
