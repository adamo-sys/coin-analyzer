"""Synthetic final-acceptance tests; no contestant or historical grading execution."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from tools import bakeoff_v1_final_acceptance as acceptance


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest(value):
    return sha256(encoded(value)).hexdigest()


def fixture():
    packet = {
        "task_id": "SYNTHETIC", "starting_sha": "1" * 40,
        "reference_end_sha": "2" * 40, "reference_changed_paths": ["tests/test_synthetic.py"],
        "required_validation": ["python -B -m unittest tests.test_synthetic"],
        "expected_implementation_paths": {"tests/test_synthetic.py": ["synthetic.py"]},
        "allowed_scope": ["synthetic.py"], "forbidden_benchmark_mutations": [],
    }
    candidate = {"ending_sha": "3" * 40, "tree_sha": "4" * 40, "git_status": [],
                 "changed_paths": ["synthetic.py"], "name_status": ["M\tsynthetic.py"],
                 "diff_fingerprint": "5" * 40}
    check = {"check_id": packet["required_validation"][0], "command": packet["required_validation"][0],
             "execution_order": 0, "candidate_ending_sha": candidate["ending_sha"], "status": "passed",
             "exit_code": 0, "output_sha256": "6" * 64, "provenance": "trusted_local_execution", "error": None}
    oracle = {"check_id": "reference-acceptance:tests/test_synthetic.py", "test_path": "tests/test_synthetic.py",
              "source": "2" * 40 + ":tests/test_synthetic.py", "source_blob_sha": "7" * 40,
              "source_content_sha256": "8" * 64, "execution_order": 0,
              "candidate_ending_sha": candidate["ending_sha"], "status": "passed", "exit_code": 0,
              "output_sha256": "9" * 64, "provenance": "frozen_reference_test_blob_against_candidate",
              "candidate_module_provenance": [["synthetic", "synthetic.py", True]],
              "expected_implementation_paths": ["synthetic.py"], "observed_implementation_paths": ["synthetic.py"],
              "outside_implementation_paths": [], "provenance_validation": "passed",
              "candidate_import_root": "synthetic-root", "error": None}
    evidence = {"schema_version": "1", "grader_id": "bakeoff-v1-deterministic-grader",
                "grader_implementation": "evidence-bound-v2", "corpus_manifest_sha256": "a" * 64,
                "task_id": "SYNTHETIC", "run_id": "synthetic-run", "starting_sha": "1" * 40,
                "candidate": candidate, "required_checks": [check], "independent_acceptance": [oracle],
                "unverified_claim_mismatches": {}}
    result = {"schema_version": "1", "grader_id": evidence["grader_id"],
              "grader_implementation": evidence["grader_implementation"], "checked_at_utc": "2026-10-11T00:00:00Z",
              "task_id": "SYNTHETIC", "run_id": "synthetic-run", "corpus_manifest_sha256": "a" * 64,
              "status": "VALID_WITH_FINDINGS", "task_success": "passed",
              "required_validation": {"missing_or_failed": [], "evidence": [copy.deepcopy(check)]},
              "scope": {"changed_paths": candidate["changed_paths"], "name_status": candidate["name_status"],
                        "diff_fingerprint": candidate["diff_fingerprint"], "findings": []},
              "anti_gaming": {"tamper_status": "not_detected", "findings": []}, "invalid_reasons": [],
              "evidence": {"evidence_sha256": "", "claims": {}}}
    review = {"schema_version": "1", "reviewer_id": "independent-synthetic-reviewer", "bindings": {}, "findings": []}
    attestation = {"schema_version": "1", "operator_id": "synthetic-operator", "workflow_reference": "synthetic-owner-workflow",
                   "bindings": {}, "review_sha256": "", "reviewer_independently_authorized": True,
                   "reviewer_not_contestant": True, "operator_approved_review": True,
                   "operator_accepts_authority_responsibility": True}
    return [result, evidence, packet, review, attestation]


def bind(values):
    result, evidence, packet, review, attestation = values
    evidence.pop("evidence_sha256", None)
    evidence["evidence_sha256"] = digest(evidence)
    result["evidence"]["evidence_sha256"] = evidence["evidence_sha256"]
    review["bindings"] = {
        "grading_result_sha256": digest(result), "grading_evidence_sha256": digest(evidence),
        "task_packet_sha256": digest(packet),
        "run_identity": {key: evidence[key] for key in ("task_id", "run_id", "starting_sha", "corpus_manifest_sha256")},
        "candidate_identity": {"kind": "candidate_state_sha256", "value": evidence["candidate"]["candidate_state_sha256"]}
        if "candidate_state_sha256" in evidence["candidate"] else {"kind": "ending_sha", "value": evidence["candidate"]["ending_sha"]},
    }
    attestation["bindings"] = copy.deepcopy(review["bindings"])
    attestation["review_sha256"] = digest(review)
    return [encoded(value) for value in values]


def finding(disposition="nonblocking", technical=None):
    return {"finding_id": "synthetic-finding", "severity": "note" if disposition == "nonblocking" else "blocking",
            "evidence_reference": "synthetic:evidence:1", "violated_rule": "synthetic scope rule",
            "smallest_correction": "Review the synthetic scope change", "disposition": disposition,
            "technical_finding_sha256": None if technical is None else digest(technical)}


class FinalAcceptanceTests(unittest.TestCase):
    def evaluate(self, values):
        return acceptance.evaluate_final_acceptance(*bind(values))

    def test_clean_success_and_raw_result_preservation(self):
        values = fixture()
        inputs = bind(values)
        before = copy.deepcopy(inputs)
        output = acceptance.evaluate_final_acceptance(*inputs)
        self.assertEqual(output["verdict"], "PASS")
        self.assertEqual(inputs, before)
        self.assertEqual(output["bindings"]["grading_result_sha256"], sha256(inputs[0]).hexdigest())
        self.assertNotIn("task_success", output)

    def test_nonblocking_note_requires_independent_disposition(self):
        values = fixture()
        raw = {"kind": "out_of_scope_change", "path": "note.txt"}
        values[1]["candidate"]["changed_paths"].append("note.txt")
        values[1]["candidate"]["name_status"].append("A\tnote.txt")
        values[0]["scope"]["findings"] = [raw]
        values[0]["anti_gaming"]["findings"] = [copy.deepcopy(raw)]
        values[3]["findings"] = [finding(technical=raw)]
        self.assertEqual(self.evaluate(values)["verdict"], "PASS_WITH_NOTES")
        values[3]["findings"] = []
        self.assertEqual(self.evaluate(values)["verdict"], "FAIL")

    def test_blocking_and_ambiguous_findings_prevent_success(self):
        for disposition in ("blocking", "ambiguous"):
            with self.subTest(disposition=disposition):
                values = fixture()
                values[3]["findings"] = [finding(disposition)]
                self.assertEqual(self.evaluate(values)["verdict"], "FAIL")

    def test_immutable_acceptance_failed_or_unavailable(self):
        for status in ("failed", "unavailable", "timed_out"):
            with self.subTest(status=status):
                values = fixture()
                values[1]["independent_acceptance"][0]["status"] = status
                values[1]["independent_acceptance"][0]["exit_code"] = 1
                values[0]["status"], values[0]["task_success"] = "FAILED_TASK", "failed"
                values[0]["required_validation"]["missing_or_failed"] = ["reference-acceptance:tests/test_synthetic.py"]
                self.assertEqual(self.evaluate(values)["verdict"], "FAIL")

    def test_invalid_run_precedence_over_task_failure(self):
        values = fixture()
        values[3]["findings"] = [finding("prohibited_shortcut")]
        values[1]["independent_acceptance"][0]["status"] = "failed"
        values[1]["independent_acceptance"][0]["exit_code"] = 1
        values[0]["status"], values[0]["task_success"] = "FAILED_TASK", "failed"
        values[0]["required_validation"]["missing_or_failed"] = ["reference-acceptance:tests/test_synthetic.py"]
        self.assertEqual(self.evaluate(values)["verdict"], "INVALID_RUN")
        values[0]["status"] = "INVALID"
        values[4] = None
        inputs = [encoded(values[0]), b"{}", b"{}", None, None]
        self.assertEqual(acceptance.evaluate_final_acceptance(*inputs)["verdict"], "INVALID_RUN")

    def test_extra_path_alone_is_not_cheating(self):
        values = fixture()
        values[1]["candidate"]["changed_paths"].append("extra.txt")
        values[1]["candidate"]["name_status"].append("A\textra.txt")
        self.assertEqual(self.evaluate(values)["verdict"], "FAIL")

    def test_missing_duplicate_and_contradictory_dispositions(self):
        for mutation in ("missing", "duplicate", "contradictory", "unknown", "unmatched"):
            with self.subTest(mutation=mutation):
                values = fixture()
                note = finding()
                if mutation == "missing":
                    note.pop("disposition")
                elif mutation == "contradictory":
                    note["severity"] = "blocking"
                elif mutation == "unknown":
                    note["disposition"] = "resolved"
                elif mutation == "unmatched":
                    note["technical_finding_sha256"] = "f" * 64
                values[3]["findings"] = [note, copy.deepcopy(note)] if mutation == "duplicate" else [note]
                self.assertEqual(self.evaluate(values)["verdict"], "FAIL")

    def test_review_and_attestation_exact_bindings(self):
        for index in (3, 4):
            for field in ("grading_result_sha256", "grading_evidence_sha256", "task_packet_sha256", "run_identity", "candidate_identity"):
                with self.subTest(index=index, field=field):
                    values = fixture()
                    bind(values)
                    values[index]["bindings"][field] = "mismatch"
                    if index == 3:
                        values[4]["review_sha256"] = digest(values[3])
                    self.assertEqual(acceptance.evaluate_final_acceptance(*[encoded(v) for v in values])["verdict"], "FAIL")
        values = fixture()
        bind(values)
        values[4]["review_sha256"] = "f" * 64
        self.assertEqual(acceptance.evaluate_final_acceptance(*[encoded(v) for v in values])["verdict"], "FAIL")

    def test_missing_and_unverified_independent_authority(self):
        confirmations = ("reviewer_independently_authorized", "reviewer_not_contestant", "operator_approved_review", "operator_accepts_authority_responsibility")
        for field in confirmations:
            for value in (False, None, "true", 1):
                with self.subTest(field=field, value=value):
                    values = fixture()
                    values[4][field] = value
                    self.assertEqual(self.evaluate(values)["verdict"], "FAIL")
        for index in (3, 4):
            inputs = bind(fixture())
            inputs[index] = None
            self.assertEqual(acceptance.evaluate_final_acceptance(*inputs)["verdict"], "FAIL")
        values = fixture()
        values[4] = {"independent": True, "authority_verified": True}
        self.assertEqual(self.evaluate(values)["verdict"], "FAIL")

    def test_byte_digest_changes_with_whitespace(self):
        inputs = bind(fixture())
        inputs[0] += b"\n"
        self.assertEqual(acceptance.evaluate_final_acceptance(*inputs)["verdict"], "FAIL")
        inputs = bind(fixture())
        inputs[3] += b"\n"
        self.assertEqual(acceptance.evaluate_final_acceptance(*inputs)["verdict"], "FAIL")

    def test_malformed_json_duplicate_keys_and_nonfinite_numbers(self):
        for index in range(5):
            for malformed in (b"{", b"[]", b'{"status":"VALID_WITH_FINDINGS","status":"INVALID"}', b'{"value":NaN}'):
                with self.subTest(index=index, malformed=malformed):
                    inputs = bind(fixture())
                    inputs[index] = malformed
                    self.assertEqual(acceptance.evaluate_final_acceptance(*inputs)["verdict"], "FAIL")

    def test_incomplete_or_contradictory_technical_evidence(self):
        for mutation in ("empty_required", "empty_acceptance", "duplicate_check", "wrong_run", "wrong_candidate",
                         "wrong_packet", "wrong_summary", "false_pass", "bad_provenance", "missing_implementation",
                         "missing_source_digest", "unavailable_output", "tamper", "false_scope"):
            with self.subTest(mutation=mutation):
                values = fixture()
                result, evidence, packet = values[:3]
                if mutation == "empty_required":
                    evidence["required_checks"] = []
                elif mutation == "empty_acceptance":
                    evidence["independent_acceptance"] = []
                elif mutation == "duplicate_check":
                    evidence["required_checks"] *= 2
                elif mutation == "wrong_run":
                    result["run_id"] = "other-run"
                elif mutation == "wrong_candidate":
                    evidence["required_checks"][0]["candidate_ending_sha"] = "f" * 40
                elif mutation == "wrong_packet":
                    packet["starting_sha"] = "f" * 40
                elif mutation == "wrong_summary":
                    result["required_validation"]["evidence"] = []
                elif mutation == "false_pass":
                    evidence["independent_acceptance"][0]["exit_code"] = 1
                elif mutation == "bad_provenance":
                    evidence["independent_acceptance"][0]["provenance"] = "contestant_claim"
                elif mutation == "missing_implementation":
                    evidence["independent_acceptance"][0]["observed_implementation_paths"] = []
                elif mutation == "missing_source_digest":
                    evidence["independent_acceptance"][0]["source_content_sha256"] = None
                elif mutation == "unavailable_output":
                    evidence["required_checks"][0]["output_sha256"] = None
                    result["required_validation"]["evidence"] = copy.deepcopy(evidence["required_checks"])
                elif mutation == "tamper":
                    result["anti_gaming"]["tamper_status"] = "failed"
                elif mutation == "false_scope":
                    result["scope"]["changed_paths"] = []
                self.assertEqual(self.evaluate(values)["verdict"], "FAIL")

    def test_protocol_v11_candidate_identity(self):
        values = fixture()
        values[1]["candidate"].pop("ending_sha")
        values[1]["candidate"]["candidate_state_sha256"] = "b" * 64
        values[0]["execution_protocol_version"] = "1.1"
        values[0]["candidate_state_sha256"] = "b" * 64
        values[1]["candidate"]["diff_fingerprint"] = "b" * 64
        values[0]["scope"]["diff_fingerprint"] = "b" * 64
        for check in values[1]["required_checks"] + values[1]["independent_acceptance"]:
            check.pop("candidate_ending_sha")
            check["candidate_state_sha256"] = "b" * 64
        values[0]["required_validation"]["evidence"] = copy.deepcopy(values[1]["required_checks"])
        self.assertEqual(self.evaluate(values)["verdict"], "PASS")
        values[0]["candidate_state_sha256"] = "c" * 64
        self.assertEqual(self.evaluate(values)["verdict"], "FAIL")

    def test_repeated_evaluation_is_deterministic(self):
        inputs = bind(fixture())
        first = acceptance.evaluate_final_acceptance(*inputs)
        for _ in range(5):
            self.assertEqual(acceptance.evaluate_final_acceptance(*inputs), first)

    def test_cli_success_failure_and_input_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = bind(fixture())
            paths = [root / name for name in ("result.json", "evidence.json", "packet.json", "review.json", "attestation.json")]
            args = [sys.executable, "-B", "-m", "tools.bakeoff_v1_final_acceptance"]
            for option, path, data in zip(("--grading-result", "--grading-evidence", "--task-packet", "--review", "--operator-attestation"), paths, inputs):
                path.write_bytes(data)
                args.extend([option, str(path)])
            run = subprocess.run(args, capture_output=True, check=False)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["verdict"], "PASS")
            self.assertEqual([path.read_bytes() for path in paths], inputs)
            paths[4].write_text("{}", encoding="utf-8")
            run = subprocess.run(args, capture_output=True, check=False)
            self.assertEqual(run.returncode, 1)
            self.assertEqual(json.loads(run.stdout)["verdict"], "FAIL")
            paths[4].unlink()
            run = subprocess.run(args, capture_output=True, check=False)
            self.assertEqual(run.returncode, 1)
            self.assertEqual(json.loads(run.stdout)["verdict"], "FAIL")



class CandidateMetadataTests(unittest.TestCase):
    def test_malformed_candidate_metadata_cannot_be_echoed_into_success(self):
        for key, value in (("diff_fingerprint", None), ("diff_fingerprint", "short"), ("name_status", None),
                           ("name_status", [1]), ("git_status", [" M synthetic.py"]), ("tree_sha", "short")):
            with self.subTest(key=key, value=value):
                values = fixture()
                values[1]["candidate"][key] = value
                if key in values[0]["scope"]:
                    values[0]["scope"][key] = value
                self.assertEqual(acceptance.evaluate_final_acceptance(*bind(values))["verdict"], "FAIL")

    def test_missing_check_metadata_and_unsafe_packet_paths(self):
        for mutation in ("missing_error", "missing_order", "unsafe_path"):
            with self.subTest(mutation=mutation):
                values = fixture()
                if mutation == "unsafe_path":
                    values[2]["allowed_scope"].append(".")
                else:
                    values[1]["required_checks"][0].pop("error" if mutation == "missing_error" else "execution_order")
                    values[0]["required_validation"]["evidence"] = copy.deepcopy(values[1]["required_checks"])
                self.assertEqual(acceptance.evaluate_final_acceptance(*bind(values))["verdict"], "FAIL")



class IndependentReviewRegressionTests(unittest.TestCase):
    def test_outside_module_cannot_hide_behind_passed_provenance_summary(self):
        values = fixture()
        values[1]["independent_acceptance"][0]["candidate_module_provenance"].append(
            ["outside.synthetic", "C:/outside/synthetic.py", False])
        self.assertEqual(acceptance.evaluate_final_acceptance(*bind(values))["verdict"], "FAIL")

    def test_name_status_cannot_hide_a_protected_change(self):
        values = fixture()
        values[1]["candidate"]["name_status"].append("M\tbenchmarks/bakeoff-v1/ground_truth.json")
        self.assertEqual(acceptance.evaluate_final_acceptance(*bind(values))["verdict"], "FAIL")

    def test_legitimate_rename_and_copy_destinations_match_git_changed_paths(self):
        for status in ("R100", "C075"):
            with self.subTest(status=status):
                values = fixture()
                values[1]["candidate"]["name_status"][:] = [status + "\told.py\tsynthetic.py"]
                self.assertEqual(acceptance.evaluate_final_acceptance(*bind(values))["verdict"], "PASS")

    def test_malformed_name_status_fails_closed(self):
        for line in ("bogus\tsynthetic.py", "R101\told.py\tsynthetic.py", "R100\tsynthetic.py",
                     "M\t../synthetic.py", "M\tsynthetic.py\textra.py"):
            with self.subTest(line=line):
                values = fixture()
                values[1]["candidate"]["name_status"][:] = [line]
                self.assertEqual(acceptance.evaluate_final_acceptance(*bind(values))["verdict"], "FAIL")


class InvalidCliPrecedenceTests(unittest.TestCase):
    def test_technical_invalid_survives_missing_other_cli_input_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = root / "result.json"
            result.write_bytes(encoded({"schema_version": "1", "status": "INVALID", "invalid_reasons": ["synthetic breach"]}))
            args = [sys.executable, "-B", "-m", "tools.bakeoff_v1_final_acceptance", "--grading-result", str(result)]
            for option in ("--grading-evidence", "--task-packet", "--review", "--operator-attestation"):
                args.extend([option, str(root / (option + ".missing"))])
            run = subprocess.run(args, capture_output=True, check=False)
            self.assertEqual(run.returncode, 1)
            self.assertEqual(json.loads(run.stdout)["verdict"], "INVALID_RUN")

if __name__ == "__main__":
    unittest.main()
