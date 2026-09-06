"""Deterministic binding between retrieval evidence and multimodal references.

Issue #93 Slice C2 preserves the frozen Slice A retrieval contracts while
proving that one retrievable evidence item's generic provenance references map
exactly to validated typed multimodal references. This module is read-only and
performs no filesystem access, persistence, model calls, or mutation.
"""

from __future__ import annotations

from dataclasses import dataclass

from multimodal_evidence_references import MultimodalEvidenceReference
from retrieval_contracts import RetrievableEvidenceItem


@dataclass(frozen=True, slots=True)
class MultimodalRetrievalBinding:
    """Bind one immutable retrieval item to its typed multimodal references."""

    item: RetrievableEvidenceItem
    references: tuple[MultimodalEvidenceReference, ...] = ()

    @property
    def reference_ids(self) -> tuple[str, ...]:
        return tuple(reference.reference_id for reference in self.references)

    def validate(self) -> None:
        if not isinstance(self.item, RetrievableEvidenceItem):
            raise TypeError("item must be a RetrievableEvidenceItem.")
        self.item.validate()

        if not isinstance(self.references, tuple):
            raise TypeError("references must be a tuple.")

        reference_ids: list[str] = []
        for index, reference in enumerate(self.references):
            if not isinstance(reference, MultimodalEvidenceReference):
                raise TypeError(
                    f"references[{index}] must be a MultimodalEvidenceReference."
                )
            reference.validate()
            reference_ids.append(reference.reference_id)

        if reference_ids != sorted(reference_ids):
            raise ValueError("references must be in deterministic reference_id order.")
        if len(set(reference_ids)) != len(reference_ids):
            raise ValueError("references must not contain duplicate reference_id values.")

        expected = self.item.provenance.evidence_refs
        actual = tuple(reference_ids)
        if actual != expected:
            raise ValueError(
                "typed multimodal reference IDs must exactly match "
                "item.provenance.evidence_refs."
            )
