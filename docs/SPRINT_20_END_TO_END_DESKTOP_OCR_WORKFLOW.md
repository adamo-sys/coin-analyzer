# Sprint 20 — End-to-End Desktop OCR Workflow

## Status

This document is the frozen architecture specification for Sprint 20.
Implementation has not started.

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
