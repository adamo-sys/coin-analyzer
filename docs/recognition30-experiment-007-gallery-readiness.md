# Recognition30 Experiment 7 — Gallery Readiness Matrix

Status: **PREFLIGHT ONLY — NOT EXECUTION AUTHORITY**

This step converts the E7 Numista metadata audit into an explicit, fail-closed
30-case readiness matrix. It does not resolve additional identities, download
reference images, run Coin-CLIP, compute embeddings, or modify the production
recognition pipeline.

A case is execution-ready only when all three independent gates are true:

1. **Identity resolved** — the metadata audit selected a candidate through an
   `AUTO_*` resolution.
2. **Rights eligible** — every selected reference side has a picture URL plus
   explicit license name and license URL.
3. **Leakage audited clear** — every selected reference side explicitly records
   boolean `false` for same-image, derived-image, and same-physical-specimen
   leakage.

`NOT_AUDITED`, missing fields, ambiguous identities, or missing license
metadata fail closed. The generated report always records
`execution_authorized: false`; it is evidence for a later owner decision, not
permission to execute E7.

For the current v3 metadata audit, the expected identity-resolution headline is
23 resolved / 7 review-required. Rights and leakage are evaluated separately;
a resolved identity is not automatically an eligible gallery item.
