from pathlib import Path
import copy
import re
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SPARSE_PATTERNS = ("/*", "!/test_coins/*", "/test_coins/README.md")
ARTIFACT_ALLOWLIST = {
    ("quality-advisory.yml", "pyright-advisory"): ("pyright-report.json",),
    ("mutmut-advisory.yml", "reviewer-mutation-pilot"): (
        "artifacts/mutmut-results.txt",
        "artifacts/mutmut-survivor-diffs.txt",
        "artifacts/mutmut-report.json",
    ),
}


class WorkflowLoader(yaml.SafeLoader):
    # GitHub's YAML uses `on` as a string, unlike YAML 1.1's boolean resolver.
    yaml_implicit_resolvers = copy.deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ValueError("Workflow keys must be unique strings")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


for initial, resolvers in WorkflowLoader.yaml_implicit_resolvers.items():
    WorkflowLoader.yaml_implicit_resolvers[initial] = [
        entry for entry in resolvers if entry[0] != "tag:yaml.org,2002:bool"
    ]
WorkflowLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$", re.IGNORECASE), list("tTfF")
)


def validate_workflow_privacy(text, filename):
    """Fail closed on ambiguous YAML and validate each checkout/upload step."""
    if any(isinstance(token, (yaml.AliasToken, yaml.AnchorToken)) for token in yaml.scan(text)):
        raise ValueError("Workflow aliases and anchors are not permitted")
    workflow = yaml.load(text, Loader=WorkflowLoader)
    if not isinstance(workflow, dict) or not isinstance(workflow.get("jobs"), dict):
        raise ValueError("Workflow must contain a jobs mapping")
    checkouts = 0
    for job_name, job in workflow["jobs"].items():
        if not isinstance(job, dict):
            raise ValueError("Job must be a mapping")
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            raise ValueError("Steps must be a list")
        for index, step in enumerate(steps):
            location = f"{filename}:{job_name}:step {index + 1}"
            if not isinstance(step, dict) or not isinstance(step.get("uses", ""), str):
                raise ValueError(f"{location}: invalid step")
            action = step.get("uses", "").lower()
            if not action.startswith(("actions/checkout@", "actions/upload-artifact@")):
                continue
            options = step.get("with", {})
            if not isinstance(options, dict):
                raise ValueError(f"{location}: with must be a mapping")
            if action.startswith("actions/checkout@"):
                checkouts += 1
                patterns = options.get("sparse-checkout")
                if not isinstance(patterns, str) or tuple(patterns.splitlines()) != SPARSE_PATTERNS:
                    raise ValueError(f"{location}: protected-image exclusions required")
                for key in ("sparse-checkout-cone-mode", "persist-credentials"):
                    if options.get(key) is not False:
                        raise ValueError(f"{location}: {key} must be false")
            else:
                paths = options.get("path")
                permitted = ARTIFACT_ALLOWLIST.get((filename, job_name))
                if not isinstance(paths, str) or permitted is None:
                    raise ValueError(f"{location}: artifact upload not permitted")
                if tuple(paths.splitlines()) != permitted:
                    raise ValueError(f"{location}: exact artifact allowlist required")
                if options.get("include-hidden-files", False) is not False:
                    raise ValueError(f"{location}: hidden artifact files not permitted")
    return checkouts
PRIVATE_ARTIFACT_NAMES = {
    "collection_backup_before_reimport.json",
    "collection_backup_encoding.json",
    "numista_export.xlsx",
}


class RepositoryPrivacyBoundaryTests(unittest.TestCase):
    def test_uncertain_images_are_documented_as_local_only(self):
        policy = (ROOT / "test_coins" / "README.md").read_text(encoding="utf-8")

        self.assertIn("UNCERTAIN /", policy)
        self.assertIn("LOCAL-ONLY", policy)
        self.assertIn("must not be uploaded", policy)

    def test_every_workflow_checkout_and_upload_obeys_privacy_policy(self):
        workflows = sorted(set(WORKFLOWS.glob("*.yml")) | set(WORKFLOWS.glob("*.yaml")))
        self.assertTrue(workflows)
        checkouts = 0
        for path in workflows:
            with self.subTest(workflow=path.name):
                checkouts += validate_workflow_privacy(path.read_text(encoding="utf-8"), path.name)
        self.assertGreater(checkouts, 0)

    def test_policy_rejects_each_unsafe_checkout_independently(self):
        checkout = {
            "uses": "actions/checkout@v4",
            "with": {
                "sparse-checkout": "\n".join(SPARSE_PATTERNS) + "\n",
                "sparse-checkout-cone-mode": False,
                "persist-credentials": False,
            },
        }
        invalid_options = [
            {},
            {"sparse-checkout": "/*\n/test_coins/README.md\n"},
            {"sparse-checkout": "\n".join(SPARSE_PATTERNS) + "\n/test_coins/nested/\n"},
            {"sparse-checkout-cone-mode": True},
            {"sparse-checkout-cone-mode": "false"},
            {"persist-credentials": True},
            {"persist-credentials": "false"},
        ]
        for changes in invalid_options:
            for key in (None, "sparse-checkout", "sparse-checkout-cone-mode", "persist-credentials"):
                unsafe = copy.deepcopy(checkout)
                if changes:
                    unsafe["with"].update(changes)
                elif key is None:
                    unsafe.pop("with")
                else:
                    unsafe["with"].pop(key)
                for position in (0, 1):
                    steps = [copy.deepcopy(checkout), copy.deepcopy(checkout)]
                    steps[position] = unsafe
                    for separate_jobs in (False, True):
                        jobs = {"first": {"steps": steps}}
                        if separate_jobs:
                            jobs = {str(i): {"steps": [step]} for i, step in enumerate(steps)}
                        with self.subTest(changes=changes, key=key, position=position, jobs=separate_jobs):
                            with self.assertRaises(ValueError):
                                validate_workflow_privacy(yaml.safe_dump({"jobs": jobs}), "tests.yml")
        self.assertEqual(validate_workflow_privacy(
            yaml.safe_dump({"jobs": {"valid": {"steps": [checkout]}}}), "tests.yml"
        ), 1)

    def test_policy_rejects_malformed_duplicate_and_ambiguous_yaml(self):
        fixtures = [
            "jobs: [", "jobs: {}\njobs: {}", "jobs: {one: {steps: [], steps: []}}",
            "jobs: {one: {steps: [{uses: actions/checkout@v4, with: {persist-credentials: false, persist-credentials: true}}]}}",
            "jobs: &jobs {}", "jobs: {one: {<<: {steps: []}}}",
            "jobs: []", "jobs: {one: {steps: {}}}", "jobs: {one: {steps: [null]}}",
            "jobs: {one: {steps: [{uses: actions/checkout@v4, with: []}]}}",
        ]
        for fixture in fixtures:
            with self.subTest(fixture=fixture), self.assertRaises((ValueError, yaml.YAMLError)):
                validate_workflow_privacy(fixture, "tests.yml")

    def test_artifact_policy_rejects_broadened_paths_and_unknown_jobs(self):
        for (filename, job), allowed in ARTIFACT_ALLOWLIST.items():
            def workflow(paths):
                return yaml.safe_dump({"jobs": {job: {"steps": [{
                    "uses": "actions/upload-artifact@v4", "with": {"path": paths}
                }]}}})
            validate_workflow_privacy(workflow("\n".join(allowed)), filename)
            for paths in ("artifacts/", "**/*", "test_coins/", "../report.json",
                          "${{ github.workspace }}", "\n".join((*allowed, "extra.txt"))):
                with self.subTest(filename=filename, paths=paths), self.assertRaises(ValueError):
                    validate_workflow_privacy(workflow(paths), filename)
            with self.assertRaises(ValueError):
                validate_workflow_privacy(workflow("\n".join(allowed)), "tests.yml")

    def test_sparse_checkout_materializes_only_readme_from_synthetic_image_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True,
                                      capture_output=True, text=True)
            git("init")
            files = ("source.py", "other/nested/source.py", "test_coins/README.md",
                     "test_coins/dummy.jpg", "test_coins/nested/dummy.jpg",
                     "test_coins/nested/deeper/dummy.txt", "test_coins/.hidden")
            for name in files:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic fixture\n", encoding="utf-8")
            git("add", "--", *files)
            git("-c", "user.name=Privacy Test", "-c", "user.email=privacy@example.invalid",
                "-c", "commit.gpgsign=false", "commit", "-m", "Synthetic fixtures")
            git("sparse-checkout", "set", "--no-cone", *SPARSE_PATTERNS)
            for name in files:
                with self.subTest(path=name):
                    self.assertEqual((root / name).exists(),
                                     not name.startswith("test_coins/") or name == "test_coins/README.md")

    def test_public_benchmark_manifests_do_not_reference_uncertain_images(self):
        for manifest in sorted((ROOT / "benchmarks").glob("*/manifest.json")):
            with self.subTest(manifest=manifest):
                text = manifest.read_text(encoding="utf-8")
                self.assertNotIn("test_coins/", text)
                self.assertNotIn("IMG_346", text)

    def test_known_private_exports_are_not_tracked(self):
        tracked = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()

        self.assertTrue(PRIVATE_ARTIFACT_NAMES.isdisjoint(Path(name).name for name in tracked))

    def test_known_private_exports_are_ignored_at_repository_root(self):
        rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

        self.assertTrue({f"/{name}" for name in PRIVATE_ARTIFACT_NAMES}.issubset(rules))


if __name__ == "__main__":
    unittest.main()
