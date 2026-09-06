"""Deterministic explicit relationship contracts for Issue #93 Slice E.

This module models caller-supplied domain nodes and edges without inferring,
searching, traversing, persisting, or promoting relationships. It is backend
neutral and intentionally does not introduce a graph database.
"""

from __future__ import annotations

from dataclasses import dataclass


CURRENT_DOMAIN_RELATIONSHIP_SCHEMA_VERSION = "1"

_MAX_TEXT_CHARS = 16_384
_MAX_NODE_TYPE_CHARS = 128
_MAX_RELATIONSHIP_TYPE_CHARS = 128
_MAX_EVIDENCE_REFS = 64
_MAX_EVIDENCE_REF_CHARS = 4_096


def _required_text(value: object, name: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value.strip():
        raise ValueError(f"{name} must not be empty.")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds maximum length {maximum}.")
    return value


def _validate_evidence_refs(values: object) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError("evidence_refs must be a tuple.")
    if len(values) > _MAX_EVIDENCE_REFS:
        raise ValueError("evidence_refs contains too many items.")
    for index, value in enumerate(values):
        _required_text(
            value,
            f"evidence_refs[{index}]",
            maximum=_MAX_EVIDENCE_REF_CHARS,
        )
    if values != tuple(sorted(values)):
        raise ValueError("evidence_refs must be in deterministic sorted order.")
    if len(set(values)) != len(values):
        raise ValueError("evidence_refs must not contain duplicates.")
    return values


@dataclass(frozen=True, slots=True)
class DomainNodeRef:
    """One explicit domain-node identity supplied by the caller."""

    node_type: str
    node_id: str

    @property
    def identity(self) -> tuple[str, str]:
        return (self.node_type, self.node_id)

    def validate(self) -> None:
        _required_text(self.node_type, "node_type", maximum=_MAX_NODE_TYPE_CHARS)
        _required_text(self.node_id, "node_id", maximum=_MAX_TEXT_CHARS)


@dataclass(frozen=True, slots=True)
class DomainRelationshipEdge:
    """One explicit directed relationship between two caller-supplied nodes."""

    schema_version: str
    edge_id: str
    source: DomainNodeRef
    relationship_type: str
    target: DomainNodeRef
    evidence_refs: tuple[str, ...] = ()

    @property
    def identity(self) -> tuple[str, tuple[str, str], str, tuple[str, str]]:
        return (
            self.edge_id,
            self.source.identity,
            self.relationship_type,
            self.target.identity,
        )

    def validate(self) -> None:
        if self.schema_version != CURRENT_DOMAIN_RELATIONSHIP_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported domain relationship schema version: "
                f"{self.schema_version!r}."
            )
        _required_text(self.edge_id, "edge_id", maximum=_MAX_TEXT_CHARS)
        if not isinstance(self.source, DomainNodeRef):
            raise TypeError("source must be a DomainNodeRef.")
        self.source.validate()
        _required_text(
            self.relationship_type,
            "relationship_type",
            maximum=_MAX_RELATIONSHIP_TYPE_CHARS,
        )
        if not isinstance(self.target, DomainNodeRef):
            raise TypeError("target must be a DomainNodeRef.")
        self.target.validate()
        _validate_evidence_refs(self.evidence_refs)

        if self.source == self.target:
            raise ValueError("source and target must identify distinct nodes.")
