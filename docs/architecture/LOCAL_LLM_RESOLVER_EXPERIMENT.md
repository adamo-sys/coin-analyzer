# Local LLM Resolver Experiment Architecture Amendment

Status: APPROVED — standalone benchmark/test experiment only

## Purpose

Define a removable, feature-flagged local LLM resolver experiment for Coin Analyzer.
The experiment exists only to measure whether a local language model can improve
identity resolution from already-produced recognition evidence without changing
production OCR, UI, persistence, review behavior, or the default recognition flow.

## Scope

The local resolver is an opt-in, headless evaluation component. It may be invoked
only from standalone benchmark and test code. It is not wired into production
composition, desktop UI, persistence services, import workflow defaults, or OCR
provider behavior.

The experiment may consume bounded evidence already produced by existing
recognition/evaluation code, such as normalized OCR text, candidate country,
denomination and year values, candidate identities, and provenance-safe metadata.
It must not alter or regenerate OCR output.

## Feature flag and removability

- The resolver is disabled by default.
- Invocation requires an explicit experiment feature flag or CLI/test option.
- No production code path may call the resolver implicitly.
- Removing the experiment must not require changes to UI, persistence, OCR, or
  the default recognition pipeline.
- The implementation should remain isolated behind a small resolver interface so
  that alternate local runtimes can be compared without restructuring the app.

## Input and privacy boundary

- Inputs must be local, bounded, and provenance-safe.
- Private collection data, private photographs, backups, exports, credentials,
  and the uncertain-provenance `test_coins/` JPEGs must not be sent to external
  providers or published in artifacts.
- The resolver experiment may run against sanitized benchmark evidence and
  synthetic fixtures.
- The experiment must not add cloud inference as a fallback.

## Structured output contract

The resolver must return strict structured JSON with this logical shape:

- `country`: string or null
- `denomination`: string or null
- `year`: string or null
- `candidate_id`: string or null
- `confidence`: numeric value only if the selected local runtime exposes a
  defensible score semantics; otherwise null
- `reason`: short diagnostic string
- `abstain`: boolean

Malformed JSON, schema violations, timeouts, runtime unavailability, or model
errors are resolver failures and must not be converted into a guessed identity.

The resolver must be allowed to abstain. An abstention is preferable to an
unsupported identity guess.

## Advisory-only semantics

Resolver output is advisory evidence only.

- It does not become a confirmed observation.
- It does not bypass collector review.
- It does not automatically persist to the collection.
- It does not override existing OCR candidates in production.
- It does not create or mutate benchmark ground truth.

## Evaluation metrics

Standalone benchmark/test execution must report at minimum:

- country exact accuracy
- denomination exact accuracy
- year exact accuracy
- full-identity exact accuracy
- unresolved rate
- false-positive rate
- mean resolver latency
- median resolver latency
- nearest-rank p95 resolver latency
- resolver/runtime failure count

A false positive is a non-abstaining resolver prediction that is incorrect
against certain provenance-backed ground truth. Uncertain references are excluded
from exact-accuracy and false-positive denominators, consistent with the existing
evaluation contract.

Results must remain separate from production OCR baseline metrics so that any
improvement or regression attributable to the resolver is visible.

## Runtime assumptions

The first implementation may target a local HTTP or CLI-compatible inference
runtime. Runtime configuration must be injectable and testable; tests must not
require a real large model download.

Unit tests should use deterministic fake/stub responses for success, abstention,
malformed JSON, timeout/unavailable runtime, and incorrect prediction cases.

## Explicit non-goals

- no UI changes
- no persistence changes
- no OCR changes
- no default recognition-flow changes
- no automatic collector decision-making
- no cloud-provider fallback
- no benchmark-ground-truth modification
- no model fine-tuning or training pipeline
- no claim that model scores are calibrated probabilities

## Implementation gate

Implementation may proceed only as a bounded experiment matching this amendment.
Any proposal to wire the resolver into the production scan → review → save path,
change acceptance/review semantics, or persist resolver output automatically
requires a separate architecture amendment and explicit authorization.
