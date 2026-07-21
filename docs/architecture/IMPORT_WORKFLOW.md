# Import Workflow Architecture

## Authority

This document describes the deterministic preprocessing pipeline that runs before the durable transaction boundary. It is subordinate to:

- `docs/architecture/durable-persistence.md` (frozen at SHA-256 `A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4`)
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
| `PackageImportTransactionService` | Durable persistence and rollback (unchanged) |
| `PackageImportRecoveryService` | Reconciliation of interrupted durable work (unchanged) |
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
```

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
- Reference implementation: `build_reference_pipeline()` in `capture_import/workflow_stages.py`.
- Sprint 8 image stages are optional additions to the reference pipeline; callers that do not require image processing may continue to use the Sprint 7 pipeline.

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

### Stage order

1. `ImageNormalizationStage` — produces `normalized/<coin_id>/<role>.jpg` artifacts.
2. `ImageQualityScoringStage` — metadata-only quality metrics on normalized artifacts.
3. `CropDetectionStage` — produces optional `cropped/<coin_id>/<role>.jpg` artifacts and crop rectangles.
4. `ObverseReversePairingStage` — metadata-only consistency check between front and reverse images.
5. `ImageDuplicateDetectionStage` — metadata-only duplicate signals based on exact normalized-byte hashes.

## Adapter amendment for preprocessed images

Sprint 8 amends the Sprint 7 adapter contract. `capture_import/workflow_adapter.py` currently forwards only `prepared.request.source` to `PackageImportCoordinator.prepare()`. Under Sprint 8:

- `PreparedImport.files` contains the workspace-relative paths of normalized (and optionally cropped) image artifacts produced by image-processing stages.
- The adapter must pass these preprocessed artifacts to the coordinator so that durable persistence uses the normalized bytes.
- Unit 7 must design a routing mechanism so the adapter can distinguish image artifacts from non-image artifacts (e.g., `prepared-manifest.json`). Options include: extending `PreparedFile` with `content_type`, passing the `StageArtifact` mapping alongside `PreparedImport`, or using deterministic path conventions/file extensions.
- `PackageImportCoordinator` retains sole ownership of snapshots, validation, and transaction boundaries.
- The existing prepare-from-source path remains available for backward compatibility.

The exact coordinator signature change is left to Sprint 8 Unit 7 implementation and must preserve fail-closed semantics.

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
   - In the Sprint 8 extended pipeline, the adapter passes preprocessed image artifacts from `PreparedImport.files` to the coordinator as durable inputs, while `request.source` remains the immutable audit source; the workspace is cleaned after the handoff.
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
8. Existing Sprint 5 recovery semantics remain unchanged.
9. Existing Sprint 6 transaction event ordering remains unchanged.
10. Cancellation remains cooperative and cannot interrupt the durable commit boundary.
11. No dynamic or third-party code loading is introduced.
12. The frozen Schema-2 specification hash remains unchanged.
