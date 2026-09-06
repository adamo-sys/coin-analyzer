from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import unittest

from domain_relationships import (
    CURRENT_DOMAIN_RELATIONSHIP_SCHEMA_VERSION,
    DomainNodeRef,
    DomainRelationshipEdge,
)


class DomainRelationshipTests(unittest.TestCase):
    def _edge(self) -> DomainRelationshipEdge:
        edge = DomainRelationshipEdge(
            schema_version=CURRENT_DOMAIN_RELATIONSHIP_SCHEMA_VERSION,
            edge_id="edge-coin-denomination",
            source=DomainNodeRef(node_type="coin", node_id="coin-1"),
            relationship_type="has_denomination",
            target=DomainNodeRef(node_type="denomination", node_id="25-cents"),
            evidence_refs=("evidence-1", "evidence-2"),
        )
        edge.validate()
        return edge

    def test_valid_explicit_edge_preserves_identity(self) -> None:
        edge = self._edge()
        self.assertEqual(
            edge.identity,
            (
                "edge-coin-denomination",
                ("coin", "coin-1"),
                "has_denomination",
                ("denomination", "25-cents"),
            ),
        )

    def test_node_identity_is_exact_and_immutable(self) -> None:
        node = DomainNodeRef(node_type="observation", node_id="obs-1")
        node.validate()
        self.assertEqual(node.identity, ("observation", "obs-1"))
        with self.assertRaises(FrozenInstanceError):
            node.node_id = "changed"  # type: ignore[misc]

    def test_edge_is_immutable(self) -> None:
        edge = self._edge()
        with self.assertRaises(FrozenInstanceError):
            edge.edge_id = "changed"  # type: ignore[misc]

    def test_rejects_unsupported_schema_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            replace(self._edge(), schema_version="2").validate()

    def test_rejects_empty_node_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "node_type"):
            DomainNodeRef(node_type="", node_id="coin-1").validate()

    def test_rejects_empty_node_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "node_id"):
            DomainNodeRef(node_type="coin", node_id=" ").validate()

    def test_rejects_invalid_source_type(self) -> None:
        edge = self._edge()
        with self.assertRaisesRegex(TypeError, "source"):
            replace(edge, source="coin-1").validate()  # type: ignore[arg-type]

    def test_rejects_invalid_target_type(self) -> None:
        edge = self._edge()
        with self.assertRaisesRegex(TypeError, "target"):
            replace(edge, target="denomination").validate()  # type: ignore[arg-type]

    def test_rejects_empty_relationship_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "relationship_type"):
            replace(self._edge(), relationship_type="").validate()

    def test_rejects_self_edge(self) -> None:
        node = DomainNodeRef(node_type="coin", node_id="coin-1")
        edge = DomainRelationshipEdge(
            schema_version=CURRENT_DOMAIN_RELATIONSHIP_SCHEMA_VERSION,
            edge_id="self-edge",
            source=node,
            relationship_type="related_to",
            target=node,
        )
        with self.assertRaisesRegex(ValueError, "distinct"):
            edge.validate()

    def test_evidence_refs_must_be_tuple(self) -> None:
        with self.assertRaisesRegex(TypeError, "tuple"):
            replace(self._edge(), evidence_refs=["evidence-1"]).validate()  # type: ignore[arg-type]

    def test_evidence_refs_must_be_sorted(self) -> None:
        with self.assertRaisesRegex(ValueError, "sorted"):
            replace(
                self._edge(), evidence_refs=("evidence-b", "evidence-a")
            ).validate()

    def test_evidence_refs_must_be_unique(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicates"):
            replace(
                self._edge(), evidence_refs=("evidence-a", "evidence-a")
            ).validate()

    def test_empty_evidence_refs_are_valid(self) -> None:
        edge = replace(self._edge(), evidence_refs=())
        edge.validate()
        self.assertEqual(edge.evidence_refs, ())

    def test_contract_does_not_normalize_domain_labels(self) -> None:
        edge = DomainRelationshipEdge(
            schema_version=CURRENT_DOMAIN_RELATIONSHIP_SCHEMA_VERSION,
            edge_id="edge-exact-labels",
            source=DomainNodeRef(node_type="Coin Record", node_id="Coin-001"),
            relationship_type="Collector Declared Link",
            target=DomainNodeRef(node_type="Diagnostic", node_id="Mintmark-A"),
        )
        edge.validate()
        self.assertEqual(edge.source.node_type, "Coin Record")
        self.assertEqual(edge.relationship_type, "Collector Declared Link")
        self.assertEqual(edge.target.node_id, "Mintmark-A")


if __name__ == "__main__":
    unittest.main()
