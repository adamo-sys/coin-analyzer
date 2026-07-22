# ADR-008: Image Processing Pipeline

- Status: Accepted (implementation begins in Sprint 8 Unit 2)
- Date: 2026-07-21

## Context

Sprint 7 (`docs/adr/ADR-007-internal-processing-stage-framework.md`) established an internal `ProcessingStage` protocol and deterministic `ProcessingPipeline` that runs before the durable transaction boundary. The reference pipeline (`PackageValidationStage`, `ManifestPreparationStage`) proves the design but performs no image processing.

`docs/roadmap/PRODUCT_ROADMAP.md` identifies Sprint 8 as the **Image Processing Pipeline**, with the following capabilities:

- Image normalization
- Crop detection
- Obverse/reverse pairing
- Duplicate detection improvements
- Image quality scoring

The roadmap explicitly states that Sprint 8 "Builds on: Sprint 7 processing-stage framework." This means the work belongs in the pre-import preparation pipeline, not in post-import collection analysis.

Two separate image-related seams already exist in the repository:

1. **Pre-import capture-package media** (`capture_import/media.py`, `capture_import/image_store.py`) — JPEG/PNG bytes inside the zip archive, validated at import time and copied into `coin_photos/collection/imports/<import_id>/`.
2. **Post-import collection analysis** (`image_assessment.py`, `image_analyzer.py`) — operates on `CoinItem`/`ItemPhoto` objects already in the collection.

Sprint 8 must not conflate these. The Sprint 7 framework owns the pre-import seam; post-import analysis is out of scope for Sprint 8.

## Decision

Extend the Sprint 7 pre-import pipeline with a bounded family of internal image-processing stages. All stages obey ADR-007 boundaries with one deliberate amendment: **preprocessed image artifacts are allowed to cross the durability boundary as `PreparedImport.files`**, so the durable collection contains normalized images instead of raw archive bytes.

### Scope boundary

**In scope for Sprint 8:**
- Pre-import processing of capture-package images before `TransactionService.execute()`.
- Stages that read from `ImportRequest.source` (the validated capture-package archive) and write normalized/derived artifacts into the caller-owned workspace.
- Producing `PreparedImport.files` and `PreparedImport.metadata` that the transaction delegate consumes.

**Explicitly out of scope:**
- Post-import collection image analysis (`image_assessment.py`, `image_analyzer.py` workflows on `CoinItem`).
- OCR and metadata extraction (Sprint 9).
- AI grading (Sprint 10).
- Third-party plugins, dynamic stage discovery, parallel execution, GPU acceleration, cloud processing.
- Modifying Schema-2 durable persistence, recovery, or event semantics.

### Pipeline contract

#### Stage order (recommended)

```text
PackageValidationStage
ManifestPreparationStage
ImageNormalizationStage
ImageQualityScoringStage
CropDetectionStage
ObverseReversePairingStage
ImageDuplicateDetectionStage
```

Rationale:
- Normalization runs first so every downstream stage works on a canonical pixel representation.
- Quality scoring can run on normalized images before or after crop detection; placing it before crop detection lets quality metrics inform whether cropping is attempted.
- Crop detection produces crop rectangles and optional cropped artifacts.
- Obverse/reverse pairing consumes normalized front/reverse images and emits consistency metadata.
- Duplicate detection consumes normalized images and hashes last, after all other preprocessing, so its evidence reflects the final pre-import representation.

#### Inputs and outputs

Every stage implements the existing `ProcessingStage` protocol:

```python
class ProcessingStage(Protocol):
    @property
    def stage_id(self) -> str: ...
    def execute(self, stage_input: StageInput) -> StageResult: ...
```

- **Inputs:** `StageInput.request.source` (the validated package), `StageInput.workspace`, and upstream `StageInput.artifacts`.
- **Outputs:** `StageResult.artifacts` (workspace-relative paths) and `StageResult.metadata` (JSON-safe mapping).
- No mutable shared context; no direct journal/lock/collection access.

#### Artifact ownership and lifecycle

- All image artifacts are written beneath `StageInput.workspace`.
- Artifact paths are validated by `_validate_relative_path` (no `..`, no absolute paths, no control characters).
- Each artifact is declared in `StageResult.artifacts` with a stable key and `content_type`.
- `ImportWorkflow` merges artifacts and metadata; duplicate keys across stages fail fast with `StageContractError`.
- `assemble_prepared_import` verifies every declared artifact is a plain regular file inside the workspace and converts it to `PreparedFile(expected_size=..., sha256=None)` (byte-integrity hashing remains with the Sprint 5/6 snapshot path).
- The workspace is cleaned on success, failure, and cancellation by the caller (`WorkflowWorkspace`).

#### Consuming `PreparedImport.files` downstream

ADR-007’s technical debt register notes that `workflow_adapter.py` currently forwards only `request.source` and ignores `PreparedImport.files`/`metadata`. Sprint 8 amends this:

- `commit_prepared_import` remains the sole application-layer bridge.
- It must pass the normalized image artifacts from `PreparedImport.files` to `PackageImportCoordinator` so that durable persistence uses the preprocessed bytes.
- Unit 7 must design a routing mechanism so the adapter can distinguish image artifacts from non-image artifacts (e.g., `prepared-manifest.json`). Options include: extending `PreparedFile` with `content_type`, passing the `StageArtifact` mapping alongside `PreparedImport`, or using deterministic path conventions/file extensions. The chosen mechanism must be documented before implementation.
- `PackageImportCoordinator.prepare()` may need a new overload or optional argument that accepts a verified workspace of preprocessed images instead of re-deriving everything from the raw archive.
- The coordinator continues to own snapshots, validation, and transaction boundaries. Stages do not call the coordinator.

This amendment is architectural: it requires an update to `docs/architecture/IMPORT_WORKFLOW.md` and a new contract between the adapter and the coordinator.

### Image contracts

#### General principles

- **Accepted input formats:** JPEG and PNG only (matching `capture_import/media.py` and `capture_import/limits.SUPPORTED_IMAGE_TYPES`).
- **Canonical output format:** JPEG with configurable quality, sRGB color space, EXIF stripped, progressive disabled (baseline), no embedded ICC profile transformations beyond sRGB normalization.
- **Deterministic behavior:** Same input bytes + same stage configuration produce identical output bytes on the same platform/library version. We do not claim cross-library-bit-exactness.
- **Bounded resources:** All dimensions, pixel counts, file sizes, and coin counts are bounded by existing `capture_import/limits.py` values.
- **Error model:** `StageExecutionError(stage_id, cause)` for unexpected failures; `StageContractError(stage_id, message)` for contract violations; original exceptions preserved via chaining.
- **Security considerations:** Stages open images read-only, reject links/reparse points via Sprint 5 filesystem primitives, validate paths, and never execute image-derived data. No external network calls. No dynamic code loading.
- **Test obligations:** Every stage requires deterministic unit tests, cancellation-boundary tests, and workspace-containment tests. Integration tests verify the extended pipeline and adapter amendment.

#### Image normalization stage

- **Stage ID:** `image-normalization`
- **Input:** Validated capture-package archive via `request.source`; upstream `prepared-manifest` artifact.
- **Output artifacts:** One normalized image per package coin photo under `normalized/<coin_id>/<role>.jpg`, where `<role>` is the lowercase `ImageRole` value (e.g., `front`, `reverse`, `edge`).
- **Output metadata:** `normalized_image_count`, `normalized_formats`, per-image dimensions.
- **Behavior:** Decode each referenced JPEG/PNG, resize so the larger dimension is at most a configured maximum (default derived from `MAX_IMAGE_DIMENSION`), convert to sRGB, strip EXIF, save as JPEG with quality 92, deterministic filename based on coin id and image role.
- **Limits:** Output dimensions ≤ input dimensions or a configured cap; output file size ≤ `MAX_IMAGE_SIZE`.
- **Stop condition:** If a referenced image cannot be decoded, fail fast with `StageExecutionError`.

#### Image quality scoring stage

- **Stage ID:** `image-quality-scoring`
- **Input:** Normalized image artifacts from `image-normalization`.
- **Output artifacts:** None (metadata-only stage).
- **Output metadata:** Per-photo quality record with `sharpness`, `contrast`, `brightness`, `resolution`, `blown_highlight_ratio`, `readiness_score`, `decision` (`READY`/`MAYBE`/`NOT_READY`), and `confidence` (`HIGH`/`MEDIUM`/`LOW`).
- **Behavior:** Reuse/adapt the deterministic Level A metrics from `image_assessment.py`, but scoped to workspace artifacts and expressed as JSON metadata. No `CoinItem` dependency.
- **Determinism:** Metrics computed with fixed OpenCV parameters; scores rounded to integers.
- **Stop condition:** If a normalized artifact is missing or unreadable, fail fast with `StageContractError`.

#### Crop detection stage

- **Stage ID:** `crop-detection`
- **Input:** Normalized image artifacts.
- **Output artifacts:** Cropped images under `cropped/<coin_id>/<role>.jpg`, where `<role>` is the lowercase `ImageRole` value.
- **Output metadata:** Per-photo crop rectangle (`x`, `y`, `width`, `height`) and a `crop_confidence` value.
- **Behavior:** Rule-based or simple contour heuristic to find the coin region. If a confident crop is found, the cropped region is saved under `cropped/<coin_id>/<role>.jpg`. If no confident crop is found, the stage copies the normalized image into `cropped/<coin_id>/<role>.jpg` and sets `crop_confidence` to `0.0`; the crop rectangle covers the full normalized image. This guarantees every downstream consumer has a single artifact path to read.
- **Determinism:** Fixed thresholds; no ML inference in Sprint 8.
- **Limits:** Cropped output dimensions bounded by `MAX_IMAGE_DIMENSION` and `MAX_IMAGE_PIXELS`.
- **Stop condition:** If cropping produces an empty or oversized region, fail closed with `StageContractError`.

#### Obverse/reverse pairing stage

- **Stage ID:** `obverse-reverse-pairing`
- **Input:** Normalized front (`ImageRole.FRONT`) and reverse (`ImageRole.REVERSE`) artifacts for each coin.
- **Output artifacts:** None.
- **Output metadata:** Per-coin pairing record with `paired` boolean, `consistency_score`, and `explanation`.
- **Behavior:** Compare dimensions, aspect ratios, and simple color histograms to confirm the two images plausibly depict opposite sides of the same coin. This is a heuristic sanity check, not identification.
- **Determinism:** Fixed comparison thresholds.
- **Stop condition:** Missing required roles trigger `StageContractError`.

#### Image duplicate detection stage

- **Stage ID:** `image-duplicate-detection`
- **Input:** Normalized image artifacts and manifest metadata.
- **Output artifacts:** None.
- **Output metadata:** Duplicate signal records keyed by source coin id, including `category`, `confidence`, `matched_desktop_ids`, and `reasons`.
- **Behavior:**
  - Compute exact SHA-256 hashes of normalized images for within-package duplicate detection.
  - Compare front/reverse hashes against the durable collection via a read-only lookup of existing collection image descriptors (read-only; no mutation). No such descriptor service currently exists; Unit 6 must design a bounded, read-only seam.
  - Emit new `DuplicateCategory` values if needed (e.g., `NORMALIZED_MEDIA_HASHES`).
- **Scope:** Within-package and package-vs-collection only.
- **Determinism:** Hash-based exact matching; no perceptual hashing in Sprint 8.
- **Stop condition:** If collection lookup fails, the stage may emit a `StageExecutionError`; it must not silently ignore failures.

### Duplicate detection

Sprint 8 image-derived duplicate detection **supplements** the existing `PackageDuplicateDetectionService` rather than replacing it.

- Existing evidence categories (`PACKAGE_REPLAY`, `SOURCE_AND_MEDIA`, `MEDIA_HASHES`, `IDENTITY_AND_ACQUISITION`, `IDENTITY`, `ACQUISITION_DETAILS`, `PARTIAL_MEDIA`) remain unchanged.
- New category recommended: `NORMALIZED_MEDIA_HASHES` for matches based on normalized front/reverse image bytes.
- Confidence semantics: exact normalized-byte match → `EXACT` or `HIGH`; partial match → `MEDIUM` or `WEAK`.
- False-positive handling: exact hash collisions on normalized bytes are treated as true duplicates for the purpose of the signal; downstream `PreviewDecisionSet` still lets the collector decide.
- Durability implications: duplicate signals are ephemeral preprocessing metadata. They flow through `PreparedImport.metadata` to the coordinator but do not modify durable state until the collector confirms an import decision.

### Alternatives considered

| Alternative | Trade-off | Disposition |
|---|---|---|
| Keep raw archive bytes durable; run image processing post-import | Preserves durability model but contradicts roadmap (“Builds on Sprint 7 framework”) and delays image improvements until after collection commit. | Rejected for Sprint 8 scope. |
| Make image stages operate on `CoinItem`/`ItemPhoto` post-import | Matches `image_assessment.py` seam but is not a Sprint 7 pipeline extension. | Out of scope; may be a future sprint. |
| Introduce perceptual hashing for duplicates | More robust to minor crops/lighting but is non-deterministic across library versions and harder to test. | Deferred; Sprint 8 uses exact normalized-byte hashes. |
| Allow stages to call `PackageImportCoordinator` directly | Would bypass the adapter and break the durability-ownership boundary. | Rejected per ADR-007 boundary 2. |
| Parallel image processing | Faster but violates cooperative cancellation and workspace ownership simplicity. | Rejected per ADR-007 rejected alternatives. |

### Invariants

1. No stage performs durable collection persistence.
2. No stage mutates the transaction journal.
3. No stage invokes rollback or recovery.
4. Stage ordering is explicit and deterministic.
5. A failed or cancelled pipeline cannot invoke `TransactionService`.
6. Source material (the original capture-package archive) remains immutable.
7. Temporary resources are path-contained and ownership-verified.
8. Existing Sprint 5 recovery semantics remain unchanged.
9. Existing Sprint 6 transaction event ordering remains unchanged.
10. Cancellation remains cooperative and cannot interrupt the durable commit boundary.
11. No dynamic or third-party code loading is introduced.
12. The frozen Schema-2 specification hash remains unchanged.
13. Preprocessed image artifacts cross the durability boundary only through `PreparedImport.files` consumed by the amended adapter.

### Unresolved choices requiring clarification

The following decisions materially affect durable data, backward compatibility, or pipeline ownership. The recommended choice is indicated; if you disagree, stop and clarify before implementation begins.

1. **Normalized images replace raw archive bytes in durable storage.**
   - Recommended: Yes. The durable collection stores normalized JPEGs; the original archive remains the immutable source of truth for re-import/audit.
   - Implication: `PackageImportCoordinator` must accept preprocessed image artifacts.

2. **Crop detection produces durable cropped artifacts or only metadata.**
   - Recommended: Cropped artifacts are durable by default if confidence is high; otherwise the normalized image is carried forward. The crop rectangle is always metadata.
   - Implication: `ImageDuplicateDetectionStage` should operate on the final durable image (cropped if available).

3. **Duplicate detection compares against the durable collection.**
   - Recommended: Yes, read-only, bounded to `MAX_DUPLICATE_EXISTING_ITEMS`.
   - Implication: The stage needs a read-only lookup into existing collection image descriptors, not a full `CoinItem` load.

4. **Perceptual hashing is deferred beyond Sprint 8.**
   - Recommended: Yes. Use exact normalized-byte hashes in Sprint 8.
   - Implication: Near-duplicate images (same coin, different lighting) will not be detected as duplicates in Sprint 8.

## Consequences

- The pre-import pipeline becomes capable of producing analysis-ready images before durable persistence.
- Downstream Sprint 9 (OCR) and Sprint 10 (AI grading) can consume normalized/cropped images from the durable collection instead of reprocessing raw captures.
- The adapter/coordinator contract must change; this is the only deliberate durability-boundary amendment in Sprint 8.
- Testing burden increases because image stages require fixtures and deterministic OpenCV/PIL behavior.
- No public API or plugin surface is introduced.

## Subject extensibility

The Sprint 8 pipeline is designed for coin photographs but the stage protocol and data contracts are intentionally geometry-neutral wherever feasible.

### Identifiers

The `coin_id` field in pipeline records, artifact keys, and workspace paths is a **generic collectible-item identifier** for the purpose of the pre-import pipeline. It is treated as an opaque, path-safe string (`^[A-Za-z0-9_-]{1,64}$`). Future subject types (banknotes, medals, tokens) can reuse the same pipeline by supplying their own identifiers; no field renaming is required for the pipeline to function, although downstream documentation may use subject-specific terminology.

### Image roles

`ImageRole.FRONT` and `ImageRole.REVERSE` describe two-sided collectibles generically. `ImageRole.EDGE` is coin-specific; stages that consume normalized artifacts gracefully ignore unknown roles. A future `ImageRole.BACK` (or renaming `REVERSE` to `BACK`) would be a capture-package format change, not a pipeline-protocol change.

### Crop detection

The `CropDetectionStage` (Unit 4) uses circular-contour qualification because coins are the initial target subject. The stage's fallback behavior—copying the full normalized image when no confident crop is found—ensures the pipeline remains usable for rectangular subjects (banknotes, stamps) without modification. A future geometry-specific crop stage can replace or extend the circular strategy without changing the `ProcessingStage` protocol, artifact key format, or downstream consumer contracts.

### Geometry-specific quality metrics

The `ImageQualityScoringStage` metrics (sharpness, contrast, brightness, resolution, blown highlights) are pixel-statistic based and remain valid for any flat subject. No amendment is required.
