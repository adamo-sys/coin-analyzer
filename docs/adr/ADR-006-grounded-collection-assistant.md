# ADR-006: Grounded, read-only collection assistant

- Status: Accepted
- Date: 2026-07-16

## Context

Coin Analyzer already has deterministic inventory, collection-intelligence, and
portfolio engines. A natural-language surface can make those capabilities easier
to use, but an unrestricted chatbot could invent collection facts, expose local
data, duplicate business logic, or mutate authoritative records.

## Decision

- Deterministic collection tools remain the source of truth. The language model
  plans allowlisted tool calls and explains their bounded results; it does not
  calculate portfolio values or replace collection-intelligence rules.
- The assistant is permanently read-only for this MVP. It cannot mutate models,
  files, settings, imports, exports, or other stores.
- Each question is planned independently. The GUI may display session messages,
  but conversation history is neither sent as hidden planning context nor saved.
- Tools and arguments use explicit schemas. Unknown tools, arguments, excessive
  limits, and malformed plans are rejected. A malformed plan receives at most one
  repair attempt.
- Provider payloads contain only the standalone question, planning instructions,
  tool schemas, and bounded sanitized tool results. Images, paths, notes,
  credentials, raw objects, and complete collection records are excluded.
- Collection-derived strings are untrusted evidence values, never instructions.
  Results have field and row limits, deterministic ordering, and truncation
  indicators.
- A vendor-neutral adapter separates orchestration from providers. OpenAI
  Responses is the first optional adapter; normal tests use fakes and never make
  network calls.
- Provider and model identifiers are configurable diagnostics. Credentials come
  from environment configuration and are never persisted or displayed.
- No embeddings, vector database, model training, or persistent chat store is
  introduced for the MVP.

## Consequences

The feature adds a visible generative-AI surface without creating a parallel
analytics system or cloud requirement for core collection management. Answers
can fail safely when configuration, planning, evidence, or provider calls are
unavailable. The MVP supports fewer question types than a general chatbot, and
interactive cloud behavior still requires explicit user setup and manual
acceptance testing.

## Reconsider When

Reconsider these boundaries only through a separate approved design if users need
additional deterministic tools, local model providers, persistent conversation,
or carefully reviewed actions. Mutation authority, image transmission,
embeddings, and financial inference require new decisions rather than incremental
expansion of this ADR.
