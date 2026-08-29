from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from capture_import.desktop_acceptance_review import (
    DesktopAcceptanceReviewError,
    EVIDENCE_RESOLUTION_SCHEMA,
    EVIDENCE_RESOLUTION_VERSION,
    normalized_evidence_resolution_catalog_json,
    validate_evidence_resolution_catalog,
)


class DesktopAcceptanceEvidenceResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.review_record = Path(
            "benchmarks/real-world-desktop-v1/reviews/terms-2026-08-29.md"
        )
        self.evidence_record = Path(
            "benchmarks/real-world-desktop-v1/evidence/inventory-S001.json"
        )
        for relative in (self.review_record, self.evidence_record):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("sanitized synthetic attestation\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _payload(self) -> dict[str, object]:
        return {
            "schema": EVIDENCE_RESOLUTION_SCHEMA,
            "version": EVIDENCE_RESOLUTION_VERSION,
            "entries": [
                {
                    "evidence_reference": "https://example.test/terms/2026-08-29",
                    "resolution_record": self.review_record.as_posix(),
                },
                {
                    "evidence_reference": "inventory:S001",
                    "resolution_record": self.evidence_record.as_posix(),
                },
            ],
        }

    def test_catalog_normalizes_entries_and_digest_canonically(self) -> None:
        payload = self._payload()
        payload["entries"].reverse()
        catalog = validate_evidence_resolution_catalog(payload, self.root)
        self.assertEqual(
            [entry.evidence_reference for entry in catalog.entries],
            sorted(entry["evidence_reference"] for entry in payload["entries"]),
        )
        expected_payload = {
            "schema": EVIDENCE_RESOLUTION_SCHEMA,
            "version": EVIDENCE_RESOLUTION_VERSION,
            "entries": sorted(
                payload["entries"],
                key=lambda entry: (
                    entry["evidence_reference"], entry["resolution_record"]
                ),
            ),
        }
        canonical = json.dumps(
            expected_payload,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        self.assertEqual(
            catalog.digest, hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        )
        self.assertFalse(canonical.endswith("\n"))

    def test_equivalent_entry_order_has_identical_digest_and_json(self) -> None:
        first = validate_evidence_resolution_catalog(self._payload(), self.root)
        reordered = self._payload()
        reordered["entries"].reverse()
        second = validate_evidence_resolution_catalog(reordered, self.root)
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(
            normalized_evidence_resolution_catalog_json(first, self.root),
            normalized_evidence_resolution_catalog_json(second, self.root),
        )

    def test_schema_shape_and_duplicates_fail_closed(self) -> None:
        mutations = (
            lambda value: value.update({"schema": "unsupported"}),
            lambda value: value.update({"version": "2.0.0"}),
            lambda value: value.update({"extra": True}),
            lambda value: value.update({"entries": "not-an-array"}),
            lambda value: value["entries"].append(dict(value["entries"][0])),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                payload = self._payload()
                mutate(payload)
                with self.assertRaises(DesktopAcceptanceReviewError):
                    validate_evidence_resolution_catalog(payload, self.root)

    def test_resolution_path_must_be_existing_regular_file_under_allowed_root(self) -> None:
        unsafe = (
            "C:/private/attestation.md",
            "/private/attestation.md",
            "../private/attestation.md",
            "benchmarks/real-world-desktop-v1/reviews/../private.md",
            "benchmarks\\real-world-desktop-v1\\reviews\\record.md",
            "https://example.test/record",
            "benchmarks/real-world-desktop-v1/reviews/password=secret.md",
            "private/record.md",
            "benchmarks/real-world-desktop-v1/reviews/missing.md",
            "benchmarks/real-world-desktop-v1/reviews/",
        )
        for path in unsafe:
            with self.subTest(path=path):
                payload = self._payload()
                payload["entries"][0]["resolution_record"] = path
                with self.assertRaises(DesktopAcceptanceReviewError):
                    validate_evidence_resolution_catalog(payload, self.root)

    def test_windows_alias_and_invalid_component_syntax_fails_closed(self) -> None:
        actual = self.root / "benchmarks/real-world-desktop-v1/reviews/a.md"
        actual.write_text("canonical\n", encoding="utf-8")
        unsafe = (
            "benchmarks/real-world-desktop-v1/reviews/a.md:attestation",
            "benchmarks/real-world-desktop-v1/reviews/A.MD",
            "benchmarks/real-world-desktop-v1/reviews/a.md.",
            "benchmarks/real-world-desktop-v1/reviews/a.md ",
            "benchmarks/real-world-desktop-v1/reviews/a<.md",
            "benchmarks/real-world-desktop-v1/reviews/a>.md",
            'benchmarks/real-world-desktop-v1/reviews/a".md',
            "benchmarks/real-world-desktop-v1/reviews/a|.md",
            "benchmarks/real-world-desktop-v1/reviews/a?.md",
            "benchmarks/real-world-desktop-v1/reviews/a*.md",
            "benchmarks/real-world-desktop-v1/reviews/CON.md",
            "benchmarks/real-world-desktop-v1/reviews/lpt1.txt",
        )
        for path in unsafe:
            with self.subTest(path=path):
                payload = self._payload()
                payload["entries"][0]["resolution_record"] = path
                with self.assertRaises(DesktopAcceptanceReviewError):
                    validate_evidence_resolution_catalog(payload, self.root)

    def test_valid_path_requires_exact_on_disk_spelling(self) -> None:
        catalog = validate_evidence_resolution_catalog(self._payload(), self.root)
        self.assertEqual(
            catalog.entries[0].resolution_record,
            self.review_record.as_posix(),
        )

    def test_existing_file_under_protected_root_is_rejected(self) -> None:
        protected = self.root / "private/protected-attestation.md"
        protected.parent.mkdir(parents=True)
        protected.write_text("protected\n", encoding="utf-8")
        payload = self._payload()
        payload["entries"][0]["resolution_record"] = "private/protected-attestation.md"
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, "permitted"):
            validate_evidence_resolution_catalog(payload, self.root)

    def test_symlink_or_reparse_traversal_fails_closed_when_supported(self) -> None:
        outside = Path(self.temporary.name).parent / "outside-attestation.md"
        outside.write_text("outside\n", encoding="utf-8")
        link = self.root / "benchmarks/real-world-desktop-v1/reviews/link.md"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation is not available")
        try:
            payload = self._payload()
            payload["entries"][0]["resolution_record"] = link.relative_to(
                self.root
            ).as_posix()
            with self.assertRaises(DesktopAcceptanceReviewError):
                validate_evidence_resolution_catalog(payload, self.root)
        finally:
            outside.unlink(missing_ok=True)

    def test_reference_forms_are_validated_without_network_or_inventory_access(self) -> None:
        catalog = validate_evidence_resolution_catalog(self._payload(), self.root)
        self.assertEqual(len(catalog.entries), 2)

    def test_direct_model_digest_tampering_cannot_serialize(self) -> None:
        catalog = validate_evidence_resolution_catalog(self._payload(), self.root)
        malformed = replace(catalog, digest="0" * 64)
        with self.assertRaisesRegex(DesktopAcceptanceReviewError, "canonical form"):
            normalized_evidence_resolution_catalog_json(malformed, self.root)


if __name__ == "__main__":
    unittest.main()
