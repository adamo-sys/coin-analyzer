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

## Sprint 7 — Image Processing Pipeline (Planned)

| Sprint | Focus | Builds On |
|---|---|---|
| 7 | Image Processing Pipeline | Sprint 6 pipeline |
| 8 | OCR + Metadata Extraction | Sprint 7 images |
| 9 | Grading Engine | Sprint 8 metadata |
| 10 | Dealer Tools (valuation, market, ROI) | Sprint 9 grades |

**Depends on:**

| Foundation | Reference |
|---|---|
| Sprint 5 baseline | Commit `55817fd` |
| Architecture | Schema-2 Durable Persistence |
| Frozen spec hash | `A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4` |

### Objective

Turn the durable persistence system into a complete import execution pipeline with structured observability.

### Planned Deliverables

- **Transactional import coordinator** — multi-stage execution pipeline leveraging Sprint 5 replay guarantees.
- **Structured event system** — `ImportStarted`, `PackageValidated`, `CollectionCreated`, `ImagesImported`, `OCRStarted`, `OCRComplete`, `RecoveryTriggered`, `RollbackStarted`, `RollbackComplete`, `ImportComplete`.
- **Progress persistence** — resume interrupted imports from any durable boundary.
- **Cancellation support** — graceful abort with deterministic rollback.
- **Execution metrics** — per-stage timing, retry counts, failure rates.

### Why Now

Sprint 5 guarantees durability and replay. Sprint 6 uses those guarantees to build a user-visible, observable, and resumable import pipeline.

### Proposed Roadmap

| Sprint | Focus | Builds On |
|---|---|---|
| 6 | Import Execution Engine & Observability | Sprint 5 durability |
| 7 | Image Processing Pipeline | Sprint 6 pipeline |
| 8 | OCR + Metadata Extraction | Sprint 7 images |
| 9 | Grading Engine | Sprint 8 metadata |
| 10 | Dealer Tools (valuation, market, ROI) | Sprint 9 grades |
