"""Offline wrapper tests. Fake scanner receipts are never qualification evidence."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests.test_repository_privacy_boundaries import WorkflowLoader
from tools import c07_remaining

try:
    from tools import gitleaks_history as wrapper
except ImportError:
    wrapper = None


class HistoryWrapperTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(wrapper, "explicit full-history wrapper is missing")

    def test_real_git_patches_include_root_deleted_unmerged_and_merge_only(self):
        from tools.c07_native import materialize
        definitions = [d for d in c07_remaining.build_definitions() if d.case.requirement == "P09"]
        self.assertEqual(len(definitions), 8)
        for definition in definitions:
            with self.subTest(case=definition.case.case_id), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "fixture"
                materialize(definition.case, root, refs=definition.refs)
                result = subprocess.run(
                    ["git", "-C", str(root), "log", "-p", "-U0", *wrapper.LOG_OPTIONS.split()],
                    env=wrapper.scan_environment(temp), capture_output=True, check=True, timeout=10)
                occurrence = definition.case.expected[0]
                self.assertIn(occurrence.commit.encode(), result.stdout)
                self.assertIn(("+api_key = \"" + occurrence.value).encode(), result.stdout)
                if definition.topology == "merge-only":
                    old = subprocess.run(["git", "-C", str(root), "log", "-p", "-U0",
                                          "--all", "--no-merges", "--first-parent"],
                                         env=wrapper.scan_environment(temp), capture_output=True,
                                         check=True, timeout=10)
                    self.assertNotIn(occurrence.value.encode(), old.stdout)

    def test_merged_side_commit_is_traversed_without_a_side_ref(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = wrapper.scan_environment(temp)
            def git(*args):
                return subprocess.run(["git", "-C", temp, "-c", "user.name=Inert",
                                       "-c", "user.email=inert@example.invalid", "-c",
                                       "commit.gpgsign=false", *args], env=env,
                                      capture_output=True, check=True, timeout=10).stdout
            git("init", "-b", "main")
            git("commit", "--allow-empty", "-m", "root")
            git("checkout", "-b", "side")
            (root / "side.txt").write_text("C07-MERGED-SIDE-CONTROL\n")
            git("add", "--", "side.txt")
            git("commit", "-m", "side")
            side = git("rev-parse", "HEAD").strip()
            git("checkout", "main")
            git("commit", "--allow-empty", "-m", "main")
            git("merge", "--no-ff", "side", "-m", "merge")
            git("branch", "-D", "side")
            self.assertIn(b"commit " + side, git("log", "-p", "-U0", *wrapper.LOG_OPTIONS.split()))
            self.assertNotIn(b"commit " + side, git("log", "-p", "-U0", "--all", "--first-parent"))

    def test_command_never_uses_event_ranges_or_ambient_ignore_sources(self):
        command = wrapper.scan_command(("scanner",), "repo", "config", "report", "ignore")
        self.assertIn("--log-opts=--all --full-history --root --diff-merges=first-parent --no-renames --no-ext-diff --no-textconv", command)
        self.assertIn("--ignore-gitleaks-allow", command)
        self.assertIn("--gitleaks-ignore-path=ignore", command)
        self.assertIn("--redact=100", command)
        self.assertFalse(any("baseline" in arg or arg == "--first-parent" for arg in command))
        env = wrapper.scan_environment("empty-home")
        self.assertNotIn("GITHUB_TOKEN", env)
        self.assertNotIn("GITLEAKS_CONFIG_TOML", env)
        self.assertEqual(env["GIT_NO_REPLACE_OBJECTS"], "1")

    def test_workflow_rejects_skips_event_action_and_swallowed_errors(self):
        root = Path(__file__).resolve().parents[1]
        workflow = yaml.load((root / ".github/workflows/tests.yml").read_text(), Loader=WorkflowLoader)
        wrapper.validate_workflow(workflow)
        mutations = [
            lambda j: j.update({"if": "false"}),
            lambda j: j.update({"continue-on-error": True}),
            lambda j: j["steps"][-1].update({"if": "false"}),
            lambda j: j["steps"][-1].update({"continue-on-error": True}),
            lambda j: j["steps"][-1].update({"run": j["steps"][-1]["run"] + " || true"}),
            lambda j: j["steps"][0]["with"].update({"fetch-depth": 1}),
            lambda j: j["steps"][-1].update({"uses": "gitleaks/gitleaks-action@v3"}),
            lambda j: j.update({"env": {"GIT_CONFIG_COUNT": "1"}}),
        ]
        for mutation in mutations:
            changed = copy.deepcopy(workflow)
            mutation(changed["jobs"]["gitleaks"])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                wrapper.validate_workflow(changed)

    def test_fake_process_failures_missing_reports_and_output_do_not_pass(self):
        # Real subprocess boundary, inert Python program instead of a scanner.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            env = wrapper.scan_environment(temp)
            subprocess.run(["git", "init", str(repo)], env=env, capture_output=True, check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c",
                            "user.email=test@example.invalid", "-c", "commit.gpgsign=false",
                            "commit", "--allow-empty", "-m", "inert"],
                           env=env, capture_output=True, check=True)
            config = root / "config.toml"
            config.write_text("[extend]\nuseDefault = true\n")
            fake = root / "fake.py"
            for code, payload, expected in ((0, "[]", 0), (2, "[{}]", 1),
                                             (0, "{}", 1), (0, "[", 1),
                                             (0, None, 1), (1, "[]", 1), (3, "[]", 1)):
                fake.write_text("import sys, pathlib\n"
                                "if sys.argv[1:] == ['version']:\n"
                                " print('8.24.3'); sys.exit(0)\n"
                                "print('DO-NOT-PUBLISH-RAW-OUTPUT')\n"
                                f"payload = {payload!r}\n"
                                "if payload is not None:\n"
                                " p = next(a.split('=',1)[1] for a in sys.argv if a.startswith('--report-path='))\n"
                                " pathlib.Path(p).write_text(payload)\n"
                                f"sys.exit({code})\n")
                with self.subTest(code=code, payload=payload):
                    self.assertEqual(wrapper.run_scan((sys.executable, str(fake)), repo, config, timeout=5), expected)
            fake.write_text("import sys, pathlib\n"
                            "if sys.argv[1:] == ['version']:\n"
                            " print('8.24.3'); sys.exit(0)\n"
                            "p = next(a.split('=',1)[1] for a in sys.argv if a.startswith('--report-path='))\n"
                            "pathlib.Path(p).write_text('[]')\n")
            for relative in (".git/info/grafts", ".git/objects/info/alternates"):
                path = repo / relative
                path.parent.mkdir(exist_ok=True)
                path.write_text("")
                with self.subTest(forbidden=relative):
                    self.assertEqual(wrapper.run_scan((sys.executable, str(fake)), repo, config, timeout=5), 1)
                path.unlink()
            fake.write_text("import time; time.sleep(5)\n")
            self.assertEqual(wrapper.run_scan((sys.executable, str(fake)), repo, config, timeout=0.05), 1)
            self.assertEqual(wrapper.run_scan((str(root / 'missing'),), repo, config, timeout=1), 1)

    def test_report_exit_consistency_and_duplicate_fields(self):
        record = {"RuleID": "inert-rule", "File": "inert.txt", "Commit": "a" * 40,
                  "StartLine": 1, "EndLine": 1, "StartColumn": 1, "EndColumn": 8,
                  "Secret": "REDACTED"}
        self.assertEqual(wrapper.check_report(json.dumps([record]).encode(), 2), 2)
        for data, code in ((b"[]", 2), (json.dumps([record]).encode(), 0),
                           (b'[{"RuleID":"a","RuleID":"b"}]', 2), (b"null", 0)):
            with self.subTest(data=data, code=code), self.assertRaises(ValueError):
                wrapper.check_report(data, code)


if __name__ == "__main__":
    unittest.main()
