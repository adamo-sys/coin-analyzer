# Sprint 6 — Import Execution Engine & Observability

## Objective

Turn the durable persistence system into a complete import execution pipeline
with structured observability. Every major operation emits typed events for
progress UI, debugging, telemetry, and future plugin hooks.

## Architecture Dependency

| Foundation | Reference |
|---|---|
| Sprint 5 baseline | Commit `55817fd` |
| Architecture | Schema-2 Durable Persistence |
| Frozen spec hash | `A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4` |

## Deliverables

### Unit 1: Structured Event System ✅
- `capture_import/events.py` — typed event dataclasses, severity levels, event bus
- `tests/test_capture_import_events.py` — event recording, filtering, serialization
- **Status:** Implemented, 13 tests pass

### Unit 2: Event Integration into Transaction Service ✅
- Emit events at durable boundaries in `PackageImportTransactionService.execute()`
- Emit events during rollback paths
- **Status:** Implemented — IMPORT_STARTED, PACKAGE_VALIDATED, COLLECTION_CREATED, IMAGES_IMPORTED, COLLECTION_COMMITTED, IMPORT_COMPLETE, ROLLBACK_STARTED, ROLLBACK_COMPLETE, CANCELLED

### Unit 3: Event Integration into Recovery Service ✅
- Emit events during recovery reconciliation
- Emit progress events for long-running recovery
- **Status:** Implemented — RECOVERY_TRIGGERED, RECOVERY_COMPLETE, PROGRESS

### Unit 4: Execution Metrics ✅
- Per-stage timing captured via event timestamps
- Retry counts captured in RECOVERY_TRIGGERED context
- **Status:** Implemented — implicit via event system; explicit metrics via event querying

### Unit 5: Cancellation Support ✅
- `is_cancelled` callable parameter on transaction service
- `_check_cancelled()` helper at durable boundaries; cancellation invariant documented
- Event emission on cancellation
- **Status:** Implemented

## Risks

| Risk | Mitigation |
|---|---|
| Event emission overhead | Events are in-memory, off critical path; serialization is lazy |
| Event bus thread safety | Import lock already serializes; document assumption |
| Breaking existing tests | Full regression after each unit; no production behavior changes |

## Exit Criteria

- [x] All 10 event types are emitted from at least one code path
- [x] Events are queryable by type and severity
- [x] Progress events support UI rendering (current/total/stage)
- [x] Full regression: 211 tests pass (207 existing + 4 new integration)
- [x] No performance regression in import path

## Implementation Notes

- Events are immutable dataclasses with strict typing
- Event bus is in-memory only for Sprint 6; persistence is Sprint 6.x or later
- Severity ordering: DEBUG < INFO < WARNING < ERROR < CRITICAL
- Context fields are plain JSON-serializable types only
- Transaction and recovery services accept optional `event_bus`; no events emitted when None
- Cancellation checked at journal creation, image copy, and collection commit boundaries
- Cancellation invariant: cooperative only before commit; once COMMITTING_COLLECTION begins, execution must complete or enter recovery
- EventBus lifecycle: one instance per import session; must not be retained or reused across imports
