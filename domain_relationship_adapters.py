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
LINKED_COLLECTION_ITEM_RELATIONSHIP = "linked_collection_item"


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
