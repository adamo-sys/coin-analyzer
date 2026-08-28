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
    load_desktop_acceptance_manifest,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class DesktopAcceptanceSetTests(unittest.TestCase):
    def _fixture(self, root: Path):
        images = root / "images"
        images.mkdir()
        front = b"synthetic-obverse"
        back = b"synthetic-reverse"
        (images / "001-obverse.bin").write_bytes(front)
        (images / "001-reverse.bin").write_bytes(back)

        case = {
            "case_id": "case-001",
            "specimen_id": "specimen-001",
            "expected_action": "identify",
            "expected_identity": {
                "country": "Canada",
                "denomination": "5 cents",
                "year": "1964",
            },
            "reserved_attribution": {
                "mint": None,
                "mint_mark": None,
                "variety": None,
                "catalog_reference": None,
            },
            "capture_conditions": {
                "lighting": "diffuse",
                "background": "neutral",
            },
            "privacy_classification": "synthetic",
            "images": [
                {
                    "role": "obverse",
                    "path": "images/001-obverse.bin",
                    "sha256": _sha(front),
                    "author": "test suite",
                    "license": None,
                    "source_reference": "synthetic-fixture",
                },
                {
                    "role": "reverse",
                    "path": "images/001-reverse.bin",
                    "sha256": _sha(back),
                    "author": "test suite",
                    "license": None,
                    "source_reference": "synthetic-fixture",
                },
            ],
            "notes": "synthetic only",
        }

        payload = {
            "schema": "coin-analyzer-real-world-desktop-acceptance-set",
            "version": "1",
            "cases": [case],
        }
        path = root / "manifest.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path, payload

    def _write(self, path, payload):
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def test_loads_paired_frozen_case(self):
        with tempfile.TemporaryDirectory() as d:
            path, _ = self._fixture(Path(d))
            manifest = load_desktop_acceptance_manifest(path)
            self.assertEqual(len(manifest.cases), 1)
            case = manifest.cases[0]
            self.assertEqual(case.expected_action, "identify")
            self.assertEqual(
                [image.role for image in case.images],
                ["obverse", "reverse"],
            )
            self.assertIsNone(case.reserved_attribution["variety"])

    def test_rejects_stale_hash(self):
        with tempfile.TemporaryDirectory() as d:
            path, payload = self._fixture(Path(d))
            payload["cases"][0]["images"][0]["sha256"] = "0" * 64
            self._write(path, payload)
            with self.assertRaisesRegex(
                DesktopAcceptanceManifestError, "SHA-256"
            ):
                load_desktop_acceptance_manifest(path)

    def test_rejects_unsafe_path(self):
        with tempfile.TemporaryDirectory() as d:
            path, payload = self._fixture(Path(d))
            payload["cases"][0]["images"][0]["path"] = "../escape.bin"
            self._write(path, payload)
            with self.assertRaisesRegex(
                DesktopAcceptanceManifestError, "unsafe"
            ):
                load_desktop_acceptance_manifest(path)

    def test_rejects_drive_like_path(self):
        with tempfile.TemporaryDirectory() as d:
            path, payload = self._fixture(Path(d))
            payload["cases"][0]["images"][0]["path"] = "C:/escape.bin"
            self._write(path, payload)
            with self.assertRaisesRegex(
                DesktopAcceptanceManifestError, "unsafe"
            ):
                load_desktop_acceptance_manifest(path)

    def test_rejects_empty_capture_conditions(self):
        with tempfile.TemporaryDirectory() as d:
            path, payload = self._fixture(Path(d))
            payload["cases"][0]["capture_conditions"] = {}
            self._write(path, payload)
            with self.assertRaisesRegex(
                DesktopAcceptanceManifestError, "must not be empty"
            ):
                load_desktop_acceptance_manifest(path)

    def test_identify_requires_complete_identity(self):
        with tempfile.TemporaryDirectory() as d:
            path, payload = self._fixture(Path(d))
            payload["cases"][0]["expected_identity"]["year"] = None
            self._write(path, payload)
            with self.assertRaisesRegex(
                DesktopAcceptanceManifestError, "complete"
            ):
                load_desktop_acceptance_manifest(path)

    def test_abstain_can_retain_partial_identity_in_foundation(self):
        with tempfile.TemporaryDirectory() as d:
            path, payload = self._fixture(Path(d))
            payload["cases"][0]["expected_action"] = "abstain"
            payload["cases"][0]["expected_identity"]["year"] = None
            self._write(path, payload)
            manifest = load_desktop_acceptance_manifest(path)
            self.assertIsNone(
                manifest.cases[0].expected_identity["year"]
            )

    def test_reserved_attribution_is_null_only(self):
        with tempfile.TemporaryDirectory() as d:
            path, payload = self._fixture(Path(d))
            payload["cases"][0]["reserved_attribution"]["variety"] = "invented"
            self._write(path, payload)
            with self.assertRaisesRegex(
                DesktopAcceptanceManifestError, "remain null"
            ):
                load_desktop_acceptance_manifest(path)

    def test_audit_reports_exact_duplicates_deterministically(self):
        with tempfile.TemporaryDirectory() as d:
            path, payload = self._fixture(Path(d))
            second = copy.deepcopy(payload["cases"][0])
            second["case_id"] = "case-002"
            second["specimen_id"] = "specimen-002"
            second["expected_action"] = "abstain"
            payload["cases"].append(second)
            self._write(path, payload)

            manifest = load_desktop_acceptance_manifest(path)
            first = audit_desktop_acceptance_manifest(manifest)
            second_audit = audit_desktop_acceptance_manifest(manifest)

            self.assertEqual(first, second_audit)
            self.assertEqual(first["cases"], 2)
            self.assertEqual(first["images"], 4)
            self.assertEqual(
                first["expected_actions"],
                {"abstain": 1, "identify": 1},
            )
            self.assertEqual(len(first["duplicate_image_hashes"]), 2)


if __name__ == "__main__":
    unittest.main()
