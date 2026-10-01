import json
import os
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from tests.test_bakeoff_v1_run_ledger import valid_record
from tools.bakeoff_v1_grader import (
    _grade_collected_evidence,
    _canonical_digest,
    _execute_checks,
    _independent_acceptance,
    collect_grading_evidence,
    grade_run,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks" / "bakeoff-v1" / "manifest.json"
SIDECAR = ROOT / "benchmarks" / "bakeoff-v1" / "manifest.sha256"
EXPECTED_CORPUS_SEAL = "1caa322927e4147f2f5e02d0cdb7a0069917da16277c2424700e9dd6d694ded1"
START = "9369b3f6d830d2f0ee7fe41cdabc8c57d7b77612"
END = "2f18d5fd7b1227f13aaee24467950353a77e8fee"
_PRIVATE_IMAGE_SPARSE_PATTERNS = ("/*", "!/test_coins/*", "/test_coins/README.md")


def _configure_private_image_sparse_checkout(repository: Path) -> None:
    subprocess.run(
        ["git", "-C", str(repository), "sparse-checkout", "set", "--no-cone", *_PRIVATE_IMAGE_SPARSE_PATTERNS],
        check=True,
    )


def _historical_candidate(directory: Path, ending_sha: str) -> Path:
    """Create a sparse Git candidate that shares only already-local source objects."""
    candidate = directory / "candidate"
    subprocess.run(["git", "clone", "--quiet", "--shared", "--no-checkout", str(ROOT), str(candidate)], check=True)
    _configure_private_image_sparse_checkout(candidate)
    subprocess.run(["git", "-C", str(candidate), "checkout", "--quiet", "--detach", ending_sha], check=True)
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

    def test_historical_candidate_uses_alternates_and_excludes_local_only_images(self) -> None:
        alternates = self.candidate / ".git" / "objects" / "info" / "alternates"
        self.assertTrue(alternates.is_file())
        self.assertTrue(alternates.read_text(encoding="utf-8").strip())
        self.assertFalse((self.candidate / "test_coins" / "IMG_3460.jpeg").exists())
        self.assertEqual(
            subprocess.run(
                ["git", "-C", str(self.candidate), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip(),
            END,
        )
        for start, end in (
            (START, END),
            ("ad1401aa63177ce754212241db6a7c6ee0788a8d", "d068be2f7f152c49c779b66e595ebadf50661bdb"),
        ):
            with self.subTest(start=start, end=end):
                subprocess.run(
                    ["git", "-C", str(self.candidate), "rev-parse", f"{start}^{{commit}}", f"{end}^{{commit}}"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertTrue(
                    subprocess.run(
                        ["git", "-C", str(self.candidate), "diff", "--name-only", start, end],
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

    @contextmanager
    def _candidate_variant(self):
        """Yield one cheap, clean, committed candidate variant for a real grade."""
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            subprocess.run(["git", "-C", str(self.candidate), "worktree", "add", "--quiet", "--detach", "--no-checkout", str(candidate), END], check=True)
            _configure_private_image_sparse_checkout(candidate)
            subprocess.run(["git", "-C", str(candidate), "checkout", "--quiet", "--detach", END], check=True)
            try:
                yield candidate
            finally:
                subprocess.run(["git", "-C", str(self.candidate), "worktree", "remove", "--force", str(candidate)], check=True)

    def _commit_variant(self, candidate: Path) -> str:
        subprocess.run(["git", "-C", str(candidate), "add", "--all"], check=True)
        subprocess.run(["git", "-C", str(candidate), "-c", "user.name=Bake-Off Test", "-c", "user.email=bakeoff-test@example.invalid", "commit", "--quiet", "-m", "test candidate variant"], check=True)
        return subprocess.run(["git", "-C", str(candidate), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

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
            getattr(grader, "grade_evidence")(self._record(), MANIFEST, SIDECAR, fabricated, expected_corpus_seal=EXPECTED_CORPUS_SEAL)
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
