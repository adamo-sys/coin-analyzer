# Coin Analyzer Roadmap

This roadmap records durable direction, not sprint commitments. Detailed work belongs in issues or an approved implementation plan.

## Recently Completed

- **Sprint 5 — Schema-2 Durable Persistence & Recovery Replay**
  - Append-only journal generation chains with immutable transitions
  - Deterministic startup recovery for `RECOVERY_REQUIRED` and `ROLLBACK_FAILED`
  - 41-scenario recovery matrix (RM-01–RM-41) with unique dedicated tests
  - Frozen architecture spec and agent workflow (`AGENTS.md`)
  - Commit: `55817fd`

- Acquisition tracking with exact decimal costs and backward-compatible persistence
- Collector discovery and confirmed-observation foundations
- Collection toolbar usability improvement
- Local runtime-data hygiene for `data/collection.json`
- Debug-output cleanup and OCR experiment hardening
- Architecture reconciliation against the implemented system and ADRs
- Portfolio Analytics with exact acquisition-cost coverage and comparable-CAD reporting
- Ask My Collection grounded, read-only MVP for inventory, collection intelligence, and portfolio questions

- Acquisition tracking with exact decimal costs and backward-compatible persistence
- Collector discovery and confirmed-observation foundations
- Collection toolbar usability improvement
- Local runtime-data hygiene for `data/collection.json`
- Debug-output cleanup and OCR experiment hardening
- Architecture reconciliation against the implemented system and ADRs
- Portfolio Analytics with exact acquisition-cost coverage and comparable-CAD reporting
- Ask My Collection grounded, read-only MVP for inventory, collection intelligence, and portfolio questions

## Next

1. **Sprint 6 — Import Execution Engine & Observability**
   - Transactional import coordinator with multi-stage pipeline
   - Structured event system (`ImportStarted`, `PackageValidated`, `ImagesImported`, `OCRStarted`, `OCRComplete`, `RecoveryTriggered`, `RollbackStarted`, `RollbackComplete`, `ImportComplete`)
   - Progress persistence and resume from any durable boundary
   - Cancellation support with deterministic rollback
   - Execution metrics (per-stage timing, retry counts, failure rates)
   - Depends on Sprint 5 baseline (`55817fd`) and frozen architecture hash `A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4`

2. **Sprint 7 — Image Processing Pipeline**
   - Image normalization, crop detection, obverse/reverse pairing
   - Duplicate detection improvements, image quality scoring

3. **Sprint 8 — OCR + Metadata Extraction**
   - OCR orchestration, metadata reconciliation

4. **Sprint 9 — Grading Engine**
   - Wear estimation, cleaning detection, rim damage, strike quality, luster estimation

5. **Sprint 10 — Dealer Tools**
   - Valuation, market lookup, ROI, duplicate inventory, export

1. Recruiter-focused README audit
   - Review the repository front door after the grounded assistant milestone without overstating unsupported AI capabilities.
2. ADR index
   - Add a lightweight navigation page for accepted architecture decisions.
3. Portfolio-focused release milestone
   - Prepare validated release notes, screenshots, setup guidance, and migration notes where required.

## Later Candidates

- Collection Intelligence refinements
- Ask My Collection capability expansion only after MVP evaluation
- Market Intelligence improvements
- Portfolio surface consolidation

Candidates are not approved scope. Each requires repository inspection, explicit acceptance criteria, and a reviewed implementation plan.

## Completed Capability Areas

Coin Analyzer already includes local collection management, acquisition tracking, photo workflows, deterministic collection intelligence, reference-provider foundations, collector workflows, reporting, backup tooling, and regression coverage.

See [`PROJECT_STATE.md`](PROJECT_STATE.md) for current implementation status and [`docs/releases/`](docs/releases/) for historical releases.
