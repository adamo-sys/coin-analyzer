"""Scanner-free engineering checks; no case receives qualification evidence."""

import hashlib
import json
import subprocess
import tempfile
import tomllib
import unittest
import zlib
from collections import Counter
from copy import deepcopy
from pathlib import Path

from tools import c07_synthetic as harness
from tools.c07_findings import ReconciliationError


def reports_for(plan):
    """Explicit test double, never exported as scanner evidence."""
    reports = []
    for case in plan["cases"]:
        remaining = deepcopy(case["expected_baseline"])
        for occurrence in case["exceptions"]:
            remaining.remove(occurrence)
        row = {"case_id": case["case_id"], "snapshot_sha256": case["snapshot_sha256"]}
        for lane, findings in (("baseline", case["expected_baseline"]), ("candidate", remaining)):
            row[lane] = {
                "execution_id": case[lane + "_execution_id"], "status": "completed",
                "started_at": "2001-01-01T00:00:00Z", "finished_at": "2001-01-01T00:00:01Z",
                "exit_code": 2 if findings else 0, "findings": deepcopy(findings),
            }
        reports.append(row)
    return reports


class SyntheticHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = harness.build_cases()

    def group(self, number):
        return [c for c in self.cases if c.case_id.startswith(number + "/")]

    def test_complete_matrix_and_deterministic_fresh_generation(self):
        self.assertEqual(Counter(c.case_id[:3] for c in self.cases), {
            "P01": 1, "P02": 9, "P03": 4, "P04": 4, "P05": 2,
            "P06": 18, "P07": 54, "P08": 9,
        })
        self.assertEqual(len({c.case_id for c in self.cases}), 101)
        self.assertEqual(self.cases, harness.build_cases())
        self.assertEqual({c.requirement for c in self.cases}, {"P0" + str(i) for i in range(1, 9)})

    def test_policy_pair_changes_only_exception_and_preserves_defaults(self):
        for case in self.cases:
            b = tomllib.loads(case.baseline_config.decode())
            c = tomllib.loads(case.candidate_config.decode())
            self.assertTrue(b["extend"]["useDefault"])
            self.assertTrue(c["extend"]["useDefault"])
            self.assertEqual(c["rules"][0].pop("allowlists")[0]["condition"], "AND")
            self.assertEqual(b, c)

    def test_p01_empty_complete_reports_and_exit_semantics(self):
        plan = harness.make_plan(tuple(self.group("P01")))
        reports = reports_for(plan)
        result = harness.reconcile_synthetic(tuple(self.group("P01")), reports)
        self.assertEqual((result.summary.baseline, result.summary.candidate), (0, 0))
        self.assertFalse(result.qualified)
        self.assertFalse(result.scanner_executed)
        for lane in ("baseline", "candidate"):
            for bad in (1, 2, 3, None, True):
                broken = deepcopy(reports)
                broken[0][lane]["exit_code"] = bad
                with self.subTest(lane=lane, bad=bad), self.assertRaises(ReconciliationError):
                    harness.reconcile_synthetic(tuple(self.group("P01")), broken)
        with self.assertRaises(ReconciliationError):
            harness.reconcile_synthetic(tuple(self.group("P01")), [])

    def test_p02_all_existing_contexts_individually_with_exact_exception(self):
        cases = self.group("P02")
        self.assertEqual(sorted(c.expected[0].start_line for c in cases),
                         [147, 816, 834, 846, 853, 857, 874, 892, 905])
        self.assertEqual({c.expected[0].path for c in cases}, set(harness.AUTHORIZED_PATHS))
        for case in cases:
            self.assertEqual(case.exceptions, case.expected)
            self.assertEqual(len(case.expected), 1)
            self.assertEqual(case.expected[0].value, "normalized-coin-1-front")
            self.assertEqual(case.expected[0].rule, "generic-api-key")

    def test_p02_source_contexts_retain_original_indentation_and_predicate(self):
        expected_indent = {147: 8, 816: 20, 834: 28, 846: 20, 853: 12,
                           857: 16, 874: 20, 892: 28, 905: 24}
        for case in self.group("P02"):
            finding = case.expected[0]
            line = case.revisions[0].content.decode().splitlines()[finding.start_line - 1]
            self.assertEqual(len(line) - len(line.lstrip()), expected_indent[finding.start_line])
            if finding.start_line == 857:
                self.assertEqual(
                    line,
                    "".join((
                        " " * 16,
                        "if item.artifact_key == ",
                        '"',
                        "-".join(("normalized", "coin", "1", "front")),
                        '"',
                    )),
                )

    def test_p03_separate_and_same_line_controls_in_both_paths(self):
        for case in self.group("P03"):
            fixture, key = case.expected
            self.assertEqual(fixture.path, key.path)
            self.assertNotEqual(fixture.value, key.value)
            self.assertEqual(case.exceptions, (fixture,))
            same = case.case_id.endswith("same-line")
            self.assertEqual(fixture.start_line == key.start_line, same)

    def test_p04_independent_same_location_histories_without_exception(self):
        for path in harness.AUTHORIZED_PATHS:
            cases = [c for c in self.group("P04") if c.expected[0].path == path]
            a, b = [c.expected[0] for c in cases]
            self.assertEqual((a.rule, a.start_line, a.end_line), (b.rule, b.start_line, b.end_line))
            self.assertNotEqual(a.value, b.value)
            self.assertNotEqual(a.commit, b.commit)
            self.assertTrue(all(len(c.revisions) == 1 and not c.exceptions for c in cases))

    def test_p05_replacement_history_retains_three_commit_identities(self):
        for case in self.group("P05"):
            self.assertEqual(len(case.revisions), 3)
            self.assertEqual(len({f.commit for f in case.expected}), 3)
            self.assertEqual([f.commit for f in case.expected], [r.commit for r in case.revisions])
            self.assertEqual(len({(f.path, f.rule, f.start_line) for f in case.expected}), 1)
            self.assertEqual(case.exceptions, case.expected[:1])
            self.assertEqual([r.parent for r in case.revisions],
                             [None, case.revisions[0].commit, case.revisions[1].commit])

    def test_p06_each_path_boundary_and_detectable_wrong_rule_recipe(self):
        names = {c.case_id.rsplit("/", 1)[1] for c in self.group("P06")}
        self.assertEqual(names, {"outside", "nested", "lookalike", "prefix-name", "suffix-name",
                                 "prefix-path", "suffix-path", "unicode-lookalike", "wrong-rule"})
        for case in self.group("P06"):
            finding = case.expected[0]
            self.assertEqual(case.exceptions, ())
            if case.case_id.endswith("wrong-rule"):
                self.assertEqual(finding.rule, "c07-synthetic-wrong-rule")
                self.assertIn(b'c07-synthetic-wrong-rule', case.baseline_config)
                self.assertIn(finding.path, harness.AUTHORIZED_PATHS)
            else:
                self.assertNotIn(finding.path, harness.AUTHORIZED_PATHS)
                self.assertEqual(finding.rule, "generic-api-key")

    def test_p07_all_character_positions_prefix_suffix_and_replacements(self):
        original = "normalized-coin-1-front"
        for path in harness.AUTHORIZED_PATHS:
            cases = [c for c in self.group("P07") if c.expected[0].path == path]
            substitutions = [c.expected[0].value for c in cases if "/char-" in c.case_id]
            self.assertEqual(len(substitutions), 23)
            self.assertEqual({next(i for i, (a, b) in enumerate(zip(original, value)) if a != b)
                              for value in substitutions}, set(range(23)))
            for value in substitutions:
                self.assertEqual(sum(a != b for a, b in zip(original, value)), 1)
            self.assertTrue(any(c.expected[0].value == "X" + original for c in cases))
            self.assertTrue(any(c.expected[0].value == original + "X" for c in cases))
            self.assertEqual(sum("/high-entropy-" in c.case_id for c in cases), 2)
            self.assertTrue(all(not c.exceptions for c in cases))

    def test_p08_builtin_controls_inside_both_paths_and_elsewhere(self):
        cases = self.group("P08")
        self.assertEqual(Counter(c.expected[0].rule for c in cases),
                         {"generic-api-key": 3, "github-pat": 3, "aws-access-token": 3})
        for rule in {c.expected[0].rule for c in cases}:
            self.assertEqual({c.expected[0].path for c in cases if c.expected[0].rule == rule},
                             {*harness.AUTHORIZED_PATHS, "synthetic/unrelated.txt"})
        self.assertTrue(all(not c.exceptions for c in cases))

    def test_occurrences_correspond_to_inert_content_not_just_counts(self):
        for case in self.cases:
            revisions = {r.commit: r for r in case.revisions}
            for finding in case.expected:
                revision = revisions[finding.commit]
                self.assertEqual(finding.path, revision.path)
                line = revision.content.decode().splitlines()[finding.start_line - 1]
                self.assertIn(finding.value, line)
                self.assertTrue(finding.role and finding.context)
                self.assertEqual(finding.end_line, finding.start_line)

    def test_git_objects_are_usable_offline_and_not_invented_commit_labels(self):
        # Git reads these locally generated objects only; no scanner, network or commit command.
        case = self.group("P05")[0]
        with tempfile.TemporaryDirectory(prefix="c07-objects-") as directory:
            root = Path(directory)
            (root / "objects").mkdir()
            (root / "refs" / "heads").mkdir(parents=True)
            (root / "HEAD").write_text("ref: refs/heads/main\n", encoding="ascii")
            (root / "refs" / "heads" / "main").write_text(case.revisions[-1].commit + "\n")
            (root / "config").write_text("[core]\nrepositoryformatversion = 0\nbare = true\n")
            for obj in case.objects:
                payload = obj.kind.encode() + b" " + str(len(obj.data)).encode() + b"\0" + obj.data
                self.assertEqual(hashlib.sha1(payload).hexdigest(), obj.oid)
                target = root / "objects" / obj.oid[:2] / obj.oid[2:]
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(zlib.compress(payload))
            env = harness.sterile_git_environment(directory)
            result = subprocess.run(["git", "--git-dir=" + directory, "fsck", "--strict"],
                                    env=env, capture_output=True, timeout=10, check=False)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            for revision in case.revisions:
                result = subprocess.run(["git", "--git-dir=" + directory, "show",
                                         revision.commit + ":" + revision.path], env=env,
                                        capture_output=True, timeout=10, check=False)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, revision.content)

    def test_sterile_environment_drops_ambient_git_config_and_credentials(self):
        env = harness.sterile_git_environment(tempfile.gettempdir())
        self.assertEqual(env["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(env["GIT_ALLOW_PROTOCOL"], "")
        self.assertEqual(env["GIT_NO_LAZY_FETCH"], "1")
        self.assertNotIn("GITHUB_TOKEN", env)
        self.assertNotIn("GIT_CONFIG_COUNT", env)

    def test_full_p13_reconciliation_only_returns_engineering_result(self):
        plan = harness.make_plan(self.cases)
        before = deepcopy(plan)
        reports = reports_for(plan)
        result = harness.reconcile_synthetic(self.cases, reports)
        self.assertEqual(result.summary.cases, 101)
        self.assertEqual(result.summary.suppressed, 15)
        self.assertEqual(plan, before)
        self.assertEqual(result.status, "SYNTHETIC_RECONCILED_NOT_QUALIFIED")
        self.assertFalse(result.qualified)
        self.assertFalse(result.scanner_executed)
        self.assertTrue(all(c.blockers for c in self.cases))
        self.assertTrue(all("B_DETECTION_NOT_EXECUTED" in c.blockers for c in self.cases if c.expected))
        self.assertTrue(all("EXCEPTION_NOT_APPROVED" in c.blockers for c in self.cases if c.exceptions))

    def test_p13_rejects_each_missing_or_unexpected_identity_even_with_same_count(self):
        cases = tuple(self.group("P05"))
        plan = harness.make_plan(cases)
        good = reports_for(plan)
        for lane in ("baseline", "candidate"):
            for field, bad in (("rule", "wrong"), ("path", "wrong.py"), ("value", "INERT-wrong"),
                               ("commit", "f" * 40), ("start_line", 40), ("end_line", 42)):
                reports = deepcopy(good)
                reports[0][lane]["findings"][-1][field] = bad
                with self.subTest(lane=lane, field=field), self.assertRaises(ReconciliationError):
                    harness.reconcile_synthetic(cases, reports)
            for bad in ([], good[0][lane]["findings"] * 2):
                reports = deepcopy(good)
                reports[0][lane]["findings"] = bad
                reports[0][lane]["exit_code"] = 2 if bad else 0
                with self.assertRaises(ReconciliationError):
                    harness.reconcile_synthetic(cases, reports)

    def test_columns_require_explicit_predeclared_binding_never_guessed(self):
        cases = tuple(self.group("P03")[:1])
        bindings = {(cases[0].case_id, 0): {"start_column": 4, "end_column": 60}}
        plan = harness.make_plan(cases, columns=bindings)
        reports = reports_for(plan)
        self.assertEqual(harness.reconcile_synthetic(cases, reports, columns=bindings).summary.cases, 1)
        with self.assertRaises(ReconciliationError):
            harness.reconcile_synthetic(cases, reports)
        for bad in ({("unknown", 0): {}}, {(cases[0].case_id, 99): {}},
                    {(cases[0].case_id, 0): {"value": "guess"}},
                    {(cases[0].case_id, 0): {"start_column": True}}):
            with self.assertRaises(ReconciliationError):
                harness.make_plan(cases, columns=bad)

    def test_case_omission_skips_operational_errors_and_snapshot_replay_fail_closed(self):
        plan = harness.make_plan(self.cases)
        good = reports_for(plan)
        for mutation in ("omit", "duplicate", "skip", "exit", "snapshot", "empty-B", "absent-report"):
            reports = deepcopy(good)
            if mutation == "omit":
                reports.pop()
            elif mutation == "duplicate":
                reports.append(deepcopy(reports[-1]))
            elif mutation == "skip":
                reports[1]["candidate"]["status"] = "skipped"
            elif mutation == "exit":
                reports[1]["baseline"]["exit_code"] = 1
            elif mutation == "snapshot":
                reports[1]["snapshot_sha256"] = "0" * 64
            elif mutation == "empty-B":
                reports[1]["baseline"].update(findings=[], exit_code=0)
            else:
                del reports[1]["candidate"]["findings"]
            with self.subTest(mutation=mutation), self.assertRaises(ReconciliationError):
                harness.reconcile_synthetic(self.cases, reports)

    def test_complete_plan_binds_source_policy_history_context_and_criterion(self):
        plan = harness.make_plan(self.cases)
        self.assertEqual(plan["criterion_sha256"],
                         "B85ACAB6B686F63665947E546F54C1586D5DEE4BCCCD405CA6A53B03D61B14D8")
        self.assertEqual(len({c["snapshot_sha256"] for c in plan["cases"]}), 101)
        self.assertEqual(len({c[k] for c in plan["cases"]
                              for k in ("baseline_execution_id", "candidate_execution_id")}), 202)
        self.assertNotIn("qualified", json.dumps(plan))


if __name__ == "__main__":
    unittest.main()
