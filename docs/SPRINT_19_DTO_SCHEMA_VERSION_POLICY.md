# Sprint 19 - DTO Schema-Version Policy Stabilization

## Purpose

This document freezes the second bounded architecture unit of Sprint 19: DTO schema-version policy stabilization for the OCR review pipeline.

This unit is intentionally architecture-only. Its job is to classify the relevant DTO families before any serialized payload shape change is authorized. It does not introduce migrations, does not change durable data, and does not permit schema-version rollout work yet.

The unit is bounded to policy and ownership, not implementation.

## Scope statement

This document governs the DTO inventory for OCR, review, persistence, and cross-boundary confirmed-observation handoff contracts that are relevant to Sprint 19.

In scope:

- `OCRObservation`
- `OCRFieldCandidate`
- `OCRMetadataReport`
- `OCRFieldReview`
- `OCRReportReview`
- `OCRReviewReconciliation`
- `OCRReviewSessionEnvelope`
- `OCRStoredConflictResolution`
- `OCRReviewSessionReconstruction`
- confirmed-observation DTOs only where they form a cross-boundary dependency

Out of scope:

- durable-data migration execution
- historical-version compatibility implementation
- any payload-shape rewrite
- any change to persisted bytes outside a separately approved schema change unit

## Architectural rule

Sprint 19 Unit 2 must classify each DTO by policy boundary before code changes can be authorized.

A DTO is treated as versioned only when the current contract explicitly carries a top-level schema version field and rejects unsupported versions fail-closed.

Nested DTOs that are serialized only as part of an envelope remain policy-owned by the envelope unless they themselves carry an explicit independent version field.

## Contract kind taxonomy

The architecture must distinguish compatibility promises by contract kind so future review does not confuse storage semantics with runtime reconstruction semantics.

- persisted storage contract: a durable payload stored by a repository or other durable boundary; compatibility is governed by the durable envelope version.
- external wire contract: a payload crossing process or service boundaries and expected to remain compatible across independent implementations.
- in-memory reconstruction contract: a runtime object used to rebuild a workflow or report from persisted data; compatibility is internal to the implementation boundary and is not itself a schema-version boundary.
- runtime service contract: a transient service result used only within a process or call chain; versioning is not implied.

## Required inventory questions

For each DTO family, the architecture must state:

- persisted or transient
- exact ownership boundary
- explicit version today or not
- field and supported value contract
- serializer owner
- deserializer owner
- unsupported-version behavior
- nested under another envelope or top-level contract
- compatibility promise kind: persisted storage contract, external wire contract, in-memory reconstruction contract, or runtime service contract
- Sprint 19 treatment: version, remain unversioned, or defer

## DTO inventory and policy classification

### 1. `OCRObservation`

- Persisted or transient: transient in-memory DTO used as part of a report.
- Exact boundary: advisory OCR observation data within one `OCRMetadataReport` execution.
- Explicit version today: no.
- Field and supported value contract: source coin, image role, artifact key, provider, raw text, confidence score.
- Serializer owner: `OCRObservation.to_dict()`.
- Deserializer owner: report-level reconstruction and persistence boundary code, not a standalone versioned contract.
- Unsupported-version behavior: not applicable; there is no schema-version field.
- Nested under another envelope: yes, nested under `OCRMetadataReport`.
- Compatibility promise kind: in-memory reconstruction contract nested under the parent report payload.
- Sprint 19 treatment: remain unversioned within the parent report contract.

### 2. `OCRFieldCandidate`

- Persisted or transient: transient in-memory OCR candidate DTO.
- Exact boundary: one advisory OCR field suggestion for one source coin and image artifact.
- Explicit version today: no.
- Field and supported value contract: source coin, image role, artifact key, provider, field name, raw text, normalized value, confidence score, evidence, review status.
- Serializer owner: `OCRFieldCandidate.to_dict()`.
- Deserializer owner: persistence/reconstruction code that rebuilds `OCRMetadataReport` content from stored nested report payloads.
- Unsupported-version behavior: not applicable.
- Nested under another envelope: yes, nested under `OCRMetadataReport`.
- Compatibility promise kind: in-memory reconstruction contract nested under the parent report payload.
- Sprint 19 treatment: remain unversioned within the parent report contract.

### 3. `OCRMetadataReport`

- Persisted or transient: transient in-memory OCR report DTO.
- Exact boundary: one report-level OCR execution result containing observations, candidates, conflicts, and review status.
- Explicit version today: no.
- Field and supported value contract: provider availability, observations, candidates, conflicts, review status.
- Serializer owner: `OCRMetadataReport.to_dict()`.
- Deserializer owner: persistence envelope reconstruction code that bodies out the stored report shape.
- Unsupported-version behavior: not applicable.
- Nested under another envelope: yes, nested under `OCRReviewSessionEnvelope` in the persisted review-session path.
- Compatibility promise kind: in-memory reconstruction contract nested under a persisted storage contract.
- Sprint 19 treatment: remain unversioned unless a separate envelope-level schema change explicitly introduces one.

### 4. `OCRFieldReview`

- Persisted or transient: transient in-memory review decision DTO.
- Exact boundary: one human review decision for one OCR field target.
- Explicit version today: no.
- Field and supported value contract: source coin, image role, artifact key, provider, field name, original value, decision, reviewed value, reason.
- Serializer owner: `OCRFieldReview.to_dict()`.
- Deserializer owner: persistence envelope reconstruction and repository serialization code.
- Unsupported-version behavior: not applicable.
- Nested under another envelope: yes, the `field_reviews` array in `OCRReviewSessionEnvelope`.
- Compatibility promise kind: in-memory reconstruction contract nested under a persisted storage contract.
- Sprint 19 treatment: remain unversioned within the parent session envelope contract.

### 5. `OCRReportReview`

- Persisted or transient: transient in-memory aggregate review DTO.
- Exact boundary: reviewer identity plus a tuple of field reviews for one review session.
- Explicit version today: no.
- Field and supported value contract: reviewer identity and a tuple of `OCRFieldReview` values.
- Serializer owner: `OCRReportReview.to_dict()`.
- Deserializer owner: session persistence and reconstruction code.
- Unsupported-version behavior: not applicable.
- Nested under another envelope: yes, as the in-memory aggregate that gets serialized into the persisted session envelope.
- Compatibility promise kind: in-memory reconstruction contract nested under a persisted storage contract.
- Sprint 19 treatment: remain unversioned within the parent envelope contract.

### 6. `OCRReviewReconciliation`

- Persisted or transient: transient service result DTO.
- Exact boundary: post-review reconciliation result for accepted, rejected, deferred, and missing candidate targets.
- Explicit version today: no.
- Field and supported value contract: reviewer, mode, accepted fields, rejected/deferred/missing candidate keys, conflict flag, summary.
- Serializer owner: `OCRReviewReconciliation.to_dict()`.
- Deserializer owner: none identified as a standalone persistent wire contract; this remains a transient result object.
- Unsupported-version behavior: not applicable.
- Nested under another envelope: not currently. It is a runtime result object and not a persisted envelope DTO.
- Compatibility promise kind: runtime service contract.
- Sprint 19 treatment: remain unversioned and transient; do not introduce persistence-version semantics here.

### 7. `OCRReviewSessionEnvelope`

- Persisted or transient: persisted envelope DTO.
- Exact boundary: the durable OCR review session payload written and read by the repository.
- Explicit version today: yes, `CURRENT_OCR_REVIEW_SESSION_SCHEMA_VERSION = "1.0"`.
- Field and supported value contract: schema version, session id, source fingerprint, lifecycle state, review mode, reviewer id, nested source report, field reviews, conflict resolutions.
- Serializer owner: `OCRReviewSessionEnvelope.to_dict()`.
- Deserializer owner: `OCRReviewSessionEnvelope.from_dict()`.
- Unsupported-version behavior: fail-closed with `UnsupportedOCRReviewSessionSchemaVersion`.
- Nested under another envelope: top-level persisted envelope.
- Compatibility promise kind: persisted storage contract.
- Sprint 19 treatment: this unit may define policy ownership for the envelope boundary but must not authorize payload migration logic.

### 8. `OCRStoredConflictResolution`

- Persisted or transient: persisted nested DTO in the review-session envelope.
- Exact boundary: one explicit conflict decision stored as part of the review-session envelope.
- Explicit version today: no.
- Field and supported value contract: source coin id, field name, decision, value.
- Serializer owner: `OCRStoredConflictResolution.to_dict()`.
- Deserializer owner: `OCRReviewSessionEnvelope.from_dict()`.
- Unsupported-version behavior: not applicable; no separate schema version is carried by the nested stored resolution.
- Nested under another envelope: yes, nested under `OCRReviewSessionEnvelope`.
- Compatibility promise kind: persisted storage contract nested under the parent envelope version.
- Sprint 19 treatment: remain unversioned under the session envelope version.

### 9. `OCRReviewSessionReconstruction`

- Persisted or transient: transient reconstruction DTO used to rehydrate the review workflow from a persisted envelope.
- Exact boundary: combines `OCRMetadataReport`, `OCRReportReview`, conflict resolution requests, and mode into one immutable input object.
- Explicit version today: no.
- Field and supported value contract: source report, review, conflict resolution requests, mode.
- Serializer owner: `to_session_request()` and nested `to_dict()` methods on the request/result DTOs; this type itself is not versioned.
- Deserializer owner: repository and orchestration code that reconstructs session input from persisted envelope data.
- Unsupported-version behavior: not applicable.
- Nested under another envelope: no separate persisted envelope; it is a runtime reconstruction view.
- Compatibility promise kind: in-memory reconstruction contract.
- Sprint 19 treatment: remain unversioned and transient.

### 10. Confirmed-observation DTOs

The confirmed-observation boundary already carries explicit versioning and therefore must remain a separate ownership domain in this sprint.

Relevant DTOs:

- `ConfirmedFieldObservation`
- `ConfirmedObservationSet`
- `ConfirmedObservationProvenance`

Policy classification:

- `ConfirmedFieldObservation`: persisted cross-boundary confirmed-observation DTO; explicit version today (`schema_version` = `"1"`); serializer owner `ConfirmedFieldObservation.to_dict()`; deserializer owner `ConfirmedFieldObservation.from_dict()`; unsupported-version behavior is fail-closed via `UnsupportedConfirmedObservationSchemaVersion`; nested under a broader confirmation set only when code uses the set boundary; Sprint 19 treatment: keep version policy at the confirmed-observation envelope boundary, not as a change to OCR field identity.
- `ConfirmedObservationSet`: persisted cross-boundary confirmed-observation aggregate; explicit version today (`schema_version` = `"1"`); serializer owner `ConfirmedObservationSet.to_dict()`; deserializer owner `ConfirmedObservationSet.from_dict()`; unsupported-version behavior is fail-closed; nested under any parent contract only if a future envelope introduces one; Sprint 19 treatment: remain explicitly versioned and separate from the OCR field identity contract.
- `ConfirmedObservationProvenance`: nested provenance lineage inside a confirmed observation; no separate version; serializer owner `to_dict()`; deserializer owner `from_dict()`; unsupported-version behavior not applicable; nested under confirmed observation objects; Sprint 19 treatment: remain unversioned while the parent confirmed-observation schema remains versioned.

## Ownership principle

The unit must keep the following ownership boundaries explicit:

1. OCR field identity is an in-memory canonical contract and is not a serialized payload contract.
2. The persisted OCR review session envelope owns the version boundary for review-session persistence.
3. Confirmed-observation DTOs own their own version boundary and remain separate from the OCR review identity contract.
4. Nested report/review DTOs remain structurally fixed and do not gain independent version fields unless the owning envelope explicitly changes its version policy.
5. The version policy applies to the contract owner, not to every nested object that happens to be serialized inside it.

## Version bump policy

A schema version for an envelope changes only when a serialized payload written by a previously supported implementation can no longer be interpreted without compatibility logic.

In practice, that means:

- a new envelope field that preserves backwards parsing does not require a version bump by itself
- a field removal, structural reinterpretation, or otherwise incompatible serialized-shape change requires a version bump
- a nested DTO may remain unversioned under the parent envelope version unless the nested DTO itself is introduced as an independently versioned contract
- compatibility logic for a historical format is a migration-topic concern and is outside this unit

## Policy decision for Unit 2

The Unit 2 architecture decision is:

- Keep schema-version policy at the owning envelope boundary.
- Do not add a version field to nested OCR review/report DTOs merely because they are serialized.
- Do not authorize payload-shape changes or durable-data migration in this unit.
- Fail closed on unsupported version strings at the envelope owner.
- Treat provenance and identity as separate contracts, even when they share the same source field slots.

## Stop conditions

This unit must stop if the inventory shows any of the following:

- existing schemas with incompatible version semantics
- persisted nested DTOs whose byte shape is externally relied upon and would be broken by a blanket version field introduction
- a requirement to support historical versions without evidence
- any need to modify durable data
- ambiguity over envelope ownership versus nested DTO ownership
- any attempt to use OCR field identity stabilization as a reason to rewrite persisted payload shapes

## Non-goals

This document does not:

- define migrations
- alter any existing serialized byte representation
- introduce new persistence-format compatibility logic
- unify provenance identities with OCR field identities
- permit durable-data repair or rewrite

## Validation gate for the architecture unit

The architecture-only deliverable is complete when:

- every in-scope DTO is classified as persisted or transient
- every versioned DTO is identified by its owning serializer and deserializer
- every nested DTO is identified as envelope-owned or independently versioned
- the unit explicitly forbids payload-shape changes and migration work in this document
- the supported version behavior is documented as fail-closed for known envelope owners

## Freeze note

This document freezes only the DTO schema-version policy stabilization unit for Sprint 19.

It does not authorize any migrations, any durable-data rewrite, or any payload-shape change. It merely establishes the inventory and policy ownership needed before the next approved implementation unit can make a serialized-format decision.
