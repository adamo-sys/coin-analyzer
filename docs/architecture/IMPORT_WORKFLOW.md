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
    │       └── (future: image normalization, OCR, metadata extraction)
    │
    ├── Produce PreparedImport
    │
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
| `ImportWorkflow` | Sequencing nondurable preparation; workspace lifecycle; cancellation; event emission |
| `ProcessingPipeline` | Deterministic stage ordering; unique ID enforcement; result validation |
| `ProcessingStage` | Pure or workspace-bounded transformation; explicit input/output contract |
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

```python
pipeline = ProcessingPipeline(
    stages=(
        PackageValidationStage(),
        ManifestPreparationStage(),
    )
)
```

- Order is explicit and deterministic.
- Duplicate `stage_id` values fail at construction time.
- Empty pipeline policy: reject or allow no-op passthrough (TBD in implementation).

## Cancellation boundaries

Cancellation is checked:
1. Before each stage
2. After each stage
3. Before handing `PreparedImport` to `TransactionService`

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

## Workspace lifecycle

1. Workflow creates a path-contained temporary workspace.
2. Stages write outputs into this workspace only.
3. On success: workspace contents are handed to transaction service; workspace is cleaned.
4. On failure: workspace is cleaned; primary exception is raised.
5. On cancellation: workspace is cleaned; `WorkflowCancelledError` is raised.

Reuse Sprint 5 snapshot/workspace safety primitives where applicable.

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
