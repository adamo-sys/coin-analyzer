import dataclasses
import unittest

from multimodal_evidence_references import (
    CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
    MultimodalEvidenceKind,
    MultimodalEvidenceReference,
)


class MultimodalEvidenceReferenceTests(unittest.TestCase):
    def _reference(
        self,
        *,
        kind: MultimodalEvidenceKind = MultimodalEvidenceKind.IMAGE_OBVERSE,
        reference_id: str = "ref:synthetic:001",
        source_id: str = "source:synthetic:001",
        locator: str = "synthetic/coin/obverse.jpg",
        source_fingerprint: str | None = "sha256:synthetic",
    ) -> MultimodalEvidenceReference:
        return MultimodalEvidenceReference(
            schema_version=CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
            reference_id=reference_id,
            kind=kind,
            source_id=source_id,
            locator=locator,
            source_fingerprint=source_fingerprint,
        )

    def test_all_reference_kinds_validate(self) -> None:
        for kind in MultimodalEvidenceKind:
            with self.subTest(kind=kind):
                reference = self._reference(
                    kind=kind,
                    reference_id=f"ref:{kind.value.casefold()}",
                    locator=f"synthetic/{kind.value.casefold()}",
                )
                reference.validate()

    def test_reference_is_frozen(self) -> None:
        reference = self._reference()

        with self.assertRaises(dataclasses.FrozenInstanceError):
            reference.reference_id = "changed"  # type: ignore[misc]

    def test_unsupported_schema_fails_closed(self) -> None:
        reference = MultimodalEvidenceReference(
            schema_version="999",
            reference_id="ref:synthetic",
            kind=MultimodalEvidenceKind.OCR_TEXT,
            source_id="source:synthetic",
            locator="synthetic/ocr.txt",
        )

        with self.assertRaisesRegex(ValueError, "Unsupported multimodal"):
            reference.validate()

    def test_blank_reference_id_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "reference_id must not be empty"):
            self._reference(reference_id="   ").validate()

    def test_invalid_kind_fails_closed(self) -> None:
        reference = MultimodalEvidenceReference(
            schema_version=CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
            reference_id="ref:synthetic",
            kind="IMAGE_OBVERSE",  # type: ignore[arg-type]
            source_id="source:synthetic",
            locator="synthetic/obverse.jpg",
        )

        with self.assertRaisesRegex(TypeError, "MultimodalEvidenceKind"):
            reference.validate()

    def test_blank_source_id_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "source_id must not be empty"):
            self._reference(source_id="").validate()

    def test_blank_locator_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "locator must not be empty"):
            self._reference(locator="\t").validate()

    def test_blank_optional_fingerprint_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "source_fingerprint must not be empty",
        ):
            self._reference(source_fingerprint=" ").validate()

    def test_absent_optional_fingerprint_is_valid(self) -> None:
        self._reference(source_fingerprint=None).validate()

    def test_oversized_bounded_fields_fail_closed(self) -> None:
        cases = (
            ("reference_id", "x" * 16_385),
            ("source_id", "x" * 16_385),
            ("locator", "x" * 16_385),
            ("source_fingerprint", "x" * 4_097),
        )

        for field_name, value in cases:
            with self.subTest(field=field_name):
                kwargs = {field_name: value}
                with self.assertRaisesRegex(ValueError, "exceeds maximum length"):
                    self._reference(**kwargs).validate()  # type: ignore[arg-type]

    def test_equality_and_identity_are_deterministic(self) -> None:
        first = self._reference()
        second = self._reference()

        self.assertEqual(first, second)
        self.assertEqual(first.identity, second.identity)
        self.assertEqual(
            first.identity,
            (
                "ref:synthetic:001",
                "IMAGE_OBVERSE",
                "source:synthetic:001",
                "synthetic/coin/obverse.jpg",
                "sha256:synthetic",
            ),
        )

    def test_locator_is_a_reference_not_an_existence_requirement(self) -> None:
        reference = self._reference(
            locator="synthetic/does-not-exist/private-looking-name.jpg"
        )

        reference.validate()
        self.assertEqual(
            reference.locator,
            "synthetic/does-not-exist/private-looking-name.jpg",
        )


if __name__ == "__main__":
    unittest.main()
