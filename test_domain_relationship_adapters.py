from __future__ import annotations

import unittest

from domain_relationship_adapters import (
    CANDIDATE_NODE_TYPE,
    COLLECTION_ITEM_NODE_TYPE,
    LINKED_CANDIDATE_RELATIONSHIP,
    LINKED_COLLECTION_ITEM_RELATIONSHIP,
    PHOTO_NODE_TYPE,
    adapt_captured_photo_candidate_relationship,
    adapt_captured_photo_collection_item_relationship,
    project_captured_photo_relationships,
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


class CapturedPhotoCandidateRelationshipAdapterTests(unittest.TestCase):
    def _photo(self) -> CapturedPhoto:
        return CapturedPhoto(
            photo_id="photo-candidate-001",
            file_path="synthetic/listing.jpg",
            linked_candidate_id="candidate-123",
            linked_collection_item_id="item-unrelated",
        )

    def test_preserves_explicit_candidate_endpoint_and_edge_identities(self) -> None:
        edge = adapt_captured_photo_candidate_relationship(
            photo=self._photo(),
            edge_id="edge-candidate-001",
        )

        self.assertIsInstance(edge, DomainRelationshipEdge)
        self.assertEqual(PHOTO_NODE_TYPE, edge.source.node_type)
        self.assertEqual("photo-candidate-001", edge.source.node_id)
        self.assertEqual(CANDIDATE_NODE_TYPE, edge.target.node_type)
        self.assertEqual("candidate-123", edge.target.node_id)
        self.assertEqual(LINKED_CANDIDATE_RELATIONSHIP, edge.relationship_type)
        self.assertEqual("edge-candidate-001", edge.edge_id)
        edge.validate()

    def test_preserves_candidate_evidence_refs_exactly(self) -> None:
        evidence_refs = ("evidence:candidate:a", "evidence:candidate:b")

        edge = adapt_captured_photo_candidate_relationship(
            photo=self._photo(),
            edge_id="edge-candidate-002",
            evidence_refs=evidence_refs,
        )

        self.assertEqual(evidence_refs, edge.evidence_refs)
        self.assertIs(evidence_refs, edge.evidence_refs)

    def test_missing_linked_candidate_id_fails_closed(self) -> None:
        photo = self._photo()
        photo.linked_candidate_id = ""

        with self.assertRaises(ValueError):
            adapt_captured_photo_candidate_relationship(
                photo=photo,
                edge_id="edge-candidate-003",
            )

    def test_invalid_linked_candidate_id_fails_closed(self) -> None:
        photo = self._photo()
        photo.linked_candidate_id = None  # type: ignore[assignment]

        with self.assertRaises(TypeError):
            adapt_captured_photo_candidate_relationship(
                photo=photo,
                edge_id="edge-candidate-004",
            )

    def test_missing_candidate_photo_id_fails_closed(self) -> None:
        photo = self._photo()
        photo.photo_id = ""

        with self.assertRaises(ValueError):
            adapt_captured_photo_candidate_relationship(
                photo=photo,
                edge_id="edge-candidate-005",
            )

    def test_invalid_candidate_photo_id_fails_closed(self) -> None:
        photo = self._photo()
        photo.photo_id = None  # type: ignore[assignment]

        with self.assertRaises(TypeError):
            adapt_captured_photo_candidate_relationship(
                photo=photo,
                edge_id="edge-candidate-006",
            )

    def test_candidate_adapter_does_not_mutate_captured_photo(self) -> None:
        photo = self._photo()
        before = photo.to_dict()

        adapt_captured_photo_candidate_relationship(
            photo=photo,
            edge_id="edge-candidate-007",
            evidence_refs=("evidence:candidate:a",),
        )

        self.assertEqual(before, photo.to_dict())

    def test_candidate_edge_id_is_required_and_never_generated(self) -> None:
        with self.assertRaises(TypeError):
            adapt_captured_photo_candidate_relationship(photo=self._photo())

        with self.assertRaises(ValueError):
            adapt_captured_photo_candidate_relationship(
                photo=self._photo(),
                edge_id="",
            )

    def test_candidate_evidence_refs_are_not_normalized_or_reordered(self) -> None:
        with self.assertRaises(ValueError):
            adapt_captured_photo_candidate_relationship(
                photo=self._photo(),
                edge_id="edge-candidate-008",
                evidence_refs=("evidence:candidate:b", "evidence:candidate:a"),
            )

    def test_candidate_adapter_rejects_non_captured_photo_input(self) -> None:
        with self.assertRaises(TypeError):
            adapt_captured_photo_candidate_relationship(
                photo=object(),  # type: ignore[arg-type]
                edge_id="edge-candidate-009",
            )

    def test_candidate_adapter_ignores_unrelated_collection_link(self) -> None:
        photo = self._photo()

        edge = adapt_captured_photo_candidate_relationship(
            photo=photo,
            edge_id="edge-candidate-010",
        )

        self.assertEqual("candidate-123", edge.target.node_id)
        self.assertNotEqual(photo.linked_collection_item_id, edge.target.node_id)


class CapturedPhotoRelationshipProjectionTests(unittest.TestCase):
    def _photo(
        self,
        *,
        collection_item_id: str = "",
        candidate_id: str = "",
    ) -> CapturedPhoto:
        return CapturedPhoto(
            photo_id="photo-projection-001",
            file_path="synthetic/projection.jpg",
            linked_collection_item_id=collection_item_id,
            linked_candidate_id=candidate_id,
        )

    def test_no_links_projects_empty_tuple(self) -> None:
        self.assertEqual((), project_captured_photo_relationships(photo=self._photo()))

    def test_collection_item_only_projects_one_explicit_edge(self) -> None:
        edge_refs = ("evidence:collection:a",)
        edges = project_captured_photo_relationships(
            photo=self._photo(collection_item_id="item-123"),
            collection_item_edge_id="edge-collection-001",
            collection_item_evidence_refs=edge_refs,
        )

        self.assertEqual(1, len(edges))
        edge = edges[0]
        self.assertEqual("edge-collection-001", edge.edge_id)
        self.assertEqual(PHOTO_NODE_TYPE, edge.source.node_type)
        self.assertEqual("photo-projection-001", edge.source.node_id)
        self.assertEqual(COLLECTION_ITEM_NODE_TYPE, edge.target.node_type)
        self.assertEqual("item-123", edge.target.node_id)
        self.assertEqual(LINKED_COLLECTION_ITEM_RELATIONSHIP, edge.relationship_type)
        self.assertIs(edge_refs, edge.evidence_refs)
        edge.validate()

    def test_candidate_only_projects_one_explicit_edge(self) -> None:
        edge_refs = ("evidence:candidate:a",)
        edges = project_captured_photo_relationships(
            photo=self._photo(candidate_id="candidate-123"),
            candidate_edge_id="edge-candidate-projection-001",
            candidate_evidence_refs=edge_refs,
        )

        self.assertEqual(1, len(edges))
        edge = edges[0]
        self.assertEqual("edge-candidate-projection-001", edge.edge_id)
        self.assertEqual(PHOTO_NODE_TYPE, edge.source.node_type)
        self.assertEqual("photo-projection-001", edge.source.node_id)
        self.assertEqual(CANDIDATE_NODE_TYPE, edge.target.node_type)
        self.assertEqual("candidate-123", edge.target.node_id)
        self.assertEqual(LINKED_CANDIDATE_RELATIONSHIP, edge.relationship_type)
        self.assertIs(edge_refs, edge.evidence_refs)
        edge.validate()

    def test_both_links_project_in_frozen_relationship_order(self) -> None:
        edges = project_captured_photo_relationships(
            photo=self._photo(
                collection_item_id="item-123",
                candidate_id="candidate-123",
            ),
            collection_item_edge_id="edge-z-collection",
            candidate_edge_id="edge-a-candidate",
        )

        self.assertEqual(2, len(edges))
        self.assertEqual(
            (
                LINKED_COLLECTION_ITEM_RELATIONSHIP,
                LINKED_CANDIDATE_RELATIONSHIP,
            ),
            tuple(edge.relationship_type for edge in edges),
        )
        self.assertEqual(
            ("edge-z-collection", "edge-a-candidate"),
            tuple(edge.edge_id for edge in edges),
        )
        for edge in edges:
            edge.validate()

    def test_present_collection_link_requires_collection_edge_id(self) -> None:
        with self.assertRaises(ValueError):
            project_captured_photo_relationships(
                photo=self._photo(collection_item_id="item-123")
            )

    def test_present_candidate_link_requires_candidate_edge_id(self) -> None:
        with self.assertRaises(ValueError):
            project_captured_photo_relationships(
                photo=self._photo(candidate_id="candidate-123")
            )

    def test_absent_collection_link_rejects_collection_edge_data(self) -> None:
        with self.assertRaises(ValueError):
            project_captured_photo_relationships(
                photo=self._photo(),
                collection_item_edge_id="edge-unused",
            )

        with self.assertRaises(ValueError):
            project_captured_photo_relationships(
                photo=self._photo(),
                collection_item_evidence_refs=("evidence:unused",),
            )

    def test_absent_candidate_link_rejects_candidate_edge_data(self) -> None:
        with self.assertRaises(ValueError):
            project_captured_photo_relationships(
                photo=self._photo(),
                candidate_edge_id="edge-unused",
            )

        with self.assertRaises(ValueError):
            project_captured_photo_relationships(
                photo=self._photo(),
                candidate_evidence_refs=("evidence:unused",),
            )

    def test_invalid_edge_ids_fail_through_existing_edge_validation(self) -> None:
        with self.assertRaises(ValueError):
            project_captured_photo_relationships(
                photo=self._photo(collection_item_id="item-123"),
                collection_item_edge_id="",
            )

        with self.assertRaises(ValueError):
            project_captured_photo_relationships(
                photo=self._photo(candidate_id="candidate-123"),
                candidate_edge_id="",
            )

    def test_invalid_evidence_refs_fail_through_existing_edge_validation(self) -> None:
        with self.assertRaises(ValueError):
            project_captured_photo_relationships(
                photo=self._photo(collection_item_id="item-123"),
                collection_item_edge_id="edge-collection-002",
                collection_item_evidence_refs=("evidence:b", "evidence:a"),
            )

        with self.assertRaises(ValueError):
            project_captured_photo_relationships(
                photo=self._photo(candidate_id="candidate-123"),
                candidate_edge_id="edge-candidate-projection-002",
                candidate_evidence_refs=("evidence:b", "evidence:a"),
            )

    def test_invalid_source_identity_fails_even_when_no_edges_would_emit(self) -> None:
        missing_photo_id = self._photo()
        missing_photo_id.photo_id = ""
        with self.assertRaises(ValueError):
            project_captured_photo_relationships(photo=missing_photo_id)

        invalid_collection_id = self._photo()
        invalid_collection_id.linked_collection_item_id = None  # type: ignore[assignment]
        with self.assertRaises(TypeError):
            project_captured_photo_relationships(photo=invalid_collection_id)

        invalid_candidate_id = self._photo()
        invalid_candidate_id.linked_candidate_id = None  # type: ignore[assignment]
        with self.assertRaises(TypeError):
            project_captured_photo_relationships(photo=invalid_candidate_id)

    def test_projection_rejects_non_captured_photo(self) -> None:
        with self.assertRaises(TypeError):
            project_captured_photo_relationships(
                photo=object(),  # type: ignore[arg-type]
            )

    def test_projection_does_not_mutate_photo(self) -> None:
        photo = self._photo(
            collection_item_id="item-123",
            candidate_id="candidate-123",
        )
        before = photo.to_dict()

        project_captured_photo_relationships(
            photo=photo,
            collection_item_edge_id="edge-collection-003",
            candidate_edge_id="edge-candidate-projection-003",
            collection_item_evidence_refs=("evidence:collection:a",),
            candidate_evidence_refs=("evidence:candidate:a",),
        )

        self.assertEqual(before, photo.to_dict())


if __name__ == "__main__":
    unittest.main()
