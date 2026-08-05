# Coin Analyzer Roadmap

This roadmap records durable direction, not sprint commitments. Detailed work belongs in issues or an approved implementation plan.

## Recently Completed

- **Sprint 19 — OCR Review Schema Stabilization and Boundary Enforcement (branch milestone)**
  - Canonical OCR field identity stabilization and consumer adoption.
  - Frozen Sprint 19 policy units for DTO schema-versioning, migration, test builders, oversized test split, and package boundaries.
  - OCR review candidate-review split into behavior modules (`shortcuts`, `callbacks`, `preview`) with preserved discovery baseline.
  - AST-based OCR review package-boundary enforcement suite added.
  - Branch commits: `829aa1a`, `5c7350f`, `80239e8`, `70b93a3`, `e05a148`, `21aed59`, `5c39109`, `77f498e`, `c6147fa`, `62c9064`, `6181f89`, `8e7888a`, `411686f`, `73f971c`.
  - Authoritative full-regression closure is pending.

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

<!-- SPRINT-8-CLOSEOUT-2026-07-25 -->
1. **Sprint 9 - OCR + Metadata Extraction**
   - OCR orchestration and metadata reconciliation.
   - Collector review remains mandatory before authoritative collection mutation.
   - Requires an approved architecture and implementation plan.

2. **Sprint 10 - Grading Engine**
   - Wear estimation, cleaning detection, rim damage, strike quality, and luster estimation.
   - Advisory-only until explicitly approved otherwise.

3. **Sprint 11 - Dealer Tools**
   - Valuation workflow, market lookup contracts, ROI analysis, duplicate inventory, and export.
   - Live data or external providers require separate architecture approval.

4. **Recruiter-focused README audit**
   - Improve the repository front door without overstating unsupported AI capabilities.

5. **ADR index**
   - Add lightweight navigation for accepted architecture decisions.

6. **Portfolio-focused release milestone**
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
