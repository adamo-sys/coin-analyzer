# ADR-008: Image Processing Pipeline

- Status: Accepted; Unit 7 processed-media durability contract frozen separately
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

Extend the Sprint 7 pre-import pipeline with a bounded family of internal image-processing stages. All stages obey ADR-007 boundaries with one deliberate amendment: **selected `PreparedImport.files` are bound into a `PreparedArtifactSet` that may cross the durability boundary**, so the durable collection contains normalized images instead of raw archive bytes.

### Scope boundary

**In scope for Sprint 8:**
- Pre-import processing of capture-package images before `TransactionService.execute()`.
- Stages that read from `ImportRequest.source` (the validated capture-package archive) and write normalized/derived artifacts into the caller-owned workspace.
- Producing `PreparedImport.files`, `PreparedImport.metadata`, and an optional
  identity-bound `PreparedArtifactSet` that the transaction delegate consumes.

**Explicitly out of scope:**
- Post-import collection image analysis (`image_assessment.py`, `image_analyzer.py` workflows on `CoinItem`).
- OCR and metadata extraction (Sprint 9).
- AI grading (Sprint 10).
- Third-party plugins, dynamic stage discovery, parallel execution, GPU acceleration, cloud processing.
- Reinterpreting existing Schema-2 durable persistence, recovery, or event
  semantics in place. A separately versioned successor requires Unit 7A approval
  and a new frozen specification hash.

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
- Crop detection produces crop rectangles and one cropped artifact per
  normalized input; low-confidence output is a byte-identical full-frame
  fallback.
- Obverse/reverse pairing consumes normalized front/reverse images and emits consistency metadata.
- Duplicate detection consumes normalized images and hashes last, after all other preprocessing, so its evidence reflects the final pre-import representation.

The existing `build_reference_pipeline()` remains the two-stage Sprint 7
pipeline for backward compatibility. Sprint 8 adds
`build_image_processing_pipeline()` for the fixed seven-stage order above.
Unit 7E may migrate the production call site only after Units 7A–7D are
verified; callers that explicitly request the legacy builder remain unchanged.

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
- The current `assemble_prepared_import` verifies every declared artifact is a
  plain regular file and emits only path/size facts. Unit 7B must extend that
  assembly contract with typed routing facts and a verified ephemeral artifact
  set; no durable code may rely on the current path-only form.
- The caller (`WorkflowWorkspace`) cleans the workspace on failure and
  cancellation. On a successful processed-media handoff, cleanup occurs only
  after the coordinator has sealed and independently verified the processed
  snapshot.

#### Consuming `PreparedImport.files` downstream

ADR-007’s technical debt register notes that `workflow_adapter.py` currently
forwards only `request.source` and ignores `PreparedImport.files`/`metadata`.
Sprint 8 adopts a **coordinator-owned immutable processed-artifact snapshot**.
The workflow workspace is never a transaction input.

The handoff is:

```text
workflow workspace
    -> PreparedImport artifact descriptors
    -> coordinator verifies and seals a processed snapshot
    -> workspace may be cleaned
    -> transaction receives the original-package snapshot plus the processed snapshot
```

`PreparedFile` must carry an explicit artifact key, content type, producer stage,
and durability classification in addition to relative path, expected size, and
digest. The digest is mandatory for every selected processed-media artifact.
Image stages mark normalized/cropped outputs as processed-media candidates;
support files such as `prepared-manifest.json` remain ephemeral. Stage output
identifies both candidate keys and the exact crop record for each
`(source_coin_id, role)`. Assembly validates both candidates, applies the
inclusive `0.65` rule, verifies fallback equivalence, and creates the single
selected ephemeral descriptor. Neither the crop stage nor adapter chooses
durable bytes. The adapter routes only typed descriptors and never opens files,
parses paths, or inspects bytes.

The handoff object is a non-serializable `PreparedArtifactSet` with two parts:

- an immutable, deterministically ordered tuple of
  `PreparedArtifactDescriptor` values containing exactly the artifact key,
  source coin id, role, variant, content type, mandatory expected byte length,
  mandatory SHA-256, workspace-relative path, and captured native file identity;
- a single-use `PreparedWorkspaceLease` that owns a verified workspace-root
  directory handle plus open, read-only, no-follow handles for every selected
  file. Those handles are captured during assembly after bounded hashing.

`ProcessedArtifactDescriptor` is reserved for the closed durable manifest
schema; coordinator sealing deterministically transforms the prepared type and
removes all workspace/native facts. Assembly verifies the workspace root, parent
chain, regular-file identity, length, and digest before creating this set. The
coordinator accepts ownership
exactly once, copies only from the held handles, verifies handle identity/length
before and after each bounded copy, recomputes every digest, and revalidates the
workspace root, parent chain, and pathname identity before sealing. A replaced
path or changed handle fails closed; path equivalence alone is never authority.

Before ownership transfer, the workflow driver closes the lease on failure or
cancellation. After successful transfer, the coordinator closes every handle on
success, failure, and cancellation. A rejected or repeated transfer fails
explicitly, so neither side can silently double-own or leak the lease. Workspace
paths and native identities are ephemeral assembly facts and never appear in a
journal, audit record, terminal history, or processed-snapshot manifest.

`commit_prepared_import` remains the sole application-layer bridge and calls:

```python
PackageImportCoordinator.prepare(
    prepared.request.source,
    processed_artifacts=prepared.processed_artifacts,
)
```

`processed_artifacts` is optional. Omitting it is exactly the existing
prepare-from-source behavior. When present, it is an ephemeral descriptor set
bound to the verified workflow workspace; it is not durable evidence. The
coordinator must create and verify both snapshots before returning
`PreparedPackageImport`. The returned object owns the original snapshot and the
processed snapshot as one preparation lease. Cancellation cleans both through
their verified identities.

### Processed-artifact snapshot contract

#### Ownership and creation

- The coordinator is the sole owner and creator. Stages and the adapter cannot
  create, name, delete, or adopt a processed snapshot.
- Creation occurs after the original package snapshot has been verified and
  before the transaction boundary.
- The coordinator consumes artifacts while holding a verified workflow-root
  directory identity and verified plain-file handles. It creates one random-token
  child beneath a dedicated trusted processed-snapshot root.
- No workspace pathname, host path, or unverified reference is persisted. The
  temporary workspace may be deleted only after sealing and independent
  verification succeed.

#### Closed snapshot layout and identity

The processed snapshot has its own canonical UUID `processed_snapshot_id`, random
ownership token, native root identity, owner record, manifest, and aggregate
digest. It is derived evidence and never changes the original package SHA-256,
byte length, version, basename, manifest, or audit identity.

The exact closed manifest, descriptor, owner, completion, lease, and canonical
JSON schemas are defined only by the versioned
[Processed-Artifact Durability Specification](../architecture/processed-artifact-durability.md).
That successor bundle is authoritative if this ADR's non-normative summary is
less specific. The owner is durably published before artifacts, commits the
captured root identity and exact planned manifest, and authorizes only its closed
inventory. The manifest includes the ownership-token SHA-256, original-package
provenance, ordered selected descriptors, aggregate byte length, count, and
inventory digest. The immutable zero-byte lease is created after owner
publication. Completion is published last and alone proves sealing.

#### Bounds and sealing

- At most `MAX_COINS_PER_PACKAGE * MAX_IMAGES_PER_COIN` selected artifacts.
- Each artifact is at most `MAX_IMAGE_SIZE`; aggregate bytes are at most
  `MAX_TOTAL_UNCOMPRESSED_SIZE`.
- Dimensions and pixels remain bounded by `MAX_IMAGE_DIMENSION` and
  `MAX_IMAGE_PIXELS`; content type is `image/jpeg` for Sprint 8 durable output.
- Every destination is created no-follow and no-overwrite, copied through a
  bounded held handle, flushed and synced, then verified for exact length,
  digest, canonical image facts, object identity, and parent identity.
- The owner precedes artifact creation; artifacts and manifest are then written
  and verified in canonical order. A snapshot is sealed only after completion
  publication, fresh inventory verification, and directory durability.
- Partial or ambiguous creation is never returned. Proven coordinator-owned
  partial state is removed; uncertain state is preserved and blocks.

#### Transaction, image store, and recovery

- The transaction input is an optional verified
  `ProcessedSnapshotHandle` alongside the existing original
  `SnapshotHandle`. It contains no workspace reference.
- When the handle is present, managed-image planning and copying use the selected
  processed descriptor for each imported `(source_coin_id, role)`. They never
  fall back silently to original media. When absent, the legacy original-package
  media path is unchanged.
- Before the first durable mutation and at every processed-media read, the
  transaction verifies the processed snapshot owner, root identity, manifest,
  inventory, aggregate digest, and package derivation commitment.
- Journal evidence must identify both snapshots independently and must commit the
  processed manifest/inventory before any managed-image write. Cleanup receipts
  must distinguish original-package and processed-snapshot targets.
- Startup recovery enumerates both snapshot roots under the global lock. A
  journal-referenced processed snapshot is never an orphan. An unreferenced
  snapshot is removable only through the same conservative owner, identity,
  lease, containment, and exact-byte proof required for package snapshots.
- Rollback deletes managed images, then both owned snapshots, using durable
  cleanup intents and receipts. Success retains managed images but cleans both
  snapshots before terminalization. Ambiguity preserves evidence and remains
  nonterminal.
- Crash boundaries are required for processed-snapshot creation, sealing,
  pre-journal verification, each managed-image read, cleanup intent, each
  snapshot deletion, receipt publication, and terminal eligibility. Repeated
  recovery is idempotent and exactly-once.

#### Audit semantics

Original package provenance remains authoritative: package hashes and manifest
facts in audit/history always describe the uploaded `.ca-package`. Processed
media is separate derived evidence. Operational journal generations commit its
snapshot and artifact digests; sanitized terminal history may retain only
path-free aggregate processed-media proof (outcome, count, aggregate digest).
It never substitutes the processed digest for `package_sha256`.

#### Failure, cancellation, and cleanup ordering

- Failure or cancellation before sealing cleans only proven temporary workspace
  and partial processed-snapshot state; no transaction begins.
- Failure after sealing but before journal creation cleans both coordinator-owned
  snapshots or preserves ambiguous evidence for startup reconciliation.
- After journal creation, only transaction/recovery cleanup rules may delete
  either snapshot.
- The workflow workspace must outlive sealing, but not transaction execution.
  Durable state must never depend on it.
- Terminal `SUCCEEDED`, `ROLLED_BACK`, or `CANCELLED` is illegal until every
  required snapshot cleanup receipt is durable.

### Processed-media durability alternatives

| Alternative | Disposition | Reason |
| --- | --- | --- |
| Coordinator-owned immutable processed-artifact snapshot | **Selected; implementation requires the Unit 7A successor contract** | Preserves original evidence, gives transformed bytes independent identity, and permits deterministic recovery. |
| Rewritten canonical capture-package snapshot | Rejected | Conflates source and derived evidence, changes package/manifest hashes, and complicates audit and replay semantics. |
| Original media remains durable; processed artifacts are advisory | Rejected | Preserves the current engine but fails the Sprint 8 product requirement that normalized output becomes the stored media. |

### Frozen durability-specification conflict

The selected design cannot be implemented under the current frozen
`docs/architecture/durable-persistence.md` hash
`A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4`.
Journal schema 2.0, snapshot owner schema 1.0, cleanup target/root kinds, terminal
history schema 1.0, and RM-01–RM-41 are closed and describe one package snapshot.
They have no legal representation for a second snapshot or its cleanup evidence.

No implementation may reinterpret those schemas or append unknown fields.
Unit 7A therefore defines a separate successor bundle:

- `docs/architecture/processed-artifact-durability.md`;
- `docs/DESKTOP_PROCESSED_ARTIFACT_RECOVERY_MATRIX.md`;
- `docs/DESKTOP_PROCESSED_ARTIFACT_RECOVERY_INVARIANTS.md`;
- `docs/architecture/processed-artifact-durability-traceability.md`.

The bundle SHA-256 is
`047AD4FC27A7422260956946C6DCC6E5912D15B9E925A77D1E7E36890F180710`, calculated over the exact bytes and domain-separated
framing defined by the successor specification. The legacy file and hash remain
unchanged. Units 7B–7E MUST implement only the successor contract and MUST stop
on any missing field, transition, recovery action, or platform guarantee.

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
- **Behavior:** Rule-based or simple contour heuristic to find the coin region. If `crop_applied` is true and `crop_confidence >= 0.65`, durable selection uses the cropped artifact. Otherwise durable selection uses the normalized artifact, and the stage's always-present cropped fallback is an exact byte-for-byte full-frame copy with `crop_confidence == 0.0`. The crop rectangle covers the full normalized image. This exact selection rule is defined normatively by the processed-artifact durability specification.
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

### Pipeline-stage alternatives

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
8. Existing schema-2 imports retain their exact recovery semantics; processed
   snapshots require a separately versioned durability contract before use.
9. Existing Sprint 6 transaction event ordering remains unchanged.
10. Cancellation remains cooperative and cannot interrupt the durable commit boundary.
11. No dynamic or third-party code loading is introduced.
12. The current frozen Schema-2 hash remains authoritative and blocks processed
    snapshot implementation until a separately approved amendment is frozen.
13. Preprocessed image artifacts cross the durability boundary only through the
    `PreparedArtifactSet` assembled from selected `PreparedImport.files` and
    consumed by the amended adapter.

### Resolved product choices

1. **Normalized images replace raw archive bytes in durable storage.**
   - Decision: Yes, through the separately identified processed-artifact
     snapshot. The original archive remains the immutable audit source.

2. **Crop detection produces durable cropped artifacts or only metadata.**
   - Decision: Cropped artifacts are selected exactly when `crop_applied` is
     true and `crop_confidence >= 0.65`; otherwise normalized artifacts are
     selected and the cropped fallback must be byte-identical. The explicit
     selection metadata, not adapter path parsing, determines the descriptor.

3. **Duplicate detection compares against the durable collection.**
   - Decision: Yes, read-only, bounded to `MAX_DUPLICATE_EXISTING_ITEMS`.
   - Implication: The stage needs a read-only lookup into existing collection image descriptors, not a full `CoinItem` load.

4. **Perceptual hashing is deferred beyond Sprint 8.**
   - Decision: Yes. Use exact normalized-byte hashes in Sprint 8.
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
