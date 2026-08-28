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
