# RAG Multimodal Image-Role Semantics — Issue #93 Slice C

## Status

APPROVED ARCHITECTURE DECISION — **Option B**.

Repository-owner approval recorded September 6, 2026.

Production code may map only image-role semantics that are explicitly equivalent to an existing typed multimodal kind. Unsupported roles must fail closed. This approval does **not** authorize enum expansion, evidence promotion, collection mutation, persistence, indexing, model calls, embeddings, graph infrastructure, or agent orchestration.

The current production adapter `ocr_multimodal_role_adapter.py` is aligned with this decision: `reverse` may map to `IMAGE_REVERSE`; `front` and `edge` remain unsupported and must not be coerced to `IMAGE_OBVERSE` or `IMAGE_DETAIL`.

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

A production adapter cannot safely infer either of the following:

- `front -> IMAGE_OBVERSE`
- `edge -> IMAGE_DETAIL`

Those transformations would change source semantics rather than merely preserve provenance.

Under approved Option B, `reverse -> IMAGE_REVERSE` is the only authorized OCR image-role mapping because the source role and typed kind are explicitly equivalent. The original source role must remain preserved verbatim alongside the typed reference.

Under `AGENTS.md`, manufacturing or broadening role semantics remains an architecture/provenance stop condition.

## Required invariants

Any adapter under this decision must preserve all of the following:

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

This option remains **deferred**. It would preserve source semantics directly but requires a separate owner-approved schema/contract expansion and focused compatibility tests.

### Option B — Keep the existing typed kinds and defer unsupported mappings

**APPROVED.**

Permit adapters only where a source role is explicitly equivalent to an existing typed kind. Under the current OCR role vocabulary:

- `reverse -> IMAGE_REVERSE` is authorized;
- `front` remains unmapped;
- `edge` remains unmapped;
- unknown or future roles remain unmapped unless separately approved.

This preserves the current enum/schema, provides strict fail-closed behavior, and avoids manufacturing coin-specific or detail semantics across broader collection domains.

### Option C — Redefine existing kinds as broader aliases

Treat `IMAGE_OBVERSE` as including `front` and/or `IMAGE_DETAIL` as including `edge`.

This option is **REJECTED** because it weakens semantic precision and risks manufacturing provenance labels across coins and banknotes.

## Authorized production boundary

Option B authorizes only pure deterministic adapters that:

- accept an already-validated source record;
- preserve the original source role verbatim in traceable metadata/provenance;
- map only explicitly authorized role/kind pairs;
- reject unsupported roles without fallback coercion;
- preserve caller-supplied lineage identifiers and locators without normalization;
- perform no I/O or mutation.

The landed `ocr_multimodal_role_adapter.py` satisfies this boundary and does not require a production-code change merely to record this architecture approval.

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
