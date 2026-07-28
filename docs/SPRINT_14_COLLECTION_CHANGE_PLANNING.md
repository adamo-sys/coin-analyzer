# Sprint 14 - Collection Change Planning

## Sprint objective

Sprint 14 establishes an immutable, auditable planning boundary between a
Sprint 13 `READY` confirmed-observation result and any future collection
mutation. It maps the explicitly supported confirmed fields, compares them
with a caller-supplied immutable record snapshot, constructs field proposals,
aggregates a durable change plan, and classifies that plan conservatively.

Sprint 14 does not mutate the collection. It does not approve a proposal,
authorize execution, reread repository state, persist approval evidence, or
resolve destructive and conflicting operations.

## Executive summary

The six units form this directional pipeline:

```text
Sprint 13 READY ConfirmedObservationReadinessResult
    containing immutable ConfirmedFieldObservation values
        |
        v
Unit 1B - supported collection-field mapping
        |
        v
Unit 1C - immutable current-record comparison
        |
        v
Unit 1D - field-level change-proposal construction
        |
        v
Unit 1E - durable CollectionChangePlan aggregation
        |
        v
Unit 1F - conservative, transient policy assessment
        |
        v
future explicit approval boundary
```

Unit 1A supplies the shared immutable, versioned proposal and plan contracts.
Every later unit accepts the complete output of its predecessor or the durable
Unit 1A plan; no stage reruns an earlier mapping, comparison, or construction
decision.

The result is a dry-run domain boundary. Every supported mapped field is
represented, including `NO_CHANGE` audit evidence. Approval-required and
blocked states remain explicit, but neither is an approval or execution
decision.

## Delivered units

### Unit 1A - Change-plan contracts

Module:
`collection_management/workflow_collection_change_plan_models.py`

- Defines frozen, slotted `CollectionRecordReference`,
  `CollectionFieldChangeProposal`, and `CollectionChangePlan` contracts.
- Requires explicit schema version `1`; unsupported versions raise
  `UnsupportedCollectionChangePlanSchemaVersion`.
- Enforces deterministic target-field order, nonempty proposal tuples,
  record/source/reviewer consistency, unique target and source fields, and
  complete `ConfirmedFieldObservation` traceability.
- Binds every operation to one approval requirement and reason code.
- Distinguishes `None` from an empty string and preserves exact values.
- Rejects `grade` as a target.
- Provides strict, deterministic, JSON-safe `to_dict`/`from_dict`
  serialization for the durable proposal and plan boundary.

### Unit 1B - Confirmed collection-field mapping

Module:
`collection_management/workflow_confirmed_collection_field_mapper.py`

- Accepts only a genuine Sprint 13 `READY`
  `ConfirmedObservationReadinessResult`.
- Preserves each complete source observation and aggregate linkage.
- Uses the canonical value when present; otherwise uses the submitted value.
- Preserves the selected value exactly.
- Fails closed on ambiguous, unsupported, duplicate, or inconsistent fields.
- Performs no collection read and creates no proposal or plan.

The exact supported mapping table is:

| Confirmed field | Collection target |
| --- | --- |
| `country` | `country` |
| `denomination` | `denomination` |
| `year` | `year` |

The currently ambiguous fields are `certification_number` and `series_type`;
they require a later explicit collection-schema policy. Current unsupported
fields include `monarch`, `mintmark`, `banknote_prefix`, `silver_indicator`,
and `variety_keyword`. Unknown future fields also fail closed.

### Unit 1C - Collection-record comparison

Module:
`collection_management/workflow_collection_record_comparison.py`

- Accepts a Unit 1B mapping result and a caller-supplied immutable
  `CollectionRecordSnapshot`.
- Represents field availability as `PRESENT`, `ABSENT`, or `UNAVAILABLE`.
- Produces `ABSENT`, `EMPTY`, `UNAVAILABLE`, `EXACT_MATCH`, or `DIFFERENT`.
- Uses exact string equality: case, whitespace, punctuation, numeric text, and
  Unicode code points remain significant.
- Does not normalize either value.
- Raises `MissingCollectionRecordSnapshotFieldError` when a mapped target is
  omitted; omission never becomes `UNAVAILABLE`.
- Ignores extra snapshot fields from the supported target vocabulary that are
  not present in the mapping result.
- Rejects snapshot fields whose target is not a `CollectionTargetField`.
- Keeps collection `record_id` and confirmed `source_coin_id` distinct.
- Performs no repository lookup or mutation.

The exact empty-value semantics are:

| Current snapshot | Mapped value | Outcome |
| --- | --- | --- |
| Present `""` | `""` | `EXACT_MATCH` |
| Present `""` | Nonempty | `EMPTY` |
| Present nonempty | `""` | `DIFFERENT` |

### Unit 1D - Change-proposal construction

Module:
`collection_management/workflow_collection_change_proposal_builder.py`

- Converts a complete Unit 1C comparison result into one immutable proposal
  per comparison.
- Preserves exact current and mapped values, source-observation identity,
  rationale, record identity, reviewer identity, review-session linkage, and
  fingerprint linkage.
- Sorts the complete result deterministically by target field.
- Returns no partial result when any comparison fails.
- Preserves `current_value` as `None` for `ABSENT` and preserves the exact
  empty string for `EMPTY`.
- Lets Unit 1A NFC and contract errors propagate rather than rewriting
  decomposed or otherwise invalid evidence.
- Makes no approval or execution decision.

The exact conversion policy is:

| Comparison outcome | Operation | Approval requirement | Reason code |
| --- | --- | --- | --- |
| `ABSENT` | `ADD` | `REQUIRED` | `NEW_VALUE` |
| `EMPTY` | `UPDATE` | `REQUIRED` | `DIFFERENT_VALUE` |
| `EXACT_MATCH` | `NO_CHANGE` | `NOT_REQUIRED` | `EQUIVALENT_VALUE` |
| `DIFFERENT` | `UPDATE` | `REQUIRED` | `DIFFERENT_VALUE` |
| `UNAVAILABLE` | Error | N/A | `UnavailableCollectionProposalSourceError` |

`CLEAR` is not emitted because Unit 1B supplies mapped strings. `CONFLICT` is
not inferred from an ordinary exact difference; such evidence remains an
`UPDATE`.

### Unit 1E - Change-plan aggregation

Module:
`collection_management/workflow_collection_change_plan_builder.py`

- Accepts only `CollectionChangeProposalBuildResult`.
- Returns the durable Unit 1A `CollectionChangePlan` directly; no wrapper DTO
  or second serialization model exists.
- Maps `target_record`, `source_coin_id`, `proposals`, `review_session_id`, and
  `source_fingerprint` exactly and supplies the current Unit 1A schema version.
- Preserves the proposal tuple and every proposal object by identity.
- Consequently preserves nested source-observation and provenance identities.
- Retains `NO_CHANGE` proposals; `NO_CHANGE`-only plans are valid.
- Rejects malformed or reordered Unit 1D results rather than repairing them.
- Does not recalculate proposal operations, approval requirements, reasons, or
  values.
- Delegates aggregate validation and serialization to Unit 1A.

### Unit 1F - Change-policy assessment

Module:
`collection_management/workflow_collection_change_policy.py`

- Accepts only a complete Unit 1A `CollectionChangePlan`.
- Returns transient diagnostic assessment objects that retain the exact plan
  and proposal objects.
- Uses an immutable, exhaustive operation-to-status table.
- Fails closed if a future operation lacks an explicit policy entry.
- Provides a strict helper that raises
  `BlockedCollectionChangePlanError` for blocked plans.
- Does not approve `ADD` or `UPDATE`; an unblocked plan is still not approved
  or executable.

The exact policy table is:

| Operation | Policy status |
| --- | --- |
| `NO_CHANGE` | `SAFE_NO_OP` |
| `ADD` | `REQUIRES_APPROVAL` |
| `UPDATE` | `REQUIRES_APPROVAL` |
| `CLEAR` | `BLOCKED_CONFLICT` |
| `CONFLICT` | `BLOCKED_CONFLICT` |

The aggregate summary formulas are:

- `contains_blocked_items` is true exactly when any assessment is
  `BLOCKED_CONFLICT`.
- `contains_approval_required_items` is true exactly when any assessment is
  `REQUIRES_APPROVAL`; blocked entries do not implicitly count as
  approval-required.
- `contains_only_safe_no_ops` is true exactly when every assessment is
  `SAFE_NO_OP`.

`require_unblocked_collection_change_plan` returns the diagnostic assessment
it computes when no blocked item exists. It does not satisfy outstanding
approval, create a token, or authorize execution. `CLEAR` remains blocked
until an explicit destructive-clear policy and user-confirmation boundary
exist. `CONFLICT` remains blocked until an explicit conflict-resolution
boundary exists.

## Shared contract vocabulary

Unit 1A defines these exact structural enums:

| Contract | Values |
| --- | --- |
| `CollectionChangeOperation` | `ADD`, `UPDATE`, `CLEAR`, `NO_CHANGE`, `CONFLICT` |
| `CollectionChangeApprovalRequirement` | `NOT_REQUIRED`, `REQUIRED` |
| `CollectionChangeReasonCode` | `NEW_VALUE`, `DIFFERENT_VALUE`, `EXPLICIT_CLEAR`, `EQUIVALENT_VALUE`, `EXISTING_VALUE_CONFLICT` |

An approval requirement is not an approval result. Unit 1A contains no
approved, rejected, executable, applied, or persisted state.

## End-to-end invariants

- Only a Sprint 13 `READY` result enters Unit 1B.
- Only explicitly supported field mappings proceed.
- Current state is supplied through immutable snapshots, not repository reads.
- Comparison uses exact equality and performs no normalization.
- Missing mapped snapshot fields and unavailable current state fail closed.
- Every comparison produces one proposal, or proposal construction fails
  atomically.
- Every proposal remains in the plan; `NO_CHANGE` remains audit evidence.
- Unavailable current state fails closed.
- Current Unit 1D never emits `CLEAR`.
- Ordinary differing values become `UPDATE`, not `CONFLICT`.
- `ADD`, `UPDATE`, `CLEAR`, and `CONFLICT` structurally require future human
  approval under Unit 1A.
- Unit 1F additionally blocks `CLEAR` and `CONFLICT`.
- No status authorizes execution; unblocked is not approved, and blocked is
  not rejected.
- No stage reads a repository, persists approval, or mutates a collection.
- No timestamp, plan ID, UUID, random value, or environment-derived value is
  generated.
- Full confirmed-observation provenance remains attached by object identity
  through mapping, comparison, proposal construction, plan aggregation, and
  policy assessment.
- Contracts and intermediate results are frozen and slotted; services are
  stateless.
- Equivalent inputs produce equivalent ordered outputs.

## Public API summary

The table lists module-defined public names and excludes imported names.

| Unit | Module-defined public API |
| --- | --- |
| 1A | `CURRENT_COLLECTION_CHANGE_PLAN_SCHEMA_VERSION`, `UnsupportedCollectionChangePlanSchemaVersion`, `CollectionRecordReference`, `CollectionChangeOperation`, `CollectionChangeApprovalRequirement`, `CollectionChangeReasonCode`, `CollectionFieldChangeProposal`, `CollectionChangePlan` |
| 1B | `CollectionTargetField`, `ConfirmedCollectionFieldMappingError`, `UnsupportedConfirmedCollectionFieldError`, `AmbiguousConfirmedCollectionFieldError`, `DuplicateCollectionTargetFieldError`, `InvalidConfirmedCollectionMappingContextError`, `ConfirmedCollectionFieldMapping`, `ConfirmedCollectionFieldMappingResult`, `ConfirmedCollectionFieldMapper`, `map_ready_confirmed_observations` |
| 1C | `CollectionRecordFieldAvailability`, `CollectionFieldComparisonOutcome`, `CollectionRecordComparisonError`, `InvalidCollectionRecordComparisonContextError`, `MissingCollectionRecordSnapshotFieldError`, `CollectionRecordFieldSnapshot`, `CollectionRecordSnapshot`, `CollectionFieldComparison`, `CollectionRecordComparisonResult`, `CollectionRecordComparisonService`, `compare_mapped_collection_fields` |
| 1D | `CollectionChangeProposalBuildError`, `UnsupportedCollectionComparisonOutcomeError`, `UnavailableCollectionProposalSourceError`, `InvalidCollectionChangeProposalContextError`, `DuplicateCollectionChangeProposalFieldError`, `CollectionChangeProposalBuildResult`, `CollectionChangeProposalBuilder`, `build_collection_change_proposals` |
| 1E | `CollectionChangePlanBuildError`, `InvalidCollectionChangePlanBuildContextError`, `CollectionChangePlanBuilder`, `build_collection_change_plan` |
| 1F | `CollectionChangePolicyStatus`, `CollectionChangePolicyError`, `UnsupportedCollectionChangePolicyOperationError`, `InvalidCollectionChangePolicyContextError`, `BlockedCollectionChangePlanError`, `CollectionChangePolicyAssessment`, `CollectionChangePlanPolicyAssessment`, `CollectionChangePolicyAssessor`, `assess_collection_change_plan`, `require_unblocked_collection_change_plan` |

## Serialization boundaries

Durable, versioned serialized domain records are:

- Sprint 13 `ConfirmedObservationProvenance`,
  `ConfirmedFieldObservation`, and `ConfirmedObservationSet`;
- Unit 1A `CollectionFieldChangeProposal`; and
- Unit 1A `CollectionChangePlan`.

The Unit 1B mapping result, Unit 1C snapshots/comparison result, Unit 1D
proposal-build result, and Unit 1F policy assessment are intentionally
transient. Unit 1E returns the existing durable Unit 1A plan rather than
inventing another persisted shape.

This separation versions durable domain evidence while avoiding speculative
schemas and migration obligations for in-memory orchestration results.

Unit 1A requires serialized proposal values to be already NFC-normalized.
Unit 1D preserves exact source evidence and does not normalize decomposed
legacy text; Unit 1A validation fails explicitly instead. Sprint 14 performs
no normalization or migration.

## Validation baseline

The authoritative post-Unit 1F repository run recorded:

```text
3,320 total
3,297 passed
22 skipped
1 failure
0 errors
```

The latest targeted Sprint 14 group recorded:

```text
176 passed
0 failures
0 errors
```

The latest focused Unit 1F suite recorded:

```text
45 passed
0 failures
0 errors
```

All Sprint 14 focused and targeted tests passed. The repository suite was not
fully green because of the separately documented unrelated failure below.
This documentation-only closure does not alter executable code, so the full
suite was not rerun for the closure document.

## Known unrelated failure

Test:

```text
test_melt_value_engine.TestApiSpotPriceProvider.test_cache_persistence
```

Observed in repository-root execution:

```text
expected 40.0
actual None
```

The failure was independently reproduced and is classified as the existing
repository-root relative cache-path issue. It is unrelated to Sprint 14; no
Sprint 14 module depends on that cache path, and no melt-value fix is included
in this sprint.

Future maintenance should either isolate the test in a writable temporary
directory or allow the provider to receive an injected absolute cache path.
This is a recommendation, not completed work.

## Deliberate exclusions

These are intentional future boundaries rather than accidental omissions:

- human approval and rejection decisions;
- approval records, signatures, tokens, and persistence;
- collection mutation and mutation execution;
- repository lookup and current-record rereads;
- stale-state validation, optimistic concurrency, and record locking;
- conflict resolution and destructive-clear confirmation;
- GUI, desktop preview, and desktop approval workflow;
- automatic invocation and OCR invocation;
- external lookups;
- normalization or migration of legacy collection values;
- generated plan IDs, timestamps, UUIDs, and audit records.

Sprint 14 produces auditable planning evidence only.

## Technical boundaries and debt

### NFC boundary

Unit 1A requires NFC-normalized serialized values. Unit 1D preserves exact
evidence, so decomposed legacy values fail explicitly rather than being
silently rewritten. A future migration or normalization policy may be needed
before such values can enter durable plans.

### CLEAR boundary

`CLEAR` is structurally supported by Unit 1A, is not emitted by current Unit
1D, and is blocked by Unit 1F. A later boundary must define destructive-clear
policy and explicit user confirmation before any destructive action is
authorized.

### CONFLICT boundary

`CONFLICT` is structurally supported by Unit 1A. Ordinary `DIFFERENT` evidence
remains an `UPDATE`; Unit 1D does not infer a conflict. Valid conflict
proposals remain blocked until a later explicit conflict-resolution boundary
exists.

### Stale-state boundary

Unit 1C compares a caller-supplied snapshot and never rereads the repository.
Execution does not yet exist. A future executor must establish freshness,
optimistic-concurrency or locking policy, and already-applied detection before
writing.

### Mapping boundary

Only `country`, `denomination`, and `year` currently map. Ambiguous and
unsupported fields require an explicit collection-schema policy before the
allowlist can expand.

### Roadmap boundary

The locked roadmap's broader Sprint 14 phase includes desktop change preview
and explicit collection-change approval. This completed architecture closure
stops at immutable planning and conservative policy assessment; it does not
claim those GUI or approval capabilities. They remain prerequisites before
controlled mutation.

### Unrelated cache-test debt

The melt-value cache-path test remains separate maintenance debt and was not
addressed in Sprint 14.

## Sprint completion criteria

The Sprint 14 collection change-planning architecture is complete because:

- immutable, versioned plan and proposal contracts exist;
- supported confirmed fields map through an explicit allowlist;
- immutable record snapshots distinguish present, absent, empty, and
  unavailable state;
- exact comparisons convert atomically into field proposals;
- proposals aggregate into a deterministic durable plan;
- plans receive a conservative, non-authorizing policy assessment;
- approval-required and blocked states remain explicit;
- complete source traceability is preserved;
- all Sprint 14 focused and targeted tests pass; and
- no approval, execution, persistence, or mutation boundary was crossed.

This completion statement applies to the bounded domain architecture delivered
by Units 1A-1F. It does not claim completion of the roadmap's deferred desktop
preview or explicit approval interfaces.

## Recommended next sprint

The locked roadmap names the next phase:

```text
Sprint 15 - Controlled Collection Mutation
```

However, its mutation command requires an approved plan, and Sprint 14
deliberately created no approval result. The first bounded Sprint 15 work
should therefore establish the missing explicit collection-change approval
boundary before implementing mutation:

1. immutable approval decision contracts;
2. per-proposal approve, reject, or defer decisions;
3. plan-level approval aggregation;
4. compatibility validation against Unit 1F policy evidence;
5. strict prohibition against approving blocked `CLEAR` or `CONFLICT`
   entries;
6. durable, versioned approval serialization;
7. an explicit stale-state and freshness-validation boundary;
8. no mutation execution in the approval or freshness units; and
9. an approval-and-freshness closure review.

Only afterward should Sprint 15 proceed to its locked mutation, atomic
persistence, backup/rollback, audit, desktop apply, and end-to-end units.
Approval and mutation must remain separate acts, consistent with the locked
architectural rules.

## Commit ledger

| Unit | Commit | Subject |
| --- | --- | --- |
| 1A | `e6bf50e` | `feat: add collection change-plan contracts` |
| 1B | `f6510ea` | `feat: add confirmed collection-field mapper` |
| 1C | `6c1237e` | `feat: add collection record comparison` |
| 1D | `03a11c6` | `feat: add collection change-proposal builder` |
| 1E | `9fad257` | `feat: add collection change-plan builder` |
| 1F | `0db45e8` | `feat: add collection change policy assessment` |

## Architecture closure verdict

**PASS.** Units 1A-1F form a deterministic, immutable, fail-closed planning
boundary. Durable records are versioned, intermediate results remain
transient, exact evidence and provenance are retained, and no stage approves
or mutates collection state.
