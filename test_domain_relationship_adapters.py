from __future__ import annotations

import unittest

from domain_relationship_adapters import (
    COLLECTION_ITEM_NODE_TYPE,
    LINKED_COLLECTION_ITEM_RELATIONSHIP,
    PHOTO_NODE_TYPE,
    adapt_captured_photo_collection_item_relationship,
)
from domain_relationships import DomainRelationshipEdge
from photo_capture_workflow import CapturedPhoto


class CapturedPhotoCollectionItemRelationshipAdapterTests(unittest.TestCase):
    def _photo(self) -> CapturedPhoto:
        return CapturedPhoto(
            photo_id="photo-001",
            file_path="synthetic/front.jpg",
            linked_collection_item_id="item-123",
        )

    def test_preserves_explicit_endpoint_and_edge_identities(self) -> None:
        photo = self._photo()

        edge = adapt_captured_photo_collection_item_relationship(
            photo=photo,
            edge_id="edge-explicit-001",
        )

        self.assertIsInstance(edge, DomainRelationshipEdge)
        self.assertEqual(PHOTO_NODE_TYPE, edge.source.node_type)
        self.assertEqual("photo-001", edge.source.node_id)
        self.assertEqual(COLLECTION_ITEM_NODE_TYPE, edge.target.node_type)
        self.assertEqual("item-123", edge.target.node_id)
        self.assertEqual(LINKED_COLLECTION_ITEM_RELATIONSHIP, edge.relationship_type)
        self.assertEqual("edge-explicit-001", edge.edge_id)
        edge.validate()

    def test_preserves_caller_supplied_evidence_refs_exactly(self) -> None:
        evidence_refs = ("evidence:a", "evidence:b")

        edge = adapt_captured_photo_collection_item_relationship(
            photo=self._photo(),
            edge_id="edge-explicit-002",
            evidence_refs=evidence_refs,
        )

        self.assertEqual(evidence_refs, edge.evidence_refs)
        self.assertIs(evidence_refs, edge.evidence_refs)

    def test_missing_linked_collection_item_id_fails_closed(self) -> None:
        photo = self._photo()
        photo.linked_collection_item_id = ""

        with self.assertRaises(ValueError):
            adapt_captured_photo_collection_item_relationship(
                photo=photo,
                edge_id="edge-explicit-003",
            )

    def test_missing_photo_id_fails_closed(self) -> None:
        photo = self._photo()
        photo.photo_id = ""

        with self.assertRaises(ValueError):
            adapt_captured_photo_collection_item_relationship(
                photo=photo,
                edge_id="edge-explicit-004",
            )

    def test_invalid_photo_id_fails_closed(self) -> None:
        photo = self._photo()
        photo.photo_id = None  # type: ignore[assignment]

        with self.assertRaises(TypeError):
            adapt_captured_photo_collection_item_relationship(
                photo=photo,
                edge_id="edge-explicit-005",
            )

    def test_adapter_does_not_mutate_captured_photo(self) -> None:
        photo = self._photo()
        before = photo.to_dict()

        adapt_captured_photo_collection_item_relationship(
            photo=photo,
            edge_id="edge-explicit-006",
            evidence_refs=("evidence:a",),
        )

        self.assertEqual(before, photo.to_dict())

    def test_edge_id_is_required_and_never_generated(self) -> None:
        with self.assertRaises(TypeError):
            adapt_captured_photo_collection_item_relationship(photo=self._photo())

        with self.assertRaises(ValueError):
            adapt_captured_photo_collection_item_relationship(
                photo=self._photo(),
                edge_id="",
            )

    def test_evidence_refs_are_not_normalized_or_reordered(self) -> None:
        with self.assertRaises(ValueError):
            adapt_captured_photo_collection_item_relationship(
                photo=self._photo(),
                edge_id="edge-explicit-007",
                evidence_refs=("evidence:b", "evidence:a"),
            )

    def test_rejects_non_captured_photo_input(self) -> None:
        with self.assertRaises(TypeError):
            adapt_captured_photo_collection_item_relationship(
                photo=object(),  # type: ignore[arg-type]
                edge_id="edge-explicit-008",
            )


if __name__ == "__main__":
    unittest.main()
