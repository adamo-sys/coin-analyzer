# AI execution audit boundary

Issue #201 introduced the contract-only foundation of an AI Execution Audit Trail / AI Decision Provenance layer. The follow-on storage slice adds separate bounded JSONL persistence without changing collection authority. Issue #207 adds a narrow downstream finalization seam for completed identification-specialist executions.

## Authority boundary

The audit record is downstream and observational only:

```text
AI execution
    -> existing strict request/result contracts
    -> deterministic verification/evaluation
    -> human authority
    -> existing persistence guards

                    |
                    v
       audit finalization seam
                    |
                    v
              audit record
                    |
                    v
          separate audit store
          (observation only)
```

`ai_execution_audit.py`, `ai_execution_audit_store.py`, and
`identification_audit_finalization.py` cannot authorize or perform collection
mutation. The audit path must remain separate from `collection.json` and must
never become a second path into authoritative state.

## Contract

`AIExecutionAuditRecord` is frozen and slotted. Schema version 1 records only
bounded workflow provenance and already-established outcomes:

- execution/workflow/executor IDs;
- one explicit UTC occurrence timestamp;
- existing case, evidence, and caller-authorized candidate IDs;
- selected candidate or explicit abstention;
- existing verifier verdict/reason codes;
- existing evaluation classification/reason codes;
- explicit human disposition;
- explicit persistence disposition.

`build_ai_execution_audit_record()` derives these values from the existing
identification request and execution report. It does not infer new identity,
truth, confidence, or authority. The execution result in the comparison must
match the actual executed result.

`serialize_ai_execution_audit_record()` emits deterministic schema-v1 JSON
with an exact fixed key set and no arbitrary metadata channel.

## Append-only store

`AIExecutionAuditStore` persists one canonical JSON object per line. Its public
surface supports only `read_all()` and `append()`; it exposes no update,
delete, truncate, or clear operation for prior records.

Before every append, the store validates the new record, acquires a separate
cooperative filesystem lease, strictly validates all existing JSONL history,
rejects malformed or duplicate state, enforces bounded record/byte limits, and
publishes the prospective complete bytes through a flushed/fsynced sibling
temporary file plus atomic replacement while the lease remains held.

Whole-file replacement is an implementation mechanism for atomic publication;
the API remains append-only because callers cannot alter or remove prior
records. Existing bytes are validated and preserved exactly as the prefix of a
successful append.

The audit lease uses the repository's existing `PackageImportLock` primitive on
a distinct audit lock path. This reuses the established exclusive-create plus
OS-advisory-lock behavior without sharing collection mutation authority.

## Identification lifecycle finalization

`finalize_identification_execution_audit()` is intentionally narrower than an
execution coordinator. It accepts an already-completed
`IdentificationSpecialistExecutionReport`, its original request, explicit human
and persistence dispositions, caller-owned execution/workflow IDs and UTC time,
and an `AIExecutionAuditStore`.

The function builds the existing audit record and appends it exactly once. It
does **not** call the specialist executor or model transport, infer a human
choice, infer a persistence result, write collection state, retry an operation,
or roll back prior collection persistence if the audit append fails. Audit
failure remains an audit failure; collection authority remains elsewhere.

This ordering is deliberate: the persistence disposition describes an outcome
that has already happened. Audit finalization observes that outcome after the
fact rather than becoming a prerequisite that can grant or revoke mutation
authority.

## Bounded failure behavior

The store is fail-closed. Existing corruption, duplicate execution IDs, lock
contention, unsupported schema, or a full store blocks the append rather than
rewriting or repairing history. A failed append must leave pre-existing audit
bytes untouched.

The current bounds are 10,000 records and 16 MiB. Rotation, archival, pruning,
and retention policy are intentionally not part of this slice because each
would introduce deletion or replacement semantics that need separate design
review.

## Privacy exclusions

The contract intentionally has no fields for credentials, authorization
headers, raw prompts/system prompts, image bytes/base64 payloads, arbitrary
exception text, tracebacks, subprocess output, unrestricted filesystem paths,
full collection contents, hidden model reasoning, commands, provider clients,
or environment mappings.

Evidence references remain bounded references from the existing request; they
are not expanded into underlying image/content bytes. The storage layer
introduces no metadata escape hatch: strict parsing requires exactly the
schema-v1 key set.

## Disposition semantics

Human disposition is one of `accepted`, `rejected`, `deferred`, `cancelled`,
or `not_reached`.

Persistence disposition is one of `committed`, `rejected_stale`,
`blocked_load_failure`, `failed`, or `not_attempted`.

A committed persistence outcome requires human acceptance. Any non-accepted
human disposition requires `not_attempted`, preventing an audit record from
claiming persistence after rejection, deferral, cancellation, or an unreached
review.

## Live visual workflow boundary

The current desktop visual-identification path uses `VisualIdentityRequest` and
`VisualIdentityReport`. It produces ranked composite identity candidates from
image evidence. It does **not** have the specialist contract's caller-owned
candidate-ID universe or an authoritative `EvaluationCase` during ordinary live
use.

Consequently, the live visual path must not be forced into schema v1 by
inventing candidate IDs, authorized-candidate sets, or evaluation truth. Doing
so would make the audit log look precise while recording semantics that never
actually existed.

A separate reviewed visual-audit adapter or compatible schema is required before
GUI lifecycle emission is added. That follow-on must preserve cancellation,
upload disclosure, stale-save/load-failure protection, human review authority,
and the existing visual provider's bounded evidence rules.

## Still out of scope

This slice does not add GUI lifecycle hooks, visual-report coercion, automatic
visual audit emission, analytics dashboards, provider/model changes, network
access, collection mutation, autonomous retry, agent loops, DeepSeek Harness,
or visual-context compression.
