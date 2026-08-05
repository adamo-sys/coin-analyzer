# Sprint 19 - Migration Policy Stabilization

## Purpose

This document freezes the third bounded architecture unit of Sprint 19: migration policy stabilization for the OCR review pipeline.

This unit is intentionally architecture-only. Its job is to define when migration is permitted, what the supported version graph is, and what fail-closed behavior is required. It does not implement migration code, does not add compatibility layers, and does not authorize any automatic upgrade path.

## Scope statement

This unit governs migration policy for persisted DTO families that are already versioned at the envelope boundary.

In scope:

- `OCRReviewSessionEnvelope`
- `OCRReviewSessionReconstruction`
- `ConfirmedFieldObservation`
- `ConfirmedObservationSet`

Out of scope:

- migration implementation
- converters
- historical compatibility layers
- automatic upgrades
- any payload rewrite outside a separately approved migration-implementation unit

## Current evidence from the repository

The currently supported persisted envelope versions observed in the committed source are:

- OCR review session envelope: `1.0`
- confirmed observation boundary: `1`

That means the current migration policy must be stated as a single-version-at-a-time policy unless a later architecture unit explicitly approves a new version and its migration graph.

## Canonical version inventory

### OCR review session envelope

- canonical current version: `1.0`
- supported persisted version: `1.0`
- unknown version behavior: fail closed with `UnsupportedOCRReviewSessionSchemaVersion`
- ownership: persisted storage contract owner is `OCRReviewSessionEnvelope`

### Confirmed observation boundary

- canonical current version: `1`
- supported persisted version: `1`
- unknown version behavior: fail closed with `UnsupportedConfirmedObservationSchemaVersion`
- ownership: confirmed-observation persisted contract owner is the confirmed-observation DTO family

## Migration graph policy

This unit defines the migration graph as a policy boundary only.

Current state:

- `v1` is the only supported persisted OCR review-session version today
- `v1` is the only supported confirmed-observation persisted version today

Approved policy for future work:

- `v1 -> v2` is allowed only when a separately approved architecture unit explicitly defines the contract change and the migration rule
- `v1 -> v3` is not allowed unless the new version graph is explicitly approved in advance
- no chained migrations are permitted without explicit approval
- no silent upgrade is permitted

## Policy rule: when migration is allowed

Migration is allowed only when all of the following are true:

1. the new version is explicitly authorized by a frozen architecture unit
2. the old serialized payload can no longer be interpreted by the current supported implementation without compatibility logic
3. the new version boundary is defined with a clear before/after compatibility promise
4. the migration unit explicitly states the rollback and recoverability requirements
5. the migration unit is reviewed independently from the DTO-versioning unit

## Required migration behavior

Any future migration implementation must satisfy the following architecture rules:

- fail closed on unknown versions
- never silently upgrade persisted data
- never partially migrate
- migration must be atomic
- original payload remains recoverable until migration succeeds
- rollback must be possible if the migration fails after writing durable output
- logging and audit expectations must be explicit
- migration must preserve the authoritative source payload until the new version is durably committed

Unsupported schema versions and malformed payloads are separate failure classes. Migration policy governs only recognized schema versions. Payload corruption, malformed serialization, or invariant violations remain validation failures and must not invoke migration behavior.

## Atomicity requirements

A migration is atomic at the architecture-policy level if:

- either the original persisted payload remains the authoritative durable artifact, or
- the new persisted payload becomes the authoritative durable artifact, with no mixed-state intermediate form

A partially migrated payload is architecture-invalid.

## Recoverability requirements

Migration must preserve recoverability by:

- preserving the original payload until the new payload is fully committed
- retaining the original version marker and content for rollback investigation
- ensuring any failure path leaves the persisted state in one of two explicit states only:
  - unchanged original payload
  - fully migrated new payload

## Logging and audit expectations

Migration work must record:

- source version
- target version
- migration eligibility decision
- migration start time
- migration completion or failure state
- rollback action if any

The migration policy unit does not define the logging format itself, but it does require that the implementation unit produce explicit auditability for migration eligibility decisions and outcomes.

## Rollback requirements

Rollback is required whenever:

- the migration target cannot be committed atomically
- the new payload cannot be validated after write
- the migration path encounters an unsupported intermediate state

Rollback policy must be explicit and fail-safe:

- restore the original payload if the new artifact was not yet fully durable
- preserve the original payload bytes until the new payload is proven valid
- refuse to continue if the system cannot prove that the new payload is fully durable

## Non-goals

This document does not:

- implement migration logic
- define converters or transform helpers
- authorize historical compatibility shims
- permit automatic upgrades
- authorize chained or opportunistic migration paths
- collapse DTO schema ownership into migration policy

## Stop conditions

This unit must stop if any of the following are discovered:

- more than one canonical persisted version is already active in the codebase without an explicit policy boundary
- existing persisted envelopes are already using incompatible schema semantics that require undocumented compatibility logic
- the current code path cannot prove which payload is authoritative during migration
- any migration path would require destructive rewriting of persisted data without an explicit recovery plan

## Validation gate for the architecture unit

This unit is complete when:

- the persisted envelope versions are explicitly listed with their owning contract
- the current supported version graph is stated as `v1` only unless otherwise approved
- the fail-closed rule is explicit
- the atomicity, recoverability, rollback, and audit expectations are explicitly defined
- the document explicitly excludes implementation and automatic upgrade behavior

## Freeze note

This document freezes only the migration-policy unit for Sprint 19.

It does not authorize any migration implementation, any converter creation, any automatic upgrade path, or any persistent-data rewrite. It only establishes the policy contract that later migration work must satisfy.
