# Changelog

## Sprint 5 — Schema-2 Durable Persistence & Recovery Replay

**Commit:** `55817fd`  
**Date:** 2026-07-21

### Added

- **Schema-2 durable persistence** — append-only journal generation chains with immutable transitions, crash-safe publication, and identity-verified cleanup.
- **Recovery replay integration** — deterministic startup recovery for `RECOVERY_REQUIRED` and `ROLLBACK_FAILED` phases with bounded retry counters.
- **Recovery matrix RM-01–RM-41** — 41 crash-scenario contracts, each with a unique dedicated automated test (194 tests pass, 13 skipped POSIX).
- **Frozen architecture** — `docs/architecture/durable-persistence.md` at SHA-256 `A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4`.
- **Agent workflow** — `AGENTS.md` establishes architecture-first development, bounded units per prompt, focused validation, independent review, and explicit authorization gates.

### Changed

- `capture_import/enums.py`, `limits.py`, `lock.py`, `snapshot.py`, `_filesystem.py` — extended for schema-2 support.
- `coin_collection.py`, `coin_collection_gui.py` — integrated import lock and baseline-checked replacement.

---

## Sprint 6 — Import Execution Engine & Observability

**Depends on:**

| Foundation | Reference |
|---|---|
| Sprint 5 baseline | Commit `55817fd` |
| Architecture | Schema-2 Durable Persistence |
| Frozen spec hash | `A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4` |

### Added

- **`capture_import/events.py`** — Structured event system with 12 event types, 5 severity levels, immutable dataclasses, and in-memory event bus.
- **Event integration into transaction service** — `PackageImportTransactionService` emits `IMPORT_STARTED`, `PACKAGE_VALIDATED`, `COLLECTION_CREATED`, `IMAGES_IMPORTED`, `COLLECTION_COMMITTED`, `IMPORT_COMPLETE`, `ROLLBACK_STARTED`, `ROLLBACK_COMPLETE`, `CANCELLED`.
- **Event integration into recovery service** — `PackageImportRecoveryService` emits `RECOVERY_TRIGGERED`, `RECOVERY_COMPLETE`, `PROGRESS`.
- **Cancellation support** — Optional `is_cancelled` callable on transaction service; checked at durable boundaries; deterministic rollback on cancel.
- **Execution metrics** — Per-event timestamps enable stage timing; retry counts in recovery event context.

### Tests

- `tests/test_capture_import_events.py` — 13 tests, event system contracts
- `tests/test_capture_import_events_integration.py` — 4 tests, transaction and recovery event emission
- Full regression: 211 tests pass, 13 skipped (POSIX)

---

## Sprint 7 — Deterministic Import Workflow and Processing-Stage Framework

**Commit:** `3e61860`  
**Date:** 2026-07-21

**Depends on:**

| Foundation | Reference |
|---|---|
| Sprint 6 baseline | Commit `fd1682e` |
| Sprint 5 baseline | Commit `55817fd` |
| Architecture | Schema-2 Durable Persistence |
| Frozen spec hash | `A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4` |
| ADR | `docs/adr/ADR-007-internal-processing-stage-framework.md` (Accepted) |

### Added

- **Typed domain models** (`capture_import/workflow_models.py`) — `ImportRequest`, `StageInput`, `StageResult`, `PreparedImport`, `PreparedFile`, `StageArtifact` (Unit 2, `3bfcfec`/`785bf15`).
- **Stage protocol and pipeline validation** (`capture_import/workflow_pipeline.py`) — internal `ProcessingStage` protocol (not a public plugin API) and `ProcessingPipeline` with explicit ordering and unique-ID enforcement (Unit 3, `220dd98`).
- **Execution engine** (`capture_import/workflow_execution.py`) — sequential `ImportWorkflow` with cooperative cancellation at 2N+2 boundaries and the pipeline event family (`PIPELINE_STARTED`, `STAGE_STARTED`, `STAGE_COMPLETED`, `STAGE_FAILED`, `PIPELINE_COMPLETED`, `PIPELINE_CANCELLED`) (Unit 4, `71d0d8d`).
- **Workspace lifecycle** (`capture_import/workflow_workspace.py`) — workflow-owned, path-contained temporary workspace with ownership-verified, idempotent cleanup on success, failure, and cancellation (Unit 5, `2c67ee3`).
- **Transaction integration** — `PreparedImport` assembly (fail-closed plain-file verification) and a single durable handoff through a caller-supplied delegate, exactly once per execution; zero durable writes on failure or cancellation (Unit 6, `0617382`).
- **Reference stages and application adapter** (`capture_import/workflow_stages.py`, `capture_import/workflow_adapter.py`) — `PackageValidationStage` (race-aware source validation via the existing `CapturePackageValidator`), `ManifestPreparationStage` (normalized `prepared-manifest.json` via the existing manifest serializer/parser), deterministic `build_reference_pipeline()`, and the stateless one-way adapter onto the existing `PackageImportCoordinator.prepare()/commit()` seam (Unit 7, `3e61860`).

### Tests

- Sprint 7 focused suites: `test_workflow_models.py` (35), `test_workflow_pipeline.py` (22), `test_workflow_execution.py` (35), `test_workflow_workspace.py` (56), `test_workflow_integration.py` (28), `test_workflow_reference_stages.py` (36)
- Full regression (authoritative root discovery, `python -m unittest discover -s . -p "test_*.py"`): **2045 tests pass, 17 skipped** (POSIX-specific and platform-gated)
- No Sprint 5/6 behavior was modified (`events.py` extended additively only); transaction, rollback, recovery, journal, and event semantics remain unchanged
- Technical debt explicitly tracked in the ADR-007 register (chmod-before-no-follow race, pre-validation digest efficiency, AST-audit dynamic-import scope, adapter source forwarding)

### Explicitly Out of Scope

- OCR, AI grading, image enhancement, EXIF parsing, perceptual hashing
- Numista integration, networking, cloud services, GUI
- Third-party plugins, dynamic stage discovery, parallel execution
- Retries, resumable preprocessing, caching, persistent event storage
- Changes to Schema-2 recovery semantics

### Roadmap

See `docs/roadmap/PRODUCT_ROADMAP.md` for the forward plan.
