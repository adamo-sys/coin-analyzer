from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from domain_relationship_query import (
    DomainRelationshipQuery,
    RelationshipDirection,
    select_domain_relationship_edges,
)
from domain_relationships import (
    CURRENT_DOMAIN_RELATIONSHIP_SCHEMA_VERSION,
    DomainNodeRef,
    DomainRelationshipEdge,
)


def _node(node_type: str, node_id: str) -> DomainNodeRef:
    return DomainNodeRef(node_type=node_type, node_id=node_id)


def _edge(
    edge_id: str,
    source: DomainNodeRef,
    relationship_type: str,
    target: DomainNodeRef,
) -> DomainRelationshipEdge:
    return DomainRelationshipEdge(
        schema_version=CURRENT_DOMAIN_RELATIONSHIP_SCHEMA_VERSION,
        edge_id=edge_id,
        source=source,
        relationship_type=relationship_type,
        target=target,
        evidence_refs=(),
    )


class DomainRelationshipQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.coin = _node("coin", "coin-1")
        self.year = _node("year", "1967")
        self.diagnostic = _node("diagnostic", "diag-1")
        self.observation = _node("observation", "obs-1")
        self.edges = (
            _edge("edge-1", self.coin, "has_year", self.year),
            _edge("edge-2", self.coin, "has_diagnostic", self.diagnostic),
            _edge("edge-3", self.observation, "supports", self.diagnostic),
        )

    def test_outgoing_selection_is_exact(self) -> None:
        query = DomainRelationshipQuery(
            node=self.coin,
            direction=RelationshipDirection.OUTGOING,
        )
        result = select_domain_relationship_edges(query, self.edges)
        self.assertEqual(result, self.edges[:2])
        self.assertIs(result[0], self.edges[0])
        self.assertIs(result[1], self.edges[1])

    def test_incoming_selection_is_exact(self) -> None:
        query = DomainRelationshipQuery(
            node=self.diagnostic,
            direction=RelationshipDirection.INCOMING,
        )
        self.assertEqual(
            select_domain_relationship_edges(query, self.edges),
            (self.edges[1], self.edges[2]),
        )

    def test_either_direction_selects_incident_edges_only(self) -> None:
        query = DomainRelationshipQuery(node=self.diagnostic)
        self.assertEqual(
            select_domain_relationship_edges(query, self.edges),
            (self.edges[1], self.edges[2]),
        )

    def test_relationship_type_filter_is_exact(self) -> None:
        query = DomainRelationshipQuery(
            node=self.coin,
            relationship_types=("has_year",),
        )
        self.assertEqual(select_domain_relationship_edges(query, self.edges), (self.edges[0],))

    def test_multiple_relationship_types_must_be_sorted(self) -> None:
        with self.assertRaisesRegex(ValueError, "sorted order"):
            DomainRelationshipQuery(
                node=self.coin,
                relationship_types=("has_year", "has_diagnostic"),
            ).validate()

    def test_duplicate_relationship_types_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicates"):
            DomainRelationshipQuery(
                node=self.coin,
                relationship_types=("has_year", "has_year"),
            ).validate()

    def test_max_results_bounds_output(self) -> None:
        query = DomainRelationshipQuery(node=self.coin, max_results=1)
        self.assertEqual(select_domain_relationship_edges(query, self.edges), (self.edges[0],))

    def test_empty_match_returns_empty_tuple(self) -> None:
        query = DomainRelationshipQuery(node=_node("coin", "missing"))
        self.assertEqual(select_domain_relationship_edges(query, self.edges), ())

    def test_unsorted_edge_input_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "ordered by edge_id"):
            select_domain_relationship_edges(
                DomainRelationshipQuery(node=self.coin),
                (self.edges[1], self.edges[0]),
            )

    def test_duplicate_edge_ids_fail_closed(self) -> None:
        duplicate = _edge(
            "edge-1",
            self.observation,
            "supports",
            self.diagnostic,
        )
        with self.assertRaisesRegex(ValueError, "duplicate edge IDs"):
            select_domain_relationship_edges(
                DomainRelationshipQuery(node=self.coin),
                (self.edges[0], duplicate),
            )

    def test_edges_must_be_tuple(self) -> None:
        with self.assertRaisesRegex(TypeError, "edges must be a tuple"):
            select_domain_relationship_edges(  # type: ignore[arg-type]
                DomainRelationshipQuery(node=self.coin),
                list(self.edges),
            )

    def test_wrong_edge_type_fails_closed(self) -> None:
        with self.assertRaisesRegex(TypeError, "DomainRelationshipEdge"):
            select_domain_relationship_edges(  # type: ignore[arg-type]
                DomainRelationshipQuery(node=self.coin),
                ("edge",),
            )

    def test_query_is_immutable(self) -> None:
        query = DomainRelationshipQuery(node=self.coin)
        with self.assertRaises(FrozenInstanceError):
            query.max_results = 5  # type: ignore[misc]

    def test_invalid_direction_type_fails_closed(self) -> None:
        with self.assertRaisesRegex(TypeError, "RelationshipDirection"):
            DomainRelationshipQuery(  # type: ignore[arg-type]
                node=self.coin,
                direction="OUTGOING",
            ).validate()

    def test_invalid_max_results_fail_closed(self) -> None:
        for value in (0, 1001):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "between 1 and 1000"):
                    DomainRelationshipQuery(node=self.coin, max_results=value).validate()

    def test_boolean_max_results_is_not_integer(self) -> None:
        with self.assertRaisesRegex(TypeError, "integer"):
            DomainRelationshipQuery(node=self.coin, max_results=True).validate()  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
