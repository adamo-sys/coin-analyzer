# RAG Multimodal Image-Role Semantics — Issue #93 Slice C

## Status

PROPOSED ARCHITECTURE DECISION GATE.

This document does not authorize a production adapter, enum expansion, evidence promotion, collection mutation, persistence, indexing, model calls, embeddings, graph infrastructure, or agent orchestration.

Its purpose is to stop an unsafe semantic inference before the next Slice C implementation step.

## Current repository evidence

Issue #93 Slice C requires multimodal evidence references for obverse/reverse/detail images, OCR text, capture-package fingerprints, and structured metadata.

The landed Slice C reference contract currently exposes these image kinds:

- `IMAGE_OBVERSE`
- `IMAGE_REVERSE`
- `IMAGE_DETAIL`

The existing OCR domain contract independently defines image roles as:

- `front`
- `reverse`
- `edge`

The OCR contract validates those values as domain semantics; they are not generic path labels.

Coin Analyzer also supports banknotes, for which `front` is not necessarily equivalent to the numismatic coin term `obverse`.

## Architecture problem

A production adapter cannot safely infer either of the following without an explicit architecture decision:

- `front -> IMAGE_OBVERSE`
- `edge -> IMAGE_DETAIL`

Those transformations would change source semantics rather than merely preserve provenance.

`reverse -> IMAGE_REVERSE` appears lexically aligned, but a generalized adapter still needs an explicit rule stating whether source roles may be translated or must be preserved verbatim alongside the typed reference kind.

Under `AGENTS.md`, this is an architecture/provenance stop condition. Production behavior must not manufacture labels to satisfy a schema.

## Required invariants for any future adapter

Any approved adapter must preserve all of the following:

1. Retrieval remains local-first, read-only, and advisory.
2. Confirmed observations remain the authority boundary for accepted/learned evidence.
3. No adapter may create, confirm, promote, or mutate collection state.
4. Original source identifiers, role labels, artifact identifiers, and fingerprints must remain traceable.
5. A typed multimodal kind must not silently replace or erase the original source role.
6. Role translation must be deterministic and explicitly specified; unknown or unsupported mappings fail closed.
7. Tests must use sanitized synthetic fixtures only; private/local photos and collection exports are out of scope.
8. No filesystem existence checks, image decoding, OCR execution, network/model calls, persistence, indexing, embeddings, vector/graph storage, GUI coupling, or agent orchestration belong in the role-mapping slice.

## Decision options

### Option A — Extend the typed image-kind vocabulary

Add explicit typed kinds such as `IMAGE_FRONT` and `IMAGE_EDGE` while retaining `IMAGE_OBVERSE`, `IMAGE_REVERSE`, and `IMAGE_DETAIL`.

Advantages:

- preserves current OCR source semantics without coercion;
- works for banknotes and coins;
- avoids treating `edge` as a generic detail image.

Cost:

- expands the current Slice C contract beyond the image-kind list already implemented from Issue #93;
- requires a schema/contract change and focused compatibility tests.

### Option B — Keep the existing typed kinds and defer unsupported mappings

Permit adapters only where a source role is explicitly equivalent to an existing typed kind. Leave `front` and `edge` unmapped until another authoritative source supplies explicit semantic classification.

Advantages:

- no enum/schema expansion;
- strict fail-closed behavior;
- smallest production change.

Cost:

- partial multimodal coverage;
- many existing OCR image records may not receive typed image references yet.

### Option C — Redefine existing kinds as broader aliases

Treat `IMAGE_OBVERSE` as including `front` and/or `IMAGE_DETAIL` as including `edge`.

This option is NOT RECOMMENDED because it weakens semantic precision and risks manufacturing provenance labels across coins and banknotes.

## Recommended decision

Prefer **Option B** for the next bounded implementation slice unless the repository owner explicitly approves a vocabulary expansion under Option A.

That keeps the current contract stable and allows a future adapter to fail closed for unsupported image-role mappings rather than inventing semantics.

If Option B is approved, the next implementation slice should be limited to a pure deterministic adapter contract that:

- accepts an already-validated source record;
- preserves the original source role verbatim in traceable metadata/provenance;
- maps only explicitly authorized role/kind pairs;
- rejects unsupported roles without fallback coercion;
- performs no I/O or mutation.

## Explicitly deferred

- changing `retrieval_contracts.py` or the frozen Slice A architecture;
- enum expansion unless separately approved;
- automatic front/obverse inference;
- automatic edge/detail inference;
- image embedding or vector indexing;
- graph relationships;
- corrective re-ranking;
- specialist agents or orchestration;
- GUI integration;
- collection or confirmed-observation mutation.
