# RAG Retrieval Contracts — Slice A

## Status

FROZEN for Issue #93 Slice A.

This slice defines the collection-independent contracts that future local retrieval implementations must consume and produce. It does not implement indexing, search, embeddings, vector storage, graph storage, model calls, GUI behavior, or collection mutation.

## Authority boundary

Retrieval is advisory and read-only.

A retrieval result may provide context to a later human-controlled or validated workflow, but it cannot:

- create, edit, delete, confirm, or promote a collection record;
- create or alter a confirmed observation;
- mutate prompts, models, configuration, or training data;
- authorize learning or self-improvement promotion;
- merge, deploy, release, or otherwise promote repository state.

Confirmed observations and collection persistence remain separate authority boundaries.

## Contracts

### RetrievalProvenance

Carries stable source lineage for one retrievable evidence item.

Required:

- source type;
- source identifier.

Optional:

- source fingerprint;
- bounded evidence references.

Evidence references are deterministically ordered and unique.

### RetrievableEvidenceItem

Represents one immutable retrieval unit.

Required:

- stable item identifier;
- non-empty retrieval text;
- provenance.

Metadata is represented as a deterministic tuple of string key/value pairs. Keys must be unique and sorted.

### RetrievalQuery

Represents a bounded caller-supplied retrieval request.

Required:

- non-empty query text.

The caller may constrain source types and metadata. Result count is explicitly bounded.

Source-type constraints and metadata filters must be deterministic, sorted, and duplicate-free.

### RetrievalContext

Carries the immutable query plus the bounded set of candidate item identifiers made available to a retrieval implementation.

Candidate identifiers must be sorted and unique. An empty candidate set is valid.

### RankedRetrievalResult

Represents one item returned by retrieval.

Rank is a positive integer. Slice A intentionally does not define a probability or generic confidence field.

Optional retrieval rationale is descriptive only and carries no authority.

### RetrievalValidationOutcome

Represents an explicit downstream validation decision for one retrieved item.

Decisions are ACCEPT or REJECT.

A rejected result must contain at least one deterministic reason code.

## Determinism

Sequence-like contract fields representing sets are stored as tuples and must already be in deterministic sorted order with no duplicates.

The contracts do not silently normalize, reorder, deduplicate, enrich, search, persist, or mutate caller data.

## Slice A acceptance criteria

- contracts are frozen immutable dataclasses;
- validation is deterministic and local;
- no runtime dependency is added;
- no network access is introduced;
- no database or vector-store dependency is introduced;
- no GUI coupling is introduced;
- no generic probability confidence semantics are introduced;
- provenance is mandatory for retrievable evidence;
- invalid identifiers, text, ordering, duplicates, ranks, and validation decisions fail closed;
- retrieval remains advisory and has no collection mutation authority.

## Explicitly deferred

- Slice B local text/metadata retrieval implementation;
- indexing strategy;
- ranking algorithm;
- embeddings;
- vector database;
- multimodal image/OCR references beyond generic provenance references;
- corrective re-ranking implementation;
- graph relationships;
- specialist agents or orchestration.
