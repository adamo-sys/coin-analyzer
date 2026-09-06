"""Bounded deterministic relationship selection for Issue #93 Slice E.

This module performs only exact one-hop selection over caller-supplied explicit
relationship edges. It does not infer relationships, recurse, traverse a graph,
persist data, call models, or mutate collection/observation authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain_relationships import DomainNodeRef, DomainRelationshipEdge


_MAX_RELATIONSHIP_TYPES = 64
_MAX_RESULTS = 1_000
_MAX_RELATIONSHIP_TYPE_CHARS = 128


class RelationshipDirection(str, Enum):
    OUTGOING = "OUTGOING"
    INCOMING = "INCOMING"
    EITHER = "EITHER"


def _validate_relationship_types(values: object) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError("relationship_types must be a tuple.")
    if len(values) > _MAX_RELATIONSHIP_TYPES:
        raise ValueError("relationship_types contains too many items.")
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise TypeError(f"relationship_types[{index}] must be a string.")
        if not value.strip():
            raise ValueError(f"relationship_types[{index}] must not be empty.")
        if len(value) > _MAX_RELATIONSHIP_TYPE_CHARS:
            raise ValueError(
                f"relationship_types[{index}] exceeds maximum length "
                f"{_MAX_RELATIONSHIP_TYPE_CHARS}."
            )
    if values != tuple(sorted(values)):
        raise ValueError("relationship_types must be in deterministic sorted order.")
    if len(set(values)) != len(values):
        raise ValueError("relationship_types must not contain duplicates.")
    return values


@dataclass(frozen=True, slots=True)
class DomainRelationshipQuery:
    """Exact one-hop selection criteria over explicit domain edges."""

    node: DomainNodeRef
    direction: RelationshipDirection = RelationshipDirection.EITHER
    relationship_types: tuple[str, ...] = ()
    max_results: int = 100

    def validate(self) -> None:
        if not isinstance(self.node, DomainNodeRef):
            raise TypeError("node must be a DomainNodeRef.")
        self.node.validate()
        if not isinstance(self.direction, RelationshipDirection):
            raise TypeError("direction must be a RelationshipDirection.")
        _validate_relationship_types(self.relationship_types)
        if isinstance(self.max_results, bool) or not isinstance(self.max_results, int):
            raise TypeError("max_results must be an integer.")
        if self.max_results < 1 or self.max_results > _MAX_RESULTS:
            raise ValueError(f"max_results must be between 1 and {_MAX_RESULTS}.")


def _matches_direction(query: DomainRelationshipQuery, edge: DomainRelationshipEdge) -> bool:
    if query.direction is RelationshipDirection.OUTGOING:
        return edge.source == query.node
    if query.direction is RelationshipDirection.INCOMING:
        return edge.target == query.node
    return edge.source == query.node or edge.target == query.node


def select_domain_relationship_edges(
    query: DomainRelationshipQuery,
    edges: tuple[DomainRelationshipEdge, ...],
) -> tuple[DomainRelationshipEdge, ...]:
    """Return an exact bounded subset without inference or recursive traversal.

    The edge collection must already be deterministically ordered by ``edge_id``
    and duplicate-free. Matching preserves original edge objects and order.
    """

    if not isinstance(query, DomainRelationshipQuery):
        raise TypeError("query must be a DomainRelationshipQuery.")
    query.validate()
    if not isinstance(edges, tuple):
        raise TypeError("edges must be a tuple.")

    edge_ids: list[str] = []
    for edge in edges:
        if not isinstance(edge, DomainRelationshipEdge):
            raise TypeError("edges must contain DomainRelationshipEdge values.")
        edge.validate()
        edge_ids.append(edge.edge_id)

    if edge_ids != sorted(edge_ids):
        raise ValueError("edges must be ordered by edge_id.")
    if len(set(edge_ids)) != len(edge_ids):
        raise ValueError("edges must not contain duplicate edge IDs.")

    selected: list[DomainRelationshipEdge] = []
    relationship_types = set(query.relationship_types)

    for edge in edges:
        if not _matches_direction(query, edge):
            continue
        if relationship_types and edge.relationship_type not in relationship_types:
            continue
        selected.append(edge)
        if len(selected) == query.max_results:
            break

    return tuple(selected)
