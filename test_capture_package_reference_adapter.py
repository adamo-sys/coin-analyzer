from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from capture_import.package import ValidatedCapturePackage
from capture_package_reference_adapter import (
    CapturePackageReferenceAdaptation,
    adapt_capture_package_reference,
)
from multimodal_evidence_references import (
    CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
    MultimodalEvidenceKind,
    MultimodalEvidenceReference,
)


class CapturePackageReferenceAdapterTests(unittest.TestCase):
    def package(self, **changes: object) -> ValidatedCapturePackage:
        values: dict[str, object] = {
            "package_basename": "synthetic-session.ca-package",
            "package_sha256": "a" * 64,
            "package_byte_length": 1234,
            "archive": None,
            "manifest": None,
            "media": (),
        }
        values.update(changes)
        return ValidatedCapturePackage(**values)  # type: ignore[arg-type]

    def test_adapts_canonical_package_fingerprint(self) -> None:
        source = self.package()

        result = adapt_capture_package_reference(
            source,
            reference_id="capture-package:synthetic-session",
            source_id="capture-session:synthetic",
        )

        self.assertIs(result.source, source)
        self.assertEqual(result.reference.kind, MultimodalEvidenceKind.CAPTURE_PACKAGE)
        self.assertEqual(result.reference.locator, "synthetic-session.ca-package")
        self.assertEqual(result.reference.source_fingerprint, "a" * 64)
        self.assertEqual(result.reference.source_id, "capture-session:synthetic")

    def test_caller_cannot_supply_alternate_locator_or_fingerprint(self) -> None:
        source = self.package(
            package_basename="canonical.ca-package",
            package_sha256="b" * 64,
        )

        result = adapt_capture_package_reference(
            source,
            reference_id="capture-package:canonical",
            source_id="capture-session:canonical",
        )

        self.assertEqual(result.reference.locator, source.package_basename)
        self.assertEqual(result.reference.source_fingerprint, source.package_sha256)

    def test_rejects_invalid_source_type(self) -> None:
        with self.assertRaises(TypeError):
            adapt_capture_package_reference(  # type: ignore[arg-type]
                object(),
                reference_id="capture-package:x",
                source_id="capture-session:x",
            )

    def test_rejects_noncanonical_package_digest(self) -> None:
        with self.assertRaisesRegex(ValueError, "lowercase SHA-256"):
            adapt_capture_package_reference(
                self.package(package_sha256="A" * 64),
                reference_id="capture-package:x",
                source_id="capture-session:x",
            )

    def test_rejects_invalid_package_basename(self) -> None:
        with self.assertRaisesRegex(ValueError, "filename basename"):
            adapt_capture_package_reference(
                self.package(package_basename="folder/package.ca-package"),
                reference_id="capture-package:x",
                source_id="capture-session:x",
            )

    def test_rejects_invalid_package_byte_length(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive integer"):
            adapt_capture_package_reference(
                self.package(package_byte_length=0),
                reference_id="capture-package:x",
                source_id="capture-session:x",
            )

    def test_rejects_invalid_reference_lineage(self) -> None:
        with self.assertRaises(ValueError):
            adapt_capture_package_reference(
                self.package(),
                reference_id="",
                source_id="capture-session:x",
            )

    def test_result_is_immutable(self) -> None:
        result = adapt_capture_package_reference(
            self.package(),
            reference_id="capture-package:x",
            source_id="capture-session:x",
        )

        with self.assertRaises(FrozenInstanceError):
            result.reference = result.reference  # type: ignore[misc]

    def test_rejects_inconsistent_reference_kind(self) -> None:
        source = self.package()
        result = CapturePackageReferenceAdaptation(
            source=source,
            reference=MultimodalEvidenceReference(
                schema_version=CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
                reference_id="capture-package:x",
                kind=MultimodalEvidenceKind.OCR_TEXT,
                source_id="capture-session:x",
                locator=source.package_basename,
                source_fingerprint=source.package_sha256,
            ),
        )

        with self.assertRaisesRegex(ValueError, "CAPTURE_PACKAGE"):
            result.validate()

    def test_rejects_inconsistent_locator(self) -> None:
        source = self.package()
        result = CapturePackageReferenceAdaptation(
            source=source,
            reference=MultimodalEvidenceReference(
                schema_version=CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
                reference_id="capture-package:x",
                kind=MultimodalEvidenceKind.CAPTURE_PACKAGE,
                source_id="capture-session:x",
                locator="different.ca-package",
                source_fingerprint=source.package_sha256,
            ),
        )

        with self.assertRaisesRegex(ValueError, "package_basename"):
            result.validate()

    def test_rejects_inconsistent_fingerprint(self) -> None:
        source = self.package()
        result = CapturePackageReferenceAdaptation(
            source=source,
            reference=MultimodalEvidenceReference(
                schema_version=CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
                reference_id="capture-package:x",
                kind=MultimodalEvidenceKind.CAPTURE_PACKAGE,
                source_id="capture-session:x",
                locator=source.package_basename,
                source_fingerprint="c" * 64,
            ),
        )

        with self.assertRaisesRegex(ValueError, "package_sha256"):
            result.validate()


if __name__ == "__main__":
    unittest.main()
