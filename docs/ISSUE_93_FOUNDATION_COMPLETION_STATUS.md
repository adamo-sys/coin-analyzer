# Issue #93 — RAG + Agent Readiness Foundation Completion Status

## Purpose

Record the bounded completion boundary for Issue #93 without expanding the product into vector storage, graph infrastructure, autonomous agents, or new collection authority.

This document reconciles the repository's landed retrieval/evidence work against the roadmap in Issue #93. It does not authorize new production behavior.

## Current completion boundary

### Slice A — Retrieval contracts

**Complete.**

The frozen retrieval contracts provide immutable, collection-independent contracts for retrieval requests, evidence items, provenance, ranked results, and validation outcomes. They do not search, persist, call models, mutate collection state, or authorize promotion.

### Slice B — Local text/metadata retrieval pilot

**Complete for the bounded foundation.**

`local_retrieval.py` provides deterministic, local, read-only retrieval over caller-supplied `RetrievableEvidenceItem` values. It uses exact source-type/metadata/candidate filtering, deterministic token matching/ranking, stable result ordering, and fail-closed input validation.

PR #136 is merged. No persistence, embeddings, vector database, model call, GUI coupling, collection mutation, or evidence promotion was introduced.

### Slice C — Multimodal evidence references

**Complete for reference-level readiness.**

The repository has typed multimodal reference contracts plus bounded adapters/bindings for OCR text, capture-package evidence, structured metadata, and the explicitly approved OCR reverse-image role semantics.

The multimodal retrieval binding requires generic retrieval `evidence_refs` to correspond exactly to validated typed reference IDs rather than manufacturing a second identity.

Image embeddings and vector storage remain intentionally deferred.

### Slice D — Corrective validation

**Complete for the bounded foundation.**

The repository has a deterministic, read-only corrective validation/re-ranking gate that can reject weak or irrelevant retrieval context without changing collection or evidence authority.

PR #165 additionally proves the existing Slice B/C/D contracts compose across one sanitized synthetic integration seam while preserving evidence lineage verbatim. No new production API was needed for that proof.

### Slice E — Hybrid / graph relationships

**Foundation complete at the explicitly bounded level.**

The repository now has backend-neutral explicit domain node/edge contracts, deterministic bounded one-hop relationship selection, an identity-semantics decision gate, and production adapters for already-authoritative captured-photo relationships.

The accepted boundary is intentionally partial: relationship adapters may consume only identities and relationships whose authority already exists outside the adapter. They may not mint, hash, concatenate, serialize, infer, or normalize missing identity/relationship semantics.

A graph database, recursive traversal, graph indexing, inferred domain taxonomy, and composite-identity serialization remain deferred until justified by a separately approved architecture decision.

### Slice F — Specialist-agent orchestration

**Explicitly deferred.**

Issue #93 established readiness sequencing, not authorization to add specialist agents immediately. No agent swarm, orchestrator, autonomous collection editing, self-modifying behavior, or learning promotion should be added under this foundation issue.

Future specialist-agent work should begin only through a separately scoped issue after a concrete product use case justifies it and should continue to use explicit read-only/advisory contracts, verification, and human-controlled mutation/promotion.

## Confirmed-observation retrieval adapter decision

A direct production adapter from `ConfirmedFieldObservation` to `RetrievableEvidenceItem` is **not authorized by the current frozen architecture**.

`ConfirmedFieldObservation` exposes the composite identity `(source_coin_id, field_name)`, while `RetrievableEvidenceItem.item_id` is a scalar string. Existing identity rules explicitly prohibit an adapter from inventing, hashing, concatenating, serializing, or otherwise manufacturing a scalar identity for a composite source identity unless a separate architecture decision freezes that encoding.

An aggregate `ConfirmedObservationSet` is closer to a safe source because it carries scalar `source_coin_id` and optional `source_fingerprint`, but the repository still does not freeze all semantics required for a production retrieval adapter. In particular:

- no architecture rule establishes the aggregate retrieval `item_id` semantics;
- no frozen rule establishes how `submitted_value` versus optional `canonical_value` should be represented in deterministic retrieval text;
- arbitrary `ConfirmedObservationProvenance.evidence` strings are not automatically typed multimodal reference IDs and therefore must not be promoted into `RetrievalProvenance.evidence_refs`;
- a narrow retrieval `source_type` for the aggregate has not been frozen as a source-domain contract.

Therefore the adapter is **deferred rather than improvised**. A future bounded issue may approve these semantics explicitly if a concrete retrieval use case requires it.

## Preserved invariants

- Core behavior remains local-first.
- Retrieval, multimodal references, validation, and relationship selection remain read-only/advisory.
- Confirmed observations remain an authority boundary for accepted/learned evidence.
- Collection mutation and learning promotion remain human-controlled product actions.
- Provenance and source identities are preserved rather than manufactured.
- Retrieval interfaces remain deterministic and backend-replaceable.
- No vector database, graph database, embedding service, network dependency, agent framework, or autonomous mutation is required by the foundation.
- Private collection data, collector notes, credentials, and uncertain-provenance images remain outside this work.

## Closure recommendation

Issue #93 can be considered **foundation-complete** once this status reconciliation has passed normal repository review and authoritative CI.

Closing Issue #93 at that point should mean only that the readiness foundation described above is established. It must not be interpreted as completion of future vector search, graph infrastructure, specialist-agent orchestration, or confirmed-observation retrieval adapters whose semantics remain deliberately deferred.

Any future Slice F/product-agent implementation should use a new bounded issue with explicit objective, architecture support, invariants, acceptance criteria, validation, and human merge authority.