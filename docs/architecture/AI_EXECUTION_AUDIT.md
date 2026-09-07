# AI execution audit boundary

Issue #201 adds the first contract-only slice of an AI Execution Audit Trail / AI Decision Provenance layer.

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
              audit record
              (observation only)
```

Nothing in `ai_execution_audit.py` writes files, calls a provider, retries work,
repairs output, mutates a collection, or authorizes persistence. The audit
record must never become a second path into authoritative collection state.

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
with an exact fixed key set and no arbitrary metadata channel. This slice has
no deserializer and no storage API.

## Privacy exclusions

The contract intentionally has no fields for credentials, authorization
headers, raw prompts/system prompts, image bytes/base64 payloads, arbitrary
exception text, tracebacks, subprocess output, unrestricted filesystem paths,
full collection contents, hidden model reasoning, commands, provider clients,
or environment mappings.

Evidence references remain bounded references from the existing request; they
are not expanded into underlying image/content bytes.

## Disposition semantics

Human disposition is one of `accepted`, `rejected`, `deferred`, `cancelled`,
or `not_reached`.

Persistence disposition is one of `committed`, `rejected_stale`,
`blocked_load_failure`, `failed`, or `not_attempted`.

A committed persistence outcome requires human acceptance. Any non-accepted
human disposition requires `not_attempted`, preventing an audit record from
claiming persistence after rejection, deferral, cancellation, or an
unreached review.

## Explicit non-goals for #201

No JSONL/file storage, append API, GUI lifecycle hook, analytics dashboard,
provider/model change, network access, collection mutation, autonomous retry,
agent loop, DeepSeek Harness dependency, or visual-context compression is
introduced by this slice.

Follow-on storage and lifecycle integration require separate review and must
preserve the existing load-failure, stale-save, cancellation, privacy, and
human-authority boundaries.
