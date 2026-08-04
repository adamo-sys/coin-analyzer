# Sprint 19 - Schema Stabilization

## Purpose

This document defines the first bounded architecture unit of Sprint 19: canonical OCR field identity stabilization.

The unit does not change runtime behavior, alter persisted schema semantics, or introduce new review policy. It standardizes one shared OCR field identity contract for the OCR review pipeline and defines a controlled compatibility migration path.

The scope is deliberately narrower than a repository-wide identity unification effort: this document freezes only the OCR field identity stabilization unit. It does not claim that confirmed-observation provenance identities, confirmed-observation boundary contracts, or downstream provenance models are the same contract.

## Problem statement

The OCR review pipeline currently carries the same logical field identity through multiple layers using several overlapping representations:

- candidate identity
- review identity
- persistence identity
- reconciliation and projection identity

The current shape is effectively a six-part tuple:

```python
(
    source_coin_id,
    image_role,
    artifact_key,
    provider_id,
    field_name,
    value,
)
```

In practice, the codebase reconstructs that shape repeatedly in:

- `capture_import/workflow_ocr_review_service.py`
- `capture_import/workflow_ocr_review_presenter.py`
- `capture_import/workflow_ocr_review_models.py`
- `capture_import/workflow_confirmed_observation_mapper.py`
- `capture_import/desktop_ocr_candidate_review.py`

This creates three immediate risks:

1. duplicated identity construction logic
2. copy-and-paste drift between layers
3. fragile maintenance when a field identity must be changed or extended

The sprint goal is to centralize that contract into one canonical identity definition while preserving all existing consumers through a compatibility adapter phase.

## Current duplicated identity representations

### Candidate identity

Candidate identity is currently derived from the normalized OCR field candidate model:

- `source_coin_id`
- `image_role`
- `artifact_key`
- `provider_id`
- `field_name`
- `normalized_value`

This shape appears in the candidate review and reconciliation path where candidate records are deduplicated, matched, and projected into review state.

### Review identity

Humans review a candidate by matching the same OCR field target against the source candidate. The review path therefore reuses the same six-part logical identity, but with the human-review value semantics (`original_value`) instead of the normalized candidate value.

The review identity is currently rebuilt manually in the review service and presenter layers, which means the candidate identity and review identity are structurally identical but encoded in multiple places.

### Persistence identity

The stored OCR review-session envelope records field reviews and conflict resolutions with the same semantic target, but persistence contracts currently validate and rehydrate those values separately from the in-memory domain identity. This is a packaging boundary problem rather than a new domain concept: the persisted schema already carries the same source field identity, but it does not currently share the same canonical contract as the in-memory workflow.

### Observable duplication pattern

Across the above layers, the same identity is:

- manually recreated as a tuple
- used as a dict key for deduplication and lookups
- copied into helper functions with slightly different naming
- repeated in presenter, service, and mapper code

No new behavior is introduced by this stabilization. The only change is to give the field identity one canonical definition and keep legacy tuple callers working while the codebase migrates.

## Canonical OCR field identity contract

The Sprint 19 contract is a shared OCR field identity for the OCR review pipeline, not a repository-wide identity merge.

```python
class OCRFieldIdentity(NamedTuple):
    source_coin_id: str
    image_role: str
    artifact_key: str
    provider_id: str
    field_name: str
    value: str
```

The identity is immutable by construction and must remain immutable throughout the migration period.

### Rationale

This representation is intentionally:

- tuple-compatible for existing hash/dict/set semantics
- stable across candidate, review, and persistence boundaries within the OCR review pipeline
- explicit about the semantic role of the final value slot
- safe for a phased migration because legacy callers can continue using the tuple behavior while new code gains named-field access

### Explicit invariant

Sprint 19 standardizes the OCR field identity contract only.

It does not unify confirmed-observation provenance identities, nor does it claim that `OCRFinalProjectedField` provenance, confirmed-observation provenance, or persistence envelopes are the same identity object. Those layers retain separate responsibilities and validation contracts.

### Canonical usage rule

All OCR review pipeline consumers that identify one field target must obtain that identity through the canonical contract instead of rebuilding tuples inline.

The source of truth is the OCR model layer, where the canonical identity is exposed on the domain objects that already own the relevant source fields.

### Serialization boundary

`OCRFieldIdentity` is an in-memory identity contract only. It is not added directly to existing persisted dictionaries or JSON envelopes.

Existing `to_dict()` keys, values, ordering, and canonical persisted bytes remain unchanged. The first implementation unit must not introduce a new serialized representation for the identity object itself.

### Validation ownership

The safest first-unit rule is:

- domain objects remain responsible for validation
- `identity_key` is produced only after or from already-valid domain fields
- `OCRFieldIdentity` performs no new normalization or silent repair
- invalid source objects continue failing at their current boundaries

This avoids introducing a second validation regime with different limits from `OCRFieldCandidate` and `OCRFieldReview`.

### Ordering compatibility

Field order is contractually significant and remains:

`source_coin_id`, `image_role`, `artifact_key`, `provider_id`, `field_name`, `value`.

No normalization, lowercasing, trimming, or reordering may occur during construction. The canonical ordering preserves the existing tuple equality, hashing, ordering, and indexing behavior expected by tuple-keyed dictionaries and sets.

## Migration plan

### Compatibility table

| Legacy surface | Migration intent | Compatibility strategy |
| --- | --- | --- |
| `CandidateKey` alias | retain current tuple-style lookup behavior | alias to the canonical OCR field identity contract |
| `_candidate_key()` adapter | centralize candidate identity construction | return the canonical identity object |
| `_review_key()` adapter | centralize human review identity construction | return the canonical identity object |
| `OCRFieldReview.identity_key` | expose the shared contract from the review model | return the canonical identity object |
| tuple dictionaries / set membership | keep existing dictionary and hash behavior intact | preserve tuple compatibility of the canonical identity |

### Phase 1 - Introduce canonical identity

Introduce one shared immutable identity type in the OCR domain model package and expose it from the candidate and review contracts. At this stage:

- no behavior changes
- no schema changes
- no persistence format changes
- only a single shared contract is added

### Phase 2 - Convert consumers

Change the existing workflow consumers to read from the canonical identity rather than re-constructing the tuple locally.

Target consumer layers:

- presentation
- reconciliation service
- confirmation mapping
- desktop candidate-review navigation and review-state bookkeeping

The migration should preserve the existing hash and equality behavior of the tuple-based identity while updating callers to the shared type.

The migration window concludes only after repository-wide search confirms all production callers use the canonical identity and the compatibility cleanup unit has been independently reviewed.

### Phase 3 - Remove compatibility helpers

Private helpers may be removed only after repository-wide search confirms that no remaining consumers depend on them.

Public aliases or properties remain for the full Sprint 19 migration window. Removal is a separately reviewed cleanup unit, not part of the initial identity introduction. This preserves a defined compatibility duration instead of making the migration phase ambiguous.

## Non-goals

This sprint does not:

- add a new persistence schema version
- change OCR field semantics or allowed field vocabulary
- change review decisions or reconciliation rules
- change provider selection, candidate normalization, or downstream confirmed-metadata contracts
- create new persistence migrations or data repair routines
- redesign the review UI workflow

The unit is strictly about identity contract stabilization.

## Validation plan

Validation must remain narrow and behavior-preserving.

### Focused regression coverage

The implementation should preserve the current OCR review and persistence test baseline by validating the following areas:

1. OCR review model identity and DTO behavior
2. reconciliation service behavior for accepted, rejected, deferred, and missing review targets
3. OCR review presentation model projection and candidate/review mapping
4. OCR review persistence envelope and local repository behavior
5. confirmed-observation mapping compatibility at the cross-boundary handoff, while keeping provenance identities separate from the OCR field identity contract

### Acceptance criteria

The stabilization is complete when:

- all OCR review identity consumers share one canonical contract
- no behavioral change is observable in the focused OCR review suites
- legacy tuple-compatible callers remain valid for the migration window
- the canonical identity remains deterministic, immutable, and hashable

## Unit 1 Implementation Checklist

- [ ] Add `OCRFieldIdentity`
- [ ] Add candidate identity adapter
- [ ] Add review identity adapter
- [ ] Replace `CandidateKey`
- [ ] Preserve tuple compatibility
- [ ] No serialization changes
- [ ] No persistence changes
- [ ] No provenance changes
- [ ] Focused regression passes

### Implementation stop conditions

The first implementation unit must stop if any of the following occur:

- any serialized dictionary or byte output changes
- any consumer expects `type(identity) is tuple`
- candidate and review identity fields are found to have unequal normalization semantics
- public import paths would change
- a provenance identity must be altered
- focused tests reveal callback, navigation, ordering, or reconstruction changes

### Validation gate

The implementation unit should validate the identity stabilization with the following focused commands:

```bash
python -m unittest \
  tests.test_workflow_ocr_review_models \
  tests.test_workflow_ocr_review_service \
  tests.test_workflow_ocr_review_persistence_models \
  tests.test_workflow_confirmed_observation_mapper
```

```bash
python -m unittest \
  tests.test_workflow_ocr_review_presenter \
  tests.test_desktop_ocr_candidate_review \
  tests.test_workflow_ocr_review_local_repository
```

```bash
python -m unittest \
  tests.test_workflow_ocr_consolidation \
  tests.test_workflow_ocr_final_projection \
  tests.test_workflow_ocr_conflict_resolution
```

The final Sprint 19 closure still requires the authoritative full regression, but not necessarily during this first implementation unit.

## Unit boundaries and remaining Sprint 19 work

This document freezes only the OCR field identity stabilization unit within Sprint 19.

The following roadmap items remain outside this frozen unit and require separate architecture approval before implementation:

- DTO schema-version policy
- migration graph and migration execution policy
- reusable test builders
- oversized-test module splits
- formal package-boundary enforcement
- Sprint 19 closure audit and progress-document correction

Completion of this identity unit does not complete Sprint 19.

### Atomic unit and rollback rule

This implementation unit is intentionally limited to:

- one production-and-focused-test change unit
- no persistence rewrites
- no durable-data migration
- rollback by normal Git revert because no external data changes occur
- patch reuse only after comparing it against the approved architecture

## Freeze note

This document is the frozen architecture note for the OCR field identity stabilization unit of Sprint 19.

Any implementation must preserve current tuple equality, hashing, ordering, serialized dictionary shapes, canonical persisted bytes, public behavior, callback behavior, and provenance boundaries.

No other Sprint 19 roadmap item is authorized by this document.
