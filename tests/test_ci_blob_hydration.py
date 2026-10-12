"""Synthetic-only execution of the CI hydration program."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.test_ci_security_boundaries import HISTORY_OPTIONS, WORKFLOW
from tests.test_repository_privacy_boundaries import WorkflowLoader


class HydrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.source.mkdir()
        self.env = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0",
                        GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.git(self.source, "init", "-b", "main")
        self.git(self.source, "config", "user.name", "Synthetic")
        self.git(self.source, "config", "user.email", "ci@example.invalid")
        self.git(self.source, "config", "commit.gpgsign", "false")
        for text in ("root-marker\n", "deleted-marker\n"):
            (self.source / "fixture.txt").write_text(text)
            self.git(self.source, "add", ".")
            self.git(self.source, "commit", "-m", "Synthetic")
        (self.source / "fixture.txt").unlink()
        self.git(self.source, "add", ".")
        self.git(self.source, "commit", "-m", "Deletion")
        self.git(self.source, "config", "uploadpack.allowFilter", "true")
        self.git(self.source, "config", "uploadpack.allowAnySHA1InWant", "true")
        self.clone = self.base / "clone"
        self.clone.mkdir()
        self.git(self.clone, "init")
        self.git(self.clone, "remote", "add", "origin", self.source.as_uri())
        self.git(self.clone, "config", "remote.origin.promisor", "true")
        self.git(self.clone, "config", "remote.origin.partialclonefilter", "blob:none")
        self.git(self.clone, "fetch", "--filter=blob:none", "origin",
                 "+refs/heads/*:refs/remotes/origin/*", "+refs/tags/*:refs/tags/*")
        self.missing = self.inventory()
        self.assertEqual(len(self.missing), 2)

    def git(self, cwd, *args):
        result = subprocess.run(["git", *args], cwd=cwd, env=self.env,
                                capture_output=True, text=True, check=False)
        if result.returncode:
            self.fail("Synthetic Git setup failed")  # No raw diagnostics/IDs.
        return result.stdout

    def inventory(self):
        return {line[1:] for line in self.git(
            self.clone, "rev-list", "--objects", "--all", "--missing=print",
            "--no-object-names").splitlines() if line.startswith("?")}

    def program(self):
        step = yaml.load(WORKFLOW.read_text(), Loader=WorkflowLoader)["jobs"]["gitleaks"]["steps"][1]
        return step["run"].split("python3 - <<'PY'\n", 1)[1].split("\nPY", 1)[0]

    def run_program(self, fault=None):
        inventory = self.base / "security-object-inventory.txt"
        inventory.write_text(self.git(self.clone, "rev-list", "--objects", "--all",
                                     "--missing=print", "--no-object-names"))
        env = dict(self.env, RUNNER_TEMP=str(self.base), SECURITY_FETCH_AUTH="")
        program = self.program()
        if fault:
            # Fault injection only at the real subprocess boundary. All inventories
            # and post-transfer checks still execute Git on synthetic objects.
            prefix = """
import subprocess
_real_run = subprocess.run
def _fault_run(args, **kwargs):
    if '--missing=print-info' in args and FAULT == 'nonblob':
        result = _real_run(args, **kwargs)
        return subprocess.CompletedProcess(args, result.returncode,
                                           result.stdout.replace(b'type=blob', b'type=tree'))
    if 'fetch' in args:
        if FAULT == 'timeout':
            raise subprocess.TimeoutExpired(args, 120, output='synthetic-private-path')
        if FAULT == 'failure':
            return subprocess.CompletedProcess(args, 1, 'synthetic-private-path', 'synthetic-private-path')
        if FAULT == 'partial':
            kwargs['input'] = kwargs['input'].splitlines()[0] + b'\\n'
        if FAULT == 'empty':
            raise RuntimeError('unexpected fetch synthetic-private-path')
    return _real_run(args, **kwargs)
subprocess.run = _fault_run
"""
            program = prefix.replace("FAULT", repr(fault)) + program
        result = subprocess.run([sys.executable, "-c", program], cwd=self.clone,
                                env=env, capture_output=True, text=True, check=False)
        output = result.stdout + result.stderr
        self.assertNotIn("synthetic-private-path", output)
        self.assertNotIn("fixture.txt", output)
        for oid in self.missing:
            self.assertNotIn(oid, output)
        return result

    def test_published_omission_then_targeted_repair_preserves_history(self):
        self.git(self.source, "checkout", "--orphan", "event")
        self.git(self.source, "commit", "--allow-empty", "-m", "Event")
        event = self.git(self.source, "rev-parse", "HEAD").strip()
        self.git(self.source, "checkout", "main")
        self.git(self.source, "branch", "-D", "event")
        self.git(self.clone, "fetch", "--refetch", "--no-filter", "origin",
                 "+refs/heads/*:refs/remotes/origin/*", "+refs/tags/*:refs/tags/*",
                 f"+{event}:refs/ci/security-event")
        self.assertEqual(len(self.inventory()), 2)
        before = self.git(self.clone, "rev-list", "--all")
        refs = self.git(self.clone, "show-ref")
        objects_before = set(self.git(self.clone, "cat-file", "--batch-all-objects",
                                     "--batch-check=%(objectname)").splitlines())
        self.assertEqual(self.run_program().returncode, 0)
        self.assertEqual(self.inventory(), set())
        self.assertEqual(self.git(self.clone, "rev-list", "--all"), before)
        self.assertEqual(self.git(self.clone, "show-ref"), refs)
        objects_after = set(self.git(self.clone, "cat-file", "--batch-all-objects",
                                    "--batch-check=%(objectname)").splitlines())
        self.assertEqual(objects_after - objects_before, self.missing)
        output = self.git(self.clone, "log", "-p", *HISTORY_OPTIONS.split())
        self.assertIn("root-marker", output)
        self.assertIn("deleted-marker", output)

    def test_complete_empty_inventory_does_not_fetch(self):
        # Populate only synthetic missing blobs via the same stdin Git interface.
        subprocess.run(["git", "fetch", "--refetch", "--no-filter", "--no-tags", "--stdin", "origin"],
                       input=("\n".join(self.missing) + "\n").encode("ascii"), cwd=self.clone,
                       env=self.env, check=True, capture_output=True)
        self.assertEqual(self.run_program("empty").returncode, 0)

    def test_unreachable_remote_blob_is_not_transferred(self):
        (self.source / "unrelated.txt").write_text("unrelated-marker\n")
        self.git(self.source, "add", ".")
        self.git(self.source, "commit", "-m", "Unrequested")
        unrelated = self.git(self.source, "rev-parse", "HEAD:unrelated.txt").strip()
        self.assertEqual(self.run_program().returncode, 0)
        available = set(self.git(self.clone, "cat-file", "--batch-all-objects",
                                "--batch-check=%(objectname)").splitlines())
        self.assertNotIn(unrelated, available)

    def test_nonblob_inventory_is_rejected_without_transfer(self):
        self.assertNotEqual(self.run_program("nonblob").returncode, 0)
        self.assertEqual(len(self.inventory()), 2)

    def test_timeout_is_closed_and_quiet(self):
        self.assertNotEqual(self.run_program("timeout").returncode, 0)
        self.assertEqual(len(self.inventory()), 2)

    def test_fetch_failure_is_closed_and_quiet(self):
        self.assertNotEqual(self.run_program("failure").returncode, 0)
        self.assertEqual(len(self.inventory()), 2)

    def test_partial_transfer_is_closed(self):
        self.assertNotEqual(self.run_program("partial").returncode, 0)
        self.assertEqual(len(self.inventory()), 1)

    def test_nonpromised_missing_object_is_rejected_without_transfer(self):
        for marker in (self.clone / ".git" / "objects" / "pack").glob("*.promisor"):
            marker.unlink()
        self.git(self.clone, "config", "--unset", "remote.origin.promisor")
        self.git(self.clone, "config", "--unset", "remote.origin.partialclonefilter")
        self.assertNotEqual(self.run_program("empty").returncode, 0)
        self.assertEqual(len(self.inventory()), 2)


if __name__ == "__main__":
    unittest.main()
