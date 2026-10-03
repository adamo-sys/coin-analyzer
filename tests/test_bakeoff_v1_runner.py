"""Focused tests for reconstructed trusted Bake-Off V1 materialization."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.bakeoff_v1_candidate_state import (
    create_materialization_manifest,
    freeze_candidate_state,
    verify_frozen_worktree_copy,
)
from tools.bakeoff_v1_runner import (
    ReconstructedRunnerError,
    build_launcher_command,
    launcher_configuration_sha256,
    load_runner_specification,
    materialize_candidate,
    materialize_qualification_candidate,
    materializer_sha256,
    prepare_isolated_launcher_environment,
    prepare_sandbox_execution_paths,
    verify_candidate_isolation,
)


class ReconstructedRunnerTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def _source(self, directory: Path) -> tuple[Path, str, str]:
        source = directory / "source"
        source.mkdir()
        subprocess.run(["git", "-C", str(source), "init", "--quiet"], check=True)
        subprocess.run(["git", "-C", str(source), "config", "user.name", "Bake-Off test"], check=True)
        subprocess.run(["git", "-C", str(source), "config", "user.email", "bakeoff@example.invalid"], check=True)
        (source / "safe.txt").write_text("safe\n", encoding="utf-8")
        (source / "test_coins").mkdir()
        (source / "test_coins" / "README.md").write_text("allowed metadata\n", encoding="utf-8")
        (source / "test_coins" / "private.jpeg").write_bytes(b"private fixture bytes")
        (source / "test_coins" / "unlisted.jpeg").write_bytes(b"also private fixture bytes")
        (source / "benchmarks" / "bakeoff-v1" / "runs" / "RUN-004").mkdir(parents=True)
        (source / "benchmarks" / "bakeoff-v1" / "runs" / "RUN-004" / "retained-evidence.txt").write_text(
            "historical run evidence\n", encoding="utf-8"
        )
        subprocess.run(["git", "-C", str(source), "add", "--all"], check=True)
        subprocess.run(["git", "-C", str(source), "commit", "--quiet", "-m", "start"], check=True)
        start = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        private_blob = subprocess.run(
            ["git", "-C", str(source), "rev-parse", f"{start}:test_coins/private.jpeg"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return source, start, private_blob

    @staticmethod
    def _identity(start: str) -> dict[str, str]:
        return {
            "benchmark_id": "coin-analyzer-bakeoff-v1",
            "task_id": "DISPOSABLE-RUNNER-PROBE",
            "run_id": "disposable-runner-probe",
            "execution_protocol_version": "1.1",
            "starting_sha": start,
        }

    def test_materializes_a_standalone_candidate_without_the_protected_blob(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, start, private_blob = self._source(Path(directory))
            candidate = Path(directory) / "candidate"
            result = materialize_candidate(
                source_repository=source,
                candidate_repository=candidate,
                starting_sha=start,
                identity=self._identity(start),
                source_release="synthetic-source-release",
                protected_paths=["test_coins/private.jpeg"],
            )

            self.assertEqual(result["starting_sha"], start)
            self.assertEqual(result["protected_paths"], ["test_coins/private.jpeg", "test_coins/unlisted.jpeg"])
            self.assertFalse((candidate / "test_coins" / "private.jpeg").exists())
            self.assertFalse((candidate / "test_coins" / "unlisted.jpeg").exists())
            self.assertTrue((candidate / "test_coins" / "README.md").is_file())
            self.assertEqual(
                subprocess.run(["git", "-C", str(candidate), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip(),
                start,
            )
            self.assertNotEqual(
                subprocess.run(
                    ["git", "-C", str(candidate), "cat-file", "-e", f"{private_blob}^{{blob}}"],
                    capture_output=True,
                    check=False,
                ).returncode,
                0,
            )
            verify_candidate_isolation(candidate, protected_object_ids=[private_blob])

    def test_is_deterministic_and_compatible_with_the_v11_freezer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, start, _ = self._source(Path(directory))
            first = materialize_candidate(
                source_repository=source,
                candidate_repository=Path(directory) / "first",
                starting_sha=start,
                identity=self._identity(start),
                source_release="synthetic-source-release",
                protected_paths=["test_coins/private.jpeg"],
            )
            second = materialize_candidate(
                source_repository=source,
                candidate_repository=Path(directory) / "second",
                starting_sha=start,
                identity=self._identity(start),
                source_release="synthetic-source-release",
                protected_paths=["test_coins/private.jpeg"],
            )
            self.assertEqual(first, second)
            candidate = Path(directory) / "first"
            baseline = create_materialization_manifest(candidate, self._identity(start), protected_paths=["test_coins/private.jpeg"])
            frozen = freeze_candidate_state(candidate, self._identity(start), baseline)
            self.assertEqual(frozen["candidate_state_sha256"], freeze_candidate_state(candidate, self._identity(start), baseline)["candidate_state_sha256"])
            grading_copy = Path(directory) / "grading-copy"
            shutil.copytree(candidate, grading_copy, ignore=shutil.ignore_patterns(".git"))
            verify_frozen_worktree_copy(grading_copy, frozen, baseline)

    def test_rejects_an_existing_destination_and_an_isolation_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, start, private_blob = self._source(Path(directory))
            candidate = Path(directory) / "candidate"
            candidate.mkdir()
            with self.assertRaisesRegex(ReconstructedRunnerError, "must not exist"):
                materialize_candidate(
                    source_repository=source,
                    candidate_repository=candidate,
                    starting_sha=start,
                    identity=self._identity(start),
                    source_release="synthetic-source-release",
                    protected_paths=["test_coins/private.jpeg"],
                )
            candidate.rmdir()
            materialize_candidate(
                source_repository=source,
                candidate_repository=candidate,
                starting_sha=start,
                identity=self._identity(start),
                source_release="synthetic-source-release",
                protected_paths=["test_coins/private.jpeg"],
            )
            alternates = candidate / ".git" / "objects" / "info" / "alternates"
            alternates.parent.mkdir(parents=True, exist_ok=True)
            alternates.write_text(str(source / ".git" / "objects"), encoding="utf-8")
            with self.assertRaisesRegex(ReconstructedRunnerError, "alternates"):
                verify_candidate_isolation(candidate, protected_object_ids=[private_blob])

    def test_sealed_launcher_specification_binds_the_recovered_argument_order(self) -> None:
        specification_path = self.ROOT / "benchmarks" / "bakeoff-v1" / "orchestrator" / "reconstructed-runner-v1.json"
        specification = load_runner_specification(specification_path)
        self.assertEqual(specification["implementation_generation"], "reconstructed-materializer-v1")
        self.assertEqual(
            specification["infrastructure_discontinuity"],
            {
                "historical_runs": ["RUN-002", "RUN-003"],
                "historical_materializer": "implementation-A-unrecoverable",
                "future_runs": "RUN-004-onward",
                "launcher_discontinuity": {
                    "historical_run": "RUN-004",
                    "historical_launcher_generation": "launcher-b",
                    "historical_launcher_configuration_sha256": "01022c6092e312ea7f6eac01c69886abac5a1ad82dc9b3c42a69efb44f93cb27",
                    "future_runs": "RUN-005-onward",
                    "prospective_launcher_generation": "launcher-c",
                },
            },
        )
        self.assertEqual(specification["materializer"]["sha256"], materializer_sha256())
        self.assertEqual(specification["launcher_configuration_sha256"], launcher_configuration_sha256(specification))
        command = build_launcher_command(
            specification,
            candidate_repository=Path("C:/tmp/disposable-candidate"),
            final_output=Path("C:/tmp/disposable-evidence/final.txt"),
        )
        self.assertEqual(command[0], "C:/Program Files/nodejs/node.exe")
        self.assertEqual(command[1:4], [
            "C:/Users/adamo/AppData/Roaming/npm/node_modules/@openai/codex/bin/codex.js",
            "-c",
            'web_search="disabled"',
        ])
        self.assertEqual(command[4:10], [
            "-c",
            "features.skip_host_skill_discovery=true",
            "--disable",
            "browser_use_external",
            "--disable",
            "browser_use_full_cdp_access",
        ])
        self.assertEqual(command[10:13], ["--approve-for-me", "-C", "C:/tmp/disposable-candidate"])
        self.assertNotIn("-s", command)
        self.assertNotIn("workspace-write", command)
        self.assertNotIn("-a", command)
        self.assertNotIn("never", command)
        self.assertEqual(command[13:], [
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--json",
            "-o",
            "C:/tmp/disposable-evidence/final.txt",
            "-",
        ])

    def test_rejects_a_launcher_that_combines_auto_approval_with_legacy_approval_or_sandbox_arguments(self) -> None:
        specification_path = self.ROOT / "benchmarks" / "bakeoff-v1" / "orchestrator" / "reconstructed-runner-v1.json"
        payload = json.loads(specification_path.read_text(encoding="utf-8"))
        payload["launcher"]["global_arguments"] = [
            "--approve-for-me",
            "-s",
            "workspace-write",
            "-a",
            "never",
            "-C",
            "{candidate}",
            "exec",
        ]
        payload["launcher_configuration_sha256"] = launcher_configuration_sha256(payload)
        with tempfile.TemporaryDirectory() as directory:
            conflicting_specification = Path(directory) / "runner.json"
            conflicting_specification.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ReconstructedRunnerError, "approval/sandbox"):
                load_runner_specification(conflicting_specification)

    def test_qualification_materialization_excludes_the_entire_scored_runs_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, start, _ = self._source(root)
            candidate = root / "candidate"
            materialize_qualification_candidate(
                source_repository=source,
                candidate_repository=candidate,
                starting_sha=start,
                identity=self._identity(start),
                source_release="synthetic-source-release",
                protected_paths=[],
            )
            self.assertFalse((candidate / "benchmarks" / "bakeoff-v1" / "runs").exists())

    def test_isolated_launcher_environment_copies_only_authentication_into_a_fresh_codex_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_home = root / "source-codex-home"
            source_home.mkdir()
            (source_home / "auth.json").write_text('{"token":"synthetic"}', encoding="utf-8")
            isolated_home = root / "isolated-codex-home"
            environment = prepare_isolated_launcher_environment(
                source_codex_home=source_home,
                isolated_codex_home=isolated_home,
            )
            self.assertEqual(environment, {"CODEX_HOME": str(isolated_home.resolve())})
            self.assertEqual((isolated_home / "auth.json").read_text(encoding="utf-8"), '{"token":"synthetic"}')
            self.assertEqual([path.name for path in isolated_home.iterdir()], ["auth.json"])

    def test_prepares_only_the_disposable_candidate_and_evidence_paths_for_the_sandbox(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate"
            candidate.mkdir()
            evidence = root / "evidence"
            with patch("tools.bakeoff_v1_runner.subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess([], 0)
                environment = prepare_sandbox_execution_paths(candidate_repository=candidate, evidence_directory=evidence)
            self.assertTrue(evidence.is_dir())
            self.assertEqual(environment["GIT_CONFIG_COUNT"], "1")
            self.assertEqual(environment["GIT_CONFIG_KEY_0"], "safe.directory")
            self.assertEqual(environment["GIT_CONFIG_VALUE_0"], candidate.resolve().as_posix())
            self.assertEqual(run.call_count, 2)
            for call in run.call_args_list:
                self.assertEqual(call.args[0][0], "icacls")
                self.assertIn(str(candidate.resolve()) if call is run.call_args_list[0] else str(evidence.resolve()), call.args[0])


if __name__ == "__main__":
    unittest.main()
