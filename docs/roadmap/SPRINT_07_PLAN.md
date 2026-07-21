# Sprint 7 — Deterministic Import Workflow and Processing-Stage Framework

## Objective

Introduce a typed, deterministic workflow for running bounded preprocessing stages before durable collection persistence, while preserving all Sprint 5–6 transaction, recovery, cancellation, and event semantics.

## Architecture Dependency

| Foundation | Reference |
|---|---|
| Sprint 6 baseline | Commit `fd1682e` |
| Sprint 5 baseline | Commit `55817fd` |
| Architecture | Schema-2 Durable Persistence |
| Frozen spec hash | `A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4` |
| ADR | `docs/adr/ADR-007-internal-processing-stage-framework.md` |

## Deliverables

### Unit 1: Contract and ADRs ✅
- `docs/roadmap/SPRINT_07_PLAN.md` — this document
- `docs/architecture/IMPORT_WORKFLOW.md` — architecture specification
- `docs/adr/ADR-007-internal-processing-stage-framework.md` — design record
- **Status:** Complete — no production code changes

### Unit 2: Typed domain models
- `capture_import/workflow_models.py` — `ImportRequest`, `StageInput`, `StageResult`, `PreparedImport`, `StageArtifact`
- `tests/test_workflow_models.py` — immutability, invalid paths, duplicate artifacts, path containment
- **Status:** Planned

### Unit 3: Stage protocol and pipeline validation
- `capture_import/workflow_pipeline.py` — `ProcessingStage` (Protocol), `ProcessingPipeline`
- `tests/test_workflow_pipeline.py` — deterministic ordering, duplicate IDs, malformed output, failure attribution
- **Status:** Planned

### Unit 4: Pipeline execution and cancellation
- `ImportWorkflow` class with sequential execution
- Pre-stage and post-stage cancellation checks
- `PIPELINE_STARTED`, `STAGE_STARTED`, `STAGE_COMPLETED`, `STAGE_FAILED`, `PIPELINE_COMPLETED`, `PIPELINE_CANCELLED` events
- `tests/test_workflow_execution.py` — cancellation before first stage, between stages, stage exception, event ordering
- **Status:** Planned

### Unit 5: Workspace lifecycle
- Path-contained temporary workspace creation and cleanup
- Reuse Sprint 5 safety primitives
- `tests/test_workflow_workspace.py` — cleanup after success/failure/cancellation, source preservation, path escape rejection
- **Status:** Planned

### Unit 6: Transaction integration
- `ImportWorkflow` delegates exactly once to `TransactionService`
- Adapter from `PreparedImport` to existing transaction inputs
- `tests/test_workflow_integration.py` — transaction invoked only after successful pipeline, no durable mutation on failure
- **Status:** Planned

### Unit 7: Reference stages
- `PackageValidationStage` — adapter for existing validation
- `ManifestPreparationStage` — manifest assembly
- `tests/test_workflow_reference_stages.py` — trivial stages prove the design
- **Status:** Planned

### Unit 8: Documentation, traceability, and release gate
- Update `CHANGELOG.md`
- Update `docs/roadmap/PRODUCT_ROADMAP.md`
- Independent review
- Full regression
- **Status:** Planned

## Risks

| Risk | Mitigation |
|---|---|
| Mutable shared context temptation | Frozen contract: immutable `StageInput`/`StageResult` only |
| Stage accidentally performs durable writes | Frozen invariant: stages never see journal, lock, or collection paths |
| Event ownership confusion | Pipeline events are prefixed `PIPELINE_*`/`STAGE_*`; transaction events unchanged |
| Workspace path escape | Reuse Sprint 5 `_filesystem` safety primitives |
| Breaking existing imports | Integration tests verify observable behavior unchanged |

## Exit Criteria

| Criterion | Required result |
|---|---|
| Ordered execution | Stages execute exactly once in declared order |
| Failure handling | First failed stage halts execution and identifies `stage_id` |
| Cancellation | Safe before, between, and after preparation stages |
| Transaction handoff | Occurs exactly once after successful preparation |
| Durable safety | No transaction invocation on preprocessing failure/cancellation |
| Recovery | Existing recovery matrix remains unchanged and passing |
| Events | Pipeline lifecycle events are deterministic and queryable |
| Workspace | Owned resources cleaned on all terminal paths |
| Compatibility | Existing imports preserve externally observable behavior |
| Regression | At least Sprint 6 baseline of 211 passing tests |
| Architecture | Frozen specification hash unchanged |
| Documentation | Plan, architecture, ADR, changelog, and traceability synchronized |
| Review | No unresolved blocking or major findings |

## Stop Conditions

Stop and await direction if any of the following occur:

- Need to change Schema-2 journal or recovery semantics
- Ambiguity over which layer owns durable writes
- Duplicate or conflicting top-level events
- Requirement for dynamic plugin loading
- Source mutation during preprocessing
- Inability to prove workspace path containment
- Cancellation that can occur during an atomic durable transition
- Required breaking change to `TransactionService`
- Full-regression failure not directly explained by current unit
- Scope pressure to begin OCR, image processing, or AI functionality

## Implementation Notes

- Stages are internal processing components, not public plugins.
- Stage ordering is explicit and deterministic.
- Stages return typed results rather than mutating a shared god context.
- `TransactionService` remains the sole owner of journals, durable writes, rollback, and commit.
- `RecoveryService` semantics remain unchanged.
- Stages may only write into workflow-owned, path-contained temporary workspaces.
- Pipeline failure or cancellation prevents transaction invocation.
- Cancellation is cooperative at stage boundaries.
- No OCR, AI, image processing, networking, GUI, dynamic loading, parallelism, retries, or caching in Sprint 7.
- No runtime production code changes in Unit 1.

## Technical Debt to Avoid

| Shortcut | Resulting debt |
|---|---|
| Mutable `dict` passed through all stages | Hidden coupling and nondeterministic behavior |
| Stages writing directly to final storage | Competing durability model |
| Generic `except Exception: pass` | Concealed corruption and debugging failures |
| Runtime plugin discovery | Security and compatibility burden |
| Stage-specific orchestration branches | Pipeline becomes another monolith |
| Reimplementing snapshot/workspace safety | Divergent security semantics |
| Moving all existing code in one unit | Review becomes ineffective |
| Parallel stages now | Cancellation and ownership complexity with little benefit |
