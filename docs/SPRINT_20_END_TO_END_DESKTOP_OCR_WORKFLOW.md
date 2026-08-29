# Sprint 20 — End-to-End Desktop OCR Workflow

## Status

This document is the frozen architecture specification for Sprint 20.
Implementation has not started.

## Authorized Amendment — Primary Standalone Image Confirmed-Save Path

### Amendment status and precedence

This bounded amendment was authorized on 2026-08-26 for the desktop
standalone coin-image path. It extends the original planning-only Sprint 20
scope with one explicit, operator-confirmed new-record save boundary.

Where this amendment conflicts with the original statements that collection
mutation remains outside Sprint 20 or that OCR is always a secondary desktop
entry, this amendment controls only for the standalone image path described
below. The original non-OCR capture-package path and every other Sprint 20
boundary remain unchanged.

### Exact entry-point scope

The primary standalone coin-image action in `CoinCollectionGUI` shall:

1. accept the existing supported obverse/reverse JPG or PNG inputs;
2. adapt them through the existing temporary capture-package intake;
3. select the existing bounded OCR-enabled composition without a provider
   fallback;
4. open the existing candidate and conflict review surfaces by default;
5. require a complete strict review before constructing confirmed metadata;
6. display the corrected confirmed values before any authoritative write;
7. require a distinct affirmative save confirmation; and
8. persist one new collection record and its managed photos only after that
   confirmation.

The visible action may be labelled as the normal `Import Coin Images...`
workflow because OCR review is mandatory inside this path. This does not make
OCR the default for `Import Capture Package...`. That existing action must
continue to select `ImportPipelineMode.DEFAULT`, retain its current package
preview/commit semantics, and remain behaviorally unchanged.

### Authorized application flow

```text
standalone obverse/reverse selection
    -> existing standalone-image validation and temporary package
    -> existing OCR-enabled pipeline selection and execution
    -> existing immutable OCR handoff
    -> existing candidate review
    -> existing conflict review
    -> optional existing review-session save/resume controls
    -> strict-complete review projection
    -> existing confirmed-observation mapping
    -> existing confirmed-observation readiness validation
    -> non-mutating reviewed new-record draft
    -> operator inspects exact corrected values
    -> explicit save confirmation
        -> reject/cancel: release temporary source; no authoritative mutation
        -> confirm: existing collection persistence and managed-photo boundary
    -> reload/refresh through the existing collection interface
```

The application may coordinate these calls from the existing GUI entry-point
methods or one bounded application service. It must not duplicate OCR review,
confirmed-observation validation, collection serialization, managed-photo
copying, or collection-mutation policy.

### Trust and confirmation boundaries

- OCR reports, candidates, consolidated values, and model output remain
  advisory and never authorize a write.
- Only human-approved or human-corrected values from a strict-complete review
  may enter confirmed-observation mapping.
- Deferred, rejected, missing, unresolved, malformed, or incompatible fields
  cannot be replaced with raw proposals or inferred defaults.
- Draft creation is pure and non-mutating.
- The save confirmation occurs after draft creation and must display the exact
  country, denomination, and year that would be persisted.
- Closing, cancelling, or rejecting at either review or save confirmation
  releases adapter-owned temporary input and performs no collection or managed
  photo mutation.
- A successful explicit review-session save is separate from collection save;
  cancelling later does not erase that already-authorized review-session
  persistence.

### New-record persistence ownership

This amendment authorizes creation of exactly one new `CoinItem` through the
existing `CoinCollection` persistence owner after explicit confirmation.
Corrected confirmed values, rather than the raw OCR proposal, populate the
mapped collection fields `country`, `denomination`, and `year`. Grade remains
empty and outside the OCR workflow.

When the standalone adapter supplies a temporary capture package, the existing
managed-photo services own validation, copy, ownership markers, and rollback
attempts. A successful save must retain exactly the validated obverse and
reverse managed-photo references on the saved item. The adapter-owned source
is released exactly once after the workflow no longer needs it.

The persistence operation must use the existing shared collection/import lock
and the authoritative `CoinCollection` storage path. It may report success only
after `CoinCollection` reports a successful write. The GUI then reloads or
refreshes the existing collection view so the operator can verify and reopen
the saved record.

This bounded path does not introduce a new journal schema or claim stronger
crash durability than the reused `CoinCollection`, lock, snapshot, and
managed-image services currently provide. A failure before authoritative
collection publication must attempt owned-photo rollback. A rollback failure
or any state whose final publication cannot be proven is a recoverable/uncertain
failure, must be reported distinctly, and must never be presented as success.

### Relationship to Sprint 15 controlled mutation

Sprint 15 conditional mutation applies to fields on an existing authoritative
record. It is not a record-creation API and shall not be repurposed to create a
new `CoinItem` or attach a new managed-photo set.

If the standalone workflow detects a possible existing record, it may display
that duplicate evidence, but this bounded path must not update or overwrite the
record. Any later existing-record edit must enter the complete Sprint 14/15
chain: collection-change proposal, explicit approval, exact freshness evidence,
eligibility, immutable command, and conditional execution. No yes/no new-record
confirmation may bypass that chain.

This separation is the controlled-mutation integration boundary for the
amendment: new-record creation uses the existing collection insertion owner;
existing-record mutation remains fail-closed behind Sprint 15.

### Required user-visible outcomes

The standalone image workflow must distinguish:

- `SUCCESS`: the confirmed record and both managed photos were persisted and
  the collection view was refreshed;
- `UNRESOLVED`: review is incomplete or contains unresolved conflicts; no
  authoritative mutation occurred;
- `VALIDATION_ERROR`: selected input, review, confirmed observation, or mapped
  collection data failed validation; no authoritative mutation occurred;
- `RECOVERABLE_FAILURE`: persistence or managed-photo work failed without a
  proven clean terminal state; success is not shown and the safe message states
  that recovery or operator attention is required; and
- `CANCELLED`: the collector cancelled or rejected the workflow; no
  authoritative mutation occurred.

Safe messages must not expose private absolute paths, raw exception text, or
OCR/provider internals.

### Focused verification contract

Headless integration coverage for the primary standalone image entry must
prove all of the following with sanitized temporary fixtures:

1. the normal standalone image action selects OCR-enabled composition and
   reaches candidate review;
2. human-corrected values, not the raw proposals, are mapped and persisted;
3. cancellation/rejection before confirmation performs no collection or
   managed-photo mutation;
4. unresolved and validation failures are explicit and non-mutating;
5. managed obverse/reverse files and saved photo references remain valid after
   success;
6. a synchronous persistence/photo failure rolls back owned artifacts where
   provable, while rollback uncertainty is reported as recoverable failure;
7. reopening `CoinCollection` from the authoritative storage path returns the
   saved corrected record; and
8. the ordinary capture-package entry still selects the non-OCR default path.

Native Tk validation remains a manual Windows smoke test when the test
environment cannot genuinely exercise a display.

### Amendment exclusions

This amendment does not authorize:

- automatic approval, correction, confirmation, or mutation;
- updates to an existing collection record outside Sprint 15;
- changes to adversarial benchmarks, manifests, references, or blindness
  guarantees;
- OCR/provider redesign, provider fallback, cloud inference, grading,
  valuation, retrieval, embeddings, or visual-model work;
- a new persistence owner or schema;
- broad GUI or non-GUI refactoring; or
- claims of complete process-crash recovery beyond the reused services.

### Amendment implementation verification

**Status: `VERIFIED` on 2026-08-26.**

The bounded amendment is implemented by reusing the existing standalone-image
adapter, OCR-enabled pipeline selection, candidate/conflict review, confirmed
observation mapping/readiness, `CoinCollection` persistence, and managed-photo
services. The visible standalone action is `Import Coin Images...`; the
ordinary capture-package action remains on `ImportPipelineMode.DEFAULT`.

Verified production changes are limited to:

- the normal standalone image-import menu label and its retained OCR route;
- a typed `ReviewedCoinRecoveryRequiredError` emitted when owned managed-photo
  rollback cannot prove a clean terminal state; and
- safe desktop presentation that distinguishes recovery-required failure from
  ordinary save failure without rendering private exception details.

The focused headless integration fixture proves corrected year `1969` is
persisted instead of either raw OCR proposal (`1967` or `1968`), both managed
photos remain valid, the temporary source is released, and reopening the
authoritative collection returns the saved record. Separate tests prove
cancel/reject and unresolved review cause no mutation, real cleanup failure
emits the typed recovery state, private paths are redacted, and capture-package
default selection remains non-OCR.

Validation executed with the configured project Python:

```powershell
python -m unittest tests.test_coin_collection_gui_ocr_integration
python -m unittest tests.test_coin_collection_gui_entrypoint tests.test_coin_collection_gui_ocr_integration tests.test_desktop_import_pipeline_selection tests.test_desktop_ocr_review_integration tests.test_desktop_ocr_review_persistence tests.test_desktop_ocr_review_persistence_controls tests.test_reviewed_coin_collection_entry tests.test_standalone_image_intake tests.test_workflow_confirmed_observation_mapper tests.test_workflow_confirmed_observation_readiness tests.test_workflow_collection_change_plan_builder tests.test_workflow_collection_change_approval_models tests.test_workflow_collection_mutation_eligibility tests.test_workflow_collection_mutation_command tests.test_workflow_collection_mutation_execution
python -m compileall -q capture_import collection_management coin_collection_gui.py tests/test_coin_collection_gui_ocr_integration.py
python -m unittest discover -s . -p "test_*.py"
```

Recorded results:

```text
Primary GUI integration: 20 passed, 0 skipped, 0 failures, 0 errors
Affected validation:      383 passed, 0 skipped, 0 failures, 0 errors
Compilation:              passed
Root discovery:           4,663 total; 4,639 passed; 23 skipped;
                          1 known unrelated failure; 0 errors
```

The root failure is the pre-existing local-LLM metric debt in
`tests.test_local_llm_resolver_batch_cli.LocalLLMResolverBatchCLITests.test_model_comparison_is_json_serializable_and_separate_per_model`:
expected `full_identity_accuracy == 1.0`, received `0.75`. No unrelated code
was changed to alter that result.

Independent architecture and scope review conclusion: **PASS WITH NOTES**.
The implementation preserves the explicit confirmation boundary, default
capture-package behavior, existing-record Sprint 15 boundary, non-GUI
behavior, and adversarial benchmark/reference/blindness files. Native Tk
interaction was not exercised by headless automation and remains the manual
check below.

### Exact Windows native-Tk smoke test

Run this only with local coin images the operator is authorized to inspect.
Do not use or upload the uncertain `test_coins/` images.

1. Open PowerShell and run:

   ```powershell
   Set-Location "C:\Users\adamo\OneDrive\Documentos\Projects\coin-analyzer"
   python .\coin_collection_gui.py
   ```

2. Wait for the main window to finish startup recovery and confirm the File
   menu actions are enabled.
3. Choose **File > Import Coin Images...**.
4. Select one valid local JPG/PNG obverse image and one valid local JPG/PNG
   reverse image. Confirm the capture-package progress window reaches the OCR
   candidate-review dialog without offering the ordinary package Import
   button.
5. Review every candidate. Enter an explicit valid correction such as `1969`
   for both year candidates, correct/approve country and denomination, and
   finish the candidate and conflict reviews. Do not accept an unresolved
   required field.
6. At **Confirm Reviewed Coin**, verify the displayed country, denomination,
   and corrected year are exact. Choose **No**. Confirm no new collection row
   appears.
7. Repeat steps 3–5 with the same corrections. At **Confirm Reviewed Coin**,
   choose **Yes**. Confirm **Reviewed Coin Saved** appears and the corrected
   record is visible in the collection table.
8. Select the new row and choose **View Details**. Verify the corrected fields
   and both FRONT/BACK photo entries are present and viewable.
9. Close and restart the application with the command from step 1. Select the
   saved row and choose **View Details** again to verify the authoritative
   record and managed photos reopen.
10. Run one final import, defer a required candidate or leave a conflict
    unresolved, and finish the review. Confirm an incomplete/unresolved warning
    appears and no collection row is added.

The automated suite covers clean persistence failure, private-detail
redaction, and real rollback uncertainty; the manual smoke test must not
induce disk or cleanup failure by damaging the local collection.

## Motivation

The repository already contains substantial OCR-related architecture and tests for:

- OCR execution composition and provider contracts;
- candidate and conflict review domain/services;
- review-session persistence and resume contracts;
- confirmed-observation mapping and readiness assessment;
- field-intelligence assessment orchestration; and
- controlled collection-planning and mutation boundaries.

However, the production desktop flow does not yet wire these components end to end as one operator-visible workflow. Sprint 20 is a wiring and orchestration sprint, not an algorithm-invention sprint.

## Current Implemented Workflow

### Current production import flow

The real desktop production flow today is:

desktop capture/import
→ non-OCR image-processing pipeline
→ import preview/commit

Current entry is `CoinCollectionGUI.import_capture_package()` in `coin_collection_gui.py`, which opens `CapturePackageImportDialog` in `capture_import/ui.py`. That dialog currently executes `build_image_processing_pipeline()` from `capture_import/workflow_stages.py`, not the opt-in OCR composition.

### Separate current confirmed-observation behavior

Separately, on manual collection save, `CoinCollectionGUI.record_detection_observation_after_save()` appends a simplified detection/save outcome into `ConfirmedObservationStore` (`confirmed_observations.py`).

This is not the Sprint 10–16 reviewed OCR session pipeline and does not currently represent end-to-end OCR review wiring.

## Target Workflow

Sprint 20 target workflow:

capture/import
→ explicit OCR-enabled composition
→ OCR execution
→ candidate/conflict review
→ save/resume review session
→ confirmed-observation mapping
→ operator confirmation checkpoint
→ readiness assessment
→ field-intelligence assessment
→ operator opens planning
→ collection-change planning preview
→ stop

No automatic mutation may occur in this workflow.

## Operator Checkpoints

Mandatory human gates:

1. Collector explicitly starts OCR-enabled workflow.
2. Collector reviews candidate/conflict decisions.
3. Collector explicitly completes or saves/defer/cancels the review session.
4. Collector explicitly accepts confirmed-observation results before downstream assessment.
5. Collector explicitly opens planning preview.
6. Collection mutation remains outside Sprint 20 and cannot occur automatically.

## Proposed Owning Integration Service

Recommended owner: a new application-service module under `capture_import/` (proposed file, exact name to be finalized during implementation review).

Responsibility:

Coordinate workflow stages and transport DTOs between UI and existing domain/application services.

It must not:

- contain OCR algorithms;
- contain field-intelligence rules;
- implement persistence;
- own collection mutation;
- decide readiness policy;
- own GUI widgets; or
- bypass operator checkpoints.

Dependency direction:

GUI
→ Sprint 20 integration service
→ existing workflow/domain services
→ explicit persistence seams
→ collection-management planning boundary

Forbidden reverse dependencies:

- domain → GUI
- persistence → workflow policy
- collection_management → OCR review UI
- OCR/readiness/intelligence → collection mutation
- direct collection mutation from the Sprint 20 service

## Phase 1 — Desktop Entry and OCR Composition Selection

### Exact capability

Add an explicit desktop path that can invoke OCR-enabled composition for import-review flow while preserving the existing non-OCR default path.

### Expected files

- `capture_import/ui.py`
- proposed Sprint 20 integration service module under `capture_import/`
- `coin_collection_gui.py` (only minimal entry-point wiring)

### Contracts

- Existing import-dialog/request contracts remain authoritative.
- OCR-enabled path must use existing opt-in composition/runtime contracts.
- Default path remains `build_image_processing_pipeline()`.

### Tests

- Focused integration tests around desktop import entry and composition selection.
- Existing OCR composition/runtime tests remain green.
- Boundary tests that assert default non-OCR import path remains unchanged.

### Visible behavior

Yes. Collector can explicitly choose OCR-enabled workflow entry. Existing non-OCR import continues unchanged.

### Stop condition

Explicit OCR desktop entry exists and default non-OCR path is unchanged.

## Phase 2 — Review Session Orchestration and Persistence/Resume

### Exact capability

Wire candidate/conflict review orchestration with explicit save/resume/abandon/complete lifecycle using existing review-session persistence contracts.

### Required behavior

- Source fingerprint enforcement on resume.
- Unsupported/incompatible persisted schema fails closed.
- No silent coercion of persisted review state.

### Expected files

- proposed Sprint 20 integration service module under `capture_import/`
- `capture_import/desktop_ocr_review_*.py` orchestration call sites as needed
- `capture_import/ui.py` or bounded desktop orchestration seam where invoked

### Tests

- Review orchestration integration tests.
- Persistence/resume tests including:
  - stale fingerprint mismatch,
  - unsupported schema,
  - not-resumable lifecycle states,
  - explicit abandon/complete transitions.
- Headless GUI tests for review/persistence controls.

### Stop condition

Review sessions can be explicitly saved, resumed, abandoned, and completed with fail-closed validation and no hidden state transitions.

## Phase 3 — Confirmed Observation and Readiness Handoff

### Exact capability

Map completed reviewed OCR session output into confirmed observations, then execute readiness assessment.

### Required behavior

- Operator acceptance checkpoint before downstream handoff.
- No partial output on mapping/readiness failure.
- No collection mutation path.

### Expected files

- proposed Sprint 20 integration service module under `capture_import/`
- bounded invocation wiring for existing confirmed-observation mapper/readiness services

### Tests

- Mapper/readiness integration tests from reviewed-session output.
- Negative-path tests for incomplete review and invalid handoff conditions.
- No-mutation assertion tests.

### Stop condition

Collector can inspect and explicitly accept confirmed-observation handoff; readiness result is generated or fails with explicit typed error and no partial side effect.

## Phase 4 — Field Intelligence Presentation

### Exact capability

Invoke existing field-intelligence orchestrator on ready confirmed observations and present deterministic findings to the collector.

### Required behavior

- Deterministic findings ordering and display.
- No mutation and no hidden persistence.

### Expected files

- proposed Sprint 20 integration service module under `capture_import/`
- bounded presentation wiring in existing desktop entry surface

### Tests

- Field-intelligence orchestration integration tests.
- Presentation tests for deterministic findings output.
- Failure-path tests for evaluator exceptions (fail closed).

### Stop condition

Collector can inspect field-intelligence findings from accepted ready observations; failures are explicit and non-mutating.

## Phase 5 — Controlled Planning Handoff

### Exact capability

Provide an explicit operator action to request planning-preview handoff into collection-management planning boundary.

### Required behavior

- planning artifacts only;
- no execution path; and
- no mutation.

### Expected files

- proposed Sprint 20 integration service module under `capture_import/`
- bounded planning handoff adapters/callers

### Tests

- Planning-preview handoff integration tests.
- Boundary tests proving no execution/mutation invocation.
- Failure-path tests for planning handoff errors.

### Stop condition

Collector can explicitly open planning preview and inspect artifacts. Collection remains unchanged.

### Approved deferral policy

Phase 5 is the first approved deferral candidate if scope pressure appears. Deferral must be explicit in governance documentation and must not invalidate Phases 1–4.

## Failure and Recovery Semantics

All stages are fail-closed.

- OCR provider unavailable: surface typed provider failure; no fallback mutation.
- Malformed OCR output: reject output via existing validation; preserve source package and collection.
- Review cancellation: preserve only already-approved explicit saves; otherwise keep session transient and non-mutating.
- Persistence write failure: return explicit failure; keep last valid persisted session unchanged.
- Unsupported review schema: reject load/resume; no coercion.
- Source fingerprint mismatch: reject resume as stale; no merge/override.
- Confirmed-observation mapping failure: no partial mapped result committed.
- Readiness failure: no downstream assessment/hand-off; explicit error.
- Field-intelligence failure: no planning handoff; explicit error.
- Planning-preview failure: no execution path and no mutation side effect.

Source package, reviewed evidence, and collection data remain unchanged unless an already-approved explicit persistence action succeeds.

## Persistence Ownership

Sprint 20 preserves existing persistence ownership:

- Import transaction persistence: existing capture-import durability stack.
- OCR review-session persistence: existing OCR review persistence repository/service stack.
- Confirmed-observation persistence: existing `ConfirmedObservationStore`.
- Collection persistence: existing `CoinCollection` persistence and conditional mutation seam.

Sprint 20 introduces no hidden persistence and no new persistence owner.

## User-Visible Contract

The collector may:

- explicitly start OCR-assisted import;
- review candidate/conflict evidence;
- save and resume;
- defer;
- cancel;
- inspect confirmed observations;
- accept or reject downstream handoff;
- inspect readiness/intelligence; and
- open a planning preview.

The system must never:

- auto-approve OCR evidence;
- auto-complete review;
- silently coerce incompatible saved state;
- silently switch providers;
- mutate the collection automatically; or
- infer missing findings after a failure.

## Explicit Non-Goals

- no automatic collection mutation
- no new OCR provider
- no Ollama integration
- no grading prediction changes
- no grading dataset work
- no new schema version unless separately approved
- no broad GUI refactor
- no unrelated CollectorWorkspace consolidation
- no market valuation work
- no provider fallback behavior not already approved

## Acceptance Criteria

### Sprint-level criteria

1. Explicit OCR desktop path exists.
2. Default non-OCR path is unchanged.
3. Review persistence/resume works with fail-closed checks.
4. Confirmed-observation mapping is operator-gated.
5. Readiness and intelligence results are inspectable.
6. Planning preview is explicit and non-mutating (or explicitly deferred per Phase 5 policy).
7. No automatic mutation path exists.
8. Existing boundary tests remain green.
9. Full regression passes.

### Phase-level criteria

- Phase 1: explicit OCR entry path added; default import path unchanged.
- Phase 2: save/resume/abandon/complete lifecycle validated with fingerprint/schema enforcement.
- Phase 3: reviewed-session mapping + readiness handoff is operator-gated and fail-closed.
- Phase 4: deterministic field-intelligence presentation is available and non-mutating.
- Phase 5: explicit planning preview handoff produces artifacts only and never executes mutation.

## Test Strategy

- Unit tests for affected orchestration adapters and DTO transport.
- Application-service tests for Sprint 20 integration service behavior.
- Integration tests across import → OCR → review → persistence/resume → readiness/intelligence handoff.
- Persistence/resume tests for stale fingerprint, unsupported schema, and lifecycle constraints.
- Headless GUI tests for review and persistence controls.
- Package-boundary tests to preserve module-direction rules.
- No-mutation tests proving no automatic mutation path exists.
- Manual desktop acceptance checks for operator checkpoints and visible flow.
- Authoritative full regression command:
  - `.\.venv\Scripts\python.exe -m unittest discover -s . -p "test_*.py"`

## Risks and Scope Controls

Primary risks:

- GUI/controller coupling growth;
- orchestration duplication across entry points;
- persistence ownership bleed;
- schema drift between persisted review and runtime DTOs;
- stale resume state confusion;
- partial workflow state confusion;
- accidental mutation path introduction; and
- excessive sprint scope.

Scope-control rule:

One bounded implementation phase per reviewed commit sequence. No phase may begin until the previous phase is focused-test green and its architecture remains valid.

## Definition of Done

Sprint 20 is done only when:

- required phases are complete;
- Phase 5 is either complete or explicitly deferred with documentation;
- operator checkpoints are preserved;
- no automatic mutation path exists;
- focused tests pass;
- full regression passes;
- governance docs are reconciled;
- PR CI passes; and
- changes are merged to `main`.

## Implementation Sequence

1. freeze architecture
2. review architecture
3. create implementation branch
4. Phase 1
5. audit
6. Phase 2
7. audit
8. Phase 3
9. audit
10. Phase 4
11. audit
12. Phase 5 or documented deferral
13. full regression
14. governance closeout
15. PR/CI/merge
