"""Focused tests for privacy-safe uncommitted Bake-Off candidate freezing."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.bakeoff_v1_candidate_state import (
    CandidateStateError,
    create_materialization_manifest,
    freeze_candidate_state,
    verify_frozen_worktree_copy,
)


class CandidateStateTests(unittest.TestCase):
    def _candidate(self, directory: Path) -> tuple[Path, str]:
        candidate = directory / "candidate"
        candidate.mkdir()
        subprocess.run(["git", "-C", str(candidate), "init", "--quiet"], check=True)
        subprocess.run(["git", "-C", str(candidate), "config", "user.name", "Bake-Off test"], check=True)
        subprocess.run(["git", "-C", str(candidate), "config", "user.email", "bakeoff@example.invalid"], check=True)
        (candidate / "allowed.txt").write_text("before\n", encoding="utf-8")
        (candidate / "delete.txt").write_text("delete\n", encoding="utf-8")
        (candidate / "test_coins").mkdir()
        (candidate / "test_coins" / "README.md").write_text("permitted metadata\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(candidate), "add", "--all"], check=True)
        subprocess.run(["git", "-C", str(candidate), "commit", "--quiet", "-m", "start"], check=True)
        start = subprocess.run(["git", "-C", str(candidate), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        return candidate, start

    def _identity(self, start: str) -> dict[str, str]:
        return {
            "benchmark_id": "coin-analyzer-bakeoff-v1",
            "task_id": "BO1-TAMPER-BATCH",
            "run_id": "run-002",
            "execution_protocol_version": "1.1",
            "starting_sha": start,
        }

    def test_freeze_is_reproducible_and_derives_modified_added_and_deleted_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate, start = self._candidate(Path(directory))
            baseline = create_materialization_manifest(candidate, self._identity(start), protected_paths=["test_coins/IMG_3460.jpeg"])
            (candidate / "allowed.txt").write_text("after\n", encoding="utf-8")
            (candidate / "delete.txt").unlink()
            (candidate / "added.txt").write_text("new\n", encoding="utf-8")

            first = freeze_candidate_state(candidate, self._identity(start), baseline)
            second = freeze_candidate_state(candidate, self._identity(start), baseline)

        self.assertEqual(first["candidate_state_sha256"], second["candidate_state_sha256"])
        self.assertEqual(first["modified_paths"], ["allowed.txt"])
        self.assertEqual(first["added_paths"], ["added.txt"])
        self.assertEqual(first["deleted_paths"], ["delete.txt"])
        self.assertNotIn("test_coins/IMG_3460.jpeg", first["deleted_paths"])

    def test_freeze_rejects_materialized_protected_path_without_reading_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate, start = self._candidate(Path(directory))
            baseline = create_materialization_manifest(candidate, self._identity(start), protected_paths=["test_coins/IMG_3460.jpeg"])
            (candidate / "test_coins" / "IMG_3460.jpeg").write_bytes(b"synthetic-test-only")
            with self.assertRaisesRegex(CandidateStateError, "protected path"):
                freeze_candidate_state(candidate, self._identity(start), baseline)

    def test_freeze_enforces_the_protected_category_even_when_not_caller_listed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate, start = self._candidate(Path(directory))
            baseline = create_materialization_manifest(candidate, self._identity(start), protected_paths=[])
            (candidate / "test_coins" / "unlisted.jpeg").write_bytes(b"synthetic-test-only")
            with self.assertRaisesRegex(CandidateStateError, "protected path"):
                freeze_candidate_state(candidate, self._identity(start), baseline)

    def test_freeze_rejects_staged_index_that_disagrees_with_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate, start = self._candidate(Path(directory))
            baseline = create_materialization_manifest(candidate, self._identity(start), protected_paths=[])
            (candidate / "allowed.txt").write_text("staged\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(candidate), "add", "allowed.txt"], check=True)
            (candidate / "allowed.txt").write_text("unstaged-after-staging\n", encoding="utf-8")
            with self.assertRaisesRegex(CandidateStateError, "index/worktree"):
                freeze_candidate_state(candidate, self._identity(start), baseline)

    def test_freeze_accepts_a_staged_file_when_index_matches_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate, start = self._candidate(Path(directory))
            baseline = create_materialization_manifest(candidate, self._identity(start), protected_paths=[])
            (candidate / "allowed.txt").write_text("staged\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(candidate), "add", "allowed.txt"], check=True)
            frozen = freeze_candidate_state(candidate, self._identity(start), baseline)
        self.assertEqual(frozen["modified_paths"], ["allowed.txt"])

    def test_freeze_rejects_mutation_between_the_two_collections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate, start = self._candidate(Path(directory))
            baseline = create_materialization_manifest(candidate, self._identity(start), protected_paths=[])
            with (
                patch("tools.bakeoff_v1_candidate_state._collect_candidate_state", side_effect=[{"marker": "one"}, {"marker": "two"}]),
                self.assertRaisesRegex(CandidateStateError, "changed during freeze"),
            ):
                freeze_candidate_state(candidate, self._identity(start), baseline)

    def test_materialization_manifest_rejects_unsafe_protected_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate, start = self._candidate(Path(directory))
            with self.assertRaisesRegex(CandidateStateError, "safe relative"):
                create_materialization_manifest(candidate, self._identity(start), protected_paths=["../test_coins/IMG_3460.jpeg"])

    def test_grading_copy_must_match_the_frozen_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate, start = self._candidate(Path(directory))
            baseline = create_materialization_manifest(candidate, self._identity(start), protected_paths=[])
            (candidate / "allowed.txt").write_text("after\n", encoding="utf-8")
            frozen = freeze_candidate_state(candidate, self._identity(start), baseline)
            grading_copy = Path(directory) / "grading-copy"
            shutil.copytree(candidate, grading_copy, ignore=shutil.ignore_patterns(".git"))
            verify_frozen_worktree_copy(grading_copy, frozen, baseline)
            (grading_copy / "allowed.txt").write_text("different\n", encoding="utf-8")
            with self.assertRaisesRegex(CandidateStateError, "grading copy"):
                verify_frozen_worktree_copy(grading_copy, frozen, baseline)


if __name__ == "__main__":
    unittest.main()
