import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import ExitStack, contextmanager, nullcontext
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from tests.test_bakeoff_v1_final_acceptance import encoded, finding, fixture
from tests.test_bakeoff_v1_run_ledger import valid_record, valid_v11_record
from tools.bakeoff_v1_final_acceptance import evaluate_final_acceptance
from tools import bakeoff_v1_grader as grader
from tools.bakeoff_v1_candidate_state import (
    create_materialization_manifest,
    freeze_candidate_state,
)
from tools.bakeoff_v1_grader import (
    _canonical_digest,
    _execute_checks,
    _grade_collected_evidence,
    _independent_acceptance,
    collect_grading_evidence,
    grade_run,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks" / "bakeoff-v1" / "manifest.json"
SIDECAR = ROOT / "benchmarks" / "bakeoff-v1" / "manifest.sha256"
EXPECTED_CORPUS_SEAL = "b5627a727fb283e0eefa8156c51a93124b044f764b6dab48041b08f30df9a776"
START = "9369b3f6d830d2f0ee7fe41cdabc8c57d7b77612"
END = "2f18d5fd7b1227f13aaee24467950353a77e8fee"
TAMPER_START = "ad1401aa63177ce754212241db6a7c6ee0788a8d"
TAMPER_END = "d068be2f7f152c49c779b66e595ebadf50661bdb"
_EXCLUDED_IMAGE_BLOB = "82baba277de116060acdde417884f763181f24dc"
_HISTORICAL_CANDIDATES = {
    END: {
        "start": START,
        "paths": (
            ".gitignore",
            ".ops/outcome-packet.schema.json",
            ".ops/outcome-packet.template.json",
            ".ops/task-packet.schema.json",
            ".ops/task-packet.template.json",
            "docs/CODEX_WORKFLOW.md",
            "tests/test_task_packet.py",
            "tools/task-packet.py",
        ),
    },
    TAMPER_END: {
        "start": TAMPER_START,
        "paths": (
            ".gitignore",
            "ai_evaluation_contracts.py",
            "ai_evaluation_evaluator.py",
            "identification_adversarial_tamper_harness.py",
            "identification_specialist.py",
            "identification_specialist_evaluation_adapter.py",
            "identification_specialist_verifier.py",
            "identification_verification_evaluation_batch.py",
            "identification_verification_evaluation_report.py",
            "test_identification_adversarial_tamper_harness.py",
            "test_identification_verification_evaluation_batch.py",
        ),
    },
}


def _git_bytes(repository: Path, arguments: list[str]) -> bytes:
    return subprocess.run(["git", "-C", str(repository), *arguments], capture_output=True, check=True).stdout


def _copy_source_object(candidate: Path, object_sha: str) -> bytes:
    """Copy one explicitly selected non-private object without Git transport."""
    if object_sha == _EXCLUDED_IMAGE_BLOB:
        raise AssertionError("the local-only image blob is never candidate material")
    object_type = _git_bytes(ROOT, ["cat-file", "-t", object_sha]).decode("ascii").strip()
    contents = _git_bytes(ROOT, ["cat-file", object_type, object_sha])
    written = subprocess.run(
        ["git", "-C", str(candidate), "hash-object", "-w", "-t", object_type, "--stdin"],
        input=contents,
        capture_output=True,
        check=True,
    ).stdout.decode("ascii").strip()
    if written != object_sha:
        raise AssertionError("candidate object identity changed during bounded materialization")
    return contents


def _copy_history_commits(candidate: Path, start: str, end: str) -> None:
    pending = [end]
    copied: set[str] = set()
    while pending:
        commit = pending.pop()
        if commit in copied:
            continue
        contents = _copy_source_object(candidate, commit).decode("utf-8")
        copied.add(commit)
        if commit == start:
            continue
        parents = [line.split()[1] for line in contents.splitlines() if line.startswith("parent ")]
        if not parents or len(copied) > 16:
            raise AssertionError("frozen history closure is not bounded by its declared starting commit")
        pending.extend(parents)
    if start not in copied:
        raise AssertionError("frozen starting commit is absent from candidate history")


def _copy_endpoint_trees(candidate: Path, endpoint: str) -> None:
    root_tree = _git_bytes(ROOT, ["rev-parse", f"{endpoint}^{{tree}}"]).decode("ascii").strip()
    tree_objects = {root_tree}
    for line in _git_bytes(ROOT, ["ls-tree", "-r", "-t", endpoint]).decode("utf-8").splitlines():
        metadata, _ = line.split("\t", 1)
        _, object_type, object_sha = metadata.split()
        if object_type == "tree":
            tree_objects.add(object_sha)
    for object_sha in tree_objects:
        _copy_source_object(candidate, object_sha)


def _copy_path_blob(candidate: Path, endpoint: str, path: str) -> None:
    if path.startswith("test_coins/"):
        raise AssertionError("local-only image paths are never candidate material")
    result = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", f"{endpoint}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        _copy_source_object(candidate, result.stdout.strip())


def _materialize_bounded_worktree(repository: Path, ending_sha: str, paths: tuple[str, ...]) -> None:
    """Populate only selected paths while marking every other tracked path skipped."""
    tracked_paths = _git_bytes(repository, ["ls-tree", "-r", "--name-only", ending_sha]).decode("utf-8").splitlines()
    selected = set(paths)
    subprocess.run(["git", "-C", str(repository), "config", "core.sparseCheckout", "true"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "read-tree", ending_sha],
        check=True,
    )
    skipped = [path for path in tracked_paths if path not in selected]
    subprocess.run(
        ["git", "-C", str(repository), "update-index", "--skip-worktree", "--stdin"],
        input=("\n".join(skipped) + "\n").encode("utf-8"),
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "checkout-index", "--force", "--stdin"],
        input=("\n".join(paths) + "\n").encode("utf-8"),
        check=True,
    )


def _historical_candidate(directory: Path, ending_sha: str) -> Path:
    """Create a real, sparse candidate from the frozen task's safe object closure."""
    specification = _HISTORICAL_CANDIDATES[ending_sha]
    start = str(specification["start"])
    paths = tuple(specification["paths"])
    candidate = directory / "candidate"
    subprocess.run(["git", "init", "--quiet", str(candidate)], check=True)
    _copy_history_commits(candidate, start, ending_sha)
    for endpoint in (start, ending_sha):
        _copy_endpoint_trees(candidate, endpoint)
    changed_paths = _git_bytes(ROOT, ["diff", "--name-only", start, ending_sha]).decode("utf-8").splitlines()
    for endpoint in (start, ending_sha):
        for path in {*paths, *changed_paths}:
            _copy_path_blob(candidate, endpoint, path)
    reference = f"refs/bakeoff/reference/{ending_sha}"
    subprocess.run(["git", "-C", str(candidate), "update-ref", reference, ending_sha], check=True)
    subprocess.run(["git", "-C", str(candidate), "symbolic-ref", "HEAD", reference], check=True)
    (candidate / ".git" / "shallow").write_text(f"{start}\n", encoding="ascii")
    _materialize_bounded_worktree(candidate, ending_sha, paths)
    return candidate


def _uncommitted_task_packet_candidate(directory: Path) -> Path:
    """Create a trusted test-only candidate whose HEAD remains at the task start."""
    candidate = _historical_candidate(directory, END)
    reference = "refs/heads/bakeoff-contestant"
    subprocess.run(["git", "-C", str(candidate), "update-ref", reference, START], check=True)
    subprocess.run(["git", "-C", str(candidate), "symbolic-ref", "HEAD", reference], check=True)
    for child in candidate.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    start_paths = tuple(
        path
        for path in _HISTORICAL_CANDIDATES[END]["paths"]
        if subprocess.run(["git", "-C", str(candidate), "cat-file", "-e", f"{START}:{path}"], capture_output=True, check=False).returncode == 0
    )
    _materialize_bounded_worktree(candidate, START, start_paths)
    return candidate


class GraderTests(unittest.TestCase):
    def test_grade_run_rejects_missing_external_corpus_seal(self) -> None:
        result = grade_run(self._record(), MANIFEST, SIDECAR, candidate_repository=self.candidate, check_inputs=self._inputs(), expected_corpus_seal=None)
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("external corpus seal", result["invalid_reasons"][0])

    @classmethod
    def setUpClass(cls) -> None:
        cls._candidate_directory = tempfile.TemporaryDirectory()
        cls.candidate = _historical_candidate(Path(cls._candidate_directory.name), END)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._candidate_directory.cleanup()

    def test_historical_candidate_is_object_bounded_and_excludes_local_only_images(self) -> None:
        alternates = self.candidate / ".git" / "objects" / "info" / "alternates"
        self.assertFalse(alternates.exists())
        self.assertFalse(
            subprocess.run(
                ["git", "-C", str(self.candidate), "remote"],
                capture_output=True,
                check=True,
            ).stdout.strip()
        )
        self.assertFalse((self.candidate / "test_coins" / "IMG_3460.jpeg").exists())
        self.assertNotEqual(
            subprocess.run(
                ["git", "-C", str(self.candidate), "cat-file", "-e", "82baba277de116060acdde417884f763181f24dc"],
                capture_output=True,
                check=False,
            ).returncode,
            0,
        )
        self.assertEqual(
            subprocess.run(
                ["git", "-C", str(self.candidate), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip(),
            END,
        )
        self._assert_historical_refs(self.candidate, START, END)
        with tempfile.TemporaryDirectory() as directory:
            self._assert_historical_refs(_historical_candidate(Path(directory), TAMPER_END), TAMPER_START, TAMPER_END)

    def _assert_historical_refs(self, candidate: Path, start: str, end: str) -> None:
        subprocess.run(
            ["git", "-C", str(candidate), "rev-parse", f"{start}^{{commit}}", f"{end}^{{commit}}"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertTrue(
            subprocess.run(
                ["git", "-C", str(candidate), "diff", "--name-only", start, end],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )

    def _record(self, ending_sha: str = END) -> dict[str, object]:
        record = valid_record()
        record["ending_sha"] = ending_sha
        return record

    def _inputs(self) -> dict[str, dict[str, str]]:
        return {
            "python -B tools/task-packet.py validate --kind task --path <task-packet>": {"<task-packet>": ".ops/task-packet.template.json"},
            "python -B tools/task-packet.py validate --kind outcome --path <outcome-packet>": {"<outcome-packet>": ".ops/outcome-packet.template.json"},
        }

    def _v11_identity(self) -> dict[str, str]:
        return {
            "benchmark_id": "coin-analyzer-bakeoff-v1",
            "task_id": "BO1-TASK-PACKETS",
            "run_id": "bo1-task-packets-native-001",
            "execution_protocol_version": "1.1",
            "starting_sha": START,
        }

    def _write_reference_task_packet_solution(self, candidate: Path) -> None:
        for path in _HISTORICAL_CANDIDATES[END]["paths"]:
            source = _git_bytes(ROOT, ["show", f"{END}:{path}"])
            target = candidate / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source)

    @contextmanager
    def _candidate_variant(self):
        """Yield one cheap, clean, committed candidate variant for a real grade."""
        with tempfile.TemporaryDirectory() as directory:
            yield _historical_candidate(Path(directory), END)

    def _commit_variant(self, candidate: Path) -> str:
        subprocess.run(["git", "-C", str(candidate), "add", "--all"], check=True)
        tree = _git_bytes(candidate, ["write-tree", "--missing-ok"]).decode("ascii").strip()
        commit = subprocess.run(
            ["git", "-C", str(candidate), "-c", "user.name=Bake-Off Test", "-c", "user.email=bakeoff-test@example.invalid", "commit-tree", tree, "-p", END, "-m", "test candidate variant"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        subprocess.run(["git", "-C", str(candidate), "update-ref", "HEAD", commit], check=True)
        status = _git_bytes(candidate, ["status", "--porcelain=v1"])
        if status:
            raise AssertionError(f"candidate variant is unexpectedly dirty: {status.decode('utf-8')}")
        return commit

    def _break_implementation(self, candidate: Path) -> None:
        implementation = candidate / "tools" / "task-packet.py"
        implementation.write_text(implementation.read_text(encoding="utf-8").replace("print(f'valid {args.kind} packet')", "print('invalid packet')"), encoding="utf-8")

    def _grade_variant(self, candidate: Path, *, claimed_required_checks: dict[str, str] | None = None) -> tuple[dict[str, object], dict[str, object]]:
        record = self._record(self._commit_variant(candidate))
        evidence = collect_grading_evidence(record, MANIFEST, SIDECAR, candidate_repository=candidate, expected_corpus_seal=EXPECTED_CORPUS_SEAL, check_inputs=self._inputs(), claimed_required_checks=claimed_required_checks)
        return evidence, grade_run(record, MANIFEST, SIDECAR, candidate_repository=candidate, expected_corpus_seal=EXPECTED_CORPUS_SEAL, check_inputs=self._inputs(), claimed_required_checks=claimed_required_checks)

    def test_independent_execution_controls_false_pass_claim(self) -> None:
        result = grade_run(self._record(), MANIFEST, SIDECAR, candidate_repository=self.candidate, expected_corpus_seal=EXPECTED_CORPUS_SEAL, check_inputs=self._inputs(), claimed_changed_paths=[], claimed_required_checks={check: "passed" for check in ["python -B -m unittest tests.test_task_packet", *self._inputs()]})
        self.assertEqual(result["status"], "VALID_WITH_FINDINGS")
        self.assertIn("changed_paths_mismatch", result["evidence"]["claims"])

    def test_v11_grade_run_accepts_frozen_dirty_candidate_without_an_ending_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = _uncommitted_task_packet_candidate(Path(directory))
            baseline = create_materialization_manifest(candidate, self._v11_identity(), protected_paths=["test_coins/IMG_3460.jpeg"])
            self._write_reference_task_packet_solution(candidate)
            frozen = freeze_candidate_state(candidate, self._v11_identity(), baseline)
            record = valid_v11_record()
            record.update(
                {
                    "candidate_state_sha256": frozen["candidate_state_sha256"],
                    "candidate_state_manifest_sha256": frozen["candidate_state_sha256"],
                    "materialization_policy_sha256": baseline["materialization_policy_sha256"],
                    "candidate_head": START,
                    "candidate_worktree_status": "dirty",
                    "candidate_changes": {"added": frozen["added_paths"], "modified": frozen["modified_paths"], "deleted": frozen["deleted_paths"]},
                }
            )
            result = grade_run(
                record,
                MANIFEST,
                SIDECAR,
                candidate_repository=candidate,
                expected_corpus_seal=EXPECTED_CORPUS_SEAL,
                check_inputs=self._inputs(),
                materialization_manifest=baseline,
            )
            after_grading = freeze_candidate_state(candidate, self._v11_identity(), baseline)
        self.assertEqual(result["status"], "VALID_WITH_FINDINGS")
        self.assertEqual(result["candidate_state_sha256"], frozen["candidate_state_sha256"])
        self.assertEqual(after_grading["candidate_state_sha256"], frozen["candidate_state_sha256"])

    def test_v11_grade_run_rejects_forged_recorded_candidate_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = _uncommitted_task_packet_candidate(Path(directory))
            baseline = create_materialization_manifest(candidate, self._v11_identity(), protected_paths=[])
            record = valid_v11_record()
            record["materialization_policy_sha256"] = baseline["materialization_policy_sha256"]
            result = grade_run(record, MANIFEST, SIDECAR, candidate_repository=candidate, expected_corpus_seal=EXPECTED_CORPUS_SEAL, materialization_manifest=baseline)
        self.assertEqual(result["status"], "INVALID")

    def test_claimed_pass_cannot_override_unavailable_frozen_check(self) -> None:
        result = grade_run(self._record(), MANIFEST, SIDECAR, candidate_repository=self.candidate, expected_corpus_seal=EXPECTED_CORPUS_SEAL, claimed_required_checks={"python -B -m unittest tests.test_task_packet": "passed"})
        self.assertEqual(result["status"], "FAILED_TASK")
        self.assertIn("required_checks_mismatch", result["evidence"]["claims"])

    def test_nonexistent_end_and_unrelated_end_are_invalid(self) -> None:
        nonexistent = grade_run(self._record("0" * 40), MANIFEST, SIDECAR, candidate_repository=self.candidate, expected_corpus_seal=EXPECTED_CORPUS_SEAL, check_inputs=self._inputs())
        unrelated = grade_run(self._record("d199223122e0d49ca98c909f3c9f4114ff3bb564"), MANIFEST, SIDECAR, candidate_repository=self.candidate, expected_corpus_seal=EXPECTED_CORPUS_SEAL, check_inputs=self._inputs())
        self.assertEqual(nonexistent["status"], "INVALID")
        self.assertEqual(unrelated["status"], "INVALID")

    def test_raw_evidence_has_no_authoritative_public_grading_entry_point(self) -> None:
        import tools.bakeoff_v1_grader as grader

        fabricated = {
            "schema_version": "1",
            "grader_id": "bakeoff-v1-deterministic-grader",
            "grader_implementation": "evidence-bound-v2",
            "corpus_manifest_sha256": self._record()["corpus_manifest_sha256"],
            "task_id": "BO1-TASK-PACKETS",
            "run_id": self._record()["run_id"],
            "starting_sha": START,
            "candidate": {"ending_sha": END, "changed_paths": [], "name_status": [], "diff_fingerprint": "0" * 40},
            "required_checks": [],
            "independent_acceptance": [],
            "unverified_claim_mismatches": {},
        }
        fabricated["evidence_sha256"] = _canonical_digest(fabricated)
        self.assertFalse(hasattr(grader, "grade_evidence"))
        with self.assertRaises(AttributeError):
            grader.grade_evidence(self._record(), MANIFEST, SIDECAR, fabricated, expected_corpus_seal=EXPECTED_CORPUS_SEAL)
        with self.assertRaises(TypeError):
            grade_run(self._record(), MANIFEST, SIDECAR, candidate_repository=self.candidate, expected_corpus_seal=EXPECTED_CORPUS_SEAL, check_inputs=self._inputs(), evidence={})  # type: ignore[call-arg]

    def test_private_evaluator_rejects_incomplete_or_substituted_evidence(self) -> None:
        evidence = collect_grading_evidence(self._record(), MANIFEST, SIDECAR, candidate_repository=self.candidate, expected_corpus_seal=EXPECTED_CORPUS_SEAL, check_inputs=self._inputs())
        variants = []
        for mutation in (
            lambda value: value.__setitem__("required_checks", value["required_checks"][:-1]),
            lambda value: value.__setitem__("required_checks", []),
            lambda value: value.__setitem__("required_checks", [value["required_checks"][0], value["required_checks"][0]]),
            lambda value: value.__setitem__("independent_acceptance", value["independent_acceptance"][:-1]),
            lambda value: value.__setitem__("independent_acceptance", []),
        ):
            variant = json.loads(json.dumps(evidence))
            mutation(variant)
            variant["evidence_sha256"] = _canonical_digest({key: value for key, value in variant.items() if key != "evidence_sha256"})
            variants.append(variant)
        for variant in variants:
            with self.subTest(variant=variant["required_checks"]):
                result = _grade_collected_evidence(self._record(), MANIFEST, SIDECAR, variant, expected_corpus_seal=EXPECTED_CORPUS_SEAL)
                self.assertEqual(result["status"], "INVALID")

    def test_private_evaluator_rejects_wrong_run_or_candidate_identity(self) -> None:
        evidence = collect_grading_evidence(self._record(), MANIFEST, SIDECAR, candidate_repository=self.candidate, expected_corpus_seal=EXPECTED_CORPUS_SEAL, check_inputs=self._inputs())
        another = self._record()
        another["run_id"] = "different-run"
        self.assertEqual(_grade_collected_evidence(another, MANIFEST, SIDECAR, evidence, expected_corpus_seal=EXPECTED_CORPUS_SEAL)["status"], "INVALID")
        wrong_candidate = json.loads(json.dumps(evidence))
        wrong_candidate["candidate"]["ending_sha"] = "0" * 40
        wrong_candidate["evidence_sha256"] = _canonical_digest({key: value for key, value in wrong_candidate.items() if key != "evidence_sha256"})
        self.assertEqual(_grade_collected_evidence(self._record(), MANIFEST, SIDECAR, wrong_candidate, expected_corpus_seal=EXPECTED_CORPUS_SEAL)["status"], "INVALID")

    def test_ledger_rejects_abbreviated_ending_sha(self) -> None:
        record = self._record("2f18d5f")
        result = grade_run(record, MANIFEST, SIDECAR, candidate_repository=self.candidate, expected_corpus_seal=EXPECTED_CORPUS_SEAL, check_inputs=self._inputs())
        self.assertEqual(result["status"], "INVALID")

    def test_timed_out_check_is_never_success(self) -> None:
        with patch("tools.bakeoff_v1_grader.subprocess.run", side_effect=subprocess.TimeoutExpired(["python"], 5)):
            checks = _execute_checks({"required_validation": ["python -B -m unittest tests.test_task_packet"]}, self.candidate, {"ending_sha": END}, None)
        self.assertEqual(checks[0]["status"], "timed_out")
        self.assertIsNone(checks[0]["exit_code"])

    def test_reference_oracle_identity_is_git_blob_bound_for_both_tasks(self) -> None:
        packets = [
            ("BO1-TASK-PACKETS", END),
            ("BO1-TAMPER-BATCH", "d068be2f7f152c49c779b66e595ebadf50661bdb"),
        ]
        for task_id, end in packets:
            with self.subTest(task_id=task_id), tempfile.TemporaryDirectory() as directory:
                candidate = _historical_candidate(Path(directory), end)
                packet = json.loads((ROOT / "benchmarks" / "bakeoff-v1" / "tasks" / f"{task_id}.json").read_text())
                results = _independent_acceptance(packet, candidate, {"ending_sha": end})
                self.assertTrue(all(item["status"] == "passed" for item in results))
                for item in results:
                    source = subprocess.run(["git", "-C", str(candidate), "show", item["source"]], capture_output=True, check=True).stdout
                    self.assertEqual(item["source_blob_sha"], subprocess.run(["git", "-C", str(candidate), "rev-parse", item["source"]], capture_output=True, text=True, check=True).stdout.strip())
                    self.assertEqual(item["source_content_sha256"], sha256(source).hexdigest())
                    self.assertEqual(item["candidate_import_root"], str(candidate.resolve()))
                    self.assertEqual(item["provenance_validation"], "passed")
                    self.assertEqual(item["expected_implementation_paths"], packet["expected_implementation_paths"][item["test_path"]])
                    self.assertEqual(item["observed_implementation_paths"], item["expected_implementation_paths"])

    def test_synthetic_test_provenance_cannot_satisfy_expected_implementation(self) -> None:
        from tools.bakeoff_v1_grader import _validate_implementation_provenance

        status, observed, outside = _validate_implementation_provenance(
            ["tools/task-packet.py"],
            [("__main__", "tests/test_task_packet.py", True)],
        )
        self.assertEqual(status, "missing_expected_implementation")
        self.assertEqual(observed, [])
        self.assertEqual(outside, [])

    def test_outside_candidate_implementation_cannot_satisfy_expected_provenance(self) -> None:
        from tools.bakeoff_v1_grader import _validate_implementation_provenance

        status, observed, outside = _validate_implementation_provenance(
            ["tools/task-packet.py"],
            [("task_packet", "C:/outside/tools/task-packet.py", False)],
        )
        self.assertEqual(status, "outside_candidate_implementation")
        self.assertEqual(observed, [])
        self.assertEqual(outside, ["C:/outside/tools/task-packet.py"])

    def test_immutable_oracle_rejects_an_expected_module_resolved_only_from_outside_candidate(self) -> None:
        packet = json.loads((ROOT / "benchmarks" / "bakeoff-v1" / "tasks" / "BO1-TAMPER-BATCH.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            candidate = _historical_candidate(Path(directory), "d068be2f7f152c49c779b66e595ebadf50661bdb")
            (candidate / "identification_verification_evaluation_batch.py").unlink()
            with patch.dict(os.environ, {"PYTHONPATH": str(ROOT)}):
                results = _independent_acceptance(packet, candidate, {"ending_sha": "d068be2f7f152c49c779b66e595ebadf50661bdb"})
        result = next(item for item in results if item["test_path"] == "test_identification_verification_evaluation_batch.py")
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["provenance_validation"], "outside_candidate_implementation")
        self.assertTrue(result["outside_implementation_paths"])

    def test_weakened_candidate_test_cannot_turn_broken_implementation_into_success(self) -> None:
        with self._candidate_variant() as candidate:
            self._break_implementation(candidate)
            (candidate / "tests" / "test_task_packet.py").write_text("import unittest\n\nclass WeakTest(unittest.TestCase):\n    def test_passes(self): self.assertTrue(True)\n", encoding="utf-8")
            evidence, result = self._grade_variant(candidate, claimed_required_checks={"python -B -m unittest tests.test_task_packet": "passed", **{command: "passed" for command in self._inputs()}})
        self.assertTrue(all(check["status"] == "passed" for check in evidence["required_checks"]))
        self.assertTrue(any(check["status"] == "failed" for check in evidence["independent_acceptance"]))
        self.assertEqual(result["status"], "FAILED_TASK")

    def test_deleted_candidate_test_cannot_turn_broken_implementation_into_success(self) -> None:
        with self._candidate_variant() as candidate:
            self._break_implementation(candidate)
            (candidate / "tests" / "test_task_packet.py").unlink()
            evidence, result = self._grade_variant(candidate)
        self.assertTrue(any(check["status"] != "passed" for check in evidence["required_checks"]))
        self.assertTrue(any(check["status"] != "passed" for check in evidence["independent_acceptance"]))
        self.assertEqual(result["status"], "FAILED_TASK")

    def test_renamed_candidate_test_cannot_turn_broken_implementation_into_success(self) -> None:
        with self._candidate_variant() as candidate:
            self._break_implementation(candidate)
            test = candidate / "tests" / "test_task_packet.py"
            test.rename(candidate / "tests" / "test_task_packet_renamed.py")
            evidence, result = self._grade_variant(candidate)
        self.assertTrue(any(check["status"] != "passed" for check in evidence["required_checks"]))
        self.assertTrue(any(check["status"] != "passed" for check in evidence["independent_acceptance"]))
        self.assertEqual(result["status"], "FAILED_TASK")

    def test_trivial_candidate_test_cannot_substitute_for_immutable_oracle(self) -> None:
        with self._candidate_variant() as candidate:
            self._break_implementation(candidate)
            (candidate / "tests" / "test_task_packet.py").write_text("import unittest\n\nclass TrivialTest(unittest.TestCase):\n    def test_always_passes(self): self.assertEqual(1, 1)\n", encoding="utf-8")
            evidence, result = self._grade_variant(candidate)
        self.assertTrue(all(check["status"] == "passed" for check in evidence["required_checks"]))
        self.assertTrue(any(check["status"] == "failed" for check in evidence["independent_acceptance"]))
        self.assertEqual(result["status"], "FAILED_TASK")

    def test_reference_candidate_test_change_is_permitted_and_non_reference_equivalent_implementation_can_pass(self) -> None:
        with self._candidate_variant() as candidate:
            implementation = candidate / "tools" / "task-packet.py"
            implementation.write_text(implementation.read_text(encoding="utf-8").replace("choices=sorted(SCHEMA_PATHS)", "choices=['outcome', 'task']"), encoding="utf-8")
            evidence, result = self._grade_variant(candidate)
        self.assertIn("tests/test_task_packet.py", evidence["candidate"]["changed_paths"])
        self.assertTrue(all(check["status"] == "passed" for check in evidence["independent_acceptance"]))
        self.assertEqual(result["status"], "VALID_WITH_FINDINGS")
        self.assertNotEqual(evidence["candidate"]["diff_fingerprint"], "45d6d5b86dfb4941bb31de41739410796230a12b")

    def test_protected_benchmark_control_mutation_is_invalid(self) -> None:
        with self._candidate_variant() as candidate:
            protected = candidate / "benchmarks" / "bakeoff-v1"
            protected.mkdir(parents=True)
            (protected / "manifest.json").write_text("{}\n", encoding="utf-8")
            _, result = self._grade_variant(candidate)
        self.assertEqual(result["status"], "INVALID")

    def test_z_broken_candidate_fails_immutable_task_packet_oracle(self) -> None:
        with self._candidate_variant() as candidate:
            self._break_implementation(candidate)
            packet = json.loads((ROOT / "benchmarks" / "bakeoff-v1" / "tasks" / "BO1-TASK-PACKETS.json").read_text())
            results = _independent_acceptance(packet, candidate, {"ending_sha": END})
        self.assertTrue(any(item["status"] == "failed" for item in results))
        self.assertTrue(any(path == "tools/task-packet.py" for item in results for _, path, _ in item["candidate_module_provenance"]))

    def test_provenance_changes_canonical_evidence_identity(self) -> None:
        evidence = collect_grading_evidence(self._record(), MANIFEST, SIDECAR, candidate_repository=self.candidate, expected_corpus_seal=EXPECTED_CORPUS_SEAL, check_inputs=self._inputs())
        unsigned = dict(evidence)
        original = unsigned.pop("evidence_sha256")
        changed = json.loads(json.dumps(unsigned))
        changed["independent_acceptance"][0]["candidate_module_provenance"].append(["wrong_source", "outside/candidate.py"])
        self.assertNotEqual(original, _canonical_digest(changed))


class ExactEvidenceRetentionTests(unittest.TestCase):
    """Synthetic collection seams; real collector, grading and final acceptance."""

    @contextmanager
    def synthetic(self, *, protocol="1.0", extra_path=None, failed=False):
        values = fixture()
        expected, evidence, packet = values[:3]
        if extra_path:
            evidence["candidate"]["changed_paths"].append(extra_path)
            evidence["candidate"]["name_status"].append("A\t" + extra_path)
        if protocol == "1.1":
            candidate = evidence["candidate"]
            candidate.pop("ending_sha")
            candidate["candidate_state_sha256"] = "b" * 64
            candidate["frozen_state"] = {"synthetic": True}
            candidate["diff_fingerprint"] = "b" * 64
            expected["scope"]["diff_fingerprint"] = "b" * 64
            expected["candidate_state_sha256"] = "b" * 64
            expected["execution_protocol_version"] = "1.1"
            for check in evidence["required_checks"] + evidence["independent_acceptance"]:
                check.pop("candidate_ending_sha")
                check["candidate_state_sha256"] = "b" * 64
            expected["required_validation"]["evidence"] = copy.deepcopy(evidence["required_checks"])
        if failed:
            evidence["required_checks"][0].update(status="failed", exit_code=1)
        record = {key: evidence[key] for key in ("task_id", "run_id", "starting_sha", "corpus_manifest_sha256")}
        record.update(schema_version="1" if protocol == "1.0" else "1.1", freezer={"status": "frozen"})
        record.update({key: value for key, value in evidence["candidate"].items()
                       if key in ("ending_sha", "candidate_state_sha256")})
        with ExitStack() as stack:
            for name, value in (
                ("validate_run_record", record),
                ("validate_frozen_corpus", {"tasks": [packet]}),
                ("_frozen_packet", packet),
                ("_candidate_identity", evidence["candidate"]),
                ("_uncommitted_candidate_identity", evidence["candidate"]),
                ("_execute_checks", evidence["required_checks"]),
                ("_independent_acceptance", evidence["independent_acceptance"]),
            ):
                stack.enter_context(patch.object(grader, name, return_value=copy.deepcopy(value)))
            stack.enter_context(patch.object(grader, "_trusted_grading_copy", side_effect=lambda _: nullcontext("synthetic-only")))
            stack.enter_context(patch.object(grader, "verify_frozen_worktree_copy"))
            collector = stack.enter_context(patch.object(grader, "collect_grading_evidence", wraps=collect_grading_evidence))
            kwargs = {"candidate_repository": Path("synthetic-only"), "expected_corpus_seal": "a" * 64}
            if protocol == "1.1":
                kwargs["materialization_manifest"] = {}
            yield record, kwargs, values, collector

    def retained_grade(self, **options):
        retained = []
        with self.synthetic(**options) as (record, kwargs, values, collector):
            result = grade_run(record, MANIFEST, SIDECAR, retain_evidence=retained.append, **kwargs)
            collector.assert_called_once()
        self.assertEqual(len(retained), 1)
        values[0], values[1] = result, retained[0]
        return values

    def bound_bytes(self, values):
        """Bind finalized bytes without repairing any technical checksum or result."""
        result, evidence, packet, review, attestation = values
        raw = [encoded(result), encoded(evidence), encoded(packet)]
        bindings = {
            "grading_result_sha256": sha256(raw[0]).hexdigest(),
            "grading_evidence_sha256": sha256(raw[1]).hexdigest(),
            "task_packet_sha256": sha256(raw[2]).hexdigest(),
            "run_identity": {key: evidence[key] for key in ("task_id", "run_id", "starting_sha", "corpus_manifest_sha256")},
            "candidate_identity": {"kind": "candidate_state_sha256", "value": evidence["candidate"]["candidate_state_sha256"]}
            if "candidate_state_sha256" in evidence["candidate"] else {"kind": "ending_sha", "value": evidence["candidate"]["ending_sha"]},
        }
        review["bindings"] = copy.deepcopy(bindings)
        attestation["bindings"] = copy.deepcopy(bindings)
        raw.append(encoded(review))
        attestation["review_sha256"] = sha256(raw[3]).hexdigest()
        raw.append(encoded(attestation))
        return raw

    def test_default_result_and_exact_retention_for_both_protocols(self):
        for protocol in ("1.0", "1.1"):
            with self.subTest(protocol=protocol), self.synthetic(protocol=protocol) as (record, kwargs, values, collector):
                expected = copy.deepcopy(values[0])
                baseline = grade_run(record, MANIFEST, SIDECAR, **kwargs)
                collector.assert_called_once()
                collector.reset_mock()
                retained = []
                result = grade_run(record, MANIFEST, SIDECAR, retain_evidence=retained.append, **kwargs)
                collector.assert_called_once()
                self.assertEqual(len(retained), 1)
                evidence = retained[0]
                checksum = sha256(encoded({key: value for key, value in evidence.items() if key != "evidence_sha256"})).hexdigest()
                self.assertEqual(evidence["evidence_sha256"], checksum)
                self.assertEqual(result["evidence"]["evidence_sha256"], checksum)
                for output in (baseline, result):
                    output = copy.deepcopy(output)
                    output.pop("checked_at_utc")
                    expected.pop("checked_at_utc", None)
                    expected["evidence"]["evidence_sha256"] = checksum
                    self.assertEqual(output, expected)

    def test_nested_callback_mutation_cannot_change_result_or_collected_evidence(self):
        with self.synthetic() as (record, kwargs, _, collector):
            collected = []
            original_collect = collect_grading_evidence

            def capture(*args, **kw):
                value = original_collect(*args, **kw)
                collected.append(value)
                return value

            collector.side_effect = capture
            retained = []

            def mutate(value):
                retained.append(value)
                value["candidate"]["changed_paths"].append("tools/bakeoff_v1_grader.py")
                value["required_checks"][0]["status"] = "failed"
                value["independent_acceptance"][0]["candidate_module_provenance"][0][1] = "outside.py"
                value["unverified_claim_mismatches"]["forged"] = True

            result = grade_run(record, MANIFEST, SIDECAR, retain_evidence=mutate, **kwargs)
            collector.assert_called_once()
        self.assertEqual(result["status"], "VALID_WITH_FINDINGS")
        self.assertEqual(result["task_success"], "passed")
        self.assertEqual(result["scope"]["changed_paths"], ["synthetic.py"])
        self.assertEqual(result["required_validation"]["evidence"][0]["status"], "passed")
        self.assertEqual(result["evidence"]["claims"], {})
        self.assertEqual(collected[0]["independent_acceptance"][0]["candidate_module_provenance"], [["synthetic", "synthetic.py", True]])
        retained[0]["candidate"]["name_status"].clear()
        self.assertEqual(result["scope"]["name_status"], ["M\tsynthetic.py"])
        self.assertEqual(collected[0]["candidate"]["changed_paths"], ["synthetic.py"])

    def test_retention_failure_is_explicit_and_never_retried(self):
        for error in (OSError("synthetic disk failure"), ValueError("synthetic serialization failure")):
            with self.subTest(error=type(error).__name__), self.synthetic() as (record, kwargs, _, collector):
                calls = []

                def fail(value):
                    calls.append(value)
                    raise error

                with self.assertRaises(grader.GradingEvidenceRetentionError) as raised:
                    grade_run(record, MANIFEST, SIDECAR, retain_evidence=fail, **kwargs)
                self.assertIs(raised.exception.__cause__, error)
                self.assertEqual(len(calls), 1)
                collector.assert_called_once()

    def test_partial_persistence_failure_does_not_return_success(self):
        with tempfile.TemporaryDirectory() as directory, self.synthetic() as (record, kwargs, _, collector):
            path = Path(directory) / "evidence.json"

            def partial(value):
                path.write_bytes(encoded(value)[:20])
                raise OSError("synthetic partial write")

            with self.assertRaises(grader.GradingEvidenceRetentionError):
                grade_run(record, MANIFEST, SIDECAR, retain_evidence=partial, **kwargs)
            self.assertEqual(path.stat().st_size, 20)
            collector.assert_called_once()

    def test_collection_failure_never_calls_retention_or_fabricates_evidence(self):
        for error in (grader.GradingEvidenceError("synthetic collection failure"), ValueError("synthetic invalid run")):
            with self.subTest(error=type(error).__name__), self.synthetic() as (record, kwargs, _, collector):
                collector.side_effect = error
                retained = []
                result = grade_run(record, MANIFEST, SIDECAR, retain_evidence=retained.append, **kwargs)
                collector.assert_called_once()
                self.assertEqual(retained, [])
                self.assertEqual(result["status"], "INVALID")
                self.assertEqual(result["invalid_reasons"], [str(error)])
                self.assertNotIn("evidence", result)

    def test_repeated_grading_leaves_duplicate_persistence_policy_to_caller(self):
        with self.synthetic() as (record, kwargs, _, collector):
            seen = set()
            calls = []

            def retain_once(value):
                calls.append(value["evidence_sha256"])
                if value["evidence_sha256"] in seen:
                    raise FileExistsError("synthetic duplicate retention")
                seen.add(value["evidence_sha256"])

            first = grade_run(record, MANIFEST, SIDECAR, retain_evidence=retain_once, **kwargs)
            with self.assertRaises(grader.GradingEvidenceRetentionError) as raised:
                grade_run(record, MANIFEST, SIDECAR, retain_evidence=retain_once, **kwargs)
            self.assertIsInstance(raised.exception.__cause__, FileExistsError)
            self.assertEqual(calls, [first["evidence"]["evidence_sha256"]] * 2)
            self.assertEqual(collector.call_count, 2)

    def test_exact_handoff_preserves_raw_results_and_both_candidate_identities(self):
        for protocol, kind in (("1.0", "ending_sha"), ("1.1", "candidate_state_sha256")):
            with self.subTest(protocol=protocol):
                values = self.retained_grade(protocol=protocol)
                raw_result = copy.deepcopy(values[0])
                inputs = self.bound_bytes(values)
                output = evaluate_final_acceptance(*inputs)
                self.assertEqual(output["verdict"], "PASS")
                self.assertEqual(output["bindings"]["candidate_identity"]["kind"], kind)
                self.assertEqual(output["bindings"]["run_identity"]["run_id"], "synthetic-run")
                self.assertEqual(output["bindings"]["grading_evidence_sha256"], sha256(inputs[1]).hexdigest())
                self.assertEqual(values[0], raw_result)
                self.assertEqual(values[0]["task_success"], "passed")
                self.assertNotIn("verdict", values[0])
                self.assertNotIn("task_success", output)

    def test_missing_review_attestation_and_false_authority_cannot_promote_success(self):
        for index in (1, 3, 4):
            with self.subTest(missing=index):
                values = self.retained_grade()
                inputs = self.bound_bytes(values)
                inputs[index] = None
                self.assertEqual(evaluate_final_acceptance(*inputs)["verdict"], "FAIL")
                self.assertEqual(values[0]["task_success"], "passed")
        for key in ("reviewer_independently_authorized", "reviewer_not_contestant",
                    "operator_approved_review", "operator_accepts_authority_responsibility"):
            with self.subTest(confirmation=key):
                values = self.retained_grade()
                values[4][key] = False
                self.assertEqual(evaluate_final_acceptance(*self.bound_bytes(values))["verdict"], "FAIL")

    def test_replaced_stale_and_checksum_mismatched_evidence_fail_closed(self):
        for mutation in ("byte_change", "replaced", "stale", "canonical", "result_checksum", "missing_check"):
            with self.subTest(mutation=mutation):
                values = self.retained_grade()
                inputs = self.bound_bytes(values)
                if mutation == "byte_change":
                    inputs[1] += b"\n"
                elif mutation == "replaced":
                    values[1]["required_checks"][0]["output_sha256"] = "f" * 64
                    inputs[1] = encoded(values[1])
                else:
                    if mutation == "stale":
                        values[1]["run_id"] = "older-run"
                    elif mutation == "canonical":
                        values[1]["evidence_sha256"] = "f" * 64
                    elif mutation == "result_checksum":
                        values[0]["evidence"]["evidence_sha256"] = "f" * 64
                    else:
                        values[1]["required_checks"] = []
                    inputs = self.bound_bytes(values)
                self.assertEqual(evaluate_final_acceptance(*inputs)["verdict"], "FAIL")

    def test_review_bound_to_another_run_or_candidate_fails_closed(self):
        for field in ("run_identity", "candidate_identity"):
            with self.subTest(field=field):
                values = self.retained_grade()
                self.bound_bytes(values)
                key = "run_id" if field == "run_identity" else "value"
                values[3]["bindings"][field][key] = "other-run" if key == "run_id" else "f" * 40
                values[4]["bindings"] = copy.deepcopy(values[3]["bindings"])
                values[4]["review_sha256"] = sha256(encoded(values[3])).hexdigest()
                self.assertEqual(evaluate_final_acceptance(*[encoded(value) for value in values])["verdict"], "FAIL")

    def test_scope_findings_require_one_consistent_independent_disposition(self):
        for disposition, want in (("nonblocking", "PASS_WITH_NOTES"), ("blocking", "FAIL"),
                                  ("ambiguous", "FAIL"), ("missing", "FAIL"), ("duplicate", "FAIL"),
                                  ("contradictory", "FAIL")):
            with self.subTest(disposition=disposition):
                values = self.retained_grade(extra_path="note.txt")
                raw = {"kind": "out_of_scope_change", "path": "note.txt"}
                self.assertEqual(values[0]["scope"]["findings"], [raw])
                note = finding("nonblocking" if disposition in ("duplicate", "contradictory") else disposition,
                               technical=raw)
                values[3]["findings"] = [] if disposition == "missing" else [note]
                if disposition == "duplicate":
                    other = copy.deepcopy(note)
                    other["finding_id"] = "second"
                    values[3]["findings"].append(other)
                elif disposition == "contradictory":
                    note["severity"] = "blocking"
                self.assertEqual(evaluate_final_acceptance(*self.bound_bytes(values))["verdict"], want)
                self.assertEqual(values[0]["task_success"], "passed")

    def test_confirmed_shortcut_and_technical_invalid_precede_task_failure(self):
        values = self.retained_grade(failed=True)
        self.assertEqual(values[0]["status"], "FAILED_TASK")
        self.assertEqual(evaluate_final_acceptance(*self.bound_bytes(values))["verdict"], "FAIL")
        values[3]["findings"] = [finding("prohibited_shortcut")]
        self.assertEqual(evaluate_final_acceptance(*self.bound_bytes(values))["verdict"], "INVALID_RUN")
        values = self.retained_grade(extra_path="tools/bakeoff_v1_grader.py", failed=True)
        self.assertEqual(values[0]["status"], "INVALID")
        self.assertEqual(values[0]["task_success"], "unavailable")
        self.assertEqual(evaluate_final_acceptance(encoded(values[0]), None, None, None, None)["verdict"], "INVALID_RUN")
