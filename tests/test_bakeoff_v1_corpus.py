"""Tests for the frozen Bake-Off v1 replay corpus declaration."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from tools.bakeoff_v1_corpus import (
    CorpusValidationError,
    _canonical_prompt_bytes,
    validate_corpus,
    validate_frozen_corpus,
    validate_prompt_cohorts,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks" / "bakeoff-v1" / "manifest.json"
SIDECAR = ROOT / "benchmarks" / "bakeoff-v1" / "manifest.sha256"
PROMPT_COHORTS = ROOT / "benchmarks" / "bakeoff-v1" / "prompt-cohorts-v1.1.json"
EXPECTED_CORPUS_SEAL = "51c0abe19e97e6032226968fd2f2cd3fae4514dfaf0bba113ae20be2162a0a74"
PRE_RECONSTRUCTED_RUNNER_CORPUS_SEAL = "daccc7fef89286e59ea1df9c6e7b8bed9396a985088df925650791d95fbbfe40"
PRE_PROSPECTIVE_PROMPT_CORPUS_SEAL = "89afe86ac0608c121f14ea7cfd8d1dc8fd61cd9f3eb656045348baa8ae7dccc1"
PRE_V11_CORPUS_SEAL = "1caa322927e4147f2f5e02d0cdb7a0069917da16277c2424700e9dd6d694ded1"


class BakeoffV1CorpusTests(unittest.TestCase):
    def _copied_corpus_paths(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        package = Path(temporary.name) / "benchmarks" / "bakeoff-v1"
        package.parent.mkdir(parents=True)
        shutil.copytree(MANIFEST.parent, package)
        return temporary, package / "manifest.json", package / "manifest.sha256"

    def test_frozen_manifest_has_exactly_the_two_selected_known_history_tasks(self) -> None:
        corpus = validate_corpus(MANIFEST, SIDECAR)

        self.assertEqual(corpus["benchmark_id"], "coin-analyzer-bakeoff-v1")
        self.assertEqual(corpus["benchmark_version"], "1.0")
        self.assertEqual(
            [task["task_id"] for task in corpus["tasks"]],
            ["BO1-TASK-PACKETS", "BO1-TAMPER-BATCH"],
        )
        self.assertEqual(
            corpus["tasks"][0]["starting_sha"],
            "9369b3f6d830d2f0ee7fe41cdabc8c57d7b77612",
        )
        self.assertEqual(
            corpus["tasks"][1]["starting_sha"],
            "ad1401aa63177ce754212241db6a7c6ee0788a8d",
        )
        for task in corpus["tasks"]:
            self.assertEqual(task["benchmark_class"], "replay_known_history")
            self.assertEqual(task["network_provider_policy"], "network_and_provider_access_forbidden")

    def test_rejects_manifest_with_a_non_full_starting_sha(self) -> None:
        with self.assertRaisesRegex(CorpusValidationError, "full SHA"):
            validate_corpus(
                MANIFEST,
                SIDECAR,
                overrides={"tasks.0.starting_sha": "9369b3f"},
            )

    def test_rejects_mutated_task_packet_under_a_valid_manifest(self) -> None:
        temporary, manifest, sidecar = self._copied_corpus_paths()
        with temporary:
            packet = manifest.parent / "tasks" / "BO1-TASK-PACKETS.json"
            packet.write_text(packet.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesRegex(CorpusValidationError, "integrity artifact SHA-256"):
                validate_corpus(manifest, sidecar, repository=ROOT)

    def test_rejects_mutated_reference_evidence_integrity_root(self) -> None:
        temporary, manifest, sidecar = self._copied_corpus_paths()
        with temporary:
            integrity = manifest.parent / "integrity.json"
            integrity.write_text(integrity.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesRegex(CorpusValidationError, "integrity root SHA-256"):
                validate_corpus(manifest, sidecar, repository=ROOT)

    def test_rejects_mutated_v11_protocol_control_artifact(self) -> None:
        temporary, manifest, sidecar = self._copied_corpus_paths()
        with temporary:
            protocol = manifest.parent / "EXECUTION-PROTOCOL-v1.1.md"
            protocol.write_text(protocol.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesRegex(CorpusValidationError, "integrity artifact SHA-256"):
                validate_corpus(manifest, sidecar, repository=ROOT)

    def test_sealed_v11_prompt_cohorts_bind_exact_prompts_and_runs(self) -> None:
        cohorts = validate_prompt_cohorts(MANIFEST)

        self.assertEqual(
            [(cohort["task_id"], cohort["authorized_runs"]) for cohort in cohorts["cohorts"]],
            [
                ("BO1-TASK-PACKETS", ["RUN-004", "RUN-005"]),
                ("BO1-TAMPER-BATCH", ["RUN-002", "RUN-003", "RUN-006"]),
            ],
        )
        self.assertEqual(
            cohorts["historical_runs"],
            [
                {
                    "run_id": "RUN-001",
                    "task_id": "BO1-TASK-PACKETS",
                    "execution_protocol_version": "1.0",
                    "prompt_sha256": "ee59f6c5815beed3601df17f3e2228c100ca12d30d13ca507836eac638c502f1",
                    "prompt_bytes_availability": "unrecoverable",
                }
            ],
        )
        for cohort in cohorts["cohorts"]:
            prompt = ROOT / cohort["prompt_path"]
            self.assertEqual(sha256(prompt.read_bytes()).hexdigest(), cohort["prompt_sha256"])

        integrity = json.loads((ROOT / "benchmarks/bakeoff-v1/integrity.json").read_text(encoding="utf-8"))
        artifact_hashes = {artifact["path"]: artifact["sha256"] for artifact in integrity["artifacts"]}
        self.assertEqual(
            artifact_hashes["benchmarks/bakeoff-v1/tasks/BO1-TASK-PACKETS.json"],
            "da14741ffd98b07a03fb67b2624beb7367ab5b3ec0ddd56d84c56a19b30e32eb",
        )
        self.assertEqual(
            artifact_hashes["benchmarks/bakeoff-v1/tasks/BO1-TAMPER-BATCH.json"],
            "cb5b72cbbee8e573bb2e3657e149b7a243110c7647250e8e551c51da4ab638d4",
        )

        self.assertEqual(
            sha256((ROOT / "benchmarks/bakeoff-v1/prompts/BO1-TAMPER-BATCH-v1.1.txt").read_bytes()).hexdigest(),
            "2de9e4fc28455d242694abda08601578bbeb5537b367bc48de99beb940bd8b80",
        )
        runner_specification = ROOT / "benchmarks/bakeoff-v1/orchestrator/reconstructed-runner-v1.json"
        self.assertEqual(
            artifact_hashes["benchmarks/bakeoff-v1/orchestrator/reconstructed-runner-v1.json"],
            sha256(runner_specification.read_bytes()).hexdigest(),
        )

    def test_rejects_manifest_task_packet_mismatch(self) -> None:
        with self.assertRaisesRegex(CorpusValidationError, "task packet path"):
            validate_corpus(
                MANIFEST,
                SIDECAR,
                overrides={"tasks.0.task_packet": "benchmarks/bakeoff-v1/tasks/BO1-TAMPER-BATCH.json"},
            )

    def test_freeze_grade_requires_the_explicit_external_seal(self) -> None:
        corpus = validate_frozen_corpus(MANIFEST, SIDECAR, expected_seal=EXPECTED_CORPUS_SEAL)
        self.assertEqual(corpus["benchmark_id"], "coin-analyzer-bakeoff-v1")
        with self.assertRaisesRegex(CorpusValidationError, "external corpus seal"):
            validate_frozen_corpus(MANIFEST, SIDECAR, expected_seal=None)
        with self.assertRaisesRegex(CorpusValidationError, "external corpus seal"):
            validate_frozen_corpus(MANIFEST, SIDECAR, expected_seal="not-a-digest")
        with self.assertRaisesRegex(CorpusValidationError, "external corpus seal"):
            validate_frozen_corpus(MANIFEST, SIDECAR, expected_seal="f" * 64)
        with self.assertRaisesRegex(CorpusValidationError, "external corpus seal"):
            validate_frozen_corpus(MANIFEST, SIDECAR, expected_seal=PRE_PROSPECTIVE_PROMPT_CORPUS_SEAL)
        with self.assertRaisesRegex(CorpusValidationError, "external corpus seal"):
            validate_frozen_corpus(MANIFEST, SIDECAR, expected_seal=PRE_RECONSTRUCTED_RUNNER_CORPUS_SEAL)
        with self.assertRaisesRegex(CorpusValidationError, "external corpus seal"):
            validate_frozen_corpus(MANIFEST, SIDECAR, expected_seal=PRE_V11_CORPUS_SEAL)
        with self.assertRaisesRegex(CorpusValidationError, "external corpus seal"):
            validate_frozen_corpus(MANIFEST, SIDECAR, expected_seal="7a3710611872fa6a6abf093e1deffd3cc405e321d4342cc3e1b80afb027e1ed3")

    def test_coherent_rewrite_cannot_match_the_original_external_seal(self) -> None:
        temporary, manifest, sidecar = self._copied_corpus_paths()
        with temporary:
            packet = manifest.parent / "tasks" / "BO1-TASK-PACKETS.json"
            packet_payload = json.loads(packet.read_text(encoding="utf-8"))
            packet_payload["objective"] = "coherently rewritten task intent"
            packet.write_text(json.dumps(packet_payload, separators=(",", ":")) + "\n", encoding="utf-8")
            prompt_path = manifest.parent / "prompts" / "BO1-TASK-PACKETS-v1.1.txt"
            prompt_path.write_bytes(_canonical_prompt_bytes(packet_payload))
            cohorts_path = manifest.parent / "prompt-cohorts-v1.1.json"
            cohorts_payload = json.loads(cohorts_path.read_text(encoding="utf-8"))
            cohorts_payload["cohorts"][0]["prompt_sha256"] = sha256(prompt_path.read_bytes()).hexdigest()
            cohorts_path.write_text(json.dumps(cohorts_payload, separators=(",", ":")) + "\n", encoding="utf-8")
            integrity = manifest.parent / "integrity.json"
            integrity_payload = json.loads(integrity.read_text(encoding="utf-8"))
            artifact_hashes = {
                "benchmarks/bakeoff-v1/tasks/BO1-TASK-PACKETS.json": sha256(packet.read_bytes()).hexdigest(),
                "benchmarks/bakeoff-v1/prompts/BO1-TASK-PACKETS-v1.1.txt": sha256(prompt_path.read_bytes()).hexdigest(),
                "benchmarks/bakeoff-v1/prompt-cohorts-v1.1.json": sha256(cohorts_path.read_bytes()).hexdigest(),
            }
            for artifact in integrity_payload["artifacts"]:
                if artifact["path"] in artifact_hashes:
                    artifact["sha256"] = artifact_hashes[artifact["path"]]
            integrity.write_text(json.dumps(integrity_payload, separators=(",", ":")) + "\n", encoding="utf-8")
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_payload["integrity_root_sha256"] = sha256(integrity.read_bytes()).hexdigest()
            manifest.write_text(json.dumps(manifest_payload, separators=(",", ":")) + "\n", encoding="utf-8")
            sidecar.write_text(sha256(manifest.read_bytes()).hexdigest() + "\n", encoding="ascii")

            self.assertEqual(validate_corpus(manifest, sidecar, repository=ROOT)["tasks"][0]["task_id"], "BO1-TASK-PACKETS")
            with self.assertRaisesRegex(CorpusValidationError, "external corpus seal"):
                validate_frozen_corpus(manifest, sidecar, expected_seal=EXPECTED_CORPUS_SEAL, repository=ROOT)


if __name__ == "__main__":
    unittest.main()
