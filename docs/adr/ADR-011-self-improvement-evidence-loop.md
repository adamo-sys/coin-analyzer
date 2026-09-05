# ADR-011: Guarded Self-Improvement Evidence Loop

**Status:** Accepted

**Date:** 2026-09-05

## Context

Coin Analyzer already has two relevant trust boundaries:

1. `confirmed_observations.py` persists collector-confirmed outcomes separately from authoritative collection records for later offline evaluation.
2. The Sprint 10-20 capture-import path produces immutable human-confirmed field observations after strict review, while collection mutation remains explicit and separately authorized.

The project now needs an architectural rule that allows future recognition improvements to learn from confirmed outcomes without allowing evaluation data, model output, or an implementation agent to silently change collection facts or production behavior.

## Decision

Coin Analyzer will use a guarded evidence loop:

```text
prediction
  -> collector review
  -> confirmed/corrected outcome
  -> immutable evaluation evidence
  -> offline evaluation
  -> bounded experiment
  -> candidate change
  -> focused tests + regression + CI
  -> pull request
  -> repository-owner approval
  -> production
```

The loop is intentionally broken at the promotion boundary. Evidence may inform evaluation and candidate development, but it does not itself authorize mutation or deployment.

### Architectural invariant

> User-confirmed observations may influence evaluation and candidate development, but no learned result may silently modify authoritative collection data, recognition behavior, model configuration, prompts, or production code. Promotion requires explicit evaluation and repository-owner approval.

### Evidence rules

- Preserve both the original proposed value and the collector-confirmed value. A correction must never erase the prediction that produced it.
- Preserve provenance sufficient to identify the producing engine/provider, version when available, recognition method, source workflow, and bounded confidence metadata when that metadata has defensible semantics.
- Confidence values are evidence, not generic probability claims. Missing or semantically undefined confidence remains unavailable rather than being invented.
- Confirmed evidence is append-oriented and independent from the authoritative `CoinCollection` representation.
- Private absolute paths, collector notes, credentials, and private images must not be promoted into public fixtures or CI artifacts.
- Ground truth is human-confirmed or otherwise provenance-backed. Labels must never be manufactured to make an evaluation complete.

### Evaluation rules

Offline evaluators may:

- count accepted, corrected, deferred, and rejected outcomes;
- calculate exact-match and per-field agreement over records that contain confirmed values;
- summarize failure categories and producing engine/version/method metadata;
- report confidence coverage and bounded score summaries only when source confidence is numeric and in its documented range; and
- identify candidate failure clusters for later investigation.

Offline evaluators must not:

- mutate observations or collection records;
- retrain or replace a model;
- rewrite prompts or configuration;
- create authoritative collection facts;
- auto-approve a candidate change; or
- treat evaluation-set performance as sufficient evidence for deployment.

### Dataset discipline

Future benchmark work should distinguish:

- **development evidence** used to investigate and improve behavior;
- **validation evidence** used while selecting among candidates; and
- **frozen golden evaluation cases** used as an independent promotion gate.

A golden set must not automatically absorb every new user correction. Changes to a frozen evaluation manifest require explicit review so that candidate development cannot silently train against the final promotion set.

### Sprint 20 integration boundary

The mature Sprint 20 standalone-image path already enforces strict review and explicit save confirmation. A later bounded implementation slice may persist a sanitized evaluation projection from that path, but only after the strict human-confirmed boundary has been reached. That bridge must reuse the existing confirmed-observation contracts rather than create a second review or collection-persistence model.

This ADR does **not** authorize changing the existing Sprint 20 mutation sequence in the same slice as the initial evaluator foundation.

## Consequences

### Positive

- Real collector corrections become durable engineering evidence.
- Recognition changes can be compared against a stable baseline rather than subjective impressions.
- Future coding agents can propose improvements without receiving deployment authority.
- The project establishes data and provenance habits before a large private corpus accumulates.

### Costs

- Evidence schemas and evaluator outputs require backward-compatible maintenance.
- Some observations will remain unevaluable because confidence, provenance, or confirmed values are incomplete; this is preferable to manufacturing data.
- A separate future slice is required to bridge strict Sprint 20 reviewed outcomes into durable evaluation evidence.

## Initial implementation slice

ADR-011 authorizes only the following production-adjacent foundation:

1. a deterministic, read-only offline evaluator over `ConfirmedObservationRecord` values;
2. focused unit tests using synthetic records; and
3. documentation of the promotion and evidence invariants above.

Automatic retraining, model replacement, prompt mutation, background learning, collection mutation, and automatic PR merge are explicitly out of scope.
