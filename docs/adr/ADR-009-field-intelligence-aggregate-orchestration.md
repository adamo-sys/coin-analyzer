# ADR-009: Field-Intelligence Aggregate Orchestration

- Status: Accepted (implemented and verified)
- Date: 2026-08-01
- Scope: Separately named post-Sprint-17 architecture amendment

## Context

Sprint 17 closed the immutable field-intelligence contracts and five independent
leaf evaluators. The closure in `docs/progress.md` explicitly deferred aggregate
orchestration pending a separate architecture design and approval. The completed
leaf surface is:

1. `assess_coin_specific_year` with a caller-owned `CoinYearRuleCatalog`;
2. `assess_denomination_country_compatibility` with a caller-owned
   `DenominationCountryRuleCatalog`;
3. `assess_monarch_year_compatibility` with no caller-owned catalog;
4. `assess_mintmark` with a caller-owned `MintmarkRuleCatalog`; and
5. `assess_certification_context` with a caller-owned
   `CertificationContextRuleCatalog` and optional
   `CertificationEvaluationContext`.

Each leaf accepts the exact `ConfirmedObservationSet`, validates its own inputs,
reads submitted values without normalization, returns at most one transient
`FieldIntelligenceFinding`, and returns `None` when all of its relevant source
fields are absent. The existing
`ConfirmedObservationFieldIntelligenceAssessment` retains the exact source and
finding objects, rejects duplicate rule IDs or source-field misalignment, and
requires findings in lexical `rule_id` order.

Callers currently have no single pure function that invokes all five leaves and
constructs that assessment. Adding such a function is a lasting cross-feature
boundary, so this ADR defines it before production implementation.

This amendment is not Sprint 18 and does not change the locked roadmap. Sprint 18
remains "Image and OCR UX refinement." This work is recorded only as the
separately named post-Sprint-17 aggregate-orchestration unit authorized by the
Sprint 17 closure.

## Decision

Add one pure aggregate orchestration function in a new module. The orchestrator
will compose the five existing leaf functions without changing their modules,
signatures, result contracts, validation behavior, or direct-call availability.

### 1. Owning module

The owning production module will be:

`capture_import/workflow_confirmed_observation_field_intelligence_orchestrator.py`

The module will own orchestration only. It will contain no field policy, catalog
facts, matching logic, normalization, persistence, readiness logic, collection
mapping, mutation, caching, discovery, registry, or runtime composition.

The module-level public API will contain exactly the aggregate callable. It will
not be re-exported from `capture_import.__init__`; the field-intelligence modules
currently use explicit module imports, and broadening the package-root API is not
needed for this unit.

### 2. Public callable and exact signature

```python
def assess_confirmed_observation_field_intelligence(
    source: ConfirmedObservationSet,
    coin_year_catalog: CoinYearRuleCatalog,
    denomination_country_catalog: DenominationCountryRuleCatalog,
    mintmark_catalog: MintmarkRuleCatalog,
    certification_context_catalog: CertificationContextRuleCatalog,
    certification_evaluation_context: CertificationEvaluationContext | None = None,
) -> ConfirmedObservationFieldIntelligenceAssessment:
    ...
```

`__all__` will be exactly:

```python
["assess_confirmed_observation_field_intelligence"]
```

No aggregate class, mutable builder, input DTO, output wrapper, registry, callback,
or new public error hierarchy is introduced.

### 3. Catalog and context input contract

The four catalog arguments are mandatory exact caller-owned catalog objects:

- `CoinYearRuleCatalog`;
- `DenominationCountryRuleCatalog`;
- `MintmarkRuleCatalog`; and
- `CertificationContextRuleCatalog`.

Empty catalogs are valid and preserve each leaf's existing conservative
no-coverage behavior. The orchestrator does not supply defaults, clone catalogs,
merge catalogs, alter their order, infer missing rules, or retain them in the
result.

`certification_evaluation_context` is the exact caller-owned
`CertificationEvaluationContext` or `None`. It is passed unchanged to
`assess_certification_context`. It is advisory context, not confirmed evidence,
and is never added to the source or result.

The monarch-year leaf has no catalog or additional context. The orchestrator must
not invent one.

### 4. Evaluator invocation and omission rules

For every request that reaches leaf invocation, the orchestrator calls each leaf
exactly once in this fixed implementation sequence:

1. `assess_coin_specific_year(source, coin_year_catalog)`;
2. `assess_denomination_country_compatibility(source, denomination_country_catalog)`;
3. `assess_monarch_year_compatibility(source)`;
4. `assess_mintmark(source, mintmark_catalog)`; and
5. `assess_certification_context(source, certification_context_catalog,
   certification_evaluation_context)`.

All five leaves are invoked even when the source lacks a leaf's relevant fields.
The leaf remains the sole owner of relevance, missing-context, matching, and
coverage policy. The orchestrator must not inspect source field values, predict a
leaf outcome, or skip a leaf through duplicated applicability logic.

After all calls succeed, the orchestrator discards results that are exactly
`None`. It retains every returned `FieldIntelligenceFinding` object by identity.
It never changes, combines, suppresses, reconstructs, or reclassifies a finding.
Every non-`None` result must be an exact `FieldIntelligenceFinding`; any other
result raises the existing `InvalidFieldIntelligenceContextError`. Each retained
finding is validated through its existing public `validate()` contract before
ordering. This output-boundary check prevents incidental attribute failures while
adding no aggregate-specific error vocabulary.

An all-`None` result is valid and produces an assessment with `findings=()`. Under
the existing assessment contract, that means no field-intelligence rules reported
a finding; it does not mean valid, ready, or approved.

### 5. Deterministic ordering

Leaf invocation order and assessment order are separate concerns. Invocation uses
the fixed sequence above. Non-`None` findings are then ordered by ascending lexical
`finding.rule_id` before assessment construction:

```python
findings = tuple(sorted(non_none_findings, key=lambda finding: finding.rule_id))
```

Sorting creates only the aggregate tuple; it does not reconstruct findings or
modify leaf catalogs. ASCII-bounded rule IDs make ordering locale-independent.
There is no status, severity, evaluator, diagnostic, source-field, catalog, or
insertion-order precedence.

If two leaves return the same `rule_id`, the orchestrator must not overwrite,
deduplicate, or choose a winner. Construction of
`ConfirmedObservationFieldIntelligenceAssessment` fails closed with the existing
`DuplicateFieldIntelligenceFindingError`.

### 6. Validation and failure behavior

The aggregate accepts a validated `ConfirmedObservationSet`. It does not weaken or
replace validation. Each existing leaf continues to validate the source and its
own catalog or context through its current public boundary before evaluating.
The orchestrator does not duplicate those validators or add a competing validation
error vocabulary.

Failure behavior is deliberately transparent and fail-fast:

- a leaf input or evaluation error propagates unchanged;
- leaves after the failing leaf are not invoked;
- no partial assessment is returned;
- a non-finding leaf result or malformed returned finding fails through the
  existing field-intelligence contract errors rather than being repaired;
- duplicate rule IDs, invalid source linkage, invalid nested findings, or invalid
  final ordering fail through the existing field-intelligence contract errors;
- exceptions are not converted into `None` or `NOT_EVALUATED`;
- no retry, fallback, partial-success, warning-only, or continue-on-error policy is
  introduced.

Because every leaf and the aggregate are pure and transient, successful earlier
calls create no externally visible partial state when a later call fails.

### 7. Source-immutability and identity guarantees

The exact `source` object supplied by the caller is passed to every leaf and then
to `ConfirmedObservationFieldIntelligenceAssessment`. The orchestrator does not:

- reconstruct, copy, canonicalize, enrich, or mutate the source;
- copy or rewrite observations, submitted values, canonical values, or provenance;
- write a value back into `ConfirmedObservationSet`;
- retain catalogs or evaluation context in the assessment;
- persist, serialize, cache, log, or publish any input or result.

The returned assessment's `source is source`. Its `findings` tuple contains the
exact non-`None` finding objects returned by the leaves, reordered only by lexical
rule ID. Repeated calls with equal immutable inputs remain deterministic under the
existing leaf contracts.

### 8. Backward-compatibility guarantees

Implementation must add one module and one focused test module only. It must not
modify the five leaf evaluator modules, their rule catalogs, the certification
context contract, `ConfirmedObservationSet`, the assessment contract, existing
tests, or `capture_import.__init__`.

All existing leaf evaluator APIs remain directly callable with their exact current
signatures and behavior. No leaf is wrapped, registered, renamed, deprecated, or
made dependent on the orchestrator. Existing callers may ignore the new module.
No default runtime wiring is introduced, so current readiness, OCR, persistence,
collection, and mutation behavior remains unchanged.

### 9. Focused test matrix

The focused test module will be:

`tests/test_workflow_confirmed_observation_field_intelligence_orchestrator.py`

It must cover:

#### Public and architecture boundary

- exact `__all__`, module-defined public names, callable name, parameter order,
  defaults, annotations, and return annotation;
- no aggregate class, registry, default catalog, serializer, persistence,
  readiness, collection, OCR-runtime, GUI, filesystem, environment, network,
  clock, logging, normalization, or historical-data API;
- exact bounded imports and no package-root re-export.

#### Invocation contract

- all five leaves are invoked once with the exact source objects and corresponding
  catalog/context objects;
- the fixed invocation sequence is observed;
- `None` certification context is forwarded unchanged;
- empty caller catalogs are forwarded unchanged;
- absence of relevant evidence does not cause orchestrator-side skipping;
- a failing leaf prevents later leaf invocation and produces no assessment.

#### Omission, ordering, and identity

- all five `None` results produce an empty assessment;
- every combination of `None` and finding results omits only `None`;
- a non-`None` result of the wrong type fails through
  `InvalidFieldIntelligenceContextError` before sorting;
- deliberately non-lexical leaf rule IDs are reordered lexically;
- status and invocation order do not affect final ordering;
- exact finding identities survive filtering and sorting;
- duplicate rule IDs fail through
  `DuplicateFieldIntelligenceFindingError` without overwrite;
- source-field misalignment and malformed findings fail closed through existing
  assessment contracts.

#### Source and result guarantees

- returned assessment retains the exact source identity;
- source, observations, catalogs, rules, and certification context remain
  unchanged;
- no submitted, canonical, or provenance values are copied into aggregate state;
- repeated calls with identical inputs return equal deterministic assessments;
- emitted findings remain valid under direct assessment reconstruction.

#### Real-leaf integration

- one fixture with evidence spanning all leaf domains and caller-owned catalogs
  produces the expected mixed assessment;
- unrelated-only evidence yields the existing leaf-driven empty assessment;
- empty catalogs preserve `NOT_EVALUATED` rather than becoming valid or invalid;
- existing leaf validation errors propagate unchanged;
- no readiness or collection behavior is invoked.

The implementation gate runs the new focused module first, then all five existing
leaf evaluator modules and the field-intelligence assessment module. The complete
repository regression remains the authoritative pre-commit gate.

### 10. Proposed implementation units and atomic commit sequence

The smallest sequence is:

1. **Architecture record** — this ADR only. Proposed commit subject after approval:
   `docs: define field-intelligence aggregate orchestration`.
2. **Aggregate implementation** — add the one owning production module and its one
   focused test module in a single coherent unit. Proposed commit subject after
   focused and full validation:
   `feat: add field-intelligence aggregate orchestration`.
3. **Verification record** — after authoritative regression and independent review,
   update only this ADR's status and the appropriate progress record without
   changing the locked roadmap. Proposed commit subject:
   `docs: verify field-intelligence aggregate orchestration`.

Each commit is separately reviewable. No implementation commit may include roadmap,
production-integration, readiness, persistence, collection, or cleanup changes.

### 11. Recording without changing Sprint 18

This ADR and any later progress entry use the exact label:

**Post-Sprint-17 Field-Intelligence Aggregate Orchestration**

They must not call the work Sprint 18, renumber a roadmap item, or imply that the
locked Sprint 18 scope has changed. `docs/roadmap/COIN_ANALYZER_ROADMAP_LOCKED.txt`
remains byte-for-byte unchanged. The work is traceable to the explicit deferred
aggregate-orchestration section in `docs/progress.md`, not to a roadmap sprint.

## Explicit exclusions

This architecture does not authorize:

- persistence, serialization, schema changes, repositories, or migrations;
- collection mapping, mutation, rollback, recovery, or audit records;
- readiness authority, blocking decisions, strict-valid helpers, or UI state;
- default or global catalogs, catalog discovery, or built-in historical knowledge;
- normalization, canonicalization, inference, aliasing, fuzzy matching, or fallback;
- evaluator concurrency, retries, timeouts, caching, metrics, or logging;
- edits to `data/collection.json`;
- unrelated cleanup, refactoring, leaf consolidation, or public API expansion;
- production runtime composition beyond the explicit caller-invoked aggregate;
- any claim that this work is Sprint 18.

## Consequences and tradeoffs

- Callers gain one deterministic assessment boundary while retaining direct access
  to every leaf evaluator.
- The explicit six-argument signature is longer than a context DTO, but it keeps
  ownership visible and avoids a new mutable or versioned aggregate-input contract.
- Repeated source validation inside the unchanged leaves remains intentional. It
  preserves each leaf's standalone safety and avoids compatibility-affecting
  refactoring for a small pure orchestration function.
- Fixed sequential invocation is simpler and makes failure order deterministic;
  parallel execution would add complexity without meaningful benefit for five
  in-memory leaf calls.
- Transparent propagation exposes the precise existing contract that failed and
  avoids masking malformed input as an advisory finding.
- Caller rule-ID collisions are rejected by the existing assessment contract rather
  than silently reconciled.

## Rejected alternatives

| Alternative | Disposition | Reason |
| --- | --- | --- |
| Mutable aggregate-input context | Rejected | Hides ownership and creates a second lifecycle-bearing contract. |
| Default/global catalogs | Rejected | Violates caller ownership and could silently assert incomplete knowledge. |
| Orchestrator-side field applicability checks | Rejected | Duplicates leaf policy and can drift from existing `None` behavior. |
| Registry or dynamic evaluator discovery | Rejected | Weakens exact-once invocation and deterministic public scope. |
| Concurrent leaf invocation | Rejected | Complicates deterministic failure ordering for negligible gain. |
| Deduplicate findings by rule ID | Rejected | Would hide caller catalog conflicts and violate fail-closed assessment semantics. |
| Aggregate-specific status or readiness result | Rejected | The assessment already preserves mixed advisory findings without readiness authority. |
| Package-root re-export | Rejected | Unnecessary public-surface expansion; explicit module import matches existing field-intelligence practice. |

## Invariants

1. Every successful call invokes each of the five existing leaves exactly once.
2. Only exact `None` leaf results are omitted.
3. Every retained finding is the exact object returned by its leaf.
4. Findings are ordered only by ascending lexical `rule_id`.
5. Duplicate rule IDs fail closed; no result is overwritten.
6. The returned assessment retains the exact supplied source object.
7. Source, catalogs, context, observations, and findings are never mutated.
8. No exception becomes `None`, `VALID`, `INVALID`, or `NOT_EVALUATED`.
9. No durable state, readiness authority, collection authority, or runtime default is introduced.
10. Every existing leaf evaluator remains independently callable and behaviorally unchanged.
11. The locked roadmap and its Sprint 18 scope remain unchanged.

## Implementation verification

The approved design was implemented in commit `7a7c1ed` with exactly these new
files:

- `capture_import/workflow_confirmed_observation_field_intelligence_orchestrator.py`;
- `tests/test_workflow_confirmed_observation_field_intelligence_orchestrator.py`.

Verification on 2026-08-01 completed with:

- focused aggregate orchestration: 25 tests passed;
- existing assessment and five leaf evaluators: 178 tests passed;
- authoritative root discovery: 4,270 tests run, 23 skipped, zero failures,
  and zero errors;
- `git diff --check`: passed.

Independent review confirmed that the implementation invokes every leaf exactly
once on successful calls, filters only exact `None`, validates and retains exact
finding objects, orders findings lexically by `rule_id`, preserves the exact
source, and adds no persistence, readiness, collection, default-catalog, built-in
knowledge, normalization, inference, registry, DTO, or runtime-wiring behavior.

## Reconsider when

Reconsider only through a separately approved architecture amendment if:

- another leaf evaluator is added or a current leaf signature changes;
- aggregate callers require an explicitly versioned immutable input contract;
- profiling demonstrates a material need for concurrent evaluation with reviewed
  deterministic failure semantics;
- rule-ID namespace ownership is formalized across catalogs;
- findings become durable or gain readiness, collection, or mutation authority; or
- aggregate orchestration is integrated into a default production workflow.
