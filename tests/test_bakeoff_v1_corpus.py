"""Tests for the frozen Bake-Off v1 replay corpus declaration."""

from __future__ import annotations

import unittest
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile

from tools.bakeoff_v1_corpus import (
    CorpusValidationError,
    validate_corpus,
    validate_frozen_corpus,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks" / "bakeoff-v1" / "manifest.json"
SIDECAR = ROOT / "benchmarks" / "bakeoff-v1" / "manifest.sha256"
EXPECTED_CORPUS_SEAL = "1caa322927e4147f2f5e02d0cdb7a0069917da16277c2424700e9dd6d694ded1"


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
            with self.assertRaisesRegex(CorpusValidationError, "task packet SHA-256"):
                validate_corpus(manifest, sidecar, repository=ROOT)

    def test_rejects_mutated_reference_evidence_integrity_root(self) -> None:
        temporary, manifest, sidecar = self._copied_corpus_paths()
        with temporary:
            integrity = manifest.parent / "integrity.json"
            integrity.write_text(integrity.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesRegex(CorpusValidationError, "integrity root SHA-256"):
                validate_corpus(manifest, sidecar, repository=ROOT)

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
            validate_frozen_corpus(MANIFEST, SIDECAR, expected_seal="7a3710611872fa6a6abf093e1deffd3cc405e321d4342cc3e1b80afb027e1ed3")

    def test_coherent_rewrite_cannot_match_the_original_external_seal(self) -> None:
        temporary, manifest, sidecar = self._copied_corpus_paths()
        with temporary:
            packet = manifest.parent / "tasks" / "BO1-TASK-PACKETS.json"
            packet_payload = json.loads(packet.read_text(encoding="utf-8"))
            packet_payload["objective"] = "coherently rewritten task intent"
            packet.write_text(json.dumps(packet_payload, separators=(",", ":")) + "\n", encoding="utf-8")
            integrity = manifest.parent / "integrity.json"
            integrity_payload = json.loads(integrity.read_text(encoding="utf-8"))
            integrity_payload["artifacts"][0]["sha256"] = sha256(packet.read_bytes()).hexdigest()
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
