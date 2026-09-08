"""Evidence reporting tests: no installed mutmut or real mutation execution."""

import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import capture_mutmut_evidence as evidence


def result(stdout="", stderr="", code=0):
    return subprocess.CompletedProcess([], code, stdout, stderr)


def detail(mutant, text="diff evidence"):
    return result(f"# {mutant}: survived\n{text}\n")


class MutmutEvidenceCaptureTests(unittest.TestCase):
    def invoke(self, responses, outcome="success", exit_code="0"):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(evidence.subprocess, "run", side_effect=responses) as run:
                with contextlib.redirect_stdout(io.StringIO()):
                    code = evidence.main([
                        "--output-dir", directory, "--run-outcome", outcome,
                        "--run-exit-code", exit_code,
                    ])
            root = Path(directory)
            report = json.loads((root / "mutmut-report.json").read_text(encoding="utf-8"))
            rendered = (root / "mutmut-survivor-diffs.txt").read_text(encoding="utf-8")
            primary = (root / "mutmut-results.txt").read_text(encoding="utf-8")
            return code, report, rendered, primary, run

    def assert_not_zero(self, report, rendered):
        self.assertIsNone(report["survivor_count"])
        self.assertNotIn("Survivor count: 0", rendered)
        self.assertNotIn("No survivor entries reported", rendered)

    def test_successful_empty_results(self):
        code, report, rendered, _, run = self.invoke([result()])
        self.assertEqual(code, 0)
        self.assertEqual(report["state"], "COMPLETE")
        self.assertEqual(report["survivor_count"], 0)
        self.assertIn("No survivor entries reported", rendered)
        self.assertNotIn("No surviving mutants", rendered)
        run.assert_called_once_with(["mutmut", "results"], capture_output=True,
                                    text=True, encoding="utf-8",
                                    errors="backslashreplace", check=False)

    def test_results_failure_overrides_mutation_outcome_and_partial_stdout(self):
        for outcome in ("success", "failure", "cancelled", "skipped", "unknown"):
            with self.subTest(outcome=outcome):
                code, report, rendered, primary, run = self.invoke(
                    [result("    reviewer.x__mutmut_1: survived\n", "retrieval failed", 7)],
                    outcome=outcome,
                )
                self.assertEqual(code, 1)
                self.assertEqual(report["state"], "UNAVAILABLE")
                self.assertEqual(report["results"]["exit_code"], 7)
                self.assertEqual(report["results"]["stderr"], "retrieval failed")
                self.assertIn("retrieval failed", primary)
                self.assertIn("reviewer.x__mutmut_1", primary)
                self.assert_not_zero(report, rendered)
                self.assertEqual(run.call_count, 1)

    def test_missing_executable_has_no_invented_exit_code(self):
        code, report, rendered, primary, _ = self.invoke([FileNotFoundError("not installed")])
        self.assertEqual(code, 1)
        self.assertEqual(report["state"], "UNAVAILABLE")
        self.assertIsNone(report["results"]["exit_code"])
        self.assertIn("not installed", primary)
        self.assert_not_zero(report, rendered)

    def test_failed_or_unknown_execution_with_empty_results(self):
        for outcome, exit_code in (
            ("failure", "8"), ("cancelled", ""), ("skipped", ""),
            ("unknown", ""), ("success", ""), ("success", "bad"), ("success", "8"),
        ):
            with self.subTest(outcome=outcome, exit_code=exit_code):
                code, report, rendered, _, _ = self.invoke([result()], outcome, exit_code)
                self.assertEqual(code, 1)
                self.assertEqual(report["state"], "INCOMPLETE")
                self.assertEqual(report["mutation_run"]["outcome"], outcome)
                self.assert_not_zero(report, rendered)

    def test_failed_mutation_still_captures_readable_survivors(self):
        mutant = "reviewer.x__mutmut_1"
        code, report, rendered, _, _ = self.invoke(
            [result(f"    {mutant}: survived\n"), detail(mutant)], "failure", "9")
        self.assertEqual(code, 1)
        self.assertEqual(report["state"], "INCOMPLETE")
        self.assertEqual(report["mutation_run"]["exit_code"], 9)
        self.assertEqual(report["details"][0]["state"], "COMPLETE")
        self.assertIn("diff evidence", rendered)
        self.assert_not_zero(report, rendered)

    def test_failed_detail_does_not_discard_other_details(self):
        first, second = "reviewer.x__mutmut_1", "reviewer.x__mutmut_2"
        code, report, rendered, _, run = self.invoke([
            result(f"    {first}: survived\n    {second}: survived\n"),
            result("partial diff", "show failed", 4), detail(second, "retained diff"),
        ])
        self.assertEqual(code, 1)
        self.assertEqual(report["state"], "INCOMPLETE")
        self.assertEqual([d["state"] for d in report["details"]], ["INCOMPLETE", "COMPLETE"])
        self.assertEqual(report["details"][0]["mutant"], first)
        self.assertEqual(report["details"][0]["exit_code"], 4)
        self.assertEqual(report["details"][0]["stdout"], "partial diff")
        self.assertEqual(report["details"][0]["stderr"], "show failed")
        for text in (first, second, "show failed", "partial diff", "retained diff"):
            self.assertIn(text, rendered)
        self.assertEqual(run.call_args_list[-1].args[0], ["mutmut", "show", second])
        self.assert_not_zero(report, rendered)

    def test_successful_survivor_capture(self):
        mutant = "reviewer.x__mutmut_1"
        code, report, rendered, _, _ = self.invoke([
            result(f"    {mutant}: survived\n"), detail(mutant),
        ])
        self.assertEqual(code, 0)
        self.assertEqual(report["state"], "COMPLETE")
        self.assertEqual(report["survivor_count"], 1)
        self.assertEqual(report["details"][0]["exit_code"], 0)
        self.assertIn(f"MUTANT: {mutant}", rendered)

    def test_unknown_results_fail_closed_without_running_show(self):
        for output in (
            "unexpected new summary\n",
            "    reviewer.x__mutmut_1: new-status\n",
            "    reviewer.x__mutmut_1: survived\nunknown footer\n",
        ):
            with self.subTest(output=output):
                code, report, rendered, primary, run = self.invoke([result(output)])
                self.assertEqual(code, 1)
                self.assertEqual(report["state"], "UNAVAILABLE")
                self.assertIn(output, primary)
                self.assertIn("Unrecognized", rendered)
                self.assert_not_zero(report, rendered)
                self.assertEqual(run.call_count, 1)

    def test_known_non_survivor_statuses_are_not_a_perfect_score(self):
        statuses = ("killed", "no tests", "check was interrupted by user",
                    "not checked", "skipped", "suspicious", "timeout",
                    "caught by type check", "segfault")
        output = "".join(f"    reviewer.x__mutmut_{i}: {s}\n" for i, s in enumerate(statuses))
        code, report, rendered, primary, run = self.invoke([result(output)])
        self.assertEqual(code, 0)
        self.assertEqual(report["state"], "COMPLETE")
        self.assertIn(output, primary)
        self.assertIn("not a mutation score", rendered)
        self.assertEqual(run.call_count, 1)

    def test_missing_or_unrecognized_detail_is_incomplete(self):
        first, second = "reviewer.x__mutmut_1", "reviewer.x__mutmut_2"
        for failed_detail in (FileNotFoundError("missing"), result(""), result("unknown format")):
            with self.subTest(failed_detail=failed_detail):
                code, report, rendered, _, _ = self.invoke([
                    result(f"    {first}: survived\n    {second}: survived\n"),
                    failed_detail, detail(second),
                ])
                self.assertEqual(code, 1)
                self.assertEqual(report["state"], "INCOMPLETE")
                self.assertEqual(report["details"][0]["state"], "INCOMPLETE")
                self.assertEqual(report["details"][1]["state"], "COMPLETE")
                self.assertIn(first, rendered)
                self.assert_not_zero(report, rendered)


if __name__ == "__main__":
    unittest.main()
