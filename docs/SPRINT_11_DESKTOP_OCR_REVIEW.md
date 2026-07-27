# Sprint 11 - Desktop OCR Review Experience

## Status

Sprint 11 adds an explicit, opt-in desktop review experience around the
advisory OCR workflow introduced in Sprint 9 and the immutable human-review
services introduced in Sprint 10.

The implementation is prepared for closure pending the Unit 1F and
documentation commits. Sprint 11 is not yet committed or closed.

The latest authoritative repository validation is:

```text
2,696 total
2,673 passed
22 skipped
1 known unrelated failure
0 errors
runtime: 125.130 seconds
```

The unrelated failure is:

```text
test_melt_value_engine.TestApiSpotPriceProvider.test_cache_persistence
```

The failure is caused by the test's relative
`data/test_silver_spot_cache.json` path in an execution environment that
cannot write beneath the repository root. The cache write failure is swallowed
by the provider, so the second provider reloads no cached price. The same test
has passed from a writable temporary working directory. It is separate
maintenance debt and is not related to OCR review.

## Sprint objective

Provide a bounded desktop surface in which a collector can:

- inspect advisory OCR field candidates;
- approve, correct, reject, or defer each candidate;
- compare consolidation conflicts with their provenance;
- select an existing value, enter an exact corrected value, or defer;
- inspect final and unresolved reviewed metadata;
- discard the in-memory review by closing the application.

The sprint deliberately stops at an immutable reviewed projection. It does not
persist review state, create confirmed observations, plan collection changes,
or mutate collection data.

## Units completed

### Unit 1A - Presentation models

Commit:

```text
a8514ba feat: add OCR review presentation models
```

`capture_import/workflow_ocr_review_presenter.py` defines frozen, slotted
display projections for:

- candidate review state;
- accepted-value provenance;
- consolidated fields;
- conflict-resolution state;
- final and unresolved fields;
- complete review-session summaries.

`OCRReviewPresenter` remains the only Sprint 11 source of display-ready state.
It presents existing Sprint 9 and Sprint 10 immutable DTOs without changing
domain outcomes.

### Unit 1B - Review-session controller

Commit:

```text
ecf0480 feat: add OCR review session controller
```

`capture_import/workflow_ocr_review_controller.py` provides
`OCRReviewSessionController` and immutable `OCRReviewControllerState`.
The controller reconstructs state from a report, review aggregate, resolution
tuple, and review mode. It delegates orchestration to
`OCRReviewSessionService` and presentation to `OCRReviewPresenter`.

### Unit 1C - Opt-in desktop composition

Commit:

```text
7565e32 feat: add opt-in desktop OCR review composition
```

`capture_import/desktop_ocr_review_composition.py` provides:

- `DesktopOCRReviewComposition`;
- `create_desktop_ocr_review_composition(...)`.

The factory constructs an OCR-enabled pipeline and an independent review
controller only when explicitly called. Optional legacy OCR runtime imports
remain lazy. Default desktop composition is unchanged and OCR-free.

### Unit 1D - Candidate-review UI

Commit:

```text
e558bdd feat: add desktop OCR candidate review UI
```

`capture_import/desktop_ocr_candidate_review.py` provides a headless
interaction model and a thin Tkinter/ttk dialog:

- `OCRCandidatePreview`;
- `OCRCandidateReviewDisplay`;
- `OCRCandidateReviewModel`;
- `OCRCandidateReviewDialog`;
- `create_ocr_candidate_review_dialog(...)`.

Approve, correct, reject, and defer actions construct existing Sprint 10 review
contracts. The model submits complete proposed review aggregates through the
Unit 1B controller and changes local state only after validation succeeds.

### Unit 1E - Conflict-resolution UI

Commit:

```text
c792b8b feat: add desktop OCR conflict review UI
```

`capture_import/desktop_ocr_conflict_review.py` provides:

- `OCRConflictProvenanceDisplay`;
- `OCRConflictReviewDisplay`;
- `OCRConflictReviewModel`;
- `OCRConflictReviewDialog`;
- `create_ocr_conflict_review_dialog(...)`.

Select-existing, corrected-value, and defer actions construct existing Sprint
10 conflict-resolution requests. Proposed resolution aggregates are submitted
through the Unit 1B controller before display or local state changes.

### Unit 1F - Workflow handoff and integration tests

Prepared but not yet committed:

- `capture_import/desktop_ocr_review_handoff.py`;
- `tests/test_desktop_ocr_review_integration.py`.

The unit adds:

- `DesktopOCRReviewHandoff`;
- `create_desktop_ocr_review_handoff(...)`.

The OCR workflow emits JSON-safe, per-image report payloads. The handoff
explicitly decodes and validates those payloads, deterministically aggregates
them into one `OCRMetadataReport`, and returns the existing Unit 1C review
controller. It does not own review-session state or become a second
composition root.

A regression found that validating Unit 1C composition by concrete class
identity was sensitive to `importlib.reload`. The implementation now validates
the minimal public contract instead:

- `pipeline` must be a `ProcessingPipeline` containing the advisory OCR stage;
- `review_controller` must be an `OCRReviewSessionController`.

The original reload ordering and invalid-object cases now pass.
Closure validation also found that the reload regression test initially left
the Unit 1C module in its reloaded state, which could disturb later Unit 1C
tests in the reverse module order. The test now restores the public class and
factory identities in a `finally` block; both module orders pass.

## Final architecture

Sprint 11 preserves the existing layer direction:

```text
Sprint 9 opt-in OCR workflow
        |
        v
PipelineOutcome with serialized OCR reports
        |
        v
Unit 1F immutable report handoff
        |
        v
Unit 1D candidate-review model/dialog
        |
        v
Unit 1B review-session controller
        |
        v
Sprint 10 reconciliation and consolidation
        |
        v
Unit 1E conflict-review model/dialog
        |
        v
Sprint 10 final projection
        |
        v
Unit 1A presentation state
```

The responsibilities are intentionally separate:

- Unit 1C owns explicit OCR-enabled desktop composition.
- Unit 1F owns serialized workflow-output decoding and aggregation.
- Unit 1D and Unit 1E own explicit ephemeral interaction state.
- Unit 1B owns application orchestration.
- Sprint 10 owns all review, reconciliation, consolidation,
  conflict-resolution, and final-projection rules.
- Unit 1A owns display projection.

No circular dependency or second composition root was found.

## End-to-end data flow

1. The caller explicitly invokes `create_desktop_ocr_review_composition`.
2. The opt-in pipeline produces JSON-safe OCR reports through an injected OCR
   provider or explicitly selected runtime.
3. `create_desktop_ocr_review_handoff` validates the workflow metadata,
   decodes each report, sorts its immutable observations, candidates, and
   conflicts, and returns one aggregate report with the Unit 1C controller.
4. `OCRCandidateReviewModel` presents Unit 1A candidate views and collects
   explicit Sprint 10 field-review decisions.
5. Each candidate action submits the complete proposed review aggregate through
   `OCRReviewSessionController`.
6. Sprint 10 reconciliation accepts only approved or corrected values,
   preserves provenance, and separates rejected, deferred, and missing
   candidates.
7. Sprint 10 consolidation emits agreed fields or unresolved conflicts.
8. `OCRConflictReviewModel` presents Unit 1A conflict views and constructs
   existing Sprint 10 resolution requests.
9. Each resolution action submits the complete proposed resolution tuple
   through `OCRReviewSessionController`.
10. Sprint 10 final projection emits final and unresolved fields.
11. Unit 1A presents completion state, final values, unresolved values, and
    counts.

No step maps the projection into a collection or durable observation.

## Public APIs introduced

### Presentation

- `OCRProvenanceView`
- `OCRReviewCandidateView`
- `OCRConsolidatedFieldView`
- `OCRConflictResolutionView`
- `OCRFinalFieldView`
- `OCRReviewSessionView`
- `OCRReviewPresenter`

### Controller

- `OCRReviewControllerState`
- `OCRReviewSessionController`

### Opt-in composition

- `DesktopOCRReviewComposition`
- `create_desktop_ocr_review_composition(...)`

### Candidate review

- `OCRCandidatePreview`
- `OCRCandidateReviewDisplay`
- `OCRCandidateReviewModel`
- `OCRCandidateReviewDialog`
- `create_ocr_candidate_review_dialog(...)`

### Conflict review

- `OCRConflictProvenanceDisplay`
- `OCRConflictReviewDisplay`
- `OCRConflictReviewModel`
- `OCRConflictReviewDialog`
- `create_ocr_conflict_review_dialog(...)`

### Workflow handoff

- `DesktopOCRReviewHandoff`
- `create_desktop_ocr_review_handoff(...)`

## Default-path safety

- `build_image_processing_pipeline()` remains OCR-free.
- Default desktop startup does not import or construct candidate or conflict
  review dialogs.
- Unit 1C composition is created only through an explicit factory call.
- Optional OCR runtime dependencies are not imported eagerly.
- No environment-variable feature switch was added.
- No global service registration or mutable singleton was added.
- No review dialog opens automatically after import.
- Unit 1F consumes an already-produced `PipelineOutcome`; it does not execute
  OCR or alter default composition.

## Human-review trust boundaries

- **OCR remains advisory.** Workflow candidates are suggestions and never
  authorize collection changes.
- **Human review remains mandatory.** Only explicit approve or correct field
  decisions become accepted metadata.
- **Conflicts remain explicit.** No source priority, fallback, or automatic
  winner is implemented.
- **Unresolved remains unresolved.** Deferred or missing decisions and
  unresolved conflicts never receive fabricated values.
- **Corrected values remain exact.** UI models do not normalize user-entered
  corrections.
- **Invalid actions are atomic.** Candidate and conflict models retain prior
  valid state when controller or domain validation fails.
- **Grade remains excluded.** Grade is absent from supported OCR fields and is
  rejected by existing immutable domain validation.
- **Final projection is not collection-ready.** It contains reviewed metadata,
  provenance, and resolution state only.

## Test coverage and latest validation

The latest authoritative full discovery run reported:

```text
Ran 2,696 tests in 125.130s
FAILED (failures=1, skipped=22)
```

Derived totals:

```text
2,673 passed
22 skipped
1 known unrelated failure
0 errors
```

The previous 14 Unit 1F reload-order errors are gone.

Focused architectural groups:

```text
Sprint 11 presentation/controller/composition/UI/integration: 142 passed
Sprint 10 review-domain support:                         81 passed
Unit 1C -> Unit 1F reload-order regression:              35 passed
Unit 1F focused integration:                             21 passed
```

The integration suite remains headless. It executes the explicit Unit 1C
composition pipeline with deterministic injected OCR/runtime and image-byte
dependencies, then uses real Unit 1A through Unit 1E public APIs. Tk dialog
shells are substituted only where needed to verify factory handoff without a
display server.

## Architecture-review findings

### Presentation and controller

Unit 1A view models are frozen and slotted. Presentation ordering is explicit
and deterministic. Unit 1B is stateless apart from injected stateless service
references and delegates the complete session request to Sprint 10 before
presenting it.

### Candidate UI

The candidate model stores only an index and an in-memory mapping of explicit
field-review decisions. Navigation is bounded. Proposed decisions are copied,
sorted, and controller-validated before replacement. Confidence, evidence,
human state, artifact identity, provider identity, and image role remain
visible. Preview resolution is injected and preview failures are display-safe.

### Conflict UI

The conflict model stores only an index, exact immutable consolidated targets,
and an in-memory mapping of resolution requests. It reconstructs session state
from immutable inputs. Provenance records are not collapsed. Optional
confidence and evidence are enriched only through an exact source-candidate
correlation. Final and unresolved fields come from Unit 1A presentation state
after controller validation.

### Handoff

The handoff contains no UI or review-domain orchestration. It explicitly
validates workflow metadata shape, count fields, status enums, selected image
variants, nested OCR DTOs, and Unit 1C's public composition contract.
Malformed or incompatible metadata raises clear `TypeError` or `ValueError`
exceptions. Aggregation uses explicit stable sort keys and immutable tuples.

### Side effects and imports

The Sprint 11 review components have no persistence, confirmed-observation, or
collection imports. The presentation, controller, UI models, and handoff do
not read files, traverse directories, inspect environment variables, execute
OCR, or register global services. Tkinter is confined to the two explicit
dialog modules. The optional legacy runtime import remains local to the Unit
1C opt-in factory.

### Code quality

- The candidate dialog is 714 lines and the conflict dialog is 818 lines.
  Both remain cohesive because each module contains one headless model, one
  thin dialog, its display DTOs, and one explicit factory.
- The handoff decoder is 484 lines and remains cohesive around one serialized
  metadata boundary.
- Candidate and conflict modules repeat small amounts of navigation, error
  display, and label formatting. Extracting a UI framework now would add
  coupling without correcting a defect.
- Test modules contain repeated deterministic OCR builders. Shared builders may
  become worthwhile if Sprint 12 repeats these fixtures.
- No hidden mutable coupling exists between Unit 1D and Unit 1E. Their public
  connection is the immutable report/review aggregate and the injected Unit 1B
  controller.

## Known technical debt

- The Unit 1F workflow handoff is coupled to the current serialized OCR metadata
  keys and nesting.
- OCR workflow metadata has no explicit schema-version abstraction or migration
  policy.
- Candidate and conflict Tk dialog modules are large but currently cohesive.
- The preview resolver must supply a pre-created Tk-compatible image object;
  image decoding and lifecycle remain external.
- Sprint 10 conflict-resolution DTOs do not contain a conflict-resolution
  rationale, so Unit 1A presents `resolution_rationale=None`.
- Conflict provenance enrichment depends on exact correlation with a Unit 1A
  candidate identity. Missing or ambiguous matches safely omit optional
  confidence and evidence.
- Review and resolution state is ephemeral and may be discarded when the
  dialog or application closes.
- No persistence repository, durable session identity, schema migration, or
  save/resume strategy exists.
- No confirmed-observation mapping boundary exists.
- No collection-change planning or collection-mutation boundary exists.
- Candidate identities, conflict identities, display formatting, and test
  builders contain small repeated structures that may justify extraction in a
  later unit.
- The melt-value cache persistence test uses a relative cache path and the
  provider silently swallows its write failure. This makes the test dependent
  on repository-root write permissions.

These are documented constraints or deferred capabilities, not unresolved
Sprint 11 correctness defects.

## Explicitly deferred work

- Durable review-session persistence.
- Review-session IDs and reviewer identity integration.
- Save, resume, migration, and incompatible-schema handling.
- Mapping final reviewed metadata into confirmed observations.
- Collection change planning and explicit second approval.
- Collection mutation and durable audit recording.
- Field-specific normalization or equivalence rules.
- Automatic OCR execution or default enablement.
- Automatic dialog launch or main-window redesign.
- Release packaging.

## Sprint 11 exit-gate assessment

| Exit criterion | Assessment |
| --- | --- |
| OCR review works through the explicit desktop path | PASS |
| Candidate review supports all explicit decisions | PASS |
| Conflict review supports all explicit resolutions | PASS |
| Provenance and final projection remain visible | PASS |
| Default desktop behavior remains OCR-free | PASS |
| No collection data is changed | PASS |
| Review state may be discarded on close | PASS |
| Unit 1F has no related regression failures or errors | PASS |
| Full regression has no new Sprint 11 failure | PASS |
| Known unrelated environment debt is documented | PASS |

Sprint 11 is prepared for closure pending the Unit 1F and documentation
commits. It must not be described as closed until those commits are created and
validated.

## Recommended Sprint 12 starting point

Begin with a persistence architecture unit, not collection mutation:

1. Define a repository interface for immutable review-session snapshots.
2. Define an explicit schema version for serialized OCR reports, reviews,
   resolutions, and projections.
3. Define stable review-session and reviewer identity contracts.
4. Specify migration and incompatible-version behavior.
5. Specify incomplete-session save/resume lifecycle.
6. Preserve the current default-off OCR boundary.
7. Keep confirmed-observation mapping and collection mutation behind later,
   separately authorized units.

The first Sprint 12 unit should consume the existing immutable report, review,
resolution, and projection DTOs without moving persistence concerns into the
Sprint 10 services or Sprint 11 UI models.
