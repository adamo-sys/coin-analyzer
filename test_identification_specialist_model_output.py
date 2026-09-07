"""Synthetic-only tests: no transport performs I/O or receives real content."""

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import inspect
import json
import unittest
from unittest.mock import Mock, patch

from ai_evaluation_contracts import EvaluationCase, EvaluationOutcomeClassification
from identification_specialist import (
    IdentificationSpecialistRequest,
    IdentificationSpecialistResult,
    run_identification_specialist,
)
from identification_specialist_execution import (
    DETERMINISTIC_IDENTIFICATION_EXECUTOR,
    execute_and_compare_identification,
    execute_identification_specialist,
)
import identification_specialist_model_output as model_output
from identification_specialist_model_output import (
    IDENTIFICATION_MODEL_SCHEMA_VERSION,
    MAX_MODEL_RESPONSE_CHARS,
    IdentificationModelRequest,
    create_model_identification_executor,
    parse_identification_model_output,
)
from identification_verification_evaluation_batch import compare_identification_batch


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, request):
        self.calls.append(request)
        return self.response


def response(candidate_id="candidate:a", abstained=False, **extra):
    return json.dumps({
        "schema_version": IDENTIFICATION_MODEL_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "abstained": abstained,
        **extra,
    })


class IdentificationModelOutputTests(unittest.TestCase):
    def setUp(self):
        self.request = IdentificationSpecialistRequest(
            "1", "case:synthetic:1", ("candidate:a", "candidate:b"),
            ("candidate:a",), ("ref:synthetic:1", "ref:synthetic:2"),
        )
        self.case = EvaluationCase(
            "1", self.request.case_id, ("candidate:b",),
            evidence_refs=("ref:independent-truth",),
        )

    def parse(self, raw):
        return parse_identification_model_output(self.request, raw)

    def compose(self, raw, request=None):
        fake = FakeTransport(raw)
        executor = create_model_identification_executor("synthetic-model-v1", fake)
        report = execute_and_compare_identification(
            self.request if request is None else request, executor, self.case,
        )
        return report, fake

    def test_valid_selection_preserves_exact_case_and_evidence(self):
        result = self.parse(response())
        self.assertIs(type(result), IdentificationSpecialistResult)
        self.assertEqual(result, run_identification_specialist(self.request))
        self.assertIs(result.case_id, self.request.case_id)
        self.assertIs(result.evidence_refs, self.request.evidence_refs)
        self.assertEqual(result.schema_version, self.request.schema_version)

    def test_valid_abstention(self):
        result = self.parse(response(None, True))
        self.assertTrue(result.abstained)
        self.assertIsNone(result.candidate_id)
        self.assertIs(result.evidence_refs, self.request.evidence_refs)

    def test_matching_empty_request_evidence_preserved(self):
        request = replace(self.request, evidence_refs=())
        result = parse_identification_model_output(request, response())
        self.assertEqual(result.evidence_refs, ())

    def test_unknown_candidate_rejected_without_normalization(self):
        for candidate in ("candidate:c", " candidate:a", "candidate:a ",
                          "CANDIDATE:A", "a", "candidate:а"):
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(ValueError, "not authorized"):
                    self.parse(response(candidate))

    def test_significant_whitespace_in_authorized_id_is_preserved(self):
        candidate = " candidate:a "
        request = replace(self.request, candidate_ids=(candidate,),
                          eligible_candidate_ids=(candidate,))
        result = parse_identification_model_output(request, response(candidate))
        self.assertEqual(result.candidate_id, candidate)

    def test_empty_and_whitespace_only_ids_rejected(self):
        for candidate in ("", " ", "\t\n"):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                self.parse(response(candidate))

    def test_candidate_type_rejected(self):
        for candidate in (True, False, 1, 1.5, [], {}):
            with self.subTest(candidate=candidate), self.assertRaises(TypeError):
                self.parse(response(candidate))

    def test_abstained_requires_boolean_without_coercion(self):
        for abstained in (0, 1, "false", "true", None, [], {}):
            with self.subTest(abstained=abstained), self.assertRaises(TypeError):
                self.parse(response(abstained=abstained))

    def test_incompatible_selection_and_abstention_rejected(self):
        for raw in (response(None, False), response("candidate:a", True)):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.parse(raw)

    def test_each_missing_field_rejected(self):
        payload = json.loads(response())
        for field in payload:
            incomplete = dict(payload)
            del incomplete[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.parse(json.dumps(incomplete))

    def test_extra_fields_cannot_redefine_authority_even_when_matching(self):
        extras = {
            "case_id": self.request.case_id,
            "evidence_refs": list(self.request.evidence_refs),
            "eligible_candidate_ids": ["candidate:b"],
            "allowed_candidate_ids": ["candidate:a"],
            "expected_candidate_id": "candidate:a",
            "confidence": 0.9,
            "reason": "synthetic prose",
            "metadata": {},
            "candidate": "candidate:a",
        }
        for field, value in extras.items():
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.parse(response(**{field: value}))
        for field in ("case_id", "evidence_refs"):
            with self.subTest(mismatch=field), self.assertRaises(ValueError):
                self.parse(response(**{field: "fabricated"}))

    def test_unsupported_version_rejected(self):
        for version in ("", "2", "01", "1 "):
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.parse(response(schema_version=version))

    def test_version_requires_string(self):
        for version in (1, True, None, [], {}):
            with self.subTest(version=version), self.assertRaises(TypeError):
                self.parse(response(schema_version=version))

    def test_raw_type_must_be_text(self):
        for raw in (None, b"{}", {}, [], 1, True):
            with self.subTest(raw=raw), self.assertRaises(TypeError):
                self.parse(raw)

    def test_non_object_json_rejected(self):
        for raw in ("[]", "null", "1", '"text"', "true"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.parse(raw)

    def test_malformed_json_and_fallback_text_rejected(self):
        for raw in ("", " ", "{", "{'candidate_id': 'candidate:a'}",
                    response() + " trailing", response() + response(),
                    "```json\n" + response() + "\n```", "\ufeff" + response(),
                    response()[:-1] + ",}", "/*comment*/" + response()):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.parse(raw)

    def test_duplicate_fields_rejected_even_when_values_agree(self):
        for field, value in (("schema_version", '"1"'),
                             ("candidate_id", '"candidate:a"'),
                             ("abstained", "false")):
            raw = response()[:-1] + ', "' + field + '":' + value + "}"
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    self.parse(raw)

    def test_escape_equivalent_duplicate_key_rejected(self):
        raw = response()[:-1] + ', "candidate_\\u0069d":"candidate:b"}'
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.parse(raw)

    def test_non_json_constants_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            raw = response().replace('"candidate:a"', value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.parse(raw)

    def test_nested_values_and_excessive_depth_rejected(self):
        raw = '{"schema_version":"1","candidate_id":' + "[" * 2000
        raw += "null" + "]" * 2000 + ',"abstained":false}'
        with self.assertRaises((TypeError, ValueError)):
            self.parse(raw)
        with self.assertRaises(TypeError):
            self.parse(response({"candidate_id": "candidate:a"}))

    def test_decoder_recursion_failure_becomes_value_error_without_retry(self):
        with patch.object(model_output.json, "loads", side_effect=RecursionError) as loads:
            with self.assertRaisesRegex(ValueError, "valid bounded JSON"):
                self.parse(response())
            loads.assert_called_once()

    def test_unpaired_unicode_surrogates_rejected(self):
        for candidate in ("\ud800", "\udfff"):
            for escaped in (True, False):
                raw = json.dumps({"schema_version": "1", "candidate_id": candidate,
                                  "abstained": False}, ensure_ascii=escaped)
                with self.subTest(escaped=escaped), self.assertRaises(ValueError):
                    self.parse(raw)

    def test_standard_json_escapes_and_field_order_are_valid(self):
        raw = '{"abstained":false,"candidate_id":"candidate:\\u0061","schema_version":"1"}'
        self.assertEqual(self.parse(raw), self.parse(response()))

    def test_response_budget_checked_before_json_decode(self):
        with patch.object(model_output.json, "loads") as loads:
            with self.assertRaisesRegex(ValueError, "character limit"):
                self.parse(" " * (MAX_MODEL_RESPONSE_CHARS + 1))
            loads.assert_not_called()
        raw = response()
        padded = raw + " " * (MAX_MODEL_RESPONSE_CHARS - len(raw))
        self.assertEqual(self.parse(padded), self.parse(raw))

    def test_existing_candidate_length_limit_including_escaped_unicode(self):
        candidate = "\U0001f4a1" * 16_384
        request = replace(self.request, candidate_ids=(candidate,),
                          eligible_candidate_ids=(candidate,))
        raw = response(candidate)
        self.assertLess(len(raw), MAX_MODEL_RESPONSE_CHARS)
        self.assertEqual(parse_identification_model_output(request, raw).candidate_id,
                         candidate)
        with self.assertRaises(ValueError):
            self.parse(response("x" * 16_385))

    def test_transport_receives_only_frozen_synthetic_projection(self):
        report, fake = self.compose(response())
        self.assertEqual(len(fake.calls), 1)
        projection = fake.calls[0]
        self.assertIs(type(projection), IdentificationModelRequest)
        self.assertEqual({field.name for field in fields(projection)},
                         {"schema_version", "candidate_ids"})
        self.assertIs(projection.candidate_ids, self.request.candidate_ids)
        self.assertEqual(projection.schema_version, "1")
        self.assertFalse(hasattr(projection, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            projection.schema_version = "2"
        report.validate(self.request, self.case)
        self.assertEqual(len(fake.calls), 1)

    def test_injection_and_repeat_execution_are_deterministic(self):
        fake = FakeTransport(response("candidate:b"))
        executor = create_model_identification_executor("synthetic-test-v1", fake)
        first = execute_identification_specialist(self.request, executor)
        second = execute_identification_specialist(self.request, executor)
        self.assertEqual(first, second)
        self.assertEqual(first.executor_id, "synthetic-test-v1")
        self.assertEqual(first.specialist_result.candidate_id, "candidate:b")
        self.assertEqual(len(fake.calls), 2)
        report1 = execute_and_compare_identification(self.request, executor, self.case)
        report2 = execute_and_compare_identification(self.request, executor, self.case)
        self.assertEqual(report1, report2)

    def test_inputs_and_response_not_mutated(self):
        raw = response()
        before = deepcopy((self.request, self.case, raw))
        self.compose(raw)
        self.assertEqual((self.request, self.case, raw), before)
        self.assertEqual(self.parse(raw), self.parse(raw))

    def test_authorized_policy_invalid_result_can_evaluate_correct(self):
        report, _ = self.compose(response("candidate:b"))
        self.assertEqual(report.comparison.verification.reason_codes,
                         ("candidate_does_not_match_sole_eligible",))
        self.assertFalse(report.comparison.verification.accepted)
        self.assertEqual(report.comparison.evaluation_outcome.classification,
                         EvaluationOutcomeClassification.CORRECT)

    def test_policy_valid_result_can_evaluate_incorrect(self):
        report, _ = self.compose(response("candidate:a"))
        self.assertTrue(report.comparison.verification.accepted)
        self.assertEqual(report.comparison.evaluation_outcome.classification,
                         EvaluationOutcomeClassification.INCORRECT)
        self.assertEqual(self.case.allowed_candidate_ids, ("candidate:b",))

    def test_forced_selection_with_zero_or_multiple_eligible_reaches_verifier(self):
        for eligible in ((), self.request.candidate_ids):
            request = replace(self.request, eligible_candidate_ids=eligible)
            report, _ = self.compose(response(), request=request)
            with self.subTest(eligible=eligible):
                self.assertEqual(report.comparison.verification.reason_codes,
                                 ("selection_when_abstention_required",))

    def test_abstention_remains_explicit_through_execution(self):
        for eligible in (("candidate:a",), (), self.request.candidate_ids):
            request = replace(self.request, eligible_candidate_ids=eligible)
            report, _ = self.compose(response(None, True), request=request)
            with self.subTest(eligible=eligible):
                self.assertTrue(report.execution.specialist_result.abstained)
                self.assertIsNone(report.execution.specialist_result.candidate_id)
                self.assertEqual(report.comparison.evaluation_outcome.classification,
                                 EvaluationOutcomeClassification.ABSTAINED)
                self.assertEqual(report.comparison.verification.accepted, len(eligible) != 1)

    def test_bad_transport_output_never_retries_or_reaches_comparison(self):
        for raw in ("{", response("unknown"), response(confidence=0.5), None):
            fake = FakeTransport(raw)
            executor = create_model_identification_executor("synthetic-v1", fake)
            with patch("identification_specialist_execution.compare_identification_verification_and_evaluation") as compare:
                with self.subTest(raw=raw), self.assertRaises((TypeError, ValueError)):
                    execute_and_compare_identification(self.request, executor, self.case)
                compare.assert_not_called()
            self.assertEqual(len(fake.calls), 1)

    def test_transport_exception_propagates_without_retry(self):
        error = RuntimeError("synthetic failure")
        transport = Mock(side_effect=error)
        executor = create_model_identification_executor("synthetic-v1", transport)
        with self.assertRaises(RuntimeError) as caught:
            execute_identification_specialist(self.request, executor)
        self.assertIs(caught.exception, error)
        transport.assert_called_once()

    def test_invalid_request_rejected_before_transport_and_by_parser(self):
        for request in (None, replace(self.request, candidate_ids=()),
                        replace(self.request, eligible_candidate_ids=("unknown",))):
            transport = Mock()
            executor = create_model_identification_executor("synthetic-v1", transport)
            with self.subTest(request=request):
                with self.assertRaises((TypeError, ValueError)):
                    executor.execute(request)
                with self.assertRaises((TypeError, ValueError)):
                    parse_identification_model_output(request, response())
                transport.assert_not_called()

    def test_factory_reuses_executor_validation_and_rejects_non_callable(self):
        with self.assertRaises(TypeError):
            create_model_identification_executor("synthetic-v1", None)
        transport = Mock()
        for identifier in ("", "with space", "x" * 129, None):
            with self.subTest(identifier=identifier), self.assertRaises((TypeError, ValueError)):
                create_model_identification_executor(identifier, transport)
        transport.assert_not_called()

    def test_existing_batch_and_deterministic_executor_unchanged(self):
        report, _ = self.compose(response("candidate:b"))
        batch = compare_identification_batch((
            (self.request, report.execution.specialist_result, self.case),
        ))
        self.assertEqual(batch.reports, (report.comparison,))
        self.assertEqual(batch.verifier_rejected, 1)
        self.assertEqual(batch.evaluation_aggregate.correct, 1)
        self.assertIs(DETERMINISTIC_IDENTIFICATION_EXECUTOR.execute,
                      run_identification_specialist)
        self.assertEqual(execute_identification_specialist(
            self.request, DETERMINISTIC_IDENTIFICATION_EXECUTOR,
        ).specialist_result, run_identification_specialist(self.request))

    def test_production_imports_and_calls_do_not_add_io_or_provider_access(self):
        tree = ast.parse(inspect.getsource(model_output))
        allowed = {"__future__", "collections.abc", "dataclasses", "json", "typing",
                   "identification_specialist", "identification_specialist_execution"}
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"open", "exec", "eval", "__import__"})
        self.assertEqual(imports, allowed)


if __name__ == "__main__":
    unittest.main()
