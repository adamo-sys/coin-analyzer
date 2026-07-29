# Sprint 15 — Controlled Collection Mutation

## Status

**Architecture closure: COMPLETE**

**Unrestricted production rollout: NOT COMPLETE**

Sprint 15 completes the controlled mutation architecture and provides a tested
conditional write path for the current JSON-backed collection store.

Sprint completion does not mean unrestricted production rollout is complete.
Recoverable backup, post-replacement recovery, durable mutation audit
evidence, and end-to-end apply orchestration remain mandatory rollout work.

## Scope

Sprint 15 establishes the explicit boundaries between a Sprint 14 collection
change plan and a controlled mutation of the authoritative collection record.
It adds:

- immutable approval evidence;
- approval-policy compatibility diagnostics;
- immutable freshness evidence;
- exact freshness compatibility diagnostics;
- deterministic mutation eligibility;
- an immutable mutation command;
- a narrow conditional repository capability;
- one controlled JSON-backed execution path; and
- an immutable execution result.

The sprint does not add desktop orchestration, operator authentication,
authorization roles, durable mutation audit storage, recoverable collection
backup, or automatic post-replacement recovery.

Confirmed observations and collection change-plan construction originate in
Sprints 13 and 14. Sprint 15 begins at explicit collection-change approval and
freshness evidence.

## Architecture chain

```text
Confirmed collection observations                 Sprint 13
    |
    v
Collection change plan                            Sprint 14
    |
    v
Collection change policy assessment               Sprint 14
    |
    v
Approval evidence                                 Sprint 15 Unit 1A
    |
    v
Approval compatibility                            Sprint 15 Unit 1B
    |
    v
Freshness evidence                                Sprint 15 Unit 1C
    |
    v
Freshness compatibility                           Sprint 15 Unit 1D
    |
    v
Mutation eligibility                              Sprint 15 Unit 1E
    |
    v
Immutable mutation command                        Sprint 15 Unit 1F
    |
    v
Controlled conditional repository mutation        Sprint 15 Unit 1G
    |
    v
Immutable execution result                        Sprint 15 Unit 1G
```

Each stage consumes the validated output or durable evidence of the preceding
boundary. No stage silently reruns or replaces an earlier approval, freshness,
policy, or eligibility decision.

## Unit chronology

| Unit | Title | Commit | Primary output | Lifetime |
| --- | --- | --- | --- | --- |
| 1A | Immutable approval-decision contracts | `b79e1d3` | `CollectionChangePlanApproval` | Durable |
| 1B | Approval-policy compatibility validation | `78d0782` | `CollectionChangePlanApprovalCompatibility` | Transient |
| 1C | Collection freshness evidence contracts | `7b73a88` | `CollectionRecordFreshnessEvidence` | Durable |
| 1D | Freshness evidence compatibility validation | `1ba9f1a` | `CollectionChangePlanFreshnessCompatibility` | Transient |
| 1E | Approval and freshness composition | `f9d07f7` | `CollectionChangePlanMutationEligibility` | Transient |
| 1F | Immutable mutation command construction | `b85303b` | `CollectionMutationCommand` | Transient |
| 1G | Controlled repository mutation | `104dce9` | `CollectionMutationExecutionResult` | Transient |

## Unit 1A - Immutable approval-decision contracts

Unit 1A defines durable, versioned evidence of a separate collection-change
decision.

The decision vocabulary is:

- `APPROVE`;
- `REJECT`; and
- `DEFER`.

The contracts:

- bind every decision to an exact plan proposal reference;
- require one approver identity across one approval aggregate;
- accept a strict caller-supplied UTC RFC 3339 timestamp ending in `Z`;
- preserve exact rationale text when present;
- reject duplicate or mismatched proposal decisions;
- serialize through closed, deterministic field sets; and
- retain plan, record, source, review-session, and fingerprint linkage.

The contracts record decision evidence only. `APPROVE` is not an authentication
result, role grant, permission, execution token, or proof of current repository
state. Structurally recorded approval for a blocked operation does not make
that operation policy-compatible.

## Unit 1B - Approval-policy compatibility

Unit 1B compares Unit 1A approval evidence with the Sprint 14 policy
assessment.

It determines:

- whether a supplied decision is compatible with the proposal policy;
- whether a compatible decision is resolved or unresolved;
- whether a required decision is missing;
- whether a safe no-op has an unexpected decision; and
- whether a blocked proposal has a forbidden approval.

Blocked status remains independent from approval-required status. A blocked
proposal is not made executable by `APPROVE`, and rejection or deferral does
not erase its blocked policy classification.

The findings are transient diagnostics. They are not serialized approval
records and do not mutate the durable approval evidence.

## Unit 1C - Collection freshness evidence

Unit 1C defines durable, versioned evidence describing the caller-observed
state of mapped collection fields.

Field availability is exactly:

- `PRESENT`;
- `ABSENT`; and
- `UNAVAILABLE`.

Evidence is a partial but nonempty tuple. Values remain exact:

- `PRESENT` requires a string, including an exact empty string when observed;
- `ABSENT` carries no value; and
- `UNAVAILABLE` carries no value.

The caller supplies `observed_at`; the contract does not invoke a clock.
Serialization is strict and deterministic. Unit 1C records an observation
time but defines no age, expiry, or maximum-staleness policy.

## Unit 1D - Freshness compatibility

Unit 1D compares a change plan's expected values with Unit 1C evidence.

The compatibility statuses are:

- `MATCHED`;
- `MISMATCHED`;
- `UNAVAILABLE`; and
- `MISSING`.

Comparison is exact. Expected absence is distinct from a present empty string.
Case, whitespace, punctuation, numeric-looking strings, and Unicode code
points are not normalized.

`observed_at` is retained as evidence but is not interpreted as an aging
policy. The result is transient and does not update the plan or evidence.

## Unit 1E - Mutation eligibility

Unit 1E composes the exact Unit 1B and Unit 1D diagnostics. It does not
recalculate either source.

The statuses are:

- `ELIGIBLE`;
- `NO_CHANGE`;
- `EXCLUDED`;
- `BLOCKED`; and
- `UNRESOLVED`.

The deterministic precedence is:

1. policy block;
2. missing approval;
3. incompatible approval;
4. rejection;
5. deferral;
6. freshness mismatch;
7. freshness unavailable;
8. freshness missing;
9. safe no-op; and
10. approved and freshness-matched.

`ELIGIBLE` means the supplied policy, approval, and freshness diagnostics
permit command construction. It is not independent operator authorization,
does not prove that repository state is still current, and does not perform a
write.

## Unit 1F - Immutable mutation command

Unit 1F constructs a command from a complete Unit 1E result.

Command policy:

- every `ELIGIBLE` finding creates exactly one command item;
- `NO_CHANGE` findings are omitted;
- any `EXCLUDED`, `BLOCKED`, or `UNRESOLVED` finding rejects the entire command;
- an empty eligible subset rejects command construction;
- command items retain exact expected and desired state; and
- items preserve plan-relative order and exact eligibility finding identity.

Current eligible operations are `ADD` and `UPDATE`. `CLEAR` is structurally
representable at the lower repository boundary but remains blocked by the
current policy. `NO_CHANGE` and `CONFLICT` cannot become command items.

The command is frozen, slotted, transient, and deliberately has no serializer.
It is not a durable authorization token and does not access a repository.

## Unit 1G - Controlled repository mutation

### Authoritative store

`CoinCollection` remains the authoritative collection store. JSON remains the
authoritative persistence format.

The new repository-neutral seam adds one capability:

```text
CoinCollection.mutate_fields_conditionally(record_id, changes)
```

Mutation uses the same injected `storage_path` used by existing collection
load, save, and import operations. The default remains
`data/collection.json`. No parallel production repository or in-memory-only
production path was introduced.

### Field allowlist

The mutable field allowlist is exactly:

- `country`;
- `denomination`; and
- `year`.

Identifiers, grade, notes, timestamps, fingerprints, schema values, arbitrary
keys, aliases, dotted paths, nested paths, case variants, and whitespace
variants are rejected.

### Raw JSON state

Conditional mutation reads authoritative raw JSON rather than comparing a
normalized `CoinItem`.

This preserves:

- a missing key as absence;
- a present empty string as `""`;
- a present whitespace string as its exact text; and
- every nonempty value exactly.

JSON `null` is rejected as malformed authoritative state for a mapped field.
The existing general `CoinItem.from_dict()` loader may normalize absence or
`null` into an empty string, which is why it is not the comparison authority
for conditional mutation.

### State classification

For every command field:

| Authoritative state | Classification |
| --- | --- |
| Exactly equals expected | Pending application |
| Exactly equals desired | Already applied |
| Equals neither | Stale conflict |

Expected and desired values cannot be equal in a valid conditional change.

Aggregate behavior is:

| Batch state | Result |
| --- | --- |
| All fields expected | Apply all; `APPLIED` |
| All fields desired | No replacement; `ALREADY_APPLIED` |
| Mixed expected and desired | Apply pending fields together; `APPLIED` |
| Any conflict | Reject entire batch; no write |

One already-desired field does not excuse a conflict in another field.

### Atomic publication

Unit 1G publishes one complete candidate JSON document through a single atomic
file replacement, preventing publication of a subset of command fields by
this method.

The sequence is:

1. acquire and verify the shared collection lease;
2. read and parse authoritative JSON;
3. locate the exact case-sensitive record ID;
4. classify every requested field;
5. reject all conflicts before candidate mutation;
6. construct the complete candidate in memory;
7. create a same-directory temporary file;
8. write UTF-8 JSON;
9. flush and `fsync` the temporary file;
10. close the temporary handle;
11. publish once with `os.replace`;
12. reread the authoritative JSON under the lease;
13. verify every command field against its exact desired value; and
14. construct the immutable result before releasing the lease.

Pre-replacement failures and `os.replace` failure preserve the prior
authoritative file. Temporary files are cleaned after pre-replacement
failures.

This guarantee is file-entry atomicity, not complete crash durability. The
shared writer does not `fsync` the containing directory and does not explicitly
preserve prior target-file permissions.

### Cooperative concurrency

Unit 1G provides cooperative stale-write protection among participants using
the shared collection lease, with exact expected-state enforcement inside
that critical section.

The lease is file-based and uses exclusive lock-file creation plus an OS
advisory lock. It coordinates threads and processes that participate in the
same lease convention. Normal `CoinCollection` saves and capture imports
participate.

The lease does not prevent:

- a maintenance script that bypasses the lease;
- a direct edit of the JSON file;
- an external process that ignores the lease; or
- storage changes below the application boundary.

A process crash releases the OS lock but may leave the lock file requiring
recovery. Unit 1G does not claim universal concurrency protection and does not
invent a revision, row version, or ETag.

### Verification uncertainty

A post-replacement verification failure means the final authoritative state
is uncertain; it does not imply the old file was restored.

Once `os.replace` succeeds, the new document may already be authoritative.
Failure to retain lock ownership, reread the file, locate the target, or
confirm every desired field raises `ConditionalCollectionVerificationError`.
The workflow translates that error to
`CollectionMutationVerificationError`.

No automatic rollback is claimed or attempted without a recoverable backup.

### Execution result

The execution statuses are exactly:

- `APPLIED`; and
- `ALREADY_APPLIED`.

`CollectionMutationExecutionResult` retains exactly:

- the exact command;
- status;
- ordered applied fields; and
- ordered already-applied fields.

The field groups are immutable, disjoint, duplicate-free, command-ordered, and
together cover every command target. The result is transient and contains no
repository handle, transaction, timestamp, actor, authorization flag, or
serializer.

## Durable and transient boundaries

| Boundary | Lifetime | Reason |
| --- | --- | --- |
| Approval proposal reference | Durable | Binds durable decision evidence to an exact proposal |
| Proposal approval | Durable | Records exact decision, approver, time, and rationale |
| Plan approval | Durable | Aggregates the caller-supplied decisions and linkage |
| Approval compatibility | Transient | Derived policy diagnostic |
| Field freshness evidence | Durable | Records caller-observed exact state |
| Record freshness evidence | Durable | Aggregates observation time, target, and fields |
| Freshness compatibility | Transient | Derived exact comparison diagnostic |
| Mutation eligibility | Transient | Derived composition of approval and freshness |
| Mutation command | Transient | One-time exact execution instruction |
| Repository conditional result | Transient | Lower-level invocation result |
| Workflow execution result | Transient | Controlled execution diagnostic |

Only evidence requiring later reconstruction is versioned and serialized.
Derived compatibility, eligibility, command, and execution objects avoid
speculative persistence schemas.

## Boundary statements

- Approval alone does not permit mutation.
- Freshness match alone does not permit mutation.
- `ELIGIBLE` does not authenticate or authorize an operator.
- Command construction does not prove repository currency.
- Unit 1G rereads authoritative state at execution time.
- Unit 1G does not authenticate an operator.
- The cooperative lease does not prevent every external race.
- Verification failure after replacement does not restore the old file.
- Mutation audit evidence is not persisted.
- Production rollout is not complete.

Unit 1G is a controlled execution boundary for a previously constructed
command. It does not authenticate an operator or independently authorize the
underlying business decision.

## Completion criteria

The bounded Sprint 15 controlled-mutation architecture is complete because:

- approval evidence is explicit, immutable, and durable;
- policy compatibility is deterministic;
- current-state evidence is explicit, immutable, and durable;
- freshness compatibility is deterministic and exact;
- proposal-level eligibility is explicit;
- commands contain only eligible changes;
- commands preserve exact expected and desired state;
- authoritative stale state prevents mutation;
- multiple pending fields publish through one atomic file replacement;
- replay is idempotent when the repository already contains desired state;
- controlled execution returns immutable diagnostics;
- no force, partial, or best-effort mutation path exists;
- focused, repository, locking, and full regression tests pass; and
- remaining production hardening is explicitly documented.

This completion statement applies to the architecture delivered by Units
1A-1G. It does not claim satisfaction of the locked roadmap's broader
production-rollout exit gate.

## Production-readiness gaps

### A. Required before full production mutation rollout

| Gap | Risk | Why architecture closure can proceed | Likely bounded unit | Acceptance criterion |
| --- | --- | --- | --- | --- |
| Recoverable old-file backup | A successful replacement cannot currently restore the prior document | Unit 1G accurately reports uncertainty and never claims rollback | Backup artifact and retention unit | Exact prior bytes are durably retained before publication and safely recoverable |
| Post-replacement recovery strategy | Verification or process failure after replacement can leave uncertain final state | The uncertainty is typed and fail-closed at the current boundary | Recovery state machine and startup reconciliation unit | Startup deterministically proves old or new state and completes or restores without guessing |
| Durable mutation audit record | Decisions and transient results do not form retained execution history | Durable approval and freshness evidence already preserve inputs; execution audit is a separate responsibility | Versioned mutation-audit contracts and repository unit | Approved changes, old/new values, linkage, result, and schema survive restart without unsafe paths |
| End-to-end apply orchestration | The implemented services are not yet connected into one deliberate user apply path | Each lower boundary is independently testable and explicit | Desktop/application apply coordinator unit | One explicit workflow binds review, plan, approval, freshness reread, command, execution, recovery, and audit |

These gaps are mandatory because the locked roadmap requires rollback/backup,
auditable writes, desktop apply, and end-to-end recovery behavior before its
production mutation exit gate can pass.

### B. Desirable hardening

| Hardening | Current limitation | Consequence | Urgency |
| --- | --- | --- | --- |
| Directory `fsync` | Temporary content is fsynced, but containing-directory metadata is not | A sudden system/storage failure can weaken replacement durability | High for strong crash-durability claims; not required for bounded local/manual validation |
| Permission preservation | Atomic replacement does not explicitly copy prior target permissions | Replacement metadata can differ on some platforms | Medium before deployment with managed file ACL expectations |
| Revision/ETag or stronger conditional primitive | Concurrency uses exact comparison under a cooperative lease | Nonparticipating writers remain outside the guarantee | Medium for broader multi-process deployment; not required for the current participating local workflow |
| Operational enforcement against bypass writers | Maintenance tools or manual edits may ignore the lease | A nonparticipant can race or overwrite state | High before environments with multiple writer tools |
| Stale lock-file recovery hardening | A crashed participant may leave an exclusive lock file | Later writes can remain blocked pending deliberate recovery | Medium; important operational hardening before unattended use |

These items should be evaluated before broader deployment. They do not change
the exact correctness of Unit 1G within its documented cooperative boundary.

### C. Later maintenance and enhancement

| Item | Classification |
| --- | --- |
| Reusable Sprint 14/15 test fixtures | Maintenance; reduce duplicated construction without changing policy |
| Generic transaction abstraction | Enhancement; introduce only when another concrete store requires it |
| Broader workflow integration beyond the first apply path | Later product integration |
| Additional mutable fields | Later policy work; require explicit mapping, validation, approval, freshness, and repository allowlisting |
| UI/desktop orchestration | Later bounded application unit; no automatic apply |
| Operator identity and permissions | Deployment-dependent security boundary; add only with an explicit authentication model |

## Locked-roadmap relationship

The locked roadmap retains the exact phase title:

```text
Sprint 15 — Controlled Collection Mutation
```

Its atomic persistence requirement is implemented by Unit 1G. Its broader
backup/rollback, durable audit, desktop apply, end-to-end recovery, and
production exit-gate requirements remain open.

The locked roadmap is intentionally unchanged by this closure document. It has
no unit-level completion-marker convention, and changing its open rollout
requirements to complete would be inaccurate. This document records completion
of the bounded controlled-mutation architecture and explicitly preserves those
remaining roadmap gates.

## Authoritative validation

The Sprint 15 closure authoritative regression recorded:

```text
3,570 total
3,548 passed
22 skipped
0 failures
0 errors
```

The focused Sprint 15 group recorded:

```text
250 total
250 passed
0 skipped
0 failures
0 errors
```

The existing `CoinCollection`, shared collection/import lease, baseline,
capture-import execution, and durability group recorded:

```text
75 total
71 passed
4 skipped
0 failures
0 errors
```

The historical melt-value cache-persistence test passed in the closure
regression. No failure or regression was related to Sprint 15.

## Deliberate exclusions

Sprint 15 architecture closure deliberately excludes:

- recoverable backup implementation;
- automatic post-replacement recovery;
- durable mutation audit persistence;
- desktop or GUI apply orchestration;
- OCR invocation;
- operator authentication;
- role or permission enforcement;
- authorization tokens;
- generated execution actors or timestamps;
- revision or ETag generation;
- directory `fsync`;
- explicit target-permission migration;
- enforcement against nonparticipating file writers;
- arbitrary or dynamically expanded mutable fields;
- mutation-result serialization; and
- Sprint 16 provider-quality work.

## Closure statement

**PASS.** Units 1A-1G form a deterministic, immutable, fail-closed chain from
explicit collection-change approval and freshness evidence through exact
command construction and controlled conditional mutation.

The architecture prevents silent partial command execution, enforces exact
expected state under the shared lease, publishes pending fields together, and
returns immutable execution diagnostics. Its concurrency, atomicity, and
verification language is intentionally limited to guarantees the current JSON
store implements.

Sprint 15 is complete as the bounded controlled-mutation architecture.
Production rollout remains gated on backup/recovery, durable mutation audit,
and end-to-end apply orchestration.
