# Issue #93 Slice E — Photo to Collection Item Relationship Adapter

## Scope

This slice adds one pure, read-only adapter for the explicit `CapturedPhoto.photo_id -> CapturedPhoto.linked_collection_item_id` relationship.

The adapter consumes only identities already present on the source record. It does not mint, hash, concatenate, serialize, normalize, or otherwise manufacture endpoint identities. `edge_id` and optional `evidence_refs` are caller supplied and remain subject to the existing `DomainRelationshipEdge` validation contract.

## Preserved authority boundaries

- local-first and provider-neutral;
- read-only/advisory relationship construction only;
- no collection or confirmed-observation mutation;
- no promotion or learning authority;
- no graph persistence, traversal, indexing, embeddings, model/network calls, GUI coupling, schema migration, or agent orchestration;
- frozen Slice A retrieval contracts remain unchanged;
- malformed, missing, ambiguous, or unsupported identities fail closed.

## Validation

Focused tests cover exact endpoint types/IDs, exact relationship label, exact caller-supplied edge ID, evidence-reference preservation, fail-closed behavior for invalid identities, non-mutation of `CapturedPhoto`, and absence of generated identity behavior.

Authoritative repository validation remains GitHub Actions. This document does not claim local execution by ChatGPT or replace CI/human merge authority.
