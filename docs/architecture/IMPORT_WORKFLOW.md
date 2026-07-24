# Import Workflow Architecture

## Authority

This document describes the deterministic preprocessing pipeline that runs before the durable transaction boundary. It is subordinate to:

- `docs/architecture/durable-persistence.md` (frozen at SHA-256 `A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4`)
- `docs/architecture/processed-artifact-durability.md` for processed-media
  imports (Unit 7A bundle SHA-256
  `047AD4FC27A7422260956946C6DCC6E5912D15B9E925A77D1E7E36890F180710`)
- `docs/adr/ADR-007-internal-processing-stage-framework.md`

## Overview

```text
Import request
    │
    ▼
ImportWorkflow
    │
    ├── Build immutable request/context
    │
    ├── Run ordered preparation stages
    │       ├── PackageValidationStage
    │       ├── ManifestPreparationStage
    │       ├── ImageNormalizationStage        ← Sprint 8
    │       ├── ImageQualityScoringStage       ← Sprint 8 (metadata only)
    │       ├── CropDetectionStage             ← Sprint 8
    │       ├── ObverseReversePairingStage     ← Sprint 8 (metadata only)
    │       ├── ImageDuplicateDetectionStage   ← Sprint 8 (metadata only)
    │       └── (future: OCR, metadata extraction)
    │
    ├── Produce PreparedImport
    │
    ▼
Transaction delegate (application-layer adapter
    │                    → PackageImportCoordinator)
    ▼
PackageImportTransactionService
    │
    ├── journal
    ├── copy/persist files
    ├── durable state transitions
    ├── collection commit
    ├── rollback
    └── recovery compatibility
```

## Layer responsibilities

| Layer | Responsibility |
|---|---|
| `ImportWorkflow` | Sequencing nondurable preparation; cancellation; event emission |
| `ProcessingPipeline` | Deterministic stage ordering; unique ID enforcement; result validation |
| `ProcessingStage` | Pure or workspace-bounded transformation; explicit input/output contract |
| `WorkflowWorkspace` | Workspace creation, containment, and cleanup (owned by the application driver) |
| `PackageImportTransactionService` | Durable persistence and rollback; legacy behavior unchanged unless the separately versioned processed-snapshot contract is selected |
| `PackageImportRecoveryService` | Reconciliation of interrupted durable work; legacy behavior unchanged for imports without a processed snapshot |
| `ImportEventBus` | Observability only (unchanged) |

## Data contracts

### ImportRequest

Immutable request to begin an import workflow.

```python
@dataclass(frozen=True)
class ImportRequest:
    source: Path
    collection_id: str
    configuration: ImportConfiguration
```

### StageInput

Explicit input to a single stage.

```python
@dataclass(frozen=True)
class StageInput:
    request: ImportRequest
    workspace: Path
    artifacts: Mapping[str, StageArtifact]
```

### StageResult

Explicit output from a single stage.

```python
@dataclass(frozen=True)
class StageResult:
    artifacts: Mapping[str, StageArtifact]
    metadata: Mapping[str, JsonValue]
```

### PreparedImport

The sole output of a successful pipeline, accepted by the transaction layer.

```python
@dataclass(frozen=True)
class PreparedImport:
    request: ImportRequest
    files: tuple[PreparedFile, ...]
    metadata: Mapping[str, JsonValue]
    processed_artifacts: PreparedArtifactSet | None = None
```

`PreparedArtifactSet` is a non-serializable, single-use ownership object. It
combines immutable, ordered descriptors with a verified workspace-root lease and
open read-only no-follow handles for every selected artifact. Each selected
descriptor has a mandatory expected byte length and SHA-256 plus captured native
identity. Assembly verifies and hashes through those handles; the coordinator
takes ownership exactly once, copies through the same handles, and verifies
identity, length, digest, root, parents, and path binding before and after the
bounded copy. Workflow paths and native identities are never durable fields.

## Stage protocol

```python
class ProcessingStage(Protocol):
    @property
    def stage_id(self) -> str: ...

    def execute(self, stage_input: StageInput) -> StageResult: ...
```

- `stage_id` must be unique within a pipeline.
- `execute` must not mutate shared state invisibly.
- Stages may only write into the provided `workspace` path.

## Pipeline construction

### Sprint 7 reference pipeline

```python
pipeline = ProcessingPipeline(
    stages=(
        PackageValidationStage(),
        ManifestPreparationStage(),
    )
)
```

### Sprint 8 extended pipeline

```python
pipeline = ProcessingPipeline(
    stages=(
        PackageValidationStage(),
        ManifestPreparationStage(),
        ImageNormalizationStage(),
        ImageQualityScoringStage(),
        CropDetectionStage(),
        ObverseReversePairingStage(),
        ImageDuplicateDetectionStage(),
    )
)
```

- Order is explicit and deterministic.
- Duplicate `stage_id` values fail at construction time.
- Empty pipeline policy (ADR-007): an empty pipeline is valid and behaves as the identity operation.
- Legacy implementation: `build_reference_pipeline()` remains the Sprint 7
  two-stage builder.
- Sprint 8 implementation: `build_image_processing_pipeline()` returns the fixed
  seven-stage order above.
- Unit 7E migrates the production call site to the Sprint 8 builder only after
  Units 7A–7D are verified. Callers explicitly using the legacy builder retain
  their existing behavior.

## Cancellation boundaries

Cancellation is checked:
1. Before each stage
2. After each stage
3. Before handing `PreparedImport` to the transaction delegate (the application-layer adapter, which reaches `PackageImportCoordinator` and `TransactionService`)

Once `TransactionService.execute()` begins, Sprint 6 cancellation semantics apply: cooperative checks before `COMMITTING_COLLECTION`, then commit-or-recovery only.

## Event ordering

On a successful durable handoff, events are emitted in exactly this order:

```text
PIPELINE_STARTED        ← ImportWorkflow
STAGE_STARTED           (stage_id, stage_index, stage_count)
STAGE_COMPLETED / STAGE_FAILED
PIPELINE_COMPLETED      ← ImportWorkflow (preprocessing succeeded)
IMPORT_STARTED          ← TransactionService (existing)
PACKAGE_VALIDATED       ← TransactionService (existing)
...                     ← existing transaction events
IMPORT_COMPLETE         ← TransactionService (existing)
```

- Pipeline-family events are emitted entirely before transaction-family
  events: `IMPORT_STARTED` never precedes `PIPELINE_STARTED`.
- `IMPORT_STARTED` originates inside `TransactionService.execute()`; the
  transaction begins only after preprocessing has completed and the
  `PreparedImport` handoff occurs.
- `ImportWorkflow` does not emit or duplicate transaction-family events,
  and there is no duplicate `IMPORT_STARTED`.
- `PIPELINE_CANCELLED` replaces `PIPELINE_COMPLETED` on cancellation paths;
  a run never emits both. Cancellation before the handoff commits nothing,
  so no transaction-family event follows it.

## Prepared-import assembly failure

Assembly occurs after successful stage execution and before the durability
handoff. If assembly fails (a declared artifact is missing or is not a
plain regular file in the workspace):

- the transaction delegate is invoked zero times;
- a stage-attributed `StageContractError` is raised, identifying the
  declaring stage and preserving the original `OSError` via chaining;
- neither `STAGE_FAILED` nor any transaction-family event is emitted;
- under the current Sprint 7 contract, no additional pipeline-terminal
  event is emitted either: `PIPELINE_COMPLETED` represents successful
  preprocessing execution, while assembly is a separate pre-handoff
  boundary. The bus therefore shows `PIPELINE_STARTED` plus the stage
  lifecycle events with no terminal marker on this path.

## Error model

```text
ImportWorkflowError
├── PipelineConfigurationError
├── StageContractError
├── StageExecutionError
└── WorkflowCancelledError
```

- Preserve original exception via chaining.
- Include `stage_id` in stage-related errors.
- Do not convert transaction or recovery errors into generic stage errors.
- Cleanup failure must not conceal the primary failure.

## Image-stage contracts (Sprint 8)

Sprint 8 adds internal image-processing stages to the pre-import pipeline. Full contracts are defined in `docs/adr/ADR-008-image-processing-pipeline.md`. The following rules govern every image stage:

- **Input format:** JPEG and PNG only, matching `capture_import/media.py` validation.
- **Output format:** Canonical normalized JPEG (sRGB, EXIF stripped, baseline, quality 92) unless a stage explicitly documents otherwise.
- **Artifact ownership:** All image artifacts are written beneath `StageInput.workspace` and declared in `StageResult.artifacts` with stable keys.
- **Determinism:** Same input bytes + same configuration produce identical output bytes on the same platform/library version.
- **Resource bounds:** Output dimensions, pixel counts, and file sizes are bounded by existing `capture_import/limits.py` values.
- **No durable writes:** Stages do not mutate journals, locks, collections, or managed image storage.
- **Subject extensibility:** The `coin_id` field in pipeline records and artifact paths is a generic collectible-item identifier. `ImageRole.FRONT` and `ImageRole.REVERSE` are generic two-sided roles. `ImageRole.EDGE` is coin-specific and ignored by stages that do not recognise it. Crop-detection strategies are geometry-specific and may be replaced for non-circular subjects without changing the stage protocol.

Sprint 8 adds internal image-processing stages to the pre-import pipeline. Full contracts are defined in `docs/adr/ADR-008-image-processing-pipeline.md`. The following rules govern every image stage:

- **Input format:** JPEG and PNG only, matching `capture_import/media.py` validation.
- **Output format:** Canonical normalized JPEG (sRGB, EXIF stripped, baseline, quality 92) unless a stage explicitly documents otherwise.
- **Artifact ownership:** All image artifacts are written beneath `StageInput.workspace` and declared in `StageResult.artifacts` with stable keys.
- **Determinism:** Same input bytes + same configuration produce identical output bytes on the same platform/library version.
- **Resource bounds:** Output dimensions, pixel counts, and file sizes are bounded by existing `capture_import/limits.py` values.
- **No durable writes:** Stages do not mutate journals, locks, collections, or managed image storage.

### Stage order

1. `ImageNormalizationStage` — produces `normalized/<coin_id>/<role>.jpg` artifacts.
2. `ImageQualityScoringStage` — metadata-only quality metrics on normalized artifacts.
3. `CropDetectionStage` — always produces `cropped/<coin_id>/<role>.jpg` artifacts and crop records; the durable selector uses cropped bytes only when `crop_applied` is true and `crop_confidence >= 0.65`, otherwise it selects the normalized artifact and requires the cropped fallback to be an exact full-frame copy.
4. `ObverseReversePairingStage` — metadata-only consistency check between front and reverse images.
5. `ImageDuplicateDetectionStage` — metadata-only duplicate signals based on exact normalized-byte hashes.

## Adapter amendment for preprocessed images

Sprint 8 amends the Sprint 7 adapter contract. `capture_import/workflow_adapter.py` currently forwards only `prepared.request.source` to `PackageImportCoordinator.prepare()`. Under Sprint 8:

- `PreparedFile` retains the artifact key, content type, producer stage,
  durability classification, mandatory expected length, mandatory SHA-256, and
  captured native file identity verified during assembly. Stage output identifies
  both normalized/cropped candidate keys and the exact crop record. Assembly
  validates both, applies the inclusive `0.65` selection rule, verifies fallback
  equivalence, and creates one selected `PreparedArtifactDescriptor`.
- The adapter routes immutable descriptors without parsing filenames, inspecting
  bytes, or opening files.
- The coordinator API becomes
  `prepare(source_path, *, processed_artifacts=None)`. The optional keyword keeps
  every existing caller source-compatible and preserves the legacy path when no
  processed artifacts are supplied.
- `PreparedArtifactSet` binds those descriptors to a single-use
  `PreparedWorkspaceLease`: a verified root-directory handle and open read-only
  no-follow handles for every selected file. Assembly performs bounded hashing
  through the handles. The coordinator accepts the lease exactly once, copies
  only through those same handles, compares identity/length before and after
  copying, recomputes the digest, and revalidates the workspace root, parent
  chain, and pathname identity before sealing.
- Before transfer, the workflow driver closes the lease on every failure or
  cancellation path. After transfer, the coordinator owns and closes it on every
  terminal path. Repeated transfer fails explicitly. No workflow path, host
  identity, or handle is serialized.
- `PreparedPackageImport` owns the original package snapshot and the optional
  processed snapshot as one preparation lease. Transactions receive verified
  immutable handles, never workflow paths.
- `PackageImportCoordinator` retains sole ownership of snapshot creation,
  validation, cancellation cleanup, and transaction handoff.

The processed snapshot has its own UUID, owner token, root identity, closed
canonical manifest, per-artifact role/type/size/digest facts, and aggregate
inventory digest. It commits the original package SHA-256 as derivation
provenance but never replaces that SHA-256 in previews, audits, journals, or
terminal history.

When a processed snapshot is present, the image store copies selected media only
from that snapshot. Missing, mismatched, or unverifiable processed evidence fails
closed; there is no silent fallback to original media. Without one, the current
package-snapshot path remains unchanged.
If final decisions select no coins, the image store is not invoked: the
pre-journal preparation lease cleans processed then raw and returns the existing
successful no-op without a journal or terminal record.

### Versioned durability gate

The frozen Schema 2 contract remains authoritative for imports without processed
media. It is not extended in place. Processed imports use the separately frozen
Unit 7A successor bundle at SHA-256
`047AD4FC27A7422260956946C6DCC6E5912D15B9E925A77D1E7E36890F180710`, which defines journal `3.0`, processed snapshot
owner/manifest/completion `1.0`, journal owner `2.0`, terminal history `2.0`,
PA-RM-01 through PA-RM-43, and the complete cleanup/recovery contract.

Unit 7B may implement only the identity-bound handoff and sealing portion after
Unit 7A approval. Units 7C–7E remain bounded by the successor traceability gates.
Any behavior absent from the frozen bundle requires a documentation-only
amendment, re-review, and new bundle hash before production changes continue.

## Duplicate detection signals

Image-derived duplicate detection in Sprint 8 supplements — but does not replace — the existing `PackageDuplicateDetectionService` evidence categories. It emits signals such as `NORMALIZED_MEDIA_HASHES` based on exact SHA-256 hashes of normalized images.

- **Within-package:** exact normalized-byte matches between coins in the same package.
- **Package-vs-collection:** exact normalized-byte matches against existing collection image descriptors, bounded by `MAX_DUPLICATE_EXISTING_ITEMS`.
- **Precedence:** existing categories remain unchanged; new categories are additive.
- **Durability:** signals are ephemeral preprocessing metadata that flow through `PreparedImport.metadata` to the coordinator; no durable mutation occurs before collector confirmation.

## Workspace lifecycle

1. The application driver creates a workflow-owned, path-contained temporary workspace (`WorkflowWorkspace`); the execution engine never creates or deletes it.
2. Stages write outputs into this workspace only.
3. On success:
   - In the Sprint 7 reference pipeline, the transaction delegate re-derives durable inputs from `request.source` through the existing coordinator snapshot path — workspace artifacts are ephemeral preprocessing products, not transaction inputs; the workspace is cleaned.
   - In the Sprint 8 extended pipeline, the adapter passes typed artifact
     descriptors to the coordinator. The coordinator seals and re-verifies a
     separate processed snapshot while the workspace remains owned. Only after
     sealing may the workspace be cleaned. `request.source` and its package
     snapshot remain the immutable audit source.
4. On failure: workspace is cleaned; primary exception is raised.
5. On cancellation: workspace is cleaned; `WorkflowCancelledError` is raised.

Reuse Sprint 5 snapshot/workspace safety primitives where applicable (implemented in `workflow_workspace.py`).

## Invariants

1. No stage performs durable collection persistence.
2. No stage mutates the transaction journal.
3. No stage invokes rollback or recovery.
4. Stage ordering is explicit and deterministic.
5. A failed or cancelled pipeline cannot invoke `TransactionService`.
6. Source material remains immutable.
7. Temporary resources are path-contained and ownership-verified.
8. Existing schema-2 recovery semantics remain unchanged; processed snapshots
   are disabled until a separately versioned durability amendment is approved.
9. Existing Sprint 6 transaction event ordering remains unchanged.
10. Cancellation remains cooperative and cannot interrupt the durable commit boundary.
11. No dynamic or third-party code loading is introduced.
12. The current frozen Schema-2 hash remains authoritative and is an explicit
    implementation gate, not a schema that Unit 7 may extend in place.
13. Original package identity and derived processed-media identity are distinct.
14. Durable state never depends on the workflow workspace.
15. Stages never create or own durable snapshots.
16. Transactions consume verified immutable snapshots only.
