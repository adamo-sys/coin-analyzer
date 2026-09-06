import dataclasses
import unittest

from multimodal_evidence_references import (
    CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
    MultimodalEvidenceKind,
    MultimodalEvidenceReference,
)
from multimodal_retrieval_binding import MultimodalRetrievalBinding
from retrieval_contracts import (
    CURRENT_RETRIEVAL_SCHEMA_VERSION,
    RetrievalProvenance,
    RetrievableEvidenceItem,
)


class MultimodalRetrievalBindingTests(unittest.TestCase):
    def _reference(
        self,
        reference_id: str,
        *,
        kind: MultimodalEvidenceKind = MultimodalEvidenceKind.IMAGE_OBVERSE,
        locator: str | None = None,
    ) -> MultimodalEvidenceReference:
        return MultimodalEvidenceReference(
            schema_version=CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
            reference_id=reference_id,
            kind=kind,
            source_id="source:synthetic:001",
            locator=locator or f"synthetic/{reference_id}",
            source_fingerprint="sha256:synthetic",
        )

    def _item(
        self,
        evidence_refs: tuple[str, ...],
    ) -> RetrievableEvidenceItem:
        return RetrievableEvidenceItem(
            schema_version=CURRENT_RETRIEVAL_SCHEMA_VERSION,
            item_id="item:synthetic:001",
            text="synthetic Canadian cent evidence",
            provenance=RetrievalProvenance(
                source_type="confirmed_observation",
                source_id="observation:synthetic:001",
                source_fingerprint="sha256:observation-synthetic",
                evidence_refs=evidence_refs,
            ),
            metadata=(("country", "Canada"),),
        )

    def test_valid_exact_binding(self) -> None:
        references = (
            self._reference("ref:a"),
            self._reference(
                "ref:b",
                kind=MultimodalEvidenceKind.OCR_TEXT,
                locator="synthetic/ocr.txt",
            ),
        )
        binding = MultimodalRetrievalBinding(
            item=self._item(("ref:a", "ref:b")),
            references=references,
        )

        binding.validate()
        self.assertEqual(binding.reference_ids, ("ref:a", "ref:b"))

    def test_binding_is_frozen(self) -> None:
        binding = MultimodalRetrievalBinding(item=self._item(()))

        with self.assertRaises(dataclasses.FrozenInstanceError):
            binding.references = ()  # type: ignore[misc]

    def test_invalid_item_type_fails_closed(self) -> None:
        binding = MultimodalRetrievalBinding(item=object())  # type: ignore[arg-type]

        with self.assertRaisesRegex(TypeError, "RetrievableEvidenceItem"):
            binding.validate()

    def test_references_must_be_tuple(self) -> None:
        binding = MultimodalRetrievalBinding(
            item=self._item(("ref:a",)),
            references=[self._reference("ref:a")],  # type: ignore[arg-type]
        )

        with self.assertRaisesRegex(TypeError, "references must be a tuple"):
            binding.validate()

    def test_invalid_reference_type_fails_closed(self) -> None:
        binding = MultimodalRetrievalBinding(
            item=self._item(("ref:a",)),
            references=(object(),),  # type: ignore[arg-type]
        )

        with self.assertRaisesRegex(TypeError, "MultimodalEvidenceReference"):
            binding.validate()

    def test_unsorted_reference_ids_fail_closed(self) -> None:
        binding = MultimodalRetrievalBinding(
            item=self._item(("ref:a", "ref:b")),
            references=(
                self._reference("ref:b"),
                self._reference("ref:a"),
            ),
        )

        with self.assertRaisesRegex(ValueError, "deterministic reference_id order"):
            binding.validate()

    def test_duplicate_reference_ids_fail_closed(self) -> None:
        binding = MultimodalRetrievalBinding(
            item=self._item(("ref:a",)),
            references=(
                self._reference("ref:a"),
                self._reference("ref:a"),
            ),
        )

        with self.assertRaisesRegex(ValueError, "duplicate reference_id"):
            binding.validate()

    def test_missing_typed_reference_fails_closed(self) -> None:
        binding = MultimodalRetrievalBinding(
            item=self._item(("ref:a", "ref:b")),
            references=(self._reference("ref:a"),),
        )

        with self.assertRaisesRegex(ValueError, "exactly match"):
            binding.validate()

    def test_extra_typed_reference_fails_closed(self) -> None:
        binding = MultimodalRetrievalBinding(
            item=self._item(("ref:a",)),
            references=(
                self._reference("ref:a"),
                self._reference("ref:b"),
            ),
        )

        with self.assertRaisesRegex(ValueError, "exactly match"):
            binding.validate()

    def test_invalid_nested_reference_fails_closed(self) -> None:
        reference = MultimodalEvidenceReference(
            schema_version="999",
            reference_id="ref:a",
            kind=MultimodalEvidenceKind.IMAGE_DETAIL,
            source_id="source:synthetic:001",
            locator="synthetic/detail.jpg",
        )
        binding = MultimodalRetrievalBinding(
            item=self._item(("ref:a",)),
            references=(reference,),
        )

        with self.assertRaisesRegex(ValueError, "Unsupported multimodal"):
            binding.validate()

    def test_empty_binding_is_valid_when_item_has_no_evidence_refs(self) -> None:
        binding = MultimodalRetrievalBinding(item=self._item(()), references=())

        binding.validate()
        self.assertEqual(binding.reference_ids, ())

    def test_nonexistent_synthetic_locators_require_no_filesystem_access(self) -> None:
        references = (
            self._reference(
                "ref:a",
                locator="synthetic/definitely-not-a-real-file/obverse.jpg",
            ),
        )
        binding = MultimodalRetrievalBinding(
            item=self._item(("ref:a",)),
            references=references,
        )

        binding.validate()
        self.assertEqual(binding.reference_ids, ("ref:a",))


if __name__ == "__main__":
    unittest.main()
