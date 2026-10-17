"""Small static and synthetic guards for the inspected blocking CI boundary."""

import copy
import re
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

import tomllib
import yaml

from tests.test_repository_privacy_boundaries import (
    WorkflowLoader,
    validate_workflow_privacy,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
HISTORY_OPTIONS = "--full-history --all --root -m --no-ext-diff --no-textconv"
SCAN_COMMAND = (
    '"$RUNNER_TEMP/gitleaks/gitleaks" git . --config=.gitleaks.toml '
    f'--log-opts="{HISTORY_OPTIONS}" --redact=100 --exit-code=2 --log-level=info'
)
ALLOWED_ACTIONS = {
    "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
}


def script_commands(script):
    return [line.strip() for line in script.replace("\\\n", "").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def validate_tests_security(text):
    """Pin inspected controls; this does not establish protected-data confidentiality."""
    validate_workflow_privacy(text, "tests.yml")
    if re.search(r"\$\{\{[^}]*\bsecrets\b", text, re.IGNORECASE):
        raise ValueError("Tests must not expose repository secrets to PR code")
    workflow = yaml.load(text, Loader=WorkflowLoader)
    if workflow.get("on") != {"push": None, "pull_request": None, "workflow_dispatch": None}:
        raise ValueError("Tests must use the unfiltered, unprivileged event set")
    if workflow.get("permissions") != {"contents": "read"}:
        raise ValueError("Tests permissions must be contents: read only")
    jobs = workflow["jobs"]
    if "gitleaks" not in jobs:
        raise ValueError("Blocking Gitleaks job required")
    for job in jobs.values():
        if "permissions" in job and job["permissions"] != {"contents": "read"}:
            raise ValueError("Job permissions must not expand token authority")
        if "uses" in job or "secrets" in job:
            raise ValueError("Unreviewed reusable workflow or inherited secrets")
        for step in job.get("steps", []):
            if "uses" in step and step["uses"] not in ALLOWED_ACTIONS:
                raise ValueError("Unreviewed action or embedded publication")
    job = jobs["gitleaks"]
    if any(key in job for key in ("if", "continue-on-error", "needs", "strategy", "env")):
        raise ValueError("Gitleaks must run unconditionally and remain blocking")
    if "env" in workflow:
        raise ValueError("Unreviewed global environment")
    steps = job.get("steps", [])
    if len(steps) != 4:
        raise ValueError("Gitleaks requires checkout, object preparation, binary, and scan")
    checkout, objects, binary, scan = steps
    if not checkout.get("uses", "").startswith("actions/checkout@"):
        raise ValueError("Gitleaks requires checkout before scanning")
    depth = checkout.get("with", {}).get("fetch-depth")
    if type(depth) is not int or depth != 0:
        raise ValueError("Gitleaks checkout must retain full commit history")
    for step in steps:
        if any(key in step for key in ("if", "continue-on-error")):
            raise ValueError("Security steps must not skip or suppress failures")
    for step in (objects, binary, scan):
        if step.get("shell") != "bash" or not step.get("run", "").startswith("set -euo pipefail\n"):
            raise ValueError("Security scripts require explicit Bash failure propagation")
    if objects.get("env") != {"CI_TOKEN": "${{ github.token }}", "CI_SHA": "${{ github.sha }}"}:
        raise ValueError("Object fetch uses only the read token and event SHA")
    required = (
        'fetch --refetch --no-filter origin',
        "'+refs/heads/*:refs/remotes/origin/*' '+refs/tags/*:refs/tags/*'",
        '"+$CI_SHA:refs/ci/security-event"',
        'unset auth CI_TOKEN',
        'test "$(git rev-parse --is-shallow-repository)" = false',
        'git rev-list --objects --all --missing=print --no-object-names > "$RUNNER_TEMP/security-object-inventory.txt"',
        "if grep -q '^?'",
        'exit 1',
        'export GIT_NO_LAZY_FETCH=1 GIT_TERMINAL_PROMPT=0',
        '"--missing=allow-promisor"',
        '"--missing=print-info"',
        '"--no-recurse-submodules", "--no-write-fetch-head", "--refmap="',
        '"--stdin", "origin"',
        'stderr=subprocess.DEVNULL',
        'timeout=120',
        'if blobs != missing:',
        'if missing_ids(complete):',
    )
    if any(part not in objects["run"] for part in required):
        raise ValueError("Full-history object preparation and completeness gates required")
    if binary.get("env") or any(part not in binary["run"] for part in (
        'curl --fail --silent --show-error --location',
        'https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz',
        "9991e0b2903da4c8f6122b5c3186448b927a5da4deef1fe45271c3793f4ee29c  gitleaks.tar.gz",
        'sha256sum --check --strict',
        'tar -xzf gitleaks.tar.gz gitleaks',
    )):
        raise ValueError("Inspected scanner download and checksum required")
    if scan.get("env") != {"GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"}:
        raise ValueError("Scan must not receive credentials or allow lazy hydration")
    commands = script_commands(scan["run"])
    if len(commands) != 2 or commands[0] != "set -euo pipefail" or shlex.split(commands[1]) != shlex.split(SCAN_COMMAND):
        raise ValueError("Exact full-history redacted blocking scan required")


class TestsWorkflowSecurityTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.workflow = yaml.load(self.text, Loader=WorkflowLoader)

    def assert_rejected(self, workflow):
        with self.assertRaises(ValueError):
            validate_tests_security(yaml.safe_dump(workflow))

    def test_blocking_tests_controls(self):
        validate_tests_security(self.text)

    def test_explicit_and_embedded_artifact_actions_are_rejected(self):
        for name in self.workflow["jobs"]:
            for action in ("actions/upload-artifact@v4", "gitleaks/gitleaks-action@v3"):
                workflow = copy.deepcopy(self.workflow)
                workflow["jobs"][name]["steps"].append({"uses": action, "with": {"path": "synthetic.txt"}})
                with self.subTest(job=name, action=action):
                    self.assert_rejected(workflow)

    def test_security_steps_cannot_be_skipped_or_made_nonblocking(self):
        for target in ("job", 0, 1, 2, 3):
            for key, value in (("continue-on-error", True), ("if", "false")):
                workflow = copy.deepcopy(self.workflow)
                job = workflow["jobs"]["gitleaks"]
                node = job if target == "job" else job["steps"][target]
                node[key] = value
                with self.subTest(target=target, key=key):
                    self.assert_rejected(workflow)
        workflow = copy.deepcopy(self.workflow)
        del workflow["jobs"]["gitleaks"]
        self.assert_rejected(workflow)

    def test_history_coverage_and_failure_suppression_mutations_are_rejected(self):
        for old, new in ((HISTORY_OPTIONS, "HEAD^..HEAD"), ("--all", "--first-parent"),
                         ("--root -m", "--root"), ("--redact=100", "--redact=0"),
                         ("--exit-code=2", "--exit-code=0"), ("--log-level=info", "--verbose"),
                         ("--log-level=info", "--report-path=results.sarif"),
                         ("set -euo pipefail", "set +e")):
            workflow = copy.deepcopy(self.workflow)
            scan = workflow["jobs"]["gitleaks"]["steps"][3]
            scan["run"] = scan["run"].replace(old, new)
            with self.subTest(old=old, new=new):
                self.assert_rejected(workflow)
        for suffix in (" || true", "\nexit 0", "\necho upload"):
            workflow = copy.deepcopy(self.workflow)
            workflow["jobs"]["gitleaks"]["steps"][3]["run"] += suffix
            self.assert_rejected(workflow)

    def test_history_and_object_availability_cannot_be_weakened(self):
        for depth in (None, 1, "0", False):
            workflow = copy.deepcopy(self.workflow)
            options = workflow["jobs"]["gitleaks"]["steps"][0]["with"]
            if depth is None:
                options.pop("fetch-depth")
            else:
                options["fetch-depth"] = depth
            with self.subTest(depth=depth):
                self.assert_rejected(workflow)
        for token in ("--no-filter", "--refetch", "--missing=print", "exit 1", "unset auth CI_TOKEN"):
            workflow = copy.deepcopy(self.workflow)
            step = workflow["jobs"]["gitleaks"]["steps"][1]
            step["run"] = step["run"].replace(token, "")
            with self.subTest(token=token):
                self.assert_rejected(workflow)

    def test_targeted_hydration_controls_cannot_be_removed(self):
        for token in ('"--missing=allow-promisor"', '"--missing=print-info"',
                      '"--stdin", "origin"', '"--no-recurse-submodules"',
                      '"--no-write-fetch-head"', '"--refmap="',
                      'if blobs != missing:', 'if missing_ids(complete):',
                      'export GIT_NO_LAZY_FETCH=1 GIT_TERMINAL_PROMPT=0'):
            workflow = copy.deepcopy(self.workflow)
            step = workflow["jobs"]["gitleaks"]["steps"][1]
            step["run"] = step["run"].replace(token, "")
            with self.subTest(token=token):
                self.assert_rejected(workflow)

    def test_permissions_privileged_events_and_scan_credentials_are_rejected(self):
        for permissions in (None, "write-all", {"contents": "write"},
                            {"contents": "read", "id-token": "write"}):
            workflow = copy.deepcopy(self.workflow)
            workflow["permissions"] = permissions
            self.assert_rejected(workflow)
            for name in self.workflow["jobs"]:
                workflow = copy.deepcopy(self.workflow)
                workflow["jobs"][name]["permissions"] = permissions
                self.assert_rejected(workflow)
        for event in ("pull_request_target", "workflow_run"):
            workflow = copy.deepcopy(self.workflow)
            workflow["on"][event] = None
            self.assert_rejected(workflow)
        workflow = copy.deepcopy(self.workflow)
        workflow["jobs"]["gitleaks"]["steps"][3]["env"]["GITHUB_TOKEN"] = "${{ github.token }}"
        self.assert_rejected(workflow)
        for reference in ("${{ secrets.PROVIDER_KEY }}", "${{ secrets['PROVIDER_KEY'] }}", "${{ toJSON(secrets) }}"):
            for name in self.workflow["jobs"]:
                workflow = copy.deepcopy(self.workflow)
                workflow["jobs"][name]["steps"][-1]["env"] = {"SYNTHETIC": reference}
                with self.subTest(job=name, reference=reference):
                    self.assert_rejected(workflow)

    def test_pinned_binary_and_default_detection_rules(self):
        config = tomllib.loads((ROOT / ".gitleaks.toml").read_text(encoding="utf-8"))
        self.assertEqual(config.get("extend"), {"useDefault": True})
        for token in ("sha256sum --check --strict", "9991e0b2903da4c8f6122b5c3186448b927a5da4deef1fe45271c3793f4ee29c"):
            workflow = copy.deepcopy(self.workflow)
            step = workflow["jobs"]["gitleaks"]["steps"][2]
            step["run"] = step["run"].replace(token, "")
            self.assert_rejected(workflow)

    def test_history_options_include_root_deleted_side_branch_and_merge_only_text(self):
        # Exercise Git selection with harmless text, never the repository's objects.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout
            git("init", "-b", "main")
            git("config", "user.name", "Synthetic CI")
            git("config", "user.email", "ci@example.invalid")
            git("config", "commit.gpgsign", "false")
            def commit(text):
                (root / "fixture.txt").write_text(text, encoding="utf-8")
                git("add", "fixture.txt")
                git("commit", "-m", "Synthetic fixture")
            commit("root-marker\n")
            git("checkout", "-b", "side")
            commit("root-marker\nside-marker\n")
            git("checkout", "main")
            commit("root-marker\nmain-marker\n")
            result = subprocess.run(["git", "merge", "--no-commit", "side"], cwd=root, capture_output=True, check=False)
            self.assertNotEqual(result.returncode, 0)  # Synthetic conflict resolved only in merge.
            commit("root-marker\nmain-marker\nside-marker\nmerge-marker\n")
            (root / "fixture.txt").unlink()
            git("add", "fixture.txt")
            git("commit", "-m", "Synthetic deletion")
            git("checkout", "--orphan", "unmerged")
            commit("unmerged-marker\n")
            git("checkout", "main")
            output = git("log", "-p", "-U0", *HISTORY_OPTIONS.split())
            for marker in ("root-marker", "side-marker", "merge-marker", "unmerged-marker"):
                self.assertIn(marker, output)
            limited = git("log", "-p", "-U0", "HEAD^..HEAD")
            self.assertNotIn("unmerged-marker", limited)


if __name__ == "__main__":
    unittest.main()
