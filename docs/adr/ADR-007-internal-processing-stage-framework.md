# ADR-007: Internal Processing Stage Framework

- Status: Accepted (implemented in Sprint 7, Units 2–7)
- Date: 2026-07-21

## Context

Sprints 5 and 6 established a durable transaction engine (`PackageImportTransactionService`) and structured observability (`ImportEventBus`). The transaction service owns journal transitions, file persistence, collection commits, rollback, and recovery. This separation must remain authoritative.

Future sprints will introduce image normalization, OCR, metadata extraction, and AI grading. These capabilities need a deterministic preprocessing pipeline that runs *before* the durable transaction boundary, without destabilizing the existing transaction, recovery, or event semantics.

A premature public plugin system would create unnecessary attack surface, compatibility commitments, and lifecycle complexity. The project is not ready to support third-party extensions.

## Decision

Introduce an **internal** `ProcessingStage` protocol and `ProcessingPipeline` for bounded, deterministic preprocessing before durable persistence. The framework is explicitly not a public plugin system.

### Key boundaries

1. **No public plugin API.** No dynamic module discovery, entry points, third-party Python code, plugin manifests, version negotiation, sandboxing, or code loaded from disk. The protocol is for internal stages only.
2. **Transaction service remains sole durable-state owner.** Stages must never update the transaction journal, mutate collection storage, invoke recovery, commit database state, delete source material, manipulate import locks, or perform rollback.
3. **Explicit inputs and outputs.** Stages receive `StageInput` and return `StageResult`. No mutable "god context" is shared across stages. Results are immutable and explicitly typed.
4. **Deterministic ordering.** Stage order is declared explicitly at pipeline construction. No inference from filesystem, class names, registration timing, or dependency injection.
5. **Fail-fast.** Unless explicitly defined as optional, a failed stage halts the workflow. No partial-success policies, retry frameworks, or "continue on error" behavior in Sprint 7.
6. **Cooperative cancellation at stage boundaries.** Cancellation is checked before and after each stage, and before handing prepared results to `TransactionService`. Once the transaction crosses its commit boundary, Sprint 6 cancellation semantics remain authoritative.
7. **Workspace ownership.** Stages may write only into a workflow-owned, path-contained temporary workspace. Cleanup occurs on success, failure, and cancellation. Source files remain immutable. Durable destination files are untouched until transaction execution.
8. **Event ownership unchanged.** Pipeline emits `PIPELINE_STARTED`, `STAGE_STARTED`, `STAGE_COMPLETED`, `STAGE_FAILED`, `PIPELINE_COMPLETED`, `PIPELINE_CANCELLED`. Existing transaction events (`IMPORT_STARTED`, `IMPORT_COMPLETE`, etc.) retain current semantics and ownership. No duplicate top-level events.
9. **Empty pipeline policy.** An empty processing pipeline is valid and behaves as an identity operation, returning the validated initial input unchanged.

## Consequences

- Image processing, OCR, and future AI stages will have a clean, deterministic seam to integrate without destabilizing durable persistence.
- Testing is simplified because stages are pure or workspace-bounded transformations with explicit inputs and outputs.
- The framework can be extracted into packages later if needed, but no third-party compatibility commitment is made now.
- Cancellation and failure semantics are predictable because stages are isolated and ordered.

## Rejected alternatives

- **Public plugin system:** Deferred until product and security requirements are defined.
- **Mutable shared context:** Rejected in favor of immutable `StageInput`/`StageResult` to prevent hidden coupling.
- **Parallel stage execution:** Rejected for Sprint 7 due to cancellation and ownership complexity with little benefit for trivial stages.
- **Resumable preprocessing:** Rejected. Only durable state (transaction journal) is resumable. Preprocessing is ephemeral.

## Reconsider When

Reconsider only through a separate approved design if:
- A user-validated workflow requires third-party extensions with defined security, versioning, and lifecycle policies.
- Parallel execution is justified by profiling data and a reviewed cancellation/ownership design.
- A stage needs to persist intermediate state across process restarts (making it durable, not preprocessing).

## Sprint 7 invariants

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

## Technical Debt Register

| Item | Location | Finding | Disposition |
|---|---|---|---|
| Duplicate `_check_cancelled` | `capture_import/transaction.py` lines 100–111 (origin: Sprint 6 review) | Two identical consecutive blocks; does not affect compilation or behavior | Note for cleanup; do not modify unless blocking |
| Chmod follows links in verified delete | `capture_import/_filesystem.py` (callers: `snapshot.py` `_delete_regular_file`, `workflow_workspace.py` `_delete_verified_file`; origin: Unit 5 review) | Cleanup chmods a path before the no-follow open; an attacker able to race filesystem entries could cause chmod to affect a substituted symlink target (permission tampering only; the subsequent no-follow open still fails closed). Unit 5 mirrors the frozen Sprint 5 pattern and neither worsens nor independently redesigns it. | Accepted (Minor): stages are trusted and the workspace is process-owned. Remediate in the shared filesystem primitive and validate against both snapshot and workspace cleanup. Must not be forgotten. |
| Uncapped pre-validation digest pass | `capture_import/workflow_stages.py` `_digest_handle` (origin: Unit 7 review M2) | An oversized source is fully hashed before `validate_stream` rejects it at limit+1 bytes; the coordinator's `_source_digest` caps mid-digest. The stage digest is deliberately policy-free so validation policy stays singular inside the validator. | Accepted (Minor): efficiency/robustness asymmetry only — no correctness, safety, or durability impact. Future remediation: cap the streaming digest at the validator's size budget in a dedicated optimization pass, without coupling stage behavior to validator policy. |
| Dynamic imports invisible to AST audit | `tests/test_workflow_reference_stages.py` durability-boundary audit (origin: Unit 7 review) | The structural import audit parses static `import`/`from` statements; `importlib.import_module()` or equivalent dynamic loading would be invisible to it. Dynamic/third-party code loading is currently forbidden by boundary 1 of this ADR. | Accepted (Minor): structural audit covers all static forms and fails closed on unrecognized ones. If dynamic loading is ever introduced (a separate approved design per "Reconsider When"), the audit must be extended with runtime import tracking first. |
| Adapter forwards only `request.source` | `capture_import/workflow_adapter.py` `commit_prepared_import` (origin: Unit 7 review O2) | `PreparedImport.files`/`metadata` are ephemeral workflow products and are not consumed by the durable path; the coordinator re-derives snapshot, validation, and preview from the source. Deliberate per the no-new-durability-semantics constraint. | Accepted (by design): no remediation required. Revisit only through an architecture amendment if a future stage's output must cross the durability boundary. |

