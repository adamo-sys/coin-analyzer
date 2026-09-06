"""Pure adapters for explicit Issue #93 Slice E relationships.

Adapters in this module preserve caller- and source-supplied identities exactly.
They do not infer, generate, persist, traverse, promote, or mutate relationships.
"""

from __future__ import annotations

from domain_relationships import (
    CURRENT_DOMAIN_RELATIONSHIP_SCHEMA_VERSION,
    DomainNodeRef,
    DomainRelationshipEdge,
)
from photo_capture_workflow import CapturedPhoto


PHOTO_NODE_TYPE = "photo"
COLLECTION_ITEM_NODE_TYPE = "collection_item"
CANDIDATE_NODE_TYPE = "candidate"
LINKED_COLLECTION_ITEM_RELATIONSHIP = "linked_collection_item"
LINKED_CANDIDATE_RELATIONSHIP = "linked_candidate"


def adapt_captured_photo_collection_item_relationship(
    *,
    photo: CapturedPhoto,
    edge_id: str,
    evidence_refs: tuple[str, ...] = (),
) -> DomainRelationshipEdge:
    """Adapt one explicit CapturedPhoto -> collection-item linkage.

    Both endpoint identities already exist on ``CapturedPhoto``. ``edge_id`` and
    ``evidence_refs`` are caller supplied and are never generated or normalized
    here. Existing ``DomainRelationshipEdge`` validation is the fail-closed gate.
    """

    if not isinstance(photo, CapturedPhoto):
        raise TypeError("photo must be a CapturedPhoto.")

    edge = DomainRelationshipEdge(
        schema_version=CURRENT_DOMAIN_RELATIONSHIP_SCHEMA_VERSION,
        edge_id=edge_id,
        source=DomainNodeRef(
            node_type=PHOTO_NODE_TYPE,
            node_id=photo.photo_id,
        ),
        relationship_type=LINKED_COLLECTION_ITEM_RELATIONSHIP,
        target=DomainNodeRef(
            node_type=COLLECTION_ITEM_NODE_TYPE,
            node_id=photo.linked_collection_item_id,
        ),
        evidence_refs=evidence_refs,
    )
    edge.validate()
    return edge


def adapt_captured_photo_candidate_relationship(
    *,
    photo: CapturedPhoto,
    edge_id: str,
    evidence_refs: tuple[str, ...] = (),
) -> DomainRelationshipEdge:
    """Adapt one explicit CapturedPhoto -> candidate linkage.

    Both endpoint identities already exist on ``CapturedPhoto``. ``edge_id`` and
    ``evidence_refs`` are caller supplied and are never generated or normalized
    here. Existing ``DomainRelationshipEdge`` validation is the fail-closed gate.
    """

    if not isinstance(photo, CapturedPhoto):
        raise TypeError("photo must be a CapturedPhoto.")

    edge = DomainRelationshipEdge(
        schema_version=CURRENT_DOMAIN_RELATIONSHIP_SCHEMA_VERSION,
        edge_id=edge_id,
        source=DomainNodeRef(
            node_type=PHOTO_NODE_TYPE,
            node_id=photo.photo_id,
        ),
        relationship_type=LINKED_CANDIDATE_RELATIONSHIP,
        target=DomainNodeRef(
            node_type=CANDIDATE_NODE_TYPE,
            node_id=photo.linked_candidate_id,
        ),
        evidence_refs=evidence_refs,
    )
    edge.validate()
    return edge


def project_captured_photo_relationships(
    *,
    photo: CapturedPhoto,
    collection_item_edge_id: str | None = None,
    candidate_edge_id: str | None = None,
    collection_item_evidence_refs: tuple[str, ...] = (),
    candidate_evidence_refs: tuple[str, ...] = (),
) -> tuple[DomainRelationshipEdge, ...]:
    """Project only the explicit relationships already stored on a photo.

    Edge identifiers remain caller supplied. Absent source relationships do not
    produce edges, and caller data for an absent relationship is rejected rather
    than interpreted as permission to infer a relationship.
    """

    if not isinstance(photo, CapturedPhoto):
        raise TypeError("photo must be a CapturedPhoto.")
    if not isinstance(photo.photo_id, str):
        raise TypeError("photo.photo_id must be a string.")
    if not photo.photo_id:
        raise ValueError("photo.photo_id must not be empty.")
    if not isinstance(photo.linked_collection_item_id, str):
        raise TypeError("photo.linked_collection_item_id must be a string.")
    if not isinstance(photo.linked_candidate_id, str):
        raise TypeError("photo.linked_candidate_id must be a string.")

    has_collection_item = bool(photo.linked_collection_item_id)
    has_candidate = bool(photo.linked_candidate_id)

    if has_collection_item:
        if collection_item_edge_id is None:
            raise ValueError(
                "collection_item_edge_id is required when the collection-item link exists."
            )
    elif collection_item_edge_id is not None or collection_item_evidence_refs:
        raise ValueError(
            "collection-item edge data requires an explicit collection-item link."
        )

    if has_candidate:
        if candidate_edge_id is None:
            raise ValueError(
                "candidate_edge_id is required when the candidate link exists."
            )
    elif candidate_edge_id is not None or candidate_evidence_refs:
        raise ValueError("candidate edge data requires an explicit candidate link.")

    edges: list[DomainRelationshipEdge] = []
    if has_collection_item:
        assert collection_item_edge_id is not None
        edges.append(
            adapt_captured_photo_collection_item_relationship(
                photo=photo,
                edge_id=collection_item_edge_id,
                evidence_refs=collection_item_evidence_refs,
            )
        )
    if has_candidate:
        assert candidate_edge_id is not None
        edges.append(
            adapt_captured_photo_candidate_relationship(
                photo=photo,
                edge_id=candidate_edge_id,
                evidence_refs=candidate_evidence_refs,
            )
        )

    return tuple(edges)
