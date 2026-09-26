# Recognition30 Experiment 7 — reference-gallery leakage audit

## Status

`DESIGN_ONLY_NOT_EXECUTION_AUTHORITY`

This document defines the evidence required to clear E7 reference images for
independence from Recognition30 query specimens. It does **not** authorize image
downloads, model downloads, embedding inference, or E7 execution.

The current readiness matrix has 30 cases: 23 identities are resolved, 13 are
rights-eligible, zero are leakage-cleared, and zero are execution-ready. The
first leakage-audit scope is therefore limited to those 13 identity-resolved,
rights-eligible cases. Cases blocked on identity or rights remain blocked.

## Threat model

E7 estimates visual-reference retrieval performance. A reference can leak
benchmark information even when its URL or encoded bytes differ from the query.
Three independent leakage questions must therefore be answered for every
reference side:

1. `same_image_as_query` — is the reference the same underlying photograph?
2. `derived_from_query` — was either image transformed, cropped, recompressed,
   resized, recolored, watermarked, or otherwise derived from the other?
3. `same_physical_specimen_as_query` — do the photographs depict the same
   physical coin?

Any `true`, `NOT_AUDITED`, unknown, or unsupported negative assertion keeps
the reference ineligible.

## Evidence hierarchy

### Same image

A cryptographic digest match is sufficient evidence for `true`, never for
`false`. Different SHA-256 digests only establish different byte streams.

A negative assertion may use stronger independent evidence such as distinct
source/provenance records plus visual comparison showing materially different
photographic capture. Perceptual hashes or image similarity may flag likely
duplicates/derivatives for review but must not independently clear a reference.

### Derived image

Exact-byte inequality is insufficient. Automated perceptual similarity,
feature matching, crop/resize checks, or metadata comparison may generate
`REVIEW_REQUIRED` evidence. They may not alone convert an unknown result to
`false`.

A `false` declaration requires provenance or review evidence sufficient to
support that neither image is a transformation of the other.

### Same physical specimen

This is the strongest independence requirement and cannot be inferred from
different bytes, URLs, backgrounds, rotations, lighting, crops, or file
metadata.

A `false` declaration requires affirmative specimen-level evidence. Examples
include:

- source provenance explicitly identifying a different specimen;
- independently documented collection/auction/specimen identifiers that differ;
- manual numismatic comparison identifying stable specimen-specific features
  that demonstrate different physical coins, with the evidence recorded.

Absence of an obvious matching scratch, toning mark, or defect is not by itself
sufficient. If specimen identity cannot be established, retain
`NOT_AUDITED`.

## Audit record

For every reference side preserve:

- Recognition30 case ID and query side;
- selected candidate identity and Numista type ID;
- reference role and source URL;
- source/copyright/license metadata;
- query SHA-256 and reference SHA-256 when bytes are legitimately available;
- automated duplicate/derivative signals, if used;
- provenance evidence;
- specimen-level evidence;
- reviewer/method;
- the three leakage declarations;
- reason/evidence for every declaration;
- audit timestamp and audit schema/version.

No private image bytes belong in Git.

## Automation boundary

Automation may:

- validate manifest completeness;
- compute hashes for already-authorized local bytes;
- flag exact matches;
- flag high-similarity or likely-derived pairs for review;
- validate that required evidence fields exist.

Automation must not:

- treat hash inequality as independence;
- treat perceptual-hash distance as proof of a different specimen;
- manufacture `false` declarations from missing evidence;
- infer specimen independence solely from URL/domain/uploader differences;
- overwrite a human/provenance uncertainty with a heuristic.

## Fail-closed state machine

Allowed states for each leakage field are:

- `true` — leakage established;
- `false` — independence supported by recorded evidence;
- `REVIEW_REQUIRED` — suspicious or conflicting evidence;
- `NOT_AUDITED` — no adequate audit yet.

Only three explicit `false` values clear a reference side.

If any reference side for a candidate remains uncleared, that candidate remains
leakage-ineligible for E7.

## First bounded pass

The first pass is restricted to the 13 cases already both identity-resolved and
rights-eligible in the readiness matrix:

`001, 002, 003, 004, 006, 008, 010, 015, 017, 021, 025, 026, 029`.

Before any reference bytes are fetched, create a zero-download leakage manifest
for these cases containing the query/reference identifiers, provenance fields,
rights evidence, and `NOT_AUDITED` leakage declarations.

That manifest is the review surface. A later, separately authorized step may
obtain only the minimum reference bytes needed for the audit.

## Stop conditions

Stop and report rather than weaken the gate if:

- provenance cannot support specimen-level independence;
- rights do not permit the required processing;
- a reference is the same image, derived from a query image, or the same known
  specimen;
- evidence is contradictory;
- completing the gallery would require outcome-driven reference selection.

A partial independent gallery is useful preflight evidence but does not satisfy
the frozen E7 requirement for all 30 candidate identities.

## Execution boundary

Completing this design or its zero-download manifest does not authorize E7.
The original E7 preflight still requires a frozen model artifact, full
independent gallery, preprocessing/ranking configuration, hashes, offline
fixtures, resource budgets, and a final zero-inference validation before any
bounded retrieval execution.
