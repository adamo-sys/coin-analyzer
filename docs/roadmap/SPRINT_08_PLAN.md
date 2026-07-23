# Sprint 8 — Image Processing Pipeline

## Objective

Extend the Sprint 7 deterministic import workflow with internal image-processing stages that run before the durable transaction boundary. Produce analysis-ready, normalized images and derived metadata so that downstream sprints (OCR, AI grading) operate on a canonical representation, while preserving all Sprint 5–7 transaction, recovery, cancellation, and event semantics.

## Architecture Dependency

| Foundation | Reference |
|---|---|
| Sprint 7 baseline | Commit `f73f29f` |
| Sprint 6 baseline | Commit `fd1682e` |
| Sprint 5 baseline | Commit `55817fd` |
| Architecture | Schema-2 Durable Persistence |
| Frozen spec hash | `A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4` |
| ADR | `docs/adr/ADR-007-internal-processing-stage-framework.md` (Accepted) |
| ADR | `docs/adr/ADR-008-image-processing-pipeline.md` (Proposed) |
| Builds on | Sprint 7 `ProcessingStage` protocol and `ProcessingPipeline` |

## Scope Boundary

**In scope:** Pre-import image processing inside the Sprint 7 pipeline.

**Subject-type extensibility note:** Sprint 8 targets coin photographs, but the stage protocol, quality metrics, and duplicate detection are geometry-neutral. `coin_id` in pipeline records and paths is a generic item identifier. Crop detection uses a coin-oriented circular strategy with full-image fallback; future subjects may use different geometry-specific crop strategies without protocol changes.

**Explicitly out of scope:**

**Explicitly out of scope:**
- Post-import collection image analysis (`image_assessment.py`, `image_analyzer.py` workflows on `CoinItem`).
- OCR and metadata extraction (Sprint 9).
- AI grading (Sprint 10).
- Third-party plugins, dynamic stage discovery, parallel execution, GPU acceleration, cloud processing.
- Changes to Schema-2 durable persistence, recovery, or event semantics.

## Deliverables

### Unit 1: Contract and ADRs
- `docs/roadmap/SPRINT_08_PLAN.md` — this document
- `docs/adr/ADR-008-image-processing-pipeline.md` — design record
- Required updates to `docs/architecture/IMPORT_WORKFLOW.md`
- Optional roadmap/changelog draft updates if convention requires
- **Status:** In progress (this unit)

### Unit 2: Image normalization stage
- `capture_import/workflow_image_normalization.py` — `ImageNormalizationStage`
- `tests/test_workflow_image_normalization.py` — decode failures, dimension caps, EXIF stripping, deterministic output, workspace containment
- **Objective:** Convert every validated capture-package JPEG/PNG into a canonical normalized JPEG artifact in the workspace.

### Unit 3: Image quality scoring stage
- `capture_import/workflow_image_quality.py` — `ImageQualityScoringStage`
- `tests/test_workflow_image_quality.py` — sharpness, contrast, brightness, blown highlights, readiness decisions, missing artifact handling
- **Objective:** Score normalized images with deterministic Level A metrics and emit JSON-safe quality metadata.

### Unit 4: Crop detection stage
- `capture_import/workflow_crop_detection.py` — `CropDetectionStage`
- `tests/test_workflow_crop_detection.py` — coin region detection, fallback to full image, oversized/empty crop rejection, deterministic rectangles
- **Objective:** Detect the coin region in normalized images and emit crop rectangles plus optional cropped artifacts.

### Unit 5: Obverse/reverse pairing stage
- `capture_import/workflow_obverse_reverse_pairing.py` — `ObverseReversePairingStage`
- `tests/test_workflow_obverse_reverse_pairing.py` — missing roles, dimension/aspect consistency, histogram sanity checks, deterministic scores
- **Objective:** Confirm that the front and reverse images for each coin plausibly depict opposite sides of the same object.

### Unit 6: Image duplicate detection stage
- `capture_import/workflow_image_duplicates.py` — `ImageDuplicateDetectionStage`
- `tests/test_workflow_image_duplicates.py` — within-package exact duplicates, package-vs-collection hash matches, bounded existing-item lookup, new duplicate category semantics
- **Objective:** Emit image-derived duplicate signals that supplement existing `PackageDuplicateDetectionService` evidence.

### Unit 7: Adapter amendment and pipeline integration
- `capture_import/workflow_adapter.py` — consume `PreparedImport.files` for normalized images
- `capture_import/workflow_stages.py` — `build_reference_pipeline()` extended deterministically
- `capture_import/coordinator.py` — new coordinator overload/argument accepting preprocessed image artifacts (only if required by adapter amendment)
- `tests/test_workflow_image_integration.py` — end-to-end pipeline with normalized images crossing the adapter boundary
- **Objective:** Wire all Sprint 8 stages into the reference pipeline and amend the adapter so normalized images become durable inputs.

### Unit 8: Documentation, traceability, and release gate
- Update `CHANGELOG.md`
- Update `docs/roadmap/PRODUCT_ROADMAP.md` Sprint 8 status
- Update `docs/architecture/IMPORT_WORKFLOW.md` final traceability
- Independent review
- Full regression
- **Objective:** Close out Sprint 8 with synchronized documentation and a passing full-regression gate.

## Risks

| Risk | Mitigation |
|---|---|
| Durable-state leakage by image stages | Frozen ADR-007/ADR-008 invariant: workspace-only writes; adapter is the sole bridge. |
| Coordinator API change destabilizes imports | Adapter amendment is localized; existing prepare-from-source path remains available for callers that do not use the extended pipeline. |
| OpenCV/PIL non-determinism | Define tolerant contracts; pin preprocessing parameters; tests assert bounded properties, not cross-library byte equality. |
| Source archive mutation | Stages open images read-only; original archive bytes never modified. |
| Confusing pre-import vs post-import seams | Sprint 8 scope is explicitly pre-import only; post-import analysis remains in `image_assessment.py`. |
| Image duplicate detection false positives | Exact normalized-byte hashes only in Sprint 8; perceptual hashing deferred. |
| Cancellation during slow image I/O | Cooperative boundaries between stages; each stage is atomic. |
| Breaking existing preview/duplicate logic | Existing `PackageDuplicateDetectionService` categories remain; new categories are additive. |

## Exit Criteria

| Criterion | Required result |
|---|---|
| Ordered execution | Image stages execute exactly once in declared order |
| Failure handling | First failed stage halts execution and identifies `stage_id` |
| Cancellation | Safe before, between, and after image-processing stages |
| Transaction handoff | Occurs exactly once after successful preprocessing |
| Durable safety | Normalized image artifacts cross the boundary only through `PreparedImport.files` consumed by the adapter |
| Recovery | Existing recovery matrix remains unchanged and passing |
| Events | Pipeline lifecycle events remain deterministic and queryable |
| Workspace | Owned resources cleaned on all terminal paths |
| Compatibility | Existing imports preserve externally observable behavior when image stages are disabled or not present |
| Regression | At least Sprint 7 baseline of 2045 passing tests |
| Architecture | Frozen specification hash unchanged |
| Documentation | Plan, architecture, ADR, changelog, and traceability synchronized |
| Review | No unresolved blocking or major findings |

## Closeout Traceability Matrix

| Unit | Planned deliverables | Implemented | Focused tests | Commit(s) | Status |
|---|---|---|---|---|---|
| 1 | Contract, architecture, ADR | `SPRINT_08_PLAN.md`, `ADR-008-...md`, `IMPORT_WORKFLOW.md` updates | — (docs only) | TBD | PLANNED |
| 2 | Image normalization stage | `capture_import/workflow_image_normalization.py` | `test_workflow_image_normalization.py` | TBD | PLANNED |
| 3 | Image quality scoring stage | `capture_import/workflow_image_quality.py` | `test_workflow_image_quality.py` | TBD | PLANNED |
| 4 | Crop detection stage | `capture_import/workflow_crop_detection.py` | `test_workflow_crop_detection.py` | TBD | PLANNED |
| 5 | Obverse/reverse pairing stage | `capture_import/workflow_obverse_reverse_pairing.py` | `test_workflow_obverse_reverse_pairing.py` (48 run, 2 expected Windows skips) | `6a42ab0`, `dc6363b` | VERIFIED |
| 6 | Image duplicate detection stage | `capture_import/workflow_image_duplicates.py` | `test_workflow_image_duplicates.py` (31 passed) | `456db79` | VERIFIED |
| 7 | Adapter amendment and pipeline integration | `workflow_adapter.py`, `workflow_stages.py`, optional `coordinator.py` | `test_workflow_image_integration.py` | TBD | PLANNED |
| 8 | Documentation, traceability, release gate | `CHANGELOG.md`, `PRODUCT_ROADMAP.md`, traceability updates | Full regression | TBD | PLANNED |

## Exit Criteria Verification

| Criterion | Required result | Verified result (Unit 8 closeout) |
|---|---|---|
| Ordered execution | Image stages execute exactly once in declared order | Pending |
| Failure handling | First failed stage halts execution and identifies `stage_id` | Pending |
| Cancellation | Safe before, between, and after image-processing stages | Pending |
| Transaction handoff | Occurs exactly once after successful preprocessing | Pending |
| Durable safety | Normalized image artifacts cross boundary only through `PreparedImport.files` | Pending |
| Recovery | Existing recovery matrix unchanged and passing | Pending |
| Events | Pipeline lifecycle events deterministic and queryable | Pending |
| Workspace | Owned resources cleaned on all terminal paths | Pending |
| Compatibility | Existing imports preserve observable behavior | Pending |
| Regression | At least Sprint 7 baseline of 2045 passing tests | Pending |
| Architecture | Frozen specification hash unchanged | Pending |
| Documentation | Plan, architecture, ADR, changelog, traceability synchronized | Pending |
| Review | No unresolved blocking or major findings | Pending |

## Unit Detail

### Unit 1: Contract and ADRs

**Objective:** Authorize the Sprint 8 architecture and planning package.

**Files expected to change:**
- `docs/adr/ADR-008-image-processing-pipeline.md` (new)
- `docs/roadmap/SPRINT_08_PLAN.md` (new)
- `docs/architecture/IMPORT_WORKFLOW.md` (update)
- `docs/roadmap/PRODUCT_ROADMAP.md` (optional status update)
- `CHANGELOG.md` (optional draft entry)

**Contracts introduced or modified:**
- `ADR-008` — image-processing pipeline boundaries, stage order, image contracts, duplicate detection approach.
- `IMPORT_WORKFLOW.md` — extended pipeline overview, image-stage data contracts, adapter amendment contract.

**Implementation constraints:**
- No production code changes.
- No test changes.
- No commits without explicit authorization.

**Focused tests:** None (documentation-only unit).

**Regression gate:** None required; documentation changes do not affect executable artifacts.

**Acceptance criteria:**
- ADR and plan are internally consistent.
- All referenced paths and symbols exist in the repository.
- Scope boundary is explicit and unambiguous.
- Adapter amendment is described without bypassing coordinator ownership.

**Stop conditions:**
- Architecture contradiction with ADR-007 or frozen durable-persistence spec.
- Unresolved ambiguity about pre-import vs post-import scope.
- Unresolved ambiguity about whether normalized images replace raw bytes durably.

**Documentation obligations:**
- ADR-008 accepted status must be updated before Unit 2 begins.
- IMPORT_WORKFLOW.md must reflect the amended adapter contract.

**Required pre-commit evidence:**
- Independent review of the planning package.
- `git diff --check` clean.
- All referenced paths verified.

---

### Unit 2: Image Normalization Stage

**Objective:** Convert validated capture-package JPEG/PNG images into deterministic, canonical normalized JPEG artifacts inside the workspace.

**Files expected to change:**
- `capture_import/workflow_image_normalization.py` (new)
- `tests/test_workflow_image_normalization.py` (new)

**Contracts introduced or modified:**
- `ImageNormalizationStage` implementing `ProcessingStage`.
- Normalized artifact layout: `normalized/<coin_id>/<role>.jpg`, where `<role>` is the lowercase `ImageRole` value.
- Metadata schema: `normalized_image_count`, `normalized_formats`, per-image dimensions.

**Implementation constraints:**
- Read images from `request.source` archive only; no direct filesystem access outside workspace.
- Write artifacts only into `StageInput.workspace`.
- Output JPEG, sRGB, EXIF stripped, quality 92, baseline (non-progressive).
- Maximum dimensions bounded by existing `MAX_IMAGE_DIMENSION` and `MAX_IMAGE_PIXELS`.
- Reuse `CapturePackageArchiveReader` and `CapturePackageMediaValidator` concepts where applicable.
- No coordinator/transaction/lock/recovery imports.

**Focused tests:**
- `python -m unittest tests.test_workflow_image_normalization`
- Decode failure handling
- Dimension capping
- EXIF stripping verification
- Deterministic filename generation
- Workspace path containment
- Missing upstream `prepared-manifest` artifact handling

**Regression gate:**
- `python -m unittest tests.test_workflow_models tests.test_workflow_pipeline tests.test_workflow_execution tests.test_workflow_reference_stages`

**Acceptance criteria:**
- Stage produces valid JPEG artifacts for every supported input image.
- Stage fails fast with `StageExecutionError` on unrecoverable decode errors.
- Stage fails with `StageContractError` when required upstream artifacts are missing.
- No durable state is mutated.

**Stop conditions:**
- Need to change `CapturePackageMediaValidator` or `ImageRole` semantics.
- Cannot prove workspace path containment for output artifacts.
- Non-deterministic output across identical inputs.

**Documentation obligations:**
- Update `SPRINT_08_PLAN.md` Unit 2 row with commit and test counts.

**Required pre-commit evidence:**
- Focused tests pass.
- Independent review of the stage.

---

### Unit 3: Image Quality Scoring Stage

**Objective:** Compute deterministic Level A quality metrics on normalized images and emit JSON-safe metadata.

**Files expected to change:**
- `capture_import/workflow_image_quality.py` (new)
- `tests/test_workflow_image_quality.py` (new)

**Contracts introduced or modified:**
- `ImageQualityScoringStage` implementing `ProcessingStage`.
- Quality metadata schema: sharpness, contrast, brightness, resolution, blown highlight ratio, readiness score, readiness decision, confidence.

**Implementation constraints:**
- Input is the normalized artifact mapping from Unit 2.
- Metadata-only stage (no new artifacts).
- Adapt metrics from `image_assessment.py` but remove `CoinItem` dependency.
- Use OpenCV with fixed parameters; round scores to integers for determinism.
- No durable state access.

**Focused tests:**
- `python -m unittest tests.test_workflow_image_quality`
- Blurred, low-contrast, overexposed, and valid images
- Missing normalized artifact handling
- Metadata validation
- Deterministic scoring

**Regression gate:**
- `python -m unittest tests.test_workflow_models tests.test_workflow_pipeline tests.test_workflow_execution tests.test_workflow_reference_stages tests.test_workflow_image_normalization`

**Acceptance criteria:**
- Stage emits valid JSON-safe quality metadata for every normalized image.
- Blocking quality issues are recorded but do not halt the pipeline unless configured to do so.
- Stage fails with `StageContractError` when normalized artifacts are missing.

**Stop conditions:**
- Quality metrics require post-import `CoinItem` data.
- Metrics are non-deterministic across runs.

**Documentation obligations:**
- Update `SPRINT_08_PLAN.md` Unit 3 row.

**Required pre-commit evidence:**
- Focused tests pass.
- Independent review.

---

### Unit 4: Crop Detection Stage

**Objective:** Detect the coin region in normalized images and emit crop rectangles plus optional cropped artifacts.

**Files expected to change:**
- `capture_import/workflow_crop_detection.py` (new)
- `tests/test_workflow_crop_detection.py` (new)

**Contracts introduced or modified:**
- `CropDetectionStage` implementing `ProcessingStage`.
- Crop metadata schema: `x`, `y`, `width`, `height`, `crop_confidence`.
- Cropped artifact layout: `cropped/<coin_id>/<role>.jpg`, where `<role>` is the lowercase `ImageRole` value.

**Implementation constraints:**
- Rule-based or simple contour heuristic only; no ML inference in Sprint 8.
- If confidence is below threshold, copy the normalized image into `cropped/<coin_id>/<role>.jpg` and set `crop_confidence` to `0.0`; the crop rectangle covers the full normalized image.
- Cropped output must respect `MAX_IMAGE_DIMENSION` and `MAX_IMAGE_PIXELS`.
- Write only into workspace; avoid duplicate relative paths in `PreparedImport.files`.

**Focused tests:**
- `python -m unittest tests.test_workflow_crop_detection`
- Coin on uniform background
- Full-frame coin (fallback)
- Empty/oversized crop rejection
- Deterministic rectangle output
- Workspace containment

**Regression gate:**
- `python -m unittest tests.test_workflow_models tests.test_workflow_pipeline tests.test_workflow_execution tests.test_workflow_reference_stages tests.test_workflow_image_normalization tests.test_workflow_image_quality`

**Acceptance criteria:**
- Stage emits crop metadata for every normalized image.
- Stage emits a valid cropped artifact when confidence is high.
- Stage falls back to the normalized image when confidence is low.
- Stage fails with `StageContractError` on invalid crop geometry.

**Stop conditions:**
- Crop detection requires ML model or external data.
- Cannot prove cropped artifacts remain path-contained.

**Documentation obligations:**
- Update `SPRINT_08_PLAN.md` Unit 4 row.

**Required pre-commit evidence:**
- Focused tests pass.
- Independent review.

---

### Unit 5: Obverse/Reverse Pairing Stage

**Objective:** Confirm that the front and reverse images for each coin plausibly depict opposite sides of the same object.

**Files expected to change:**
- `capture_import/workflow_obverse_reverse_pairing.py` (new)
- `tests/test_workflow_obverse_reverse_pairing.py` (new)

**Contracts introduced or modified:**
- `ObverseReversePairingStage` implementing `ProcessingStage`.
- Pairing metadata schema: `paired` boolean, `consistency_score`, `explanation`.

**Implementation constraints:**
- Compare dimensions, aspect ratios, and simple color histograms.
- Heuristic sanity check only; not identification.
- Require `FRONT` and `REVERSE` normalized/cropped artifacts per coin.
- Metadata-only stage.

**Focused tests:**
- `python -m unittest tests.test_workflow_obverse_reverse_pairing`
- Missing front or reverse role
- Mismatched dimensions/aspect ratios
- Consistent pairs
- Deterministic scores

**Regression gate:**
- `python -m unittest tests.test_workflow_models tests.test_workflow_pipeline tests.test_workflow_execution tests.test_workflow_reference_stages tests.test_workflow_image_normalization tests.test_workflow_image_quality tests.test_workflow_crop_detection`

**Acceptance criteria:**
- Stage emits pairing metadata for every coin with front and reverse images.
- Stage fails with `StageContractError` when required roles are missing.
- Pairing signal is deterministic and bounded.

**Stop conditions:**
- Pairing requires ML or external reference data.
- Cannot define deterministic comparison without collection context.

**Documentation obligations:**
- Update `SPRINT_08_PLAN.md` Unit 5 row.

**Required pre-commit evidence:**
- Focused tests pass.
- Independent review.

---

### Unit 6: Image Duplicate Detection Stage

**Objective:** Emit image-derived duplicate signals that supplement existing `PackageDuplicateDetectionService` evidence.

**Files expected to change:**
- `capture_import/workflow_image_duplicates.py` (new)
- `tests/test_workflow_image_duplicates.py` (new)
- `capture_import/enums.py` — possible new `DuplicateCategory` value(s)

**Contracts introduced or modified:**
- `ImageDuplicateDetectionStage` implementing `ProcessingStage`.
- New duplicate category: `NORMALIZED_MEDIA_HASHES`.
- Duplicate signal metadata schema matching existing `DuplicateCandidate` shape.

**Implementation constraints:**
- Compute exact SHA-256 hashes of normalized (or cropped, if high-confidence) image artifacts.
- Detect within-package exact duplicates.
- Compare package images against the durable collection via read-only lookup, bounded by `MAX_DUPLICATE_EXISTING_ITEMS`. No existing read-only collection image-descriptor service exists; Unit 6 must design this seam without loading full `CoinItem` objects.
- Do not mutate collection or audit state.
- No perceptual hashing in Sprint 8.

**Focused tests:**
- `python -m unittest tests.test_workflow_image_duplicates`
- Within-package exact duplicate
- Package-vs-collection hash match
- Bounded existing-item lookup
- New duplicate category semantics
- Missing artifact handling

**Regression gate:**
- `python -m unittest tests.test_workflow_models tests.test_workflow_pipeline tests.test_workflow_execution tests.test_workflow_reference_stages tests.test_workflow_image_normalization tests.test_workflow_image_quality tests.test_workflow_crop_detection tests.test_workflow_obverse_reverse_pairing`

**Acceptance criteria:**
- Stage emits deterministic duplicate signals.
- Existing duplicate categories remain unchanged.
- Collection lookup is read-only and bounded.
- Stage fails with `StageContractError` on missing artifacts.

**Stop conditions:**
- Need to modify `PackageDuplicateDetectionService` contract beyond additive categories.
- Need to write duplicate signals durably before collector confirmation.

**Documentation obligations:**
- Update `SPRINT_08_PLAN.md` Unit 6 row.
- Update `docs/architecture/IMPORT_WORKFLOW.md` duplicate-detection contract if needed.

**Required pre-commit evidence:**
- Focused tests pass.
- Independent review.

---

### Unit 7: Adapter Amendment and Pipeline Integration

**Objective:** Wire all Sprint 8 stages into the reference pipeline and amend the adapter so normalized images can become durable inputs.

**Files expected to change:**
- `capture_import/workflow_stages.py` — extend `build_reference_pipeline()`
- `capture_import/workflow_adapter.py` — consume `PreparedImport.files`
- `capture_import/coordinator.py` — optional new overload/argument for preprocessed image artifacts
- `tests/test_workflow_image_integration.py` (new)

**Contracts introduced or modified:**
- `build_reference_pipeline()` deterministic order now includes image stages.
- Adapter contract: normalized artifacts in `PreparedImport.files` are passed to the coordinator. Unit 7 must design a routing mechanism so the adapter can distinguish image artifacts from non-image artifacts (e.g., `prepared-manifest.json`). Options include: extending `PreparedFile` with `content_type`, passing the `StageArtifact` mapping alongside `PreparedImport`, or using deterministic path conventions/file extensions.
- Coordinator contract amendment (if needed) to accept a workspace of preprocessed images.

**Implementation constraints:**
- Preserve the existing prepare-from-source path for backward compatibility.
- Coordinator continues to own snapshots, validation, and transaction boundaries.
- Adapter remains a thin translation layer with no business logic.
- All image stages respect the same cancellation and error contracts as Sprint 7 stages.

**Focused tests:**
- `python -m unittest tests.test_workflow_image_integration`
- End-to-end pipeline execution with image stages
- Normalized images present in `PreparedImport.files`
- Adapter passes artifacts to coordinator
- Zero durable invocation on failure/cancellation
- Existing reference pipeline still works when image stages are omitted

**Regression gate:**
- `python -m unittest tests.test_workflow_models tests.test_workflow_pipeline tests.test_workflow_execution tests.test_workflow_workspace tests.test_workflow_integration tests.test_workflow_reference_stages tests.test_workflow_image_normalization tests.test_workflow_image_quality tests.test_workflow_crop_detection tests.test_workflow_obverse_reverse_pairing tests.test_workflow_image_duplicates`

**Acceptance criteria:**
- `build_reference_pipeline()` returns a deterministic pipeline with image stages in the documented order.
- `commit_prepared_import` consumes `PreparedImport.files` when preprocessed artifacts are present.
- Existing behavior is preserved when the legacy pipeline is used.
- No transaction invocation on failure or cancellation.

**Stop conditions:**
- Coordinator API change would break existing callers.
- Adapter must inspect artifact contents to route them.
- Cannot preserve coordinator ownership of snapshots.

**Documentation obligations:**
- Update `IMPORT_WORKFLOW.md` with the final integrated pipeline.
- Update `SPRINT_08_PLAN.md` Unit 7 row.

**Required pre-commit evidence:**
- Focused integration tests pass.
- Independent review.

---

### Unit 8: Documentation, Traceability, and Release Gate

**Objective:** Close out Sprint 8 with synchronized documentation and a passing full-regression gate.

**Files expected to change:**
- `CHANGELOG.md`
- `docs/roadmap/PRODUCT_ROADMAP.md`
- `docs/roadmap/SPRINT_08_PLAN.md`
- `docs/architecture/IMPORT_WORKFLOW.md` (final polish)

**Contracts introduced or modified:**
- None new; documentation synchronization only.

**Implementation constraints:**
- No production code changes.
- Status transitions from `IMPLEMENTED` to `VERIFIED` only after tests pass.

**Focused tests:** None new.

**Regression gate:**
- `python -m unittest discover -s . -p "test_*.py"` — must meet or exceed Sprint 7 baseline (2045 pass, 17 skipped).

**Acceptance criteria:**
- All Sprint 8 units show `VERIFIED` in the closeout traceability matrix.
- Full regression passes.
- Frozen spec hash unchanged.
- Independent review passed with no blocking or major findings.

**Stop conditions:**
- Full-regression failure not explained by the current unit.
- Documentation inconsistent with verified code.

**Documentation obligations:**
- Update all traceability matrices.
- Update `CHANGELOG.md` with Sprint 8 closeout entry.

**Required pre-commit evidence:**
- Full regression results.
- Independent review report.

## Stop Conditions

Stop and await direction if any of the following occur:

- Need to change Schema-2 journal or recovery semantics.
- Ambiguity over which layer owns durable writes.
- Duplicate or conflicting top-level events.
- Requirement for dynamic plugin loading or third-party image services.
- Source mutation during preprocessing.
- Inability to prove workspace path containment for image artifacts.
- Cancellation that can occur during an atomic durable transition.
- Required breaking change to `TransactionService` or `RecoveryService`.
- Full-regression failure not directly explained by the current unit.
- Scope pressure to begin OCR, AI grading, or post-import collection analysis under Sprint 8.
- Unresolved decision about whether normalized images replace raw archive bytes durably.

## Implementation Notes

- Stages are internal processing components, not public plugins.
- Stage ordering is explicit and deterministic.
- Stages return typed results rather than mutating a shared god context.
- `TransactionService` remains the sole owner of journals, durable writes, rollback, and commit.
- `RecoveryService` semantics remain unchanged.
- Stages may only write into workflow-owned, path-contained temporary workspaces.
- Pipeline failure or cancellation prevents transaction invocation.
- Cancellation is cooperative at stage boundaries.
- No OCR, AI, networking, GUI, dynamic loading, parallelism, retries, or caching in Sprint 8.
- Post-import image analysis (`image_assessment.py`, `image_analyzer.py`) remains independent of the Sprint 7/8 pipeline.

## Technical Debt to Avoid

| Shortcut | Resulting debt |
|---|---|
| Mutable `dict` passed through all stages | Hidden coupling and nondeterministic behavior |
| Stages writing directly to `coin_photos/collection` | Competing durability model |
| Bypassing `PreparedImport.files` to pass images to the coordinator | Silent circumvention of the adapter boundary |
| Generic `except Exception: pass` in image decoding | Concealed corruption and debugging failures |
| Perceptual hashing in Sprint 8 | Cross-version non-determinism and harder testing |
| Reimplementing archive reading/media validation | Divergent security semantics |
| Combining all image stages in one unit | Review becomes ineffective |
| Parallel image processing now | Cancellation and ownership complexity with little benefit |
