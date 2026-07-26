# Sprint 10 - Human-Reviewed OCR Metadata

## Status

Sprint 10 adds a pure, deterministic human-review layer for advisory OCR
metadata. It takes the immutable OCR report produced by Sprint 9 through
explicit field review, accepted-value consolidation, conflict resolution, and
a final collection-independent projection.

The validated repository baseline entering Sprint 10 closure is:

```text
2,554 passed
22 skipped
```

## Goals

- Represent explicit human decisions for each OCR field candidate.
- Reconcile those decisions against the exact source report.
- Preserve accepted values, original values, provenance, and reviewer reasons.
- Detect agreement and conflict across accepted values.
- Require explicit human decisions for conflict resolution.
- Produce an immutable, JSON-safe final metadata projection.
- Keep the entire workflow deterministic, stateless, and auditable.
- Expose one narrow application-service boundary for the complete review
  session.

## Non-goals

Sprint 10 does not:

- enable OCR in the default desktop workflow;
- provide a review GUI or desktop presentation model;
- persist reviews, resolutions, or projected metadata;
- mutate collection records;
- create confirmed observations;
- map projected fields into collection models;
- infer, review, or assign grades;
- automatically resolve conflicts;
- register runtime features;
- replace Sprint 9 OCR providers or mutable legacy OCR internals.

## Trust boundaries

- **OCR is advisory.** An OCR candidate is a suggestion, not a fact.
- **Human review is mandatory.** Only explicit approve or correct decisions
  become accepted metadata.
- **Grade is excluded.** Grade is not an allowed review field and is rejected
  again at downstream validation boundaries.
- **The final projection is not collection-ready.** It is an audit-friendly
  metadata projection, not a collection or confirmed-observation model.
- **No persistence or mutation occurs.** Sprint 10 services have no filesystem,
  database, collection-backend, GUI, or global-registration side effects.
- **Unresolved means unresolved.** Missing or deferred decisions never silently
  select or emit a value.

## Units and responsibilities

### Unit 1A - Review contracts

`capture_import/workflow_ocr_review_models.py`

Defines immutable field-level and report-level human-review DTOs:

- `OCRReviewDecision`
- `OCRFieldReview`
- `OCRReportReview`

It validates supported fields, exact review targets, reviewed values, reviewer
reasons, immutable tuples, and JSON-safe serialization.

### Unit 1B - Review reconciliation

`capture_import/workflow_ocr_review_service.py`

Reconciles an `OCRReportReview` against the exact candidates in an
`OCRMetadataReport`. It produces `OCRReviewReconciliation`, separating
accepted, rejected, deferred, and missing candidates. Accepted fields preserve
their original value, accepted value, decision, and reviewer reason.

### Unit 1C - Accepted metadata consolidation

`capture_import/workflow_ocr_consolidation.py`

Groups accepted fields by `(source_coin_id, field_name)`, preserves their full
provenance, and emits:

- `AGREED` when all accepted sources contain one exact value;
- `CONFLICT` when two or more distinct accepted values remain.

No conflict value is selected automatically.

### Unit 1D - Explicit conflict resolution

`capture_import/workflow_ocr_conflict_resolution.py`

Applies one explicit human resolution request to one consolidated conflict.
The result retains the complete original conflict, including distinct values
and provenance.

### Unit 1E - Final reviewed metadata projection

`capture_import/workflow_ocr_final_projection.py`

Combines agreed fields and explicit conflict-resolution results into
`OCRFinalMetadataProjection`. Final and unresolved fields remain separate.
The projection retains each source field and any conflict-resolution decision.
It is collection-independent and does not authorize persistence.

### Unit 1F - Review-session orchestration

`capture_import/workflow_ocr_review_session.py`

Provides the stateless application-service boundary:

- `OCRReviewSessionRequest`
- `OCRReviewSessionResult`
- `OCRReviewSessionService`

It invokes Units 1B through 1E in order and returns every major intermediate
result for auditability. It coordinates the existing services without
reimplementing their business rules.

## End-to-end flow

```text
OCRMetadataReport
        |
        v
OCRReportReview
        |
        v
OCRReviewReconciliation
        |
        v
OCRMetadataConsolidation
        |
        v
explicit conflict resolutions
        |
        v
OCRFinalMetadataProjection
```

The detailed sequence is:

1. Reconcile source OCR candidates with exact human field reviews.
2. Consolidate approved and corrected values by coin and field.
3. Apply zero or more explicit resolution requests to consolidated conflicts.
4. Project agreed and explicitly resolved fields as final metadata.
5. Preserve missing or deferred conflict outcomes as unresolved fields.

The session result exposes reconciliation, consolidation, conflict resolutions,
and final projection together. Its `is_complete` property requires both
complete reconciliation and a final projection with no unresolved fields.

## Reconciliation modes

### `STRICT_COMPLETE`

Every source candidate must have a non-deferred human decision. A missing
review or a field-level `DEFER` causes reconciliation to fail. Rejection is an
explicit, complete decision and therefore does not make strict reconciliation
incomplete.

Strict reconciliation does not automatically resolve consolidated conflicts.
A strict session can still have an incomplete final projection when accepted
sources disagree and no completing conflict resolution is supplied.

### `PARTIAL`

Missing and deferred field reviews are recorded instead of causing
reconciliation to fail. Approved or corrected fields may continue through the
remaining stages. Session completeness remains false while reconciliation or
the final projection is incomplete.

## Field-review decisions

- **`APPROVE`** accepts the source candidate's exact normalized value.
- **`CORRECT`** requires a non-empty reviewed value different from the source
  candidate value. The original and corrected values are both preserved.
- **`REJECT`** explicitly excludes the candidate from accepted metadata and
  emits no accepted value.
- **`DEFER`** records that no decision has been made and emits no accepted
  value.

All field-review decisions retain the opaque reviewer identifier and the
human-provided reason in the review and reconciliation audit trail.

## Consolidation outcomes

- **`AGREED`** requires exactly one distinct accepted value. That value becomes
  the consolidated value and passes through the final projection unchanged.
- **`CONFLICT`** requires at least two exact distinct values. Its consolidated
  value is `None`; all values and provenance remain available for review.

Consolidation currently uses exact string equality. It does not apply fuzzy
matching, field-specific equivalence, source priority, or automatic selection.

## Conflict-resolution decisions

- **`SELECT_EXISTING_VALUE`** selects exactly one value already present in the
  conflict's distinct values.
- **`ENTER_CORRECTED_VALUE`** supplies a non-empty value that is not already one
  of the conflicting values.
- **`DEFER`** supplies no resolved value and leaves the projected field
  unresolved.

A missing conflict-resolution request also leaves the field unresolved.
Invented targets, duplicate targets, non-conflict targets, and targets whose
original values or provenance do not match the consolidation are rejected by
the existing conflict-resolution and final-projection rules.

## Determinism and serialization

Sprint 10 DTOs use frozen, slotted dataclasses and immutable tuples. Each DTO
has explicit `validate()` and deterministic `to_dict()` behavior. Enums
serialize to strings, tuples serialize to JSON arrays, and no timestamps or
runtime-dependent identifiers are added.

Consolidated, resolved, projected, and session results use deterministic
ordering by `source_coin_id` and `field_name`. Lower-level candidate and
provenance ordering includes stable source attributes as tie-breakers.
Equivalent validated inputs therefore produce identical JSON-safe result
payloads.

## Independent architecture review

**Verdict: PASS**

### Separation of responsibilities

Responsibilities are separated cleanly. Contracts, reconciliation,
consolidation, single-conflict resolution, final projection, and session
orchestration live in distinct modules. No production defect was found during
the closure review.

### Orchestration ownership

Unit 1F orchestrates rather than duplicates domain behavior. Its call sequence
is reconciliation service, consolidation service, conflict-resolution service
for each explicit request, and final-projection service. Strict-mode failure,
grade rejection, conflict decision validity, and invented, duplicate,
mismatched, or non-conflict resolution rejection remain owned by Units 1A
through 1E.

### Import direction and cycles

The dependencies are directional:

```text
review contracts
    <- reconciliation
    <- consolidation
    <- conflict resolution
    <- final projection
    <- review-session orchestration
```

Some higher units import more than one lower unit for their DTO types, but no
lower unit imports a higher unit. No cycle was found.

### Boundary preservation

The Sprint 10 production modules do not import GUI, persistence, collection,
confirmed-observation, desktop-workflow, feature-registration, or legacy
mutable OCR modules. Unit 1F's focused import-boundary test enforces its exact
allowed imports. Existing focused tests cover the remaining module boundaries
through their pure contracts and service behavior, so no additional broad
architecture test was warranted.

### Human control and collection mutation

No Sprint 10 module contains a collection mutation path. Accepted metadata
requires explicit approve or correct decisions, and conflicts require an
explicit selecting or correcting decision before emitting a final value.
Consequently, no OCR value can reach collection mutation through Sprint 10,
with or without human decisions, because collection mapping and mutation are
deliberately absent.

### Grade exclusion

Grade is absent from the allowed OCR review fields and is rejected at review,
accepted-field, consolidation, conflict-resolution, final-projection, and
session validation boundaries. No valid Sprint 10 contract can carry grade.

### Unresolved states

Missing and deferred field reviews are explicit reconciliation states.
Consolidation conflicts have no consolidated value. Missing or deferred
conflict resolutions remain in `unresolved_fields` with no final value. No
fallback, source priority, or implicit winner is present.

### DTO and side-effect review

The DTOs are frozen and slotted, validate tuple-backed collections, and expose
JSON-safe deterministic dictionaries. The services are stateless. No hidden
filesystem access, persistence, background work, global mutation, or runtime
registration was found.

### Defects

No defects were identified. The items below are technical debt or explicitly
deferred scope, not current correctness failures.

## Known technical debt

- Candidate keys, field identities, and provenance identities repeat similar
  tuple structures across modules. A shared typed identity may eventually
  reduce drift, but extracting it now would broaden coupling.
- Validation is primarily generic string validation. Field-specific validators
  for years, countries, denominations, certification numbers, and other fields
  remain future work.
- Consolidation uses exact string equality and has no field-aware normalization
  or equivalence policy.
- Reviewer identity is an opaque string with no identity-provider or actor
  model.
- Field-review reasons are preserved in provenance, while conflict-resolution
  decisions have no durable persistence or audit-storage boundary.
- The final projection is not mapped to confirmed observations or collection
  models.
- There is no desktop presentation model or review UI.
- There is no persistence boundary for reviews, resolutions, or projections.
- Review DTOs have no explicit schema version or migration strategy.
- The focused test files, especially session orchestration tests, are large.
  Shared helper extraction may become worthwhile if another workflow unit
  repeats the same fixtures; extracting them now would add indirection without
  production benefit.
- Git may warn that LF files will be converted to CRLF in this Windows
  checkout. This is environmental and non-blocking.

## Deferred work

- Desktop review and conflict-resolution presentation models.
- Opt-in desktop integration after an explicit product boundary is approved.
- Durable audit storage for reviews and conflict resolutions.
- Mapping approved final metadata into confirmed-observation contracts.
- Collection mapping and mutation behind a separate explicit authorization
  boundary.
- Field-specific validation and equivalence rules.
- Reviewer identity integration.
- DTO schema versioning and migrations.

## Sprint 10 commits

```text
24ef70c feat: add OCR review domain contracts
7fcc56e feat: add OCR review reconciliation service
8b1902d feat: add OCR metadata consolidation
ef79b4d feat: add OCR conflict resolution
6c05147 feat: add final OCR metadata projection
93b4fab feat: add OCR review session orchestration
```
