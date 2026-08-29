from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from capture_import.desktop_acceptance_set import (
    DesktopAcceptanceManifestError,
    audit_desktop_acceptance_manifest,
    compute_desktop_acceptance_digests,
    load_desktop_acceptance_manifest,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class DesktopAcceptanceSetTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, dict[str, object]]:
        schema = root / "manifest.schema.json"
        schema.write_text('{"synthetic":"schema"}', encoding="utf-8")
        policy = root / "canonicalization-policy.json"
        policy.write_text('{"synthetic":"policy"}', encoding="utf-8")
        cases = []
        for number in range(1, 31):
            case_id = f"case-{number:03d}"
            specimen_number = number if number <= 24 else number - 24
            specimen_id = f"specimen-{specimen_number:03d}"
            partner = None
            difference = None
            if number <= 6:
                partner = f"case-{number + 24:03d}"
                difference = "paired capture uses directional rather than diffuse light"
            elif number >= 25:
                partner = f"case-{number - 24:03d}"
                difference = "paired capture uses directional rather than diffuse light"
            action = "identify" if number <= 24 else "abstain"
            identity = {"country": "Canada", "denomination": "25 cents", "year": "1964"}
            image_dir = root / "images" / case_id
            image_dir.mkdir(parents=True)
            images = []
            for role in ("obverse", "reverse"):
                data = f"synthetic-{case_id}-{role}".encode()
                image_path = image_dir / f"{role}.bin"
                image_path.write_bytes(data)
                images.append({
                    "role": role,
                    "path": f"images/{case_id}/{role}.bin",
                    "sha256": _sha(data),
                    "provenance": {
                        "author": "synthetic test suite", "license": "synthetic-only",
                        "source_reference": f"fixture-source-{case_id}-{role}",
                        "capture_reference": f"fixture-capture-{case_id}-{role}",
                    },
                    "transformation": {
                        "operation": "none", "source_sha256": None,
                        "parameters": {}, "rationale": "original capture bytes",
                    },
                    "provider_eligibility": {
                        "eligible": True, "privacy_approved": True,
                        "license_approved": True,
                        "authorization_reference": f"fixture-authorization-{case_id}",
                    },
                })
            ground_reviewers = [
                {"reviewer_id": "reviewer-a", "decision": copy.deepcopy(identity),
                 "evidence_reference": f"ground-evidence-a-{case_id}"},
                {"reviewer_id": "reviewer-b", "decision": copy.deepcopy(identity),
                 "evidence_reference": f"ground-evidence-b-{case_id}"},
            ]
            action_reviewers = [
                {"reviewer_id": "reviewer-a", "decision": action,
                 "evidence_reference": f"action-evidence-a-{case_id}"},
                {"reviewer_id": "reviewer-b", "decision": action,
                 "evidence_reference": f"action-evidence-b-{case_id}"},
            ]
            cases.append({
                "case_id": case_id, "specimen_id": specimen_id,
                "repeated_case_id": partner, "expected_action": action,
                "expected_identity": identity,
                "reserved_attribution": {"mint": None, "mint_mark": None,
                                         "variety": None, "catalog_reference": None},
                "capture_conditions": {
                    "background": "neutral", "device": "synthetic-camera",
                    "distance": "fixed", "lighting": "diffuse" if number <= 24 else "directional",
                    "orientation": "upright",
                },
                "capture_difference_fields": ["lighting"] if partner else None,
                "capture_difference_rationale": difference,
                "cohorts": ["challenging", "standard"] if action == "abstain" else ["standard"],
                "stability": number in set(range(7, 16)) | {25},
                "privacy_classification": "synthetic",
                "prior_benchmark_use": {"used": False, "details": None},
                "ground_truth_review": {"reviewers": ground_reviewers, "adjudication": None},
                "action_review": {"reviewers": action_reviewers, "adjudication": None},
                "images": images, "notes": "synthetic fixture only",
            })
        payload = {
            "schema": "coin-analyzer-real-world-desktop-acceptance-set",
            "version": "1.0.0",
            "canonicalization_policy": {
                "policy_id": "coin-analyzer-desktop-acceptance-canonicalization",
                "version": "1.0.0", "path": "canonicalization-policy.json",
                "sha256": _sha(policy.read_bytes()),
            },
            "freeze": {
                "corpus_version": "1.0.0", "frozen_at_utc": "2026-01-01T00:00:00Z",
                "manifest_sha256": "0" * 64, "schema_sha256": "0" * 64,
                "ground_truth_sha256": "0" * 64, "action_sha256": "0" * 64,
                "transformation_ledger_sha256": "0" * 64,
                "near_duplicate_review": {
                    "reviewer_id": "leakage-reviewer", "reviewed_at_utc": "2026-01-01T00:00:00Z",
                    "method": "synthetic exact and perceptual comparison",
                    "evidence_reference": "synthetic-near-duplicate-review",
                    "result": "no_unresolved_matches",
                },
            },
            "stability_relevant_cohorts": ["challenging", "standard"],
            "cases": cases,
        }
        path = root / "manifest.json"
        self._write(path, payload, resign=True)
        return path, payload

    def _write(self, path: Path, payload: dict[str, object], *, resign: bool) -> None:
        if resign:
            digests = compute_desktop_acceptance_digests(
                payload, (path.parent / "manifest.schema.json").read_bytes()
            )
            payload["freeze"].update(digests)  # type: ignore[union-attr]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def test_loads_complete_frozen_contract_and_audits_deterministically(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self._fixture(Path(directory))
            manifest = load_desktop_acceptance_manifest(path)
            first = audit_desktop_acceptance_manifest(manifest)
            self.assertEqual(first, audit_desktop_acceptance_manifest(manifest))
            self.assertEqual((first["cases"], first["images"], first["specimens"]), (30, 60, 24))
            self.assertEqual(first["expected_actions"], {"abstain": 6, "identify": 24})
            self.assertEqual(len(first["stability_cases"]), 10)
            self.assertTrue(first["ready"])

    def test_rejects_stale_image_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path, payload = self._fixture(Path(directory))
            payload["cases"][0]["images"][0]["sha256"] = "0" * 64
            self._write(path, payload, resign=True)
            with self.assertRaisesRegex(DesktopAcceptanceManifestError, "frozen bytes"):
                load_desktop_acceptance_manifest(path)

    def test_requires_complete_identity_for_abstain(self):
        with tempfile.TemporaryDirectory() as directory:
            path, payload = self._fixture(Path(directory))
            payload["cases"][24]["expected_identity"]["year"] = None
            self._write(path, payload, resign=True)
            with self.assertRaisesRegex(DesktopAcceptanceManifestError, "non-empty text"):
                load_desktop_acceptance_manifest(path)

    def test_enforces_action_balance(self):
        with tempfile.TemporaryDirectory() as directory:
            path, payload = self._fixture(Path(directory))
            case = payload["cases"][23]
            case["expected_action"] = "abstain"
            for reviewer in case["action_review"]["reviewers"]:
                reviewer["decision"] = "abstain"
            self._write(path, payload, resign=True)
            with self.assertRaisesRegex(DesktopAcceptanceManifestError, "24 identify"):
                load_desktop_acceptance_manifest(path)

    def test_requires_reciprocal_specimen_declarations(self):
        with tempfile.TemporaryDirectory() as directory:
            path, payload = self._fixture(Path(directory))
            payload["cases"][0]["repeated_case_id"] = "case-026"
            self._write(path, payload, resign=True)
            with self.assertRaisesRegex(DesktopAcceptanceManifestError, "reciprocal"):
                load_desktop_acceptance_manifest(path)

    def test_rejects_duplicate_image_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, payload = self._fixture(root)
            first = payload["cases"][0]["images"][0]
            second = payload["cases"][1]["images"][0]
            (root / second["path"]).write_bytes((root / first["path"]).read_bytes())
            second["sha256"] = first["sha256"]
            self._write(path, payload, resign=True)
            with self.assertRaisesRegex(DesktopAcceptanceManifestError, "unique bytes"):
                load_desktop_acceptance_manifest(path)

    def test_stability_subset_requires_distinct_specimens_and_both_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            path, payload = self._fixture(Path(directory))
            payload["cases"][24]["stability"] = False
            payload["cases"][15]["stability"] = True
            self._write(path, payload, resign=True)
            with self.assertRaisesRegex(DesktopAcceptanceManifestError, "both expected actions"):
                load_desktop_acceptance_manifest(path)

    def test_provider_eligibility_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path, payload = self._fixture(Path(directory))
            payload["cases"][0]["images"][0]["provider_eligibility"]["license_approved"] = False
            self._write(path, payload, resign=True)
            with self.assertRaisesRegex(DesktopAcceptanceManifestError, "fail closed"):
                load_desktop_acceptance_manifest(path)

    def test_forbids_benchmark_specific_transformation(self):
        with tempfile.TemporaryDirectory() as directory:
            path, payload = self._fixture(Path(directory))
            payload["cases"][0]["images"][0]["transformation"]["operation"] = "sharpen"
            self._write(path, payload, resign=True)
            with self.assertRaisesRegex(DesktopAcceptanceManifestError, "forbidden"):
                load_desktop_acceptance_manifest(path)

    def test_requires_independent_reviewers(self):
        with tempfile.TemporaryDirectory() as directory:
            path, payload = self._fixture(Path(directory))
            payload["cases"][0]["ground_truth_review"]["reviewers"][1]["reviewer_id"] = "reviewer-a"
            self._write(path, payload, resign=True)
            with self.assertRaisesRegex(DesktopAcceptanceManifestError, "independent"):
                load_desktop_acceptance_manifest(path)

    def test_rejects_stale_policy_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path, payload = self._fixture(Path(directory))
            payload["canonicalization_policy"]["sha256"] = "0" * 64
            self._write(path, payload, resign=True)
            with self.assertRaisesRegex(DesktopAcceptanceManifestError, "policy SHA-256"):
                load_desktop_acceptance_manifest(path)

    def test_rejects_stale_manifest_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path, payload = self._fixture(Path(directory))
            payload["freeze"]["manifest_sha256"] = "0" * 64
            self._write(path, payload, resign=False)
            with self.assertRaisesRegex(DesktopAcceptanceManifestError, "manifest_sha256"):
                load_desktop_acceptance_manifest(path)

    def test_rejects_each_stale_subordinate_digest(self):
        for field in (
            "schema_sha256", "ground_truth_sha256", "action_sha256",
            "transformation_ledger_sha256",
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                path, payload = self._fixture(Path(directory))
                payload["freeze"][field] = "0" * 64
                self._write(path, payload, resign=False)
                with self.assertRaisesRegex(DesktopAcceptanceManifestError, field):
                    load_desktop_acceptance_manifest(path)

    def test_rejects_unsafe_nonsemantic_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path, payload = self._fixture(Path(directory))
            payload["cases"][0]["images"][0]["path"] = "../obverse.bin"
            self._write(path, payload, resign=True)
            with self.assertRaisesRegex(DesktopAcceptanceManifestError, "unsafe"):
                load_desktop_acceptance_manifest(path)


if __name__ == "__main__":
    unittest.main()
