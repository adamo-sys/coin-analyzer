# RAG Domain Relationship Identity Semantics — Issue #93 Slice E

## Status

PROPOSED ARCHITECTURE DECISION GATE.

This document does not authorize a production adapter, schema migration, persistence layer, graph database, traversal engine, indexing, embeddings, model calls, GUI integration, collection mutation, confirmed-observation mutation, evidence promotion, or agent orchestration.

Its purpose is to stop relationship adapters from manufacturing node identities or relationship semantics before the repository has an explicit authority-preserving rule.

## Current repository evidence

Issue #93 Slice E calls for useful domain relationships such as:

`coin ↔ denomination ↔ year ↔ variety ↔ diagnostic ↔ observation ↔ market comparable`

and explicitly requires starting with IDs/edges while deferring a dedicated graph database until scale or query needs justify one.

The landed Slice E contract (`domain_relationships.py`) provides backend-neutral `DomainNodeRef` and `DomainRelationshipEdge` values. Node IDs and relationship labels are caller-supplied and preserved exactly; the contract intentionally does not infer or normalize a domain taxonomy.

The landed selector (`domain_relationship_query.py`) performs deterministic bounded one-hop selection over already-explicit edges. It does not discover, infer, enrich, or manufacture relationships.

The current confirmed-observation contract (`capture_import/workflow_confirmed_observation_models.py`) exposes an explicit `source_coin_id` and a composite field-observation identity of `(source_coin_id, field_name)`. It does not expose a standalone observation ID on `ConfirmedFieldObservation`.

The existing diagnostic model (`diagnostic_agent.py`) carries `observation_ids` on each `DiagnosticFinding`, but `DiagnosticFinding` itself does not expose a stable diagnostic ID.

Therefore, a production adapter that emitted `coin -> observation` or `diagnostic -> observation` edges today would need to invent at least one opaque node identifier or serialization rule unless the caller supplied an already-authoritative ID from another contract.

## Architecture problem

Issue #93 authorizes explicit relationships; it does not authorize manufacturing identities to make those relationships fit the generic edge schema.

The repository currently has three distinct identity shapes relevant to Slice E:

1. explicit scalar IDs such as `source_coin_id`;
2. explicit composite identities such as `(source_coin_id, field_name)`;
3. records that reference observation IDs but do not themselves expose a stable node ID, such as `DiagnosticFinding`.

Silently converting a composite identity into an opaque string, inventing a diagnostic ID, or assigning a relationship label with stronger semantics than the source contract would create provenance/authority ambiguity.

Under `AGENTS.md`, production behavior must stop at that boundary rather than manufacture labels or identity semantics.

## Required invariants for future Slice E adapters

Any future adapter from an existing domain record into `DomainRelationshipEdge` must preserve all of the following:

1. Relationships remain local-first, read-only, and advisory.
2. Confirmed observations remain the authority boundary for accepted/learned evidence.
3. No adapter may create, confirm, promote, or mutate collection or observation state.
4. Node identities must come from an existing authoritative identity or from an explicitly approved deterministic identity rule.
5. Relationship labels must reflect an explicit source relationship; adapters must not infer causation, equivalence, ownership, canonicality, or confidence.
6. Source identifiers and evidence/provenance references must remain traceable.
7. Unknown, ambiguous, missing, or unsupported identities fail closed.
8. Adapters must not silently normalize, hash, concatenate, serialize, reorder, or otherwise transform domain identities unless that transformation is explicitly frozen as part of the relationship architecture.
9. Tests use sanitized synthetic fixtures only; private collection exports, notes, photographs, and live user data are out of scope.
10. No persistence, graph storage, recursive traversal, embeddings, network/model calls, GUI coupling, mutation, promotion, or agent orchestration belongs in the identity-adapter slice.

## Decision options

### Option A — Add stable scalar IDs to source domain contracts

Introduce first-class IDs (for example, an observation ID or diagnostic finding ID) into the authoritative source contracts before relationship adapters consume them.

Advantages:

- simple scalar `DomainNodeRef.node_id` mapping;
- strongest long-term traceability;
- avoids opaque adapter-owned identity encodings.

Costs:

- changes established source schemas and serialization contracts;
- may require migrations and broad compatibility work;
- too large for the next bounded Issue #93 slice without a separately approved schema plan.

### Option B — Freeze explicit deterministic encodings for existing composite identities

Define a canonical reversible encoding for an existing authoritative composite identity such as `(source_coin_id, field_name)`, then permit a pure adapter to use that encoding as a relationship node ID.

Advantages:

- no source-schema migration;
- preserves the existing domain identity components;
- can remain deterministic and backend-neutral.

Costs:

- introduces a new serialization contract that must be versioned and frozen;
- requires careful escaping/length rules;
- still does not solve records that have no stable identity at all, such as `DiagnosticFinding`.

### Option C — Require caller-supplied authoritative node IDs and adapt only records that already carry them

Keep `DomainNodeRef` unchanged. A relationship adapter may operate only when the caller supplies node IDs whose authority is established outside the adapter. The adapter validates source linkage but does not invent IDs.

Advantages:

- smallest scope;
- no source-schema or generic relationship-contract change;
- strongest fail-closed behavior;
- preserves the current caller-supplied identity design of `domain_relationships.py`.

Costs:

- adapters remain intentionally partial;
- some source models cannot participate until they gain an authoritative ID or an approved identity encoding.

## Recommended decision

Prefer **Option C** for the next bounded Slice E implementation.

Under this rule, the first production relationship adapter should be limited to a source relationship where both endpoint IDs are already authoritative and explicit. If no such source relationship is available, Slice E should stop rather than invent identifiers.

A future adapter may accept an explicit caller-supplied node ID only when the caller can trace that ID to an authoritative source contract. The adapter itself must not mint, hash, concatenate, serialize, or otherwise manufacture a missing domain identity.

Composite confirmed-field identities and diagnostic findings should remain deferred until a separate architecture decision approves either a stable scalar ID or a reversible deterministic encoding.

## Explicitly deferred

- modifying the frozen Slice A retrieval contracts;
- changing `DomainNodeRef` or `DomainRelationshipEdge`;
- adding IDs to confirmed-observation or diagnostic schemas;
- defining a composite-ID serialization format;
- `coin -> observation` adapters that invent observation IDs;
- `diagnostic -> observation` adapters that invent diagnostic IDs;
- denomination/year/variety relationship inference from free-form labels;
- graph database or graph indexing;
- recursive traversal/path finding;
- embeddings/vector infrastructure;
- persistence;
- specialist agents or orchestration;
- GUI integration;
- collection or confirmed-observation mutation.
