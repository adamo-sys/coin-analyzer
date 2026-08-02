# Sprint 17 Progress

This closure update records the completed contract and leaf-evaluator scope of the Sprint 17 field-intelligence workstream. Aggregate orchestration and production integration were outside this closure and were explicitly deferred at that point.

## 1. Completed Units

The following Sprint 17 units are completed in the existing Git history, in chronological order.

| Unit identifier | Short description | Commit hash | Status |
| --- | --- | --- | --- |
| 1A | Field-intelligence assessment contracts for transient rule outcomes over `ConfirmedObservationSet`. | `346f8db` | Complete |
| 1B | Coin-year rule catalog contracts for caller-owned year rules and exact country/denomination scope matching. | `682fff6` | Complete |
| 1C | Coin-specific year evaluator for exact submitted-year membership checks against a caller-supplied catalog. | `2b39f87` | Complete |
| 1D | Denomination-country compatibility contracts for exact rule records across country and denomination. | `8598f5f` | Complete |
| 1E | Denomination-country compatibility evaluator for advisory `VALID`/`INVALID`/`NOT_EVALUATED` outcomes. | `57ce284` | Complete |
| 1F | Shared monarch-year compatibility helper extraction to keep year compatibility logic consistent across field-intelligence features. | `ddfcfe3` | Complete |
| 1G | Monarch-year compatibility evaluator for exact monarch/year compatibility assessment. | `eae4605` | Complete |
| 1H | Mintmark rule catalog contracts for deterministic mintmark rule scope and ordering. | `2a692b3` | Complete |
| 1I | Mintmark compatibility evaluator for exact caller-supplied mintmark evidence evaluation. | `2764942` | Complete |
| 1J | Certification context rule contracts for caller-supplied grading-company context and exact certification scope records. | `eb74314` | Complete |
| 1K | Certification-context evaluator for exact caller-supplied grading-company and certification evidence evaluation. | `c7148eb`, refined by `7740f8e` | Complete |

## 2. Current Architecture

The Sprint 17 architecture is a pure field-intelligence layer that remains advisory and deterministic.

### Current field-intelligence architecture

- The layer reads exact submitted values from `ConfirmedObservationSet`.
- It never mutates the source observation set.
- It never persists findings, catalogs, or evaluator state.
- It never introduces built-in grading-company knowledge, historical numbering knowledge, or default catalogs.
- It emits at most one transient `FieldIntelligenceFinding` per evaluation call.
- It leaves readiness, persistence, OCR, and collection mutation fully outside the evaluator boundary.

### Immutable rule contracts

The immutable rule-contract modules currently present in the repository are:

- `capture_import/workflow_confirmed_observation_field_intelligence.py`
  - `FieldIntelligenceStatus`
  - `FieldIntelligenceFinding`
  - `ConfirmedObservationFieldIntelligenceAssessment`
- `capture_import/workflow_confirmed_observation_coin_year_rules.py`
  - `CoinYearRule`
  - `CoinYearRuleCatalog`
- `capture_import/workflow_confirmed_observation_denomination_country_rules.py`
  - `DenominationCountryRule`
  - `DenominationCountryRuleCatalog`
- `capture_import/workflow_confirmed_observation_mintmark_rules.py`
  - `MintmarkRule`
  - `MintmarkRuleCatalog`
- `capture_import/workflow_confirmed_observation_certification_context_rules.py`
  - `CertificationContextRule`
  - `CertificationContextRuleCatalog`
  - `CertificationEvaluationContext`

### Evaluators

The current evaluator surface is:

- `capture_import/workflow_confirmed_observation_coin_year_evaluator.py`
  - `assess_coin_specific_year`
- `capture_import/workflow_confirmed_observation_denomination_country_evaluator.py`
  - `assess_denomination_country_compatibility`
- `capture_import/workflow_confirmed_observation_monarch_year_evaluator.py`
  - `assess_monarch_year_compatibility`
- `capture_import/workflow_confirmed_observation_mintmark_evaluator.py`
  - `assess_mintmark`
- `capture_import/workflow_confirmed_observation_certification_context_evaluator.py`
  - `assess_certification_context`

All five leaf evaluators are complete and present in repository history. Each
returns at most one transient `FieldIntelligenceFinding`, or `None` when its
relevant fields are wholly absent. No public aggregate evaluator currently
exists to invoke or combine these leaf results into
`ConfirmedObservationFieldIntelligenceAssessment`.

### Interaction with `ConfirmedObservationSet`

- `ConfirmedObservationSet` remains the authoritative evidence boundary.
- Field-intelligence evaluators receive a validated `ConfirmedObservationSet`.
- The evaluators validate the source first using the existing confirmed-observation validation boundary.
- Evaluators read exact submitted values only.
- Canonical values are ignored by the field-intelligence layer.
- `ConfirmedObservationSet` is not rewritten, enriched, or mutated.
- Findings are returned as transient field-intelligence artifacts only.

### Architectural boundaries

The current field-intelligence architecture intentionally keeps these boundaries fixed:

- No persistence
- No readiness integration
- No default catalogs
- No built-in grading-company knowledge
- No built-in historical numbering knowledge
- No normalization, inference, trimming, or rewrite of certification values
- No mutation of `ConfirmedObservationSet`
- Caller-owned rule catalogs only
- Advisory outcomes only; no readiness or collection-authority claims

## 3. Sprint 17 Closure Scope

Sprint 17 closes only the field-intelligence contract and leaf-evaluator
scope. The completed scope consists of the immutable assessment and finding
contracts, the caller-owned rule-catalog contracts, the shared monarch-year
compatibility helper, and the five independent leaf evaluators listed above.

Aggregate orchestration is not part of the completed scope. No aggregate
orchestration function or public aggregate evaluator currently exists, and
none of the five leaf evaluators is wired into an aggregate production flow.
Production integration is therefore deferred, not complete.

## 4. Aggregate Orchestration Gate at Sprint 17 Closure

At Sprint 17 closure, aggregate orchestration required a separately designed
architectural unit and explicit approval before implementation. That design and
approval had to cover:

1. ownership and module boundary;
2. the public callable and its signature;
3. catalog and context inputs;
4. deterministic evaluator ordering;
5. handling of `None` findings;
6. `ConfirmedObservationFieldIntelligenceAssessment` construction and validation;
7. backward compatibility; and
8. preservation of transient, advisory-only behaviour.

Until that separate gate was satisfied, the leaf evaluators remained independent,
caller-invoked functions. No documentation in the Sprint 17 closure should be read
as claiming aggregate evaluation, production wiring, persistence, readiness
authority, or collection-mutation authority.

## 5. Sprint 17 Closure Repository Status

### Closure authoritative regression baseline

- Command: `python -m unittest discover -s . -p "test_*.py"`
- Result: `Ran 4241 tests in 128.602s`
- Status: `OK (skipped=22)`; zero failures and zero errors

### Closure test count

- Tests run: 4,241
- Skipped: 22
- Failures: 0
- Errors: 0

### Closure architecture baseline

- Closure architecture baseline: a pure, immutable, caller-owned field-intelligence layer over `ConfirmedObservationSet`.
- Rule catalogs remain deterministic and caller-supplied.
- Evaluators remain advisory and non-authoritative.
- No persistence, readiness, or default-catalog behavior is wired into the layer.
- No aggregate orchestration or production integration is wired into the layer.

## Closure Decision

**PASS for the bounded contract and leaf-evaluator scope.**

Sprint 17 is closed only for its contracts and five leaf evaluators. Aggregate
orchestration remained outside Sprint 17 and is recorded separately below;
production integration remains deferred.

## Post-Sprint-17 Field-Intelligence Aggregate Orchestration

**Status: VERIFIED**

The separately approved post-Sprint-17 architecture unit is now complete. It is
not Sprint 18 and does not amend, renumber, reinterpret, or unlock the roadmap.
Sprint 18 remains "Image and OCR UX refinement."

- Architecture: `docs/adr/ADR-009-field-intelligence-aggregate-orchestration.md`
- Architecture commit: `4516925`
- Implementation commit: `7a7c1ed`
- Public callable:
  `assess_confirmed_observation_field_intelligence`
- Owning module:
  `capture_import/workflow_confirmed_observation_field_intelligence_orchestrator.py`

The aggregate is pure, transient, and advisory. It invokes each of the five
existing leaf evaluators exactly once on successful calls, passes through the
exact caller-owned source, catalogs, and certification evaluation context,
discards only exact `None` results, validates every retained finding, preserves
finding identity, orders findings lexically by `rule_id`, and returns
`ConfirmedObservationFieldIntelligenceAssessment` with the exact source.

No leaf API changed. No persistence, readiness authority, collection mutation,
default catalog, built-in historical knowledge, normalization, inference, DTO,
registry, package-root export, or default runtime wiring was introduced.

Verification completed on 2026-08-01:

- focused aggregate orchestration: 25 tests passed;
- existing assessment and five leaf evaluators: 178 tests passed;
- authoritative root discovery: 4,270 tests run, 23 skipped, zero failures,
  and zero errors;
- independent ADR-009 and `AGENTS.md` review: PASS.

## Sprint 18 — Image and OCR UX Refinement

**Status: IN PROGRESS**

### Side-by-side obverse/reverse review

The first bounded Sprint 18 slice is complete in commit `a2e5b62`.

- The opt-in OCR candidate-review dialog now presents available obverse and
  reverse previews together for the current coin.
- A one-sided review retains a clearly labelled obverse or reverse panel, and
  an empty review presents an explicit no-images state.
- Preview panels use the existing injected resolver and immutable OCR review
  state. Existing candidate-review APIs and the current-preview contract are
  unchanged.
- The layout uses two columns when space permits and stacks at narrow widths.
- Image panels include meaningful side labels, focusable image or fallback
  content, and descriptive text for available images.
- No crop, zoom, contrast, candidate-highlighting, keyboard, batch-review, or
  persistence behavior was added in this slice.

Focused verification on 2026-08-01:

- candidate-review tests: 32 passed;
- candidate-review plus related desktop review/integration tests: 126 passed;
- authoritative root discovery: 4,277 tests run, 4,253 passed, 23 skipped,
  one known unrelated local-only melt-value cache failure, and zero errors;
- `git diff --check`: passed;
- independent `AGENTS.md` and Sprint 18 scope review: PASS.

### Zoom and contrast controls

The second bounded Sprint 18 slice is complete in commit `6270141`, following
the callback contract recorded in `docs/SPRINT_18_IMAGE_OCR_UX_REFINEMENT.md`
and commit `001f06a`.

- `OCRCandidatePreview` accepts an optional `AdjustedPreviewRenderer` callback
  with signature `Callable[[float, float], object]`.
- Existing resolvers remain valid. Legacy previews continue to display their
  original image with visibly disabled adjustment controls.
- Zoom is bounded from 0.50× through 3.00× in 0.25× steps. Contrast is bounded
  from 0.50× through 2.00× in 0.10× steps. Both default to 1.00×.
- Adjustment state is transient and independent by exact coin, side, and
  preview reference. Reset restores the exact original image without invoking
  the callback.
- Rendering failures retain the prior valid values and displayed image while
  surfacing a bounded dialog error.
- Controls are focusable, communicate current values, wrap at narrow widths,
  and preserve paired, single-side, and empty review states.
- Pixel decoding, transformation, Tk-image creation, and source-image ownership
  remain with the injected resolver. No transformed image is persisted.

Verification completed on 2026-08-01:

- candidate-review tests: 43 passed;
- related desktop review/integration tests: 94 passed;
- authoritative root discovery: 4,288 tests run, 4,264 passed, 23 skipped,
  one known unrelated local-only melt-value cache failure, and zero errors;
- syntax compilation and `git diff --check`: passed;
- independent contract, `AGENTS.md`, and Sprint 18 scope review: PASS.

### Crop adjustment

The third bounded Sprint 18 slice is complete in commit `daf7d6d`, following
the supplemental crop-renderer contract recorded in
`docs/SPRINT_18_IMAGE_OCR_UX_REFINEMENT.md` and commit `ce7a6b7`.

- `NormalizedCrop` represents the retained visible rectangle with exact,
  finite normalized `left`, `top`, `right`, and `bottom` coordinates.
- The full image is the default. Each edge moves in 0.05 steps, remains inside
  0.0 through 1.0, and preserves a minimum retained width and height of 0.20.
- The existing two-argument `AdjustedPreviewRenderer` remains unchanged.
  Crop-capable previews may optionally supply a
  `CropAdjustedPreviewRenderer` with signature
  `Callable[[float, float, NormalizedCrop], object]`.
- Crop, zoom, and contrast compose through the resolver-owned renderer.
  Legacy and zoom/contrast-only previews remain compatible and show disabled
  crop controls.
- Crop state is transient and independent by exact coin, side, and preview
  reference. Reset restores the full crop, default zoom and contrast, and the
  exact original image without invoking a callback.
- Rendering failures preserve the prior valid crop, adjustment values, and
  displayed-image reference while surfacing the existing bounded dialog error.
- Focusable native edge controls and a coordinate status label preserve the
  responsive paired, single-side, and empty review states.
- Pixel decoding, cropping, transformation, Tk-image creation, and image
  lifecycle remain resolver-owned. No source image or OCR evidence is mutated,
  and no crop or transformed image is persisted.

Verification completed on 2026-08-01:

- candidate-review tests: 57 passed;
- related desktop review/integration tests: 94 passed;
- authoritative root discovery: 4,302 tests run, 4,278 passed, 23 skipped,
  one known unrelated local-only melt-value cache failure, and zero errors;
- syntax compilation and `git diff --check`: passed;
- independent contract, backward-compatibility, `AGENTS.md`, and Sprint 18
  scope review: PASS.

### Candidate highlighting

The fourth bounded Sprint 18 slice is complete in commit `2d8450c`.

- Selection remains owned exclusively by the existing current-candidate
  navigation index; the dialog adds no second selection model or persisted
  highlight state.
- The exact preview panel representing the current candidate uses a stronger
  border, bold panel label, and explicit "Selected candidate reference" text.
- Other visible same-coin side panels are identified as "Related image
  evidence (not selected)." This keeps selection understandable without color
  and without implying approval, rejection, ranking, or confidence.
- Native focus remains on the existing focusable image, status, and adjustment
  widgets, so keyboard focus and candidate selection remain distinct.
- Navigation rebuilds the panels from the new current candidate and moves the
  selected marker immediately. Multiple references for one side continue to
  show the current candidate's exact reference.
- Paired, single-side, unavailable, legacy-preview, narrow-layout, and empty
  states remain intact.
- Crop, zoom, and contrast state remains transient and independently keyed by
  exact coin, side, and preview reference, including across navigation.
- No public API, renderer callback, source model, candidate order, OCR
  evidence, review decision, or collection data changed.

Verification completed on 2026-08-01:

- candidate-review tests: 62 passed;
- related desktop review/integration tests: 94 passed;
- authoritative root discovery: 4,307 tests run, 4,283 passed, 23 skipped,
  one known unrelated local-only melt-value cache failure, and zero errors;
- syntax compilation and `git diff --check`: passed;
- independent selection-ownership, accessibility, `AGENTS.md`, and Sprint 18
  scope review: PASS.

### Remaining implementation sequence

1. Keyboard shortcuts after review and image actions are stable.
2. Batch review using the proven single-coin review flow.
3. Final end-to-end accessibility pass, while retaining accessibility checks
   in each preceding slice.
