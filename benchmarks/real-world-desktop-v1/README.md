# Real-World Desktop Acceptance Set v1

This directory defines the authoring contract for a future paired-image,
real-world desktop acceptance set. It intentionally contains no manifest and no
images yet. Dataset assembly and recognition execution are separate, explicitly
authorized units of work.

`manifest.schema.json` documents strict contract version `1.0.0`. Runtime
loading additionally checks cross-case composition, safe relative paths, exact
image-byte SHA-256 values, deterministic ordering, reviewer decisions,
eligibility, leakage controls, stability coverage, and all freeze digests.

Every case reserves nullable `mint`, `mint_mark`, `variety`, and
`catalog_reference` fields. They remain `null` in this foundation unless a later
approved contract explicitly changes that rule.

Private or uncertain-local inputs remain local. This foundation validates local
metadata and frozen bytes only; it does not run recognition or authorize
provider execution.

## Frozen v1 protocol

This authoring scaffold is unpublished. No real manifest or corpus exists in
the repository, so the strict v1 schema may replace the scaffold without a data
migration. Do not create a placeholder real manifest or fabricate provenance.

The eventual frozen corpus has exactly 30 paired-image cases: 24 `identify`, 6
`abstain`, at least 24 physical specimens, and no more than two independently
captured cases per specimen. Repeated specimens must declare reciprocal links
and materially different capture conditions. Every case, including abstentions,
has provenance-backed country, denomination, and year reviewed independently by
two reviewers before recognition; ground-truth and expected-action evidence are
separate, with explicit adjudication when reviewers disagree.

Exactly 10 distinct-specimen cases form the stability subset, covering both
expected actions and every declared relevant cohort. A future authorized run
makes five provider calls per stability case. The primary metrics are specimen-
weighted and report exact numerators and denominators. Complete identity credit
requires canonical country, denomination, and year; exact-string comparison is
diagnostic and partial identity receives no complete-identity credit.

Freeze metadata binds the manifest, schema, ground truth, expected actions,
transformation ledger, and exact image bytes by digest. Image or label changes
after freeze require a new corpus version. Every image declares a permitted
representation-only transformation or explicit `none`; enhancement, sharpening,
denoising, synthetic relighting, compositing, and semantic/benchmark-specific
cropping are prohibited.

Preflight rejects unsafe or semantic paths, stale/missing hashes, duplicate
bytes or pairs, same-side reuse, specimen-limit or reciprocal-link violations,
and missing external near-duplicate review. Privacy, license, and provider-use
authorization are separate declarations, and eligibility fails closed.

Execution is limited to paired-image multimodal visual-provider evaluation.
OCR, fusion, ranking, GUI, persistence, durability, and production thresholds
remain separate. Provider scores are uncalibrated, system confidence is
unavailable, output is advisory, evidence precedes inference, variety is outside
v1 correctness, and collection decisions still require human confirmation.
