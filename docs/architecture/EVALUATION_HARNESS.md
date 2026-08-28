# Evaluation Harness Architecture Amendment

Status: APPROVED — Benchmark v1 measurement contract

## Scope

The evaluation harness measures the existing, opt-in production image/OCR
workflow without changing its stages, providers, thresholds, review rules, or
persistence behavior. It is a headless application-layer caller, not a
production pipeline variant.

## Dataset contract

Each immutable benchmark version is rooted at `benchmarks/<version>/` and owns
a JSON manifest plus relative image paths. A case records a stable ID, front
and reverse paths, expected identity, optional already-supported identity
fields, provenance URL, author, license, difficulty tags, notes, and whether
the reference identity is certain. Absolute paths and parent traversal are
invalid. Derived images retain their parent provenance/license and declare the
transformation.

Benchmark versions are baselines, not training sets. Existing versions are not
silently rewritten, hard cases are not removed after observing results, and no
OCR tuning occurs in the same unit that establishes a baseline.

## Execution contract

For each case the harness:

1. validates the manifest and image containment;
2. adapts the selected files through `create_temporary_capture_package`;
3. builds the real `create_desktop_ocr_review_composition` composition;
4. executes `ImportWorkflow` over the production OCR pipeline;
5. decodes the result through `create_desktop_ocr_review_handoff`;
6. records raw observations/candidates/conflicts without applying GUI review;
7. optionally exercises the existing confirmed-draft persistence boundary in
   an isolated collection, then reloads it to verify durability.

The latency boundary starts immediately before temporary-package creation and
ends after OCR handoff decoding (or after optional persistence/reload). Dataset
loading, manifest validation, report serialization, and summary rendering are
outside that boundary.

## Outcome separation

- `raw_prediction` is derived only from production OCR candidates. It is never
  replaced by the expected value.
- `unresolved` means the required identity cannot be selected uniquely from
  raw candidates or the provider abstained/unavailable.
- `correction_required` compares the raw prediction with a certain reference.
- `reference_corrected_result` is the manifest's human-established reference,
  reported separately and never scored as raw model success.
- `infrastructure_failure` means the case could not be evaluated because the
  manifest, files, runtime, pipeline, or persistence infrastructure failed. It
  is excluded from accuracy denominators and reported separately.

## Scoring and reporting

Country, denomination, and year use Unicode-normalized, trimmed,
case-insensitive exact matching. Full identity requires all three fields.
Uncertain references are executed and reported but excluded from exact-accuracy
denominators. Latency reports mean, median, and nearest-rank p95 over evaluated
cases. Difficulty breakdowns use the same rules.

Every machine-readable report records dataset version, git commit, UTC
timestamp, Python/platform details, OCR provider/runtime configuration, timing
boundary, per-case results, aggregate metrics, and infrastructure failures.
The human summary is a deterministic rendering of that report except for the
explicit runtime metadata values already captured in it.

Visual-provider reports also separate usefulness from safety. Field coverage
measures how often each expected field was supplied. Selective accuracy
measures correctness only among supplied fields, so abstention or partial
answers cannot be mistaken for correct identification. Full-required-identity
coverage and selective accuracy are reported independently.

Provider source scores remain explicitly uncalibrated. Reports count missing
and invalid scores separately, count incomplete and incorrect full identities
above the fixed high-score threshold, combine them as a conservative
unsafe-result rate, and show score-bin accuracy plus a weighted absolute-gap
diagnostic. Scored findings require stable case IDs, and report case lists are
deterministically ordered. Exact-match and canonical-match safety summaries
remain separate. These are warning and comparison metrics only: they do not
turn a heuristic score into a probability, authorize an acceptance threshold,
or bypass collector review.

Benchmark mismatches are data, not harness failures. The command exits nonzero
only for manifest/output/infrastructure conditions that prevent a valid run.

## Explicit exclusions

- OCR/provider optimization or threshold changes
- benchmark-specific production behavior
- automatic acceptance of expected values as predictions
- GUI automation
- statistical-significance claims for Benchmark v1
- process-crash recovery changes

### Multimodal diagnostic replay amendment

Every successfully evaluated multimodal row retains its complete, ordered
`diagnostic_candidates` collection even when the provider's public outcome is
`ABSTAINED`. Each entry has a stable row-local `candidate_id`, and the row
records `best_candidate_id` independently of the public prediction. Public
`predictions` continue to follow the provider outcome and therefore remain
empty for an abstention.

Threshold-frontier replay resolves the candidate named by
`best_candidate_id`; it must not infer a candidate from public predictions or
list position. A missing, duplicate, stale, or otherwise invalid candidate
reference, or an invalid source score, makes that row explicitly unscorable
for replay. Diagnostic retention and replay are evaluation-only: they do not
change provider output, candidate ordering, recognition thresholds, review
rules, persistence semantics, or production recognition behavior.

#### Real-World Desktop Acceptance Set v1 foundation

The Real-World Desktop Acceptance Set is an offline paired-image evaluation
inventory. Each case names one physical specimen, exactly one obverse image and
one reverse image, an explicit expected action (`identify` or `abstain`), frozen
image-byte SHA-256 values, capture-condition metadata, a privacy classification,
and reserved attribution fields.

The v1 foundation reserves `mint`, `mint_mark`, `variety`, and
`catalog_reference` as explicit nullable fields. This contract does not infer,
repair, or populate those fields. An `identify` case requires complete
country/denomination/year ground truth. An `abstain` case may retain known
identity fields, but this foundation does not manufacture missing labels.

Manifest loading is local-only and fail-closed for malformed identifiers,
unsafe relative paths, stale hashes, missing image bytes, unsupported privacy
classes, duplicate case identifiers, malformed image roles, and non-null
reserved attribution. The deterministic audit reports inventory counts,
expected-action and privacy balance, capture-condition distributions, and exact
duplicate image hashes.

This foundation does not execute recognition providers, OCR, fusion, scoring,
GUI review, persistence, durability workflows, or threshold selection. It does
not add a real manifest or real benchmark images. Corpus assembly and execution
are separately authorized work.

### Real-World Desktop Acceptance Set v1 frozen protocol

The v1 authoring scaffold is unpublished: the repository contains neither a
real acceptance manifest nor acceptance images. The strict contract may
therefore replace the scaffold without a migration path. Compatibility is
desirable for synthetic authoring tools, but no nonexistent corpus format is a
published compatibility obligation.

#### Corpus composition and independence

The frozen corpus contains exactly 30 paired-image cases: 24 with expected
action `identify` and 6 with expected action `abstain`. It represents at least
24 distinct physical specimens. A specimen may appear in at most two cases,
and a repeated specimen must use independently captured image pairs under
materially different declared capture conditions. Repeated cases identify one
another reciprocally.

Every case records complete provenance-backed country, denomination, and year
ground truth, including abstain cases. Known identity and expected action are
different judgments: abstention never erases known identity. Before any
recognition call, two named independent reviewers review ground truth and
expected action independently. Disagreement requires a named adjudicator,
rationale, and final decision; agreement records that adjudication was not
required. Ground-truth evidence and action evidence are separately recorded so
that difficult imagery cannot be used to weaken identity truth.

The corpus declares cohorts needed for deterministic breakdowns, including
expected action and capture-condition cohorts. Exactly 10 cases, each from a
different specimen, form the stability subset. That subset covers both
expected actions and every cohort designated as relevant to stability. Each
stability case receives five independent provider calls during a separately
authorized execution.

#### Freeze, transformation, and leakage controls

The freeze records exact image bytes and lowercase SHA-256 digests, a canonical
manifest digest, the schema digest, and separate digests for ground truth,
expected action, and the transformation ledger. Paths are sanitized,
non-semantic relative identifiers. Post-freeze image-byte or label changes
create a new corpus version; an existing version is never silently rewritten.

Every image has an explicit transformation ledger, including an explicit
`none` record when it is an original capture. Permitted transformations are
representation-only operations declared by the frozen schema. Benchmark-
specific enhancement, sharpening, denoising, synthetic relighting, compositing,
and semantic or benchmark-specific cropping are forbidden.

Preflight fails closed on duplicate bytes, duplicate obverse/reverse pairs,
same-side byte reuse, unsafe or semantic paths, missing or stale hashes,
specimen-limit violations, non-reciprocal repeated-specimen declarations, and
missing external near-duplicate review. Near-duplicate review is a recorded
human/tool-assisted leakage check, not an automatic assertion that distinct
bytes depict distinct captures.

Privacy classification is separate from copyright/license status and from
provider authorization. Provider eligibility is an explicit per-image and
per-case decision derived only from recorded privacy, licensing, and provider-
use declarations; missing, ambiguous, private, or uncertain authorization
fails closed. Prior benchmark or model-development use is declared before
freeze and is never inferred from provenance.

#### Execution and authority boundaries

The v1 execution view is paired-image multimodal visual-provider evaluation.
OCR, fusion, ranking, GUI behavior, persistence, durability, and production
thresholds remain separate evaluation views. Acceptance code must not tune or
branch production behavior, and no acceptance image may be used for provider,
prompt, ranking, or threshold optimization.

Provider output is advisory evidence. Evidence must precede inference, system
confidence is unavailable in v1, and provider source scores remain
uncalibrated rather than being interpreted as probabilities. Variety
attribution is outside v1 correctness, and `mint`, `mint_mark`, `variety`, and
`catalog_reference` remain null-only. Human confirmation remains required for
collection decisions and persistence.

#### Identity and metric semantics

The authoritative headline identity metric uses the separately versioned,
frozen canonical-equivalence policy. Exact normalized-string matching is a
diagnostic only. Complete identity credit requires country, denomination, and
year all to be present, canonicalizable, and equal; partial proposals receive
no complete-identity credit. Unknown, malformed, ambiguous, or unmapped values
fail closed rather than receiving inferred credit.

Reports state exact numerators and denominators. Specimen-weighted reporting is
primary so that a specimen represented twice does not receive twice the weight
of a specimen represented once. Case-weighted results remain a labeled
diagnostic. Action correctness, complete-identity correctness, provider
availability, and infrastructure failure are reported separately; an
infrastructure failure is never counted as an abstention or silently removed
from an unstated denominator.

Stability reporting lists all 50 calls (10 cases by five calls), per-case
outcome distributions, action consistency, canonical complete-identity
consistency where applicable, exact denominators, and relevant-cohort coverage.
It does not convert repeatability into confidence or correctness.
